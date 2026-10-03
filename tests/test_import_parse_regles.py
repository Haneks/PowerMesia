"""
Tests de verrouillage de tools/import_chants/parse.py : une règle de la spec §6 par test.
Textes inventés (aucune parole réelle).
"""

import re

import pytest

from context.models import MomentLiturgique as M
from context.models import TypeSection
from tests.helpers_import import L
from tools.import_chants.parse import parse_lines


def chant_de(*lignes, nom="chant inventé.docx"):
    """Le seul chant d'un fichier sans en-tête (chant seul)."""
    [chant] = parse_lines(list(lignes), nom).chants
    return chant


def ids(chant) -> list[str]:
    return [s.id for s in chant.structure]


def toutes_les_lignes(chant) -> list[str]:
    """Les paroles du chant, section après section."""
    return [ligne for s in chant.structure for ligne in s.lignes]


def titre_sous_entree(vers: str) -> str:
    """Titre proposé pour une entrée dont le seul vers (en gras) est `vers`."""
    [chant] = parse_lines([L("Entrée", gras=True, souligne=True), L(vers, gras=True)], "x.docx").chants
    return chant.titre


# --- Consignes entre crochets : ignorées avec une note (spec §6) ---

def test_consigne_entre_crochets_ignoree_et_signalee():
    chant = chant_de(L("Premier couplet inventé"), L("[Tous se lèvent]"), L("Suite du couplet"))
    assert chant.structure[0].lignes == ["Premier couplet inventé", "Suite du couplet"]
    assert chant.notes == ["Consigne ignorée : [Tous se lèvent]"]


def test_consigne_entre_deux_blocs_ne_les_fusionne_pas():
    # la ligne vide précédait la consigne : la ligne qui la suit doit hériter de cette coupure
    chant = chant_de(L("Premier couplet inventé"), L("[Procession]", vide=True), L("Second couplet inventé"))
    assert [s.lignes for s in chant.structure] == [["Premier couplet inventé"], ["Second couplet inventé"]]
    assert chant.notes == ["Consigne ignorée : [Procession]"]


def test_crochet_au_milieu_d_un_vers_ou_non_apparie_n_est_pas_une_consigne():
    chant = chant_de(L("Je chante [encore] pour toi"), L("[Mal refermé"), L("Fin] du vers"),
                     L("Nous chantons [en chœur]"))
    assert toutes_les_lignes(chant) == ["Je chante [encore] pour toi", "[Mal refermé", "Fin] du vers",
                                        "Nous chantons [en chœur]"]
    assert chant.notes == []


def test_un_chant_qui_ne_contient_qu_une_consigne_n_est_pas_importe():
    lignes = [L("Entrée", gras=True, souligne=True), L("[Procession des enfants]")]
    resultat = parse_lines(lignes, "x.docx")
    assert resultat.chants == []
    assert any("Entrée" in n and "Consigne ignorée" in n for n in resultat.notes)


# --- En-tête de feuille à n'importe quelle position (spec §6) ---

def test_en_tete_de_feuille_en_milieu_de_fichier_n_est_pas_un_chant():
    lignes = [
        L("Dimanche 4 octobre 2026", gras=True, souligne=True),
        L("Entrée", gras=True, souligne=True, vide=True), L("Chantons au bord de l'eau", gras=True),
        L("Dimanche 11 octobre 2026", gras=True, souligne=True, vide=True),
        L("Communion", gras=True, souligne=True, vide=True), L("Le fleuve descend vers la mer"),
    ]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.COMMUNION]
    assert resultat.notes == ["Feuille : Dimanche 4 octobre 2026", "Feuille : Dimanche 11 octobre 2026"]


