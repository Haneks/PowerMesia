# Import de chants depuis Word / PDF, refrains en gras — Spécification

Date : 2026-10-03 · Statut : à valider

## 1. Objectif

Permettre de déposer une feuille de messe ou un chant (`.docx`, `.pdf` exporté depuis Word) dans
l'application pour que :

1. les chants soient **reconnus et séparés** automatiquement ;
2. ils soient **importés dans la bibliothèque** après une étape de vérification ;
3. les **refrains soient reconnus** et écrits **en gras** dans le PowerPoint, **répétés après chaque
   couplet**.

## 2. Hors périmètre (cette spécification)

- LLM local, reconnaissance de caractères (OCR) : non nécessaires pour les fichiers visés (voir §3).
  L'analyseur est conçu pour qu'un classifieur de repli puisse être ajouté plus tard.
- Ajout automatique des chants importés aux blocs de la messe du jour (ordre de la célébration).
  Seule la bibliothèque est concernée ; ce sera une évolution ultérieure.
- Accords, partitions, PDF-images, `.doc` / `.docm`.
- Correction automatique des paroles : le texte est conservé tel quel, fautes de frappe comprises.
- Édition de la structure d'un chant dans la page « Bibliothèque » (seul l'écran d'import l'édite).

## 3. Constats sur le corpus (49 fichiers, `G:\Mon Drive\Chants`)

| Famille | Contenu | Exploitable |
|---|---|---|
| Word, feuilles de messe (7) | plusieurs chants, en-têtes **gras + souligné**, refrain en gras ou gras-italique | oui |
| Word, chants seuls (23) | un chant, titre dans le **nom du fichier**, refrain en gras / gras-italique / absent | oui |
| PDF exportés de Word (10) | mêmes conventions ; un fichier simule le gras en imprimant chaque ligne 3 à 4 fois | oui |
| PDF partitions (7) | police de notation (`Maestro`, `EngraverText`), paroles mêlées aux notes | non, refusés avec un message |
| PDF images (2) | aucun texte (`Hosanna exo`, `c est ton sang qui purifie`) | non, refusés avec un message |

Variantes de mise en forme observées : en-têtes `Title: X` / `Artist: Y` ; `Pardon (Lyon centre 2)` ;
`Gloire a Dieu   Lyon centre 4` (recueil après plusieurs espaces) ; en-tête de feuille
`Messe St Roch   Dimanche 04 octobre 2026` ; titre en majuscules sous un en-tête de moment
(`Communion` puis `JE N'AI QUE MA PRIÈRE`) ; `1.` `2.` `Pont :` `2x` ; renvoi
`VOIR CHANT D'ENTRÉE` ; psaume dont seul le refrain est en gras dans la ligne d'en-tête ;
plusieurs vers dans un paragraphe séparés par des doubles espaces.

## 4. Architecture

```
.docx / .pdf
  └─ extraction (par format) ──► liste de Line {texte, gras, italique, souligné, vide_avant}
        └─ analyse (commune) ──► liste de ParsedSong {titre, moment, recueil, sections, ordre, notes}
              └─ écran de vérification (Streamlit) ──► bibliothèque (SQLite)
                                                         └─ générateur PPTX (gras, ordre)
```

Modules (nouveau paquet `tools/import_chants/`) :

| Module | Rôle | Dépend de |
|---|---|---|
| `extract_docx.py` | `extract_docx(data: bytes) -> list[Line]` (python-docx) | — |
| `extract_pdf.py` | `extract_pdf(data: bytes) -> list[Line]` (PyMuPDF) ; lève `UnsupportedFile` (partition, image) | — |
| `parse.py` | `parse_lines(lines, filename) -> ParseResult` (chants + notes + avertissements) | `Line` |
| `dedupe.py` | `find_duplicate(song, library) -> Duplicate` : `none` / `identical` / `different` | db_handler |
| `tools/db_handler.py` | migration, lecture/écriture de `structure`, `ordre`, `recueil` | — |
| `tools/pptx_generator.py` | suit `ordre`, lignes de refrain en gras | slicing |
| `app.py` | page « 📥 Importer des chants » | tout ce qui précède |

Chaque module est testable seul ; l'analyse ne connaît ni Word, ni PDF, ni la base.

## 5. Modèle de données

Colonnes ajoutées à `chants` :

- `recueil TEXT` — « Lyon centre 4 », etc.
- `structure TEXT` — JSON : `{"sections": [{"id": "R", "type": "refrain", "lignes": [...]}, {"id": "1", "type": "couplet", "lignes": [...]}, {"id": "P", "type": "pont", "lignes": [...]}]}`
- `ordre TEXT` — JSON : ordre chanté, par exemple `["R","1","R","2","R"]`.

