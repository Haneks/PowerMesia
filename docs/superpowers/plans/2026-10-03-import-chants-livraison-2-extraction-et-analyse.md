# Import de chants — Livraison 2 : extraction et analyse — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** Lire un fichier Word ou PDF et en tirer les chants : une feuille de messe est découpée en chants (moment, recueil, titre proposé), chaque chant en sections (refrain, couplets, pont) avec son ordre chanté ; les partitions et les PDF-images sont refusés avec une raison lisible. Aucune interface dans cette livraison (écran d'import, doublons et écriture en base : livraison 3).

**Architecture :** Deux extracteurs (`extract_docx` avec python-docx, `extract_pdf` avec PyMuPDF) produisent la même liste de `Line` (texte, gras, italique, souligné, ligne vide avant) en s'appuyant sur une logique commune (`lignes.py`). `parse.py`, pur et indépendant du format, découpe cette liste en chants puis en sections avec des règles. `importer.py` est le point d'entrée (nom + contenu du fichier → résultat). Les règles ont été validées sur le corpus réel de la paroisse (50 fichiers) avant la rédaction de ce plan.

**Tech Stack :** Python 3.11 (image Docker) / 3.13 (poste), `python-docx>=1.1.0`, `PyMuPDF>=1.24.0`, pytest. **Aucun LLM, aucune reconnaissance de caractères.**

**Spec :** `docs/superpowers/specs/2026-10-03-import-chants-design.md` (§4 architecture, §6 règles d'analyse, §9 tests, §10 étape 2). Les précisions apportées par ce plan à §4 et §6 sont reportées dans la spec à la Task 6.

## Global Constraints

- Entrée : seuls `.docx` et `.pdf` (extension insensible à la casse), 10 Mo au plus par fichier, lecture en mémoire, rien n'est écrit sur le disque.
- Une ligne est grasse / italique / soulignée si au moins la moitié de ses caractères (espaces exclus) le sont.
- Un paragraphe est éclaté en lignes aux retours à la ligne et aux suites de 2 espaces ou plus (fins de vers) ; un titre souligné n'est coupé qu'aux retours à la ligne, ainsi qu'un texte court (6 mots ou moins).
- Refrain : bloc entièrement en gras (ou, à défaut, en italique) alors que le chant a d'autres blocs ; ou bloc répété à l'identique ; si tout le chant est en gras ou en italique, ou si rien n'est marqué : aucun refrain et un avertissement.
- Ordre chanté : refrain répété dans le document → ordre du document conservé ; sinon `compute_ordre` (`R 1 R 2 R P R`, `1 R 2 R`).
- **L'`ordre` d'un chant ne référence que des ids de ses sections** (postcondition testée, y compris sur le corpus).
- PDF : partition refusée si une police de notation (`maestro`, `engraver`, `musica`, `bravura`, `sonata`, `petrucci`) est présente ou si le texte est en fragments de 1 à 2 caractères (≥ 100 fragments, moins de 3 caractères en moyenne) ; PDF sans texte (< 40 caractères) refusé. « Faux gras » : caractères identiques à moins de 1,5 pt les uns des autres fusionnés, multiplicité ≥ 3 → gras. Une ligne vide est restituée quand l'écart entre deux lignes dépasse 1,75 fois la taille de police.
- Les paroles ne sont jamais corrigées : fautes de frappe conservées ; seuls les espaces (`clean_spaces`) et les reprises `2x` / `bis` sont retirés (et signalés).
- Moments : `entree`, `pardon`, `gloire`, `psaume`, `alleluia`, `pu`, `offertoire`, `sanctus`, `anamnese`, `agneau`, `communion`, `envoi`, `autre` (énumération existante `MomentLiturgique`).
- **Aucun fichier du corpus ni aucune parole réelle dans le dépôt** (public) : les tests utilisent des textes inventés ; le test « corpus » ne s'exécute que sur le poste qui possède les fichiers et se saute ailleurs.
- Python 3.11 compatible ; code, docstrings et commentaires en français, comme l'existant ; aucune dépendance autre que `python-docx` et `PyMuPDF` (`PyMuPDF` est sous licence AGPL : sans objet pour un usage paroissial, à revoir si l'application est redistribuée).
- Les messages de commit finissent par la ligne `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Commandes lancées depuis la racine du dépôt : `python -m pytest …`. Pour écrire du code contenant des antislashs, utiliser les outils d'écriture de fichiers, pas un heredoc shell.

## Précisions par rapport à la spec (à reporter dans la spec : Task 6)

- Modules : en plus de `extract_docx.py`, `extract_pdf.py` et `parse.py`, le paquet contient `modeles.py` (types `Line`, `ParsedSong`, `ParseResult`, `UnsupportedFile`), `lignes.py` (caractères → lignes, commun aux deux extracteurs) et `importer.py` (point d'entrée `analyser_fichier`). `dedupe.py` est livré en livraison 3.
- Étiquettes de section reconnues : `1.`, `1)`, `Couplet 2`, `Pont :`, `Refrain`, `R/` ; une étiquette soulignée n'est jamais un titre de chant.
- Vocabulaire des en-têtes élargi : `Gloria`, `Agnus (Dei)`, `Kyrie`, `Evangile` / `Acclamation` (→ alléluia), `Prière(s) universelle(s)`, et le préfixe `Chant de …` (« Chant de Pardon » → pardon).
- Le soulignement PDF est évalué par caractère (le milieu du caractère est sur un trait fin situé sous sa ligne de base), puis par ligne avec le seuil de la moitié.
- Un titre tiré d'un vers est coupé à la première ponctuation et ne finit jamais par un mot-outil (« Chaque jour, chaque moment, en ce » → « Chaque jour »).

## Reportés à la livraison 3 (rappel de la revue finale de la livraison 1, hors périmètre ici)

Test AppTest du câblage « Ajouter ce chant » → export avant toute modification d'`app.py` ; repli du générateur sur les paroles quand l'ordre ne donne aucune ligne et validation des ids de `ordre` à l'écran de vérification ; renommage de la clé `ordre` du bloc générateur en `ordre_chant` ; avertissement avant qu'une édition de paroles ne supprime la structure. Deux points de cette liste sont déjà satisfaits côté analyse : les lignes sont normalisées (`clean_spaces`, fins de ligne uniformes) et l'`ordre` produit ne référence que des sections existantes.

**Branche de travail :** après fusion de la branche qui contient ce plan dans `main`, créer `feat/import-extraction` depuis `main`.

## Carte des fichiers

| Fichier | Action | Responsabilité |
|---|---|---|
| `requirements.txt` | modifier | ajoute `python-docx`, `PyMuPDF` |
| `tools/import_chants/__init__.py` | créer | paquet (vide) |
| `tools/import_chants/modeles.py` | créer | `Line`, `ParsedSong`, `ParseResult`, `UnsupportedFile` |
| `tools/import_chants/lignes.py` | créer | caractères mis en forme → lignes (commun Word / PDF) |
| `tools/import_chants/extract_docx.py` | créer | `extract_docx(data) -> list[Line]` |
| `tools/import_chants/extract_pdf.py` | créer | `extract_pdf(data) -> list[Line]`, refus des partitions et images |
| `tools/import_chants/parse.py` | créer | `parse_lines(lignes, nom_fichier) -> ParseResult` |
| `tools/import_chants/importer.py` | créer | `analyser_fichier(nom, data) -> ParseResult` |
| `tests/helpers_import.py` | créer (3 étapes) | `L`, `docx_bytes`, `pdf_bytes`, `pdf_image_seule`, `pdf_en_syllabes` |
| `tests/test_import_*.py` | créer | tests par module + test « corpus » local |
| `hardprompts/import_rules.md`, `README.md`, `ARBORESCENCE.md`, spec | créer / modifier | documentation |

---

### Task 1: Types, dépendances et éclatement des lignes

**Files:**
- Modify: `requirements.txt`
- Create: `tools/import_chants/__init__.py` (vide), `tools/import_chants/modeles.py`, `tools/import_chants/lignes.py`, `tests/helpers_import.py` (version 1)
- Test: `tests/test_import_lignes.py`

**Interfaces:**
- Consumes: `MomentLiturgique`, `SectionChant` (`context/models.py`)
- Produces:
  - `UnsupportedFile(Exception)` avec `.raison: str`
  - `Line(texte: str, gras=False, italique=False, souligne=False, vide_avant=False)` (dataclass figée)
  - `ParsedSong(titre, moment, recueil=None, structure=[], ordre=[], notes=[], avertissements=[])`, `ParseResult(chants=[], notes=[])`
  - `Caractere = tuple[str, bool, bool, bool]` ; `lignes_depuis_caracteres(caracteres: list[Caractere]) -> list[Line]`
  - Test : `L(texte, gras=False, italique=False, souligne=False, vide=False) -> Line`

- [ ] **Step 1: Dépendances**

Ajouter à la fin de `requirements.txt` :

```
python-docx>=1.1.0
PyMuPDF>=1.24.0
```

Run: `pip install -r requirements.txt`
Expected: installation sans erreur (les deux paquets sont déjà présents sur le poste de développement).

- [ ] **Step 2: Écrire les tests qui échouent**

Créer `tools/import_chants/__init__.py` (fichier vide), puis `tests/helpers_import.py` (version 1) :

```python
"""Fabrique de fichiers Word et PDF pour les tests de l'import (textes inventés, rien du corpus)."""

from tools.import_chants.modeles import Line


def L(texte: str, gras=False, italique=False, souligne=False, vide=False) -> Line:
    """Une Line abrégée, pour tester l'analyse sans passer par un fichier."""
    return Line(texte, gras, italique, souligne, vide)
```

Créer `tests/test_import_lignes.py` :

```python
"""Tests de tools/import_chants/lignes.py : des caractères mis en forme → des lignes de chant."""

from tools.import_chants.lignes import lignes_depuis_caracteres
from tools.import_chants.modeles import Line


def car(texte: str, gras=False, italique=False, souligne=False) -> list[tuple]:
    return [(c, gras, italique, souligne) for c in texte]


def textes(lignes: list[Line]) -> list[str]:
    return [l.texte for l in lignes]


def test_retour_a_la_ligne_separe_deux_vers():
    assert textes(lignes_depuis_caracteres(car("le vent se lève\nla mer s'agite"))) == [
        "le vent se lève", "la mer s'agite"]


def test_double_espace_separe_deux_vers_quand_le_texte_est_long():
    texte = "le vent du soir se lève sur la ville  les cloches annoncent le jour"
    assert textes(lignes_depuis_caracteres(car(texte))) == [
        "le vent du soir se lève sur la ville", "les cloches annoncent le jour"]


def test_double_espace_ne_coupe_pas_un_texte_court():
    assert textes(lignes_depuis_caracteres(car("Agneau  Recueil Aurore 2"))) == ["Agneau  Recueil Aurore 2"]


