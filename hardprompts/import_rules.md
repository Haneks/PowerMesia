# Règles de l'import de chants (tools/import_chants)

Fichiers acceptés : `.docx` et `.pdf` exportés de Word (texte sélectionnable), 10 Mo au plus, lus en
mémoire. Partitions (police de notation, texte en syllabes) et PDF-images : refusés avec une raison, comme un
.docx de plus de 50 Mo décompressé (5 Mo pour `word/document.xml`, 1000 entrées) ou un PDF de plus de 50 pages.

- **Lignes** : un paragraphe est éclaté aux retours à la ligne et aux doubles espaces (fins de vers) ; une
  ligne est grasse / italique / soulignée si la moitié de ses caractères le sont. PDF : « faux gras »
  (texte imprimé 3 fois) reconnu comme du gras ; lignes vides déduites des écarts verticaux.
- **Chants d'une feuille** : un en-tête est une ligne en gras et soulignée (ou `Title:` / `Artist:`, ou un
  mot du vocabulaire en gras seul sur son bloc). Le recueil est lu entre parenthèses, après 3 espaces, après
  le mot-clé du moment, ou sur la ligne suivante. L'en-tête de la feuille (date, église) et les renvois
  (`VOIR CHANT D'ENTREE`) ne sont pas des chants et sont signalés.
- **En-têtes** : un seul en-tête de chant suffit à lire titre et moment ; un fichier sans aucun en-tête est
  un chant seul, titre tiré du nom du fichier.
- **En-tête de feuille** : une date, une ligne « Messe … » sans moment du vocabulaire et suivie d'une ligne
  vide, ou « Église … » est reconnue à toute position ; un `Title:` explicite n'est jamais pris pour un
  en-tête de feuille.
- **Consignes** : les consignes entre crochets (`[Procession des enfants]`) sont ignorées avec une note
  « Consigne ignorée ».
- **Sections** : étiquettes `1.`, `1)`, `Couplet 2`, `Pont :`, `Refrain`, `Refrain :`, `R/`, `Ref.` ; sinon un
  bloc par ligne vide. Un saut de page commence toujours un nouveau bloc (PDF).
- **Refrain** : bloc entièrement en gras (à défaut en italique), ou bloc répété ; tout en gras ou rien de
  marqué : pas de refrain et un avertissement. Un refrain étiqueté (`Refrain :`) puis répété sans étiquette
  reste ce refrain (jamais un couplet). Psaume : seul le refrain en gras est gardé.
- **Après le mot-moment d'un en-tête** : les séparateurs de tête (`:`, `–`) sont retirés ; un numéro de
  psaume (`Psaume 22`, `Psaume 22 (21)`) reste dans le nom et le titre, jamais dans le recueil ; un complément
  de l'intitulé (`Acclamation de l'Évangile`) n'est pas un recueil ; ce qui suit une virgule ou `:` est des
  paroles collées.
- **Ordre chanté** : refrain répété dans le document → ordre du document ; sinon `compute_ordre`.
- **Titres** : titre explicite (`Title:` ou ligne en majuscules sous tout en-tête de chant, et sous le chant
  seul, sauf quand un `Title:` explicite donne déjà le titre) ; chant seul : nom du fichier ; ordinaire
  (pardon, gloire…) : « Pardon – Lyon centre 4 » ; sinon début du premier refrain.
- Les paroles ne sont jamais corrigées ; seuls les espaces et les reprises `2x` / `bis` sont retirés.

## Limite connue

Un psaume dont le refrain est écrit sur la ligne d'en-tête, quand toute la ligne est en gras et soulignée,
est signalé « rien à importer » : le refrain y est indiscernable d'un recueil. Le cas courant (refrain en
gras dans le corps du psaume) est géré.

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
