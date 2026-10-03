"""Fabrique de fichiers Word et PDF pour les tests de l'import (textes inventés, rien du corpus)."""

import io

import fitz
from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.import_chants.modeles import Line


def L(texte: str, gras=False, italique=False, souligne=False, vide=False) -> Line:
    """Une Line abrégée, pour tester l'analyse sans passer par un fichier."""
    return Line(texte, gras, italique, souligne, vide)


def docx_bytes(paragraphes: list, style_gras: bool = False) -> bytes:
    """
    Un .docx. Chaque paragraphe est "" (paragraphe vide), une chaîne (texte simple) ou une liste de
    segments (texte, drapeaux) où les drapeaux sont des lettres : g = gras, i = italique, s = souligné.
    style_gras : applique à tous les paragraphes un style de paragraphe en gras (sans gras sur les runs).
    """
    document = Document()
    style = None
    if style_gras:
        style = document.styles.add_style("TitreGras", WD_STYLE_TYPE.PARAGRAPH)
        style.font.bold = True
    for paragraphe in paragraphes:
        segments = [(paragraphe, "")] if isinstance(paragraphe, str) else paragraphe
        p = document.add_paragraph(style=style)
        for texte, drapeaux in segments:
            run = p.add_run(texte)
            if "g" in drapeaux:
                run.bold = True
            if "i" in drapeaux:
                run.italic = True
            if "s" in drapeaux:
                run.underline = True
    sortie = io.BytesIO()
    document.save(sortie)
    return sortie.getvalue()


def pdf_bytes(lignes: list[dict]) -> bytes:
    """
    Un PDF d'une page. Chaque ligne : {"texte", "y", "taille" (12), "gras" (False), "souligne" (False),
    "copies" (1 : 3 ou plus simule le « faux gras » en imprimant le texte plusieurs fois)}.
    """
    document = fitz.open()
    page = document.new_page()
    for ligne in lignes:
        taille = ligne.get("taille", 12)
        police = "hebo" if ligne.get("gras") else "helv"
        for copie in range(ligne.get("copies", 1)):
            page.insert_text((72 + 0.4 * copie, ligne["y"] + 0.3 * copie), ligne["texte"],
                             fontsize=taille, fontname=police)
        if ligne.get("souligne"):
            largeur = fitz.Font(police).text_length(ligne["texte"], fontsize=taille)  # gère les accents
            page.draw_line((72, ligne["y"] + 2), (72 + largeur, ligne["y"] + 2), width=0.8)
    return document.tobytes()


def pdf_image_seule() -> bytes:
    """Un PDF dont la seule page est une image (un scan) : aucun texte."""
    document = fitz.open()
    page = document.new_page()
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    image.clear_with(200)
    page.insert_image(fitz.Rect(50, 50, 150, 150), pixmap=image)
    return document.tobytes()


def pdf_en_syllabes() -> bytes:
    """Un PDF dont le texte est découpé en fragments de 1 à 2 caractères, comme sous les notes d'une partition."""
    document = fitz.open()
    page = document.new_page()
    for k in range(150):
        page.insert_text((20 + (k % 25) * 22, 60 + (k // 25) * 30), ["la", "so", "a"][k % 3], fontsize=10)
    return document.tobytes()