def test_titre_souligne_garde_son_separateur_de_recueil():
    lignes = lignes_depuis_caracteres(car("Pardon   Recueil Aurore 2", gras=True, souligne=True))
    assert len(lignes) == 1 and lignes[0].texte == "Pardon   Recueil Aurore 2"
    assert lignes[0].gras and lignes[0].souligne


def test_espaces_non_soulignees_entre_deux_mots_soulignes_ne_coupent_pas_le_titre():
    caracteres = (car("Gloire", gras=True, souligne=True) + car("   ", gras=True)
                  + car("Recueil Aurore 2", gras=True, souligne=True))
    lignes = lignes_depuis_caracteres(caracteres)
    assert len(lignes) == 1 and lignes[0].souligne


def test_titre_souligne_puis_paroles_dans_le_meme_paragraphe_donnent_deux_lignes():
    caracteres = car("Psaume", gras=True, souligne=True) + car(" ") + car("Le fleuve chante la paix.", gras=True)
    lignes = lignes_depuis_caracteres(caracteres)
    assert textes(lignes) == ["Psaume", "Le fleuve chante la paix."]
    assert lignes[0].souligne and not lignes[1].souligne and lignes[1].gras


def test_une_ligne_est_grasse_si_la_moitie_de_ses_caracteres_le_sont():
    assert lignes_depuis_caracteres(car("abcd", gras=True)[:2] + car("ef"))[0].gras is True       # 2 sur 4
    assert lignes_depuis_caracteres(car("a", gras=True) + car("bcd"))[0].gras is False             # 1 sur 4


def test_italique_et_les_espaces_ne_comptent_pas_dans_la_proportion():
    ligne = lignes_depuis_caracteres(car("ab", italique=True) + car("   ") + car("cd", italique=True))[0]
    assert ligne.italique is True


def test_texte_vide_ou_blanc_ne_donne_aucune_ligne():
    assert lignes_depuis_caracteres([]) == []
    assert lignes_depuis_caracteres(car("  \n  ")) == []
```

- [ ] **Step 3: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_import_lignes.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.import_chants.modeles'` (ou `.lignes`).

- [ ] **Step 4: Implémenter**

Créer `tools/import_chants/modeles.py` :

```python
"""Types communs à l'import de chants : extraction (Word / PDF) puis analyse."""

from dataclasses import dataclass, field
from typing import Optional

from context.models import MomentLiturgique, SectionChant


class UnsupportedFile(Exception):
    """Fichier que l'import ne sait pas lire (partition, image, fichier illisible)."""

    def __init__(self, raison: str):
        super().__init__(raison)
        self.raison = raison


@dataclass(frozen=True)
class Line:
    """Une ligne de texte avec sa mise en forme, telle que sortie par l'extraction."""
    texte: str
    gras: bool = False
    italique: bool = False
    souligne: bool = False
    vide_avant: bool = False  # une ligne vide précède cette ligne


@dataclass
class ParsedSong:
    """Un chant reconnu dans un fichier, prêt à être vérifié puis importé."""
    titre: str
    moment: MomentLiturgique
    recueil: Optional[str] = None
    structure: list[SectionChant] = field(default_factory=list)
    ordre: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


@dataclass
class ParseResult:
    """Résultat de l'analyse d'un fichier."""
    chants: list[ParsedSong] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # métadonnées et éléments ignorés (date, renvois…)
```

Créer `tools/import_chants/lignes.py` :

```python
"""
Éclatement d'un paragraphe (Word) ou d'une ligne visuelle (PDF) en lignes de chant, à partir de
ses caractères et de leur mise en forme. Commun aux deux extracteurs.
"""

import re

from tools.import_chants.modeles import Line

# (caractère, gras, italique, souligné)
Caractere = tuple[str, bool, bool, bool]

# Fins de vers dans un paragraphe : retour à la ligne, ou 2 espaces (insécables compris) et plus.
_FIN_DE_VERS = re.compile(r"\n|[^\S\n]{2,}")
_FIN_DE_LIGNE = re.compile(r"\n")
SEUIL = 0.5  # une ligne est grasse / italique / soulignée si au moins la moitié de ses caractères le sont
MOTS_MAX_SANS_COUPURE = 6  # en dessous, des doubles espaces ne séparent pas deux vers


def _espaces_heritent_du_soulignement(caracteres: list[Caractere]) -> list[Caractere]:
    """
    Les espaces entre deux mots soulignés ne le sont souvent pas. Une espace prend le soulignement
    du caractère visible qui la précède (ou, en tête, qui la suit) : sinon
    « Gloire a Dieu   Lyon centre 4 » serait coupé en deux titres.
    """
    resultat: list[Caractere] = []
    precedent = next((c[3] for c in caracteres if not c[0].isspace()), False)
    for caractere in caracteres:
        if caractere[0].isspace() and caractere[0] != "\n":
            caractere = (caractere[0], caractere[1], caractere[2], precedent)
        else:
            precedent = caractere[3]
        resultat.append(caractere)
    return resultat


def _decouper(segment: list[Caractere], motif: re.Pattern) -> list[Line]:
    texte = "".join(c[0] for c in segment)
    bornes, debut = [], 0
    for m in motif.finditer(texte):
        bornes.append((debut, m.start()))
        debut = m.end()
    bornes.append((debut, len(texte)))

    lignes = []
    for a, b in bornes:
        morceau = segment[a:b]
        brut = "".join(c[0] for c in morceau).strip()
        visibles = [c for c in morceau if not c[0].isspace()]
        if not brut or not visibles:
            continue

        def part(i: int) -> bool:
            return sum(1 for c in visibles if c[i]) / len(visibles) >= SEUIL

        lignes.append(Line(texte=brut, gras=part(1), italique=part(2), souligne=part(3)))
    return lignes


def lignes_depuis_caracteres(caracteres: list[Caractere]) -> list[Line]:
    """
    Éclate des caractères en lignes : à chaque changement de soulignement (un titre souligné suivi
    de paroles donne deux lignes), puis aux retours à la ligne et aux doubles espaces. Un segment
    souligné (un titre) n'est coupé qu'aux retours à la ligne, ainsi qu'un texte court.
    """
    caracteres = _espaces_heritent_du_soulignement(caracteres)
    lignes: list[Line] = []
    debut = 0
    while debut < len(caracteres):
        fin = debut
        while fin < len(caracteres) and caracteres[fin][3] == caracteres[debut][3]:
            fin += 1
        segment = caracteres[debut:fin]
        court = len("".join(c[0] for c in segment).split()) <= MOTS_MAX_SANS_COUPURE
        motif = _FIN_DE_LIGNE if segment[0][3] or court else _FIN_DE_VERS
        lignes += _decouper(segment, motif)
        debut = fin
    return lignes
```

- [ ] **Step 5: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_import_lignes.py -q`
Expected: `9 passed`

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tools/import_chants tests/helpers_import.py tests/test_import_lignes.py
git commit -m "feat: types de l'import de chants et éclatement des lignes mises en forme" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Extraction d'un fichier Word

**Files:**
- Create: `tools/import_chants/extract_docx.py`
- Modify: `tests/helpers_import.py` (version 2 : ajoute `docx_bytes`)
- Test: `tests/test_import_extract_docx.py`

**Interfaces:**
- Consumes: `Line`, `UnsupportedFile` (Task 1), `lignes_depuis_caracteres`, `Caractere` (Task 1)
- Produces: `extract_docx(data: bytes) -> list[Line]` (lève `UnsupportedFile` si le fichier n'est pas un .docx) ; test : `docx_bytes(paragraphes: list, style_gras: bool = False) -> bytes` — chaque paragraphe est `""` (vide), une chaîne, ou une liste de segments `(texte, drapeaux)` avec `g` gras, `i` italique, `s` souligné

- [ ] **Step 1: Écrire les tests qui échouent**

Remplacer `tests/helpers_import.py` par (version 2) :

```python
"""Fabrique de fichiers Word et PDF pour les tests de l'import (textes inventés, rien du corpus)."""

import io

from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.import_chants.modeles import Line


def L(texte: str, gras=False, italique=False, souligne=False, vide=False) -> Line:
    """Une Line abrégée, pour tester l'analyse sans passer par un fichier."""
    return Line(texte, gras, italique, souligne, vide)


def docx_bytes(paragraphes: list, style_gras: bool = False) -> bytes:
    """
    Un .docx. Chaque paragraphe est "" (paragraphe vide), une chaîne (texte simple) ou une liste de
    segments (texte, drapeaux) où les drapeaux sont des lettres : g = gras, i = italique, s = souligné.
    style_gras : applique à tous les paragraphes un style de paragraphe en gras (sans gras sur les runs).
    """
    document = Document()
    style = None
    if style_gras:
        style = document.styles.add_style("TitreGras", WD_STYLE_TYPE.PARAGRAPH)
        style.font.bold = True
    for paragraphe in paragraphes:
        segments = [(paragraphe, "")] if isinstance(paragraphe, str) else paragraphe
        p = document.add_paragraph(style=style)
        for texte, drapeaux in segments:
            run = p.add_run(texte)
            if "g" in drapeaux:
                run.bold = True
            if "i" in drapeaux:
                run.italic = True
            if "s" in drapeaux:
                run.underline = True
    sortie = io.BytesIO()
    document.save(sortie)
    return sortie.getvalue()
```

Créer `tests/test_import_extract_docx.py` :

```python
"""Tests de tools/import_chants/extract_docx.py (documents Word fabriqués par les tests)."""

import pytest

from tests.helpers_import import docx_bytes
from tools.import_chants.extract_docx import extract_docx
from tools.import_chants.modeles import UnsupportedFile


def test_un_titre_souligne_suivi_de_paroles_dans_le_meme_paragraphe_donne_deux_lignes():
    lignes = extract_docx(docx_bytes([[("Psaume", "gs"), (" Le fleuve chante la paix.", "g")]]))
    assert [l.texte for l in lignes] == ["Psaume", "Le fleuve chante la paix."]
    assert lignes[0].gras and lignes[0].souligne
    assert lignes[1].gras and not lignes[1].souligne


def test_paragraphes_vides_deviennent_vide_avant_de_la_ligne_suivante():
    lignes = extract_docx(docx_bytes(["premier vers", "second vers", "", "", "troisième vers"]))
    assert [(l.texte, l.vide_avant) for l in lignes] == [
        ("premier vers", False), ("second vers", False), ("troisième vers", True)]


def test_retours_a_la_ligne_et_doubles_espaces_separent_les_vers():
    paragraphe = "le vent du soir se lève sur la ville  les cloches annoncent le jour\nla nuit vient"
    assert [l.texte for l in extract_docx(docx_bytes([paragraphe]))] == [
        "le vent du soir se lève sur la ville", "les cloches annoncent le jour", "la nuit vient"]


