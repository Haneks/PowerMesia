"""
Gestion de la bibliothèque de chants - SQLite.
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

from context.models import Chant, MomentLiturgique

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = os.environ.get("DATA_DIR")
if _DATA_DIR:
    _DATA_PATH = Path(_DATA_DIR)
else:
    _DATA_PATH = PROJECT_ROOT / "data"
DEFAULT_DB = _DATA_PATH / "chants.db"
SCHEMA_PATH = PROJECT_ROOT / "context" / "chant_schema.sql"


def _ensure_data_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def _get_connection(db_path: Optional[Path] = None) -> tuple[sqlite3.Connection, Path]:
    path = db_path or DEFAULT_DB
    _ensure_data_dir(path)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn, path


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialise la base de données avec le schéma."""
    conn, _ = _get_connection(db_path)
    try:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def create_chant(chant: Chant, db_path: Optional[Path] = None) -> int:
    """Insère un chant et retourne son id."""
    conn, _ = _get_connection(db_path)
    try:
        init_db(db_path)
        cur = conn.execute(
            """
            INSERT INTO chants (titre, paroles, auteur, compositeur, reference, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chant.titre,
                chant.paroles,
                chant.auteur,
                chant.compositeur,
                chant.reference,
                chant.notes,
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
        if not row:
            return None
        moments_rows = conn.execute(
            "SELECT moment FROM chant_moments WHERE chant_id = ?", (chant_id,)
        ).fetchall()
        moments = [MomentLiturgique(r["moment"]) for r in moments_rows]
        return Chant(
            id=row["id"],
            titre=row["titre"],
            paroles=row["paroles"],
            auteur=row["auteur"],
            compositeur=row["compositeur"],
            reference=row["reference"],
            notes=row["notes"],
            moments=moments,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
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
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                chant.titre,
                chant.paroles,
                chant.auteur,
                chant.compositeur,
                chant.reference,
                chant.notes,
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
    """Recherche des chants par titre/paroles ou par moment."""
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

        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            moments_rows = conn.execute(
                "SELECT moment FROM chant_moments WHERE chant_id = ?", (row["id"],)
            ).fetchall()
            moments = [MomentLiturgique(r["moment"]) for r in moments_rows]
            result.append(
                Chant(
                    id=row["id"],
                    titre=row["titre"],
                    paroles=row["paroles"],
                    auteur=row["auteur"],
                    compositeur=row["compositeur"],
                    reference=row["reference"],
                    notes=row["notes"],
                    moments=moments,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )
        return result
    finally:
        conn.close()


def list_all_chants(db_path: Optional[Path] = None) -> list[Chant]:
    """Liste tous les chants."""
    return search_chants(db_path=db_path)
