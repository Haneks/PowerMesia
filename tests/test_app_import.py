"""Tests de la page « 📥 Importer des chants » (AppTest).

Le dépôt de fichiers n'est pas pilotable par AppTest : l'analyse est injectée dans l'état de session
(`import_analyse`, avec la signature d'un dépôt vide), ce qui exerce toute la vérification et l'import."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from streamlit.testing.v1 import AppTest

from context.models import Chant, MomentLiturgique as M, SectionChant, TypeSection
from tests.helpers_import import L
from tools.db_handler import create_chant, delete_chant, init_db, search_chants
from tools.import_chants import ecran
from tools.import_chants.ecran import _analyses_a_jour, _cle_fichier
from tools.import_chants.parse import parse_lines

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGE = "📥 Importer des chants"

FEUILLE = [
    L("Entrée", gras=True, souligne=True),
    L("Chantons au bord du fleuve", gras=True),
    L("Premier couplet inventé", vide=True),
    L("Second couplet inventé", vide=True),
]


@pytest.fixture(autouse=True)
def bibliotheque_vide():
    init_db()
    for chant in search_chants():
        delete_chant(chant.id)


def chants_analyses(lignes=FEUILLE):
    return parse_lines(lignes, "feuille.docx").chants


def page(fichiers: list[dict]) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(PAGE).run()
    at.session_state["import_analyse"] = {"signature": (), "fichiers": fichiers}
    return at.run()


def fichier(chants=None, nom="feuille.docx", notes=(), refus=None):
    return {"nom": nom, "chants": chants if chants is not None else chants_analyses(), "notes": list(notes), "refus": refus}


def widget(elements, suffixe):
    return next(e for e in elements if e.key and e.key.endswith(suffixe))


def bouton_import(at):
    return next(b for b in at.button if b.key == "import_go")


def marqueurs(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_la_page_existe_et_s_affiche_sans_fichier():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(PAGE).run()
    assert not at.exception
    assert PAGE in at.sidebar.radio[0].options
    assert not [b for b in at.button if b.key == "import_go"]  # rien à importer tant qu'aucun fichier n'est analysé


def test_fichier_refuse_est_liste_avec_sa_raison_sans_bloquer_les_autres():
    at = page([fichier(nom="partition.pdf", chants=[], refus="Partition : les paroles sont mêlées aux notes"), fichier()])
    assert not at.exception
    assert any("partition.pdf" in w.value and "Partition" in w.value for w in at.warning)
    assert "🆕 nouveau" in marqueurs(at)
    assert bouton_import(at).label == "Importer 1 chant"


def test_carte_propose_titre_moment_sections_et_ordre():
    at = page([fichier()])
    assert widget(at.text_input, "_titre").value == "Chantons au bord du fleuve"
    assert widget(at.multiselect, "_moments").value == ["entree"]
    assert [widget(at.selectbox, f"_s{k}_type").value for k in range(3)] == ["refrain", "couplet", "couplet"]
    assert widget(at.checkbox, "_repeter").value is True
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · R · 2 · R"


def test_importer_ajoute_le_chant_avec_structure_et_ordre_puis_affiche_le_recapitulatif():
    at = page([fichier()])
    bouton_import(at).click().run()
    assert not at.exception
    [chant] = search_chants()
    assert chant.titre == "Chantons au bord du fleuve" and chant.moments == [M.ENTREE]
    assert chant.ordre == ["R", "1", "R", "2", "R"]
    assert [s.type for s in chant.structure] == [TypeSection.REFRAIN, TypeSection.COUPLET, TypeSection.COUPLET]
    assert any("1 ajouté(s)" in s.value for s in at.success)
    assert at.session_state["import_analyse"]["fichiers"] == []  # l'analyse est vidée après l'import


def test_decocher_importer_n_ajoute_rien():
    at = page([fichier()])
    widget(at.checkbox, "_ok").uncheck().run()
    assert bouton_import(at).disabled
    assert search_chants() == []


def test_titre_et_recueil_modifies_sont_enregistres():
    at = page([fichier()])
    widget(at.text_input, "_titre").set_value("Venez au fleuve").run()
    widget(at.text_input, "_recueil").set_value("Lyon centre 4").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert (chant.titre, chant.recueil) == ("Venez au fleuve", "Lyon centre 4")


def test_changer_un_type_de_section_recalcule_l_ordre():
    at = page([fichier()])
    widget(at.selectbox, "_s2_type").set_value("pont").run()
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · R · P · R"
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert [s.id for s in chant.structure] == ["R", "1", "P"] and chant.ordre == ["R", "1", "R", "P", "R"]


def test_decocher_repeter_le_refrain_donne_l_ordre_du_document():
    at = page([fichier()])
    widget(at.checkbox, "_repeter").uncheck().run()
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · 2"


def test_ordre_invalide_rend_le_chant_non_importable():
    at = page([fichier()])
    next(t for t in at.text_input if t.label.startswith("Ordre chanté")).set_value("R 1 9").run()
    assert any("inconnue" in e.value for e in at.error)
    assert bouton_import(at).disabled


def test_section_videe_n_est_pas_importee():
    at = page([fichier()])
    widget(at.text_area, "_s2_texte").set_value("").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert [s.id for s in chant.structure] == ["R", "1"] and chant.ordre == ["R", "1", "R"]


def test_notes_et_avertissements_sont_affiches():
    sans_marque = chants_analyses([L("Communion", gras=True, souligne=True), L("Un vers inventé"), L("Un autre vers inventé", vide=True)])
    at = page([fichier(chants=sans_marque, notes=["Feuille : Messe de test"])])
    assert any("refrain" in w.value.lower() for w in at.warning)
    assert any("Messe de test" in c.value for c in at.caption)


def test_doublon_identique_est_signale_et_ignore():
    create_chant(Chant(
        titre="Chantons au bord du fleuve", moments=[M.ENTREE],
        paroles="Chantons au bord du fleuve\n\nPremier couplet inventé\n\nSecond couplet inventé",
        structure=[SectionChant("R", TypeSection.REFRAIN, ["Chantons au bord du fleuve"]),
                   SectionChant("1", TypeSection.COUPLET, ["Premier couplet inventé"]),
                   SectionChant("2", TypeSection.COUPLET, ["Second couplet inventé"])],
        ordre=["R", "1", "R", "2", "R"],
    ))
    at = page([fichier()])
    assert "déjà présent (identique)" in marqueurs(at)
    assert bouton_import(at).disabled
    assert len(search_chants()) == 1


def _chant_existant_different() -> int:
    return create_chant(Chant(titre="Chantons au bord du fleuve", paroles="Un ancien texte", moments=[M.COMMUNION], auteur="Une autrice"))


def test_doublon_different_propose_trois_actions_dont_ignorer_par_defaut():
    _chant_existant_different()
    at = page([fichier()])
    assert "déjà présent (différent)" in marqueurs(at)
    action = widget(at.radio, "_action")
    assert action.value == "ignorer" and action.options == ["Ignorer (conserver l'existant)", "Remplacer", "Ajouter quand même"]
    assert any("Un ancien texte" in t.value for t in at.text)  # ancien et nouveau texte affichés
    assert bouton_import(at).disabled and bouton_import(at).label == "Importer 0 chant"  # « Ignorer » ne fait rien
    [reste] = search_chants()
    assert reste.paroles == "Un ancien texte"


def test_doublon_different_remplacer():
    ancien = _chant_existant_different()
    at = page([fichier()])
    widget(at.radio, "_action").set_value("remplacer").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert chant.id == ancien and chant.ordre == ["R", "1", "R", "2", "R"] and chant.auteur == "Une autrice"
    assert any("1 remplacé(s)" in s.value for s in at.success)


def test_doublon_different_ajouter_quand_meme():
    _chant_existant_different()
    at = page([fichier()])
    widget(at.radio, "_action").set_value("ajouter").run()
    bouton_import(at).click().run()
    assert len(search_chants()) == 2


def _chant_identique_a_la_feuille(recueil=None) -> int:
    return create_chant(Chant(
        titre="Chantons au bord du fleuve", moments=[M.ENTREE], recueil=recueil,
        paroles="Chantons au bord du fleuve\n\nPremier couplet inventé\n\nSecond couplet inventé",
        structure=[SectionChant("R", TypeSection.REFRAIN, ["Chantons au bord du fleuve"]),
                   SectionChant("1", TypeSection.COUPLET, ["Premier couplet inventé"]),
                   SectionChant("2", TypeSection.COUPLET, ["Second couplet inventé"])],
        ordre=["R", "1", "R", "2", "R"],
    ))


def test_meme_texte_mais_structure_corrigee_a_l_ecran_est_un_doublon_different_remplacable():
    ancien = _chant_identique_a_la_feuille()
    at = page([fichier()])
    assert "déjà présent (identique)" in marqueurs(at) and bouton_import(at).disabled
    widget(at.selectbox, "_s2_type").set_value("pont").run()
    assert "déjà présent (différent)" in marqueurs(at)
    assert widget(at.radio, "_action").value == "ignorer"
    assert any("Même texte : seule la structure (refrains, ordre chanté) diffère." in c.value for c in at.caption)
    widget(at.radio, "_action").set_value("remplacer").run()
    assert not bouton_import(at).disabled
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert chant.id == ancien and [s.id for s in chant.structure] == ["R", "1", "P"]
    assert [s.type for s in chant.structure][2] is TypeSection.PONT


def test_texte_different_n_affiche_pas_la_legende_de_structure():
    _chant_existant_different()
    at = page([fichier()])
    assert not any("seule la structure" in c.value for c in at.caption)


def test_chant_nouveau_de_meme_titre_dans_un_autre_recueil_affiche_une_legende_de_verification():
    _chant_identique_a_la_feuille(recueil="Lyon centre 2")
    at = page([fichier()])
    assert "🆕 nouveau" in marqueurs(at)
    legende = next(c.value for c in at.caption if "Un chant de même titre existe déjà" in c.value)
    assert "Lyon centre 2" in legende and "vérifiez qu'il ne s'agit pas du même chant" in legende


def test_pas_de_legende_de_titre_voisin_sans_chant_de_meme_titre():
    at = page([fichier()])
    assert not any("même titre existe déjà" in c.value for c in at.caption)


AUTRE_FEUILLE = [
    L("Communion", gras=True, souligne=True),
    L("Partageons le pain inventé", gras=True),
    L("Un couplet de communion inventé", vide=True),
]


def test_le_libelle_ne_compte_pas_les_doublons_differents_laisses_sur_ignorer():
    _chant_existant_different()
    at = page([fichier(), fichier(chants=chants_analyses(AUTRE_FEUILLE), nom="autre.docx")])
    assert bouton_import(at).label == "Importer 1 chant" and not bouton_import(at).disabled
    widget(at.radio, "_action").set_value("remplacer").run()
    assert bouton_import(at).label == "Importer 2 chants"


def test_la_legende_demande_de_rester_sur_la_page():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(PAGE).run()
    assert any("Restez sur cette page pendant la vérification : changer de page vide le dépôt." in c.value for c in at.caption)


def test_les_saisies_d_une_carte_survivent_a_l_ajout_d_un_autre_fichier():
    a = {**fichier(nom="a.docx"), "cle": "a"}
    b = {**fichier(chants=chants_analyses(AUTRE_FEUILLE), nom="b.docx"), "cle": "b"}
    at = page([a, b])
    at.text_input(key="imp_0_a_0_titre").set_value("Titre corrigé à la main").run()
    c = {**fichier(chants=chants_analyses(AUTRE_FEUILLE), nom="c.docx"), "cle": "c"}
    at.session_state["import_analyse"] = {"signature": (), "fichiers": [c, a, b]}  # le nouveau fichier passe devant
    at.run()
    assert not at.exception
    assert at.text_input(key="imp_0_a_0_titre").value == "Titre corrigé à la main"
    assert at.text_input(key="imp_0_c_0_titre").value == "Partageons le pain inventé"


class _Analyse:
    chants, notes = [], []


def _faux_fichier(nom, taille=10, file_id=None):
    return SimpleNamespace(name=nom, size=taille, file_id=file_id, getvalue=lambda: b"x")


def test_cle_fichier_prefere_l_identifiant_du_depot_sinon_nom_et_taille():
    assert _cle_fichier(_faux_fichier("a.docx", 10, "id-1")) == "id-1"
    assert _cle_fichier(_faux_fichier("a.docx", 10)) == "a.docx-10"


def test_deux_fichiers_de_meme_nom_et_meme_taille_ont_des_cles_differentes(monkeypatch):
    monkeypatch.setattr(ecran, "analyser_fichier", lambda nom, octets: _Analyse())
    analyses = _analyses_a_jour([_faux_fichier("a.docx"), _faux_fichier("a.docx"), _faux_fichier("a.docx")], [])
    assert [x["cle"] for x in analyses] == ["a.docx-10", "a.docx-10-2", "a.docx-10-3"]


def test_analyses_a_jour_ne_reanalyse_pas_un_fichier_deja_analyse(monkeypatch):
    appels = []

    def faux_analyser(nom, octets):
        appels.append(nom)
        return _Analyse()

    monkeypatch.setattr(ecran, "analyser_fichier", faux_analyser)
    premieres = _analyses_a_jour([_faux_fichier("a.docx"), _faux_fichier("b.docx")], [])
    assert appels == ["a.docx", "b.docx"]
    suivantes = _analyses_a_jour([_faux_fichier("c.docx"), _faux_fichier("a.docx"), _faux_fichier("b.docx")], premieres)
    assert appels == ["a.docx", "b.docx", "c.docx"]  # seul le nouveau est analysé
    assert [x["nom"] for x in suivantes] == ["c.docx", "a.docx", "b.docx"]
    assert suivantes[1] is premieres[0] and suivantes[2] is premieres[1]