def test_titre_souligne_garde_ses_espaces_et_n_est_pas_coupe():
    lignes = extract_docx(docx_bytes([[("Gloire a Dieu", "gs"), ("   ", "g"), ("Recueil Aurore 2", "gs")]]))
    assert [l.texte for l in lignes] == ["Gloire a Dieu   Recueil Aurore 2"]


def test_gras_et_italique_par_ligne():
    lignes = extract_docx(docx_bytes([[("refrain en gras", "g")], [("vers en italique", "i")], "vers simple"]))
    assert [(l.gras, l.italique) for l in lignes] == [(True, False), (False, True), (False, False)]


def test_le_gras_peut_venir_du_style_du_paragraphe():
    lignes = extract_docx(docx_bytes(["texte sans gras sur le run"], style_gras=True))
    assert lignes[0].gras is True


def test_fichier_illisible():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_docx(b"ceci n'est pas un fichier Word")
    assert "Word" in erreur.value.raison
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_import_extract_docx.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.import_chants.extract_docx'`.

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/extract_docx.py` :

```python
"""Extraction d'un fichier Word (.docx) : une liste de Line avec gras / italique / souligné."""

import dataclasses
import io
import zipfile

from docx import Document
from docx.enum.text import WD_UNDERLINE
from docx.text.paragraph import Paragraph
from docx.text.run import Run

from tools.import_chants.lignes import Caractere, lignes_depuis_caracteres
from tools.import_chants.modeles import Line, UnsupportedFile


def _valeur(police, attribut: str):
    valeur = getattr(police, attribut)
    if valeur is None:
        return None
    if attribut == "underline":
        return valeur not in (False, WD_UNDERLINE.NONE)
    return bool(valeur)


def _effectif(run: Run, paragraphe: Paragraph, attribut: str) -> bool:
    """Valeur effective d'un attribut de police : le run, puis son style, puis les styles du paragraphe."""
    valeur = _valeur(run.font, attribut)
    if valeur is not None:
        return valeur
    for depart in (run.style, paragraphe.style):
        style = depart
        while style is not None:
            valeur = _valeur(style.font, attribut)
            if valeur is not None:
                return valeur
            style = style.base_style
    return False


def _runs(paragraphe: Paragraph) -> list[Run]:
    runs: list[Run] = []
    for element in paragraphe.iter_inner_content():
        runs += [element] if isinstance(element, Run) else list(element.runs)
    return runs


def _lignes_du_paragraphe(paragraphe: Paragraph) -> list[Line]:
    caracteres: list[Caractere] = []
    for run in _runs(paragraphe):
        gras, italique, souligne = (_effectif(run, paragraphe, a) for a in ("bold", "italic", "underline"))
        caracteres += [(c, gras, italique, souligne) for c in run.text]
    return lignes_depuis_caracteres(caracteres)


def extract_docx(data: bytes) -> list[Line]:
    """
    Lit un .docx. Un paragraphe est éclaté en plusieurs lignes (retours à la ligne, doubles espaces,
    changement de soulignement) ; les paragraphes vides deviennent `vide_avant` de la ligne suivante.
    Les tableaux et zones de texte ne sont pas lus.
    """
    try:
        document = Document(io.BytesIO(data))
    except (zipfile.BadZipFile, KeyError, ValueError) as e:
        raise UnsupportedFile("Fichier Word illisible (est-ce bien un .docx ?)") from e

    lignes: list[Line] = []
    vide = False
    for element in document.iter_inner_content():
        if not isinstance(element, Paragraph):
            continue
        du_paragraphe = _lignes_du_paragraphe(element)
        if not du_paragraphe:
            vide = True
            continue
        lignes.append(dataclasses.replace(du_paragraphe[0], vide_avant=vide))
        lignes += du_paragraphe[1:]
        vide = False
    return lignes
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_import_extract_docx.py tests/test_import_lignes.py -q`
Expected: `16 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/extract_docx.py tests/helpers_import.py tests/test_import_extract_docx.py
git commit -m "feat: extraction des fichiers Word (gras, italique, souligné, lignes vides)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Extraction d'un PDF

**Files:**
- Create: `tools/import_chants/extract_pdf.py`
- Modify: `tests/helpers_import.py` (version 3 : ajoute `pdf_bytes`, `pdf_image_seule`, `pdf_en_syllabes`)
- Test: `tests/test_import_extract_pdf.py`

**Interfaces:**
- Consumes: `Line`, `UnsupportedFile`, `lignes_depuis_caracteres`, `Caractere` (Task 1)
- Produces: `extract_pdf(data: bytes) -> list[Line]` ; `_raison_de_refus(polices: set[str], caracteres: int, empans: int, images: int) -> Optional[str]` (testée directement) ; test : `pdf_bytes(lignes: list[dict]) -> bytes` (clés `texte`, `y`, `taille`, `gras`, `souligne`, `copies`), `pdf_image_seule() -> bytes`, `pdf_en_syllabes() -> bytes`

- [ ] **Step 1: Écrire les tests qui échouent**

Remplacer `tests/helpers_import.py` par (version 3, finale) :

```python
"""Fabrique de fichiers Word et PDF pour les tests de l'import (textes inventés, rien du corpus)."""

import io

import fitz
from docx import Document
from docx.enum.style import WD_STYLE_TYPE

from tools.import_chants.modeles import Line


def L(texte: str, gras=False, italique=False, souligne=False, vide=False) -> Line:
    """Une Line abrégée, pour tester l'analyse sans passer par un fichier."""
    return Line(texte, gras, italique, souligne, vide)


def docx_bytes(paragraphes: list, style_gras: bool = False) -> bytes:
    """
    Un .docx. Chaque paragraphe est "" (paragraphe vide), une chaîne (texte simple) ou une liste de
    segments (texte, drapeaux) où les drapeaux sont des lettres : g = gras, i = italique, s = souligné.
    style_gras : applique à tous les paragraphes un style de paragraphe en gras (sans gras sur les runs).
    """
    document = Document()
    style = None
    if style_gras:
        style = document.styles.add_style("TitreGras", WD_STYLE_TYPE.PARAGRAPH)
        style.font.bold = True
    for paragraphe in paragraphes:
        segments = [(paragraphe, "")] if isinstance(paragraphe, str) else paragraphe
        p = document.add_paragraph(style=style)
        for texte, drapeaux in segments:
            run = p.add_run(texte)
            if "g" in drapeaux:
                run.bold = True
            if "i" in drapeaux:
                run.italic = True
            if "s" in drapeaux:
                run.underline = True
    sortie = io.BytesIO()
    document.save(sortie)
    return sortie.getvalue()


def pdf_bytes(lignes: list[dict]) -> bytes:
    """
    Un PDF d'une page. Chaque ligne : {"texte", "y", "taille" (12), "gras" (False), "souligne" (False),
    "copies" (1 : 3 ou plus simule le « faux gras » en imprimant le texte plusieurs fois)}.
    """
    document = fitz.open()
    page = document.new_page()
    for ligne in lignes:
        taille = ligne.get("taille", 12)
        police = "hebo" if ligne.get("gras") else "helv"
        for copie in range(ligne.get("copies", 1)):
            page.insert_text((72 + 0.4 * copie, ligne["y"] + 0.3 * copie), ligne["texte"],
                             fontsize=taille, fontname=police)
        if ligne.get("souligne"):
            largeur = fitz.Font(police).text_length(ligne["texte"], fontsize=taille)  # gère les accents
            page.draw_line((72, ligne["y"] + 2), (72 + largeur, ligne["y"] + 2), width=0.8)
    return document.tobytes()


def pdf_image_seule() -> bytes:
    """Un PDF dont la seule page est une image (un scan) : aucun texte."""
    document = fitz.open()
    page = document.new_page()
    image = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 20, 20), False)
    image.clear_with(200)
    page.insert_image(fitz.Rect(50, 50, 150, 150), pixmap=image)
    return document.tobytes()


def pdf_en_syllabes() -> bytes:
    """Un PDF dont le texte est découpé en fragments de 1 à 2 caractères, comme sous les notes d'une partition."""
    document = fitz.open()
    page = document.new_page()
    for k in range(150):
        page.insert_text((20 + (k % 25) * 22, 60 + (k // 25) * 30), ["la", "so", "a"][k % 3], fontsize=10)
    return document.tobytes()
```

Créer `tests/test_import_extract_pdf.py` :

```python
"""Tests de tools/import_chants/extract_pdf.py (PDF fabriqués par les tests avec PyMuPDF)."""

import pytest

from tests.helpers_import import pdf_bytes, pdf_en_syllabes, pdf_image_seule
from tools.import_chants.extract_pdf import _raison_de_refus, extract_pdf
from tools.import_chants.modeles import UnsupportedFile

# Texte d'au moins 40 caractères pour qu'un PDF de test ne soit pas jugé « sans texte ».
VERS = "Le vent du soir se lève sur la ville"


def lignes_pdf(*lignes):
    return extract_pdf(pdf_bytes(list(lignes)))


def test_police_grasse_donne_une_ligne_grasse():
    lignes = lignes_pdf({"texte": VERS, "y": 100, "gras": True}, {"texte": VERS + " encore", "y": 114})
    assert [(l.gras, l.italique) for l in lignes] == [(True, False), (False, False)]


def test_soulignement_detecte_sous_le_texte():
    lignes = lignes_pdf({"texte": "Pardon", "y": 100, "gras": True, "souligne": True},
                        {"texte": VERS, "y": 120})
    assert [(l.texte, l.souligne) for l in lignes] == [("Pardon", True), (VERS, False)]


def test_faux_gras_texte_imprime_plusieurs_fois_est_gras_et_non_duplique():
    lignes = lignes_pdf({"texte": VERS, "y": 100, "copies": 4}, {"texte": VERS + " encore", "y": 114})
    assert [l.texte for l in lignes] == [VERS, VERS + " encore"]
    assert lignes[0].gras is True and lignes[1].gras is False


def test_deux_copies_ne_font_pas_un_faux_gras():
    assert lignes_pdf({"texte": VERS, "y": 100, "copies": 2})[0].gras is False


def test_ligne_vide_restituee_quand_l_ecart_depasse_1_75_fois_la_taille():
    lignes = lignes_pdf(
        {"texte": VERS, "y": 100}, {"texte": VERS + " un", "y": 114},     # écart 14 pour 12 pt : même bloc
        {"texte": VERS + " deux", "y": 150},                                 # écart 36 : ligne vide
    )
    assert [l.vide_avant for l in lignes] == [True, False, True]  # la première ligne d'une page ouvre un bloc


def test_pdf_image_seule_est_refuse():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_pdf(pdf_image_seule())
    assert "image" in erreur.value.raison


def test_pdf_en_syllabes_est_une_partition():
    with pytest.raises(UnsupportedFile) as erreur:
        extract_pdf(pdf_en_syllabes())
    assert "Partition" in erreur.value.raison


def test_fichier_illisible():
    with pytest.raises(UnsupportedFile):
        extract_pdf(b"ceci n'est pas un PDF")


@pytest.mark.parametrize("polices, caracteres, empans, images, attendu", [
    ({"Helvetica"}, 500, 20, 0, None),                              # feuille normale
    ({"Maestro", "TimesNewRomanPSMT"}, 500, 20, 0, "Partition"),    # police de notation musicale
    ({"EngraverTextT"}, 500, 20, 0, "Partition"),
    ({"Helvetica"}, 300, 150, 0, "Partition"),                      # syllabes isolées
    ({"Helvetica"}, 10, 2, 1, "image"),                             # scan
    ({"Helvetica"}, 10, 2, 0, "vide"),
])
def test_raison_de_refus(polices, caracteres, empans, images, attendu):
    raison = _raison_de_refus(polices, caracteres, empans, images)
    assert (raison is None) if attendu is None else (attendu in raison)
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_import_extract_pdf.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.import_chants.extract_pdf'`.

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/extract_pdf.py` :

```python
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
_ESPACE_ENTRE_MOTS = 0.25    # écart (en tailles de police) à partir duquel on insère une espace


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


