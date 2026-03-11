"""
Générateur de PowerPoint Paroissial - Interface Streamlit.
"""

import os
import sys
from pathlib import Path

# Ajouter la racine du projet au path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Répertoires données/sortie (Docker-friendly: DATA_DIR, OUTPUT_DIR)
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", str(ROOT / "output")))

import streamlit as st

from context.models import Chant, MomentLiturgique, TypeLecture
from tools.aelf_service import get_messe
from tools.db_handler import (
    init_db,
    create_chant,
    get_chant,
    update_chant,
    delete_chant,
    search_chants,
)
from tools.pptx_generator import generate_pptx

# Configuration de la page
st.set_page_config(
    page_title="PowerPoint Paroissial",
    page_icon="⛪",
    layout="wide",
)

st.title("⛪ Générateur de PowerPoint Paroissial")


def _format_lecture_type(t: TypeLecture) -> str:
    d = {
        TypeLecture.PREMIERE_LECTURE: "1ère lecture",
        TypeLecture.PSAUME: "Psaume",
        TypeLecture.DEUXIEME_LECTURE: "2e lecture",
        TypeLecture.EVANGILE: "Évangile",
    }
    return d.get(t, t.value)


# Sidebar
st.sidebar.header("Paramètres")
menu = st.sidebar.radio(
    "Menu",
    ["📅 Générer une messe", "📚 Bibliothèque de chants"],
)

if menu == "📅 Générer une messe":
    init_db()

    date_messe = st.sidebar.date_input("Date de la messe")
    date_str = date_messe.strftime("%Y-%m-%d")

    if st.sidebar.button("Récupérer les lectures"):
        with st.spinner("Appel API AELF..."):
            data = get_messe(date_str)
        st.session_state["aelf_data"] = data
        st.session_state["blocs"] = []

    data = st.session_state.get("aelf_data")
    blocs = st.session_state.get("blocs", [])

    if data and data.get("error"):
        st.error(data["error"])

    if data and data.get("lectures"):
        info = data.get("informations", {}) or {}
        st.success(
            f"**{info.get('jour_liturgique_nom', 'Messe')}** — "
            f"{info.get('couleur', '')} — {info.get('annee', '')}"
        )

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("Blocs de la messe")
            st.caption("Réordonnez les blocs avec ⬆️ / ⬇️ avant de générer le PowerPoint.")
            if not blocs:
                # Construire les blocs initiaux à partir des lectures
                for i, lect in enumerate(data["lectures"]):
                    blocs.append({
                        "ordre": i,
                        "type": "lecture",
                        "lecture_type": lect.type.value,
                        "reference": lect.reference,
                        "intro_lue": lect.intro_lue,
                        "titre": lect.titre,
                        "contenu": lect.contenu,
                    })
                st.session_state["blocs"] = blocs

            for i, b in enumerate(blocs):
                if b.get("type") == "lecture":
                    label = f"{_format_lecture_type(TypeLecture(b.get('lecture_type', 'lecture_1')))} — {b.get('reference', 'Sans ref')}"
                else:
                    label = f"{b.get('type', 'lecture').title()} — {b.get('titre', b.get('reference', 'Bloc'))}"
                with st.expander(f"**{i + 1}.** {label}", expanded=(i == 0)):
                    if b.get("type") == "lecture":
                        st.write(b.get("intro_lue", ""), b.get("reference", ""))
                        st.caption(b.get("contenu", "")[:200] + "...")
                    elif b.get("type") == "chant":
                        st.write("Chant :", b.get("titre", ""))
                    elif b.get("type") == "message":
                        st.write("Message :", b.get("titre", ""))
                    # Ordre : boutons Monter / Descendre / Supprimer
                    btn_col1, btn_col2, btn_col3, _ = st.columns([1, 1, 1, 3])
                    with btn_col1:
                        if st.button("⬆️ Monter", key=f"up_{i}", disabled=(i == 0)):
                            blocs[i], blocs[i - 1] = blocs[i - 1], blocs[i]
                            for j, bloc in enumerate(blocs):
                                bloc["ordre"] = j
                            st.session_state["blocs"] = blocs
                            st.rerun()
                    with btn_col2:
                        if st.button("⬇️ Descendre", key=f"down_{i}", disabled=(i == len(blocs) - 1)):
                            blocs[i], blocs[i + 1] = blocs[i + 1], blocs[i]
                            for j, bloc in enumerate(blocs):
                                bloc["ordre"] = j
                            st.session_state["blocs"] = blocs
                            st.rerun()
                    with btn_col3:
                        if st.button("🗑️ Supprimer", key=f"del_{i}"):
                            blocs.pop(i)
                            for j, bloc in enumerate(blocs):
                                bloc["ordre"] = j
                            st.session_state["blocs"] = blocs
                            st.rerun()

        with col2:
            st.subheader("Ajouter un chant")
            chants = search_chants()
            if chants:
                for c in chants:
                    if st.button(f"➕ {c.titre}", key=f"add_{c.id}"):
                        blocs.append({
                            "ordre": len(blocs),
                            "type": "chant",
                            "chant_id": c.id,
                            "titre": c.titre,
                            "paroles": c.paroles,
                        })
                        st.session_state["blocs"] = blocs
                        st.rerun()
            else:
                st.caption("Aucun chant. Ajoutez-en dans la Bibliothèque.")

            st.subheader("Générer le PowerPoint")
            if st.button("📥 Générer et télécharger PPTX", type="primary"):
                if not blocs:
                    st.warning("Ajoutez au moins un bloc (lectures ou chants).")
                else:
                    out = OUTPUT_DIR / f"messe_{date_str}.pptx"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    pptx_blocs = []
                    for b in blocs:
                        if b.get("type") == "chant":
                            pptx_blocs.append({
                                "type": "chant",
                                "titre": b.get("titre", ""),
                                "paroles": b.get("paroles", ""),
                            })
                        elif b.get("type") == "lecture" and "contenu" in b:
                            pptx_blocs.append({
                                "type": "lecture",
                                "reference": b.get("reference", ""),
                                "intro_lue": b.get("intro_lue", ""),
                                "contenu": b.get("contenu", ""),
                            })
                    generate_pptx(pptx_blocs, out)
                    with open(out, "rb") as f:
                        st.session_state["pptx_bytes"] = f.read()
                    st.session_state["pptx_filename"] = out.name

            if "pptx_bytes" in st.session_state:
                st.download_button(
                    "📥 Télécharger le fichier généré",
                    data=st.session_state["pptx_bytes"],
                    file_name=st.session_state.get("pptx_filename", "messe.pptx"),
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    key="download",
                )

    elif not data:
        st.info("Choisissez une date et cliquez sur **Récupérer les lectures**.")

