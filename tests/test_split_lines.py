"""Tests de split_lines_for_slides : le découpage conserve le gras de chaque ligne."""

from tools.slicing import split_lines_for_slides, split_text_for_slides

REFRAIN = [("Gloire à Dieu, au plus haut des cieux,", True), ("Paix sur la terre aux hommes qu'il aime !", True)]
COUPLET = [("Nous te louons, nous te bénissons,", False), ("Nous t'adorons, nous te glorifions,", False)]
SEP = ("", False)


def test_slides_have_the_same_text_as_plain_chant_slicing():
    lines = REFRAIN + [SEP] + COUPLET
    pages = split_lines_for_slides(lines, max_lines=6)
    expected = split_text_for_slides("\n".join(t for t, _ in lines), mode="chant", max_lines=6)
    assert ["\n".join(t for t, _ in page) for page in pages] == expected


def test_bold_flag_follows_each_line():
    lines = REFRAIN + [SEP] + COUPLET + [SEP] + REFRAIN
    refrain_texts = {t for t, _ in REFRAIN}
    for page in split_lines_for_slides(lines, max_lines=6):
        for text, bold in page:
            if text:
                assert bold == (text in refrain_texts), text


def test_blank_line_between_sections_is_kept_when_they_share_a_slide():
    pages = split_lines_for_slides([("Alléluia", True), SEP, ("Chantons le Seigneur", False)])
    assert pages == [[("Alléluia", True), ("", False), ("Chantons le Seigneur", False)]]


def test_overlong_bold_line_stays_bold_across_slides():
    line = " ".join(["alléluia"] * 40)
    pages = split_lines_for_slides([(line, True)], max_lines=6)
    assert len(pages) > 1
    assert all(bold for page in pages for text, bold in page if text)
    assert " ".join(t for page in pages for t, _ in page) == line


def test_line_with_embedded_newline_is_split_into_lines():
    pages = split_lines_for_slides([("un\ndeux", True)])
    assert pages == [[("un", True), ("deux", True)]]


def test_empty_input_gives_no_slide():
    assert split_lines_for_slides([]) == []
    assert split_lines_for_slides([SEP]) == []


def test_a_couplet_is_not_split_when_it_fits_on_its_own_slide():
    refrain = [("Chantons au Seigneur un chant nouveau,", True), ("Alléluia, alléluia !", True)]
    couplet_1 = [("Le matin se lève sur la ville,", False), ("Les cloches annoncent le jour.", False)]
    couplet_2 = [("Le soir descend sur la vallée,", False), ("Nous rendons grâce pour ce jour.", False)]
    lines = refrain + [SEP] + couplet_1 + [SEP] + refrain + [SEP] + couplet_2 + [SEP] + refrain

    pages = split_lines_for_slides(lines, max_lines=6)

    for first, second in (couplet_1, couplet_2):
        for page in pages:
            texts = [t for t, _ in page]
            assert (first[0] in texts) == (second[0] in texts), texts
