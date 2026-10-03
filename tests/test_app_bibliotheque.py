"""Page « Bibliothèque de chants » : recueil et structure visibles, avertissement avant de perdre la structure."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from context.models import Chant, SectionChant, TypeSection
from tools.db_handler import create_chant, delete_chant, init_db, search_chants

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def bibliotheque_vide():
    init_db()
    for chant in search_chants():
        delete_chant(chant.id)


def _page() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    return at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()


def _chant(structure: bool) -> None:
    create_chant(Chant(
        titre="Chant de la bibliothèque", paroles="Refrain inventé\n\nCouplet inventé", recueil="Lyon centre 4",
        structure=[SectionChant("R", TypeSection.REFRAIN, ["Refrain inventé"]),
                   SectionChant("1", TypeSection.COUPLET, ["Couplet inventé"])] if structure else [],
        ordre=["R", "1", "R"] if structure else [],
    ))


def test_la_recherche_montre_le_recueil_et_la_structure():
    _chant(structure=True)
    at = _page()
    textes = " ".join([w.value for w in at.markdown] + [c.value for c in at.caption])
    assert "Lyon centre 4" in textes and "R · 1 · R" in textes


def test_modifier_un_chant_structure_avertit_avant_la_perte_de_la_structure():
    _chant(structure=True)
    assert any("supprime la structure" in c.value for c in _page().caption)


def test_modifier_un_chant_sans_structure_n_avertit_pas():
    _chant(structure=False)
    assert not any("supprime la structure" in c.value for c in _page().caption)
