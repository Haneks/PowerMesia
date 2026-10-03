"""Fabrique de fichiers Word et PDF pour les tests de l'import (textes inventés, rien du corpus)."""

from tools.import_chants.modeles import Line


def L(texte: str, gras=False, italique=False, souligne=False, vide=False) -> Line:
    """Une Line abrégée, pour tester l'analyse sans passer par un fichier."""
    return Line(texte, gras, italique, souligne, vide)
