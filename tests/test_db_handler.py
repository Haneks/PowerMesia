"""Tests de la bibliothèque de chants (tools/db_handler.py)."""

import sqlite3

import pytest

from context.models import Chant, MomentLiturgique, SectionChant, TypeSection
from tools.db_handler import (
    SCHEMA_VERSION,
    create_chant,
    get_chant,
    init_db,
    search_chants,
    update_chant,
)

# Schéma d'avant cette livraison (avec la contrainte CHECK sur les moments)
OLD_SCHEMA = """
CREATE TABLE chants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    paroles TEXT NOT NULL,
    auteur TEXT, compositeur TEXT, reference TEXT, notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE chant_moments (
    chant_id INTEGER NOT NULL,
    moment TEXT NOT NULL CHECK (moment IN ('entree', 'offertoire', 'communion', 'envoi', 'autre')),
    PRIMARY KEY (chant_id, moment),
    FOREIGN KEY (chant_id) REFERENCES chants(id) ON DELETE CASCADE
);
CREATE INDEX idx_chants_titre ON chants(titre);
CREATE INDEX idx_chant_moments_moment ON chant_moments(moment);
"""


@pytest.fixture
def db(tmp_path):
    return tmp_path / "chants.db"


def _structured_chant() -> Chant:
    return Chant(
        titre="Gloire à Dieu",
        paroles="refrain\n\ncouplet",
        recueil="Lyon centre 4",
        structure=[
            SectionChant("R", TypeSection.REFRAIN, ["Gloire à Dieu"]),
            SectionChant("1", TypeSection.COUPLET, ["Nous te louons"]),
        ],
        ordre=["R", "1", "R"],
        moments=[MomentLiturgique.GLOIRE],
    )


def _user_version(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_structured_chant_roundtrip(db):
    chant_id = create_chant(_structured_chant(), db)
    chant = get_chant(chant_id, db)
    assert chant.recueil == "Lyon centre 4"
    assert [s.id for s in chant.structure] == ["R", "1"]
    assert chant.structure[0].type is TypeSection.REFRAIN
    assert chant.ordre == ["R", "1", "R"]
    assert chant.moments == [MomentLiturgique.GLOIRE]


def test_chant_without_structure_still_works(db):
    chant_id = create_chant(Chant(titre="Simple", paroles="un\ndeux"), db)
    chant = get_chant(chant_id, db)
    assert chant.paroles == "un\ndeux"
    assert chant.structure == [] and chant.ordre == [] and chant.recueil is None


def test_search_returns_structure(db):
    create_chant(_structured_chant(), db)
    [found] = search_chants(query="Gloire", db_path=db)
    assert found.ordre == ["R", "1", "R"] and found.recueil == "Lyon centre 4"


def test_search_by_new_moment(db):
    create_chant(_structured_chant(), db)
    assert len(search_chants(moment=MomentLiturgique.GLOIRE, db_path=db)) == 1
    assert search_chants(moment=MomentLiturgique.PARDON, db_path=db) == []


def test_update_persists_and_clears_structure(db):
    chant_id = create_chant(_structured_chant(), db)
    chant = get_chant(chant_id, db)
    chant.recueil = "Lyon centre 5"
    update_chant(chant, db)
    assert get_chant(chant_id, db).recueil == "Lyon centre 5"
    assert get_chant(chant_id, db).ordre == ["R", "1", "R"]

    chant.set_paroles("tout autre texte")
    update_chant(chant, db)
    assert get_chant(chant_id, db).structure == []
    assert get_chant(chant_id, db).ordre == []


def test_fresh_database_is_versioned_and_accepts_new_moments(db):
    init_db(db)
    assert _user_version(db) == SCHEMA_VERSION
    chant_id = create_chant(Chant(titre="K", paroles="p", moments=[MomentLiturgique.AGNEAU]), db)
    assert get_chant(chant_id, db).moments == [MomentLiturgique.AGNEAU]


def test_old_database_is_migrated_without_data_loss(db):
    conn = sqlite3.connect(db)
    conn.executescript(OLD_SCHEMA)
    conn.execute("INSERT INTO chants (titre, paroles, reference) VALUES ('Ancien', 'paroles', 'B 12')")
    conn.execute("INSERT INTO chant_moments VALUES (1, 'entree')")
    conn.commit()
    conn.close()

    init_db(db)

    old = get_chant(1, db)
    assert (old.titre, old.paroles, old.reference) == ("Ancien", "paroles", "B 12")
    assert old.moments == [MomentLiturgique.ENTREE]
    assert old.structure == [] and old.recueil is None
    # La contrainte CHECK a disparu : un nouveau moment est accepté
    new_id = create_chant(Chant(titre="Neuf", paroles="p", moments=[MomentLiturgique.PARDON]), db)
    assert get_chant(new_id, db).moments == [MomentLiturgique.PARDON]
    assert _user_version(db) == SCHEMA_VERSION


def test_init_db_is_idempotent(db):
    init_db(db)
    chant_id = create_chant(_structured_chant(), db)
    init_db(db)
    init_db(db)
    assert get_chant(chant_id, db).ordre == ["R", "1", "R"]
