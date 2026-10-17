"""Les tests ne doivent jamais toucher la vraie bibliothèque ni le dossier de sortie."""

import os
import tempfile
from types import SimpleNamespace

import pytest

# Avant tout import de tools.db_handler / app, qui lisent ces variables à l'import.
# Affectation directe (pas setdefault) : une variable déjà exportée dans le shell ne doit
# jamais faire pointer les tests vers une vraie bibliothèque.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="powermesia-data-")
os.environ["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="powermesia-out-")


class ComposantGlissableFactice:
    """Remplace le composant de liste glissable dans les tests de l'application.

    AppTest (Streamlit 1.55) exécute les scripts avec un runtime simulé qui ne sait pas monter un
    composant v2 : même un composant de trois lignes y échoue. Ce double garde ce qui compte pour
    app.py : il reçoit les éléments à afficher (`appels`) et, quand un test le demande
    (`evenement`), reproduit ce que fait Streamlit à la réexécution suivant une action dans le
    navigateur : valeur rangée sous la clé du composant, puis rappel appelé.
    Le vrai glisser-déposer se vérifie dans un navigateur, pas ici.
    """

    def __init__(self):
        self.appels = []
        self.evenement = None  # ("reorder", [uid, ...]) ou ("delete", uid), consommé à l'appel suivant

    def dernier(self) -> list[dict]:
        return self.appels[-1]

    def __call__(self, items, *, key, on_reorder=None, on_delete=None):
        import streamlit as st

        self.appels.append(items)
        if self.evenement is None:
            return None
        nom, valeur = self.evenement
        self.evenement = None
        st.session_state[key] = SimpleNamespace(
            reorder=valeur if nom == "reorder" else None,
            delete=valeur if nom == "delete" else None,
        )
        (on_reorder if nom == "reorder" else on_delete)()
        return None


@pytest.fixture(autouse=True)
def glissable(monkeypatch):
    faux = ComposantGlissableFactice()
    monkeypatch.setattr("components.sortable_blocs.sortable_blocs", faux)
    return faux
