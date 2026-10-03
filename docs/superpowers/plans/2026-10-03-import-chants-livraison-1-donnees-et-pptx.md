# Import de chants — Livraison 1 : données et PowerPoint — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** Un chant peut porter une structure (refrain, couplets, pont), un ordre chanté et un recueil ; le PowerPoint écrit les refrains en gras et les répète après chaque couplet.

**Architecture :** Le modèle `Chant` gagne `recueil`, `structure` (sections) et `ordre`. Un module pur `tools/chant_structure.py` sérialise la structure, calcule l'ordre chanté et déroule les lignes à projeter. La base SQLite est migrée sans perte (`PRAGMA user_version`). Le découpeur de slides reçoit une variante qui garde l'indicateur « gras » de chaque ligne. Aucune nouvelle interface utilisateur : la saisie de structures viendra avec l'import (livraisons 2 et 3).

**Tech Stack :** Python 3.11 (image Docker) / 3.13 (poste), sqlite3, python-pptx, pytest, Streamlit `AppTest` pour le test de fumée. **Aucune nouvelle dépendance.**

**Spec :** `docs/superpowers/specs/2026-10-03-import-chants-design.md` (§5 modèle de données, §6 « Ordre chanté », §7 PowerPoint, §10 étape 1)

## Global Constraints

- Les chants sans `structure` restent valides et se génèrent comme aujourd'hui (paroles à plat, pas de gras).
- `paroles` est conservé : texte à plat des sections dans l'ordre du document, refrain une fois.
- Moments liturgiques : `entree`, `pardon`, `gloire`, `psaume`, `alleluia`, `pu`, `offertoire`, `sanctus`, `anamnese`, `agneau`, `communion`, `envoi`, `autre` (valeurs existantes inchangées). La contrainte `CHECK` de `chant_moments` est supprimée ; la validation passe par l'énumération `MomentLiturgique`.
- Migration : `PRAGMA user_version`, dans `init_db()`, transactionnelle, sans perte, idempotente.
- Ordre chanté : refrain inséré après chaque couplet ou pont ; s'il ouvre le chant, il est aussi joué en premier (`R 1 R 2 R P R`, `1 R 2 R`). Plusieurs sections refrain ou aucune : ordre du document. Case « répéter le refrain » décochée : ordre du document.
- PowerPoint : Calibri 54 noir, 150 caractères maximum par slide, 6 lignes affichées au plus, titre `[Titre] - x/y`, refrain en gras, coupure préférée entre sections.
- **Aucun fichier du corpus ni aucune parole réelle dans le dépôt** (public) : les tests utilisent des textes inventés.
- Les messages de commit finissent par la ligne `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Commandes lancées depuis la racine du dépôt : `python -m pytest …`. Code et commentaires en français, comme l'existant.

**Branche de travail :** après fusion de la branche `docs/spec-import-chants` (spec + plan) dans `main`, créer `feat/chants-structure` depuis `main`.

## Carte des fichiers

| Fichier | Action | Responsabilité |
|---|---|---|
| `context/models.py` | modifier | `MomentLiturgique` étendu, `TypeSection`, `SectionChant`, champs `recueil` / `structure` / `ordre`, `Chant.set_paroles` |
| `tools/chant_structure.py` | créer | JSON ↔ sections, `compute_ordre`, `paroles_from_structure`, `expand_lines` |
| `context/chant_schema.sql` | modifier | schéma des bases neuves |
| `tools/db_handler.py` | modifier | migration, lecture/écriture des nouveaux champs |
| `tools/slicing.py` | modifier | `split_lines_for_slides`, coût d'une coupure au milieu d'un couplet |
| `tools/pptx_generator.py` | modifier | gras par ligne, chants structurés |
| `app.py` | modifier | liste des moments, transmission de `structure` / `ordre`, édition des paroles |
| `tests/conftest.py` | créer | `DATA_DIR` / `OUTPUT_DIR` temporaires pour les tests |
| `tests/test_models.py`, `test_chant_structure.py`, `test_db_handler.py`, `test_split_lines.py`, `test_app_smoke.py` | créer | tests |
| `tests/test_pptx_generator.py` | modifier | tests des chants structurés |
| `scripts/demo_refrain_pptx.py` | créer | génère un PPTX de démonstration à ouvrir dans PowerPoint |
| `hardprompts/slicing_rules.md`, `README.md`, `ARBORESCENCE.md` | modifier | documentation |

---

### Task 1: Modèle `Chant` — moments, sections, structure, ordre

**Files:**
- Modify: `context/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - `MomentLiturgique` : membres `ENTREE, PARDON, GLOIRE, PSAUME, ALLELUIA, PU, OFFERTOIRE, SANCTUS, ANAMNESE, AGNEAU, COMMUNION, ENVOI, AUTRE`
  - `TypeSection(Enum)` : `REFRAIN="refrain"`, `COUPLET="couplet"`, `PONT="pont"`
  - `SectionChant(id: str, type: TypeSection, lignes: list[str])` avec `to_dict() -> dict` et `SectionChant.from_dict(d: dict) -> SectionChant`
  - `Chant.recueil: Optional[str]`, `Chant.structure: list[SectionChant]`, `Chant.ordre: list[str]`
  - `Chant.set_paroles(nouvelles_paroles: str) -> bool` (True si une structure a été supprimée)

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_models.py` :

```python
"""Tests du modèle de chant (context/models.py)."""

from context.models import Chant, MomentLiturgique, SectionChant, TypeSection


def _sections() -> list[SectionChant]:
    return [
        SectionChant("R", TypeSection.REFRAIN, ["ligne refrain 1", "ligne refrain 2"]),
        SectionChant("1", TypeSection.COUPLET, ["ligne couplet"]),
    ]


