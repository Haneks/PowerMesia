"""Page « Générer une messe » : les blocs se réordonnent et se suppriment par la liste glissable
(plus de boutons Monter / Descendre), et le PowerPoint suit l'ordre choisi.

Le composant est remplacé par un double (voir conftest.ComposantGlissableFactice) : ces tests
vérifient le branchement de app.py, pas le glisser-déposer du navigateur."""

import io
from pathlib import Path

from pptx import Presentation
from streamlit.testing.v1 import AppTest

from context.models import LectureLiturgique, TypeLecture

APP = str(Path(__file__).resolve().parents[1] / "app.py")

LECTURES = [
    LectureLiturgique(TypeLecture.PREMIERE_LECTURE, "Is 55, 6-9", "T1", "Lecture du livre d'Isaïe", "TEXTE-PREMIERE-LECTURE"),
    LectureLiturgique(TypeLecture.EVANGILE, "Mt 20, 1-16", "T2", "Évangile selon saint Matthieu", "TEXTE-EVANGILE"),
]


def _page_messe() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["aelf_data"] = {"informations": {"jour_liturgique_nom": "Jour de test"}, "lectures": LECTURES}
    return at.run()


def _titres(glissable) -> list[str]:
    return [item["titre"] for item in glissable.dernier()]


def _bouton_generer(at):
    return next(b for b in at.button if b.label == "📥 Générer et télécharger PPTX")


def _ordre_dans_le_pptx(octets: bytes, *marqueurs: str) -> list[str]:
    texte_par_diapo = []
    for diapo in Presentation(io.BytesIO(octets)).slides:
        texte_par_diapo.append(" ".join(s.text_frame.text for s in diapo.shapes if s.has_text_frame))
    trouves = [(i, m) for m in marqueurs for i, t in enumerate(texte_par_diapo) if m in t]
    return [m for _, m in sorted(trouves)]


def test_les_blocs_sont_dans_la_liste_glissable_avec_un_identifiant_chacun(glissable):
    at = _page_messe()
    assert not at.exception
    assert _titres(glissable) == ["1ère lecture — Is 55, 6-9", "Évangile — Mt 20, 1-16"]
    ids = [item["id"] for item in glissable.dernier()]
    assert len(set(ids)) == 2 and all(ids)
    assert all(item["apercu"] for item in glissable.dernier())


def test_plus_de_boutons_monter_descendre_ni_supprimer_par_bloc(glissable):
    at = _page_messe()
    libelles = [b.label for b in at.button]
    assert not [l for l in libelles if "Monter" in l or "Descendre" in l or l == "🗑️ Supprimer"]
    assert not [b.key for b in at.button if b.key and b.key.startswith(("up_", "down_", "del_0", "del_1"))]


def test_glisser_un_bloc_change_l_ordre_a_l_ecran_et_dans_la_session(glissable):
    at = _page_messe()
    premier, second = (item["id"] for item in glissable.dernier())

    glissable.evenement = ("reorder", [second, premier])
    at.run()
    assert not at.exception
    assert [b["reference"] for b in at.session_state["blocs"]] == ["Mt 20, 1-16", "Is 55, 6-9"]
    assert [b["ordre"] for b in at.session_state["blocs"]] == [0, 1]

    at.run()  # la réexécution suivante affiche le nouvel ordre
    assert _titres(glissable) == ["Évangile — Mt 20, 1-16", "1ère lecture — Is 55, 6-9"]


def test_supprimer_un_bloc_le_retire_de_la_liste_et_de_la_session(glissable):
    at = _page_messe()
    premier = glissable.dernier()[0]["id"]

    glissable.evenement = ("delete", premier)
    at.run()
    assert not at.exception
    assert [b["reference"] for b in at.session_state["blocs"]] == ["Mt 20, 1-16"]

    at.run()
    assert _titres(glissable) == ["Évangile — Mt 20, 1-16"]


def test_un_ordre_perime_ne_fait_pas_disparaitre_un_bloc(glissable):
    at = _page_messe()
    premier, second = (item["id"] for item in glissable.dernier())

    # Le navigateur renvoie un ordre qui ne connaît ni le 2e bloc ni un bloc déjà supprimé.
    glissable.evenement = ("reorder", ["bloc-disparu", premier])
    at.run()
    assert not at.exception
    assert {b["uid"] for b in at.session_state["blocs"]} == {premier, second}


def test_le_powerpoint_suit_l_ordre_choisi_en_glissant(glissable):
    at = _page_messe()
    premier, second = (item["id"] for item in glissable.dernier())

    glissable.evenement = ("reorder", [second, premier])
    at.run()
    _bouton_generer(at.run()).click().run()
    assert not at.exception

    ordre = _ordre_dans_le_pptx(at.session_state["pptx_bytes"], "TEXTE-PREMIERE-LECTURE", "TEXTE-EVANGILE")
    assert ordre == ["TEXTE-EVANGILE", "TEXTE-PREMIERE-LECTURE"]


def test_une_session_ouverte_avant_cette_version_recoit_des_identifiants(glissable):
    # Des blocs déjà en session, sans « uid » (créés par l'ancienne version de la page).
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["aelf_data"] = {"informations": {"jour_liturgique_nom": "Jour de test"}, "lectures": LECTURES}
    at.session_state["blocs"] = [
        {"ordre": 0, "type": "lecture", "lecture_type": "evangile", "reference": "Mt 1", "contenu": "<p>Ancien</p>"},
    ]
    at.run()
    assert not at.exception
    assert glissable.dernier()[0]["id"]
    assert glissable.dernier()[0]["apercu"] == "Ancien"
