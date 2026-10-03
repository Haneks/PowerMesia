"""
Structure d'un chant (refrain, couplets, pont) : sérialisation JSON, ordre chanté
et lignes à projeter.
"""

import json
import logging
from typing import Optional

from context.models import SectionChant, TypeSection

logger = logging.getLogger(__name__)

# (texte, gras). Une ligne vide ("", False) sépare deux sections.
BlocLine = tuple[str, bool]


def sections_to_dicts(sections: list[SectionChant]) -> list[dict]:
    return [s.to_dict() for s in sections]


def sections_from_dicts(dicts: list[dict]) -> list[SectionChant]:
    return [SectionChant.from_dict(d) for d in dicts]


def structure_to_json(sections: list[SectionChant]) -> Optional[str]:
    if not sections:
        return None
    return json.dumps({"sections": sections_to_dicts(sections)}, ensure_ascii=False)


def structure_from_json(raw: Optional[str]) -> list[SectionChant]:
    if not raw:
        return []
    return sections_from_dicts(json.loads(raw)["sections"])


def ordre_to_json(ordre: list[str]) -> Optional[str]:
    return json.dumps(ordre, ensure_ascii=False) if ordre else None


def ordre_from_json(raw: Optional[str]) -> list[str]:
    return list(json.loads(raw)) if raw else []


def compute_ordre(sections: list[SectionChant], repeat_refrain: bool = True) -> list[str]:
    """
    Ordre chanté d'un chant.
    - Un seul refrain : il est inséré après chaque couplet ou pont ; s'il ouvre le chant,
      il est aussi joué en premier (R 1 R 2 R P R ; ou 1 R 2 R si le refrain suit le couplet 1).
    - Aucun refrain, plusieurs sections refrain (ordre explicite du document) ou
      repeat_refrain=False : ordre du document.
    """
    ids = [s.id for s in sections]
    refrains = [s for s in sections if s.type is TypeSection.REFRAIN]
    if not repeat_refrain or len(refrains) != 1:
        return ids
    refrain = refrains[0]
    ordre = [refrain.id] if sections[0] is refrain else []
    for section in sections:
        if section is not refrain:
            ordre += [section.id, refrain.id]
    return ordre


def paroles_from_structure(sections: list[SectionChant]) -> str:
    """Texte à plat : sections dans l'ordre du document, refrain une seule fois."""
    return "\n\n".join("\n".join(s.lignes) for s in sections)


def expand_lines(sections: list[SectionChant], ordre: list[str]) -> list[BlocLine]:
    """Déroule l'ordre chanté en lignes (texte, gras), refrain en gras, ligne vide entre sections."""
    by_id = {s.id: s for s in sections}
    lines: list[BlocLine] = []
    for section_id in ordre:
        section = by_id.get(section_id)
        if section is None:
            logger.warning("Section inconnue dans l'ordre du chant : %r", section_id)
            continue
        if lines:
            lines.append(("", False))
        bold = section.type is TypeSection.REFRAIN
        lines += [(ligne, bold) for ligne in section.lignes]
    return lines
