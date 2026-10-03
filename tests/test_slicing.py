"""Tests du découpage de texte en slides (tools/slicing.py)."""

import re

import pytest

from tools.slicing import split_text_for_slides

MAX = 150
FORBIDDEN_ENDINGS = (",", ";", ":", "-", "–", "—")
CLOSERS = "»”\""
OPENERS = ("«", "“")

# Extrait de l'Évangile (Jn 3), avec ponctuation française (espaces avant : ; ? ! »)
EVANGILE = (
    "En ce temps-là, Jésus disait à Nicodème : « Dieu a tellement aimé le monde "
    "qu’il a donné son Fils unique, afin que quiconque croit en lui ne se perde pas, "
    "mais obtienne la vie éternelle. Car Dieu n’a pas envoyé son Fils dans le monde "
    "pour condamner le monde, mais pour que, par lui, le monde soit sauvé. "
    "Celui qui croit en lui n’est pas condamné ; celui qui ne croit pas est déjà "
    "condamné, parce qu’il n’a pas cru au nom du Fils unique de Dieu. "
    "Et voici le jugement : la lumière est venue dans le monde, et les hommes ont "
    "préféré les ténèbres à la lumière, parce que leurs œuvres étaient mauvaises. »"
)

# Lecture avec une longue phrase pleine de virgules
LECTURE = (
    "Frères, Dieu, qui est riche en miséricorde, à cause du grand amour dont il nous "
    "a aimés, nous qui étions morts à cause de nos fautes, nous a fait revivre avec "
    "le Christ, c’est par grâce que vous êtes sauvés, avec lui il nous a ressuscités, "
    "avec lui il nous a fait siéger aux cieux, dans le Christ Jésus. Ainsi, il a voulu "
    "montrer dans les siècles à venir l’extraordinaire richesse de sa grâce, par sa "
    "bonté pour nous dans le Christ Jésus."
)


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _last_char(chunk: str) -> str:
    return chunk.rstrip(CLOSERS + " \n")[-1:]


@pytest.mark.parametrize("text", [EVANGILE, LECTURE])
class TestTextRules:
    def test_chunks_respect_max_length(self, text):
        for chunk in split_text_for_slides(text):
            assert len(chunk) <= MAX

    def test_words_never_cut_and_text_preserved(self, text):
        chunks = split_text_for_slides(text)
        assert _normalized(" ".join(chunks)) == _normalized(text)

    def test_no_chunk_ends_with_forbidden_punctuation(self, text):
        for chunk in split_text_for_slides(text)[:-1]:
            assert _last_char(chunk) not in FORBIDDEN_ENDINGS, chunk

    def test_no_chunk_ends_with_opening_quote(self, text):
        for chunk in split_text_for_slides(text):
            assert not chunk.rstrip().endswith(OPENERS), chunk

    def test_no_chunk_starts_with_orphan_punctuation(self, text):
        for chunk in split_text_for_slides(text):
            assert chunk[0] not in ":;?!»”.,)", chunk


def test_empty_text_gives_no_chunk():
    assert split_text_for_slides("") == []
    assert split_text_for_slides("  \n ") == []


def test_short_text_is_a_single_chunk():
    assert split_text_for_slides("Parole du Seigneur.") == ["Parole du Seigneur."]


def test_prefers_sentence_boundary_even_if_shorter_than_max():
    s1 = "Le Seigneur est mon berger, je ne manque de rien, il me fait reposer dans de verts pâturages."
    s2 = "Il me conduit vers les eaux tranquilles et me fait revivre, il me guide sur le bon chemin."
    assert len(s1) + len(s2) + 1 > MAX
    assert split_text_for_slides(f"{s1} {s2}") == [s1, s2]


@pytest.mark.parametrize("end", ["?", "!", ")", "…"])
def test_question_exclamation_paren_and_ellipsis_are_allowed_endings(end):
    s1 = f"Pourquoi cherchez-vous parmi les morts celui qui est vivant, lui qui vous parlait en Galilée{end}"
    s2 = "Il n’est pas ici, il est ressuscité, souvenez-vous de ce qu’il vous a dit."
    assert len(s1) + len(s2) + 1 > MAX
    assert split_text_for_slides(f"{s1} {s2}") == [s1, s2]


def test_french_spaced_punctuation_stays_with_previous_word():
    text = ("Jésus leur dit : « Pourquoi avez-vous peur ? Pourquoi hésiter ? "
            "Regardez mes mains et mes pieds ! C’est bien moi ; touchez-moi et voyez. "
            "Un esprit n’a ni chair ni os, comme vous constatez que j’en ai. »")
    for chunk in split_text_for_slides(text):
        assert not re.match(r"^[:;?!»]", chunk), chunk


