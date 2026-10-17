"""Blocs de la messe (lectures, chants) : identifiants stables, ordre, suppression et contenu de la
liste glissable de la page « Générer une messe ».

Chaque bloc porte un `uid` : l'ordre reçu du navigateur est exprimé en identifiants et non en
positions, donc un bloc ajouté ou supprimé entre-temps ne peut pas être confondu avec un autre.
"""

import html
import re
import uuid

from context.models import TypeLecture

_NOMS_LECTURE = {
    TypeLecture.PREMIERE_LECTURE.value: "1ère lecture",
    TypeLecture.PSAUME.value: "Psaume",
    TypeLecture.DEUXIEME_LECTURE.value: "2e lecture",
    TypeLecture.EVANGILE.value: "Évangile",
}


def assurer_uid(blocs: list[dict]) -> None:
    """Donne un `uid` unique, sur place, aux blocs qui n'en ont pas encore."""
    connus = {b["uid"] for b in blocs if b.get("uid")}
    for bloc in blocs:
        if bloc.get("uid"):
            continue
        uid = uuid.uuid4().hex[:8]
        while uid in connus:
            uid = uuid.uuid4().hex[:8]
        connus.add(uid)
        bloc["uid"] = uid


def _numeroter(blocs: list[dict]) -> list[dict]:
    return [{**bloc, "ordre": i} for i, bloc in enumerate(blocs)]


def appliquer_ordre(blocs: list[dict], uids: list[str]) -> list[dict]:
    """Nouvelle liste de blocs dans l'ordre `uids`.

    Les identifiants inconnus et les doublons sont ignorés ; un bloc absent de `uids` (ajouté après
    l'envoi de l'ordre) n'est jamais perdu : il suit les autres, dans son ordre actuel.
    """
    par_uid = {b["uid"]: b for b in blocs}
    voulus = []
    for uid in uids:
        if uid in par_uid and uid not in voulus:
            voulus.append(uid)
    ordonnes = [par_uid[uid] for uid in voulus]
    ordonnes += [b for b in blocs if b["uid"] not in voulus]
    return _numeroter(ordonnes)


def supprimer_bloc(blocs: list[dict], uid: str) -> list[dict]:
    """Nouvelle liste sans le bloc `uid` (liste inchangée si l'identifiant est inconnu)."""
    return _numeroter([b for b in blocs if b["uid"] != uid])


def libelle_bloc(bloc: dict) -> str:
    """Titre affiché sur la ligne : « 1ère lecture — Is 55, 6-9 », « Chant — Titre »."""
    if bloc.get("type") == "lecture":
        nom = _NOMS_LECTURE.get(bloc.get("lecture_type", TypeLecture.PREMIERE_LECTURE.value), "Lecture")
        return f"{nom} — {bloc.get('reference', 'Sans ref')}"
    return f"{bloc.get('type', 'lecture').title()} — {bloc.get('titre', bloc.get('reference', 'Bloc'))}"


def _texte_brut(contenu: str) -> str:
    """Texte sans balises (puis sans entités : l'ordre compte), espaces regroupés."""
    sans_balises = re.sub(r"<[^>]+>", " ", contenu)
    return re.sub(r"\s+", " ", html.unescape(sans_balises)).strip()


def apercu_bloc(bloc: dict, longueur: int = 140) -> str:
    """Début du texte du bloc, sur une ligne : lecture = son texte, chant = sa première ligne."""
    if bloc.get("type") == "lecture":
        texte = _texte_brut(bloc.get("contenu") or "")
    elif bloc.get("type") == "chant":
        lignes = [ligne.strip() for ligne in (bloc.get("paroles") or "").splitlines()]
        texte = next((ligne for ligne in lignes if ligne), "")
    else:
        texte = ""
    if len(texte) > longueur:
        return texte[: longueur - 1].rstrip() + "…"
    return texte


def elements_liste(blocs: list[dict]) -> list[dict]:
    """Données du composant glissable : un `id`, un `titre` et un `apercu` par bloc."""
    return [{"id": b["uid"], "titre": libelle_bloc(b), "apercu": apercu_bloc(b)} for b in blocs]
