"""Extraction d'un fichier Word (.docx) : une liste de Line avec gras / italique / souligné."""

import dataclasses
import io
import zipfile

from docx import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run
from lxml.etree import LxmlError

from tools.import_chants.lignes import Caractere, lignes_depuis_caracteres
from tools.import_chants.modeles import Line, UnsupportedFile

# Garde anti-bombe de décompression : une feuille de chants Word reste très en deçà de ces limites.
TAILLE_MAX_DECOMPRESSEE = 50 * 1024 * 1024    # somme des tailles décompressées de toutes les entrées
TAILLE_MAX_DOCUMENT_XML = 5 * 1024 * 1024     # word/document.xml décompressé
ENTREES_MAX = 1000                            # nombre d'entrées de l'archive


def _valeur(police, attribut: str):
    """Valeur d'un attribut de police : `None` si non défini, sinon `bool`."""
    valeur = getattr(police, attribut)
    if valeur is None:
        return None
    return valeur is not False  # le souligné peut être un type de trait (double, pointillé…) : souligné


def _valeur_du_style(depart, attribut: str):
    """Valeur d'un attribut de police dans un style et ses styles de base (`None` s'il n'est défini nulle part)."""
    style, vus = depart, set()
    while style is not None:
        if style.style_id in vus:
            break
        vus.add(style.style_id)
        valeur = _valeur(style.font, attribut)
        if valeur is not None:
            return valeur
        style = style.base_style
    return None


def _effectif(run: Run, paragraphe: Paragraph, attribut: str, memo: dict) -> bool:
    """
    Valeur effective d'un attribut de police : le run, puis son style de caractère, puis les styles du
    paragraphe. `memo` (propre à une lecture) évite de parcourir les styles à chaque run.
    """
    valeur = _valeur(run.font, attribut)
    if valeur is not None:
        return valeur
    for genre, identifiant in (("caractere", run._r.style), ("paragraphe", paragraphe._p.style)):
        cle = (genre, identifiant, attribut)
        if cle not in memo:
            memo[cle] = _valeur_du_style(run.style if genre == "caractere" else paragraphe.style, attribut)
        if memo[cle] is not None:
            return memo[cle]
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


def _lignes_du_paragraphe(paragraphe: Paragraph, memo: dict) -> list[Line]:
    """Éclaté un paragraphe en lignes selon ses retours à la ligne, doubles espaces et souligné."""
    caracteres: list[Caractere] = []
    for run in _runs(paragraphe):
        gras, italique, souligne = (_effectif(run, paragraphe, a, memo) for a in ("bold", "italic", "underline"))
        caracteres += [(c, gras, italique, souligne) for c in run.text]
    return lignes_depuis_caracteres(caracteres)


def _verifier_taille_decompressee(data: bytes) -> None:
    """Refuse une archive qui, décompressée, serait énorme (bombe de décompression), avant toute lecture."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entrees = archive.infolist()
    except zipfile.BadZipFile as e:
        raise UnsupportedFile("Fichier Word illisible (est-ce bien un .docx ?)") from e
    if (
        len(entrees) > ENTREES_MAX
        or sum(e.file_size for e in entrees) > TAILLE_MAX_DECOMPRESSEE
        or any(e.filename == "word/document.xml" and e.file_size > TAILLE_MAX_DOCUMENT_XML for e in entrees)
    ):
        raise UnsupportedFile("Fichier Word trop volumineux une fois décompressé")


def _lire(data: bytes) -> list[Line]:
    try:
        document = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError, LxmlError) as e:
        raise UnsupportedFile("Fichier Word illisible (est-ce bien un .docx ?)") from e

    lignes: list[Line] = []
    memo: dict = {}
    vide = False
    for element in document.iter_inner_content():
        if not isinstance(element, Paragraph):
            continue
        du_paragraphe = _lignes_du_paragraphe(element, memo)
        if not du_paragraphe:
            vide = True
            continue
        lignes.append(dataclasses.replace(du_paragraphe[0], vide_avant=vide))
        lignes += du_paragraphe[1:]
        vide = False
    return lignes


def extract_docx(data: bytes) -> list[Line]:
    """
    Lit un .docx. Un paragraphe est éclaté en plusieurs lignes (retours à la ligne, doubles espaces,
    changement de soulignement) ; les paragraphes vides deviennent `vide_avant` de la ligne suivante.
    Les tableaux, zones de texte et contrôles de contenu de niveau bloc ne sont pas lus.
    Un fichier abîmé, trop volumineux une fois décompressé ou d'une structure inattendue est refusé
    (UnsupportedFile), jamais un plantage.
    """
    _verifier_taille_decompressee(data)
    try:
        return _lire(data)
    except UnsupportedFile:
        raise
    except Exception as e:  # python-docx et lxml lèvent des types variés sur un XML bien formé mais inattendu
        raise UnsupportedFile("Fichier Word illisible") from e
