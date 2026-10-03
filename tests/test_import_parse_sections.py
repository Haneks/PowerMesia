"""Tests de tools/import_chants/parse.py : sections, refrain et ordre chanté d'un chant."""

from context.models import TypeSection
from tests.helpers_import import L
from tools.import_chants.parse import parse_lines


def chant_de(*lignes):
    """Le seul chant d'un fichier sans en-tête (chant seul)."""
    [chant] = parse_lines(list(lignes), "chant inventé.docx").chants
    return chant


def ids(chant) -> list[str]:
    return [s.id for s in chant.structure]


def test_refrain_en_gras_avec_couplets_numerotes():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Alléluia pour la rivière", gras=True),
        L("1. Le matin se lève sur la ville", vide=True), L("Les cloches annoncent le jour"),
        L("2. Le soir descend sur la vallée", vide=True), L("Nous rendons grâce pour ce jour"),
    )
    assert ids(chant) == ["R", "1", "2"]
    assert chant.structure[0].type is TypeSection.REFRAIN
    assert chant.structure[1].lignes[0] == "Le matin se lève sur la ville"  # le « 1. » est retiré
    assert chant.ordre == ["R", "1", "R", "2", "R"]


def test_refrain_apres_le_premier_couplet():
    chant = chant_de(
        L("Premier couplet inventé"), L("Chantons au bord de l'eau", gras=True, vide=True),
        L("Second couplet inventé", vide=True),
    )
    assert ids(chant) == ["1", "R", "2"]
    assert chant.ordre == ["1", "R", "2", "R"]


def test_pont_etiquete():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Premier couplet inventé", vide=True),
        L("Pont :", vide=True), L("Plus haut que les nuages"),
    )
    assert ids(chant) == ["R", "1", "P"]
    assert chant.structure[2].type is TypeSection.PONT
    assert chant.structure[2].lignes == ["Plus haut que les nuages"]
    assert chant.ordre == ["R", "1", "R", "P", "R"]


def test_refrain_en_italique_a_defaut_de_gras():
    chant = chant_de(L("Premier couplet inventé"), L("Chantons au bord de l'eau", italique=True, vide=True))
    assert [s.type for s in chant.structure] == [TypeSection.COUPLET, TypeSection.REFRAIN]


def test_le_gras_l_emporte_sur_l_italique():
    chant = chant_de(
        L("Couplet en italique", italique=True), L("Refrain en gras", gras=True, vide=True),
        L("Autre couplet", vide=True),
    )
    assert [s.type for s in chant.structure] == [TypeSection.COUPLET, TypeSection.REFRAIN, TypeSection.COUPLET]


def test_bloc_repete_est_un_refrain_et_l_ordre_du_document_est_conserve():
    chant = chant_de(
        L("Chantons au bord de l'eau"), L("Premier couplet inventé", vide=True),
        L("Chantons au bord de l'eau", vide=True),
    )
    assert ids(chant) == ["R", "1"]
    assert chant.ordre == ["R", "1", "R"]


def test_tout_le_chant_en_gras_aucun_refrain_et_avertissement():
    chant = chant_de(L("Premier bloc", gras=True), L("Second bloc", gras=True, vide=True))
    assert all(s.type is TypeSection.COUPLET for s in chant.structure)
    assert any("gras" in a for a in chant.avertissements)


def test_aucun_refrain_avertissement_et_ordre_du_document():
    chant = chant_de(L("Premier couplet inventé"), L("Second couplet inventé", vide=True))
    assert chant.avertissements == ["Aucun refrain détecté"]
    assert chant.ordre == ["1", "2"]


def test_deux_refrains_differents_gardent_l_ordre_du_document():
    chant = chant_de(
        L("Premier refrain", gras=True), L("Un couplet inventé", vide=True),
        L("Second refrain", gras=True, vide=True),
    )
    assert ids(chant) == ["R", "1", "R2"]
    assert chant.ordre == ["R", "1", "R2"]


def test_numeros_de_couplets_en_double_restent_uniques():
    chant = chant_de(L("1. Premier"), L("1. Deuxième", vide=True), L("1. Troisième", vide=True))
    assert ids(chant) == ["1", "2", "3"]


def test_les_espaces_sont_nettoyees_et_les_lignes_vides_ignorees():
    chant = chant_de(L("  Le vent   se lève\xa0!  "), L("   ", vide=True), L("La mer"))
    assert chant.structure[0].lignes == ["Le vent se lève\xa0!", "La mer"]


def test_l_ordre_ne_reference_que_des_sections_existantes():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Pont :", vide=True), L("Plus haut"),
        L("Un couplet inventé", vide=True), L("Chantons au bord de l'eau", gras=True, vide=True),
    )
    assert set(chant.ordre) <= set(ids(chant))