def extract_pdf(data: bytes) -> list[Line]:
    """
    Lit un PDF exporté de Word. Les lignes sont reconstruites caractère par caractère : gras de la
    police ou « faux gras » (texte imprimé 3 fois), italique, soulignement (trait fin sous le texte).
    Une ligne vide est restituée par `vide_avant` quand l'écart avec la ligne précédente dépasse
    1,75 fois la taille de police.
    """
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as e:  # PyMuPDF lève plusieurs types d'erreurs selon le fichier
        raise UnsupportedFile("PDF illisible") from e
    _verifier_exploitable(document)

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
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_import_extract_pdf.py -q`
Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/extract_pdf.py tests/helpers_import.py tests/test_import_extract_pdf.py
git commit -m "feat: extraction des PDF (faux gras, soulignement) et refus des partitions et images" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Analyse en chants et en sections

**Files:**
- Create: `tools/import_chants/parse.py`
- Test: `tests/test_import_parse_entetes.py`, `tests/test_import_parse_sections.py`

**Interfaces:**
- Consumes: `Line`, `ParsedSong`, `ParseResult` (Task 1) ; `clean_spaces` (`tools/slicing.py`) ; `compute_ordre` (`tools/chant_structure.py`) ; `MomentLiturgique`, `SectionChant`, `TypeSection` (`context/models.py`) ; test : `L` (Task 1)
- Produces: `parse_lines(lignes: list[Line], nom_fichier: str = "") -> ParseResult` ; chaque `ParsedSong` a un titre non vide, au moins une section, et un `ordre` qui ne référence que ses sections

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_import_parse_entetes.py` (reconnaissance des chants, moments, recueils, titres) :

```python
"""Tests de tools/import_chants/parse.py : reconnaissance des chants, moments, recueils et titres."""

from context.models import MomentLiturgique as M
from tests.helpers_import import L
from tools.import_chants.parse import parse_lines


def feuille() -> list:
    """Une feuille de messe inventée : en-tête, un chant d'entrée, un pardon, un gloire."""
    return [
        L("Messe du village   Dimanche 4 octobre 2026", gras=True, souligne=True),
        L("Entrée", gras=True, souligne=True, vide=True),
        L("Venez au bord du fleuve, chantons la lumière", gras=True),
        L("Le soleil se lève sur la rivière", gras=True),
        L("1. L'eau claire descend de la colline", vide=True),
        L("Les enfants courent vers le pont"),
        L("Pardon (Recueil Aurore 2)", gras=True, souligne=True, vide=True),
        L("Seigneur, nous marchons dans la nuit", vide=True),
        L("Gloire a Dieu   Recueil Aurore 2", gras=True, souligne=True, vide=True),
        L("Gloire au vent qui passe, gloire aux rivières !", gras=True, vide=True),
        L("Les montagnes chantent le matin", vide=True),
    ]


def test_une_feuille_est_decoupee_en_chants_avec_moments_et_recueils():
    resultat = parse_lines(feuille(), "feuille.docx")
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.PARDON, M.GLOIRE]
    assert [c.recueil for c in resultat.chants] == [None, "Recueil Aurore 2", "Recueil Aurore 2"]
    assert resultat.notes == ["Feuille : Messe du village Dimanche 4 octobre 2026"]


def test_titres_proposes():
    titres = [c.titre for c in parse_lines(feuille(), "feuille.docx").chants]
    assert titres == [
        "Venez au bord du fleuve",              # entrée : début du premier refrain
        "Pardon – Recueil Aurore 2",             # ordinaire : en-tête et recueil
        "Gloire a Dieu – Recueil Aurore 2",
    ]


def test_une_ligne_de_refrain_qui_commence_par_un_mot_du_vocabulaire_n_est_pas_un_en_tete():
    # « Gloire au vent qui passe, … » est en gras mais contient de la ponctuation et fait partie du chant
    resultat = parse_lines(feuille(), "feuille.docx")
    assert len(resultat.chants) == 3


def test_en_tete_title_artist():
    lignes = [
        L("Title: ALLÉLUIA", gras=True), L("Artist: Recueil Aurore 2", gras=True),
        L("Alléluia, chantons", vide=True),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil, chant.titre) == (M.ALLELUIA, "Recueil Aurore 2", "Alléluia – Recueil Aurore 2")


def test_en_tete_en_gras_seul_sur_sa_propre_ligne():
    lignes = [
        L("Agneau  Recueil Aurore 2", gras=True, vide=True),
        L("Toi l'Agneau qui enlèves nos fautes", vide=True),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert (chant.moment, chant.recueil) == (M.AGNEAU, "Recueil Aurore 2")


def test_recueil_entre_parentheses_sur_la_ligne_suivante():
    lignes = [L("Pardon", gras=True, souligne=True), L("(Recueil Aurore 2)"), L("Prends pitié de nous", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil == "Recueil Aurore 2"
    assert chant.structure[0].lignes == ["Prends pitié de nous"]


def test_etiquettes_de_section_soulignees_ne_sont_pas_des_chants():
    lignes = [
        L("Communion", gras=True, souligne=True),
        L("Couplet 1", gras=True, souligne=True, vide=True), L("La rivière chante"),
        L("Refrain", gras=True, souligne=True, vide=True), L("Chantons tous ensemble", gras=True),
        L("Pont", gras=True, souligne=True, vide=True), L("Plus haut que les nuages"),
    ]
    resultat = parse_lines(lignes, "x.docx")
    assert [c.moment for c in resultat.chants] == [M.COMMUNION]
    assert [s.id for s in resultat.chants[0].structure] == ["1", "R", "P"]


def test_renvoi_vers_un_autre_chant_n_est_pas_importe():
    lignes = [L("Sortie", gras=True, souligne=True), L("VOIR CHANT D'ENTREE", gras=True, souligne=True)]
    resultat = parse_lines(lignes, "x.docx")
    assert resultat.chants == []
    assert any("Sortie" in n and "Renvoi" in n for n in resultat.notes)


def test_psaume_ne_garde_que_le_refrain_en_gras():
    lignes = [
        L("Psaume", gras=True, souligne=True),
        L("Le fleuve chante la paix du Seigneur.", gras=True),
        L("Premier verset du psaume", vide=True), L("Second verset du psaume"),
    ]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert [(s.id, s.lignes) for s in chant.structure] == [("R", ["Le fleuve chante la paix du Seigneur."])]
    assert any("psaume" in n.lower() for n in chant.notes)


def test_titre_en_majuscules_sous_l_en_tete():
    lignes = [L("Communion", gras=True, souligne=True), L("LE CHANT DU FLEUVE", gras=True, vide=True),
              L("Le fleuve descend vers la mer", vide=True)]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.titre == "Le chant du fleuve"
    assert chant.moment is M.COMMUNION


def test_chant_seul_titre_et_moment_viennent_du_nom_du_fichier():
    [chant] = parse_lines([L("Alléluia, chantons le matin"), L("Alléluia, chantons le soir")],
                          "C:/chants/alleluia du matin.docx").chants
    assert (chant.titre, chant.moment, chant.recueil) == ("Alleluia du matin", M.ALLELUIA, None)


def test_vocabulaire_varie():
    cas = {"Chant de Pardon": M.PARDON, "Prières universelle": M.PU, "Gloria": M.GLOIRE, "Agnus Dei": M.AGNEAU,
           "Saint": M.SANCTUS, "Evangile": M.ALLELUIA, "Sortie": M.ENVOI, "Offertoire": M.OFFERTOIRE}
    for en_tete, moment in cas.items():
        [chant] = parse_lines([L(en_tete, gras=True, souligne=True), L("Un vers inventé")], "x.docx").chants
        assert chant.moment is moment, en_tete


def test_les_reprises_2x_sont_retirees_et_signalees():
    lignes = [L("Sanctus", gras=True, souligne=True), L("Saint, saint, saint 2x"), L("Le ciel chante 2X")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.structure[0].lignes == ["Saint, saint, saint", "Le ciel chante"]
    assert any("reprise" in n for n in chant.notes)


def test_bis_en_fin_de_ligne_est_une_reprise_et_non_un_recueil():
    lignes = [L("Prière universelle (bis)", gras=True, souligne=True), L("Entends nos prières (bis)")]
    [chant] = parse_lines(lignes, "x.docx").chants
    assert chant.recueil is None
    assert chant.structure[0].lignes == ["Entends nos prières"]


def test_lignes_avant_le_premier_chant_sont_signalees():
    lignes = [L("Un texte d'introduction"), L("Entrée", gras=True, souligne=True), L("Un vers inventé")]
    resultat = parse_lines(lignes, "x.docx")
    assert any("avant le premier chant" in n for n in resultat.notes)
    assert len(resultat.chants) == 1


def test_fichier_sans_texte_ne_donne_aucun_chant():
    assert parse_lines([], "x.docx").chants == []
```

Créer `tests/test_import_parse_sections.py` (sections, refrain, ordre chanté) :