def test_new_liturgical_moments_exist_and_old_ones_are_unchanged():
    values = {m.value for m in MomentLiturgique}
    assert values >= {"pardon", "gloire", "psaume", "alleluia", "pu", "sanctus", "anamnese", "agneau"}
    assert values >= {"entree", "offertoire", "communion", "envoi", "autre"}
    assert MomentLiturgique("entree") is MomentLiturgique.ENTREE


def test_chant_has_empty_structure_by_default():
    chant = Chant(titre="T", paroles="p")
    assert chant.recueil is None
    assert chant.structure == []
    assert chant.ordre == []


def test_chant_roundtrip_through_dict_keeps_structure():
    chant = Chant(
        titre="T",
        paroles="p",
        recueil="Lyon centre 4",
        structure=_sections(),
        ordre=["R", "1", "R"],
        moments=[MomentLiturgique.PARDON],
    )
    assert Chant.from_dict(chant.to_dict()) == chant


def test_from_dict_accepts_old_dicts_without_structure():
    chant = Chant.from_dict({"titre": "T", "paroles": "p"})
    assert chant.structure == [] and chant.ordre == [] and chant.recueil is None


def test_set_paroles_unchanged_text_keeps_structure():
    chant = Chant(titre="T", paroles="a", structure=_sections(), ordre=["R", "1"])
    assert chant.set_paroles("a") is False
    assert chant.structure and chant.ordre == ["R", "1"]


def test_set_paroles_changed_text_drops_structure():
    chant = Chant(titre="T", paroles="a", structure=_sections(), ordre=["R", "1"])
    assert chant.set_paroles("autre texte") is True
    assert chant.paroles == "autre texte"
    assert chant.structure == [] and chant.ordre == []


def test_set_paroles_without_structure_just_updates_text():
    chant = Chant(titre="T", paroles="a")
    assert chant.set_paroles("b") is False
    assert chant.paroles == "b"
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_models.py -q`
Expected: erreur de collecte `ImportError: cannot import name 'SectionChant'`.

- [ ] **Step 3: Implémenter**

Dans `context/models.py`, remplacer l'énumération `MomentLiturgique` par :

```python
class MomentLiturgique(Enum):
    """Moment de la messe où le chant est utilisé."""
    ENTREE = "entree"
    PARDON = "pardon"
    GLOIRE = "gloire"
    PSAUME = "psaume"
    ALLELUIA = "alleluia"
    PU = "pu"
    OFFERTOIRE = "offertoire"
    SANCTUS = "sanctus"
    ANAMNESE = "anamnese"
    AGNEAU = "agneau"
    COMMUNION = "communion"
    ENVOI = "envoi"
    AUTRE = "autre"


class TypeSection(Enum):
    """Type d'une section de chant."""
    REFRAIN = "refrain"
    COUPLET = "couplet"
    PONT = "pont"


@dataclass
class SectionChant:
    """Une section d'un chant : refrain, couplet ou pont."""
    id: str
    type: TypeSection
    lignes: list[str]

    def to_dict(self) -> dict:
        return {"id": self.id, "type": self.type.value, "lignes": list(self.lignes)}

    @classmethod
    def from_dict(cls, d: dict) -> "SectionChant":
        return cls(id=d["id"], type=TypeSection(d["type"]), lignes=list(d.get("lignes", [])))
```

Dans la classe `Chant`, ajouter après `updated_at` :

```python
    recueil: Optional[str] = None  # Ex: "Lyon centre 4"
    structure: list[SectionChant] = field(default_factory=list)
    ordre: list[str] = field(default_factory=list)  # Ex: ["R", "1", "R", "2", "R"]
```

Dans `Chant.to_dict`, ajouter avant la dernière accolade :

```python
            "recueil": self.recueil,
            "structure": [s.to_dict() for s in self.structure],
            "ordre": list(self.ordre),
```

Dans `Chant.from_dict`, ajouter aux arguments du `cls(...)` final :

```python
            recueil=d.get("recueil"),
            structure=[SectionChant.from_dict(s) for s in d.get("structure") or []],
            ordre=list(d.get("ordre") or []),
```

Ajouter la méthode à `Chant`, après `from_dict` :

```python
    def set_paroles(self, nouvelles_paroles: str) -> bool:
        """
        Remplace les paroles. Si le texte change, la structure (refrains) ne correspond
        plus : elle est supprimée. Retourne True si une structure a été supprimée.
        """
        changed = nouvelles_paroles != self.paroles
        self.paroles = nouvelles_paroles
        if changed and self.structure:
            self.structure, self.ordre = [], []
            return True
        return False
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_models.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add context/models.py tests/test_models.py
git commit -m "feat: modèle de chant avec structure, ordre, recueil et nouveaux moments" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Module `tools/chant_structure.py`

**Files:**
- Create: `tools/chant_structure.py`
- Test: `tests/test_chant_structure.py`

**Interfaces:**
- Consumes: `SectionChant`, `TypeSection` (Task 1)
- Produces:
  - `BlocLine = tuple[str, bool]` — (texte, gras) ; `("", False)` sépare deux sections
  - `sections_to_dicts(sections: list[SectionChant]) -> list[dict]`, `sections_from_dicts(dicts: list[dict]) -> list[SectionChant]`
  - `structure_to_json(sections) -> Optional[str]`, `structure_from_json(raw: Optional[str]) -> list[SectionChant]`
  - `ordre_to_json(ordre: list[str]) -> Optional[str]`, `ordre_from_json(raw: Optional[str]) -> list[str]`
  - `compute_ordre(sections: list[SectionChant], repeat_refrain: bool = True) -> list[str]`
  - `paroles_from_structure(sections: list[SectionChant]) -> str`
  - `expand_lines(sections: list[SectionChant], ordre: list[str]) -> list[BlocLine]`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_chant_structure.py` :

```python
"""Tests de tools/chant_structure.py."""

import logging

