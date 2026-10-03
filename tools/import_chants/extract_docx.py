"""Extraction d'un fichier Word (.docx) : une liste de Line avec gras / italique / souligné."""

import dataclasses
import io
import zipfile

from docx import Document
from docx.enum.text import WD_UNDERLINE
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from lxml.etree import LxmlError

from tools.import_chants.lignes import Caractere, lignes_depuis_caracteres
from tools.import_chants.modeles import Line, UnsupportedFile


def _valeur(police, attribut: str):
    """Valeur d'un attribut de police : `None` si non défini, sinon `bool`."""
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
        vus = set()
        while style is not None:
            if style.style_id in vus:
                break
            vus.add(style.style_id)
            valeur = _valeur(style.font, attribut)
            if valeur is not None:
                return valeur
            style = style.base_style
    return False


# Où se trouvent les runs d'un paragraphe : directement, dans un lien, une insertion suivie
# (suivi des modifications), une balise intelligente, un champ ou un contrôle de contenu en ligne.
_CHEMINS_DES_RUNS = (
    "./w:r | ./w:hyperlink/w:r | ./w:ins/w:r | ./w:smartTag/w:r | ./w:fldSimple/w:r"
    " | ./w:sdt/w:sdtContent/w:r"
)


def _runs(paragraphe: Paragraph) -> list[Run]:
    """Les runs du paragraphe dans l'ordre du document, y compris ceux des liens, insertions suivies,
    balises, champs et contrôles de contenu en ligne (leur texte ne doit jamais être perdu)."""
    return [Run(r, paragraphe) for r in paragraphe._p.xpath(_CHEMINS_DES_RUNS)]


def _lignes_du_paragraphe(paragraphe: Paragraph) -> list[Line]:
    """Éclaté un paragraphe en lignes selon ses retours à la ligne, doubles espaces et souligné."""
    caracteres: list[Caractere] = []
    for run in _runs(paragraphe):
        gras, italique, souligne = (_effectif(run, paragraphe, a) for a in ("bold", "italic", "underline"))
        caracteres += [(c, gras, italique, souligne) for c in run.text]
    return lignes_depuis_caracteres(caracteres)


def extract_docx(data: bytes) -> list[Line]:
    """
    Lit un .docx. Un paragraphe est éclaté en plusieurs lignes (retours à la ligne, doubles espaces,
    changement de soulignement) ; les paragraphes vides deviennent `vide_avant` de la ligne suivante.
    Les tableaux, zones de texte et contrôles de contenu de niveau bloc ne sont pas lus.
    """
    try:
        document = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError, LxmlError) as e:
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