```python
"""Tests de tools/import_chants/parse.py : sections, refrain et ordre chanté d'un chant."""

from context.models import TypeSection
from tests.helpers_import import L
from tools.import_chants.parse import parse_lines


def chant_de(*lignes):
    """Le seul chant d'un fichier sans en-tête (chant seul)."""
    [chant] = parse_lines(list(lignes), "chant inventé.docx").chants
    return chant


def ids(chant) -> list[str]:
    return [s.id for s in chant.structure]


def test_refrain_en_gras_avec_couplets_numerotes():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Alléluia pour la rivière", gras=True),
        L("1. Le matin se lève sur la ville", vide=True), L("Les cloches annoncent le jour"),
        L("2. Le soir descend sur la vallée", vide=True), L("Nous rendons grâce pour ce jour"),
    )
    assert ids(chant) == ["R", "1", "2"]
    assert chant.structure[0].type is TypeSection.REFRAIN
    assert chant.structure[1].lignes[0] == "Le matin se lève sur la ville"  # le « 1. » est retiré
    assert chant.ordre == ["R", "1", "R", "2", "R"]


def test_refrain_apres_le_premier_couplet():
    chant = chant_de(
        L("Premier couplet inventé"), L("Chantons au bord de l'eau", gras=True, vide=True),
        L("Second couplet inventé", vide=True),
    )
    assert ids(chant) == ["1", "R", "2"]
    assert chant.ordre == ["1", "R", "2", "R"]


def test_pont_etiquete():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Premier couplet inventé", vide=True),
        L("Pont :", vide=True), L("Plus haut que les nuages"),
    )
    assert ids(chant) == ["R", "1", "P"]
    assert chant.structure[2].type is TypeSection.PONT
    assert chant.structure[2].lignes == ["Plus haut que les nuages"]
    assert chant.ordre == ["R", "1", "R", "P", "R"]


def test_refrain_en_italique_a_defaut_de_gras():
    chant = chant_de(L("Premier couplet inventé"), L("Chantons au bord de l'eau", italique=True, vide=True))
    assert [s.type for s in chant.structure] == [TypeSection.COUPLET, TypeSection.REFRAIN]


def test_le_gras_l_emporte_sur_l_italique():
    chant = chant_de(
        L("Couplet en italique", italique=True), L("Refrain en gras", gras=True, vide=True),
        L("Autre couplet", vide=True),
    )
    assert [s.type for s in chant.structure] == [TypeSection.COUPLET, TypeSection.REFRAIN, TypeSection.COUPLET]


def test_bloc_repete_est_un_refrain_et_l_ordre_du_document_est_conserve():
    chant = chant_de(
        L("Chantons au bord de l'eau"), L("Premier couplet inventé", vide=True),
        L("Chantons au bord de l'eau", vide=True),
    )
    assert ids(chant) == ["R", "1"]
    assert chant.ordre == ["R", "1", "R"]


def test_tout_le_chant_en_gras_aucun_refrain_et_avertissement():
    chant = chant_de(L("Premier bloc", gras=True), L("Second bloc", gras=True, vide=True))
    assert all(s.type is TypeSection.COUPLET for s in chant.structure)
    assert any("gras" in a for a in chant.avertissements)


def test_aucun_refrain_avertissement_et_ordre_du_document():
    chant = chant_de(L("Premier couplet inventé"), L("Second couplet inventé", vide=True))
    assert chant.avertissements == ["Aucun refrain détecté"]
    assert chant.ordre == ["1", "2"]


def test_deux_refrains_differents_gardent_l_ordre_du_document():
    chant = chant_de(
        L("Premier refrain", gras=True), L("Un couplet inventé", vide=True),
        L("Second refrain", gras=True, vide=True),
    )
    assert ids(chant) == ["R", "1", "R2"]
    assert chant.ordre == ["R", "1", "R2"]


def test_numeros_de_couplets_en_double_restent_uniques():
    chant = chant_de(L("1. Premier"), L("1. Deuxième", vide=True), L("1. Troisième", vide=True))
    assert ids(chant) == ["1", "2", "3"]


def test_les_espaces_sont_nettoyees_et_les_lignes_vides_ignorees():
    chant = chant_de(L("  Le vent   se lève\xa0!  "), L("   ", vide=True), L("La mer"))
    assert chant.structure[0].lignes == ["Le vent se lève\xa0!", "La mer"]


def test_l_ordre_ne_reference_que_des_sections_existantes():
    chant = chant_de(
        L("Chantons au bord de l'eau", gras=True), L("Pont :", vide=True), L("Plus haut"),
        L("Un couplet inventé", vide=True), L("Chantons au bord de l'eau", gras=True, vide=True),
    )
    assert set(chant.ordre) <= set(ids(chant))
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_import_parse_entetes.py tests/test_import_parse_sections.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.import_chants.parse'`.

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/parse.py` :

```python
"""
Analyse d'une liste de Line (voir extract_docx / extract_pdf) : découpe d'une feuille de messe en
chants, et de chaque chant en sections (refrain, couplets, pont). Règles : spec §6.
"""

import dataclasses
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from context.models import MomentLiturgique as M
from context.models import SectionChant, TypeSection
from tools.chant_structure import compute_ordre
from tools.import_chants.modeles import Line, ParsedSong, ParseResult
from tools.slicing import clean_spaces

# Vocabulaire des en-têtes (texte sans accents, en minuscules, au début de l'en-tête).
_VOCABULAIRE: list[tuple[M, str]] = [
    (M.PSAUME, r"psaume"),
    (M.PU, r"prieres? universelles?"),
    (M.OFFERTOIRE, r"offertoire"),
    (M.ENTREE, r"entree"),
    (M.PARDON, r"pardon|kyrie|kirie"),
    (M.GLOIRE, r"gloire( a dieu)?|gloria"),
    (M.ALLELUIA, r"alleluia|evangile|acclamation"),
    (M.SANCTUS, r"sanctus|tu es saint|saint"),
    (M.ANAMNESE, r"anamnese"),
    (M.AGNEAU, r"agneau( de dieu)?|agnus( dei)?"),
    (M.COMMUNION, r"communion"),
    (M.ENVOI, r"sortie|envoi"),
]
_ORDINAIRES = {M.PARDON, M.GLOIRE, M.ALLELUIA, M.PU, M.SANCTUS, M.ANAMNESE, M.AGNEAU, M.PSAUME}
_TITRE_PAR_DEFAUT = {M.ENTREE: "Entrée", M.COMMUNION: "Communion", M.ENVOI: "Envoi",
                     M.OFFERTOIRE: "Offertoire"}
# Mots qu'un titre tiré d'un vers ne doit pas terminer (« Chaque jour, chaque moment, en ce »).
_MOTS_OUTILS = {
    "de", "du", "des", "la", "le", "les", "un", "une", "et", "ou", "a", "au", "aux", "en", "que", "qui",
    "ce", "se", "sa", "son", "ses", "mon", "ma", "mes", "ton", "ta", "tes", "dans", "par", "pour",
    "sur", "avec", "sans", "sous", "comme", "mais", "car", "donc", "ni", "si", "y", "ne",
}

_DATE = re.compile(
    r"\b(lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\b"
    r"|\b\d{1,2}(er)?\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\b"
)
_RENVOI = re.compile(r"^\s*voir\b", re.IGNORECASE)
_REPRISE = r"(?:\d\s*x|x\s*\d|bis)"
_BIS = re.compile(rf"\s*\(?\b{_REPRISE}\b\)?\s*$", re.IGNORECASE)
_PREFIXE_CHANT = re.compile(r"chant\s+(?:de\s+la\s+|de\s+l'|de\s+|du\s+|d'|a\s+la\s+|a\s+)?")
# Étiquettes de section : « 1. », « Couplet 2 », « Pont : », « Refrain », « R/ »
_ETIQUETTE_COUPLET = re.compile(r"^(?:(\d{1,2})\s*[.)]|couplet\s*(\d{1,2})\s*:?)\s*(.*)$", re.IGNORECASE)
_ETIQUETTE_PONT = re.compile(r"^pont\s*(?::\s*(.*))?$", re.IGNORECASE)
_ETIQUETTE_REFRAIN = re.compile(r"^(?:(?:refrain|ref|r)\s*[:./]\s*(.*)|refrain)$", re.IGNORECASE)
_PONCTUATION_FINALE = re.compile(r"[.,;:!?…]$")
_MOTS_TITRE_VERS = 6    # un titre tiré d'un vers a au plus ce nombre de mots
_MOTS_ENTETE_MAX = 6    # un en-tête en gras seul (sans soulignement) a au plus ce nombre de mots
_MOTS_TITRE_MAJUSCULES = 8


# --- Utilitaires de texte ---

def _sans_accents(texte: str) -> str:
    """Minuscules sans accents, de même longueur que le texte d'origine."""
    return "".join(unicodedata.normalize("NFD", c)[0] for c in texte).lower()


def _moment_en_tete(texte: str) -> tuple[Optional[M], str]:
    """(moment, texte restant après le mot-clé) si le texte commence par un mot du vocabulaire."""
    normal = _sans_accents(texte.strip())
    prefixe = _PREFIXE_CHANT.match(normal)  # « Chant de Pardon », « Chant de sortie »
    saut = prefixe.end() if prefixe else 0
    for moment, motif in _VOCABULAIRE:
        m = re.match(rf"(?:{motif})\b", normal[saut:])
        if m:
            return moment, texte.strip()[saut + m.end():]
    return None, texte


def _majuscule(texte: str) -> str:
    """Un titre tout en majuscules devient « Je n'ai que ma prière » ; sinon première lettre en capitale."""
    texte = clean_spaces(texte)
    if texte.isupper():
        texte = texte.capitalize()
    return texte[:1].upper() + texte[1:]


def _est_etiquette(texte: str) -> bool:
    """« Couplet 1 », « Refrain », « Pont » : une étiquette de section, jamais un titre de chant."""
    texte = clean_spaces(texte)
    return any(r.match(texte) for r in (_ETIQUETTE_COUPLET, _ETIQUETTE_PONT, _ETIQUETTE_REFRAIN))


def _ressemble_a_un_recueil(texte: str) -> bool:
    texte = texte.strip()
    return (
        bool(texte) and len(texte.split()) <= 6 and not re.search(r"[.,;:!?…]", texte)
        and not _est_etiquette(texte)  # « Couplet 1 » est une étiquette de section, pas un recueil
    )


def _brut(ligne: Line) -> str:
    return ligne.texte.replace("\xa0", " ").replace("\t", " ").strip()


def _avec_vide_avant(ligne: Line, vide: bool) -> Line:
    return dataclasses.replace(ligne, vide_avant=vide)


# --- En-têtes ---

@dataclass
class _Entete:
    debut: int            # index de la première ligne de l'en-tête
    fin: int              # index après la dernière ligne de l'en-tête
    texte: str            # texte de l'en-tête (espaces d'origine conservés)
    recueil_explicite: Optional[str] = None  # « Artist: … »
    titre_explicite: bool = False             # « Title: … »