`paroles` est conservé : texte à plat des sections dans l'ordre du document, refrain une fois. Il sert à
la recherche, à l'affichage et aux chants sans structure.

Nouveaux moments liturgiques : `pardon`, `gloire`, `psaume`, `alleluia`, `pu`, `sanctus`, `anamnese`,
`agneau` (en plus de `entree`, `offertoire`, `communion`, `envoi`, `autre`). La contrainte `CHECK` de
`chant_moments` ne pouvant pas être modifiée en SQLite, la table est reconstruite sans elle ; la
validation passe par l'énumération `MomentLiturgique`.

Migration : numéro de version dans `PRAGMA user_version`, exécutée dans `init_db()`, transactionnelle,
sans perte. Un chant sans `structure` reste valide : il s'affiche et se génère comme aujourd'hui, sans gras.

## 6. Règles d'analyse

**Préparation des lignes.** Un paragraphe contenant des retours à la ligne ou des suites de 2 espaces ou
plus est éclaté en plusieurs lignes (les doubles espaces marquent des fins de vers). Les espaces sont
ensuite normalisées par `clean_spaces`. Un suffixe `2x` / `2X` / `x2` est retiré du texte et signalé dans
`notes`.

**Type de fichier.** Au moins 2 en-têtes de chant détectés : feuille de messe. Sinon : chant seul, dont le
titre est le nom du fichier (sans extension, nettoyé).

**En-têtes de chant**, par ordre de priorité :
1. `Title: X` suivi de `Artist: Y` → titre X, recueil Y.
2. Ligne **gras + souligné** (Word : tous les segments en gras et au moins un souligné ; PDF : gras et trait
   de soulignement sous la ligne). Le recueil est extrait d'un `(…)` final ou de ce qui suit 3 espaces ou
   plus. Le moment est déduit du vocabulaire : entrée, pardon / kyrie / kirie, gloire, psaume, alléluia,
   prière universelle, offertoire, sanctus / saint, anamnèse, agneau, communion, sortie / envoi, sinon `autre`.
3. Ligne courte en gras, en majuscules, directement sous un en-tête de moment : **titre** du chant.

Un en-tête qui contient une date ou commence par « Messe » est l'en-tête de la feuille (métadonnée), pas un chant.

**Titre proposé** : titre explicite s'il existe ; sinon, pour Entrée / Communion / Envoi, les premiers mots
(6 au plus) du premier vers du refrain ; pour les ordinaires (pardon, gloire, sanctus, anamnèse, agneau,
prière universelle, alléluia) : « Pardon – Lyon centre 4 ».

**Sections.** Les blocs sont séparés par des lignes vides. Une ligne-étiquette `1.` / `2)` (couplet),
`Pont :` (pont), `Refrain :` ou `R/` (refrain) est consommée et donne le type. Sans étiquette, un bloc est
un couplet.

**Refrain.**
- Bloc dont toutes les lignes sont en gras (ou gras-italique), alors que le chant contient aussi des blocs
  non gras. Une ligne compte comme grasse si au moins la moitié de ses caractères le sont (une ligne
  partiellement grasse, fréquente dans les feuilles, ne casse donc pas la détection).
- À défaut de gras : bloc entièrement en italique, si le reste du chant ne l'est pas.
- Un bloc identique répété dans le chant est un refrain ; les répétitions sont fusionnées et l'ordre explicite
  du document est conservé.
- Si tout le chant est en gras ou en italique, ou si rien n'est marqué : pas de refrain, avertissement.
- Psaume : seul le segment en gras de la ligne d'en-tête est gardé comme refrain ; le corps est ignoré (AELF).

**Ignorés, avec une note** : `VOIR CHANT D'ENTRÉE` et autres renvois ; lignes de consignes entre crochets.

**Ordre chanté (`ordre`).** Si le refrain apparaît plusieurs fois dans le document, l'ordre du document est
conservé. Sinon : le refrain est inséré après chaque couplet ou pont ; s'il ouvre le chant, il est aussi
joué en premier. Exemples : refrain, 1, 2, pont → `R 1 R 2 R P R` ; couplet, refrain, couplet →
`1 R 2 R`. Sans refrain : ordre du document. L'ordre est modifiable à l'écran de vérification.

**PDF.**
- *Rejet* : police de notation (`maestro`, `engraver`, `musica`, `bravura`) ou moins de 40 caractères de
  texte avec image(s) → `UnsupportedFile` avec la raison.