else:
    # Bibliothèque de chants
    init_db()
    st.subheader("Bibliothèque de chants")

    tab1, tab2, tab3 = st.tabs(["Rechercher", "Ajouter", "Modifier / Supprimer"])

    with tab1:
        q = st.text_input("Recherche (titre, paroles, référence)")
        moment = st.selectbox(
            "Moment liturgique",
            [None, "entree", "offertoire", "communion", "envoi", "autre"],
            format_func=lambda x: "Tous" if x is None else x,
        )
        if st.button("Rechercher"):
            m = MomentLiturgique(moment) if moment else None
            chants = search_chants(query=q or None, moment=m)
            st.session_state["search_results"] = chants
        for c in st.session_state.get("search_results", search_chants()):
            with st.expander(c.titre):
                st.write("Réf:", c.reference or "-")
                st.write("Paroles (extrait):", (c.paroles or "")[:300] + "…" if len(c.paroles or "") > 300 else (c.paroles or ""))

    with tab2:
        with st.form("add_chant"):
            titre = st.text_input("Titre *")
            paroles = st.text_area("Paroles *")
            auteur = st.text_input("Auteur")
            compositeur = st.text_input("Compositeur")
            reference = st.text_input("Référence (ex: B 123)")
            moments = st.multiselect(
                "Moments",
                [m.value for m in MomentLiturgique],
                default=["entree"],
            )
            notes = st.text_area("Notes")
            if st.form_submit_button("Ajouter"):
                if titre and paroles:
                    chant = Chant(
                        titre=titre,
                        paroles=paroles,
                        auteur=auteur or None,
                        compositeur=compositeur or None,
                        reference=reference or None,
                        moments=[MomentLiturgique(m) for m in moments],
                        notes=notes or None,
                    )
                    cid = create_chant(chant)
                    st.success(f"Chant ajouté (id: {cid})")
                else:
                    st.error("Titre et paroles sont obligatoires.")

    with tab3:
        all_chants = search_chants()
        if all_chants:
            sel = st.selectbox(
                "Chant à modifier",
                all_chants,
                format_func=lambda c: f"{c.titre} (id: {c.id})",
            )
            if sel:
                chant = get_chant(sel.id)
                if chant:
                    with st.form("edit_chant"):
                        titre = st.text_input("Titre", value=chant.titre)
                        paroles = st.text_area("Paroles", value=chant.paroles)
                        auteur = st.text_input("Auteur", value=chant.auteur or "")
                        moments = st.multiselect(
                            "Moments",
                            [m.value for m in MomentLiturgique],
                            default=[m.value for m in chant.moments],
                        )
                        if st.form_submit_button("Modifier"):
                            chant.titre = titre
                            chant.paroles = paroles
                            chant.auteur = auteur or None
                            chant.moments = [MomentLiturgique(m) for m in moments]
                            update_chant(chant)
                            st.success("Chant mis à jour.")
                    if st.button("🗑️ Supprimer ce chant", key="del_chant"):
                        delete_chant(chant.id)
                        st.success("Chant supprimé.")
                        st.rerun()
        else:
            st.caption("Aucun chant dans la bibliothèque.")
