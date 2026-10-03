"""Tests de tools/import_chants/importer.py : le point d'entrée de l'import."""

import pytest

from context.models import MomentLiturgique as M
from tests.helpers_import import docx_bytes, pdf_bytes, pdf_en_syllabes
from tools.import_chants.importer import TAILLE_MAX, analyser_fichier
from tools.import_chants.modeles import UnsupportedFile

FEUILLE_WORD = [
    [("Entrée", "gs")],
    [("Venez au bord du fleuve, chantons", "g")],
    "",
    "Premier couplet inventé",
    [("Pardon", "gs")],
    "Prends pitié de nous",
]


def test_fichier_word():
    resultat = analyser_fichier("feuille.docx", docx_bytes(FEUILLE_WORD))
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.PARDON]


def test_extension_en_majuscules():
    assert len(analyser_fichier("FEUILLE.DOCX", docx_bytes(FEUILLE_WORD)).chants) == 2


def test_fichier_pdf():
    pdf = pdf_bytes([
        {"texte": "Entrée", "y": 100, "gras": True, "souligne": True},
        {"texte": "Venez au bord du fleuve, chantons la lumière", "y": 114, "gras": True},
        {"texte": "Premier couplet inventé pour le test", "y": 150},
    ])
    [chant] = analyser_fichier("feuille.pdf", pdf).chants
    assert chant.moment is M.ENTREE
    assert [s.id for s in chant.structure] == ["R", "1"]


def test_partition_refusee_avec_une_raison():
    with pytest.raises(UnsupportedFile) as erreur:
        analyser_fichier("partition.pdf", pdf_en_syllabes())
    assert "Partition" in erreur.value.raison


@pytest.mark.parametrize("nom, data, raison", [
    ("notes.txt", b"du texte", "Format non géré"),
    ("feuille.doc", b"ancien format", "Format non géré"),
    ("faux.docx", b"pas un fichier zip", "Word"),
    ("faux.pdf", b"pas un pdf", "PDF"),
    ("enorme.pdf", b"x" * (TAILLE_MAX + 1), "trop gros"),
], ids=["txt", "doc", "docx-illisible", "pdf-illisible", "trop-gros"])
def test_fichiers_refuses(nom, data, raison):
    with pytest.raises(UnsupportedFile) as erreur:
        analyser_fichier(nom, data)
    assert raison in erreur.value.raison


def test_une_exception_inattendue_de_l_analyse_devient_un_fichier_illisible(monkeypatch):
    def plante(*_):
        raise RuntimeError("bogue inattendu")
    monkeypatch.setattr("tools.import_chants.importer.parse_lines", plante)
    with pytest.raises(UnsupportedFile) as erreur:
        analyser_fichier("feuille.docx", docx_bytes(FEUILLE_WORD))
    assert erreur.value.raison == "Fichier illisible"
    assert isinstance(erreur.value.__cause__, RuntimeError)
