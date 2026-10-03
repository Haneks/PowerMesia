"""Tests de tools/import_chants/lignes.py : des caractères mis en forme → des lignes de chant."""

from tools.import_chants.lignes import lignes_depuis_caracteres
from tools.import_chants.modeles import Line


def car(texte: str, gras=False, italique=False, souligne=False) -> list[tuple]:
    return [(c, gras, italique, souligne) for c in texte]


def textes(lignes: list[Line]) -> list[str]:
    return [l.texte for l in lignes]


def test_retour_a_la_ligne_separe_deux_vers():
    assert textes(lignes_depuis_caracteres(car("le vent se lève\nla mer s'agite"))) == [
        "le vent se lève", "la mer s'agite"]


def test_double_espace_separe_deux_vers_quand_le_texte_est_long():
    texte = "le vent du soir se lève sur la ville  les cloches annoncent le jour"
    assert textes(lignes_depuis_caracteres(car(texte))) == [
        "le vent du soir se lève sur la ville", "les cloches annoncent le jour"]


def test_double_espace_ne_coupe_pas_un_texte_court():
    assert textes(lignes_depuis_caracteres(car("Agneau  Recueil Aurore 2"))) == ["Agneau  Recueil Aurore 2"]


def test_titre_souligne_garde_son_separateur_de_recueil():
    lignes = lignes_depuis_caracteres(car("Pardon   Recueil Aurore 2", gras=True, souligne=True))
    assert len(lignes) == 1 and lignes[0].texte == "Pardon   Recueil Aurore 2"
    assert lignes[0].gras and lignes[0].souligne


def test_espaces_non_soulignees_entre_deux_mots_soulignes_ne_coupent_pas_le_titre():
    caracteres = (car("Gloire", gras=True, souligne=True) + car("   ", gras=True)
                  + car("Recueil Aurore 2", gras=True, souligne=True))
    lignes = lignes_depuis_caracteres(caracteres)
    assert len(lignes) == 1 and lignes[0].souligne


def test_titre_souligne_puis_paroles_dans_le_meme_paragraphe_donnent_deux_lignes():
    caracteres = car("Psaume", gras=True, souligne=True) + car(" ") + car("Le fleuve chante la paix.", gras=True)
    lignes = lignes_depuis_caracteres(caracteres)
    assert textes(lignes) == ["Psaume", "Le fleuve chante la paix."]
    assert lignes[0].souligne and not lignes[1].souligne and lignes[1].gras


def test_une_ligne_est_grasse_si_la_moitie_de_ses_caracteres_le_sont():
    assert lignes_depuis_caracteres(car("abcd", gras=True)[:2] + car("ef"))[0].gras is True       # 2 sur 4
    assert lignes_depuis_caracteres(car("a", gras=True) + car("bcd"))[0].gras is False             # 1 sur 4


def test_italique_et_les_espaces_ne_comptent_pas_dans_la_proportion():
    ligne = lignes_depuis_caracteres(car("ab", italique=True) + car("   ") + car("cd", italique=True))[0]
    assert ligne.italique is True


def test_texte_vide_ou_blanc_ne_donne_aucune_ligne():
    assert lignes_depuis_caracteres([]) == []
    assert lignes_depuis_caracteres(car("  \n  ")) == []
