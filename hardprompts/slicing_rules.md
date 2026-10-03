# Règles de découpage (tools/slicing.py)

`split_text_for_slides(text, max_chars=150, mode="text" | "chant")`

- **150 caractères maximum** par slide (espaces compris), mais un slide plus court est préféré
  si la coupure est plus logique.
- Ne jamais couper un mot. La ponctuation isolée (` :`, ` ?`, ` »`) reste collée au mot précédent.
- **Fin de slide interdite** : `,` `;` `:` `-` `–` `—` (même suivie de `»`), guillemet ouvrant,
  ou tout début de citation (moins de 3 mots de la citation).
- **Fin de slide autorisée** : `.` `!` `?` `…` `)` (éventuellement suivis de `»`).
- **Citations** : une citation courte passe entière sur le slide suivant ; une citation longue
  n'est coupée qu'à une ponctuation forte à l'intérieur.
- Coupure forcée en milieu de phrase : de préférence juste avant une conjonction ou un relatif
  (`qu'il`, `mais`, `afin que`...), jamais après un mot-outil (`de`, `la`, `et`, `afin`...).
- **Chants** (`mode="chant"`) : coupure aux fins de ligne (ligne vide entre couplets préférée),
  retours à la ligne conservés, règles de ponctuation non appliquées aux fins de ligne.
- Le découpage est calculé pour tout le texte (programmation dynamique, coûts dans `slicing.py`),
  ce qui donne le nombre total de slides `y` pour le titre `[Titre] - x/y`.
