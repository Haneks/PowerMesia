"""
Écran « 📥 Importer des chants » (Streamlit) : dépôt des fichiers, vérification chant par chant,
import dans la bibliothèque. Seul module du paquet qui dépend de Streamlit ; la logique est dans
analyse (importer), doublons (dedupe), brouillon et enregistrement (enregistrer).
"""

import streamlit as st

from context.models import MomentLiturgique, TypeSection
from tools.db_handler import init_db, search_chants
from tools.import_chants.brouillon import (
    LIBELLES_TYPE,
    chant_depuis_brouillon,
    ordre_en_texte,
    ordre_initial,
    SectionEditee,
    sections_editees,
)
from tools.import_chants.dedupe import Doublon, trouver_doublon
from tools.import_chants.enregistrer import Action, Decision, importer_chants
from tools.import_chants.importer import analyser_fichier
from tools.import_chants.modeles import UnsupportedFile

LIBELLES_ACTION = {
    Action.IGNORER: "Ignorer (conserver l'existant)",
    Action.REMPLACER: "Remplacer",
    Action.AJOUTER: "Ajouter quand même",
}
BADGES = {
    Doublon.AUCUN: "🆕 nouveau",
    Doublon.IDENTIQUE: "♻️ déjà présent (identique) : sera ignoré",
    Doublon.DIFFERENT: "⚠️ déjà présent (différent)",
}
ETAT = "import_analyse"       # {"signature": tuple, "fichiers": [{"nom", "chants", "notes", "refus"}]}
RECAP = "import_recap"
COMPTEUR_DEPOT = "import_depot_n"  # change la clé du dépôt pour le vider après un import


def _analyser(fichiers) -> list[dict]:
    resultats = []
    for f in fichiers:
        try:
            analyse = analyser_fichier(f.name, f.getvalue())
            resultats.append({"nom": f.name, "chants": analyse.chants, "notes": analyse.notes, "refus": None})
        except UnsupportedFile as e:
            resultats.append({"nom": f.name, "chants": [], "notes": [], "refus": e.raison})
    return resultats


def _carte(prefixe: str, fichier: str, chant, bibliotheque) -> "Decision | None":
    """Affiche la carte d'un chant et retourne la décision à enregistrer (None si non importable ou décoché)."""
    with st.container(border=True):
        entete = st.container()
        coche = st.checkbox("Importer", value=True, key=f"{prefixe}_ok")
        col_titre, col_recueil = st.columns([2, 1])
        titre = col_titre.text_input("Titre", value=chant.titre, key=f"{prefixe}_titre")
        recueil = col_recueil.text_input("Recueil", value=chant.recueil or "", key=f"{prefixe}_recueil")
        moments = st.multiselect(
            "Moments", [m.value for m in MomentLiturgique], default=[chant.moment.value], key=f"{prefixe}_moments"
        )

        editees = []
        origine = sections_editees(chant)
        for k, section in enumerate(origine):
            col_type, col_texte = st.columns([1, 4])
            type_choisi = TypeSection(col_type.selectbox(
                f"Section {k + 1}", [t.value for t in TypeSection], index=list(TypeSection).index(section.type),
                format_func=lambda v: LIBELLES_TYPE[TypeSection(v)], key=f"{prefixe}_s{k}_type",
            ))
            texte = col_texte.text_area(
                f"Texte de la section {k + 1}", value=section.texte, key=f"{prefixe}_s{k}_texte",
                label_visibility="collapsed",
            )
            editees.append(SectionEditee(type_choisi, texte))
        st.caption("Une section sans texte n'est pas importée.")

        repeter = st.checkbox("Répéter le refrain", value=True, key=f"{prefixe}_repeter")
        # La clé de l'ordre dépend des types, des sections vides et de « Répéter » : si la structure change,
        # l'ordre est recalculé (une modification manuelle de l'ordre est alors perdue)
        signature = "".join(e.type.value[0] if e.lignes() else "_" for e in editees) + ("r" if repeter else "-")
        ordre_texte = st.text_input(
            "Ordre chanté (R = refrain, 1 2 … = couplets, P = pont)",
            value=ordre_en_texte(ordre_initial(chant, editees, repeter)),
            key=f"{prefixe}_ordre_{signature}",
        )

        for avertissement in chant.avertissements:
            st.warning(avertissement)
        for note in chant.notes:
            st.caption(f"ℹ️ {note}")

        brouillon, erreur = chant_depuis_brouillon(
            titre, [MomentLiturgique(m) for m in moments], recueil, editees, ordre_texte
        )
        statut, action = Doublon.AUCUN, Action.AJOUTER
        if brouillon is not None:
            resultat = trouver_doublon(
                brouillon.titre, brouillon.recueil, brouillon.paroles, bool(brouillon.structure), bibliotheque
            )
            statut = resultat.statut
            if statut is Doublon.DIFFERENT:
                action = _choisir_action(prefixe, resultat.existant, brouillon)
        with entete:
            st.markdown(f"**{BADGES[statut] if brouillon else '❌ non importable'}** — {fichier}")
            if erreur:
                st.error(erreur)

        if brouillon is None or not coche or statut is Doublon.IDENTIQUE:
            return None
        return Decision(brouillon, action, statut)


