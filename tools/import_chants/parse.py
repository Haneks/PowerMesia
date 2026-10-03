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
