"""
Modèles de données pour le Générateur de PowerPoint Paroissial.
Phase Trace - Schémas et mapping des lectures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# BIBLIOTHÈQUE DE CHANTS
# =============================================================================


class MomentLiturgique(Enum):
    """Moment de la messe où le chant est utilisé."""
    ENTREE = "entree"
    OFFERTOIRE = "offertoire"
    COMMUNION = "communion"
    ENVOI = "envoi"
    AUTRE = "autre"


@dataclass
class Chant:
    """
    Schéma d'un chant de la bibliothèque paroissiale.
    Stockage : SQLite ou JSON (voir db_handler).
    """
    id: Optional[int] = None
    titre: str = ""
    paroles: str = ""
    auteur: Optional[str] = None
    compositeur: Optional[str] = None
    reference: Optional[str] = None  # Ex: "B 123", "P 45"
    moments: list[MomentLiturgique] = field(default_factory=list)
    notes: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "titre": self.titre,
            "paroles": self.paroles,
            "auteur": self.auteur,
            "compositeur": self.compositeur,
            "reference": self.reference,
            "moments": [m.value for m in self.moments],
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Chant":
        moments = [
            MomentLiturgique(m) for m in (d.get("moments") or [])
            if m in [e.value for e in MomentLiturgique]
        ]
        return cls(
            id=d.get("id"),
            titre=d.get("titre", ""),
            paroles=d.get("paroles", ""),
            auteur=d.get("auteur"),
            compositeur=d.get("compositeur"),
            reference=d.get("reference"),
            moments=moments,
            notes=d.get("notes"),
            created_at=d.get("created_at"),
            updated_at=d.get("updated_at"),
        )


# =============================================================================
# MAPPING DES LECTURES AELF
# =============================================================================


class TypeLecture(Enum):
    """Types de lectures correspondant à l'API AELF."""
    PREMIERE_LECTURE = "lecture_1"
    PSAUME = "psaume"
    DEUXIEME_LECTURE = "lecture_2"
    EVANGILE = "evangile"


@dataclass
class LectureLiturgique:
    """
    Représentation normalisée d'une lecture (API AELF).
    """
    type: TypeLecture
    reference: str
    titre: Optional[str]
    intro_lue: Optional[str]
    contenu: str
    refrain_psalmique: Optional[str] = None
    ref_refrain: Optional[str] = None
    verset_evangile: Optional[str] = None
    ref_verset: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "reference": self.reference,
            "titre": self.titre,
            "intro_lue": self.intro_lue,
            "contenu": self.contenu,
            "refrain_psalmique": self.refrain_psalmique,
            "ref_refrain": self.ref_refrain,
            "verset_evangile": self.verset_evangile,
            "ref_verset": self.ref_verset,
        }


# =============================================================================
# BLOCS DE LA MESSE (Pour ordonnancement & prévisualisation)
# =============================================================================


class TypeBloc(Enum):
    """Types de blocs affichables dans le PowerPoint."""
    LECTURE = "lecture"
    CHANT = "chant"
    MESSAGE = "message"  # Message paroissial, annonces


@dataclass
class BlocMesse:
    """
    Bloc unique dans l'ordonnancement (lecture, chant ou message).
    Permet la réorganisation avant génération.
    """
    id: str
    type: TypeBloc
    ordre: int
    # Pour les lectures :
    lecture: Optional[LectureLiturgique] = None
    # Pour les chants :
    chant: Optional[Chant] = None
    moment_chant: Optional[MomentLiturgique] = None
    # Pour les messages :
    titre_message: Optional[str] = None
    contenu_message: Optional[str] = None
