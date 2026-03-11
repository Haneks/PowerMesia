-- Schéma SQL pour la bibliothèque de chants (SQLite)
-- Utilisé par db_handler.py

CREATE TABLE IF NOT EXISTS chants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titre TEXT NOT NULL,
    paroles TEXT NOT NULL,
    auteur TEXT,
    compositeur TEXT,
    reference TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chant_moments (
    chant_id INTEGER NOT NULL,
    moment TEXT NOT NULL CHECK (moment IN ('entree', 'offertoire', 'communion', 'envoi', 'autre')),
    PRIMARY KEY (chant_id, moment),
    FOREIGN KEY (chant_id) REFERENCES chants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chants_titre ON chants(titre);
CREATE INDEX IF NOT EXISTS idx_chants_reference ON chants(reference);
CREATE INDEX IF NOT EXISTS idx_chant_moments_moment ON chant_moments(moment);
