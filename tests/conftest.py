"""Les tests ne doivent jamais toucher la vraie bibliothèque ni le dossier de sortie."""

import os
import tempfile

# Avant tout import de tools.db_handler / app, qui lisent ces variables à l'import.
# Affectation directe (pas setdefault) : une variable déjà exportée dans le shell ne doit
# jamais faire pointer les tests vers une vraie bibliothèque.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="powermesia-data-")
os.environ["OUTPUT_DIR"] = tempfile.mkdtemp(prefix="powermesia-out-")