def test_short_quote_goes_whole_to_next_slide():
    s1 = ("Après cela, Jésus se rendit sur l’autre rive du lac de Tibériade et "
          "la foule le suivait en grand nombre depuis le matin de ce jour-là.")
    quote_part = "Il dit : « Viens et suis-moi. »"
    assert len(s1) + 1 + len(quote_part) > MAX
    chunks = split_text_for_slides(f"{s1} {quote_part}")
    assert chunks == [s1, quote_part]


def test_quote_is_split_only_after_strong_punctuation_inside_it():
    text = ("Jésus dit à ses disciples : « Je suis le bon pasteur. Le bon pasteur "
            "donne sa vie pour ses brebis. Le mercenaire, lui, s’enfuit quand il "
            "voit venir le loup, car il n’est pas le berger. Moi, je connais mes "
            "brebis et mes brebis me connaissent. »")
    chunks = split_text_for_slides(text)
    assert len(chunks) > 1
    for chunk in chunks[:-1]:
        assert _last_char(chunk) in ".!?…)", chunk
        assert len(chunk) <= MAX


def test_closing_quote_after_period_is_a_valid_ending():
    s1 = "Pierre répondit à Jésus : « Seigneur, tu sais bien que je t’aime, tu le sais depuis toujours. »"
    s2 = "Jésus lui dit alors de paître ses agneaux, de prendre soin de son troupeau."
    assert len(s1) + len(s2) + 1 > MAX
    assert split_text_for_slides(f"{s1} {s2}") == [s1, s2]


def test_comma_before_closing_quote_is_forbidden():
    text = ("Ils disaient : « Nous avons vu sa gloire, la gloire du Fils unique du Père, »"
            " et ils rendaient grâce à Dieu pour toutes les merveilles qu’ils avaient vues.")
    for chunk in split_text_for_slides(text)[:-1]:
        assert _last_char(chunk) not in FORBIDDEN_ENDINGS, chunk


def test_chunk_never_ends_with_a_dangling_function_word_when_avoidable():
    text = " ".join(["Dieu est amour et celui qui demeure dans l’amour demeure en Dieu"] * 4)
    for chunk in split_text_for_slides(text)[:-1]:
        assert chunk.split()[-1].lower() not in {"de", "la", "le", "et", "dans", "en", "qui"}, chunk


def test_forced_mid_sentence_cut_happens_before_a_conjunction_or_relative():
    chunks = split_text_for_slides(EVANGILE)
    assert chunks[0].endswith("le monde")
    assert chunks[1].startswith("qu’il")


def test_oversized_single_word_is_kept_whole():
    word = "a" * 200
    chunks = split_text_for_slides(f"Début {word} fin")
    assert word in chunks
    assert _normalized(" ".join(chunks)) == f"Début {word} fin"


# --- Chants : coupure aux fins de ligne, retours à la ligne conservés ---

REFRAIN = "Qu’il est bon, qu’il est doux,\nQue les frères soient unis,\nDans la paix, dans la joie,\nDans l’amour de Jésus-Christ."
COUPLET = "Je veux chanter ton nom, Seigneur,\nTu es mon roc, ma forteresse,\nMon bouclier, ma délivrance,\nMon refuge et ma joie."


def test_chant_keeps_line_breaks_and_preserves_text():
    chunks = split_text_for_slides(f"{REFRAIN}\n\n{COUPLET}", mode="chant")
    assert "\n".join(chunks).replace("\n\n", "\n") == f"{REFRAIN}\n{COUPLET}"
    assert all("\n" in c for c in chunks)
    assert all(len(c) <= MAX for c in chunks)


def test_chant_cuts_on_blank_line_between_verses():
    assert len(REFRAIN) < MAX and len(COUPLET) < MAX
    assert len(REFRAIN) + len(COUPLET) + 2 > MAX
    assert split_text_for_slides(f"{REFRAIN}\n\n{COUPLET}", mode="chant") == [REFRAIN, COUPLET]


def test_chant_cuts_at_line_end_even_after_a_comma():
    lines = ["Ligne numéro un de ce chant très long,"] * 6
    chunks = split_text_for_slides("\n".join(lines), mode="chant")
    assert len(chunks) > 1
    for chunk in chunks:
        assert all(line == lines[0] for line in chunk.split("\n")), chunk


def test_chant_overlong_line_still_respects_max_and_words():
    line = " ".join(["alléluia"] * 30)
    chunks = split_text_for_slides(line, mode="chant")
    assert all(len(c) <= MAX for c in chunks)
    assert _normalized(" ".join(chunks)) == line


# --- Hauteur : les lignes longues se replient à l'écran ---

def test_chant_wrapped_lines_are_limited_by_max_lines():
    line = "Ligne de chant un peu longue à l’écran ici"  # 42 car. : 2 lignes affichées à 30 car./ligne
    chunks = split_text_for_slides("\n".join([line] * 6), mode="chant", max_lines=6, chars_per_line=30)
    for chunk in chunks:
        displayed = sum(-(-len(part) // 30) or 1 for part in chunk.split("\n"))
        assert displayed <= 6, chunk
    assert len(chunks) == 2
