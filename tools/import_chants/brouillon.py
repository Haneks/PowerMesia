"""
Brouillon d'un chant à importer : ce que l'écran de vérification modifie (sections, ordre chanté),
et sa conversion en Chant de la bibliothèque. Aucune dépendance à Streamlit.
"""

import re
from dataclasses import dataclass
from typing import Optional

from context.models import Chant, MomentLiturgique, SectionChant, TypeSection
from tools.chant_structure import compute_ordre, paroles_from_structure
from tools.import_chants.modeles import ParsedSong

LIBELLES_TYPE = {
    TypeSection.REFRAIN: "Refrain",
    TypeSection.COUPLET: "Couplet",
    TypeSection.PONT: "Pont",
}
SEPARATEUR_ORDRE = " · "


@dataclass
class SectionEditee:
    """Une section telle qu'elle est modifiée à l'écran : un type et un texte (un vers par ligne)."""
    type: TypeSection
    texte: str

    def lignes(self) -> list[str]:
        return [ligne.strip() for ligne in self.texte.splitlines() if ligne.strip()]


def sections_editees(chant: ParsedSong) -> list[SectionEditee]:
    """Les sections reconnues par l'analyse, prêtes à être éditées."""
    return [SectionEditee(s.type, "\n".join(s.lignes)) for s in chant.structure]


def _identifiants(types: list[TypeSection]) -> list[str]:
    """Identifiants par ordre d'apparition : refrains R, R2… ; couplets 1, 2… ; ponts P, P2…"""
    compteurs = {t: 0 for t in TypeSection}
    ids = []
    for t in types:
        compteurs[t] += 1
        n = compteurs[t]
        if t is TypeSection.COUPLET:
            ids.append(str(n))
        else:
            base = "R" if t is TypeSection.REFRAIN else "P"
            ids.append(base if n == 1 else f"{base}{n}")
    return ids


def sections_depuis_edition(editees: list[SectionEditee]) -> list[SectionChant]:
    """Sections à enregistrer : les sections sans texte sont écartées, les identifiants renumérotés."""
    gardees = [e for e in editees if e.lignes()]
    ids = _identifiants([e.type for e in gardees])
    return [SectionChant(i, e.type, e.lignes()) for i, e in zip(ids, gardees)]


def ordre_initial(chant: ParsedSong, editees: list[SectionEditee], repeter: bool) -> list[str]:
    """
    Ordre chanté proposé pour les sections éditées. Si la structure reconnue n'a pas été touchée
    (mêmes types, aucune section vide) et que le refrain doit être répété, on garde l'ordre calculé
    par l'analyse, qui respecte un ordre explicite du document ; sinon il est recalculé.
    """
    sections = sections_depuis_edition(editees)
    inchangee = (
        len(sections) == len(editees)
        and [e.type for e in editees] == [s.type for s in chant.structure]
    )
    if inchangee and repeter:
        nouveau = {ancien.id: s.id for ancien, s in zip(chant.structure, sections)}
        if chant.ordre and all(i in nouveau for i in chant.ordre):
            return [nouveau[i] for i in chant.ordre]
    return compute_ordre(sections, repeat_refrain=repeter)


def ordre_en_texte(ordre: list[str]) -> str:
    return SEPARATEUR_ORDRE.join(ordre)


def ordre_depuis_texte(texte: str, sections: list[SectionChant]) -> tuple[list[str], Optional[str]]:
    """(ordre, erreur). Les identifiants sont séparés par des espaces, « · », des virgules ou des points-virgules."""
    par_nom = {s.id.casefold(): s.id for s in sections}
    ordre = []
    for jeton in (j for j in re.split(r"[\s·,;]+", texte.strip()) if j):
        if jeton.casefold() not in par_nom:
            return [], f"Section inconnue dans l'ordre : {jeton}"
        ordre.append(par_nom[jeton.casefold()])
    if not ordre:
        return [], "L'ordre chanté est vide"
    return ordre, None


def chant_depuis_brouillon(
    titre: str,
    moments: list[MomentLiturgique],
    recueil: Optional[str],
    editees: list[SectionEditee],
    ordre_texte: str,
) -> tuple[Optional[Chant], Optional[str]]:
    """(chant, erreur) : le Chant à enregistrer, ou la raison pour laquelle le brouillon n'est pas importable."""
    titre = titre.strip()
    if not titre:
        return None, "Le titre est obligatoire"
    sections = sections_depuis_edition(editees)
    if not sections:
        return None, "Le chant n'a aucune parole"
    ordre, erreur = ordre_depuis_texte(ordre_texte, sections)
    if erreur:
        return None, erreur
    chant = Chant(
        titre=titre,
        paroles=paroles_from_structure(sections),
        recueil=(recueil or "").strip() or None,
        moments=list(moments) or [MomentLiturgique.AUTRE],
        structure=sections,
        ordre=ordre,
    )
    return chant, None