def _chercher_entetes(lignes: list[Line]) -> list[_Entete]:
    """
    En-têtes de chant : « Title: … » (suivi de « Artist: … »), ligne en gras et soulignée, ou ligne en
    gras seul qui commence par un mot du vocabulaire et occupe son bloc à elle seule.
    """
    entetes: list[_Entete] = []
    i = 0
    while i < len(lignes):
        ligne, brut = lignes[i], _brut(lignes[i])
        suivante_vide = i + 1 >= len(lignes) or lignes[i + 1].vide_avant
        titre = re.match(r"^title\s*:\s*(.+)$", brut, re.IGNORECASE)
        if titre:
            fin, recueil = i + 1, None
            if i + 1 < len(lignes):
                artiste = re.match(r"^artist\s*:\s*(.*)$", _brut(lignes[i + 1]), re.IGNORECASE)
                if artiste:
                    fin, recueil = i + 2, clean_spaces(artiste.group(1)) or None
            entetes.append(_Entete(i, fin, titre.group(1).strip(), recueil, True))
            i = fin
            continue
        moment, _ = _moment_en_tete(brut)
        souligne_gras = ligne.souligne and (ligne.gras or moment is not None)
        gras_seul = (
            ligne.gras and not ligne.souligne and moment is not None
            and (i == 0 or ligne.vide_avant) and suivante_vide
            and not _PONCTUATION_FINALE.search(brut) and len(brut.split()) <= _MOTS_ENTETE_MAX
        )
        if (souligne_gras or gras_seul) and not _RENVOI.match(brut) and not _est_etiquette(brut):
            entetes.append(_Entete(i, i + 1, brut))
        i += 1
    return entetes


def _decomposer_entete(texte: str) -> tuple[str, Optional[str], Optional[str]]:
    """(partie gauche : titre ou moment, recueil, reste = paroles collées à l'en-tête)."""
    texte = _BIS.sub("", texte)  # « (bis) » ou « 2x » en fin d'en-tête : une reprise, pas un recueil
    m = re.search(r"\(([^)]*)\)?\s*$", texte)
    if m:
        return texte[:m.start()].strip(), clean_spaces(m.group(1)) or None, None
    morceaux = re.split(r"\s{3,}", texte, maxsplit=1)
    if len(morceaux) == 2:
        gauche, droite = morceaux
        if _ressemble_a_un_recueil(droite):
            return gauche.strip(), clean_spaces(droite), None
        return gauche.strip(), None, droite.strip()
    moment, reste = _moment_en_tete(texte)
    if moment is not None and reste.strip():
        gauche = texte[: len(texte) - len(reste)].strip()
        if _ressemble_a_un_recueil(reste):
            return gauche, clean_spaces(reste), None
        return gauche, None, reste.strip()
    return texte.strip(), None, None


def _est_metadonnee(entete: _Entete, lignes: list[Line]) -> bool:
    """En-tête de la feuille (date, nom de l'église) plutôt qu'un chant."""
    normal = _sans_accents(entete.texte)
    if _DATE.search(normal):
        return True
    debut_feuille = re.match(r"(messe|eglise)\b", normal) is not None
    suivante_vide = entete.fin >= len(lignes) or lignes[entete.fin].vide_avant
    return debut_feuille and _moment_en_tete(entete.texte)[0] is None and suivante_vide


# --- Corps d'un chant : lignes, blocs, sections ---

def _normaliser(lignes: list[Line]) -> tuple[list[Line], list[str]]:
    """Nettoie les espaces, retire les reprises « 2x », écarte les renvois."""
    propres, notes, reprises = [], [], 0
    for ligne in lignes:
        texte = clean_spaces(ligne.texte)
        if not texte:
            continue
        if _RENVOI.match(texte):
            notes.append(f"Renvoi ignoré : {texte}")
            continue
        sans_reprise = _BIS.sub("", texte).strip()
        if sans_reprise and sans_reprise != texte:
            reprises += 1
            texte = sans_reprise
        propres.append(dataclasses.replace(ligne, texte=texte))
    if reprises:
        notes.append(f"{reprises} reprise(s) « 2x » retirée(s) du texte")
    return propres, notes


@dataclass
class _Bloc:
    etiquette: Optional[TypeSection]
    numero: Optional[str]
    lignes: list[Line]


def _decouper_en_blocs(lignes: list[Line]) -> list[_Bloc]:
    """Un bloc par étiquette de section ou par ligne vide."""
    blocs: list[_Bloc] = []
    courant: Optional[_Bloc] = None
    for ligne in lignes:
        etiquette, numero, reste = None, None, None
        if (m := _ETIQUETTE_COUPLET.match(ligne.texte)):
            etiquette, numero, reste = TypeSection.COUPLET, m.group(1) or m.group(2), m.group(3)
        elif (m := _ETIQUETTE_PONT.match(ligne.texte)):
            etiquette, reste = TypeSection.PONT, m.group(1) or ""
        elif (m := _ETIQUETTE_REFRAIN.match(ligne.texte)):
            etiquette, reste = TypeSection.REFRAIN, m.group(1) or ""

        if etiquette is not None:
            courant = _Bloc(etiquette, numero, [])
            blocs.append(courant)
            if reste and reste.strip():
                courant.lignes.append(Line(reste.strip(), ligne.gras, ligne.italique))
            continue
        if courant is None or ligne.vide_avant:
            courant = _Bloc(None, None, [])
            blocs.append(courant)
        courant.lignes.append(ligne)
    return [b for b in blocs if b.lignes]


def _cle(bloc: _Bloc) -> str:
    return "|".join(_sans_accents(clean_spaces(l.texte)) for l in bloc.lignes)


def _toutes(bloc: _Bloc, attribut: str) -> bool:
    return all(getattr(l, attribut) for l in bloc.lignes)


def _types_des_blocs(blocs: list[_Bloc]) -> tuple[list[TypeSection], list[str]]:
    """
    Type de chaque bloc : son étiquette ; sinon refrain si tout le bloc est en gras (ou, à défaut,
    en italique) alors que le chant a d'autres blocs ; sinon refrain si le bloc est répété ; sinon couplet.
    """
    libres = [b for b in blocs if b.etiquette is None]
    avertissements: list[str] = []
    refrains: set[int] = set()
    for attribut in ("gras", "italique"):
        marques = [b for b in libres if _toutes(b, attribut)]
        autres = [b for b in blocs if not _toutes(b, attribut)]
        if marques and autres:
            refrains = {id(b) for b in marques}
            break
        if marques and len(blocs) > 1:
            avertissements.append(
                "Tout le chant est en gras : refrain non détecté" if attribut == "gras"
                else "Tout le chant est en italique : refrain non détecté"
            )
    if not refrains:
        comptes: dict[str, int] = {}
        for b in libres:
            comptes[_cle(b)] = comptes.get(_cle(b), 0) + 1
        refrains = {id(b) for b in libres if comptes[_cle(b)] >= 2}

    types = [b.etiquette or (TypeSection.REFRAIN if id(b) in refrains else TypeSection.COUPLET) for b in blocs]
    return types, avertissements


def _construire_sections(blocs: list[_Bloc]) -> tuple[list[SectionChant], list[str], list[str]]:
    """(sections, ordre du document, avertissements). Les refrains identiques sont fusionnés."""
    types, avertissements = _types_des_blocs(blocs)
    sections: list[SectionChant] = []
    par_cle: dict[str, str] = {}
    ordre_document: list[str] = []
    compteurs = {TypeSection.REFRAIN: 0, TypeSection.PONT: 0}
    prochain_couplet = 1

    for bloc, type_ in zip(blocs, types):
        if type_ is TypeSection.REFRAIN and _cle(bloc) in par_cle:
            ordre_document.append(par_cle[_cle(bloc)])
            continue
        if type_ is TypeSection.REFRAIN:
            compteurs[type_] += 1
            identifiant = "R" if compteurs[type_] == 1 else f"R{compteurs[type_]}"
            par_cle[_cle(bloc)] = identifiant
        elif type_ is TypeSection.PONT:
            compteurs[type_] += 1
            identifiant = "P" if compteurs[type_] == 1 else f"P{compteurs[type_]}"
        else:
            numero = int(bloc.numero) if bloc.numero else prochain_couplet
            while str(numero) in {s.id for s in sections}:
                numero += 1
            identifiant, prochain_couplet = str(numero), numero + 1
        sections.append(SectionChant(identifiant, type_, [l.texte for l in bloc.lignes]))
        ordre_document.append(identifiant)

    if not any(s.type is TypeSection.REFRAIN for s in sections) and not avertissements:
        avertissements.append("Aucun refrain détecté")
    return sections, ordre_document, avertissements


# --- Titres ---

def _titre_court(ligne: str) -> str:
    """Début d'une ligne comme titre : coupé à la première ponctuation, sans mot-outil à la fin."""
    mots = clean_spaces(ligne).split()[:_MOTS_TITRE_VERS]
    for i, mot in enumerate(mots[:-1]):
        if re.search(r"[,;:.!?…]$", mot):
            mots = mots[:i + 1]
            break
    while len(mots) > 1 and _sans_accents(re.sub(r"[^\w']", "", mots[-1])).split("'")[-1] in _MOTS_OUTILS:
        mots.pop()
    return re.sub(r"[\s,;:.!?…]+$", "", " ".join(mots))


def _titre_depuis_le_texte(sections: list[SectionChant], defaut: str) -> str:
    for section in sorted(sections, key=lambda s: s.type is not TypeSection.REFRAIN):
        if section.lignes:
            titre = _titre_court(section.lignes[0])
            if titre:
                return titre
    return defaut


def _titre_depuis_le_fichier(nom_fichier: str) -> str:
    nom = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", nom_fichier.replace("\\", "/").rsplit("/", 1)[-1])
    return _majuscule(re.sub(r"[_\s]+", " ", nom).strip()) or "Chant"


def _titre_du_chant(
    entete: Optional[_Entete], titre: Optional[str], base: str, moment: M, recueil: Optional[str],
    sections: list[SectionChant], nom_fichier: str,
) -> str:
    """
    Titre explicite s'il existe ; chant seul : nom du fichier ; ordinaire (pardon, gloire…) :
    « Pardon – Lyon centre 4 » ; en-tête réduit au nom du moment : début du premier refrain.
    """
    if titre is not None:
        return f"{_majuscule(titre)} – {recueil}" if moment in _ORDINAIRES and recueil else _majuscule(titre)
    if entete is None:
        return _titre_depuis_le_fichier(nom_fichier)
    base_propre = _majuscule(base) if base else ""
    if moment in _ORDINAIRES:
        return f"{base_propre} – {recueil}" if recueil else base_propre
    seulement_le_moment = moment is not M.AUTRE and not _moment_en_tete(base_propre)[1].strip()
    if seulement_le_moment or not base_propre:
        return _titre_depuis_le_texte(sections, _TITRE_PAR_DEFAUT.get(moment, "Chant"))
    return base_propre


# --- Un chant, une feuille ---

