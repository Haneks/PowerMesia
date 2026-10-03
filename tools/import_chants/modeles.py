"""Types communs à l'import de chants : extraction (Word / PDF) puis analyse."""

from dataclasses import dataclass, field
from typing import Optional

from context.models import MomentLiturgique, SectionChant


class UnsupportedFile(Exception):
    """Fichier que l'import ne sait pas lire (partition, image, fichier illisible)."""

    def __init__(self, raison: str):
        super().__init__(raison)
        self.raison = raison


@dataclass(frozen=True)
class Line:
    """Une ligne de texte avec sa mise en forme, telle que sortie par l'extraction."""
    texte: str
    gras: bool = False
    italique: bool = False
    souligne: bool = False
    vide_avant: bool = False  # une ligne vide précède cette ligne


@dataclass
class ParsedSong:
    """Un chant reconnu dans un fichier, prêt à être vérifié puis importé."""
    titre: str
    moment: MomentLiturgique
    recueil: Optional[str] = None
    structure: list[SectionChant] = field(default_factory=list)
    ordre: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    """Résultat de l'analyse d'un fichier."""
    chants: list[ParsedSong] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # métadonnées et éléments ignorés (date, renvois…)
