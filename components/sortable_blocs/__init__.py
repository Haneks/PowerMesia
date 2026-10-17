"""Liste de blocs réordonnable par glisser-déposer (poignée ≡), avec suppression.

Composant Streamlit v2 sans dépendance pip : SortableJS (MIT, voir LICENSE-SortableJS) est copié
dans ce dossier, donc rien n'est chargé depuis internet.
"""

from pathlib import Path

import streamlit as st

_DOSSIER = Path(__file__).resolve().parent


def _lire(nom: str) -> str:
    return (_DOSSIER / nom).read_text(encoding="utf-8")


# SortableJS est un module UMD : enveloppé dans une fonction, il se range dans `module.exports`
# et ne crée aucune variable globale. Le composant (module ES) le voit comme une simple constante.
_JS = (
    "const Sortable = (() => {\n"
    "  const module = { exports: {} };\n"
    "  const exports = module.exports;\n"
    f"{_lire('Sortable.min.js')}\n"
    "  return module.exports;\n"
    "})();\n"
    f"{_lire('sortable_blocs.js')}"
)

_composant = st.components.v2.component(
    "sortable_blocs",
    css=_lire("sortable_blocs.css"),
    js=_JS,
    isolate_styles=False,
)


def sortable_blocs(items: list[dict], *, key: str, on_reorder=None, on_delete=None):
    """Affiche `items` (dicts `id`, `titre`, `apercu`) en liste glissable.

    `on_reorder` et `on_delete` sont appelés au début de la réexécution qui suit l'action ;
    la valeur est alors lue dans `st.session_state[key].reorder` (liste des id dans le
    nouvel ordre) ou `st.session_state[key].delete` (id du bloc à supprimer).
    """
    return _composant(
        key=key,
        data={"items": items},
        on_reorder_change=on_reorder or (lambda: None),
        on_delete_change=on_delete or (lambda: None),
    )