from context.models import SectionChant, TypeSection
from tools.chant_structure import (
    compute_ordre,
    expand_lines,
    ordre_from_json,
    ordre_to_json,
    paroles_from_structure,
    sections_from_dicts,
    sections_to_dicts,
    structure_from_json,
    structure_to_json,
)

R = SectionChant("R", TypeSection.REFRAIN, ["refrain"])
C1 = SectionChant("1", TypeSection.COUPLET, ["couplet 1"])
C2 = SectionChant("2", TypeSection.COUPLET, ["couplet 2"])
P = SectionChant("P", TypeSection.PONT, ["pont"])


# --- compute_ordre ---

def test_refrain_opening_the_song_is_played_first_and_after_each_section():
    assert compute_ordre([R, C1, C2, P]) == ["R", "1", "R", "2", "R", "P", "R"]


def test_refrain_after_first_couplet():
    assert compute_ordre([C1, R, C2]) == ["1", "R", "2", "R"]


def test_no_refrain_keeps_document_order():
    assert compute_ordre([C1, C2, P]) == ["1", "2", "P"]


def test_several_refrain_sections_keep_document_order():
    r2 = SectionChant("R2", TypeSection.REFRAIN, ["autre refrain"])
    assert compute_ordre([R, C1, r2, C2]) == ["R", "1", "R2", "2"]


def test_repeat_disabled_keeps_document_order():
    assert compute_ordre([R, C1, C2], repeat_refrain=False) == ["R", "1", "2"]


def test_only_a_refrain():
    assert compute_ordre([R]) == ["R"]


def test_empty_structure():
    assert compute_ordre([]) == []


# --- sérialisation ---

def test_structure_json_roundtrip():
    raw = structure_to_json([R, C1])
    assert structure_from_json(raw) == [R, C1]


def test_empty_structure_is_stored_as_none_and_read_back_as_empty():
    assert structure_to_json([]) is None
    assert structure_from_json(None) == []
    assert structure_from_json("") == []


def test_ordre_json_roundtrip():
    assert ordre_from_json(ordre_to_json(["R", "1", "R"])) == ["R", "1", "R"]
    assert ordre_to_json([]) is None
    assert ordre_from_json(None) == []


def test_sections_dict_roundtrip():
    assert sections_from_dicts(sections_to_dicts([R, P])) == [R, P]


# --- paroles à plat et lignes à projeter ---

def test_paroles_from_structure_lists_each_section_once():
    assert paroles_from_structure([R, C1]) == "refrain\n\ncouplet 1"


def test_expand_lines_marks_refrain_bold_and_separates_sections():
    lines = expand_lines([R, C1], ["R", "1", "R"])
    assert lines == [
        ("refrain", True), ("", False), ("couplet 1", False), ("", False), ("refrain", True),
    ]


def test_expand_lines_skips_unknown_section_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        lines = expand_lines([R], ["R", "X", "R"])
    assert lines == [("refrain", True), ("", False), ("refrain", True)]
    assert "X" in caplog.text
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_chant_structure.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.chant_structure'`.

- [ ] **Step 3: Implémenter**

Créer `tools/chant_structure.py` :

```python
"""
Structure d'un chant (refrain, couplets, pont) : sérialisation JSON, ordre chanté
et lignes à projeter.
"""

import json
import logging
from typing import Optional

from context.models import SectionChant, TypeSection

logger = logging.getLogger(__name__)

# (texte, gras). Une ligne vide ("", False) sépare deux sections.
BlocLine = tuple[str, bool]


def sections_to_dicts(sections: list[SectionChant]) -> list[dict]:
    return [s.to_dict() for s in sections]


def sections_from_dicts(dicts: list[dict]) -> list[SectionChant]:
    return [SectionChant.from_dict(d) for d in dicts]


def structure_to_json(sections: list[SectionChant]) -> Optional[str]:
    if not sections:
        return None
    return json.dumps({"sections": sections_to_dicts(sections)}, ensure_ascii=False)


def structure_from_json(raw: Optional[str]) -> list[SectionChant]:
    if not raw:
        return []
    return sections_from_dicts(json.loads(raw)["sections"])


def ordre_to_json(ordre: list[str]) -> Optional[str]:
    return json.dumps(ordre, ensure_ascii=False) if ordre else None


def ordre_from_json(raw: Optional[str]) -> list[str]:
    return list(json.loads(raw)) if raw else []


def compute_ordre(sections: list[SectionChant], repeat_refrain: bool = True) -> list[str]:
    """
    Ordre chanté d'un chant.
    - Un seul refrain : il est inséré après chaque couplet ou pont ; s'il ouvre le chant,
      il est aussi joué en premier (R 1 R 2 R P R ; ou 1 R 2 R si le refrain suit le couplet 1).
    - Aucun refrain, plusieurs sections refrain (ordre explicite du document) ou
      repeat_refrain=False : ordre du document.
    """
    ids = [s.id for s in sections]
    refrains = [s for s in sections if s.type is TypeSection.REFRAIN]
    if not repeat_refrain or len(refrains) != 1:
        return ids
    refrain = refrains[0]
    ordre = [refrain.id] if sections[0] is refrain else []
    for section in sections:
        if section is not refrain:
            ordre += [section.id, refrain.id]
    return ordre


def paroles_from_structure(sections: list[SectionChant]) -> str:
    """Texte à plat : sections dans l'ordre du document, refrain une seule fois."""
    return "\n\n".join("\n".join(s.lignes) for s in sections)


def expand_lines(sections: list[SectionChant], ordre: list[str]) -> list[BlocLine]:
    """Déroule l'ordre chanté en lignes (texte, gras), refrain en gras, ligne vide entre sections."""
    by_id = {s.id: s for s in sections}
    lines: list[BlocLine] = []
    for section_id in ordre:
        section = by_id.get(section_id)
        if section is None:
            logger.warning("Section inconnue dans l'ordre du chant : %r", section_id)
            continue
        if lines:
            lines.append(("", False))
        bold = section.type is TypeSection.REFRAIN
        lines += [(ligne, bold) for ligne in section.lignes]
    return lines
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_chant_structure.py -q`
Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/chant_structure.py tests/test_chant_structure.py
git commit -m "feat: ordre chanté, sérialisation et lignes projetées des chants structurés" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Base de données — migration et persistance

