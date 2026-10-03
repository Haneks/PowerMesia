"""Tests de la page « 📥 Importer des chants » (AppTest).

Le dépôt de fichiers n'est pas pilotable par AppTest : l'analyse est injectée dans l'état de session
(`import_analyse`, avec la signature d'un dépôt vide), ce qui exerce toute la vérification et l'import."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from context.models import Chant, MomentLiturgique as M, SectionChant, TypeSection
from tests.helpers_import import L
from tools.db_handler import create_chant, delete_chant, init_db, search_chants
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
    assert not at.text_input  # l'analyse est vidée après l'import : plus aucune carte à vérifier


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
    bouton_import(at).click().run()
    [reste] = search_chants()
    assert reste.paroles == "Un ancien texte"
    assert any("1 ignoré(s)" in s.value for s in at.success)


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
