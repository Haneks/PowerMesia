"""Enregistrement des chants vérifiés dans la bibliothèque, avec la décision prise pour chaque doublon."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from context.models import Chant
from tools.db_handler import create_chant, init_db, search_chants, update_chant
from tools.import_chants.dedupe import Doublon, trouver_doublon


class Action(Enum):
    """Que faire d'un chant dont la clé existe déjà avec un texte différent."""
    IGNORER = "ignorer"
    REMPLACER = "remplacer"
    AJOUTER = "ajouter"


@dataclass
class Decision:
    """Un chant à importer, avec l'état de doublon vu à l'écran de vérification."""
    chant: Chant
    action: Action = Action.IGNORER
    statut_vu: Doublon = Doublon.AUCUN


@dataclass
class Recapitulatif:
    ajoutes: list[str] = field(default_factory=list)
    remplaces: list[str] = field(default_factory=list)
    ignores: list[str] = field(default_factory=list)  # « titre — raison »
    erreurs: list[str] = field(default_factory=list)


def importer_chants(decisions: list[Decision], db_path: Optional[Path] = None) -> Recapitulatif:
    """
    Enregistre les chants un par un. Les doublons sont recalculés contre la base au moment de
    l'enregistrement, car les chants précédents du même lot viennent d'y entrer : un chant vu
    comme « nouveau » à l'écran qui est devenu un doublon est ignoré, jamais ajouté deux fois.
    Une erreur sur un chant n'empêche pas l'enregistrement des autres.
    """
    init_db(db_path)
    recap = Recapitulatif()
    for decision in decisions:
        chant = decision.chant
        try:
            resultat = trouver_doublon(
                chant.titre, chant.recueil, chant.paroles, bool(chant.structure), search_chants(db_path=db_path)
            )
            if resultat.statut is Doublon.AUCUN:
                create_chant(chant, db_path)
                recap.ajoutes.append(chant.titre)
            elif resultat.statut is Doublon.IDENTIQUE:
                recap.ignores.append(f"{chant.titre} — déjà présent (identique)")
            elif decision.statut_vu is Doublon.AUCUN:
                recap.ignores.append(f"{chant.titre} — doublon dans cet import")
            elif decision.action is Action.REMPLACER:
                _remplacer(resultat.existant, chant, db_path)
                recap.remplaces.append(chant.titre)
            elif decision.action is Action.AJOUTER:
                create_chant(chant, db_path)
                recap.ajoutes.append(chant.titre)
            else:
                recap.ignores.append(f"{chant.titre} — déjà présent (différent), conservé tel quel")
        except Exception as e:  # une erreur de base sur un chant ne doit pas arrêter les suivants
            recap.erreurs.append(f"{chant.titre} — {e}")
    return recap


def _remplacer(existant: Chant, nouveau: Chant, db_path: Optional[Path]) -> None:
    """
    Remplace texte, structure, ordre et recueil ; garde l'identité et les champs saisis à la main.
    Les moments sont réunis (ceux de la bibliothèque d'abord, puis les nouveaux) : un chant déjà classé
    ne perd pas ses moments parce que le document importé n'en cite qu'un.
    """
    existant.titre = nouveau.titre
    existant.paroles = nouveau.paroles
    existant.recueil = nouveau.recueil
    existant.structure = nouveau.structure
    existant.ordre = nouveau.ordre
    existant.moments = existant.moments + [m for m in nouveau.moments if m not in existant.moments]
    update_chant(existant, db_path)