def test_en_tete_de_feuille_en_milieu_de_fichier_signale_ses_lignes_ignorees():
    lignes = [
        L("Entrée", gras=True, souligne=True), L("Chantons au bord de l'eau", gras=True),
        L("Dimanche 11 octobre 2026", gras=True, souligne=True, vide=True), L("Lectures du jour"),
        L("Communion", gras=True, souligne=True, vide=True), L("Le fleuve descend vers la mer"),
    ]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.COMMUNION]
    assert resultat.notes == ["Feuille : Dimanche 11 octobre 2026 (1 ligne(s) ignorée(s))"]


# --- Un titre explicite n'est jamais écrasé (priorité 1 de la spec) ---

def test_titre_explicite_n_est_pas_ecrase_par_une_ligne_en_majuscules():
    lignes = [L("Title: Mon vrai titre", gras=True), L("Artist: Un recueil", gras=True),
              L("CHANTONS TOUS", gras=True)]
    chants = parse_lines(lignes, "x.docx").chants
    assert [c.titre for c in chants] == ["Mon vrai titre"]
    assert chants[0].recueil == "Un recueil"
    assert toutes_les_lignes(chants[0]) == ["CHANTONS TOUS"]


# --- 1. Ordre explicite du document conservé quand le refrain est répété ---

def test_ordre_du_document_conserve_quand_le_refrain_revient_apres_le_dernier_couplet():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("1. Premier couplet inventé", vide=True),
        L("2. Second couplet inventé", vide=True), L("Chantons au bord de l'eau", gras=True, vide=True),
    )
    assert ids(chant) == ["R", "1", "2"]
    assert chant.ordre == ["R", "1", "2", "R"]  # et non « R 1 R 2 R »


# --- 2. Titre tiré d'un vers : 6 mots au plus, sans mot-outil final ---

def test_titre_tire_d_un_vers_a_six_mots_au_plus():
    titre = titre_sous_entree("Nos voix montent doucement jusqu'au grand ciel bleu")
    assert titre == "Nos voix montent doucement jusqu'au grand"
    assert len(titre.split()) == 6


@pytest.mark.parametrize("vers, attendu", [
    ("Nos voix portent la joie de tous les enfants", "Nos voix portent la joie"),
    ("Ensemble pour le monde et la paix", "Ensemble pour le monde"),
], ids=["de_final_retire", "et_la_finaux_retires"])
def test_titre_tire_d_un_vers_ne_finit_pas_par_un_mot_outil(vers, attendu):
    assert titre_sous_entree(vers) == attendu


# --- 3. Le titre vient du refrain, pas de la première section ---

def test_le_titre_vient_du_refrain_et_non_de_la_premiere_section():
    lignes = [L("Entrée", gras=True, souligne=True), L("Premier couplet inventé"),
              L("Chantons au bord de l'eau", gras=True, vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert ids(chant) == ["1", "R"]
    assert chant.titre == "Chantons au bord de l'eau"


# --- 4. Suffixes de reprise ---

@pytest.mark.parametrize("ligne", [
    "Saint, saint, saint x2", "Saint, saint, saint 2x", "Saint, saint, saint (2x)",
    "Saint, saint, saint bis", "Saint, saint, saint (bis)",
], ids=["x2", "2x", "2x_entre_parentheses", "bis", "bis_entre_parentheses"])
def test_suffixe_de_reprise_retire_et_signale(ligne):
    [chant] = parse_lines([L("Sanctus", gras=True, souligne=True), L(ligne)], "x.docx").chants
    assert chant.structure[0].lignes == ["Saint, saint, saint"]
    assert any("reprise" in n for n in chant.notes)


def test_une_ligne_bis_seule_sous_l_en_tete_n_est_pas_un_recueil():
    lignes = [L("Prière universelle", gras=True, souligne=True), L("(bis)"), L("Entends nos prières")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None


# --- 5. En-tête de feuille : une date, « Messe… » ou « Eglise… » ---

@pytest.mark.parametrize("texte", [
    "Dimanche 4 octobre 2026", "Samedi soir", "4 octobre 2026", "1er novembre",
], ids=["jour_et_date", "jour_de_semaine_seul", "jour_et_mois_seuls", "premier_du_mois"])
def test_un_en_tete_avec_une_date_est_l_en_tete_de_la_feuille(texte):
    lignes = [L(texte, gras=True, souligne=True), L("Entrée", gras=True, souligne=True, vide=True),
              L("Un vers inventé")]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE]
    assert resultat.notes == [f"Feuille : {texte}"]


@pytest.mark.parametrize("texte", ["Messe de la Trinité", "Eglise de la Colline", "Église de la Colline"],
                         ids=["messe", "eglise", "eglise_accentuee"])
def test_messe_ou_eglise_suivi_d_une_ligne_vide_est_l_en_tete_de_la_feuille(texte):
    lignes = [L(texte, gras=True, souligne=True), L("Entrée", gras=True, souligne=True, vide=True),
              L("Un vers inventé")]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE]
    assert resultat.notes == [f"Feuille : {texte}"]


def test_messe_avec_une_ligne_de_texte_collee_derriere_reste_un_chant():
    lignes = [L("Messe de la Trinité", gras=True, souligne=True), L("Venez chanter la paix")]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.titre for c in resultat.chants] == ["Messe de la Trinité"]
    assert resultat.notes == []