**Files:**
- Modify: `context/chant_schema.sql`, `tools/db_handler.py`
- Test: `tests/test_db_handler.py`

**Interfaces:**
- Consumes: `Chant`, `MomentLiturgique` (Task 1) ; `structure_to_json`, `structure_from_json`, `ordre_to_json`, `ordre_from_json` (Task 2)
- Produces: `init_db(db_path=None)` migre toute base ancienne ; `create_chant`, `get_chant`, `update_chant`, `search_chants` lisent et écrivent `recueil`, `structure`, `ordre` (signatures inchangées) ; constante `SCHEMA_VERSION = 1`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_db_handler.py` :

```python
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
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_db_handler.py -q`
Expected: erreur de collecte `ImportError: cannot import name 'SCHEMA_VERSION'`.

- [ ] **Step 3: Mettre à jour le schéma des bases neuves**

Remplacer le contenu de `context/chant_schema.sql` par :

```sql
-- Schéma SQL pour la bibliothèque de chants (SQLite)
-- Utilisé par db_handler.py (version 1 ; voir db_handler._migrate pour les bases plus anciennes)

CREATE TABLE IF NOT EXISTS chants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    paroles TEXT NOT NULL,
    auteur TEXT,
    compositeur TEXT,
    reference TEXT,
    notes TEXT,
    recueil TEXT,
    structure TEXT,  -- JSON : {"sections": [{"id", "type", "lignes"}]}
    ordre TEXT,      -- JSON : ["R", "1", "R", ...]
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Pas de CHECK sur le moment : la validation passe par l'énumération MomentLiturgique.
CREATE TABLE IF NOT EXISTS chant_moments (
    chant_id INTEGER NOT NULL,
    moment TEXT NOT NULL,
    PRIMARY KEY (chant_id, moment),
    FOREIGN KEY (chant_id) REFERENCES chants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chants_titre ON chants(titre);
CREATE INDEX IF NOT EXISTS idx_chants_reference ON chants(reference);
CREATE INDEX IF NOT EXISTS idx_chant_moments_moment ON chant_moments(moment);
```

- [ ] **Step 4: Réécrire `tools/db_handler.py`**

Remplacer tout le contenu du fichier par :

```python
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
```

- [ ] **Step 5: Vérifier que les tests passent**

Run: `python -m pytest tests/test_db_handler.py -q`
Expected: `8 passed`

Si `test_old_database_is_migrated_without_data_loss` échoue avec `OperationalError: cannot start a transaction within a transaction`, c'est que `executescript` a laissé une transaction ouverte : ajouter `conn.commit()` juste avant `_migrate(conn)` dans `init_db`.

- [ ] **Step 6: Lancer toute la suite**

Run: `python -m pytest tests -q`
Expected: tous les tests passent (aucune régression sur le découpage ni le PPTX).

- [ ] **Step 7: Commit**

```bash
git add context/chant_schema.sql tools/db_handler.py tests/test_db_handler.py
git commit -m "feat: migration de la base et persistance de la structure des chants" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: `split_lines_for_slides` — découpage qui garde le gras

**Files:**
- Modify: `tools/slicing.py` (ajout en fin de fichier ; constante `COST_LINE_END`)
- Test: `tests/test_split_lines.py`

**Interfaces:**
- Consumes: `split_text_for_slides(text, max_chars, mode, max_lines, chars_per_line)`, `clean_spaces`, `DEFAULT_MAX_CHARS`, `DEFAULT_CHARS_PER_LINE` (déjà dans `tools/slicing.py`)
- Produces: `split_lines_for_slides(lines: list[tuple[str, bool]], max_chars: int = DEFAULT_MAX_CHARS, max_lines: int | None = None, chars_per_line: int = DEFAULT_CHARS_PER_LINE) -> list[list[tuple[str, bool]]]` — une liste de slides, chacune une liste de `(texte, gras)` ; `("", False)` = ligne vide

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_split_lines.py` :

```python
"""Tests de split_lines_for_slides : le découpage conserve le gras de chaque ligne."""

from tools.slicing import split_lines_for_slides, split_text_for_slides

REFRAIN = [("Gloire à Dieu, au plus haut des cieux,", True), ("Paix sur la terre aux hommes qu’il aime !", True)]
COUPLET = [("Nous te louons, nous te bénissons,", False), ("Nous t’adorons, nous te glorifions,", False)]
SEP = ("", False)


def test_slides_have_the_same_text_as_plain_chant_slicing():
    lines = REFRAIN + [SEP] + COUPLET
    pages = split_lines_for_slides(lines, max_lines=6)
    expected = split_text_for_slides("\n".join(t for t, _ in lines), mode="chant", max_lines=6)
    assert ["\n".join(t for t, _ in page) for page in pages] == expected


def test_bold_flag_follows_each_line():
    lines = REFRAIN + [SEP] + COUPLET + [SEP] + REFRAIN
    refrain_texts = {t for t, _ in REFRAIN}
    for page in split_lines_for_slides(lines, max_lines=6):
        for text, bold in page:
            if text:
                assert bold == (text in refrain_texts), text


def test_blank_line_between_sections_is_kept_when_they_share_a_slide():
    pages = split_lines_for_slides([("Alléluia", True), SEP, ("Chantons le Seigneur", False)])
    assert pages == [[("Alléluia", True), ("", False), ("Chantons le Seigneur", False)]]


def test_overlong_bold_line_stays_bold_across_slides():
    line = " ".join(["alléluia"] * 40)
    pages = split_lines_for_slides([(line, True)], max_lines=6)
    assert len(pages) > 1
    assert all(bold for page in pages for text, bold in page if text)
    assert " ".join(t for page in pages for t, _ in page) == line


def test_line_with_embedded_newline_is_split_into_lines():
    pages = split_lines_for_slides([("un\ndeux", True)])
    assert pages == [[("un", True), ("deux", True)]]


def test_empty_input_gives_no_slide():
    assert split_lines_for_slides([]) == []
    assert split_lines_for_slides([SEP]) == []
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_split_lines.py -q`
Expected: erreur de collecte `ImportError: cannot import name 'split_lines_for_slides'`.

- [ ] **Step 3: Implémenter**

Ajouter à la fin de `tools/slicing.py` :

```python
def split_lines_for_slides(
    lines: list[tuple[str, bool]],
    max_chars: int = DEFAULT_MAX_CHARS,
    max_lines: int | None = None,
    chars_per_line: int = DEFAULT_CHARS_PER_LINE,
) -> list[list[tuple[str, bool]]]:
    """
    Découpe des lignes (texte, gras) en slides, avec les mêmes règles que le mode "chant"
    de split_text_for_slides. Chaque slide est une liste de (texte, gras) ; ("", False) est
    une ligne vide. Le gras reste attaché à sa ligne, même si une ligne trop longue est
    coupée sur plusieurs slides.
    """
    flat: list[tuple[str, bool]] = []
    for text, bold in lines:
        for part in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            flat.append((clean_spaces(part), bold))

    chunks = split_text_for_slides(
        "\n".join(t for t, _ in flat),
        max_chars,
        mode="chant",
        max_lines=max_lines,
        chars_per_line=chars_per_line,
    )

    # Chaque ligne d'un slide est un morceau (de ligne entière ou coupée) des lignes d'origine,
    # dans le même ordre : on les retrouve en avançant dans les lignes non vides.
    content = [(t, b) for t, b in flat if t]
    index = pos = 0
    pages: list[list[tuple[str, bool]]] = []
    for chunk in chunks:
        page: list[tuple[str, bool]] = []
        for part in chunk.split("\n"):
            if not part:
                page.append(("", False))
                continue
            text, bold = content[index]
            while text[pos] == " ":
                pos += 1
            if not text.startswith(part, pos):
                raise ValueError(f"Découpage incohérent : {part!r} introuvable dans {text!r}")
            page.append((part, bold))
            pos += len(part)
            if pos >= len(text):
                index, pos = index + 1, 0
        pages.append(page)
    return pages
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_split_lines.py tests/test_slicing.py -q`
Expected: tous passent.

- [ ] **Step 5: Écrire le test du couplet intact (il échoue)**

Un couplet de deux lignes qui tient seul sur un slide ne doit pas être coupé entre ses deux lignes. Ajouter à la fin de `tests/test_split_lines.py` :

```python
def test_a_couplet_is_not_split_when_it_fits_on_its_own_slide():
    refrain = [("Chantons au Seigneur un chant nouveau,", True), ("Alléluia, alléluia !", True)]
    couplet_1 = [("Le matin se lève sur la ville,", False), ("Les cloches annoncent le jour.", False)]
    couplet_2 = [("Le soir descend sur la vallée,", False), ("Nous rendons grâce pour ce jour.", False)]
    lines = refrain + [SEP] + couplet_1 + [SEP] + refrain + [SEP] + couplet_2 + [SEP] + refrain

    pages = split_lines_for_slides(lines, max_lines=6)

    for first, second in (couplet_1, couplet_2):
        for page in pages:
            texts = [t for t, _ in page]
            assert (first[0] in texts) == (second[0] in texts), texts
```

Run: `python -m pytest tests/test_split_lines.py::test_a_couplet_is_not_split_when_it_fits_on_its_own_slide -q`
Expected: FAIL (le couplet 2 est coupé entre « Le soir descend… » et « Nous rendons grâce… »).

- [ ] **Step 6: Renchérir la coupure au milieu d'un couplet**

Dans `tools/slicing.py`, remplacer la constante :

```python
COST_LINE_END = 5        # chants : fin de ligne
```

par :

```python
COST_LINE_END = 25       # chants : fin de ligne (moins bon qu'une ligne vide entre couplets)
```

Run: `python -m pytest tests -q`
Expected: tous les tests passent, y compris le nouveau.

- [ ] **Step 7: Commit**

```bash
git add tools/slicing.py tests/test_split_lines.py
git commit -m "feat: découpage de lignes qui conserve le gras de chaque ligne" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Générateur PPTX — refrain en gras et ordre chanté

**Files:**
- Modify: `tools/pptx_generator.py`
- Test: `tests/test_pptx_generator.py` (ajouts en fin de fichier)

**Interfaces:**
- Consumes: `BlocLine`, `compute_ordre`, `expand_lines`, `sections_from_dicts` (Task 2) ; `split_lines_for_slides` (Task 4)
- Produces: un bloc `{"type": "chant", "titre", "paroles", "structure": list[dict], "ordre": list[str]}` ; si `structure` est non vide, le chant suit `ordre` (à défaut `compute_ordre`) avec refrain en gras ; sinon comportement actuel. Clés optionnelles : un bloc sans `structure` est inchangé.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_pptx_generator.py` :

```python
# --- Chants structurés : refrain en gras, ordre chanté ---

SECTIONS = [
    {"id": "R", "type": "refrain", "lignes": ["Gloire à Dieu au plus haut", "Paix sur la terre"]},
    {"id": "1", "type": "couplet", "lignes": ["Nous te louons", "Nous t’adorons"]},
    {"id": "2", "type": "couplet", "lignes": ["Seigneur Dieu", "Roi du ciel"]},
]


def _body_lines(path):
    """Toutes les lignes (texte, gras) du corps des slides, dans l'ordre, lignes vides exclues."""
    lines = []
    for slide in Presentation(str(path)).slides:
        body = [sh for sh in slide.shapes if sh.has_text_frame][1]
        for p in body.text_frame.paragraphs:
            if p.runs:
                assert len({r.font.bold for r in p.runs}) == 1
                lines.append((p.text, p.runs[0].font.bold))
    return lines


def _expected(order):
    by_id = {s["id"]: s for s in SECTIONS}
    return [(ligne, sid == "R") for sid in order for ligne in by_id[sid]["lignes"]]


def test_structured_chant_repeats_bold_refrain_after_each_couplet(tmp_path):
    out = tmp_path / "c.pptx"
    generate_pptx([{"type": "chant", "titre": "Gloire", "paroles": "inutile", "structure": SECTIONS}], out)
    assert _body_lines(out) == _expected(["R", "1", "R", "2", "R"])


def test_structured_chant_follows_explicit_order(tmp_path):
    out = tmp_path / "c.pptx"
    bloc = {"type": "chant", "titre": "Gloire", "paroles": "", "structure": SECTIONS, "ordre": ["1", "R"]}
    generate_pptx([bloc], out)
    assert _body_lines(out) == _expected(["1", "R"])


def test_structured_chant_title_is_paginated(tmp_path):
    out = tmp_path / "c.pptx"
    generate_pptx([{"type": "chant", "titre": "Gloire", "paroles": "inutile", "structure": SECTIONS}], out)
    titles = [[sh for sh in s.shapes if sh.has_text_frame][0].text_frame.text for s in Presentation(str(out)).slides]
    y = len(titles)
    assert y >= 1
    assert titles == [f"Gloire - {x}/{y}" for x in range(1, y + 1)]


def test_chant_without_structure_is_unchanged_and_not_bold(tmp_path):
    out = tmp_path / "c.pptx"
    generate_pptx([{"type": "chant", "titre": "Simple", "paroles": "Premier vers\nSecond vers"}], out)
    assert _body_lines(out) == [("Premier vers", False), ("Second vers", False)]
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_pptx_generator.py -q`
Expected: `test_structured_chant_repeats_bold_refrain_after_each_couplet` et `test_structured_chant_follows_explicit_order` échouent (le générateur ignore la structure) ; les deux autres passent déjà : ce sont des garde-fous de non-régression (pagination, chant sans structure).

- [ ] **Step 3: Modifier les imports**

Dans `tools/pptx_generator.py`, remplacer la ligne d'import de `tools.slicing` par :

```python
from tools.chant_structure import BlocLine, compute_ordre, expand_lines, sections_from_dicts
from tools.slicing import (
    DEFAULT_CHARS_PER_LINE,
    DEFAULT_MAX_CHARS,
    clean_spaces,
    split_lines_for_slides,
    split_text_for_slides,
)
```

- [ ] **Step 4: Remplacer `_write_lines` et ajouter `_as_lines`**

Remplacer la fonction `_write_lines` (lignes 57-66) par :

```python
def _as_lines(text: str) -> list[BlocLine]:
    """Texte à plat → lignes (texte, gras=False)."""
    return [(line, False) for line in text.split("\n")]


def _write_lines(
    text_frame, lines: list[BlocLine], font_cfg: dict, default_size: int, bold: bool = False
) -> None:
    """
    Un paragraphe par ligne (les chants gardent leurs retours à la ligne).
    `bold` met tout en gras ; sinon le gras suit l'indicateur de chaque ligne (refrain).
    """
    for i, (line, line_bold) in enumerate(lines):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        # Une ligne vide (entre deux couplets) garde la hauteur de la police.
        p.font.size = Pt(font_cfg.get("size", default_size))
        if line:
            _style_run(p.add_run(), font_cfg, default_size, bold or line_bold)
            p.runs[0].text = line
```

- [ ] **Step 5: Adapter `_add_slide`**

Dans la signature de `_add_slide`, remplacer `body: str,` par `body: "str | list[BlocLine]",`.

Remplacer l'appel du titre :

```python
    _write_lines(title_box.text_frame, title, design.get("title", {}), 24, bold=design.get("title", {}).get("bold", True))
```

par :

```python
    _write_lines(
        title_box.text_frame, _as_lines(title), design.get("title", {}), 24,
        bold=design.get("title", {}).get("bold", True),
    )
```

et l'appel du corps :

```python
    _write_lines(body_box.text_frame, body, design.get("text", {}), 54)
```

par :

```python
    body_lines = _as_lines(body) if isinstance(body, str) else body
    _write_lines(body_box.text_frame, body_lines, design.get("text", {}), 54)
```

- [ ] **Step 6: Ajouter `_chant_pages` et utiliser `pages` dans `generate_pptx`**

Ajouter avant `generate_pptx` :

```python
def _chant_pages(bloc: dict, split_kwargs: dict) -> list:
    """
    Slides d'un chant. Chant structuré : ordre chanté, refrain en gras. Sinon : paroles à plat,
    comme avant.
    """
    sections = sections_from_dicts(bloc.get("structure") or [])
    if not sections:
        return split_text_for_slides(bloc.get("paroles", ""), mode="chant", **split_kwargs)
    ordre = bloc.get("ordre") or compute_ordre(sections)
    return split_lines_for_slides(expand_lines(sections, ordre), **split_kwargs)
```

Dans `generate_pptx`, remplacer la boucle `for bloc in blocs:` par :

```python
    for bloc in blocs:
        t = bloc.get("type", "")

        if t == "lecture":
            label = clean_spaces(bloc.get("intro_lue") or bloc.get("reference") or "Lecture")
            pages = split_text_for_slides(_strip_html(bloc.get("contenu", "")), **split_kwargs)
        elif t == "chant":
            label = clean_spaces(bloc.get("titre", "Chant"))
            pages = _chant_pages(bloc, split_kwargs)
        elif t == "message":
            label = clean_spaces(bloc.get("titre", "Message"))
            pages = split_text_for_slides(_strip_html(bloc.get("contenu", "")), **split_kwargs)
        else:
            continue

        y = len(pages)
        total_slides += y
        print(f"[pptx] {label} : {y} slide(s) générée(s)", flush=True)

        for x, page in enumerate(pages, start=1):
            _add_slide(prs, config, f"{label} - {x}/{y}", page, slide_type=t)
```

- [ ] **Step 7: Vérifier**

Run: `python -m pytest tests -q`
Expected: tous les tests passent, dont les 4 nouveaux.

- [ ] **Step 8: Commit**

```bash
git add tools/pptx_generator.py tests/test_pptx_generator.py
git commit -m "feat: refrain en gras et ordre chanté dans le PowerPoint" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Application Streamlit — moments, structure transmise, édition des paroles

**Files:**
- Modify: `app.py`
- Create: `tests/conftest.py`, `tests/test_app_smoke.py`

**Interfaces:**
- Consumes: `sections_to_dicts` (Task 2), `Chant.set_paroles` (Task 1), blocs `structure` / `ordre` (Task 5)
- Produces: les blocs chant de la session portent `structure` (liste de dicts) et `ordre` ; l'export les transmet au générateur ; la liste « Moment liturgique » de la recherche reprend tous les moments.

- [ ] **Step 1: Isoler les données des tests**

Créer `tests/conftest.py` :

```python
"""Les tests ne doivent jamais toucher la vraie bibliothèque ni le dossier de sortie."""

import os
import tempfile

# Avant tout import de tools.db_handler / app, qui lisent ces variables à l'import.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="powermesia-data-"))
os.environ.setdefault("OUTPUT_DIR", tempfile.mkdtemp(prefix="powermesia-out-"))
```

- [ ] **Step 2: Écrire le test de fumée qui échoue**

Créer `tests/test_app_smoke.py` :

```python
"""Test de fumée de l'application Streamlit."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _library_page() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()
    return at


def test_both_pages_load_without_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Rechercher", "Ajouter", "Modifier / Supprimer"]


def test_moment_filter_lists_every_liturgical_moment():
    at = _library_page()
    moment_filter = next(s for s in at.selectbox if s.label == "Moment liturgique")
    options = set(moment_filter.options)
    assert {"pardon", "gloire", "psaume", "alleluia", "pu", "sanctus", "anamnese", "agneau"} <= options
    assert {"entree", "offertoire", "communion", "envoi", "autre"} <= options
```

- [ ] **Step 3: Vérifier qu'il échoue**

Run: `python -m pytest tests/test_app_smoke.py -q`
Expected: `test_moment_filter_lists_every_liturgical_moment` échoue (`pardon` absent) ; le premier test passe.

- [ ] **Step 4: Modifier `app.py`**

a) Après `from tools.db_handler import (...)`, ajouter l'import :