def _chant(entete: Optional[_Entete], corps: list[Line], nom_fichier: str) -> Optional[ParsedSong]:
    moment, recueil, titre, base = M.AUTRE, None, None, ""
    if entete is None:  # chant seul : le moment peut se lire dans le nom du fichier
        moment = _moment_en_tete(_titre_depuis_le_fichier(nom_fichier))[0] or M.AUTRE
    elif entete.titre_explicite:
        base, recueil = entete.texte, entete.recueil_explicite
        titre, moment = base, _moment_en_tete(base)[0] or M.AUTRE
    else:
        base, recueil, collees = _decomposer_entete(entete.texte)
        moment = _moment_en_tete(base)[0] or M.AUTRE
        if collees:  # des paroles collées à l'en-tête : première ligne du corps
            corps = [Line(collees, gras=True)] + corps

    # « Pardon » souligné puis « (Lyon centre 2) » non souligné : le recueil est sur la ligne suivante
    if entete is not None and recueil is None and corps and not corps[0].vide_avant:
        m = re.fullmatch(r"\(\s*([^()]*?)\s*\)?", clean_spaces(corps[0].texte))
        if m and m.group(1) and not re.fullmatch(_REPRISE, m.group(1), re.IGNORECASE):
            recueil, corps = clean_spaces(m.group(1)), corps[1:]

    # Titre en majuscules juste sous l'en-tête (ex. « JE N'AI QUE MA PRIÈRE »)
    if corps and corps[0].gras and clean_spaces(corps[0].texte).isupper() \
            and len(corps[0].texte.split()) <= _MOTS_TITRE_MAJUSCULES \
            and not _PONCTUATION_FINALE.search(corps[0].texte.strip()):
        titre, corps = corps[0].texte, corps[1:]

    corps, notes = _normaliser(corps)

    if moment is M.PSAUME:  # le corps du psaume vient d'AELF : on ne garde que le refrain en gras
        gras = [l for l in corps if l.gras]
        if len(gras) != len(corps):
            notes.append("Corps du psaume ignoré (fourni par AELF), refrain conservé")
        corps = [_avec_vide_avant(l, i == 0) for i, l in enumerate(gras)]

    blocs = _decouper_en_blocs(corps)
    if moment is M.PSAUME:  # ce qui reste du psaume est son refrain
        for bloc in blocs:
            bloc.etiquette = TypeSection.REFRAIN
    if not blocs:
        return None
    sections, ordre_document, avertissements = _construire_sections(blocs)

    # Refrain répété dans le document : on garde l'ordre explicite ; sinon, ordre chanté par défaut
    refrain_repete = any(ordre_document.count(s.id) > 1 for s in sections if s.type is TypeSection.REFRAIN)
    ordre = ordre_document if refrain_repete else compute_ordre(sections)

    return ParsedSong(
        titre=_titre_du_chant(entete, titre, base, moment, recueil, sections, nom_fichier),
        moment=moment, recueil=recueil, structure=sections, ordre=ordre,
        notes=notes, avertissements=avertissements,
    )


def parse_lines(lignes: list[Line], nom_fichier: str = "") -> ParseResult:
    """
    Découpe les lignes d'un fichier en chants (feuille de messe) ou lit un chant seul (titre tiré du
    nom du fichier). Ce qui n'est pas importé (en-tête de la feuille, renvois, lignes avant le premier
    chant) est signalé dans `notes`.
    """
    resultat = ParseResult()
    entetes = _chercher_entetes(lignes)

    debut = 0
    if entetes and _est_metadonnee(entetes[0], lignes):  # date, nom de l'église : pas un chant
        resultat.notes.append(f"Feuille : {clean_spaces(entetes[0].texte)}")
        debut, entetes = entetes[0].fin, entetes[1:]

    if not entetes:
        chant = _chant(None, lignes[debut:], nom_fichier)
        if chant:
            resultat.chants.append(chant)
        return resultat

    avant = [l for l in lignes[debut:entetes[0].debut] if l.texte.strip()]
    if avant:
        resultat.notes.append(f"{len(avant)} ligne(s) avant le premier chant ignorée(s)")
    for k, entete in enumerate(entetes):
        fin = entetes[k + 1].debut if k + 1 < len(entetes) else len(lignes)
        corps = lignes[entete.fin:fin]
        chant = _chant(entete, corps, nom_fichier)
        if chant:
            resultat.chants.append(chant)
        else:
            raison = next(iter(_normaliser(corps)[1]), None)
            resultat.notes.append(
                f"« {clean_spaces(entete.texte)} » : rien à importer" + (f" ({raison})" if raison else "")
            )
    return resultat
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_import_parse_entetes.py tests/test_import_parse_sections.py -q`
Expected: `28 passed`

- [ ] **Step 5: Lancer toute la suite**

Run: `python -m pytest tests -q`
Expected: tous les tests passent (aucune régression sur les livraisons précédentes).

- [ ] **Step 6: Commit**

```bash
git add tools/import_chants/parse.py tests/test_import_parse_entetes.py tests/test_import_parse_sections.py
git commit -m "feat: analyse des feuilles de messe en chants, sections, refrain et ordre chanté" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Point d'entrée de l'import

**Files:**
- Create: `tools/import_chants/importer.py`
- Test: `tests/test_import_importer.py`

**Interfaces:**
- Consumes: `extract_docx` (Task 2), `extract_pdf` (Task 3), `parse_lines` (Task 4), `ParseResult`, `UnsupportedFile` (Task 1) ; tests : `docx_bytes`, `pdf_bytes`, `pdf_en_syllabes` (Tasks 2-3)
- Produces: `analyser_fichier(nom_fichier: str, data: bytes) -> ParseResult` ; `TAILLE_MAX = 10 * 1024 * 1024` ; lève `UnsupportedFile(raison)` pour une extension non gérée, un fichier trop gros ou illisible, une partition, un PDF sans texte

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_import_importer.py` :

```python
"""Tests de tools/import_chants/importer.py : le point d'entrée de l'import."""

import pytest

from context.models import MomentLiturgique as M
from tests.helpers_import import docx_bytes, pdf_bytes, pdf_en_syllabes
from tools.import_chants.importer import TAILLE_MAX, analyser_fichier
from tools.import_chants.modeles import UnsupportedFile

FEUILLE_WORD = [
    [("Entrée", "gs")],
    [("Venez au bord du fleuve, chantons", "g")],
    "",
    "Premier couplet inventé",
    [("Pardon", "gs")],
    "Prends pitié de nous",
]


def test_fichier_word():
    resultat = analyser_fichier("feuille.docx", docx_bytes(FEUILLE_WORD))
    assert [c.moment for c in resultat.chants] == [M.ENTREE, M.PARDON]


def test_extension_en_majuscules():
    assert len(analyser_fichier("FEUILLE.DOCX", docx_bytes(FEUILLE_WORD)).chants) == 2


def test_fichier_pdf():
    pdf = pdf_bytes([
        {"texte": "Entrée", "y": 100, "gras": True, "souligne": True},
        {"texte": "Venez au bord du fleuve, chantons la lumière", "y": 114, "gras": True},
        {"texte": "Premier couplet inventé pour le test", "y": 150},
    ])
    [chant] = analyser_fichier("feuille.pdf", pdf).chants
    assert chant.moment is M.ENTREE
    assert [s.id for s in chant.structure] == ["R", "1"]


def test_partition_refusee_avec_une_raison():
    with pytest.raises(UnsupportedFile) as erreur:
        analyser_fichier("partition.pdf", pdf_en_syllabes())
    assert "Partition" in erreur.value.raison


@pytest.mark.parametrize("nom, data, raison", [
    ("notes.txt", b"du texte", "Format non géré"),
    ("feuille.doc", b"ancien format", "Format non géré"),
    ("faux.docx", b"pas un fichier zip", "Word"),
    ("faux.pdf", b"pas un pdf", "PDF"),
    ("enorme.pdf", b"x" * (TAILLE_MAX + 1), "trop gros"),
], ids=["txt", "doc", "docx-illisible", "pdf-illisible", "trop-gros"])
def test_fichiers_refuses(nom, data, raison):
    with pytest.raises(UnsupportedFile) as erreur:
        analyser_fichier(nom, data)
    assert raison in erreur.value.raison
```

- [ ] **Step 2: Vérifier qu'ils échouent**

Run: `python -m pytest tests/test_import_importer.py -q`
Expected: erreur de collecte `ModuleNotFoundError: No module named 'tools.import_chants.importer'`.

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/importer.py` :

```python
"""Point d'entrée de l'import : un fichier téléversé (nom + contenu) → les chants reconnus."""

from tools.import_chants.extract_docx import extract_docx
from tools.import_chants.extract_pdf import extract_pdf
from tools.import_chants.modeles import ParseResult, UnsupportedFile
from tools.import_chants.parse import parse_lines

TAILLE_MAX = 10 * 1024 * 1024  # 10 Mo par fichier


def analyser_fichier(nom_fichier: str, data: bytes) -> ParseResult:
    """
    Lit un .docx ou un .pdf en mémoire (rien n'est écrit sur le disque) et en extrait les chants.
    Lève UnsupportedFile (avec la raison, affichable) pour une extension non gérée, un fichier trop
    gros, illisible, une partition ou un PDF sans texte.
    """
    nom = nom_fichier.lower()
    if len(data) > TAILLE_MAX:
        raise UnsupportedFile(f"Fichier trop gros (plus de {TAILLE_MAX // (1024 * 1024)} Mo)")
    if nom.endswith(".docx"):
        lignes = extract_docx(data)
    elif nom.endswith(".pdf"):
        lignes = extract_pdf(data)
    else:
        raise UnsupportedFile("Format non géré : seuls les fichiers .docx et .pdf sont acceptés")
    return parse_lines(lignes, nom_fichier)
```

- [ ] **Step 4: Vérifier qu'ils passent**

Run: `python -m pytest tests/test_import_importer.py -q`
Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/importer.py tests/test_import_importer.py
git commit -m "feat: point d'entrée de l'import (extension, taille, lecture en mémoire)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Test « corpus » local et documentation

**Files:**
- Create: `tests/test_import_corpus.py`, `hardprompts/import_rules.md`
- Modify: `README.md`, `ARBORESCENCE.md`, `docs/superpowers/specs/2026-10-03-import-chants-design.md`

**Interfaces:**
- Consumes: `analyser_fichier`, `UnsupportedFile` (Tasks 1, 5) ; `MomentLiturgique`, `TypeSection`
- Produces: un test qui parcourt les vrais fichiers de la paroisse **s'ils sont présents** (variable `CHANTS_CORPUS`, défaut `G:\Mon Drive\Chants`) et se saute sinon ; la documentation de l'import

- [ ] **Step 1: Test « corpus »**

Créer `tests/test_import_corpus.py` :

