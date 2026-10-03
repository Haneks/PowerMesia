"""Tests de tools/import_chants/extract_pdf.py (PDF fabriqués par les tests avec PyMuPDF)."""

import pytest

from tests.helpers_import import pdf_bytes, pdf_en_syllabes, pdf_image_seule
from tools.import_chants.extract_pdf import _raison_de_refus, extract_pdf
from tools.import_chants.modeles import UnsupportedFile

# Texte d'au moins 40 caractères pour qu'un PDF de test ne soit pas jugé « sans texte ».
VERS = "Le vent du soir se lève sur la ville"


def lignes_pdf(*lignes):
    return extract_pdf(pdf_bytes(list(lignes)))


def test_police_grasse_donne_une_ligne_grasse():
    lignes = lignes_pdf({"texte": VERS, "y": 100, "gras": True}, {"texte": VERS + " encore", "y": 114})
    assert [(l.gras, l.italique) for l in lignes] == [(True, False), (False, False)]


def test_soulignement_detecte_sous_le_texte():
    lignes = lignes_pdf({"texte": "Pardon", "y": 100, "gras": True, "souligne": True},
                        {"texte": VERS, "y": 120})
    assert [(l.texte, l.souligne) for l in lignes] == [("Pardon", True), (VERS, False)]


def test_faux_gras_texte_imprime_plusieurs_fois_est_gras_et_non_duplique():
    lignes = lignes_pdf({"texte": VERS, "y": 100, "copies": 4}, {"texte": VERS + " encore", "y": 114})
    assert [l.texte for l in lignes] == [VERS, VERS + " encore"]
    assert lignes[0].gras is True and lignes[1].gras is False


def test_deux_copies_ne_font_pas_un_faux_gras():
    assert lignes_pdf({"texte": VERS, "y": 100, "copies": 2})[0].gras is False


def test_ligne_vide_restituee_quand_l_ecart_depasse_1_75_fois_la_taille():
    lignes = lignes_pdf(
        {"texte": VERS, "y": 100}, {"texte": VERS + " un", "y": 114},     # écart 14 pour 12 pt : même bloc
        {"texte": VERS + " deux", "y": 150},                                 # écart 36 : ligne vide
    )
    assert [l.vide_avant for l in lignes] == [True, False, True]  # la première ligne d'une page ouvre un bloc


def test_pdf_image_seule_est_refuse():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_pdf(pdf_image_seule())
    assert "image" in erreur.value.raison


def test_pdf_en_syllabes_est_une_partition():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_pdf(pdf_en_syllabes())
    assert "Partition" in erreur.value.raison


def test_fichier_illisible():
    with pytest.raises(UnsupportedFile):
        extract_pdf(b"ceci n'est pas un PDF")


@pytest.mark.parametrize("polices, caracteres, empans, images, attendu", [
    ({"Helvetica"}, 500, 20, 0, None),                              # feuille normale
    ({"Maestro", "TimesNewRomanPSMT"}, 500, 20, 0, "Partition"),    # police de notation musicale
    ({"EngraverTextT"}, 500, 20, 0, "Partition"),
    ({"Helvetica"}, 300, 150, 0, "Partition"),                      # syllabes isolées
    ({"Helvetica"}, 10, 2, 1, "image"),                             # scan
    ({"Helvetica"}, 10, 2, 0, "vide"),
])
def test_raison_de_refus(polices, caracteres, empans, images, attendu):
    raison = _raison_de_refus(polices, caracteres, empans, images)
    assert (raison is None) if attendu is None else (attendu in raison)