```python
from tools.chant_structure import sections_to_dicts
```

b) Dans l'onglet « Rechercher », remplacer la liste du `selectbox` :

```python
            [None, "entree", "offertoire", "communion", "envoi", "autre"],
```

par :

```python
            [None] + [m.value for m in MomentLiturgique],
```

c) Dans le bouton « ➕ Ajouter ce chant », remplacer le `blocs.append({...})` par :

```python
                    blocs.append({
                        "ordre": len(blocs),
                        "type": "chant",
                        "chant_id": c.id,
                        "titre": c.titre,
                        "paroles": c.paroles,
                        "structure": sections_to_dicts(c.structure),
                        "ordre_chant": c.ordre,
                    })
```

(La clé `ordre` est déjà prise par la position du bloc dans la messe : l'ordre chanté s'appelle `ordre_chant` dans les blocs de la session.)

d) Dans la construction de `pptx_blocs`, remplacer le bloc `if b.get("type") == "chant":` par :

```python
                        if b.get("type") == "chant":
                            pptx_blocs.append({
                                "type": "chant",
                                "titre": b.get("titre", ""),
                                "paroles": b.get("paroles", ""),
                                "structure": b.get("structure", []),
                                "ordre": b.get("ordre_chant", []),
                            })
```

e) Dans le formulaire « Modifier », remplacer `chant.paroles = paroles` par :

