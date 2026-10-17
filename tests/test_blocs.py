"""Blocs de la messe : identifiants stables, ordre, suppression, libellés de la liste glissable."""

from tools.blocs import (
    appliquer_ordre,
    apercu_bloc,
    assurer_uid,
    elements_liste,
    libelle_bloc,
    supprimer_bloc,
)


def _blocs():
    return [
        {"uid": "a", "ordre": 0, "type": "lecture", "lecture_type": "lecture_1", "reference": "Is 55, 6-9"},
        {"uid": "b", "ordre": 1, "type": "chant", "titre": "Chant B"},
        {"uid": "c", "ordre": 2, "type": "lecture", "lecture_type": "evangile", "reference": "Mt 20, 1-16"},
    ]


def _uids(blocs):
    return [b["uid"] for b in blocs]


# --- identifiants -----------------------------------------------------------------------------

def test_assurer_uid_donne_un_identifiant_unique_aux_blocs_qui_n_en_ont_pas():
    blocs = [{"type": "chant"}, {"type": "chant"}, {"uid": "garde", "type": "chant"}]
    assurer_uid(blocs)
    assert blocs[2]["uid"] == "garde"
    assert len({b["uid"] for b in blocs}) == 3
    assert all(b["uid"] for b in blocs)


def test_assurer_uid_ne_change_pas_les_identifiants_existants_quand_on_le_rappelle():
    blocs = [{"type": "chant"}, {"type": "chant"}]
    assurer_uid(blocs)
    avant = _uids(blocs)
    assurer_uid(blocs)
    assert _uids(blocs) == avant


# --- ordre ------------------------------------------------------------------------------------

def test_appliquer_ordre_reordonne_les_blocs():
    assert _uids(appliquer_ordre(_blocs(), ["c", "a", "b"])) == ["c", "a", "b"]


def test_appliquer_ordre_renumerote_le_champ_ordre():
    assert [b["ordre"] for b in appliquer_ordre(_blocs(), ["c", "a", "b"])] == [0, 1, 2]


def test_appliquer_ordre_n_efface_jamais_un_bloc_absent_de_la_liste_recue():
    # « d » a été ajouté après l'envoi de l'ordre : il doit rester, en fin de liste.
    blocs = _blocs() + [{"uid": "d", "ordre": 3, "type": "chant", "titre": "Ajouté après"}]
    assert _uids(appliquer_ordre(blocs, ["c", "a", "b"])) == ["c", "a", "b", "d"]


def test_appliquer_ordre_ignore_les_identifiants_inconnus_et_les_doublons():
    assert _uids(appliquer_ordre(_blocs(), ["zzz", "c", "c", "a", "b"])) == ["c", "a", "b"]


def test_appliquer_ordre_avec_une_liste_vide_garde_l_ordre_actuel():
    assert _uids(appliquer_ordre(_blocs(), [])) == ["a", "b", "c"]


def test_appliquer_ordre_ne_modifie_pas_la_liste_d_origine():
    blocs = _blocs()
    appliquer_ordre(blocs, ["c", "a", "b"])
    assert _uids(blocs) == ["a", "b", "c"]


# --- suppression ------------------------------------------------------------------------------

def test_supprimer_bloc_retire_le_bon_bloc_et_renumerote():
    restants = supprimer_bloc(_blocs(), "b")
    assert _uids(restants) == ["a", "c"]
    assert [b["ordre"] for b in restants] == [0, 1]


def test_supprimer_bloc_inconnu_ne_change_rien():
    assert _uids(supprimer_bloc(_blocs(), "zzz")) == ["a", "b", "c"]


def test_supprimer_bloc_ne_modifie_pas_la_liste_d_origine():
    blocs = _blocs()
    supprimer_bloc(blocs, "b")
    assert _uids(blocs) == ["a", "b", "c"]


# --- libellés ---------------------------------------------------------------------------------

def test_libelle_d_une_lecture_donne_son_type_et_sa_reference():
    assert libelle_bloc({"type": "lecture", "lecture_type": "lecture_1", "reference": "Is 55, 6-9"}) == "1ère lecture — Is 55, 6-9"
    assert libelle_bloc({"type": "lecture", "lecture_type": "psaume", "reference": "Ps 144"}) == "Psaume — Ps 144"
    assert libelle_bloc({"type": "lecture", "lecture_type": "lecture_2", "reference": "Ph 1"}) == "2e lecture — Ph 1"
    assert libelle_bloc({"type": "lecture", "lecture_type": "evangile", "reference": "Mt 20"}) == "Évangile — Mt 20"


def test_libelle_d_une_lecture_sans_reference_ni_type():
    assert libelle_bloc({"type": "lecture"}) == "1ère lecture — Sans ref"


def test_libelle_d_un_chant_ou_d_un_autre_bloc():
    assert libelle_bloc({"type": "chant", "titre": "Je te donne mon cœur"}) == "Chant — Je te donne mon cœur"
    assert libelle_bloc({"type": "message", "titre": "Annonces"}) == "Message — Annonces"
    assert libelle_bloc({"type": "chant"}) == "Chant — Bloc"


# --- aperçu -----------------------------------------------------------------------------------

def test_apercu_d_une_lecture_retire_les_balises_et_decode_les_entites():
    bloc = {"type": "lecture", "contenu": "<p>Cherchez&nbsp;le Seigneur ;<br />invoquez-le &amp; priez.</p>"}
    assert apercu_bloc(bloc) == "Cherchez le Seigneur ; invoquez-le & priez."


def test_apercu_tronque_avec_une_ellipse():
    apercu = apercu_bloc({"type": "lecture", "contenu": "mot " * 100}, longueur=20)
    assert len(apercu) == 20
    assert apercu.endswith("…")


def test_apercu_court_n_est_pas_tronque():
    assert apercu_bloc({"type": "lecture", "contenu": "Texte court"}, longueur=20) == "Texte court"


def test_apercu_d_un_chant_est_sa_premiere_ligne_non_vide():
    bloc = {"type": "chant", "paroles": "\n\nPremière ligne\nDeuxième ligne"}
    assert apercu_bloc(bloc) == "Première ligne"


def test_apercu_est_vide_quand_il_n_y_a_rien_a_montrer():
    assert apercu_bloc({"type": "message", "titre": "Annonces"}) == ""
    assert apercu_bloc({"type": "lecture"}) == ""
    assert apercu_bloc({"type": "chant", "paroles": None}) == ""


# --- liste pour le composant ------------------------------------------------------------------

def test_elements_liste_fournit_id_titre_et_apercu():
    blocs = [
        {"uid": "a", "type": "lecture", "lecture_type": "evangile", "reference": "Mt 20", "contenu": "<p>Texte</p>"},
        {"uid": "b", "type": "chant", "titre": "Chant B", "paroles": "Ligne 1\nLigne 2"},
    ]
    assert elements_liste(blocs) == [
        {"id": "a", "titre": "Évangile — Mt 20", "apercu": "Texte"},
        {"id": "b", "titre": "Chant — Chant B", "apercu": "Ligne 1"},
    ]
