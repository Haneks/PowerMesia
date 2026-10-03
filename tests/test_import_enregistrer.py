"""Tests de tools/import_chants/enregistrer.py : écriture en base et décision par doublon."""

import pytest

from context.models import Chant, MomentLiturgique as M, SectionChant, TypeSection
from tools.db_handler import create_chant, get_chant, init_db, search_chants
from tools.import_chants.dedupe import Doublon
from tools.import_chants.enregistrer import Action, Decision, importer_chants

R, C = TypeSection.REFRAIN, TypeSection.COUPLET


@pytest.fixture
def db(tmp_path):
    chemin = tmp_path / "chants.db"
    init_db(chemin)
    return chemin


def nouveau(titre="Venez au fleuve", paroles="Chantons au bord du fleuve\n\nPremier couplet inventé", recueil=None):
    return Chant(
        titre=titre, paroles=paroles, recueil=recueil, moments=[M.ENTREE],
        structure=[SectionChant("R", R, ["Chantons au bord du fleuve"]), SectionChant("1", C, ["Premier couplet inventé"])],
        ordre=["R", "1", "R"],
    )


def test_chant_nouveau_est_ajoute_avec_structure_ordre_et_moments(db):
    recap = importer_chants([Decision(nouveau(recueil="Lyon centre 4"))], db)
    assert recap.ajoutes == ["Venez au fleuve"] and not recap.erreurs
    [enregistre] = search_chants(db_path=db)
    assert enregistre.recueil == "Lyon centre 4"
    assert enregistre.ordre == ["R", "1", "R"] and [s.id for s in enregistre.structure] == ["R", "1"]
    assert enregistre.moments == [M.ENTREE]


def test_chant_identique_est_ignore_meme_si_l_utilisateur_veut_l_ajouter(db):
    create_chant(nouveau(), db)
    decision = Decision(nouveau(), Action.AJOUTER, Doublon.IDENTIQUE)
    recap = importer_chants([decision], db)
    assert recap.ajoutes == [] and "identique" in recap.ignores[0]
    assert len(search_chants(db_path=db)) == 1


def test_doublon_different_ignore_par_defaut(db):
    create_chant(nouveau(paroles="Un ancien texte"), db)
    recap = importer_chants([Decision(nouveau(), Action.IGNORER, Doublon.DIFFERENT)], db)
    assert recap.ignores and not recap.ajoutes and not recap.remplaces
    [reste] = search_chants(db_path=db)
    assert reste.paroles == "Un ancien texte"


def test_doublon_different_remplace_garde_l_identite_et_les_champs_saisis(db):
    ancien = nouveau(paroles="Un ancien texte")
    ancien.auteur, ancien.compositeur, ancien.reference, ancien.notes = "Une autrice", "Un compositeur", "B 12", "Une note"
    ancien.structure, ancien.ordre = [], []
    ancien_id = create_chant(ancien, db)
    recap = importer_chants([Decision(nouveau(recueil=None), Action.REMPLACER, Doublon.DIFFERENT)], db)
    assert recap.remplaces == ["Venez au fleuve"]
    [chant] = search_chants(db_path=db)
    assert chant.id == ancien_id
    assert chant.paroles.startswith("Chantons au bord du fleuve") and chant.ordre == ["R", "1", "R"]
    assert (chant.auteur, chant.compositeur, chant.reference, chant.notes) == ("Une autrice", "Un compositeur", "B 12", "Une note")


def test_remplacement_reunit_les_moments_sans_perdre_ceux_de_la_bibliotheque(db):
    ancien = nouveau(paroles="Un ancien texte")
    ancien.moments = [M.ENTREE, M.COMMUNION, M.ENVOI]
    create_chant(ancien, db)
    importe = nouveau()
    importe.moments = [M.ENTREE, M.OFFERTOIRE]
    recap = importer_chants([Decision(importe, Action.REMPLACER, Doublon.DIFFERENT)], db)
    assert recap.remplaces == ["Venez au fleuve"]
    [chant] = search_chants(db_path=db)
    # La base ne mémorise pas l'ordre des moments (relus triés) : ici on vérifie l'ensemble, sans doublon.
    assert len(chant.moments) == 4 and set(chant.moments) == {M.ENTREE, M.COMMUNION, M.ENVOI, M.OFFERTOIRE}