```python
                            structure_supprimee = chant.set_paroles(paroles)
```

et, après `update_chant(chant)`, remplacer `st.success("Chant mis à jour.")` par :

```python
                            st.success("Chant mis à jour.")
                            if structure_supprimee:
                                st.info("Les paroles ont changé : la structure (refrains) a été supprimée.")
```

- [ ] **Step 5: Vérifier**

Run: `python -m pytest tests -q`
Expected: tous les tests passent.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/conftest.py tests/test_app_smoke.py
git commit -m "feat: l'application transmet la structure des chants et liste tous les moments" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Script de démonstration et documentation

**Files:**
- Create: `scripts/demo_refrain_pptx.py`
- Modify: `hardprompts/slicing_rules.md`, `README.md`, `ARBORESCENCE.md`

**Interfaces:**
- Consumes: `SectionChant`, `TypeSection` (Task 1), `compute_ordre`, `sections_to_dicts` (Task 2), `generate_pptx` (Task 5)
- Produces: `output/demo_refrain.pptx` (dossier `output/` ignoré par git) à ouvrir dans PowerPoint pour valider visuellement le gras et l'ordre.

- [ ] **Step 1: Créer le script**

Créer `scripts/demo_refrain_pptx.py` :

```python
"""
Génère output/demo_refrain.pptx : un chant structuré (paroles inventées) dont le refrain
est en gras et répété après chaque couplet. À ouvrir dans PowerPoint pour contrôle visuel.

    python scripts/demo_refrain_pptx.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context.models import SectionChant, TypeSection
from tools.chant_structure import compute_ordre, sections_to_dicts
from tools.pptx_generator import generate_pptx

SECTIONS = [
    SectionChant("R", TypeSection.REFRAIN, ["Chantons au Seigneur un chant nouveau,", "Alléluia, alléluia !"]),
    SectionChant("1", TypeSection.COUPLET, ["Le matin se lève sur la ville,", "Les cloches annoncent le jour."]),
    SectionChant("2", TypeSection.COUPLET, ["Le soir descend sur la vallée,", "Nous rendons grâce pour ce jour."]),
]


def main() -> Path:
    out = ROOT / "output" / "demo_refrain.pptx"
    bloc = {
        "type": "chant",
        "titre": "Chant de démonstration",
        "paroles": "",
        "structure": sections_to_dicts(SECTIONS),
        "ordre": compute_ordre(SECTIONS),
    }
    generate_pptx([bloc], out)
    return out


if __name__ == "__main__":
    print(f"Fichier généré : {main()}")
```

