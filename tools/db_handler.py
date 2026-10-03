"""
Gestion de la bibliothèque de chants - SQLite.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

from context.models import Chant, MomentLiturgique
from tools.chant_structure import (
    ordre_from_json,
    ordre_to_json,
    structure_from_json,
    structure_to_json,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = os.environ.get("DATA_DIR")
if _DATA_DIR:
    _DATA_PATH = Path(_DATA_DIR)
else:
    _DATA_PATH = PROJECT_ROOT / "data"
DEFAULT_DB = _DATA_PATH / "chants.db"
SCHEMA_PATH = PROJECT_ROOT / "context" / "chant_schema.sql"

# Version du schéma (PRAGMA user_version). 1 : recueil, structure, ordre, moments sans CHECK.
SCHEMA_VERSION = 1


def _ensure_data_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _get_connection(db_path: Optional[Path] = None) -> tuple[sqlite3.Connection, Path]:
    path = db_path or DEFAULT_DB
    _ensure_data_dir(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, path


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialise la base avec le schéma et migre une base plus ancienne (sans perte)."""
    conn, _ = _get_connection(db_path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        _migrate(conn)
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Met à niveau une base créée avec un schéma plus ancien. Transactionnelle et idempotente."""
    if conn.execute("PRAGMA user_version").fetchone()[0] >= SCHEMA_VERSION:
        return
    try:
        conn.execute("BEGIN")
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(chants)")}
        for column in ("recueil", "structure", "ordre"):
            if column not in existing:
                conn.execute(f"ALTER TABLE chants ADD COLUMN {column} TEXT")

        moments_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'chant_moments'"
        ).fetchone()["sql"]
        if "CHECK" in moments_sql.upper():
            # SQLite ne permet pas de retirer une contrainte : on reconstruit la table.
            conn.execute(
                """
                CREATE TABLE chant_moments_new (
                    chant_id INTEGER NOT NULL,
                    moment TEXT NOT NULL,
                    PRIMARY KEY (chant_id, moment),
                    FOREIGN KEY (chant_id) REFERENCES chants(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("INSERT INTO chant_moments_new SELECT chant_id, moment FROM chant_moments")
            conn.execute("DROP TABLE chant_moments")
            conn.execute("ALTER TABLE chant_moments_new RENAME TO chant_moments")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chant_moments_moment ON chant_moments(moment)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _row_to_chant(conn: sqlite3.Connection, row: sqlite3.Row) -> Chant:
    moments_rows = conn.execute(
        "SELECT moment FROM chant_moments WHERE chant_id = ?", (row["id"],)
    ).fetchall()
    return Chant(
        id=row["id"],
        titre=row["titre"],
        paroles=row["paroles"],
        auteur=row["auteur"],
        compositeur=row["compositeur"],
        reference=row["reference"],
        notes=row["notes"],
        moments=[MomentLiturgique(r["moment"]) for r in moments_rows],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        recueil=row["recueil"],
        structure=structure_from_json(row["structure"]),
        ordre=ordre_from_json(row["ordre"]),
    )


def create_chant(chant: Chant, db_path: Optional[Path] = None) -> int:
    """Insère un chant et retourne son id."""
    init_db(db_path)
    conn, _ = _get_connection(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO chants (titre, paroles, auteur, compositeur, reference, notes,
                                recueil, structure, ordre)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chant.titre,
                chant.paroles,
                chant.auteur,
                chant.compositeur,
                chant.reference,
                chant.notes,
                chant.recueil,
                structure_to_json(chant.structure),
                ordre_to_json(chant.ordre),
            ),
        )
        chant_id = cur.lastrowid
        for m in chant.moments:
            conn.execute(
                "INSERT INTO chant_moments (chant_id, moment) VALUES (?, ?)",
                (chant_id, m.value),
            )
        conn.commit()
        return chant_id
    finally:
        conn.close()


def get_chant(chant_id: int, db_path: Optional[Path] = None) -> Optional[Chant]:
    """Récupère un chant par id."""
    conn, _ = _get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM chants WHERE id = ?", (chant_id,)).fetchone()
        return _row_to_chant(conn, row) if row else None
    finally:
        conn.close()


def update_chant(chant: Chant, db_path: Optional[Path] = None) -> bool:
    """Met à jour un chant existant."""
    if chant.id is None:
        return False
    conn, _ = _get_connection(db_path)
    try:
        conn.execute(
            """
            UPDATE chants
            SET titre=?, paroles=?, auteur=?, compositeur=?, reference=?, notes=?,
                recueil=?, structure=?, ordre=?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                chant.titre,
                chant.paroles,
                chant.auteur,
                chant.compositeur,
                chant.reference,
                chant.notes,
                chant.recueil,
                structure_to_json(chant.structure),
                ordre_to_json(chant.ordre),
                chant.id,
            ),
        )
        conn.execute("DELETE FROM chant_moments WHERE chant_id = ?", (chant.id,))
        for m in chant.moments:
            conn.execute(
                "INSERT INTO chant_moments (chant_id, moment) VALUES (?, ?)",
                (chant.id, m.value),
            )
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def delete_chant(chant_id: int, db_path: Optional[Path] = None) -> bool:
    """Supprime un chant."""
    conn, _ = _get_connection(db_path)
    try:
        conn.execute("DELETE FROM chant_moments WHERE chant_id = ?", (chant_id,))
        conn.execute("DELETE FROM chants WHERE id = ?", (chant_id,))
        conn.commit()
        return conn.total_changes > 0
    finally:
        conn.close()


def search_chants(
    query: Optional[str] = None,
    moment: Optional[MomentLiturgique] = None,
    db_path: Optional[Path] = None,
) -> list[Chant]:
    """Recherche des chants par titre/paroles/référence ou par moment."""
    conn, _ = _get_connection(db_path)
    try:
        sql = """
            SELECT DISTINCT c.* FROM chants c
            LEFT JOIN chant_moments cm ON c.id = cm.chant_id
            WHERE 1=1
        """
        params: list = []
        if query:
            q = f"%{query}%"
            sql += " AND (c.titre LIKE ? OR c.paroles LIKE ? OR c.reference LIKE ?)"
            params.extend([q, q, q])
        if moment:
            sql += " AND cm.moment = ?"
            params.append(moment.value)

        sql += " ORDER BY c.titre"

        return [_row_to_chant(conn, row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def list_all_chants(db_path: Optional[Path] = None) -> list[Chant]:
    """Liste tous les chants."""
    return search_chants(db_path=db_path)
