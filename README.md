# ⛪ Générateur de PowerPoint Paroissial

Application web (Streamlit) pour générer des présentations PowerPoint de messes : textes liturgiques (AELF) et chants, avec choix de l’ordre et du thème visuel.

## Fonctionnalités

- **Récupération des lectures** : connexion à l’API AELF pour une date donnée (1ère lecture, psaume, 2e lecture, évangile).
- **Bibliothèque de chants** : base SQLite pour gérer titres, paroles, références et moments liturgiques.
- **Ordre personnalisable** : réorganisation des blocs (monter/descendre) avant génération.
- **Thème visuel** : fond foncé / texte clair ou fond clair / texte foncé ; couleurs différenciées pour textes et chants.
- **Export PPTX** : génération d’un PowerPoint 16:9, découpage intelligent du texte (~50 mots par slide).

## Prérequis

- Python 3.11+
- Ou Docker / Docker Compose

## Installation et lancement (sans Docker)

```bash
# Cloner le dépôt
git clone https://github.com/Haneks/PowerPoint-Docker-Messe.git
cd PowerPoint-Docker-Messe

# Créer un environnement virtuel (recommandé)
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # Linux / macOS

# Installer les dépendances
pip install -r requirements.txt

# Lancer l’application
streamlit run app.py
```

Ouvrir [http://localhost:8501](http://localhost:8501).

## Lancement avec Docker

```bash
# Construction et démarrage
docker compose up --build

# En arrière-plan
docker compose up -d --build
```

L’application est accessible sur [http://localhost:8501](http://localhost:8501).

- **Données** : répertoire `./data` (base SQLite des chants).
- **Fichiers générés** : répertoire `./output` (fichiers PPTX).

Pour utiliser des volumes nommés au lieu de dossiers locaux, adapter la section `volumes` dans `docker-compose.yml`.

## Variables d’environnement (Docker)

| Variable   | Description              | Défaut (hors Docker) |
|-----------|--------------------------|-----------------------|
| `DATA_DIR`   | Répertoire de la base chants | `./data`              |
| `OUTPUT_DIR` | Répertoire des PPTX générés  | `./output`            |

## Structure du projet

```
.
├── app.py              # Interface Streamlit
├── args/
│   └── config.yaml     # Configuration (design, API AELF, découpage)
├── context/            # Modèles et schéma DB
├── tools/              # API AELF, générateur PPTX, base chants
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Configuration

Le fichier `args/config.yaml` permet de modifier notamment :

- **Présentation** : format 16:9 ou 4:3
- **Design** : couleurs de fond (textes / chants), polices, tailles
- **Thèmes** : palettes `dark` et `light` (fond foncé/clair)
- **Découpage** : nombre max de mots par slide, séparateurs
- **API AELF** : URL, zone, timeout

## Licence

Voir le dépôt pour toute précision sur la licence.