- [ ] **Step 2: Exécuter le script**

Run: `python scripts/demo_refrain_pptx.py`
Expected: affiche `[pptx] Chant de démonstration : N slide(s) générée(s)` puis `Fichier généré : …\output\demo_refrain.pptx`.

- [ ] **Step 3: Contrôle visuel (manuel)**

Ouvrir `output/demo_refrain.pptx` dans PowerPoint et vérifier : les deux lignes du refrain sont **en gras**, les couplets non ; l'ordre est refrain, couplet 1, refrain, couplet 2, refrain ; les titres sont `Chant de démonstration - x/y` ; le texte rentre dans la slide.

- [ ] **Step 4: Documentation**

Ajouter à la fin de `hardprompts/slicing_rules.md` :

```markdown

## Chants structurés (refrain)

- Un chant peut porter une `structure` (sections `refrain` / `couplet` / `pont`) et un `ordre`
  chanté (`tools/chant_structure.py`).
- Ordre par défaut (`compute_ordre`) : le refrain est inséré après chaque couplet ou pont ; s'il
  ouvre le chant, il est aussi joué en premier (`R 1 R 2 R P R`). Plusieurs refrains ou aucun :
  ordre du document.
- Les lignes de refrain sont écrites **en gras** ; le découpage (`split_lines_for_slides`) garde le
  gras de chaque ligne et préfère couper entre deux sections.
- Un chant sans structure est projeté comme avant (paroles à plat, sans gras).
```

