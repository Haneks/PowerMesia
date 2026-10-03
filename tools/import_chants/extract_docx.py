"""Extraction d'un fichier Word (.docx) : une liste de Line avec gras / italique / souligné."""

import dataclasses
import io
import zipfile

from docx import Document
from docx.enum.text import WD_UNDERLINE
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from tools.import_chants.lignes import Caractere, lignes_depuis_caracteres
from tools.import_chants.modeles import Line, UnsupportedFile


def _valeur(police, attribut: str):
    valeur = getattr(police, attribut)
    if valeur is None:
        return None
    if attribut == "underline":
        return valeur not in (False, WD_UNDERLINE.NONE)
    return bool(valeur)


def _effectif(run: Run, paragraphe: Paragraph, attribut: str) -> bool:
    """Valeur effective d'un attribut de police : le run, puis son style, puis les styles du paragraphe."""
    valeur = _valeur(run.font, attribut)
    if valeur is not None:
        return valeur
    for depart in (run.style, paragraphe.style):
        style = depart
        while style is not None:
            valeur = _valeur(style.font, attribut)
            if valeur is not None:
                return valeur
            style = style.base_style
    return False


def _runs(paragraphe: Paragraph) -> list[Run]:
    runs: list[Run] = []
    for element in paragraphe.iter_inner_content():
        runs += [element] if isinstance(element, Run) else list(element.runs)
    return runs


def _lignes_du_paragraphe(paragraphe: Paragraph) -> list[Line]:
    caracteres: list[Caractere] = []
    for run in _runs(paragraphe):
        gras, italique, souligne = (_effectif(run, paragraphe, a) for a in ("bold", "italic", "underline"))
        caracteres += [(c, gras, italique, souligne) for c in run.text]
    return lignes_depuis_caracteres(caracteres)


def extract_docx(data: bytes) -> list[Line]:
    """
    Lit un .docx. Un paragraphe est éclaté en plusieurs lignes (retours à la ligne, doubles espaces,
    changement de soulignement) ; les paragraphes vides deviennent `vide_avant` de la ligne suivante.
    Les tableaux et zones de texte ne sont pas lus.
    """
    try:
        document = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise UnsupportedFile("Fichier Word illisible (est-ce bien un .docx ?)") from e

    lignes: list[Line] = []
    vide = False
    for element in document.iter_inner_content():
        if not isinstance(element, Paragraph):
            continue
        du_paragraphe = _lignes_du_paragraphe(element)
        if not du_paragraphe:
            vide = True
            continue
        lignes.append(dataclasses.replace(du_paragraphe[0], vide_avant=vide))
        lignes += du_paragraphe[1:]
        vide = False
    return lignes