- *Faux gras* : caractères identiques à moins de 1,5 pt les uns des autres fusionnés ; multiplicité ≥ 3 → gras.
- *Soulignement* : trait horizontal fin (< 2,5 pt de haut) à moins de 5 pt sous la ligne et couvrant au
  moins 30 % de sa largeur.
- Gras : drapeau de police ou nom de police contenant `bold`.

**Sûreté.** Seules les extensions `.docx` et `.pdf` sont acceptées, 10 Mo au plus par fichier, lecture en
mémoire, rien n'est conservé sur le disque. Le HTML et les macros ne sont jamais interprétés.

## 7. PowerPoint

- Un bloc chant porte `structure` et `ordre` (à défaut : `paroles`, comme aujourd'hui).
- Le générateur déroule `ordre` en une suite de lignes, chacune avec un indicateur gras (vrai pour les
  sections `refrain`), une ligne vide entre sections.
- Nouvelle fonction `split_lines_for_slides(lignes, …) -> list[list[Ligne]]` au-dessus du découpeur actuel
  (mode chant) : le texte est découpé comme aujourd'hui (150 caractères, 6 lignes affichées, coupure
  préférée entre sections), puis chaque slide retrouve ses lignes et leur indicateur gras par position.
- Les lignes de refrain sont écrites en gras (Calibri 54, noir). Titre et pagination `[Titre] - x/y` inchangés.

## 8. Écran « 📥 Importer des chants »

1. **Dépôt** : plusieurs fichiers. Les fichiers refusés sont listés avec leur raison, sans bloquer les autres.
2. **Vérification** : une carte par chant, regroupées par fichier :
   - case « Importer » (cochée) et badge **nouveau** / **déjà présent (identique)** / **déjà présent (différent)** ;
   - titre, moment (liste), recueil, modifiables ;
   - sections avec type (Refrain / Couplet / Pont) et zone de texte ; changer le type corrige une détection ;
   - case « Répéter le refrain » (cochée) et ordre résultant affiché (`R · 1 · R · 2 · R`) ;
   - avertissement « aucun refrain détecté » le cas échéant ;
   - notes (renvois ignorés, reprises `2x`).
3. **Import** : bouton « Importer N chants », puis récapitulatif (ajoutés, remplacés, ignorés).

**Doublons.** Clé : titre normalisé (casse, accents, espaces ignorés) + recueil. Texte identique : ignoré
automatiquement. Texte différent : **Remplacer** (ancien et nouveau texte affichés), **Ignorer** (défaut) ou
**Ajouter quand même**.

## 9. Tests

- Documents Word et PDF **fabriqués par les tests** (python-docx, PyMuPDF), un par convention du §3 :
  `Title:/Artist:`, en-têtes soulignés, refrain en gras / gras-italique / italique / absent, faux gras PDF,
  psaume, renvoi, `2x`, doubles espaces, partition, image.
- Analyse : découpage en chants, moments, recueils, titres proposés, sections, refrains, `ordre`.
- Doublons : nouveau, identique, différent. Migration : base existante conservée, chants sans structure inchangés.
- PowerPoint : refrain en gras, ordre répété, pagination, 150 caractères, 6 lignes, coupure entre sections.
- **Test « corpus » local** : parcourt `G:\Mon Drive\Chants` s'il existe (sinon ignoré), vérifie qu'aucun fichier
  ne fait planter l'analyse et que partitions et images sont refusées ; pour `Dimanche 04 octobre 2026.docx`,
  vérifie les 11 sections et les refrains attendus.
- **Droits d'auteur** : le dépôt est public ; aucun fichier ni paroles réelles ne sont versionnés.

## 10. Livraison en trois étapes

1. **Données et PowerPoint** : migration, `structure` / `ordre` / `recueil`, nouveaux moments, gras et
   répétition du refrain dans le PPTX.
2. **Extraction et analyse** : Word, puis PDF.
3. **Écran d'import** : dépôt, vérification, doublons, récapitulatif.

Dépendances ajoutées : `python-docx`, `PyMuPDF`. Pas de modèle, pas de service supplémentaire.

## 11. Risques

- Un fichier sans aucune mise en forme est découpé grossièrement : correction à l'écran de vérification.
- La détection du soulignement et du faux gras en PDF est heuristique : couverte par des tests et par le test corpus.
- Les fautes de frappe des feuilles sont conservées.
- `PyMuPDF` est sous licence AGPL ; sans objet pour un usage paroissial, à revoir si l'application est redistribuée.
