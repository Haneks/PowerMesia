"""Test de fumée de l'application Streamlit."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _library_page() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()
    return at


def test_both_pages_load_without_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Rechercher", "Ajouter", "Modifier / Supprimer"]


def test_moment_filter_lists_every_liturgical_moment():
    at = _library_page()
    moment_filter = next(s for s in at.selectbox if s.label == "Moment liturgique")
    options = set(moment_filter.options)
    assert {"pardon", "gloire", "psaume", "alleluia", "pu", "sanctus", "anamnese", "agneau"} <= options
    assert {"entree", "offertoire", "communion", "envoi", "autre"} <= options
