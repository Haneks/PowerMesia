"""Tests de tools/import_chants/brouillon.py : édition des sections et de l'ordre, conversion en Chant."""

import pytest

from context.models import MomentLiturgique as M
from context.models import SectionChant, TypeSection
from tools.import_chants.brouillon import (
    SectionEditee,
    chant_depuis_brouillon,
    ordre_depuis_texte,
    ordre_en_texte,
    ordre_initial,
    sections_depuis_edition,
    sections_editees,
)
from tools.import_chants.modeles import ParsedSong

R, C, P = TypeSection.REFRAIN, TypeSection.COUPLET, TypeSection.PONT


def chant_analyse(structure, ordre):
    return ParsedSong(titre="Venez au fleuve", moment=M.ENTREE, structure=structure, ordre=ordre)


def trois_sections():
    return [
        SectionChant("R", R, ["Chantons au bord du fleuve"]),
        SectionChant("1", C, ["Premier couplet inventé"]),
        SectionChant("2", C, ["Second couplet inventé"]),
    ]


def test_sections_editees_reprend_types_et_textes_multilignes():
    editees = sections_editees(chant_analyse(trois_sections(), []))
    assert [(e.type, e.texte) for e in editees] == [
        (R, "Chantons au bord du fleuve"), (C, "Premier couplet inventé"), (C, "Second couplet inventé"),
    ]
    assert sections_editees(chant_analyse([SectionChant("1", C, ["a", "b"])], []))[0].texte == "a\nb"


def test_renumerotation_apres_changement_de_type():
    editees = [SectionEditee(R, "Un refrain"), SectionEditee(C, "Un couplet"), SectionEditee(R, "Un autre refrain"),
               SectionEditee(P, "Un pont"), SectionEditee(C, "Un dernier couplet"), SectionEditee(P, "Un second pont")]
    assert [s.id for s in sections_depuis_edition(editees)] == ["R", "1", "R2", "P", "2", "P2"]


def test_sections_vides_ecartees_et_lignes_nettoyees():
    editees = [SectionEditee(C, "  Un vers  \n\n  Un autre vers "), SectionEditee(C, "   \n "), SectionEditee(C, "Fin")]
    sections = sections_depuis_edition(editees)
    assert [(s.id, s.lignes) for s in sections] == [("1", ["Un vers", "Un autre vers"]), ("2", ["Fin"])]


def test_ordre_initial_garde_l_ordre_du_document_quand_rien_n_a_change():
    chant = chant_analyse(trois_sections(), ["R", "1", "2", "R"])  # ordre explicite : pas R 1 R 2 R
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["R", "1", "2", "R"]


def test_ordre_initial_suit_la_renumerotation_des_couplets():
    # Document étiqueté 1. 3. : l'analyse a gardé « 3 » ; l'écran renumérote en « 2 »
    structure = [SectionChant("R", R, ["Un refrain"]), SectionChant("1", C, ["a"]), SectionChant("3", C, ["b"])]
    chant = chant_analyse(structure, ["R", "1", "R", "3", "R"])
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["R", "1", "R", "2", "R"]


def test_ordre_initial_sans_repetition_donne_l_ordre_du_document():
    chant = chant_analyse(trois_sections(), ["R", "1", "R", "2", "R"])
    assert ordre_initial(chant, sections_editees(chant), repeter=False) == ["R", "1", "2"]


def test_ordre_initial_recalcule_quand_un_type_change():
    chant = chant_analyse(trois_sections(), ["R", "1", "R", "2", "R"])
    editees = sections_editees(chant)
    editees[2].type = P
    assert ordre_initial(chant, editees, repeter=True) == ["R", "1", "R", "P", "R"]


def test_ordre_initial_recalcule_quand_une_section_est_videe():
    chant = chant_analyse(trois_sections(), ["R", "1", "2", "R"])
    editees = sections_editees(chant)
    editees[1].texte = ""
    assert ordre_initial(chant, editees, repeter=True) == ["R", "1", "R"]


def test_ordre_initial_recalcule_quand_l_ordre_cite_une_section_absente():
    # L'ordre du document cite « 9 », qui n'existe pas dans la structure : on ne le reprend pas tel quel
    chant = chant_analyse(trois_sections(), ["R", "1", "9", "R"])
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["R", "1", "R", "2", "R"]


def test_ordre_initial_sans_refrain_donne_l_ordre_du_document():
    structure = [SectionChant("1", C, ["a"]), SectionChant("2", C, ["b"])]
    chant = chant_analyse(structure, ["1", "2"])
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["1", "2"]


def test_ordre_en_texte_et_retour():
    sections = trois_sections()
    assert ordre_en_texte(["R", "1", "R", "2", "R"]) == "R · 1 · R · 2 · R"
    assert ordre_depuis_texte("R · 1 · R · 2 · R", sections) == (["R", "1", "R", "2", "R"], None)


@pytest.mark.parametrize("texte", ["R 1 R 2", "r, 1, R, 2", "R;1;R;2", "  R   1 R 2  "])
def test_ordre_depuis_texte_accepte_plusieurs_separateurs_et_la_casse(texte):
    assert ordre_depuis_texte(texte, trois_sections()) == (["R", "1", "R", "2"], None)


def test_ordre_depuis_texte_refuse_une_section_inconnue():
    ordre, erreur = ordre_depuis_texte("R 1 9", trois_sections())
    assert ordre == [] and "9" in erreur


def test_ordre_depuis_texte_refuse_un_ordre_vide():
    assert ordre_depuis_texte("  ·  ", trois_sections())[1] == "L'ordre chanté est vide"


def test_chant_depuis_brouillon_complet():
    editees = [SectionEditee(R, "Chantons au bord du fleuve"), SectionEditee(C, "Premier couplet inventé")]
    chant, erreur = chant_depuis_brouillon("  Venez au fleuve ", [M.ENTREE, M.COMMUNION], " Lyon centre 4 ", editees, "R · 1 · R")
    assert erreur is None
    assert (chant.titre, chant.recueil, chant.moments, chant.ordre) == ("Venez au fleuve", "Lyon centre 4", [M.ENTREE, M.COMMUNION], ["R", "1", "R"])
    assert chant.paroles == "Chantons au bord du fleuve\n\nPremier couplet inventé"
    assert [(s.id, s.type) for s in chant.structure] == [("R", R), ("1", C)]


def test_chant_depuis_brouillon_valeurs_par_defaut():
    chant, _ = chant_depuis_brouillon("Un chant", [], "  ", [SectionEditee(C, "Un vers")], "1")
    assert chant.moments == [M.AUTRE] and chant.recueil is None


@pytest.mark.parametrize("titre, editees, ordre, attendu", [
    ("  ", [SectionEditee(C, "Un vers")], "1", "titre"),
    ("Un chant", [SectionEditee(C, "  ")], "1", "aucune parole"),
    ("Un chant", [SectionEditee(C, "Un vers")], "1 7", "inconnue"),
    ("Un chant", [SectionEditee(C, "Un vers")], "", "vide"),
], ids=["titre-vide", "sans-paroles", "ordre-inconnu", "ordre-vide"])
def test_chant_depuis_brouillon_refuse_un_brouillon_inutilisable(titre, editees, ordre, attendu):
    chant, erreur = chant_depuis_brouillon(titre, [M.ENTREE], None, editees, ordre)
    assert chant is None and attendu in erreur