```python
"""
Test « corpus » : les vrais fichiers de la paroisse. Il ne tourne que sur le poste qui les possède
(le dépôt est public : aucun de ces fichiers, ni leurs paroles, n'est versionné).

    CHANTS_CORPUS             dossier des fichiers (défaut : G:\\Mon Drive\\Chants)
    CHANTS_FEUILLE_REFERENCE  feuille de référence « Dimanche 04 octobre 2026.docx »
                              (défaut : le dossier Téléchargements)
"""

import os
from pathlib import Path

import pytest

from context.models import MomentLiturgique as M
from context.models import TypeSection
from tools.import_chants.importer import analyser_fichier
from tools.import_chants.modeles import UnsupportedFile

CORPUS = Path(os.environ.get("CHANTS_CORPUS", r"G:\Mon Drive\Chants"))
FEUILLE = Path(os.environ.get(
    "CHANTS_FEUILLE_REFERENCE", str(Path.home() / "Downloads" / "Dimanche 04 octobre 2026.docx")))

FICHIERS = sorted(p for p in CORPUS.glob("*") if p.suffix.lower() in (".docx", ".pdf")) if CORPUS.is_dir() else []
# Partitions (police de notation) et scans, qui doivent être refusés
REFUSES = {
    "agneau messe de la joie.pdf", "alleluia messe de la joie.pdf", "anamnese messe de la joie.pdf",
    "gloire a dieu messe de la joie.pdf", "je n ai que ma priere.pdf", "kirie messe de la joie.pdf",
    "pu messe de la joie.pdf", "sanctus messe de la joie.pdf", "que-vienne-ton-regne.pdf",
    "hosanna exo.pdf", "c est ton sang qui purifie.pdf",
}

corpus_local = pytest.mark.skipif(not FICHIERS, reason="corpus local absent")


@corpus_local
@pytest.mark.parametrize("chemin", FICHIERS, ids=[p.name for p in FICHIERS])
def test_aucun_fichier_ne_fait_planter_l_analyse(chemin):
    try:
        resultat = analyser_fichier(chemin.name, chemin.read_bytes())
    except UnsupportedFile:
        assert chemin.suffix.lower() == ".pdf", "un fichier Word ne doit jamais être refusé"
        return
    for chant in resultat.chants:
        assert chant.titre.strip() and chant.structure
        assert set(chant.ordre) <= {s.id for s in chant.structure}


@corpus_local
def test_partitions_et_scans_sont_refuses():
    presents = [p for p in FICHIERS if p.name.lower() in REFUSES]
    assert presents, "aucune partition trouvée dans le corpus"
    for chemin in presents:
        with pytest.raises(UnsupportedFile):
            analyser_fichier(chemin.name, chemin.read_bytes())


@pytest.mark.skipif(not FEUILLE.is_file(), reason="feuille de référence absente")
def test_feuille_de_reference_du_4_octobre_2026():
    resultat = analyser_fichier(FEUILLE.name, FEUILLE.read_bytes())
    assert [c.moment for c in resultat.chants] == [
        M.ENTREE, M.PARDON, M.GLOIRE, M.PSAUME, M.ALLELUIA, M.PU, M.SANCTUS, M.ANAMNESE, M.AGNEAU, M.COMMUNION]
    avec_refrain = [c.moment for c in resultat.chants
                    if any(s.type is TypeSection.REFRAIN for s in c.structure)]
    assert avec_refrain == [M.ENTREE, M.PARDON, M.GLOIRE, M.PSAUME, M.SANCTUS, M.COMMUNION]
    assert any("Sortie" in n for n in resultat.notes)  # le renvoi « VOIR CHANT D'ENTREE » n'est pas un chant
    entree = resultat.chants[0]
    assert entree.ordre == ["R", "1", "R", "2", "R", "P", "R"]
```

Run (sur le poste qui possède les fichiers) : `python -m pytest tests/test_import_corpus.py -q`
Expected: `51 passed` (un test par fichier du corpus + 2).

Run (sans le corpus) : `CHANTS_CORPUS=/inexistant CHANTS_FEUILLE_REFERENCE=/inexistant.docx python -m pytest tests/test_import_corpus.py -q`
Expected: `3 skipped`, aucun échec.

- [ ] **Step 2: Règles d'analyse documentées**

Créer `hardprompts/import_rules.md` :

```markdown
# Règles de l'import de chants (tools/import_chants)

Fichiers acceptés : `.docx` et `.pdf` exportés de Word (texte sélectionnable), 10 Mo au plus, lus en
mémoire. Partitions (police de notation, texte en syllabes) et PDF-images : refusés avec une raison.

- **Lignes** : un paragraphe est éclaté aux retours à la ligne et aux doubles espaces (fins de vers) ; une
  ligne est grasse / italique / soulignée si la moitié de ses caractères le sont. PDF : « faux gras »
  (texte imprimé 3 fois) reconnu comme du gras ; lignes vides déduites des écarts verticaux.
- **Chants d'une feuille** : un en-tête est une ligne en gras et soulignée (ou `Title:` / `Artist:`, ou un
  mot du vocabulaire en gras seul sur son bloc). Le recueil est lu entre parenthèses, après 3 espaces, après
  le mot-clé du moment, ou sur la ligne suivante. L'en-tête de la feuille (date, église) et les renvois
  (`VOIR CHANT D'ENTREE`) ne sont pas des chants et sont signalés.
- **Sections** : étiquettes `1.`, `Couplet 2`, `Pont :`, `Refrain` ; sinon un bloc par ligne vide.
- **Refrain** : bloc entièrement en gras (à défaut en italique), ou bloc répété ; tout en gras ou rien de
  marqué : pas de refrain et un avertissement. Psaume : seul le refrain en gras est gardé.
- **Ordre chanté** : refrain répété dans le document → ordre du document ; sinon `compute_ordre`.
- **Titres** : titre explicite (`Title:` ou ligne en majuscules sous l'en-tête) ; chant seul : nom du
  fichier ; ordinaire (pardon, gloire…) : « Pardon – Lyon centre 4 » ; sinon début du premier refrain.
- Les paroles ne sont jamais corrigées ; seuls les espaces et les reprises `2x` / `bis` sont retirés.
```

- [ ] **Step 3: README, arborescence et spec**

Dans `README.md`, dans le bloc « Structure du projet », remplacer la ligne :

```
├── tools/              # API AELF, générateur PPTX, base chants
```

par :

```
├── tools/              # API AELF, générateur PPTX, base chants, import Word/PDF (tools/import_chants/)
```

Dans `ARBORESCENCE.md`, sous `tools/`, ajouter avant la ligne `│   └── db_handler.py` :

```
│   ├── import_chants/        # Lecture et analyse de feuilles de messe et de chants (Word / PDF)
```

Dans la spec `docs/superpowers/specs/2026-10-03-import-chants-design.md`, ajouter juste avant le titre `## 7. PowerPoint` :

```markdown
### Précisions apportées en livraison 2

- Modules : le paquet contient aussi `modeles.py` (types), `lignes.py` (caractères → lignes, commun aux deux
  extracteurs) et `importer.py` (point d'entrée `analyser_fichier`) ; `dedupe.py` reste en livraison 3.
- Étiquettes de section : `1.`, `1)`, `Couplet 2`, `Pont :`, `Refrain`, `R/` ; une étiquette soulignée n'est
  jamais un titre de chant.
- Vocabulaire des en-têtes élargi : `Gloria`, `Agnus (Dei)`, `Kyrie`, `Evangile` / `Acclamation` (→ alléluia),
  `Prière(s) universelle(s)`, préfixe `Chant de …`.
- Soulignement PDF évalué par caractère (milieu du caractère sur un trait fin sous sa ligne de base), puis par
  ligne avec le seuil de la moitié.
- Titre tiré d'un vers : coupé à la première ponctuation, sans mot-outil à la fin.
- Limites : les tableaux et zones de texte Word ne sont pas lus ; un vers PDF replié sur deux lignes est
  lu comme deux lignes.
```

- [ ] **Step 4: Vérification finale**

Run: `python -m pytest tests -q`
Expected: tous les tests passent.

- [ ] **Step 5: Commit**

```bash
git add tests/test_import_corpus.py hardprompts/import_rules.md README.md ARBORESCENCE.md docs/superpowers/specs/2026-10-03-import-chants-design.md
git commit -m "test: test corpus local de l'import ; docs: règles d'analyse et précisions de la spec" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Validation du code de ce plan

Le code des tâches 1 à 5 et leurs tests ont été appliqués à une copie jetable du dépôt (`main` après la livraison 1) :

- 67 nouveaux tests passent, 226 en tout avec la suite existante et le test « corpus » (51 tests sur le poste du développeur).
- **Test de mutation** : douze règles cassées volontairement une à une (faux gras, lignes vides PDF, seuil de gras, coupure des textes courts, étiquette `Couplet N`, détection du gras, ordre par défaut, psaume, reprises `2x` et `bis`, renvois, gras hérité du style) : chaque casse fait échouer au moins un test. Cette vérification a révélé un défaut réel (`Prière universelle (bis)` donnait « (bis) » comme recueil), corrigé dans le code de ce plan.
- **Corpus réel** (49 fichiers du dossier de la paroisse + la feuille du 4 octobre) : 39 analysés (181 chants), 11 refusés (8 partitions, 2 PDF-images, 1 partition de plus), **aucun plantage**, et chaque chant a un titre, au moins une section et un ordre cohérent. La feuille du 4 octobre donne 10 chants avec leurs moments, refrains et l'ordre `R 1 R 2 R P R` pour l'entrée ; `Sortie` est signalée comme renvoi.

## Auto-revue (spec ↔ plan)

| Exigence (spec §6, §9, §10 étape 2) | Tâche |
|---|---|
| Préparation des lignes : retours à la ligne, doubles espaces, `clean_spaces`, suffixe `2x` | 1, 4 |
| Type de fichier : feuille de messe ou chant seul (titre = nom du fichier) | 4 |
| En-têtes : `Title:`/`Artist:`, gras + souligné, titre en majuscules sous l'en-tête ; en-tête de feuille | 4 |
| Titre proposé (explicite, ordinaires « Pardon – recueil », début du refrain) | 4 |
| Sections, étiquettes, refrain (gras, italique, répété, avertissements), psaume, renvois, ordre chanté | 4 |
| PDF : gras, faux gras, soulignement, lignes vides ; rejet des partitions et images | 3 |
| Sûreté : `.docx` / `.pdf`, 10 Mo, lecture en mémoire | 5 |
| Tests sur documents fabriqués (Word et PDF) ; test « corpus » local ; aucune parole réelle versionnée | 2, 3, 4, 6 |
| Dépendances `python-docx` et `PyMuPDF` | 1 |

Hors de cette livraison : écran d'import, doublons, écriture en base (livraison 3).

## Limites connues

- Un fichier sans aucune mise en forme (ni gras, ni soulignement) est découpé en blocs sans refrain, avec l'avertissement « Aucun refrain détecté » : à corriger à l'écran de vérification.
- Titre d'un chant sans titre explicite : début de son premier refrain ou nom du fichier ; à relire. Un titre en majuscules devient « Gloire a dieu » (première lettre seule en capitale).
- Les tableaux et zones de texte Word ne sont pas lus ; un vers PDF replié sur deux lignes est lu comme deux lignes.
- Le recueil est reconnu par sa forme (court, sans ponctuation) : un en-tête atypique peut donner un recueil approximatif.
