"""Tests de tools/import_chants/parse.py : reconnaissance des chants, moments, recueils et titres."""

from context.models import MomentLiturgique as M
from tests.helpers_import import L
from tools.import_chants.parse import parse_lines


def feuille() -> list:
    """Une feuille de messe inventée : en-tête, un chant d'entrée, un pardon, un gloire."""
    return [
        L("Messe du village   Dimanche 4 octobre 2026", gras=True, souligne=True),
        L("Entrée", gras=True, souligne=True, vide=True),
        L("Venez au bord du fleuve, chantons la lumière", gras=True),
        L("Le soleil se lève sur la rivière", gras=True),
        L("1. L'eau claire descend de la colline", vide=True),
        L("Les enfants courent vers le pont"),
        L("Pardon (Recueil Aurore 2)", gras=True, souligne=True, vide=True),
        L("Seigneur, nous marchons dans la nuit", vide=True),
        L("Gloire a Dieu   Recueil Aurore 2", gras=True, souligne=True, vide=True),
        L("Gloire au vent qui passe, gloire aux rivières !", gras=True, vide=True),
        L("Les montagnes chantent le matin", vide=True),
    ]


def test_une_feuille_est_decoupee_en_chants_avec_moments_et_recueils():
    resultat = parse_lines(feuille(), "feuille.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.PARDON, M.GLOIRE]
    assert [c.recueil for c in resultat.chants] == [None, "Recueil Aurore 2", "Recueil Aurore 2"]
    assert resultat.notes == ["Feuille : Messe du village Dimanche 4 octobre 2026"]


def test_titres_proposes():
    titres = [c.titre for c in parse_lines(feuille(), "feuille.docx").chants]
    assert titres == [
        "Venez au bord du fleuve",              # entrée : début du premier refrain
        "Pardon – Recueil Aurore 2",             # ordinaire : en-tête et recueil
        "Gloire a Dieu – Recueil Aurore 2",
    ]


def test_une_ligne_de_refrain_qui_commence_par_un_mot_du_vocabulaire_n_est_pas_un_en_tete():
    # « Gloire au vent qui passe, … » est en gras mais contient de la ponctuation et fait partie du chant
    resultat = parse_lines(feuille(), "feuille.docx")
    assert len(resultat.chants) == 3


def test_en_tete_title_artist():
    lignes = [
        L("Title: ALLÉLUIA", gras=True), L("Artist: Recueil Aurore 2", gras=True),
        L("Alléluia, chantons", vide=True),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil, chant.titre) == (M.ALLELUIA, "Recueil Aurore 2", "Alléluia – Recueil Aurore 2")


def test_en_tete_en_gras_seul_sur_sa_propre_ligne():
    lignes = [
        L("Agneau  Recueil Aurore 2", gras=True, vide=True),
        L("Toi l'Agneau qui enlèves nos fautes", vide=True),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil) == (M.AGNEAU, "Recueil Aurore 2")


def test_recueil_entre_parentheses_sur_la_ligne_suivante():
    lignes = [L("Pardon", gras=True, souligne=True), L("(Recueil Aurore 2)"), L("Prends pitié de nous", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil == "Recueil Aurore 2"
    assert chant.structure[0].lignes == ["Prends pitié de nous"]


def test_etiquettes_de_section_soulignees_ne_sont_pas_des_chants():
    lignes = [
        L("Communion", gras=True, souligne=True),
        L("Couplet 1", gras=True, souligne=True, vide=True), L("La rivière chante"),
        L("Refrain", gras=True, souligne=True, vide=True), L("Chantons tous ensemble", gras=True),
        L("Pont", gras=True, souligne=True, vide=True), L("Plus haut que les nuages"),
    ]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.COMMUNION]
    assert [s.id for s in resultat.chants[0].structure] == ["1", "R", "P"]


def test_renvoi_vers_un_autre_chant_n_est_pas_importe():
    lignes = [L("Sortie", gras=True, souligne=True), L("VOIR CHANT D'ENTREE", gras=True, souligne=True)]
    resultat = parse_lines(lignes, "x.docx")
    assert resultat.chants == []
    assert any("Sortie" in n and "Renvoi" in n for n in resultat.notes)


def test_psaume_ne_garde_que_le_refrain_en_gras():
    lignes = [
        L("Psaume", gras=True, souligne=True),
        L("Le fleuve chante la paix du Seigneur.", gras=True),
        L("Premier verset du psaume", vide=True), L("Second verset du psaume"),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert [(s.id, s.lignes) for s in chant.structure] == [("R", ["Le fleuve chante la paix du Seigneur."])]
    assert any("psaume" in n.lower() for n in chant.notes)


def test_titre_en_majuscules_sous_l_en_tete():
    lignes = [L("Communion", gras=True, souligne=True), L("LE CHANT DU FLEUVE", gras=True, vide=True),
              L("Le fleuve descend vers la mer", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.titre == "Le chant du fleuve"
    assert chant.moment is M.COMMUNION


def test_chant_seul_titre_et_moment_viennent_du_nom_du_fichier():
    [chant] = parse_lines([L("Alléluia, chantons le matin"), L("Alléluia, chantons le soir")],
                          "C:/chants/alleluia du matin.docx").chants
    assert (chant.titre, chant.moment, chant.recueil) == ("Alleluia du matin", M.ALLELUIA, None)


def test_vocabulaire_varie():
    cas = {"Chant de Pardon": M.PARDON, "Prières universelle": M.PU, "Gloria": M.GLOIRE, "Agnus Dei": M.AGNEAU,
           "Saint": M.SANCTUS, "Evangile": M.ALLELUIA, "Sortie": M.ENVOI, "Offertoire": M.OFFERTOIRE}
    for en_tete, moment in cas.items():
        [chant] = parse_lines([L(en_tete, gras=True, souligne=True), L("Un vers inventé")], "x.docx").chants
        assert chant.moment is moment, en_tete


def test_les_reprises_2x_sont_retirees_et_signalees():
    lignes = [L("Sanctus", gras=True, souligne=True), L("Saint, saint, saint 2x"), L("Le ciel chante 2X")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.structure[0].lignes == ["Saint, saint, saint", "Le ciel chante"]
    assert any("reprise" in n for n in chant.notes)


def test_bis_en_fin_de_ligne_est_une_reprise_et_non_un_recueil():
    lignes = [L("Prière universelle (bis)", gras=True, souligne=True), L("Entends nos prières (bis)")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None
    assert chant.structure[0].lignes == ["Entends nos prières"]


def test_lignes_avant_le_premier_chant_sont_signalees():
    lignes = [L("Un texte d'introduction"), L("Entrée", gras=True, souligne=True), L("Un vers inventé")]
    resultat = parse_lines(lignes, "x.docx")
    assert any("avant le premier chant" in n for n in resultat.notes)
    assert len(resultat.chants) == 1


def test_fichier_sans_texte_ne_donne_aucun_chant():
    assert parse_lines([], "x.docx").chants == []
