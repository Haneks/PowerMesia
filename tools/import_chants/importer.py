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
    if not nom.endswith((".docx", ".pdf")):
        raise UnsupportedFile("Format non géré : seuls les fichiers .docx et .pdf sont acceptés")
    try:
        lignes = extract_docx(data) if nom.endswith(".docx") else extract_pdf(data)
        return parse_lines(lignes, nom_fichier)
    except UnsupportedFile:
        raise
    except Exception as e:  # filet de dernier recours : un fichier ne doit jamais faire planter l'écran d'import
        raise UnsupportedFile("Fichier illisible") from e