Dans `README.md`, remplacer la puce « **Bibliothèque de chants** » par :

```markdown
- **Bibliothèque de chants** : base SQLite pour gérer titres, paroles, références, recueil, moments liturgiques et structure (refrain, couplets, pont). Le refrain est écrit en gras dans le PowerPoint et répété après chaque couplet.
```

Dans `ARBORESCENCE.md`, ajouter sous `tools/` la ligne :

```
│   ├── chant_structure.py    # Structure d'un chant (refrain, ordre chanté)
│   ├── slicing.py            # Découpage du texte en slides
```

- [ ] **Step 5: Vérification finale**

Run: `python -m pytest tests -q`
Expected: tous les tests passent.

Run: `git status --short`
Expected: uniquement les fichiers de cette tâche (le dossier `output/` est ignoré).

- [ ] **Step 6: Commit**

```bash
git add scripts/demo_refrain_pptx.py hardprompts/slicing_rules.md README.md ARBORESCENCE.md
git commit -m "docs: script de démonstration du refrain en gras et documentation des chants structurés" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Auto-revue (spec ↔ plan)

| Exigence de la spec (livraison 1) | Tâche |
|---|---|
| §5 colonnes `recueil`, `structure`, `ordre` | 1, 3 |
| §5 nouveaux moments, `CHECK` retiré, migration `user_version` transactionnelle sans perte | 1, 3 |
| §5 chant sans structure inchangé ; `paroles` conservé | 3, 5, test `test_chant_without_structure_*` |
| §6 règle de l'ordre chanté (`R 1 R 2 R P R`, `1 R 2 R`) | 2 |
| §7 lignes de refrain en gras, ordre `ordre`, `split_lines_for_slides`, coupure entre sections | 2, 4, 5 |
| §7 titre et pagination inchangés | 5 (`test_structured_chant_title_is_paginated`) |
| §9 test de migration d'une base existante | 3 |
| §9 aucune parole réelle versionnée | Global Constraints ; tests et script avec textes inventés |
| §2 / §8 modification des paroles d'un chant structuré | 1 (`set_paroles`), 6 |

Hors de cette livraison (livraisons 2 et 3) : extraction Word/PDF, analyse, écran d'import, doublons.

## Points d'attention pour l'exécutant

- La clé `ordre` des blocs de la session Streamlit désigne déjà la **position** du bloc dans la messe ; l'ordre chanté s'appelle donc `ordre_chant` dans la session et `ordre` seulement dans le bloc transmis à `generate_pptx` (Task 6, étapes c et d).
- `executescript` valide la transaction en cours : la migration démarre donc avec `BEGIN` explicite. Si SQLite signale une transaction déjà ouverte, voir la note de la Task 3, étape 5.
- Un chant structuré affiche 6 lignes au plus par slide ; un refrain long sur plusieurs slides garde son gras (test `test_overlong_bold_line_stays_bold_across_slides`).
- Le coût d'une coupure entre deux lignes d'un couplet (`COST_LINE_END`) passe de 5 à 25 : un couplet qui tient seul sur un slide n'est plus coupé en deux. Le découpage des chants gagne parfois un slide.