def _choisir_action(prefixe: str, existant, nouveau) -> Action:
    action = Action(st.radio(
        "Ce chant existe déjà avec un texte différent", [a.value for a in Action],
        format_func=lambda v: LIBELLES_ACTION[Action(v)], index=0, horizontal=True, key=f"{prefixe}_action",
    ))
    ancien, courant = st.columns(2)
    ancien.caption("Texte actuel de la bibliothèque")
    ancien.text(existant.paroles)
    courant.caption("Texte importé")
    courant.text(nouveau.paroles)
    return action


def afficher_import() -> None:
    init_db()
    st.subheader("Importer des chants depuis Word ou PDF")
    st.caption(
        "Déposez une feuille de messe ou un chant (.docx, ou .pdf exporté depuis Word, 10 Mo au plus). "
        "Les chants sont reconnus, puis vérifiés avant d'entrer dans la bibliothèque."
    )

    n_depot = st.session_state.get(COMPTEUR_DEPOT, 0)
    fichiers = st.file_uploader(
        "Fichiers à importer", type=["docx", "pdf"], accept_multiple_files=True, key=f"import_depot_{n_depot}"
    )
    signature = tuple((f.name, f.size) for f in fichiers)
    etat = st.session_state.get(ETAT)
    if etat is None or etat["signature"] != signature:
        if etat is not None:  # de nouveaux fichiers : le récapitulatif de l'import précédent n'a plus lieu d'être
            st.session_state.pop(RECAP, None)
        etat = {"signature": signature, "fichiers": _analyser(fichiers)}
        st.session_state[ETAT] = etat

    recap = st.session_state.get(RECAP)
    if recap is not None:
        _afficher_recapitulatif(recap)

    refuses = [f for f in etat["fichiers"] if f["refus"]]
    for f in refuses:
        st.warning(f"**{f['nom']}** : {f['refus']}")

    bibliotheque = search_chants()
    decisions = []
    for i, f in enumerate(f for f in etat["fichiers"] if not f["refus"]):
        st.markdown(f"### 📄 {f['nom']}")
        for note in f["notes"]:
            st.caption(f"ℹ️ {note}")
        if not f["chants"]:
            st.info("Aucun chant reconnu dans ce fichier.")
        for j, chant in enumerate(f["chants"]):
            # Le jeu de fichiers entre dans les clés des champs : de nouveaux fichiers ne reprennent pas d'anciennes saisies
            decision = _carte(f"imp_{n_depot}_{abs(hash(signature)) % 10**8}_{i}_{j}", f["nom"], chant, bibliotheque)
            if decision is not None:
                decisions.append(decision)

    if any(f["chants"] for f in etat["fichiers"]):
        n = len(decisions)
        if st.button(f"Importer {n} chant{'s' if n > 1 else ''}", type="primary", key="import_go", disabled=n == 0):
            st.session_state[RECAP] = importer_chants(decisions)
            st.session_state.pop(ETAT, None)
            st.session_state[COMPTEUR_DEPOT] = n_depot + 1
            st.rerun()


def _afficher_recapitulatif(recap) -> None:
    st.success(
        f"Import terminé : {len(recap.ajoutes)} ajouté(s), {len(recap.remplaces)} remplacé(s), "
        f"{len(recap.ignores)} ignoré(s), {len(recap.erreurs)} erreur(s)."
    )
    for titre in recap.ajoutes:
        st.caption(f"➕ ajouté : {titre}")
    for titre in recap.remplaces:
        st.caption(f"🔁 remplacé : {titre}")
    for ligne in recap.ignores:
        st.caption(f"⏭️ ignoré : {ligne}")
    for ligne in recap.erreurs:
        st.error(ligne)
