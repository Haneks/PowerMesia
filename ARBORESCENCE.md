# Arborescence complète - Générateur de PowerPoint Paroissial

```
powerpoint-paroissial/
├── goals/                    # Architect - Processus et validation
│   └── roadmap.md
│
├── orchestration/            # Stress-test - Logique globale
│   └── main.py
│
├── tools/                    # Assemble - Outils métier
│   ├── aelf_service.py       # Client API AELF
│   ├── pptx_generator.py     # Génération PowerPoint (python-pptx)
│   └── db_handler.py         # Bibliothèque de chants (SQLite/JSON)
│
├── context/                  # Trace - Schémas et règles
│   └── models.py
│
├── hardprompts/              # Formatage et découpage
│   └── slicing_rules.md
│
├── args/                     # Link - Configuration
│   └── config.yaml
│
├── data/                     # Données persistantes
│   └── chants.db             # (créé à l'exécution)
│
├── app.py                    # Point d'entrée Streamlit
├── requirements.txt
└── README.md
```

## Mapping ATLAS

| Dossier      | Phase ATLAS | Rôle                                      |
|--------------|-------------|-------------------------------------------|
| goals/       | Architect   | Définition processus, étapes validation   |
| orchestration/ | Stress-test | Enchaînement étapes, gestion d'erreurs  |
| tools/       | Assemble    | aelf_service, pptx_generator, db_handler |
| context/     | Trace       | Modèles Chant, Lecture, BlocMesse        |
| hardprompts/ | -           | Règles découpage intelligent             |
| args/        | Link        | config.yaml (API, design, DB)            |
