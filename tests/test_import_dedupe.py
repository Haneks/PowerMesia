"""Tests de tools/import_chants/dedupe.py : doublons de la bibliothèque."""

import pytest

from context.models import Chant, SectionChant, TypeSection
from tools.import_chants.dedupe import Doublon, cle_chant, normaliser, titres_voisins, trouver_doublon

REFRAIN = SectionChant("R", TypeSection.REFRAIN, ["Chantons au bord du fleuve"])


def chant(titre="Venez au fleuve", recueil=None, paroles="Chantons au bord du fleuve", structure=()):
    return Chant(id=1, titre=titre, recueil=recueil, paroles=paroles, structure=list(structure))


@pytest.mark.parametrize("a, b", [
    ("Venez au Fleuve", "venez au fleuve"),
    ("Venez, au fleuve !", "VENEZ AU FLEUVE"),
    ("  Venez   au\nfleuve ", "venez au fleuve"),
    ("Étoile d’or", "etoile d'or"),
    ("Cœur de Jésus", "coeur de jesus"),
    ("Cæsar", "caesar"),
])
def test_normaliser_ignore_casse_accents_ponctuation_et_espaces(a, b):
    assert normaliser(a) == normaliser(b)


def test_normaliser_conserve_les_chiffres_et_les_mots():
    assert normaliser("Psaume 22") != normaliser("Psaume 23")
    assert normaliser(None) == ""


def test_la_cle_depend_du_titre_et_du_recueil():
    assert cle_chant("Pardon", "Lyon centre 4") != cle_chant("Pardon", "Lyon centre 2")
    assert cle_chant("Pardon", None) != cle_chant("Pardon", "Lyon centre 4")
    assert cle_chant("PARDON", " lyon  centre 4 ") == cle_chant("Pardon", "Lyon centre 4")


def test_titre_inconnu_donne_aucun():
    r = trouver_doublon("Autre chant", None, "Un texte", [], [], [chant()])
    assert r.statut is Doublon.AUCUN and r.existant is None


def test_bibliotheque_vide_donne_aucun():
    assert trouver_doublon("Venez au fleuve", None, "x", [], [], []).statut is Doublon.AUCUN


def test_titre_vide_ne_donne_jamais_un_doublon():
    assert trouver_doublon("  ", None, "x", [], [], [chant(titre="")]).statut is Doublon.AUCUN


def test_meme_titre_et_meme_texte_donne_identique():
    existant = chant()
    r = trouver_doublon("VENEZ AU FLEUVE", None, "Chantons, au bord du fleuve.", [], [], [existant])
    assert r.statut is Doublon.IDENTIQUE and r.existant is existant


def test_meme_titre_texte_different_donne_different():
    existant = chant()
    r = trouver_doublon("Venez au fleuve", None, "Un tout autre texte", [], [], [existant])
    assert r.statut is Doublon.DIFFERENT and r.existant is existant


def test_recueil_different_n_est_pas_un_doublon():
    r = trouver_doublon("Pardon", "Lyon centre 4", "Prends pitié", [], [], [chant(titre="Pardon", recueil="Lyon centre 2", paroles="Prends pitié")])
    assert r.statut is Doublon.AUCUN


def test_meme_texte_mais_import_structure_sur_chant_sans_structure_donne_different():
    # Le remplacement apporterait les refrains en gras : on ne l'ignore pas silencieusement
    r = trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", [REFRAIN], ["R"], [chant()])
    assert r.statut is Doublon.DIFFERENT


def test_meme_texte_et_chant_existant_deja_structure_donne_identique():
    existant = chant(structure=[REFRAIN])
    assert trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", [REFRAIN], [], [existant]).statut is Doublon.IDENTIQUE


def test_meme_texte_sans_structure_des_deux_cotes_donne_identique():
    assert trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", [], [], [chant()]).statut is Doublon.IDENTIQUE


def test_plusieurs_chants_de_meme_cle_prefere_l_identique():
    ancien = chant(paroles="Une ancienne version")
    ancien.id = 7
    courant = chant()
    courant.id = 9
    r = trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", [], [], [ancien, courant])
    assert r.statut is Doublon.IDENTIQUE and r.existant.id == 9


COUPLET = SectionChant("1", TypeSection.COUPLET, ["Premier couplet inventé"])
PONT = SectionChant("P", TypeSection.PONT, ["Premier couplet inventé"])
TEXTE = "Chantons au bord du fleuve\n\nPremier couplet inventé"


def structure_existante(structure, ordre):
    existant = chant(paroles=TEXTE, structure=structure)
    existant.ordre = list(ordre)
    return existant


def test_types_de_section_differents_donnent_different():
    existant = structure_existante([REFRAIN, COUPLET], ["R", "1", "R"])
    r = trouver_doublon("Venez au fleuve", None, TEXTE, [REFRAIN, PONT], ["R", "P", "R"], [existant])
    assert r.statut is Doublon.DIFFERENT and r.existant is existant


def test_ordre_chante_different_donne_different():
    existant = structure_existante([REFRAIN, COUPLET], ["R", "1", "R"])
    r = trouver_doublon("Venez au fleuve", None, TEXTE, [REFRAIN, COUPLET], ["R", "1"], [existant])
    assert r.statut is Doublon.DIFFERENT


def test_memes_types_lignes_et_ordre_donnent_identique():
    existant = structure_existante([REFRAIN, COUPLET], ["R", "1", "R"])
    r = trouver_doublon("Venez au fleuve", None, TEXTE, [REFRAIN, COUPLET], ["R", "1", "R"], [existant])
    assert r.statut is Doublon.IDENTIQUE


def test_lignes_de_section_differentes_donnent_different():
    existant = structure_existante([REFRAIN, COUPLET], ["R", "1", "R"])
    autre = SectionChant("1", TypeSection.COUPLET, ["Premier couplet"])
    r = trouver_doublon("Venez au fleuve", None, TEXTE, [REFRAIN, autre], ["R", "1", "R"], [existant])
    assert r.statut is Doublon.DIFFERENT


def test_import_structure_sur_existant_sans_structure_donne_different_meme_texte():
    r = trouver_doublon("Venez au fleuve", None, TEXTE, [REFRAIN, COUPLET], ["R", "1", "R"], [chant(paroles=TEXTE)])
    assert r.statut is Doublon.DIFFERENT


def test_import_sans_structure_sur_existant_structure_donne_identique():
    existant = structure_existante([REFRAIN, COUPLET], ["R", "1", "R"])
    assert trouver_doublon("Venez au fleuve", None, TEXTE, [], [], [existant]).statut is Doublon.IDENTIQUE


def test_titres_voisins_meme_titre_sans_recueil_ou_autre_recueil():
    sans = chant(titre="Pardon")
    sans.id = 2
    autre = chant(titre="PARDON", recueil="Lyon centre 2")
    autre.id = 3
    voisins = titres_voisins("Pardon", "Lyon centre 4", [sans, autre])
    assert [c.id for c in voisins] == [2, 3]
    assert [c.id for c in titres_voisins("Pardon", None, [sans, autre])] == [3]


def test_titres_voisins_exclut_titre_different_et_meme_cle():
    meme = chant(titre="Pardon", recueil="Lyon centre 4")
    autre_titre = chant(titre="Autre chant")
    assert titres_voisins("Pardon", "Lyon centre 4", [meme, autre_titre]) == []
    assert titres_voisins("  ", None, [chant(titre="")]) == []
