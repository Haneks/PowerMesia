# Roadmap - Générateur de PowerPoint Paroissial

> Développement selon le framework ATLAS

## Phase 1 : Architect (Objectifs & Planification)

### 1.1 Définition des objectifs
- [x] Arborescence GOTCHA définie
- [ ] Roadmap validée
- [ ] Processus de génération documenté

### 1.2 Processus de génération
1. **Sélection** : Date de la messe → Appel API AELF
2. **Enrichissement** : Ajout des chants depuis la bibliothèque locale
3. **Ordonnancement** : Ajustement de l'ordre des blocs (lectures + chants)
4. **Validation** : Prévisualisation par l'utilisateur
5. **Génération** : Création du fichier .pptx

### 1.3 Étapes de validation
- Validation de la date avant appel API
- Vérification de la présence des lectures
- Confirmation de l'ordre final avant export

---

## Phase 2 : Trace (Modèles de données)

### 2.1 Contexte
- [x] Schéma `Chant` pour la bibliothèque
- [x] Modèles AELF mappés (Lecture, Psaume, Évangile)
- [ ] Règles typographiques documentées

### 2.2 Mapping des lectures AELF
| Type API   | Libellé          | Clé interne   |
|------------|------------------|---------------|
| lecture_1  | Première lecture | premiere_lecture |
| psaume     | Psaume           | psaume        |
| lecture_2  | Deuxième lecture | deuxieme_lecture |
| evangile   | Évangile         | evangile      |

---

## Phase 3 : Link (Configuration & API)

### 3.1 Configuration
- [ ] Fichier `args/config.yaml` (couleurs, polices, endpoints)
- [ ] Test de connexion API AELF
- [ ] Gestion des zones (france, romain)

### 3.2 Endpoints AELF
- `GET /v1/messes/{date}/{zone}` → Données complètes de la messe
- `GET /v1/informations/{date}/{zone}` → Métadonnées liturgiques

---

## Phase 4 : Assemble (Outils & Interface)

### 4.1 Tools
- [ ] `aelf_service.py` — Client API
- [ ] `pptx_generator.py` — Génération PowerPoint (python-pptx)
- [ ] `db_handler.py` — CRUD bibliothèque chants (SQLite)

### 4.2 Interface Streamlit
- [ ] Sélecteur de date
- [ ] Affichage des lectures récupérées
- [ ] Recherche et sélection des chants
- [ ] Prévisualisation / réorganisation des blocs
- [ ] Bouton de génération PPTX

---

## Phase 5 : Stress-test (Orchestration)

### 5.1 Script principal
- [ ] `orchestration/main.py` — Enchaînement des étapes
- [ ] Gestion des erreurs (API, fichiers, base)
- [ ] Logging et feedback utilisateur

---

## Phase 6 : Hardprompts (Formatage)

### 6.1 Découpage intelligent
- [ ] Ne jamais couper un mot
- [ ] Priorité : point > point-virgule > virgule > espace
- [ ] Calcul lignes max par slide (taille 28)
- [ ] Titre de rappel sur chaque slide (suite)

---

## Livrables finaux
- Application Streamlit fonctionnelle
- Fichier PPTX avec fond foncé, texte blanc, police 28
- Bibliothèque de chants exploitable (CRUD)
