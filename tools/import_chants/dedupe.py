"""Doublons : un chant importé existe-t-il déjà dans la bibliothèque ? (spec §8)"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from context.models import Chant, SectionChant


class Doublon(Enum):
    AUCUN = "aucun"
    IDENTIQUE = "identique"  # même chant, même texte : rien à faire
    DIFFERENT = "different"  # même chant (titre + recueil), texte ou structure différents


@dataclass
class ResultatDoublon:
    statut: Doublon
    existant: Optional[Chant] = None


def normaliser(texte: Optional[str]) -> str:
    """Casse, accents, apostrophes, ponctuation et espaces ignorés : « Venez, au Fleuve ! » = « venez au fleuve »."""
    # « œ » et « æ » ne se décomposent pas en NFKD : « Cœur » doit valoir « Coeur ».
    ligatures = (texte or "").replace("’", "'").replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    decompose = unicodedata.normalize("NFKD", ligatures)
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.casefold()).split())


def cle_chant(titre: str, recueil: Optional[str]) -> str:
    """Clé d'identité d'un chant : titre normalisé + recueil normalisé."""
    return f"{normaliser(titre)}|{normaliser(recueil)}"


def _empreinte_structure(structure: list[SectionChant], ordre: list[str]) -> tuple:
    """Types, lignes (normalisées) des sections dans l'ordre, et ordre chanté."""
    return (
        tuple((s.type, tuple(normaliser(ligne) for ligne in s.lignes)) for s in structure),
        tuple(ordre),
    )


def trouver_doublon(
    titre: str,
    recueil: Optional[str],
    paroles: str,
    structure: list[SectionChant],
    ordre: list[str],
    bibliotheque: list[Chant],
) -> ResultatDoublon:
    """
    Compare un chant à importer à la bibliothèque. Même clé, même texte et même structure : IDENTIQUE.
    Une structure différente (types de sections, lignes, ordre chanté) est une différence, de même qu'un
    import structuré sur un chant existant sans structure (le remplacement ajoute les refrains en gras).
    Un import sans structure ne compare que le texte. Même clé et texte différent : DIFFERENT.
    """
    if not normaliser(titre):
        return ResultatDoublon(Doublon.AUCUN)
    cle = cle_chant(titre, recueil)
    memes = [c for c in bibliotheque if cle_chant(c.titre, c.recueil) == cle]
    if not memes:
        return ResultatDoublon(Doublon.AUCUN)
    texte = normaliser(paroles)
    empreinte = _empreinte_structure(structure, ordre)
    for existant in memes:
        if normaliser(existant.paroles) != texte:
            continue
        if not structure or (
            existant.structure and _empreinte_structure(existant.structure, existant.ordre) == empreinte
        ):
            return ResultatDoublon(Doublon.IDENTIQUE, existant)
    return ResultatDoublon(Doublon.DIFFERENT, memes[0])


def titres_voisins(titre: str, recueil: Optional[str], bibliotheque: list[Chant]) -> list[Chant]:
    """Chants de même titre normalisé mais de clé différente (autre recueil, ou sans recueil)."""
    if not normaliser(titre):
        return []
    cle = cle_chant(titre, recueil)
    return [
        c for c in bibliotheque
        if normaliser(c.titre) == normaliser(titre) and cle_chant(c.titre, c.recueil) != cle
    ]
