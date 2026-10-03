"""Les tests ne doivent jamais toucher la vraie bibliothèque ni le dossier de sortie."""

import os
import tempfile

# Avant tout import de tools.db_handler / app, qui lisent ces variables à l'import.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="powermesia-data-"))
os.environ.setdefault("OUTPUT_DIR", tempfile.mkdtemp(prefix="powermesia-out-"))
