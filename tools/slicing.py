"""
Découpage d'un texte en slides (max 150 caractères) - voir hardprompts/slicing_rules.md.

Le découpage est calculé en une seule passe (programmation dynamique) pour tout le
texte : on obtient donc le nombre total de slides (y) avant d'écrire les titres.
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 150
DEFAULT_CHARS_PER_LINE = 30  # estimation prudente à Calibri 54 en 16:9

# Coûts (plus bas = meilleure coupure)
SLIDE_COST = 10          # par slide : limite leur nombre
SLACK_WEIGHT = 10        # slide loin de max_chars : pénalité quadratique
COST_STRONG = 0          # fin de phrase hors citation
COST_STRONG_IN_QUOTE = 5
COST_PLAIN = 30          # mot sans ponctuation
COST_PLAIN_IN_QUOTE = 40
COST_DANGLING_WORD = 25  # mot-outil (de, la, et...) en fin de slide
COST_CLAUSE_START = -12  # coupure juste avant une conjonction / un relatif
COST_VIOLATION = 1000    # règle du cahier des charges violée (dernier recours)
COST_LINE_END = 5        # chants : fin de ligne
COST_MID_LINE = 40       # chants : coupure au milieu d'une ligne

MIN_QUOTE_WORDS = 3  # mots de citation requis avant une coupure interne

_CLOSERS = "»”\""
_STRONG_END = ".!?…)"
_FORBIDDEN_END = ",;:-–—"
_CLOSING_ONLY = re.compile(r"^[:;?!»”…).,%]+$")
_OPENING_ONLY = re.compile(r"^[«“(\[]+$")
_ABBREVIATIONS = {"cf.", "st.", "ste.", "m.", "mm.", "mme", "mgr.", "dr.", "n.", "v.", "vv."}
_DANGLING = {
    "de", "du", "des", "la", "le", "les", "un", "une", "et", "ou", "à", "au", "aux",
    "en", "que", "qui", "ne", "ce", "se", "sa", "son", "ses", "mon", "ma", "mes",
    "ton", "ta", "tes", "notre", "votre", "leur", "leurs", "dans", "par", "pour",
    "sur", "avec", "sans", "sous", "comme", "mais", "car", "donc", "ni", "si", "y",
    "afin", "parce", "puisque", "lorsque", "quand", "alors", "puis", "dont", "où",
    "voici", "voilà", "vers", "chez", "entre", "après", "avant", "selon", "depuis", "contre",
}

_CLAUSE_STARTERS = {
    "et", "ou", "mais", "car", "donc", "or", "ni", "que", "qu", "qui", "dont", "où",
    "afin", "parce", "puisque", "lorsque", "quand", "comme", "si", "ainsi", "alors", "puis",
}

Mode = Literal["text", "chant"]


@dataclass
class _Token:
    start: int
    end: int
    gap: str = ""          # séparateur après le token : " ", "\n" ou "\n\n"
    in_quote: bool = False  # une citation est ouverte après ce token
    quote_open: int = -1    # index du token qui a ouvert la citation en cours


def clean_spaces(text: str, keep_newlines: bool = False) -> str:
    """
    Ramène chaque suite d'espaces (y compris insécables) à une seule espace.
    Seule une espace insécable collée à la ponctuation française est conservée :
    avant ! ? : ; » et après «. Le HTML d'AELF met aussi des suites d'&nbsp; entre les
    versets : elles deviennent une espace simple.
    keep_newlines : conserve les retours à la ligne (une ligne vide au plus), pour les chants.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if keep_newlines:
        lines = [clean_spaces(line) for line in text.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")

    def collapse(m: re.Match) -> str:
        after = text[m.end():m.end() + 1]
        before = text[m.start() - 1:m.start()] if m.start() else ""
        glued = (after and after in "!?:;»") or (before and before == "«")
        return "\xa0" if glued and any(c in "\xa0 " for c in m.group()) else " "

    return re.sub(r"\s+", collapse, text).strip()


def _normalize(text: str, mode: Mode) -> str:
    return clean_spaces(text, keep_newlines=(mode == "chant"))


def _update_quotes(stack: list[str], token_text: str) -> None:
    for ch in token_text:
        if ch in "«“":
            stack.append(ch)
        elif ch in "»”":
            if stack:
                stack.pop()
        elif ch == '"':
            if stack and stack[-1] == '"':
                stack.pop()
            else:
                stack.append('"')


def _tokenize(s: str, mode: Mode) -> list[_Token]:
    """
    Mots séparés par espace ou saut de ligne (l'espace insécable ne sépare pas).
    La ponctuation isolée (" :", " ?", " »") est collée au mot précédent, les
    ouvrants isolés ("« ") au mot suivant : on ne peut jamais couper à cet endroit.
    """
    tokens: list[_Token] = []
    stack: list[str] = []
    carry_start = None
    carry_end = 0
    carry_was_open = False
    last_run_end = 0

    for m in re.finditer(r"[^ \n]+", s):
        text = m.group()
        if not text.strip():
            continue  # espace insécable isolée : ce n'est pas un mot
        gap_before = s[last_run_end:m.start()]
        last_run_end = m.end()
        same_line = "\n" not in gap_before

        is_closing = bool(_CLOSING_ONLY.match(text)) or (text == '"' and stack and stack[-1] == '"')
        if tokens and is_closing and carry_start is None and (mode == "text" or same_line):
            tokens[-1].end = m.end()
            _update_quotes(stack, text)
            tokens[-1].in_quote = bool(stack)
            continue

        carried = carry_start is not None
        start = carry_start if carried else m.start()
        was_open = carry_was_open if carried else bool(stack)
        carry_start = None
        if _OPENING_ONLY.match(text) or (text == '"' and not stack):
            carry_start, carry_end, carry_was_open = start, m.end(), was_open
            _update_quotes(stack, text)
            continue

        prev_open = tokens[-1].quote_open if tokens else -1
        _update_quotes(stack, text)
        idx = len(tokens)
        if stack:
            quote_open = prev_open if was_open and prev_open >= 0 else idx
        else:
            quote_open = -1
        tokens.append(_Token(start, m.end(), in_quote=bool(stack), quote_open=quote_open))

    if carry_start is not None:  # ouvrant isolé en toute fin de texte : on le garde
        if tokens:
            tokens[-1].end = carry_end
            tokens[-1].in_quote = bool(stack)
        else:
            tokens.append(_Token(carry_start, carry_end, in_quote=bool(stack), quote_open=0 if stack else -1))

    # séparateurs : "\n\n" > "\n" > " "
    for k, tok in enumerate(tokens[:-1]):
        gap = s[tok.end:tokens[k + 1].start]
        tok.gap = "\n\n" if gap.count("\n") >= 2 else ("\n" if "\n" in gap else " ")
    return tokens


def _ending(token_text: str) -> str:
    """'strong' | 'forbidden' | 'plain' selon le dernier caractère (fermants ignorés)."""
    t = token_text.rstrip(_CLOSERS + " ")
    if not t:
        return "plain"
    c = t[-1]
    if c in _FORBIDDEN_END:
        return "forbidden"
    if c in _STRONG_END:
        if c == "." and t.lower().split()[-1] in _ABBREVIATIONS:
            return "plain"
        return "strong"
    return "plain"


def _last_word_is_dangling(token_text: str) -> bool:
    words = token_text.split()
    if not words:
        return False
    return re.sub(r"[^\wÀ-ÿ’']", "", words[-1]).lower() in _DANGLING


def _starts_clause(token_text: str) -> bool:
    first = re.split(r"[’' ]", token_text.lstrip("«“\"( "), maxsplit=1)[0]
    return first.lower() in _CLAUSE_STARTERS


def _cut_cost(s: str, tokens: list[_Token], k: int, mode: Mode) -> int:
    """Coût d'une fin de slide après le token k (qui n'est pas le dernier du texte)."""
    tok = tokens[k]
    text = s[tok.start:tok.end]

    if mode == "chant" and tok.gap != " ":
        return COST_STRONG if tok.gap == "\n\n" else COST_LINE_END

    cost = 0
    ending = _ending(text)
    if ending == "forbidden":
        return COST_VIOLATION
    if tok.in_quote and k - tok.quote_open + 1 < MIN_QUOTE_WORDS:
        return COST_VIOLATION  # coupure au tout début d'une citation

    if ending == "strong":
        cost = COST_STRONG_IN_QUOTE if tok.in_quote else COST_STRONG
    else:
        cost = COST_PLAIN_IN_QUOTE if tok.in_quote else COST_PLAIN
        if _last_word_is_dangling(text):
            cost += COST_DANGLING_WORD
        if _starts_clause(s[tokens[k + 1].start:tokens[k + 1].end]):
            cost += COST_CLAUSE_START
    if mode == "chant":
        cost += COST_MID_LINE
    return cost


def _displayed_lines(chunk: str, chars_per_line: int) -> int:
    return sum(max(1, -(-len(part) // chars_per_line)) for part in chunk.split("\n"))


def split_text_for_slides(
    text: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    mode: Mode = "text",
    max_lines: int | None = None,
    chars_per_line: int = DEFAULT_CHARS_PER_LINE,
) -> list[str]:
    """
    Découpe `text` en slides de `max_chars` caractères maximum (espaces compris).

    - Ne coupe jamais un mot ; peut produire des slides plus courtes si la coupure
      est plus logique (fin de phrase, citation entière...).
    - Un slide ne se termine pas par , ; : - ni par un guillemet ouvrant ou le tout
      début d'une citation. Il peut finir par . ! ? … ou ).
    - mode="chant" : coupe aux fins de ligne (ligne vide préférée), conserve les
      retours à la ligne et n'applique pas les règles de ponctuation aux fins de ligne.
    - max_lines : nombre maximum de lignes affichées par slide (une ligne de plus de
      `chars_per_line` caractères se replie sur plusieurs lignes), pour éviter que le
      texte déborde de la slide.
    """
    s = _normalize(text or "", mode)
    if not s:
        return []
    tokens = _tokenize(s, mode)
    n = len(tokens)

    best = [float("inf")] * (n + 1)
    prev = [0] * (n + 1)
    violation = [False] * (n + 1)
    best[0] = 0.0

    for j in range(1, n + 1):
        end_cost = 0 if j == n else _cut_cost(s, tokens, j - 1, mode)
        for i in range(j - 1, -1, -1):
            length = tokens[j - 1].end - tokens[i].start
            oversize = length > max_chars or (
                max_lines is not None
                and _displayed_lines(s[tokens[i].start:tokens[j - 1].end], chars_per_line) > max_lines
            )
            if oversize and i < j - 1:
                break
            slack = SLACK_WEIGHT * ((max_chars - min(length, max_chars)) / max_chars) ** 2
            cost = best[i] + SLIDE_COST + slack + end_cost + (COST_VIOLATION if oversize else 0)
            if cost < best[j]:
                best[j] = cost
                prev[j] = i
                violation[j] = oversize or end_cost >= COST_VIOLATION

    chunks: list[str] = []
    j = n
    while j > 0:
        i = prev[j]
        chunk = s[tokens[i].start:tokens[j - 1].end]
        if violation[j]:
            logger.warning("Découpage : règle non respectable pour le slide %r", chunk)
        chunks.append(chunk)
        j = i
    chunks.reverse()
    return chunks
