"""Tests du modèle de chant (context/models.py)."""

from context.models import Chant, MomentLiturgique, SectionChant, TypeSection


def _sections() -> list[SectionChant]:
    return [
        SectionChant("R", TypeSection.REFRAIN, ["ligne refrain 1", "ligne refrain 2"]),
        SectionChant("1", TypeSection.COUPLET, ["ligne couplet"]),
    ]


def test_new_liturgical_moments_exist_and_old_ones_are_unchanged():
    values = {m.value for m in MomentLiturgique}
    assert values >= {"pardon", "gloire", "psaume", "alleluia", "pu", "sanctus", "anamnese", "agneau"}
    assert values >= {"entree", "offertoire", "communion", "envoi", "autre"}
    assert MomentLiturgique("entree") is MomentLiturgique.ENTREE


def test_chant_has_empty_structure_by_default():
    chant = Chant(titre="T", paroles="p")
    assert chant.recueil is None
    assert chant.structure == []
    assert chant.ordre == []


def test_chant_roundtrip_through_dict_keeps_structure():
    chant = Chant(
        titre="T",
        paroles="p",
        recueil="Lyon centre 4",
        structure=_sections(),
        ordre=["R", "1", "R"],
        moments=[MomentLiturgique.PARDON],
    )
    assert Chant.from_dict(chant.to_dict()) == chant


def test_from_dict_accepts_old_dicts_without_structure():
    chant = Chant.from_dict({"titre": "T", "paroles": "p"})
    assert chant.structure == [] and chant.ordre == [] and chant.recueil is None


def test_set_paroles_unchanged_text_keeps_structure():
    chant = Chant(titre="T", paroles="a", structure=_sections(), ordre=["R", "1"])
    assert chant.set_paroles("a") is False
    assert chant.structure and chant.ordre == ["R", "1"]


def test_set_paroles_changed_text_drops_structure():
    chant = Chant(titre="T", paroles="a", structure=_sections(), ordre=["R", "1"])
    assert chant.set_paroles("autre texte") is True
    assert chant.paroles == "autre texte"
    assert chant.structure == [] and chant.ordre == []


def test_set_paroles_without_structure_just_updates_text():
    chant = Chant(titre="T", paroles="a")
    assert chant.set_paroles("b") is False
    assert chant.paroles == "b"
