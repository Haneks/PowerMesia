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
- **En-têtes** : un seul en-tête de chant suffit à lire titre et moment ; un fichier sans aucun en-tête est
  un chant seul, titre tiré du nom du fichier.
- **En-tête de feuille** : une date, une ligne « Messe … » sans moment du vocabulaire et suivie d'une ligne
  vide, ou « Église … » est reconnue à toute position ; un `Title:` explicite n'est jamais pris pour un
  en-tête de feuille.
- **Consignes** : les consignes entre crochets (`[Procession des enfants]`) sont ignorées avec une note
  « Consigne ignorée ».
- **Sections** : étiquettes `1.`, `Couplet 2`, `Pont :`, `Refrain` ; sinon un bloc par ligne vide.
- **Refrain** : bloc entièrement en gras (à défaut en italique), ou bloc répété ; tout en gras ou rien de
  marqué : pas de refrain et un avertissement. Psaume : seul le refrain en gras est gardé.
- **Ordre chanté** : refrain répété dans le document → ordre du document ; sinon `compute_ordre`.
- **Titres** : titre explicite (`Title:` ou ligne en majuscules sous tout en-tête de chant, et sous le chant
  seul, sauf quand un `Title:` explicite donne déjà le titre) ; chant seul : nom du fichier ; ordinaire
  (pardon, gloire…) : « Pardon – Lyon centre 4 » ; sinon début du premier refrain.
- Les paroles ne sont jamais corrigées ; seuls les espaces et les reprises `2x` / `bis` sont retirés.

## Limite connue

Un psaume dont le refrain est écrit sur la ligne d'en-tête, quand toute la ligne est en gras et soulignée,
est signalé « rien à importer » : le refrain y est indiscernable d'un recueil. Le cas courant (refrain en
gras dans le corps du psaume) est géré.
