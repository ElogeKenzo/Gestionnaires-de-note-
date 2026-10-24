-- =====================================================================
-- Note View - Portail de notes d'un lycée technique
-- Schéma de la base de données SQLite
-- =====================================================================

-- Active la vérification des clés étrangères (désactivée par défaut dans SQLite).
-- Remarque : ce PRAGMA est aussi exécuté à CHAQUE connexion dans app.py.
PRAGMA foreign_keys = ON;

-- On supprime les tables dans l'ordre inverse des dépendances
-- pour pouvoir recréer la base proprement.
DROP TABLE IF EXISTS notes;
DROP TABLE IF EXISTS matieres;
DROP TABLE IF EXISTS eleves;
DROP TABLE IF EXISTS enseignants;
DROP TABLE IF EXISTS classes;

-- ---------------------------------------------------------------------
-- Table des classes (ex : « 2e année F3 »)
-- ---------------------------------------------------------------------
CREATE TABLE classes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nom           TEXT    NOT NULL UNIQUE,                       -- nom unique de la classe
    filiere       TEXT    NOT NULL,                              -- filière (F3, G1, ...)
    effectif_max  INTEGER NOT NULL CHECK (effectif_max > 0)      -- capacité maximale
);

-- ---------------------------------------------------------------------
-- Table des élèves
-- Le code d'accès n'est JAMAIS stocké en clair : uniquement son hachage.
-- ---------------------------------------------------------------------
CREATE TABLE eleves (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    matricule        TEXT    NOT NULL UNIQUE,                    -- ex : 24GI0001
    nom              TEXT    NOT NULL,
    prenom           TEXT    NOT NULL,
    classe_id        INTEGER NOT NULL REFERENCES classes (id),  -- classe de l'élève
    date_naissance   TEXT    NOT NULL,                           -- format AAAA-MM-JJ
    code_acces_hash  TEXT    NOT NULL                            -- code à 4 chiffres haché
);

-- ---------------------------------------------------------------------
-- Table des enseignants
-- ---------------------------------------------------------------------
CREATE TABLE enseignants (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nom                TEXT NOT NULL,
    login              TEXT NOT NULL UNIQUE,                     -- identifiant de connexion
    mot_de_passe_hash  TEXT NOT NULL                             -- mot de passe haché
);

-- ---------------------------------------------------------------------
-- Table des matières : chaque matière a un coefficient et un enseignant
-- ---------------------------------------------------------------------
CREATE TABLE matieres (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT    NOT NULL UNIQUE,
    coefficient    INTEGER NOT NULL CHECK (coefficient > 0),
    enseignant_id  INTEGER NOT NULL REFERENCES enseignants (id)  -- enseignant responsable
);

-- ---------------------------------------------------------------------
-- Table des notes : une seule note par élève, par matière et par séquence
-- ---------------------------------------------------------------------
CREATE TABLE notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    eleve_id    INTEGER NOT NULL REFERENCES eleves (id) ON DELETE CASCADE,
    matiere_id  INTEGER NOT NULL REFERENCES matieres (id) ON DELETE CASCADE,
    sequence    INTEGER NOT NULL CHECK (sequence BETWEEN 1 AND 6),   -- 6 séquences par an
    note        REAL    NOT NULL CHECK (note BETWEEN 0 AND 20),      -- note sur 20
    UNIQUE (eleve_id, matiere_id, sequence)                          -- pas de doublon
);

-- Index pour accélérer les recherches fréquentes (jointures et filtres)
CREATE INDEX idx_eleves_classe   ON eleves (classe_id);
CREATE INDEX idx_matieres_ens    ON matieres (enseignant_id);
CREATE INDEX idx_notes_sequence  ON notes (sequence, matiere_id);
