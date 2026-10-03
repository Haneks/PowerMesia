"""
Éclatement d'un paragraphe (Word) ou d'une ligne visuelle (PDF) en lignes de chant, à partir de
ses caractères et de leur mise en forme. Commun aux deux extracteurs.
"""

import re

from tools.import_chants.modeles import Line

# (caractère, gras, italique, souligné)
Caractere = tuple[str, bool, bool, bool]

# Fins de vers dans un paragraphe : retour à la ligne, ou 2 espaces (insécables compris) et plus.
_FIN_DE_VERS = re.compile(r"\n|[^\S\n]{2,}")
_FIN_DE_LIGNE = re.compile(r"\n")
SEUIL = 0.5  # une ligne est grasse / italique / soulignée si au moins la moitié de ses caractères le sont
MOTS_MAX_SANS_COUPURE = 6  # en dessous, des doubles espaces ne séparent pas deux vers


def _espaces_heritent_du_soulignement(caracteres: list[Caractere]) -> list[Caractere]:
    """
    Les espaces entre deux mots soulignés ne le sont souvent pas. Une espace prend le soulignement
    du caractère visible qui la précède (ou, en tête, qui la suit) : sinon
    « Gloire a Dieu   Lyon centre 4 » serait coupé en deux titres.
    """
    resultat: list[Caractere] = []
    precedent = next((c[3] for c in caracteres if not c[0].isspace()), False)
    for caractere in caracteres:
        if caractere[0].isspace() and caractere[0] != "\n":
            caractere = (caractere[0], caractere[1], caractere[2], precedent)
        else:
            precedent = caractere[3]
        resultat.append(caractere)
    return resultat


def _decouper(segment: list[Caractere], motif: re.Pattern) -> list[Line]:
    texte = "".join(c[0] for c in segment)
    bornes, debut = [], 0
    for m in motif.finditer(texte):
        bornes.append((debut, m.start()))
        debut = m.end()
    bornes.append((debut, len(texte)))

    lignes = []
    for a, b in bornes:
        morceau = segment[a:b]
        brut = "".join(c[0] for c in morceau).strip()
        visibles = [c for c in morceau if not c[0].isspace()]
        if not brut or not visibles:
            continue

        def part(i: int) -> bool:
            return sum(1 for c in visibles if c[i]) / len(visibles) >= SEUIL

        lignes.append(Line(texte=brut, gras=part(1), italique=part(2), souligne=part(3)))
    return lignes


def lignes_depuis_caracteres(caracteres: list[Caractere]) -> list[Line]:
    """
    Éclate des caractères en lignes : à chaque changement de soulignement (un titre souligné suivi
    de paroles donne deux lignes), puis aux retours à la ligne et aux doubles espaces. Un segment
    souligné (un titre) n'est coupé qu'aux retours à la ligne, ainsi qu'un texte court.
    """
    caracteres = _espaces_heritent_du_soulignement(caracteres)
    lignes: list[Line] = []
    debut = 0
    while debut < len(caracteres):
        fin = debut
        while fin < len(caracteres) and caracteres[fin][3] == caracteres[debut][3]:
            fin += 1
        segment = caracteres[debut:fin]
        court = len("".join(c[0] for c in segment).split()) <= MOTS_MAX_SANS_COUPURE
        motif = _FIN_DE_LIGNE if segment[0][3] or court else _FIN_DE_VERS
        lignes += _decouper(segment, motif)
        debut = fin
    return lignes
