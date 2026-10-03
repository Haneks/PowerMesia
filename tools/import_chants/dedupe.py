"""Doublons : un chant importé existe-t-il déjà dans la bibliothèque ? (spec §8)"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from context.models import Chant


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


def trouver_doublon(
    titre: str,
    recueil: Optional[str],
    paroles: str,
    avec_structure: bool,
    bibliotheque: list[Chant],
) -> ResultatDoublon:
    """
    Compare un chant à importer à la bibliothèque. Même clé et même texte : IDENTIQUE, sauf si
    le chant existant n'a pas de structure et que l'import en apporte une (alors DIFFERENT : le
    remplacement ajoute les refrains en gras). Même clé et texte différent : DIFFERENT.
    """
    if not normaliser(titre):
        return ResultatDoublon(Doublon.AUCUN)
    cle = cle_chant(titre, recueil)
    memes = [c for c in bibliotheque if cle_chant(c.titre, c.recueil) == cle]
    if not memes:
        return ResultatDoublon(Doublon.AUCUN)
    texte = normaliser(paroles)
    for existant in memes:
        if normaliser(existant.paroles) == texte and (existant.structure or not avec_structure):
            return ResultatDoublon(Doublon.IDENTIQUE, existant)
    return ResultatDoublon(Doublon.DIFFERENT, memes[0])
