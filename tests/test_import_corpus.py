"""
Test « corpus » : les vrais fichiers de la paroisse. Il ne tourne que sur le poste qui les possède
(le dépôt est public : aucun de ces fichiers, ni leurs paroles, n'est versionné).

    CHANTS_CORPUS             dossier des fichiers (défaut : G:\\Mon Drive\\Chants)
    CHANTS_FEUILLE_REFERENCE  feuille de référence « Dimanche 04 octobre 2026.docx »
                              (défaut : le dossier Téléchargements)
"""

import os
from pathlib import Path

import pytest

from context.models import MomentLiturgique as M
from context.models import TypeSection
from tools.import_chants.importer import analyser_fichier
from tools.import_chants.modeles import UnsupportedFile

CORPUS = Path(os.environ.get("CHANTS_CORPUS", r"G:\Mon Drive\Chants"))
FEUILLE = Path(os.environ.get(
    "CHANTS_FEUILLE_REFERENCE", str(Path.home() / "Downloads" / "Dimanche 04 octobre 2026.docx")))

FICHIERS = sorted(p for p in CORPUS.glob("*") if p.suffix.lower() in (".docx", ".pdf")) if CORPUS.is_dir() else []
# Partitions (police de notation) et scans, qui doivent être refusés
REFUSES = {
    "agneau messe de la joie.pdf", "alleluia messe de la joie.pdf", "anamnese messe de la joie.pdf",
    "gloire a dieu messe de la joie.pdf", "je n ai que ma priere.pdf", "kirie messe de la joie.pdf",
    "pu messe de la joie.pdf", "sanctus messe de la joie.pdf", "que-vienne-ton-regne.pdf",
    "hosanna exo.pdf", "c est ton sang qui purifie.pdf",
}

corpus_local = pytest.mark.skipif(not FICHIERS, reason="corpus local absent")


@corpus_local
@pytest.mark.parametrize("chemin", FICHIERS, ids=[p.name for p in FICHIERS])
def test_aucun_fichier_ne_fait_planter_l_analyse(chemin):
    try:
        resultat = analyser_fichier(chemin.name, chemin.read_bytes())
    except UnsupportedFile:
        assert chemin.suffix.lower() == ".pdf", "un fichier Word ne doit jamais être refusé"
        return
    for chant in resultat.chants:
        assert chant.titre.strip() and chant.structure
        assert set(chant.ordre) <= {s.id for s in chant.structure}


@corpus_local
def test_partitions_et_scans_sont_refuses():
    presents = [p for p in FICHIERS if p.name.lower() in REFUSES]
    assert presents, "aucune partition trouvée dans le corpus"
    for chemin in presents:
        with pytest.raises(UnsupportedFile):
            analyser_fichier(chemin.name, chemin.read_bytes())


@pytest.mark.skipif(not FEUILLE.is_file(), reason="feuille de référence absente")
def test_feuille_de_reference_du_4_octobre_2026():
    resultat = analyser_fichier(FEUILLE.name, FEUILLE.read_bytes())
    assert [c.moment for c in resultat.chants] == [
        M.ENTREE, M.PARDON, M.GLOIRE, M.PSAUME, M.ALLELUIA, M.PU, M.SANCTUS, M.ANAMNESE, M.AGNEAU, M.COMMUNION]
    avec_refrain = [c.moment for c in resultat.chants
                    if any(s.type is TypeSection.REFRAIN for s in c.structure)]
    assert avec_refrain == [M.ENTREE, M.PARDON, M.GLOIRE, M.PSAUME, M.SANCTUS, M.COMMUNION]
    assert any("Sortie" in n for n in resultat.notes)  # le renvoi « VOIR CHANT D'ENTREE » n'est pas un chant
    entree = resultat.chants[0]
    assert entree.ordre == ["R", "1", "R", "2", "R", "P", "R"]
