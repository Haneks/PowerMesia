"""
Extraction d'un PDF exporté de Word (texte sélectionnable) : une liste de Line avec gras / italique /
souligné. Les partitions et les PDF-images sont refusés (UnsupportedFile).
"""

import dataclasses
import re
from dataclasses import dataclass
from typing import Optional

import fitz

from tools.import_chants.lignes import Caractere, lignes_depuis_caracteres
from tools.import_chants.modeles import Line, UnsupportedFile

_POLICES_MUSIQUE = re.compile(r"maestro|engraver|musica|bravura|sonata|petrucci", re.IGNORECASE)
_TEXTE_MINIMUM = 40          # en dessous, le PDF est considéré sans texte
_EMPANS_PARTITION = 100      # une partition a de nombreux fragments de texte de 1 à 2 caractères
_TOLERANCE_LIGNE = 3.0       # écart de ligne de base (pt) pour qu'un caractère soit sur la même ligne
_TOLERANCE_COPIE = 1.5       # écart (pt) en dessous duquel deux caractères identiques sont une même copie
_COPIES_FAUX_GRAS = 3        # un caractère imprimé 3 fois ou plus est du « faux gras »
_RATIO_LIGNE_VIDE = 1.75     # écart entre deux lignes, en tailles de police, au-delà duquel une ligne vide les sépare
_PAGES_MAX = 50              # au-delà, ce n'est pas une feuille de chants (refus avant tout traitement de page)
_ESPACE_ENTRE_MOTS = 0.25    # écart (en tailles de police) à partir duquel on insère une espace
# Erreurs levées par PyMuPDF en lisant les pages d'un PDF ouvert. Les erreurs de MuPDF (arbre des pages
# mal formé...) sont des FzErrorBase, qui n'héritent PAS de RuntimeError.
_ERREURS_DE_LECTURE = (ValueError, RuntimeError, fitz.mupdf.FzErrorBase)


@dataclass
class _Car:
    c: str
    x0: float
    x1: float
    base: float
    taille: float
    gras: bool
    italique: bool
    copies: int = 1


def _caracteres(page: fitz.Page) -> list[_Car]:
    cars: list[_Car] = []
    for bloc in page.get_text("rawdict")["blocks"]:
        for ligne in bloc.get("lines", []):
            for span in ligne["spans"]:
                police = span["font"].lower()
                gras = bool(span["flags"] & 16) or "bold" in police or "black" in police
                italique = bool(span["flags"] & 2) or "italic" in police or "oblique" in police
                for ch in span["chars"]:
                    cars.append(_Car(ch["c"], ch["bbox"][0], ch["bbox"][2], ch["origin"][1],
                                     span["size"], gras, italique))
    return cars


def _soulignements(page: fitz.Page) -> list[fitz.Rect]:
    """Traits horizontaux fins : les soulignements (Word les dessine sous le texte)."""
    traits = []
    for dessin in page.get_drawings():
        r = dessin["rect"]
        if r.height < 2.5 and r.width > 3:
            traits.append(r)
    return traits


def _souligne(car: _Car, traits: list[fitz.Rect]) -> bool:
    milieu = (car.x0 + car.x1) / 2
    return any(
        t.x0 - 1 <= milieu <= t.x1 + 1 and car.base - 1 <= t.y0 <= car.base + 0.3 * car.taille + 1
        for t in traits
    )


def _regrouper_en_lignes(cars: list[_Car]) -> list[list[_Car]]:
    """Caractères triés par ligne de base puis par x ; les copies superposées (faux gras) sont fusionnées."""
    lignes: list[list[_Car]] = []
    for car in sorted(cars, key=lambda c: (c.base, c.x0)):
        if lignes and abs(car.base - lignes[-1][0].base) <= _TOLERANCE_LIGNE:
            lignes[-1].append(car)
        else:
            lignes.append([car])

    resultat = []
    for ligne in lignes:
        gardes: list[_Car] = []
        for car in sorted(ligne, key=lambda c: c.x0):
            copie = next((g for g in gardes if g.c == car.c and abs(g.x0 - car.x0) < _TOLERANCE_COPIE), None)
            if copie:
                copie.copies += 1
            else:
                gardes.append(car)
        resultat.append(gardes)
    return resultat


