"""Tests de tools/import_chants/extract_docx.py (documents Word fabriqués par les tests)."""

import pytest

from tests.helpers_import import docx_bytes
from tools.import_chants.extract_docx import extract_docx
from tools.import_chants.modeles import UnsupportedFile


def test_un_titre_souligne_suivi_de_paroles_dans_le_meme_paragraphe_donne_deux_lignes():
    lignes = extract_docx(docx_bytes([[("Psaume", "gs"), (" Le fleuve chante la paix.", "g")]]))
    assert [l.texte for l in lignes] == ["Psaume", "Le fleuve chante la paix."]
    assert lignes[0].gras and lignes[0].souligne
    assert lignes[1].gras and not lignes[1].souligne


def test_paragraphes_vides_deviennent_vide_avant_de_la_ligne_suivante():
    lignes = extract_docx(docx_bytes(["premier vers", "second vers", "", "", "troisième vers"]))
    assert [(l.texte, l.vide_avant) for l in lignes] == [
        ("premier vers", False), ("second vers", False), ("troisième vers", True)]


def test_retours_a_la_ligne_et_doubles_espaces_separent_les_vers():
    paragraphe = "le vent du soir se lève sur la ville  les cloches annoncent le jour\nla nuit vient"
    assert [l.texte for l in extract_docx(docx_bytes([paragraphe]))] == [
        "le vent du soir se lève sur la ville", "les cloches annoncent le jour", "la nuit vient"]


def test_titre_souligne_garde_ses_espaces_et_n_est_pas_coupe():
    lignes = extract_docx(docx_bytes([[("Gloire a Dieu", "gs"), ("   ", "g"), ("Recueil Aurore 2", "gs")]]))
    assert [l.texte for l in lignes] == ["Gloire a Dieu   Recueil Aurore 2"]


def test_gras_et_italique_par_ligne():
    lignes = extract_docx(docx_bytes([[("refrain en gras", "g")], [("vers en italique", "i")], "vers simple"]))
    assert [(l.gras, l.italique) for l in lignes] == [(True, False), (False, True), (False, False)]


def test_le_gras_peut_venir_du_style_du_paragraphe():
    lignes = extract_docx(docx_bytes(["texte sans gras sur le run"], style_gras=True))
    assert lignes[0].gras is True


def test_fichier_illisible():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_docx(b"ceci n'est pas un fichier Word")
    assert "Word" in erreur.value.raison