# --- 6. Vocabulaire des moments ---

_VOCABULAIRE = [
    ("Entrée", M.ENTREE), ("Chant d'entrée", M.ENTREE), ("Pardon", M.PARDON), ("Kyrie", M.PARDON),
    ("Kirie", M.PARDON), ("Gloire", M.GLOIRE), ("Gloire à Dieu", M.GLOIRE), ("Gloria", M.GLOIRE),
    ("Psaume", M.PSAUME), ("Alléluia", M.ALLELUIA), ("Évangile", M.ALLELUIA), ("Acclamation", M.ALLELUIA),
    ("Prière universelle", M.PU), ("Prières universelles", M.PU), ("Offertoire", M.OFFERTOIRE),
    ("Sanctus", M.SANCTUS), ("Saint", M.SANCTUS), ("Tu es saint", M.SANCTUS),
    ("Anamnèse", M.ANAMNESE), ("Anamnese", M.ANAMNESE),
    ("Agneau", M.AGNEAU), ("Agneau de Dieu", M.AGNEAU), ("Agnus", M.AGNEAU),
    ("Communion", M.COMMUNION), ("Chant de la communion", M.COMMUNION),
    ("Envoi", M.ENVOI), ("Sortie", M.ENVOI), ("Procession", M.AUTRE),
]


@pytest.mark.parametrize("en_tete, moment", _VOCABULAIRE,
                         ids=[en_tete.lower().replace(" ", "_").replace("'", "_") for en_tete, _ in _VOCABULAIRE])
def test_vocabulaire_des_moments(en_tete, moment):
    [chant] = parse_lines([L(en_tete, gras=True, souligne=True), L("Un vers inventé", gras=True)], "x.docx").chants
    assert chant.moment is moment


# --- 7. Titres « Nom – Recueil » des ordinaires ; pas des moments libres ---

