"""Tests de tools/chant_structure.py."""

import logging

from context.models import SectionChant, TypeSection
from tools.chant_structure import (
    compute_ordre,
    expand_lines,
    ordre_from_json,
    ordre_to_json,
    paroles_from_structure,
    sections_from_dicts,
    sections_to_dicts,
    structure_from_json,
    structure_to_json,
)

R = SectionChant("R", TypeSection.REFRAIN, ["refrain"])
C1 = SectionChant("1", TypeSection.COUPLET, ["couplet 1"])
C2 = SectionChant("2", TypeSection.COUPLET, ["couplet 2"])
P = SectionChant("P", TypeSection.PONT, ["pont"])


# --- compute_ordre ---

def test_refrain_opening_the_song_is_played_first_and_after_each_section():
    assert compute_ordre([R, C1, C2, P]) == ["R", "1", "R", "2", "R", "P", "R"]


def test_refrain_after_first_couplet():
    assert compute_ordre([C1, R, C2]) == ["1", "R", "2", "R"]


def test_no_refrain_keeps_document_order():
    assert compute_ordre([C1, C2, P]) == ["1", "2", "P"]


def test_several_refrain_sections_keep_document_order():
    r2 = SectionChant("R2", TypeSection.REFRAIN, ["autre refrain"])
    assert compute_ordre([R, C1, r2, C2]) == ["R", "1", "R2", "2"]


def test_repeat_disabled_keeps_document_order():
    assert compute_ordre([R, C1, C2], repeat_refrain=False) == ["R", "1", "2"]


def test_only_a_refrain():
    assert compute_ordre([R]) == ["R"]


def test_empty_structure():
    assert compute_ordre([]) == []


# --- sérialisation ---

def test_structure_json_roundtrip():
    raw = structure_to_json([R, C1])
    assert structure_from_json(raw) == [R, C1]


def test_empty_structure_is_stored_as_none_and_read_back_as_empty():
    assert structure_to_json([]) is None
    assert structure_from_json(None) == []
    assert structure_from_json("") == []


def test_ordre_json_roundtrip():
    assert ordre_from_json(ordre_to_json(["R", "1", "R"])) == ["R", "1", "R"]
    assert ordre_to_json([]) is None
    assert ordre_from_json(None) == []


def test_sections_dict_roundtrip():
    assert sections_from_dicts(sections_to_dicts([R, P])) == [R, P]


# --- paroles à plat et lignes à projeter ---

def test_paroles_from_structure_lists_each_section_once():
    assert paroles_from_structure([R, C1]) == "refrain\n\ncouplet 1"


def test_expand_lines_marks_refrain_bold_and_separates_sections():
    lines = expand_lines([R, C1], ["R", "1", "R"])
    assert lines == [
        ("refrain", True), ("", False), ("couplet 1", False), ("", False), ("refrain", True),
    ]


def test_expand_lines_skips_unknown_section_with_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        lines = expand_lines([R], ["R", "X", "R"])
    assert lines == [("refrain", True), ("", False), ("refrain", True)]
    assert "X" in caplog.text
