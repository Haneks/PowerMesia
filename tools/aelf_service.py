"""
Client API AELF - Récupération des textes liturgiques de la messe.
"""

import re
from pathlib import Path
from typing import Optional

import requests
import yaml

# Résolution du chemin de config
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "args" / "config.yaml"


def _load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _strip_html(text: str) -> str:
    """Supprime les balises HTML du texte AELF."""
    if not text:
        return ""
    # Suppression des balises
    text = re.sub(r"<[^>]+>", " ", text)
    # Normalisation espaces
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_messe(date: str, zone: Optional[str] = None) -> dict:
    """
    Récupère les données de la messe pour une date donnée.

    Args:
        date: Format YYYY-MM-DD
        zone: Zone liturgique (défaut: france)

    Returns:
        dict avec clés: informations, lectures, error (si erreur)

    Raises:
        requests.RequestException en cas d'erreur réseau
    """
    config = _load_config()
    base = config["aelf"]["base_url"]
    endpoint = config["aelf"]["endpoints"]["messes"]
    zone = zone or config["aelf"]["zone_default"]
    timeout = config["aelf"].get("timeout_seconds", 10)

    url = f"{base}{endpoint.format(date=date, zone=zone)}"

    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        return {"informations": None, "lectures": [], "error": str(e)}
    except ValueError as e:
        return {"informations": None, "lectures": [], "error": f"JSON invalide: {e}"}

    if "messes" not in data or not data["messes"]:
        return {
            "informations": data.get("informations"),
            "lectures": [],
            "error": "Aucune messe trouvée pour cette date.",
        }

    messe = data["messes"][0]
    raw_lectures = messe.get("lectures", [])

    # Conversion en format normalisé (LectureLiturgique)
    from context.models import LectureLiturgique, TypeLecture

    lectures = []
    type_map = {
        "lecture_1": TypeLecture.PREMIERE_LECTURE,
        "psaume": TypeLecture.PSAUME,
        "lecture_2": TypeLecture.DEUXIEME_LECTURE,
        "evangile": TypeLecture.EVANGILE,
    }

    for r in raw_lectures:
        t = r.get("type")
        if t not in type_map:
            continue
        lectures.append(
            LectureLiturgique(
                type=type_map[t],
                reference=r.get("ref", ""),
                titre=r.get("titre"),
                intro_lue=r.get("intro_lue"),
                contenu=r.get("contenu", ""),
                refrain_psalmique=r.get("refrain_psalmique"),
                ref_refrain=r.get("ref_refrain"),
                verset_evangile=r.get("verset_evangile"),
                ref_verset=r.get("ref_verset"),
            )
        )

    return {
        "informations": data.get("informations"),
        "lectures": lectures,
        "error": None,
    }


def lecture_to_plain_text(lecture: "LectureLiturgique") -> str:
    """Convertit le contenu HTML d'une lecture en texte brut."""
    if not lecture.contenu:
        return ""
    return _strip_html(lecture.contenu)