def _lignes_de_la_ligne(ligne: list[_Car], traits: list[fitz.Rect]) -> list[Line]:
    caracteres: list[Caractere] = []
    precedent = None
    for car in ligne:
        if precedent and not car.c.isspace() and not precedent.c.isspace() \
                and car.x0 - precedent.x1 > _ESPACE_ENTRE_MOTS * car.taille:
            caracteres.append((" ", precedent.gras, precedent.italique, _souligne(precedent, traits)))
        gras = car.gras or car.copies >= _COPIES_FAUX_GRAS
        caracteres.append((car.c, gras, car.italique, _souligne(car, traits)))
        precedent = car
    return lignes_depuis_caracteres(caracteres)


def _raison_de_refus(polices: set[str], caracteres: int, empans: int, images: int) -> Optional[str]:
    """Pourquoi ce PDF n'est pas exploitable (None s'il l'est) : sans texte, ou partition."""
    if caracteres < _TEXTE_MINIMUM:
        return "PDF sans texte exploitable (image ou scan)" if images else "PDF vide"
    # Police de notation musicale, ou texte en syllabes isolées sous les notes
    if any(_POLICES_MUSIQUE.search(p) for p in polices) or (empans >= _EMPANS_PARTITION and caracteres / empans < 3):
        return "Partition : les paroles sont mêlées aux notes de musique"
    return None


def _verifier_exploitable(document: fitz.Document) -> None:
    polices, caracteres, empans, images = set(), 0, 0, 0
    for page in document:
        images += len(page.get_images())
        for bloc in page.get_text("dict")["blocks"]:
            for ligne in bloc.get("lines", []):
                for span in ligne["spans"]:
                    if span["text"].strip():
                        polices.add(span["font"])
                        caracteres += len(span["text"])
                        empans += 1
    raison = _raison_de_refus(polices, caracteres, empans, images)
    if raison:
        raise UnsupportedFile(raison)


def _lignes_du_document(document: fitz.Document) -> list[Line]:
    lignes: list[Line] = []
    for page in document:
        traits = _soulignements(page)
        base_precedente = None
        for ligne in _regrouper_en_lignes(_caracteres(page)):
            du_rang = _lignes_de_la_ligne(ligne, traits)
            if not du_rang:
                continue
            base, taille = ligne[0].base, ligne[0].taille
            vide = base_precedente is None or base - base_precedente > _RATIO_LIGNE_VIDE * taille
            lignes.append(dataclasses.replace(du_rang[0], vide_avant=vide))
            lignes += du_rang[1:]
            base_precedente = base
    return lignes


def extract_pdf(data: bytes) -> list[Line]:
    """
    Lit un PDF exporté de Word. Les lignes sont reconstruites caractère par caractère : gras de la
    police ou « faux gras » (texte imprimé 3 fois), italique, soulignement (trait fin sous le texte).
    Une ligne vide est restituée par `vide_avant` quand l'écart avec la ligne précédente dépasse
    1,75 fois la taille de police.
    Un PDF illisible ou protégé par un mot de passe est refusé (UnsupportedFile), jamais un plantage.
    """
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # PyMuPDF lève plusieurs types d'erreurs selon le fichier
        raise UnsupportedFile("PDF illisible") from e
    try:
        # Ouvert sans mot de passe, un PDF protégé n'est pas lisible : l'itération sur ses pages lèverait ValueError.
        if document.needs_pass:
            raise UnsupportedFile("PDF protégé par un mot de passe")
        if document.page_count > _PAGES_MAX:
            raise UnsupportedFile("PDF trop long pour une feuille de chants")
        _verifier_exploitable(document)
        return _lignes_du_document(document)
    except _ERREURS_DE_LECTURE as e:
        raise UnsupportedFile("PDF illisible") from e
    finally:
        document.close()