def test_remplacement_place_les_moments_existants_d_abord_puis_les_nouveaux_sans_doublon(monkeypatch):
    import tools.import_chants.enregistrer as module

    enregistres = []
    monkeypatch.setattr(module, "update_chant", lambda chant, db_path=None: enregistres.append(list(chant.moments)))
    existant = nouveau(paroles="Un ancien texte")
    existant.moments = [M.ENTREE, M.COMMUNION, M.ENVOI]
    importe = nouveau()
    importe.moments = [M.ENTREE, M.OFFERTOIRE]
    module._remplacer(existant, importe, None)
    assert enregistres == [[M.ENTREE, M.COMMUNION, M.ENVOI, M.OFFERTOIRE]]


def test_chant_vu_different_devenu_aucun_a_l_enregistrement_est_cree_meme_si_ignorer(db):
    # Le chant existant a disparu entre l'écran de vérification et l'enregistrement.
    recap = importer_chants([Decision(nouveau(), Action.IGNORER, Doublon.DIFFERENT)], db)
    assert recap.ajoutes == ["Venez au fleuve"] and not recap.ignores
    assert len(search_chants(db_path=db)) == 1


def test_meme_texte_sans_structure_est_remplace_pour_apporter_les_refrains(db):
    ancien = nouveau()
    ancien.structure, ancien.ordre = [], []
    create_chant(ancien, db)
    recap = importer_chants([Decision(nouveau(), Action.REMPLACER, Doublon.DIFFERENT)], db)
    assert recap.remplaces and get_chant(search_chants(db_path=db)[0].id, db).structure


def test_doublon_different_ajouter_quand_meme(db):
    create_chant(nouveau(paroles="Un ancien texte"), db)
    recap = importer_chants([Decision(nouveau(), Action.AJOUTER, Doublon.DIFFERENT)], db)
    assert recap.ajoutes == ["Venez au fleuve"]
    assert len(search_chants(db_path=db)) == 2


def test_doublon_apparu_dans_le_meme_lot_n_est_pas_ajoute_deux_fois(db):
    lot = [Decision(nouveau()), Decision(nouveau())]  # tous deux « nouveau » à l'écran
    recap = importer_chants(lot, db)
    assert recap.ajoutes == ["Venez au fleuve"] and len(recap.ignores) == 1
    assert len(search_chants(db_path=db)) == 1


def test_doublon_different_apparu_dans_le_meme_lot_est_ignore(db):
    lot = [Decision(nouveau()), Decision(nouveau(paroles="Un autre texte"))]
    recap = importer_chants(lot, db)
    assert "doublon dans cet import" in recap.ignores[0]
    assert len(search_chants(db_path=db)) == 1


def test_une_erreur_n_arrete_pas_les_autres_chants(db, monkeypatch):
    import tools.import_chants.enregistrer as module

    vrai = module.create_chant

    def create_capricieux(chant, db_path=None):
        if chant.titre == "Chant fautif":
            raise RuntimeError("base verrouillée")
        return vrai(chant, db_path)

    monkeypatch.setattr(module, "create_chant", create_capricieux)
    recap = importer_chants([Decision(nouveau("Chant fautif")), Decision(nouveau("Un bon chant"))], db)
    assert recap.ajoutes == ["Un bon chant"]
    assert len(recap.erreurs) == 1 and "Chant fautif" in recap.erreurs[0] and "base verrouillée" in recap.erreurs[0]


def test_liste_vide_ne_fait_rien(db):
    recap = importer_chants([], db)
    assert (recap.ajoutes, recap.remplaces, recap.ignores, recap.erreurs) == ([], [], [], [])