@pytest.mark.parametrize("nom", [
    "Pardon", "Gloire", "Sanctus", "Anamnèse", "Agneau de Dieu", "Prière universelle", "Alléluia", "Psaume",
])
def test_titre_d_un_ordinaire_est_le_nom_et_le_recueil(nom):
    lignes = [L(f"{nom} (Recueil Aurore 2)", gras=True, souligne=True), L("Un vers inventé", gras=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.titre == f"{nom} – Recueil Aurore 2"
    assert chant.recueil == "Recueil Aurore 2"


@pytest.mark.parametrize("nom", ["Entrée", "Communion", "Envoi"])
def test_le_titre_d_une_entree_d_une_communion_ou_d_un_envoi_vient_du_refrain(nom):
    lignes = [L(f"{nom} (Recueil Aurore 2)", gras=True, souligne=True), L("Chantons au bord de l'eau", gras=True),
              L("Premier couplet inventé", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.titre == "Chantons au bord de l'eau"
    assert chant.recueil == "Recueil Aurore 2"


# --- 8. Formes d'étiquettes de section ---

@pytest.mark.parametrize("etiquette, type_attendu, id_attendu", [
    ("2)", TypeSection.COUPLET, "2"), ("Couplet 2", TypeSection.COUPLET, "2"),
    ("Pont", TypeSection.PONT, "P"), ("Pont :", TypeSection.PONT, "P"),
    ("Refrain", TypeSection.REFRAIN, "R"), ("Refrain :", TypeSection.REFRAIN, "R"),
    ("R/", TypeSection.REFRAIN, "R"),
], ids=["parenthese", "couplet_2", "pont", "pont_deux_points", "refrain", "refrain_deux_points", "r_barre"])
def test_etiquette_seule_sur_sa_ligne_donne_le_type_de_la_section_suivante(etiquette, type_attendu, id_attendu):
    chant = chant_de(L("Un premier bloc inventé"), L(etiquette, vide=True), L("Un texte inventé"))
    assert chant.structure[1].type is type_attendu
    assert chant.structure[1].id == id_attendu
    assert chant.structure[1].lignes == ["Un texte inventé"]  # l'étiquette est consommée


@pytest.mark.parametrize("etiquette, type_attendu, id_attendu", [
    ("2) Un texte inventé", TypeSection.COUPLET, "2"), ("2. Un texte inventé", TypeSection.COUPLET, "2"),
    ("Couplet 2 : Un texte inventé", TypeSection.COUPLET, "2"),
    ("Pont : Un texte inventé", TypeSection.PONT, "P"),
    ("Refrain : Un texte inventé", TypeSection.REFRAIN, "R"), ("R/ Un texte inventé", TypeSection.REFRAIN, "R"),
    ("Ref. Un texte inventé", TypeSection.REFRAIN, "R"),
], ids=["parenthese", "point", "couplet_2", "pont", "refrain", "r_barre", "ref_point"])
def test_etiquette_suivie_du_texte_sur_la_meme_ligne(etiquette, type_attendu, id_attendu):
    chant = chant_de(L("Un premier bloc inventé"), L(etiquette, vide=True))
    assert chant.structure[1].type is type_attendu
    assert chant.structure[1].id == id_attendu
    assert chant.structure[1].lignes == ["Un texte inventé"]


# --- 9. Avertissements « tout en gras » et « tout en italique » ---

def test_tout_le_chant_en_italique_aucun_refrain_et_avertissement():
    chant = chant_de(L("Premier bloc", italique=True), L("Second bloc", italique=True, vide=True))
    assert all(s.type is TypeSection.COUPLET for s in chant.structure)
    assert len(chant.avertissements) == 1
    assert "italique" in chant.avertissements[0] and "gras" not in chant.avertissements[0]


def test_tout_le_chant_en_gras_avertit_du_gras_et_non_de_l_italique():
    chant = chant_de(L("Premier bloc", gras=True), L("Second bloc", gras=True, vide=True))
    assert len(chant.avertissements) == 1
    assert "gras" in chant.avertissements[0] and "italique" not in chant.avertissements[0]


# --- 10. Gardes de l'en-tête en gras seul ---

def test_en_tete_en_gras_seul_de_six_mots_est_un_en_tete():
    lignes = [L("Agneau de Dieu Recueil Aurore 2", gras=True), L("Prends pitié de nous", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil) == (M.AGNEAU, "Recueil Aurore 2")
    assert toutes_les_lignes(chant) == ["Prends pitié de nous"]


@pytest.mark.parametrize("lignes", [
    [L("Gloire à notre Dieu", gras=True), L("Qui règne dans les cieux")],
    [L("Gloire à notre Dieu !", gras=True), L("Qui règne dans les cieux", vide=True)],
    [L("Gloire à notre Dieu qui règne toujours", gras=True), L("Dans les cieux", vide=True)],
    [L("Premier vers inventé"), L("Gloire à notre Dieu", gras=True), L("Dans les cieux", vide=True)],
    [L("Gloire à notre Dieu"), L("Dans les cieux", vide=True)],
], ids=["suivi_d_une_ligne_non_vide", "ponctuation_finale", "sept_mots", "pas_en_debut_de_bloc", "pas_en_gras"])
def test_une_ligne_de_paroles_qui_commence_par_un_mot_du_vocabulaire_n_est_pas_un_en_tete(lignes):
    chant = chant_de(*lignes)
    assert toutes_les_lignes(chant) == [ligne.texte for ligne in lignes]


# --- 11. Recueil collé à l'en-tête, ou paroles collées ---

def test_apres_trois_espaces_dans_un_en_tete_sans_mot_du_vocabulaire_le_recueil_est_extrait():
    lignes = [L("Le chant du fleuve   Recueil Aurore 2", gras=True, souligne=True), L("Un vers inventé")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.titre, chant.recueil, chant.moment) == ("Le chant du fleuve", "Recueil Aurore 2", M.AUTRE)


def test_apres_trois_espaces_six_mots_sans_ponctuation_sont_un_recueil():
    lignes = [L("Pardon   Recueil de chants de la communauté", gras=True, souligne=True),
              L("Prends pitié de nous", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil == "Recueil de chants de la communauté"
    assert toutes_les_lignes(chant) == ["Prends pitié de nous"]


@pytest.mark.parametrize("collees", [
    "Recueil de chants de la grande communauté",   # 7 mots
    "Seigneur prends pitié de nous, Seigneur",     # ponctuation
], ids=["sept_mots", "ponctuation"])
def test_apres_trois_espaces_sept_mots_ou_ponctuation_ce_sont_des_paroles_collees(collees):
    lignes = [L(f"Pardon   {collees}", gras=True, souligne=True), L("Prends pitié de nous")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None
    assert chant.moment is M.PARDON
    assert toutes_les_lignes(chant) == [collees, "Prends pitié de nous"]  # première ligne du corps


def test_apres_trois_espaces_une_etiquette_de_section_n_est_pas_un_recueil():
    lignes = [L("Communion   Couplet 1", gras=True, souligne=True), L("La rivière chante")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None
    assert ids(chant) == ["1"]
    assert chant.structure[0].lignes == ["La rivière chante"]


# --- 12. Titre tiré du nom du fichier ---

@pytest.mark.parametrize("nom_fichier, titre", [
    ("Venez_au_bord_du_fleuve.docx", "Venez au bord du fleuve"),
    ("C:\\chants\\du dimanche\\Venez au bord du fleuve.DOCX", "Venez au bord du fleuve"),
    ("VENEZ AU BORD DU FLEUVE.PDF", "Venez au bord du fleuve"),
    ("", "Chant"),
], ids=["underscores", "chemin_antislash_et_extension_majuscule", "tout_en_majuscules", "nom_vide"])
def test_titre_d_un_chant_seul_tire_du_nom_du_fichier(nom_fichier, titre):
    chant = chant_de(L("Un vers inventé"), L("Un autre vers inventé", vide=True), nom=nom_fichier)
    assert chant.titre == titre


def test_moment_d_un_chant_seul_lu_dans_un_nom_de_fichier_a_underscores():
    chant = chant_de(L("Un vers inventé"), nom="alleluia_du_matin.docx")
    assert (chant.titre, chant.moment) == ("Alleluia du matin", M.ALLELUIA)


def test_titre_explicite_avec_un_jour_de_la_semaine_n_est_pas_un_en_tete_de_feuille():
    lignes = [L("Title: Dimanche en famille"), L("Artist: Un recueil"), L("Un vers inventé", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.titre == "Dimanche en famille"


# --- C1. Texte collé après le mot-moment d'un en-tête : ni séparateur de tête, ni numéro pris pour un recueil ---

# (en-tête, moment, recueil, titre) ; le corps est toujours un refrain en gras puis un couplet.
_ENTETES_AVEC_SUITE = [
    ("Entrée :", M.ENTREE, None, "Chantons au bord de l'eau"),
    ("Gloire :", M.GLOIRE, None, "Gloire"),
    ("Sanctus :", M.SANCTUS, None, "Sanctus"),
    ("Prière universelle :", M.PU, None, "Prière universelle"),
    ("Psaume 22 :", M.PSAUME, None, "Psaume 22"),
    ("Psaume 22", M.PSAUME, None, "Psaume 22"),
    ("Psaume 22 (21)", M.PSAUME, None, "Psaume 22 (21)"),
    ("Psaume 117", M.PSAUME, None, "Psaume 117"),
    ("Psaume   22", M.PSAUME, None, "Psaume 22"),
    ("Acclamation de l'Évangile", M.ALLELUIA, None, "Acclamation de l'Évangile"),
    ("Agneau de l'Alliance", M.AGNEAU, None, "Agneau de l'Alliance"),
    ("Pardon – Messe du Partage", M.PARDON, "Messe du Partage", "Pardon – Messe du Partage"),
    ("Pardon :   Recueil Aurore 2", M.PARDON, "Recueil Aurore 2", "Pardon – Recueil Aurore 2"),
    ("Gloire à Dieu, au plus haut des cieux", M.GLOIRE, None, "Gloire à Dieu"),
]


@pytest.mark.parametrize("en_tete, moment, recueil, titre", _ENTETES_AVEC_SUITE,
                         ids=["entree_deux_points", "gloire_deux_points", "sanctus_deux_points", "pu_deux_points",
                              "psaume_numero_deux_points", "psaume_numero", "psaume_numero_et_parentheses",
                              "psaume_trois_chiffres", "psaume_numero_apres_trois_espaces", "acclamation_de_l_evangile", "agneau_de_l_alliance",
                              "pardon_tiret_recueil", "pardon_deux_points_puis_recueil",
                              "gloire_paroles_collees"])
def test_texte_apres_le_mot_moment_d_un_en_tete(en_tete, moment, recueil, titre):
    lignes = [L(en_tete, gras=True, souligne=True), L("Chantons au bord de l'eau", gras=True),
              L("Premier couplet inventé", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil, chant.titre) == (moment, recueil, titre)
    premieres = [s.lignes[0] for s in chant.structure]
    assert not any(not re.search(r"\w", ligne) or ligne in ("22 :", "22") for ligne in toutes_les_lignes(chant))
    assert not any(p.startswith((":", ",", "–")) for p in premieres)


def test_des_vraies_paroles_collees_apres_le_moment_restent_des_paroles_sans_ponctuation_de_tete():
    lignes = [L("Gloire à Dieu, au plus haut des cieux", gras=True, souligne=True), L("Et paix sur la terre")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None
    assert toutes_les_lignes(chant) == ["au plus haut des cieux", "Et paix sur la terre"]


def test_entree_deux_points_donne_un_titre_tire_du_refrain_et_pas_de_ligne_de_ponctuation():
    lignes = [L("Entrée :", gras=True, souligne=True), L("Premier couplet inventé"),
              L("Chantons au bord de l'eau", gras=True, vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert ids(chant) == ["1", "R"]
    assert chant.titre == "Chantons au bord de l'eau"
    assert toutes_les_lignes(chant) == ["Premier couplet inventé", "Chantons au bord de l'eau"]


def test_psaume_avec_recueil_reel_garde_son_numero_dans_le_titre():
    lignes = [L("Psaume 22   Recueil Aurore 2", gras=True, souligne=True), L("Le Seigneur est mon berger", gras=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.recueil, chant.titre) == ("Recueil Aurore 2", "Psaume 22 – Recueil Aurore 2")
