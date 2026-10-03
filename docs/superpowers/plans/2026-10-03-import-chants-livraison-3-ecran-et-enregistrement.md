# Import de chants — livraison 3 : écran d'import et enregistrement — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter la page « 📥 Importer des chants » : dépôt de fichiers Word/PDF, vérification chant par chant (type des sections, ordre chanté, doublons), import dans la bibliothèque SQLite avec récapitulatif.

**Architecture:** Trois modules purs et testés seuls (`dedupe.py` : doublons ; `brouillon.py` : édition des sections et de l'ordre, conversion en `Chant` ; `enregistrer.py` : écriture en base selon la décision prise pour chaque doublon) et un module Streamlit (`ecran.py`, dans `tools/import_chants/` pour que l'image Docker, qui ne copie que `tools/`, le contienne). L'analyse (livraisons 1 et 2) est inchangée ; l'écran affiche ce qu'elle produit et le laisse corriger. Avant d'ajouter l'écran, le câblage « chant de la bibliothèque → blocs de la messe → PowerPoint » est verrouillé par un test de bout en bout et le générateur est rendu robuste.

**Tech Stack:** Python 3.11, Streamlit 1.55 (AppTest pour les tests d'écran), SQLite, python-pptx, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-import-chants-design.md` (§8 écran, §9 tests, §10 livraison 3). Plans précédents : `docs/superpowers/plans/2026-10-03-import-chants-livraison-1-donnees-et-pptx.md`, `…-livraison-2-extraction-et-analyse.md`.

## Global Constraints

- Code, commentaires, docstrings, noms de tests et textes de l'interface en **français**.
- **Aucune parole réelle** dans le dépôt public : tests avec des textes inventés.
- Écran (spec §8) : dépôt de plusieurs fichiers, fichiers refusés listés avec leur raison sans bloquer les autres ; une carte par chant, regroupées par fichier, avec case « Importer » (cochée), badge **nouveau** / **déjà présent (identique)** / **déjà présent (différent)**, titre, moments (liste), recueil modifiables, sections avec type (Refrain / Couplet / Pont) et zone de texte, case « Répéter le refrain » (cochée), ordre résultant affiché (`R · 1 · R · 2 · R`) et modifiable, avertissement « aucun refrain détecté », notes ; bouton « Importer N chants » puis récapitulatif (ajoutés, remplacés, ignorés).
- Doublons (spec §8) : clé = titre normalisé (casse, accents, espaces ignorés) + recueil ; texte identique : ignoré automatiquement ; texte différent : **Remplacer** (ancien et nouveau texte affichés), **Ignorer** (défaut) ou **Ajouter quand même**.
- Les paroles ne sont jamais corrigées (spec §2). Édition de la structure dans la page « Bibliothèque » : hors périmètre (seul l'écran d'import l'édite).
- Un chant sans `structure` reste valide ; la base existante est conservée (aucune migration dans cette livraison : `SCHEMA_VERSION` reste 1).
- Les tests ne touchent jamais la vraie bibliothèque (`tests/conftest.py` fixe `DATA_DIR` et `OUTPUT_DIR` sur des dossiers temporaires).
- Messages de commit : `type: description` en français ; chaque commit se termine par la ligne exacte `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Baseline avant ce plan : 403 tests passent (avec le corpus local), 352 + 3 sautés sans.

## Structure des fichiers

| Fichier | Rôle | Tâche |
|---|---|---|
| `tools/pptx_generator.py` (modifié) | clé `ordre_chant`, repli sur l'ordre calculé puis sur les paroles | 1 |
| `app.py` (modifié) | clé `ordre_chant`, page Bibliothèque (recueil, structure, avertissement), entrée de menu « 📥 Importer des chants » | 1, 5 |
| `tools/import_chants/dedupe.py` | `Doublon`, `normaliser`, `cle_chant`, `trouver_doublon` | 2 |
| `tools/import_chants/brouillon.py` | `SectionEditee`, renumérotation, ordre par défaut / depuis le texte, `chant_depuis_brouillon` | 3 |
| `tools/import_chants/enregistrer.py` | `Action`, `Decision`, `Recapitulatif`, `importer_chants` | 4 |
| `tools/import_chants/ecran.py` | `afficher_import()` (Streamlit) | 5 |
| `.streamlit/config.toml`, `Dockerfile`, `README.md`, `ARBORESCENCE.md`, `hardprompts/import_rules.md`, spec | taille de dépôt 10 Mo, notes de déploiement, précisions | 6 |

---

### Task 1: Générateur robuste et câblage bibliothèque → PowerPoint verrouillé

**Files:**
- Create: `tests/test_app_generation.py`, `tests/test_app_bibliotheque.py`
- Modify: `tools/pptx_generator.py` (`_chant_pages`), `tests/test_pptx_generator.py`, `app.py`

**Interfaces:**
- Consumes: `generate_pptx(blocs, out)`, `create_chant`, `init_db`, `search_chants`, `delete_chant` (existants).
- Produces: les blocs de chant passés à `generate_pptx` portent l'ordre chanté sous la clé **`ordre_chant`** (l'ancienne clé `ordre` entrait en collision avec l'index `ordre` des blocs de l'application) ; un chant structuré dont l'ordre ne désigne aucune section est lu avec l'ordre calculé, puis, en dernier recours, avec ses paroles à plat.

- [ ] **Step 1: Verrouiller le comportement actuel par un test de bout en bout (il doit déjà passer)**

Créer `tests/test_app_generation.py` :

```python
"""Test de bout en bout de la page « Générer une messe » : un chant structuré de la bibliothèque, ajouté
aux blocs, ressort dans le PowerPoint avec son refrain en gras et dans l'ordre chanté."""

import io
from pathlib import Path

from pptx import Presentation
from streamlit.testing.v1 import AppTest

from context.models import Chant, LectureLiturgique, MomentLiturgique, SectionChant, TypeSection, TypeLecture
from tools.db_handler import create_chant, init_db

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def _chant_structure() -> int:
    init_db()
    return create_chant(Chant(
        titre="Chant de bout en bout",
        paroles="Refrain inventé de bout en bout\n\nPremier couplet inventé",
        moments=[MomentLiturgique.ENTREE],
        structure=[
            SectionChant("R", TypeSection.REFRAIN, ["Refrain inventé de bout en bout"]),
            SectionChant("1", TypeSection.COUPLET, ["Premier couplet inventé"]),
        ],
        ordre=["R", "1", "R"],
    ))


def _lignes_du_pptx(octets: bytes) -> list[tuple[str, bool]]:
    """(texte, gras) de chaque ligne du corps de chaque diapositive."""
    lignes = []
    for diapo in Presentation(io.BytesIO(octets)).slides:
        zones = [s for s in diapo.shapes if s.has_text_frame]
        for paragraphe in zones[-1].text_frame.paragraphs:
            texte = "".join(r.text for r in paragraphe.runs)
            if texte:
                lignes.append((texte, bool(paragraphe.runs[0].font.bold)))
    return lignes


def test_chant_structure_ajoute_a_la_messe_sort_en_gras_dans_l_ordre_chante():
    _chant_structure()
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.session_state["aelf_data"] = {
        "informations": {"jour_liturgique_nom": "Jour de test"},
        "lectures": [LectureLiturgique(TypeLecture.EVANGILE, "Jn 1", "Titre", "Intro", "Contenu inventé")],
    }
    at.run()
    assert not at.exception

    selecteur = next(s for s in at.selectbox if s.key == "chant_select")
    selecteur.set_value(selecteur.options.index("Chant de bout en bout"))
    next(b for b in at.button if b.key == "add_chant").click().run()
    assert not at.exception
    assert any(b.get("type") == "chant" for b in at.session_state["blocs"])

    next(b for b in at.button if b.label == "📥 Générer et télécharger PPTX").click().run()
    assert not at.exception
    lignes = _lignes_du_pptx(at.session_state["pptx_bytes"])
    chant = [l for l in lignes if l[0] in ("Refrain inventé de bout en bout", "Premier couplet inventé")]
    assert chant == [
        ("Refrain inventé de bout en bout", True),
        ("Premier couplet inventé", False),
        ("Refrain inventé de bout en bout", True),
    ]
```

Run: `python -m pytest tests/test_app_generation.py -v`
Expected: PASS (1 passed). Ce test décrit le comportement existant ; il sert de filet pour le changement de clé qui suit. S'il échoue, STOP : le câblage actuel est cassé, à signaler.

- [ ] **Step 2: Écrire les tests qui échouent (générateur)**

Dans `tests/test_pptx_generator.py`, remplacer la ligne du test `test_structured_chant_follows_explicit_order` :

```python
    bloc = {"type": "chant", "titre": "Fleuve", "paroles": "", "structure": SECTIONS, "ordre": ["1", "R"]}
```
par :
```python
    bloc = {"type": "chant", "titre": "Fleuve", "paroles": "", "structure": SECTIONS, "ordre_chant": ["1", "R"]}
```
puis ajouter à la fin du fichier :

```python


def test_ordre_qui_ne_designe_aucune_section_retombe_sur_l_ordre_calcule(tmp_path):
    out = tmp_path / "c.pptx"
    bloc = {"type": "chant", "titre": "Fleuve", "paroles": "inutile", "structure": SECTIONS, "ordre_chant": ["X", "Y"]}
    generate_pptx([bloc], out)
    assert _body_lines(out) == _expected(["R", "1", "R", "2", "R"])


def test_structure_sans_aucune_ligne_retombe_sur_les_paroles(tmp_path):
    out = tmp_path / "c.pptx"
    structure = [{"id": "1", "type": "couplet", "lignes": []}]
    bloc = {"type": "chant", "titre": "Vide", "paroles": "Premier vers\nSecond vers", "structure": structure, "ordre_chant": ["1"]}
    generate_pptx([bloc], out)
    assert _body_lines(out) == [("Premier vers", False), ("Second vers", False)]
```

Run: `python -m pytest tests/test_pptx_generator.py -q`
Expected: FAIL (au moins `test_structured_chant_follows_explicit_order` : l'ordre `["1", "R"]` n'est plus lu sous la clé `ordre_chant`, et les deux nouveaux tests).

- [ ] **Step 3: Modifier le générateur**

Dans `tools/pptx_generator.py`, remplacer ce bloc de `_chant_pages` :

```python
    sections = sections_from_dicts(bloc.get("structure") or [])
    if not sections:
        return split_text_for_slides(bloc.get("paroles", ""), mode="chant", **split_kwargs)
    ordre = bloc.get("ordre") or compute_ordre(sections)
    return split_lines_for_slides(expand_lines(sections, ordre), **split_kwargs)
```
par :
```python
    sections = sections_from_dicts(bloc.get("structure") or [])
    # Ordre mémorisé, puis ordre calculé s'il ne désigne aucune section existante ; en dernier recours,
    # les paroles à plat : un chant ne doit jamais sortir vide à cause d'une structure incohérente.
    lines = expand_lines(sections, bloc.get("ordre_chant") or compute_ordre(sections)) if sections else []
    if sections and not lines:
        lines = expand_lines(sections, compute_ordre(sections))
    if not lines:
        return split_text_for_slides(bloc.get("paroles", ""), mode="chant", **split_kwargs)
    return split_lines_for_slides(lines, **split_kwargs)
```

Dans `app.py`, remplacer `"ordre": b.get("ordre_chant", []),` par `"ordre_chant": b.get("ordre_chant", []),`.

Run: `python -m pytest tests/test_pptx_generator.py tests/test_app_generation.py -q`
Expected: PASS.

- [ ] **Step 4: Écrire les tests de la page Bibliothèque (ils échouent)**

Créer `tests/test_app_bibliotheque.py` :

```python
"""Page « Bibliothèque de chants » : recueil et structure visibles, avertissement avant de perdre la structure."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from context.models import Chant, SectionChant, TypeSection
from tools.db_handler import create_chant, delete_chant, init_db, search_chants

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def bibliotheque_vide():
    init_db()
    for chant in search_chants():
        delete_chant(chant.id)


def _page() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    return at.sidebar.radio[0].set_value("📚 Bibliothèque de chants").run()


def _chant(structure: bool) -> None:
    create_chant(Chant(
        titre="Chant de la bibliothèque", paroles="Refrain inventé\n\nCouplet inventé", recueil="Lyon centre 4",
        structure=[SectionChant("R", TypeSection.REFRAIN, ["Refrain inventé"]),
                   SectionChant("1", TypeSection.COUPLET, ["Couplet inventé"])] if structure else [],
        ordre=["R", "1", "R"] if structure else [],
    ))


def test_la_recherche_montre_le_recueil_et_la_structure():
    _chant(structure=True)
    at = _page()
    textes = " ".join([w.value for w in at.markdown] + [c.value for c in at.caption])
    assert "Lyon centre 4" in textes and "R · 1 · R" in textes


def test_modifier_un_chant_structure_avertit_avant_la_perte_de_la_structure():
    _chant(structure=True)
    assert any("supprime la structure" in c.value for c in _page().caption)


def test_modifier_un_chant_sans_structure_n_avertit_pas():
    _chant(structure=False)
    assert not any("supprime la structure" in c.value for c in _page().caption)
```

Run: `python -m pytest tests/test_app_bibliotheque.py -q`
Expected: FAIL (le recueil, la structure et l'avertissement ne sont pas affichés).

- [ ] **Step 5: Modifier la page Bibliothèque (`app.py`)**

Remplacer :
```python
                st.write("Réf:", c.reference or "-")
```
par :
```python
                st.write("Réf:", c.reference or "-")
                if c.recueil:
                    st.write("Recueil:", c.recueil)
                if c.structure:
                    st.caption("Structure : " + " · ".join(c.ordre or [s.id for s in c.structure]) + " (refrain en gras)")
```
et remplacer :
```python
                        titre = st.text_input("Titre", value=chant.titre)
                        paroles = st.text_area("Paroles", value=chant.paroles)
```
par :
```python
                        titre = st.text_input("Titre", value=chant.titre)
                        if chant.structure:
                            st.caption("⚠️ Modifier les paroles supprime la structure (refrain en gras, ordre chanté).")
                        paroles = st.text_area("Paroles", value=chant.paroles)
```

Run: `python -m pytest tests -q -W error`
Expected: tout passe (403 + 2 tests de générateur + 1 de bout en bout + 3 de bibliothèque = 409 avec le corpus).

- [ ] **Step 6: Preuve par mutation, puis commit**

Casser tour à tour : (a) la lecture de `ordre_chant` dans `_chant_pages` ; (b) le repli sur l'ordre calculé ; (c) le repli sur les paroles ; (d) l'avertissement de la page Bibliothèque ; chaque casse doit faire échouer au moins un test, puis restaurer.

```bash
git add tools/pptx_generator.py app.py tests/test_pptx_generator.py tests/test_app_generation.py tests/test_app_bibliotheque.py
git commit -m "fix: clé ordre_chant, repli du générateur sur l'ordre calculé puis les paroles ; page Bibliothèque : recueil, structure et avertissement" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Doublons

**Files:**
- Create: `tools/import_chants/dedupe.py`
- Test: `tests/test_import_dedupe.py`

**Interfaces:**
- Consumes: `Chant` (context/models.py).
- Produces: `Doublon` (`AUCUN`, `IDENTIQUE`, `DIFFERENT`) ; `ResultatDoublon(statut, existant)` ; `normaliser(texte: Optional[str]) -> str` ; `cle_chant(titre, recueil) -> str` ; `trouver_doublon(titre: str, recueil: Optional[str], paroles: str, avec_structure: bool, bibliotheque: list[Chant]) -> ResultatDoublon`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_import_dedupe.py` :

```python
"""Tests de tools/import_chants/dedupe.py : doublons de la bibliothèque."""

import pytest

from context.models import Chant, SectionChant, TypeSection
from tools.import_chants.dedupe import Doublon, cle_chant, normaliser, trouver_doublon

REFRAIN = SectionChant("R", TypeSection.REFRAIN, ["Chantons au bord du fleuve"])


def chant(titre="Venez au fleuve", recueil=None, paroles="Chantons au bord du fleuve", structure=()):
    return Chant(id=1, titre=titre, recueil=recueil, paroles=paroles, structure=list(structure))


@pytest.mark.parametrize("a, b", [
    ("Venez au Fleuve", "venez au fleuve"),
    ("Venez, au fleuve !", "VENEZ AU FLEUVE"),
    ("  Venez   au\nfleuve ", "venez au fleuve"),
    ("Étoile d’or", "etoile d'or"),
])
def test_normaliser_ignore_casse_accents_ponctuation_et_espaces(a, b):
    assert normaliser(a) == normaliser(b)


def test_normaliser_conserve_les_chiffres_et_les_mots():
    assert normaliser("Psaume 22") != normaliser("Psaume 23")
    assert normaliser(None) == ""


def test_la_cle_depend_du_titre_et_du_recueil():
    assert cle_chant("Pardon", "Lyon centre 4") != cle_chant("Pardon", "Lyon centre 2")
    assert cle_chant("Pardon", None) != cle_chant("Pardon", "Lyon centre 4")
    assert cle_chant("PARDON", " lyon  centre 4 ") == cle_chant("Pardon", "Lyon centre 4")


def test_titre_inconnu_donne_aucun():
    r = trouver_doublon("Autre chant", None, "Un texte", False, [chant()])
    assert r.statut is Doublon.AUCUN and r.existant is None


def test_bibliotheque_vide_donne_aucun():
    assert trouver_doublon("Venez au fleuve", None, "x", False, []).statut is Doublon.AUCUN


def test_titre_vide_ne_donne_jamais_un_doublon():
    assert trouver_doublon("  ", None, "x", False, [chant(titre="")]).statut is Doublon.AUCUN


def test_meme_titre_et_meme_texte_donne_identique():
    existant = chant()
    r = trouver_doublon("VENEZ AU FLEUVE", None, "Chantons, au bord du fleuve.", False, [existant])
    assert r.statut is Doublon.IDENTIQUE and r.existant is existant


def test_meme_titre_texte_different_donne_different():
    existant = chant()
    r = trouver_doublon("Venez au fleuve", None, "Un tout autre texte", False, [existant])
    assert r.statut is Doublon.DIFFERENT and r.existant is existant


def test_recueil_different_n_est_pas_un_doublon():
    r = trouver_doublon("Pardon", "Lyon centre 4", "Prends pitié", False, [chant(titre="Pardon", recueil="Lyon centre 2", paroles="Prends pitié")])
    assert r.statut is Doublon.AUCUN


def test_meme_texte_mais_import_structure_sur_chant_sans_structure_donne_different():
    # Le remplacement apporterait les refrains en gras : on ne l'ignore pas silencieusement
    r = trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", True, [chant()])
    assert r.statut is Doublon.DIFFERENT


def test_meme_texte_et_chant_existant_deja_structure_donne_identique():
    existant = chant(structure=[REFRAIN])
    assert trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", True, [existant]).statut is Doublon.IDENTIQUE


def test_meme_texte_sans_structure_des_deux_cotes_donne_identique():
    assert trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", False, [chant()]).statut is Doublon.IDENTIQUE


def test_plusieurs_chants_de_meme_cle_prefere_l_identique():
    ancien = chant(paroles="Une ancienne version")
    ancien.id = 7
    courant = chant()
    courant.id = 9
    r = trouver_doublon("Venez au fleuve", None, "Chantons au bord du fleuve", False, [ancien, courant])
    assert r.statut is Doublon.IDENTIQUE and r.existant.id == 9
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_import_dedupe.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'tools.import_chants.dedupe'`).

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/dedupe.py` :

```python
"""Doublons : un chant importé existe-t-il déjà dans la bibliothèque ? (spec §8)"""

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from context.models import Chant


class Doublon(Enum):
    AUCUN = "aucun"
    IDENTIQUE = "identique"  # même chant, même texte : rien à faire
    DIFFERENT = "different"  # même chant (titre + recueil), texte ou structure différents


@dataclass
class ResultatDoublon:
    statut: Doublon
    existant: Optional[Chant] = None


def normaliser(texte: Optional[str]) -> str:
    """Casse, accents, apostrophes, ponctuation et espaces ignorés : « Venez, au Fleuve ! » = « venez au fleuve »."""
    decompose = unicodedata.normalize("NFKD", (texte or "").replace("’", "'"))
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_accents.casefold()).split())


def cle_chant(titre: str, recueil: Optional[str]) -> str:
    """Clé d'identité d'un chant : titre normalisé + recueil normalisé."""
    return f"{normaliser(titre)}|{normaliser(recueil)}"


def trouver_doublon(
    titre: str,
    recueil: Optional[str],
    paroles: str,
    avec_structure: bool,
    bibliotheque: list[Chant],
) -> ResultatDoublon:
    """
    Compare un chant à importer à la bibliothèque. Même clé et même texte : IDENTIQUE, sauf si
    le chant existant n'a pas de structure et que l'import en apporte une (alors DIFFERENT : le
    remplacement ajoute les refrains en gras). Même clé et texte différent : DIFFERENT.
    """
    if not normaliser(titre):
        return ResultatDoublon(Doublon.AUCUN)
    cle = cle_chant(titre, recueil)
    memes = [c for c in bibliotheque if cle_chant(c.titre, c.recueil) == cle]
    if not memes:
        return ResultatDoublon(Doublon.AUCUN)
    texte = normaliser(paroles)
    for existant in memes:
        if normaliser(existant.paroles) == texte and (existant.structure or not avec_structure):
            return ResultatDoublon(Doublon.IDENTIQUE, existant)
    return ResultatDoublon(Doublon.DIFFERENT, memes[0])
```

- [ ] **Step 4: Vérifier**

Run: `python -m pytest tests/test_import_dedupe.py -q`
Expected: PASS (16 passed). Puis preuve par mutation (retirer le recueil de la clé ; ignorer la condition `existant.structure or not avec_structure` ; ne pas normaliser la ponctuation) : chaque casse fait échouer un test.

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/dedupe.py tests/test_import_dedupe.py
git commit -m "feat: détection des doublons de la bibliothèque (titre + recueil normalisés, texte identique ou différent)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Brouillon d'un chant (édition des sections et de l'ordre)

**Files:**
- Create: `tools/import_chants/brouillon.py`
- Test: `tests/test_import_brouillon.py`

**Interfaces:**
- Consumes: `ParsedSong` (modeles.py), `SectionChant`, `TypeSection`, `MomentLiturgique`, `Chant`, `compute_ordre`, `paroles_from_structure`.
- Produces: `LIBELLES_TYPE: dict[TypeSection, str]` ; `SectionEditee(type, texte)` avec `.lignes()` ; `sections_editees(chant: ParsedSong) -> list[SectionEditee]` ; `sections_depuis_edition(editees) -> list[SectionChant]` (écarte les sections vides, renumérote R/R2…, 1/2…, P/P2…) ; `ordre_initial(chant, editees, repeter: bool) -> list[str]` ; `ordre_en_texte(ordre) -> str` ; `ordre_depuis_texte(texte, sections) -> tuple[list[str], Optional[str]]` ; `chant_depuis_brouillon(titre, moments, recueil, editees, ordre_texte) -> tuple[Optional[Chant], Optional[str]]`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_import_brouillon.py` :

```python
"""Tests de tools/import_chants/brouillon.py : édition des sections et de l'ordre, conversion en Chant."""

import pytest

from context.models import MomentLiturgique as M
from context.models import SectionChant, TypeSection
from tools.import_chants.brouillon import (
    SectionEditee,
    chant_depuis_brouillon,
    ordre_depuis_texte,
    ordre_en_texte,
    ordre_initial,
    sections_depuis_edition,
    sections_editees,
)
from tools.import_chants.modeles import ParsedSong

R, C, P = TypeSection.REFRAIN, TypeSection.COUPLET, TypeSection.PONT


def chant_analyse(structure, ordre):
    return ParsedSong(titre="Venez au fleuve", moment=M.ENTREE, structure=structure, ordre=ordre)


def trois_sections():
    return [
        SectionChant("R", R, ["Chantons au bord du fleuve"]),
        SectionChant("1", C, ["Premier couplet inventé"]),
        SectionChant("2", C, ["Second couplet inventé"]),
    ]


def test_sections_editees_reprend_types_et_textes_multilignes():
    editees = sections_editees(chant_analyse(trois_sections(), []))
    assert [(e.type, e.texte) for e in editees] == [
        (R, "Chantons au bord du fleuve"), (C, "Premier couplet inventé"), (C, "Second couplet inventé"),
    ]
    assert sections_editees(chant_analyse([SectionChant("1", C, ["a", "b"])], []))[0].texte == "a\nb"


def test_renumerotation_apres_changement_de_type():
    editees = [SectionEditee(R, "Un refrain"), SectionEditee(C, "Un couplet"), SectionEditee(R, "Un autre refrain"),
               SectionEditee(P, "Un pont"), SectionEditee(C, "Un dernier couplet"), SectionEditee(P, "Un second pont")]
    assert [s.id for s in sections_depuis_edition(editees)] == ["R", "1", "R2", "P", "2", "P2"]


def test_sections_vides_ecartees_et_lignes_nettoyees():
    editees = [SectionEditee(C, "  Un vers  \n\n  Un autre vers "), SectionEditee(C, "   \n "), SectionEditee(C, "Fin")]
    sections = sections_depuis_edition(editees)
    assert [(s.id, s.lignes) for s in sections] == [("1", ["Un vers", "Un autre vers"]), ("2", ["Fin"])]


def test_ordre_initial_garde_l_ordre_du_document_quand_rien_n_a_change():
    chant = chant_analyse(trois_sections(), ["R", "1", "2", "R"])  # ordre explicite : pas R 1 R 2 R
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["R", "1", "2", "R"]


def test_ordre_initial_suit_la_renumerotation_des_couplets():
    # Document étiqueté 1. 3. : l'analyse a gardé « 3 » ; l'écran renumérote en « 2 »
    structure = [SectionChant("R", R, ["Un refrain"]), SectionChant("1", C, ["a"]), SectionChant("3", C, ["b"])]
    chant = chant_analyse(structure, ["R", "1", "R", "3", "R"])
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["R", "1", "R", "2", "R"]


def test_ordre_initial_sans_repetition_donne_l_ordre_du_document():
    chant = chant_analyse(trois_sections(), ["R", "1", "R", "2", "R"])
    assert ordre_initial(chant, sections_editees(chant), repeter=False) == ["R", "1", "2"]


def test_ordre_initial_recalcule_quand_un_type_change():
    chant = chant_analyse(trois_sections(), ["R", "1", "R", "2", "R"])
    editees = sections_editees(chant)
    editees[2].type = P
    assert ordre_initial(chant, editees, repeter=True) == ["R", "1", "R", "P", "R"]


def test_ordre_initial_recalcule_quand_une_section_est_videe():
    chant = chant_analyse(trois_sections(), ["R", "1", "2", "R"])
    editees = sections_editees(chant)
    editees[1].texte = ""
    assert ordre_initial(chant, editees, repeter=True) == ["R", "1", "R"]


def test_ordre_initial_sans_refrain_donne_l_ordre_du_document():
    structure = [SectionChant("1", C, ["a"]), SectionChant("2", C, ["b"])]
    chant = chant_analyse(structure, ["1", "2"])
    assert ordre_initial(chant, sections_editees(chant), repeter=True) == ["1", "2"]


def test_ordre_en_texte_et_retour():
    sections = trois_sections()
    assert ordre_en_texte(["R", "1", "R", "2", "R"]) == "R · 1 · R · 2 · R"
    assert ordre_depuis_texte("R · 1 · R · 2 · R", sections) == (["R", "1", "R", "2", "R"], None)


@pytest.mark.parametrize("texte", ["R 1 R 2", "r, 1, R, 2", "R;1;R;2", "  R   1 R 2  "])
def test_ordre_depuis_texte_accepte_plusieurs_separateurs_et_la_casse(texte):
    assert ordre_depuis_texte(texte, trois_sections()) == (["R", "1", "R", "2"], None)


def test_ordre_depuis_texte_refuse_une_section_inconnue():
    ordre, erreur = ordre_depuis_texte("R 1 9", trois_sections())
    assert ordre == [] and "9" in erreur


def test_ordre_depuis_texte_refuse_un_ordre_vide():
    assert ordre_depuis_texte("  ·  ", trois_sections())[1] == "L'ordre chanté est vide"


def test_chant_depuis_brouillon_complet():
    editees = [SectionEditee(R, "Chantons au bord du fleuve"), SectionEditee(C, "Premier couplet inventé")]
    chant, erreur = chant_depuis_brouillon("  Venez au fleuve ", [M.ENTREE, M.COMMUNION], " Lyon centre 4 ", editees, "R · 1 · R")
    assert erreur is None
    assert (chant.titre, chant.recueil, chant.moments, chant.ordre) == ("Venez au fleuve", "Lyon centre 4", [M.ENTREE, M.COMMUNION], ["R", "1", "R"])
    assert chant.paroles == "Chantons au bord du fleuve\n\nPremier couplet inventé"
    assert [(s.id, s.type) for s in chant.structure] == [("R", R), ("1", C)]


def test_chant_depuis_brouillon_valeurs_par_defaut():
    chant, _ = chant_depuis_brouillon("Un chant", [], "  ", [SectionEditee(C, "Un vers")], "1")
    assert chant.moments == [M.AUTRE] and chant.recueil is None


@pytest.mark.parametrize("titre, editees, ordre, attendu", [
    ("  ", [SectionEditee(C, "Un vers")], "1", "titre"),
    ("Un chant", [SectionEditee(C, "  ")], "1", "aucune parole"),
    ("Un chant", [SectionEditee(C, "Un vers")], "1 7", "inconnue"),
    ("Un chant", [SectionEditee(C, "Un vers")], "", "vide"),
], ids=["titre-vide", "sans-paroles", "ordre-inconnu", "ordre-vide"])
def test_chant_depuis_brouillon_refuse_un_brouillon_inutilisable(titre, editees, ordre, attendu):
    chant, erreur = chant_depuis_brouillon(titre, [M.ENTREE], None, editees, ordre)
    assert chant is None and attendu in erreur
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_import_brouillon.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'tools.import_chants.brouillon'`).

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/brouillon.py` :

```python
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
```

- [ ] **Step 4: Vérifier**

Run: `python -m pytest tests/test_import_brouillon.py -q`
Expected: PASS (22 passed). Preuve par mutation : retirer la renumérotation ; garder l'ordre de l'analyse même quand un type a changé ; ne pas écarter les sections vides ; refuser de reconnaître la casse des identifiants dans l'ordre ; moments par défaut `AUTRE` : chaque casse fait échouer un test.

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/brouillon.py tests/test_import_brouillon.py
git commit -m "feat: brouillon d'un chant à importer (sections éditables, renumérotation, ordre chanté, conversion en Chant)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Enregistrement dans la bibliothèque

**Files:**
- Create: `tools/import_chants/enregistrer.py`
- Test: `tests/test_import_enregistrer.py`

**Interfaces:**
- Consumes: `create_chant`, `update_chant`, `search_chants`, `init_db` (tools/db_handler.py, avec `db_path` optionnel) ; `trouver_doublon`, `Doublon` (Task 2).
- Produces: `Action` (`IGNORER`, `REMPLACER`, `AJOUTER`) ; `Decision(chant: Chant, action: Action = IGNORER, statut_vu: Doublon = AUCUN)` ; `Recapitulatif(ajoutes, remplaces, ignores, erreurs)` (listes de chaînes) ; `importer_chants(decisions: list[Decision], db_path: Optional[Path] = None) -> Recapitulatif`.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_import_enregistrer.py` :

```python
"""Tests de tools/import_chants/enregistrer.py : écriture en base et décision par doublon."""

import pytest

from context.models import Chant, MomentLiturgique as M, SectionChant, TypeSection
from tools.db_handler import create_chant, get_chant, init_db, search_chants
from tools.import_chants.dedupe import Doublon
from tools.import_chants.enregistrer import Action, Decision, importer_chants

R, C = TypeSection.REFRAIN, TypeSection.COUPLET


@pytest.fixture
def db(tmp_path):
    chemin = tmp_path / "chants.db"
    init_db(chemin)
    return chemin


def nouveau(titre="Venez au fleuve", paroles="Chantons au bord du fleuve\n\nPremier couplet inventé", recueil=None):
    return Chant(
        titre=titre, paroles=paroles, recueil=recueil, moments=[M.ENTREE],
        structure=[SectionChant("R", R, ["Chantons au bord du fleuve"]), SectionChant("1", C, ["Premier couplet inventé"])],
        ordre=["R", "1", "R"],
    )


def test_chant_nouveau_est_ajoute_avec_structure_ordre_et_moments(db):
    recap = importer_chants([Decision(nouveau(recueil="Lyon centre 4"))], db)
    assert recap.ajoutes == ["Venez au fleuve"] and not recap.erreurs
    [enregistre] = search_chants(db_path=db)
    assert enregistre.recueil == "Lyon centre 4"
    assert enregistre.ordre == ["R", "1", "R"] and [s.id for s in enregistre.structure] == ["R", "1"]
    assert enregistre.moments == [M.ENTREE]


def test_chant_identique_est_ignore_meme_si_l_utilisateur_veut_l_ajouter(db):
    create_chant(nouveau(), db)
    decision = Decision(nouveau(), Action.AJOUTER, Doublon.IDENTIQUE)
    recap = importer_chants([decision], db)
    assert recap.ajoutes == [] and "identique" in recap.ignores[0]
    assert len(search_chants(db_path=db)) == 1


def test_doublon_different_ignore_par_defaut(db):
    create_chant(nouveau(paroles="Un ancien texte"), db)
    recap = importer_chants([Decision(nouveau(), Action.IGNORER, Doublon.DIFFERENT)], db)
    assert recap.ignores and not recap.ajoutes and not recap.remplaces
    [reste] = search_chants(db_path=db)
    assert reste.paroles == "Un ancien texte"


def test_doublon_different_remplace_garde_l_identite_et_les_champs_saisis(db):
    ancien = nouveau(paroles="Un ancien texte")
    ancien.auteur, ancien.compositeur, ancien.reference, ancien.notes = "Une autrice", "Un compositeur", "B 12", "Une note"
    ancien.structure, ancien.ordre = [], []
    ancien_id = create_chant(ancien, db)
    recap = importer_chants([Decision(nouveau(recueil=None), Action.REMPLACER, Doublon.DIFFERENT)], db)
    assert recap.remplaces == ["Venez au fleuve"]
    [chant] = search_chants(db_path=db)
    assert chant.id == ancien_id
    assert chant.paroles.startswith("Chantons au bord du fleuve") and chant.ordre == ["R", "1", "R"]
    assert (chant.auteur, chant.compositeur, chant.reference, chant.notes) == ("Une autrice", "Un compositeur", "B 12", "Une note")


def test_meme_texte_sans_structure_est_remplace_pour_apporter_les_refrains(db):
    ancien = nouveau()
    ancien.structure, ancien.ordre = [], []
    create_chant(ancien, db)
    recap = importer_chants([Decision(nouveau(), Action.REMPLACER, Doublon.DIFFERENT)], db)
    assert recap.remplaces and get_chant(search_chants(db_path=db)[0].id, db).structure


def test_doublon_different_ajouter_quand_meme(db):
    create_chant(nouveau(paroles="Un ancien texte"), db)
    recap = importer_chants([Decision(nouveau(), Action.AJOUTER, Doublon.DIFFERENT)], db)
    assert recap.ajoutes == ["Venez au fleuve"]
    assert len(search_chants(db_path=db)) == 2


def test_doublon_apparu_dans_le_meme_lot_n_est_pas_ajoute_deux_fois(db):
    lot = [Decision(nouveau()), Decision(nouveau())]  # tous deux « nouveau » à l'écran
    recap = importer_chants(lot, db)
    assert recap.ajoutes == ["Venez au fleuve"] and len(recap.ignores) == 1
    assert len(search_chants(db_path=db)) == 1


def test_doublon_different_apparu_dans_le_meme_lot_est_ignore(db):
    lot = [Decision(nouveau()), Decision(nouveau(paroles="Un autre texte"))]
    recap = importer_chants(lot, db)
    assert "doublon dans cet import" in recap.ignores[0]
    assert len(search_chants(db_path=db)) == 1


def test_une_erreur_n_arrete_pas_les_autres_chants(db, monkeypatch):
    import tools.import_chants.enregistrer as module

    vrai = module.create_chant

    def create_capricieux(chant, db_path=None):
        if chant.titre == "Chant fautif":
            raise RuntimeError("base verrouillée")
        return vrai(chant, db_path)

    monkeypatch.setattr(module, "create_chant", create_capricieux)
    recap = importer_chants([Decision(nouveau("Chant fautif")), Decision(nouveau("Un bon chant"))], db)
    assert recap.ajoutes == ["Un bon chant"]
    assert len(recap.erreurs) == 1 and "Chant fautif" in recap.erreurs[0] and "base verrouillée" in recap.erreurs[0]


def test_liste_vide_ne_fait_rien(db):
    recap = importer_chants([], db)
    assert (recap.ajoutes, recap.remplaces, recap.ignores, recap.erreurs) == ([], [], [], [])
```

- [ ] **Step 2: Vérifier l'échec**

Run: `python -m pytest tests/test_import_enregistrer.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'tools.import_chants.enregistrer'`).

- [ ] **Step 3: Implémenter**

Créer `tools/import_chants/enregistrer.py` :

```python
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
    """Remplace texte, structure, ordre, recueil et moments ; garde l'identité et les champs saisis à la main."""
    existant.titre = nouveau.titre
    existant.paroles = nouveau.paroles
    existant.recueil = nouveau.recueil
    existant.structure = nouveau.structure
    existant.ordre = nouveau.ordre
    existant.moments = nouveau.moments
    update_chant(existant, db_path)
```

- [ ] **Step 4: Vérifier**

Run: `python -m pytest tests/test_import_enregistrer.py -q`
Expected: PASS (10 passed). Preuve par mutation : ne pas recalculer le doublon à l'enregistrement (utiliser seulement `statut_vu`) ; remplacer en perdant l'identité (créer au lieu de mettre à jour) ; écraser `auteur`/`reference` lors du remplacement ; laisser une exception arrêter le lot : chaque casse fait échouer un test.

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/enregistrer.py tests/test_import_enregistrer.py
git commit -m "feat: enregistrement des chants importés (ajout, remplacement, doublons ignorés, récapitulatif)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Écran « 📥 Importer des chants »

**Files:**
- Create: `tools/import_chants/ecran.py`
- Modify: `app.py` (menu et branchement)
- Test: `tests/test_app_import.py`

**Interfaces:**
- Consumes: `analyser_fichier`, `UnsupportedFile` (livraison 2) ; `trouver_doublon`, `Doublon` (T2) ; `SectionEditee`, `sections_editees`, `ordre_initial`, `ordre_en_texte`, `chant_depuis_brouillon`, `LIBELLES_TYPE` (T3) ; `Action`, `Decision`, `importer_chants` (T4) ; `search_chants`, `init_db`.
- Produces: `afficher_import() -> None`. État de session : `import_analyse` = `{"signature": tuple[(nom, taille)], "fichiers": [{"nom", "chants": list[ParsedSong], "notes": list[str], "refus": Optional[str]}]}`, `import_recap` (le `Recapitulatif` à afficher), `import_depot_n` (compteur qui change la clé du dépôt pour le vider). Clés des champs d'une carte : `imp_<n_depot>_<hash du jeu de fichiers>_<fichier>_<chant>` + `_ok`, `_titre`, `_recueil`, `_moments`, `_s<k>_type`, `_s<k>_texte`, `_repeter`, `_ordre_<signature>`, `_action` ; bouton `import_go`.

L'écran se pilote en test sans dépôt réel : AppTest ne gère pas `st.file_uploader`, donc les tests injectent `st.session_state["import_analyse"]` avec la signature d'un dépôt vide (`()`), ce qui exerce toute la vérification et l'import. La lecture d'un vrai fichier (`_analyser`) est couverte par les tests de `importer.py` (livraison 2).

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_app_import.py` :

```python
"""Tests de la page « 📥 Importer des chants » (AppTest).

Le dépôt de fichiers n'est pas pilotable par AppTest : l'analyse est injectée dans l'état de session
(`import_analyse`, avec la signature d'un dépôt vide), ce qui exerce toute la vérification et l'import."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from context.models import Chant, MomentLiturgique as M, SectionChant, TypeSection
from tests.helpers_import import L
from tools.db_handler import create_chant, delete_chant, init_db, search_chants
from tools.import_chants.parse import parse_lines

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGE = "📥 Importer des chants"

FEUILLE = [
    L("Entrée", gras=True, souligne=True),
    L("Chantons au bord du fleuve", gras=True),
    L("Premier couplet inventé", vide=True),
    L("Second couplet inventé", vide=True),
]


@pytest.fixture(autouse=True)
def bibliotheque_vide():
    init_db()
    for chant in search_chants():
        delete_chant(chant.id)


def chants_analyses(lignes=FEUILLE):
    return parse_lines(lignes, "feuille.docx").chants


def page(fichiers: list[dict]) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(PAGE).run()
    at.session_state["import_analyse"] = {"signature": (), "fichiers": fichiers}
    return at.run()


def fichier(chants=None, nom="feuille.docx", notes=(), refus=None):
    return {"nom": nom, "chants": chants if chants is not None else chants_analyses(), "notes": list(notes), "refus": refus}


def widget(elements, suffixe):
    return next(e for e in elements if e.key and e.key.endswith(suffixe))


def bouton_import(at):
    return next(b for b in at.button if b.key == "import_go")


def marqueurs(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_la_page_existe_et_s_affiche_sans_fichier():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.sidebar.radio[0].set_value(PAGE).run()
    assert not at.exception
    assert PAGE in at.sidebar.radio[0].options
    assert not [b for b in at.button if b.key == "import_go"]  # rien à importer tant qu'aucun fichier n'est analysé


def test_fichier_refuse_est_liste_avec_sa_raison_sans_bloquer_les_autres():
    at = page([fichier(nom="partition.pdf", chants=[], refus="Partition : les paroles sont mêlées aux notes"), fichier()])
    assert not at.exception
    assert any("partition.pdf" in w.value and "Partition" in w.value for w in at.warning)
    assert "🆕 nouveau" in marqueurs(at)
    assert bouton_import(at).label == "Importer 1 chant"


def test_carte_propose_titre_moment_sections_et_ordre():
    at = page([fichier()])
    assert widget(at.text_input, "_titre").value == "Chantons au bord du fleuve"
    assert widget(at.multiselect, "_moments").value == ["entree"]
    assert [widget(at.selectbox, f"_s{k}_type").value for k in range(3)] == ["refrain", "couplet", "couplet"]
    assert widget(at.checkbox, "_repeter").value is True
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · R · 2 · R"


def test_importer_ajoute_le_chant_avec_structure_et_ordre_puis_affiche_le_recapitulatif():
    at = page([fichier()])
    bouton_import(at).click().run()
    assert not at.exception
    [chant] = search_chants()
    assert chant.titre == "Chantons au bord du fleuve" and chant.moments == [M.ENTREE]
    assert chant.ordre == ["R", "1", "R", "2", "R"]
    assert [s.type for s in chant.structure] == [TypeSection.REFRAIN, TypeSection.COUPLET, TypeSection.COUPLET]
    assert any("1 ajouté(s)" in s.value for s in at.success)
    assert not at.text_input  # l'analyse est vidée après l'import : plus aucune carte à vérifier


def test_decocher_importer_n_ajoute_rien():
    at = page([fichier()])
    widget(at.checkbox, "_ok").uncheck().run()
    assert bouton_import(at).disabled
    assert search_chants() == []


def test_titre_et_recueil_modifies_sont_enregistres():
    at = page([fichier()])
    widget(at.text_input, "_titre").set_value("Venez au fleuve").run()
    widget(at.text_input, "_recueil").set_value("Lyon centre 4").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert (chant.titre, chant.recueil) == ("Venez au fleuve", "Lyon centre 4")


def test_changer_un_type_de_section_recalcule_l_ordre():
    at = page([fichier()])
    widget(at.selectbox, "_s2_type").set_value("pont").run()
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · R · P · R"
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert [s.id for s in chant.structure] == ["R", "1", "P"] and chant.ordre == ["R", "1", "R", "P", "R"]


def test_decocher_repeter_le_refrain_donne_l_ordre_du_document():
    at = page([fichier()])
    widget(at.checkbox, "_repeter").uncheck().run()
    ordre = next(t for t in at.text_input if t.label.startswith("Ordre chanté"))
    assert ordre.value == "R · 1 · 2"


def test_ordre_invalide_rend_le_chant_non_importable():
    at = page([fichier()])
    next(t for t in at.text_input if t.label.startswith("Ordre chanté")).set_value("R 1 9").run()
    assert any("inconnue" in e.value for e in at.error)
    assert bouton_import(at).disabled


def test_section_videe_n_est_pas_importee():
    at = page([fichier()])
    widget(at.text_area, "_s2_texte").set_value("").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert [s.id for s in chant.structure] == ["R", "1"] and chant.ordre == ["R", "1", "R"]


def test_notes_et_avertissements_sont_affiches():
    sans_marque = chants_analyses([L("Communion", gras=True, souligne=True), L("Un vers inventé"), L("Un autre vers inventé", vide=True)])
    at = page([fichier(chants=sans_marque, notes=["Feuille : Messe de test"])])
    assert any("refrain" in w.value.lower() for w in at.warning)
    assert any("Messe de test" in c.value for c in at.caption)


def test_doublon_identique_est_signale_et_ignore():
    create_chant(Chant(
        titre="Chantons au bord du fleuve", moments=[M.ENTREE],
        paroles="Chantons au bord du fleuve\n\nPremier couplet inventé\n\nSecond couplet inventé",
        structure=[SectionChant("R", TypeSection.REFRAIN, ["Chantons au bord du fleuve"]),
                   SectionChant("1", TypeSection.COUPLET, ["Premier couplet inventé"]),
                   SectionChant("2", TypeSection.COUPLET, ["Second couplet inventé"])],
        ordre=["R", "1", "R", "2", "R"],
    ))
    at = page([fichier()])
    assert "déjà présent (identique)" in marqueurs(at)
    assert bouton_import(at).disabled
    assert len(search_chants()) == 1


def _chant_existant_different() -> int:
    return create_chant(Chant(titre="Chantons au bord du fleuve", paroles="Un ancien texte", moments=[M.COMMUNION], auteur="Une autrice"))


def test_doublon_different_propose_trois_actions_dont_ignorer_par_defaut():
    _chant_existant_different()
    at = page([fichier()])
    assert "déjà présent (différent)" in marqueurs(at)
    action = widget(at.radio, "_action")
    assert action.value == "ignorer" and action.options == ["Ignorer (conserver l'existant)", "Remplacer", "Ajouter quand même"]
    assert any("Un ancien texte" in t.value for t in at.text)  # ancien et nouveau texte affichés
    bouton_import(at).click().run()
    [reste] = search_chants()
    assert reste.paroles == "Un ancien texte"
    assert any("1 ignoré(s)" in s.value for s in at.success)


def test_doublon_different_remplacer():
    ancien = _chant_existant_different()
    at = page([fichier()])
    widget(at.radio, "_action").set_value("remplacer").run()
    bouton_import(at).click().run()
    [chant] = search_chants()
    assert chant.id == ancien and chant.ordre == ["R", "1", "R", "2", "R"] and chant.auteur == "Une autrice"
    assert any("1 remplacé(s)" in s.value for s in at.success)


def test_doublon_different_ajouter_quand_meme():
    _chant_existant_different()
    at = page([fichier()])
    widget(at.radio, "_action").set_value("ajouter").run()
    bouton_import(at).click().run()
    assert len(search_chants()) == 2
```

Run: `python -m pytest tests/test_app_import.py -q`
Expected: FAIL (la page « 📥 Importer des chants » n'existe pas : `ModuleNotFoundError` ou option de menu absente).

- [ ] **Step 2: Créer l'écran**

Créer `tools/import_chants/ecran.py` :

```python
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
```

- [ ] **Step 3: Brancher la page dans `app.py`**

Remplacer :
```python
from tools.pptx_generator import generate_pptx
```
par :
```python
from tools.import_chants.ecran import afficher_import
from tools.pptx_generator import generate_pptx
```
Remplacer :
```python
    ["📅 Générer une messe", "📚 Bibliothèque de chants"],
```
par :
```python
    ["📅 Générer une messe", "📚 Bibliothèque de chants", "📥 Importer des chants"],
```
Remplacer :
```python
else:
    # Bibliothèque de chants
    init_db()
```
par :
```python
elif menu == "📥 Importer des chants":
    afficher_import()

else:
    # Bibliothèque de chants
    init_db()
```

- [ ] **Step 4: Vérifier**

Run: `python -m pytest tests/test_app_import.py tests/test_app_smoke.py -q` puis `python -m pytest tests -q -W error`
Expected: PASS (15 tests d'écran ; suite complète verte : 409 + 48 tests des modules purs + 15 tests d'écran = 472 avec le corpus).

Preuve par mutation (obligatoire, chaque casse doit faire échouer un test) : dans `ecran.py`, (a) ne pas recalculer l'ordre quand une section est vidée (retirer le caractère `_` de la signature) ; (b) afficher le badge « identique » mais laisser importer ; (c) action par défaut `REMPLACER` au lieu de `IGNORER` ; (d) ne pas vider l'analyse après l'import ; (e) ignorer la case « Importer » ; (f) laisser un brouillon invalide importable.

- [ ] **Step 5: Commit**

```bash
git add tools/import_chants/ecran.py app.py tests/test_app_import.py
git commit -m "feat: écran « 📥 Importer des chants » (dépôt, vérification, doublons, import, récapitulatif)" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Déploiement et documentation

**Files:**
- Create: `.streamlit/config.toml`
- Modify: `Dockerfile`, `README.md`, `ARBORESCENCE.md`, `hardprompts/import_rules.md`, `docs/superpowers/specs/2026-10-03-import-chants-design.md`

**Interfaces:** aucune (fichiers de configuration et textes).

- [ ] **Step 1: Limite de dépôt de 10 Mo**

Streamlit accepte 200 Mo par défaut ; `analyser_fichier` refuse déjà au-delà de 10 Mo, mais le fichier serait d'abord reçu en entier. Créer `.streamlit/config.toml` (lancement sans Docker) :

```toml
[server]
maxUploadSize = 10
```

Dans `Dockerfile`, après la ligne `ENV STREAMLIT_SERVER_HEADLESS=true`, ajouter :

```dockerfile
# Dépôt de fichiers (import de chants) : 10 Mo au plus, comme analyser_fichier
ENV STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10
```

Vérifier : `python -c "import streamlit.config as c; print(c.get_option('server.maxUploadSize'))"` lancé depuis la racine du dépôt affiche `10`.

- [ ] **Step 2: README**

Dans `README.md`, remplacer la phrase « La structure est renseignée par l’import de chants (bientôt disponible) ; » (dans la puce **Bibliothèque de chants**, ligne 8) par « La structure est renseignée par la page **📥 Importer des chants** ; » et ajouter, juste après cette puce, une puce :

```markdown
- **Import de chants (Word / PDF)** : déposez une feuille de messe ou un chant (`.docx`, ou `.pdf` exporté depuis Word, 10 Mo au plus). Les chants sont reconnus et séparés, les refrains détectés (en gras ou en italique, ou répétés), puis vérifiés à l'écran : titre, moments, recueil, type et texte des sections, ordre chanté, doublons de la bibliothèque (ignorer, remplacer ou ajouter). Les paroles ne sont jamais corrigées. Les partitions et les PDF-images sont refusés avec une raison.
```

Ajouter, juste avant le titre `## Structure du projet`, une section :

```markdown
## Mise à jour

- **Sauvegardez `data/chants.db`** (ou le volume `/data` de Docker) avant de déployer une nouvelle version : la base est migrée automatiquement au démarrage, sans perte, mais une copie évite tout regret.
- Depuis la prise en compte de la structure des chants, environ 17 % des chants sans structure gagnent une diapositive (les coupures se font désormais en fin de vers de préférence).
- Les dépendances `python-docx`, `PyMuPDF` et `lxml` sont installées par l'image (`pip install -r requirements.txt`) ; aucune bibliothèque système n'est requise.
- PyMuPDF est sous licence AGPL (ou licence commerciale) : sans conséquence pour une instance paroissiale ; à revoir si l'image est publiée ou l'application donnée à une autre paroisse.
```

- [ ] **Step 3: ARBORESCENCE**

Dans `ARBORESCENCE.md`, remplacer le commentaire de la ligne `│   ├── import_chants/        # Lecture et analyse de feuilles de messe et de chants (Word / PDF)` par `# Import de chants Word / PDF : lecture, analyse, vérification (ecran.py), doublons et enregistrement`.

- [ ] **Step 4: Règles documentées**

Ajouter à la fin de `hardprompts/import_rules.md` :

```markdown

## Écran d'import, doublons et enregistrement (livraison 3)

- **Doublon** : même titre et même recueil une fois normalisés (casse, accents, apostrophes, ponctuation et
  espaces ignorés). Texte identique : ignoré. Texte différent : l'utilisateur choisit Ignorer (défaut),
  Remplacer ou Ajouter quand même. Même texte mais l'import apporte une structure (refrains) que le chant
  existant n'a pas : « différent » (le remplacement ajoute les refrains en gras).
- **Remplacer** garde l'identité du chant (id) et les champs saisis à la main (auteur, compositeur,
  référence, notes) ; titre, recueil, paroles, structure et ordre sont remplacés ; les moments sont réunis
  (ceux de la bibliothèque d'abord, puis les nouveaux) : ils sont saisis à la main et absents de la comparaison.
- Les doublons sont recalculés contre la base au moment de l'enregistrement : un chant « nouveau » à l'écran
  qui est devenu un doublon dans le même lot est ignoré (« doublon dans cet import »).
- **Édition** : changer le type d'une section renumérote les identifiants (refrains R, R2 ; couplets 1, 2 ;
  ponts P, P2) et recalcule l'ordre chanté ; une section sans texte n'est pas importée ; l'ordre est
  modifiable (identifiants séparés par des espaces, `·`, virgules ; casse ignorée) et refusé s'il cite une
  section inconnue.
```

- [ ] **Step 5: Précisions dans la spec**

Dans `docs/superpowers/specs/2026-10-03-import-chants-design.md`, insérer juste avant la ligne `## 9. Tests` :

```markdown
### Précisions apportées en livraison 3

- Modules : `brouillon.py` (édition des sections et de l'ordre, conversion en `Chant`), `enregistrer.py`
  (écriture en base selon la décision prise pour chaque doublon) et `ecran.py` (Streamlit) ; `ecran.py`
  reste dans `tools/import_chants/` parce que l'image Docker ne copie que `tools/`.
- Doublon « texte identique » : le texte est comparé après normalisation (casse, accents, ponctuation,
  espaces). Si l'import apporte une structure que le chant existant n'a pas, le chant est « différent » :
  Remplacer ajoute les refrains en gras au lieu de les ignorer silencieusement.
- Remplacer garde l'id et les champs saisis à la main (auteur, compositeur, référence, notes) et réunit les moments
  (anciens puis nouveaux) au lieu de les écraser.
- Les doublons sont recalculés à l'enregistrement : un chant « nouveau » devenu doublon dans le même lot est
  ignoré et signalé ; une erreur de base sur un chant n'arrête pas les autres.
- L'ordre chanté est un champ texte modifiable (`R · 1 · R · 2 · R`) ; il est recalculé quand un type de
  section, une section vide ou « Répéter le refrain » change (une saisie manuelle de l'ordre est alors perdue).
- Dépôt limité à 10 Mo par Streamlit (`maxUploadSize`) en plus du plafond de `analyser_fichier`.
- Tests d'écran : AppTest ne pilote pas `st.file_uploader` ; l'analyse est injectée dans l'état de session.
```

- [ ] **Step 6: Vérification finale et commit**

Run: `python -m pytest tests -q -W error` puis, sans corpus, `CHANTS_CORPUS=C:\nulle-part CHANTS_FEUILLE_REFERENCE=C:\nulle-part\x.docx python -m pytest tests -q -W error`
Expected: tout passe (3 sautés sans corpus).

```bash
git add .streamlit/config.toml Dockerfile README.md ARBORESCENCE.md hardprompts/import_rules.md docs/superpowers/specs/2026-10-03-import-chants-design.md
git commit -m "docs: déploiement (dépôt 10 Mo, sauvegarde de la base), README, règles d'import, précisions de la spec" -m "Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>"
```

---

## Validation du code de ce plan

Les tâches 1 à 5 ont été appliquées à une copie jetable de `main` (après la livraison 2) : les fichiers de code et de tests ci-dessus sont ceux qui y passent. Résultat : 69 nouveaux tests (16 doublons, 22 brouillon, 10 enregistrement, 15 écran d'import, 1 de bout en bout, 3 de bibliothèque, 2 de générateur) ; la suite complète passe sur la copie avec `-W error` : 472 avec le corpus local, 421 + 3 sautés sans. Les messages `ScriptRunContext` d'AppTest sont inoffensifs.

## Auto-revue (spec ↔ plan)

| Exigence (spec §8, §9, §10 étape 3) | Tâche |
|---|---|
| Dépôt de plusieurs fichiers ; refusés listés avec leur raison sans bloquer les autres | 5 (`_analyser`, test `test_fichier_refuse_est_liste…`) |
| Carte par chant : case Importer, badge, titre / moments / recueil modifiables | 5 |
| Sections avec type et texte modifiables ; case « Répéter le refrain » ; ordre affiché et modifiable ; avertissement « aucun refrain » ; notes | 3 (logique), 5 (écran) |
| Bouton « Importer N chants », récapitulatif ajoutés / remplacés / ignorés | 4, 5 |
| Doublons : clé titre normalisé + recueil ; identique ignoré ; différent → Remplacer / Ignorer (défaut) / Ajouter ; ancien et nouveau texte affichés | 2, 4, 5 |
| Tests : doublons nouveau / identique / différent ; écran | 2, 4, 5 |
| Rappels de la revue de la livraison 1 : test AppTest « Ajouter ce chant » → export avant de toucher `app.py` ; repli du générateur ; validation de l'ordre ; clé `ordre_chant` ; avertissement avant la perte de structure | 1 (test d'abord), 3 (validation de l'ordre), 1 (clé, repli, avertissement) |
| Déploiement : sauvegarde de `chants.db`, diapo supplémentaire, taille de dépôt, licence PyMuPDF | 6 |
