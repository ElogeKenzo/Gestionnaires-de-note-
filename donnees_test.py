"""
Note View - Génération des données de test.

Ce script :
  1. supprime puis recrée la base projet.db à partir de schema.sql ;
  2. la remplit avec des données réalistes et reproductibles (random.seed(42)) :
     4 classes, 120 élèves, 7 enseignants, 8 matières, notes des séquences 1 et 2 ;
  3. affiche quelques comptes de test et le nombre de lignes de chaque table.

Lancement : python donnees_test.py
"""

import os
import random
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

# Chemins des fichiers (relatifs au dossier du script)
DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_BASE = os.path.join(DOSSIER, "projet.db")
CHEMIN_SCHEMA = os.path.join(DOSSIER, "schema.sql")

# Graine fixe : les mêmes données (et les mêmes codes d'accès) à chaque exécution
random.seed(42)

# ---------------------------------------------------------------------------
# Données de référence
# ---------------------------------------------------------------------------

# (nom, filière, effectif maximal, année de naissance la plus ancienne)
CLASSES = [
    ("1re année F3", "F3 - Électrotechnique", 40, 2009),
    ("2e année F3", "F3 - Électrotechnique", 40, 2008),
    ("1re année G1", "G1 - Techniques administratives", 40, 2009),
    ("2e année G2", "G2 - Techniques quantitatives de gestion", 40, 2008),
]

# (nom affiché, login, mot de passe en clair) : documentés dans le README
ENSEIGNANTS = [
    ("Paul ABENA", "prof", "Prof!2026"),
    ("Mireille NGONO", "ngono", "Ngono!2026"),
    ("Hervé TCHOUPO", "tchoupo", "Tchoupo!2026"),
    ("Clarisse ESSOMBA", "essomba", "Essomba!2026"),
    ("Ibrahim OUMAROU", "oumarou", "Oumarou!2026"),
    ("Landry FOTSO", "fotso", "Fotso!2026"),
    ("Grâce MBALLA", "mballa", "Mballa!2026"),
]

# (nom de la matière, coefficient, login de l'enseignant responsable)
MATIERES = [
    ("Mathématiques", 4, "prof"),
    ("Informatique", 3, "prof"),
    ("Français", 3, "ngono"),
    ("Anglais", 2, "tchoupo"),
    ("Histoire-Géographie", 2, "essomba"),
    ("Économie générale", 2, "oumarou"),
    ("Technologie professionnelle", 5, "fotso"),
    ("Éducation physique et sportive", 1, "mballa"),
]

NOMS = [
    "MBARGA", "NKOULOU", "ETOUNDI", "FOTSO", "KAMGA", "TCHOUPO", "NDJOCK",
    "ABENA", "ESSOMBA", "ONANA", "MBALLA", "NANA", "DJOUMESSI", "TAGNE",
    "WAMBA", "NGONO", "ATANGANA", "BELLA", "EYENGA", "MANGA", "OWONA", "ZANG",
    "KENFACK", "TCHAKOUNTE", "NGUEMO", "SIMO", "TALLA", "NGASSA", "MOUKOURI",
    "EKOTTO", "DOUMBE", "EWANE", "BAYIHA", "NDONGO", "HAMADOU", "ABOUBAKAR",
    "BOUBA", "OUMAROU", "NJOYA", "MOUNCHILI", "FOUDA", "NOAH", "MESSI",
    "TSALA", "EBOGO", "NGUELE", "YOMBI", "KOUOH",
]

PRENOMS = [
    "Jean-Paul", "Brice", "Cédric", "Junior", "Arnaud", "Ulrich", "Franck",
    "Hervé", "Landry", "Serge", "Rodrigue", "Yannick", "Boris", "Stéphane",
    "Christian", "Ibrahim", "Abdoulaye", "Moussa", "Patrick", "Thierry",
    "Aïcha", "Grâce", "Mireille", "Larissa", "Carine", "Sandrine", "Ornella",
    "Nadège", "Vanessa", "Danielle", "Laure", "Murielle", "Flore", "Estelle",
    "Rachelle", "Clarisse", "Josiane", "Hadiza", "Fadimatou", "Prisca",
]

ELEVES_PAR_CLASSE = 30
SEQUENCES_REMPLIES = (1, 2)

# Valeurs extrêmes injectées pour tester les cas limites (0, 20, ...)
NOTES_EXTREMES = [0, 0.5, 1.5, 2, 18.5, 19, 19.75, 20]


def note_realiste(niveau):
    """Tire une note sur 20 autour du niveau de l'élève, arrondie au quart de point."""
    valeur = random.gauss(11.5 + niveau, 2.5)
    valeur = min(20, max(0, valeur))
    return round(valeur * 4) / 4


def date_naissance_aleatoire(annee_min):
    """Renvoie une date de naissance (AAAA-MM-JJ) sur deux années à partir de annee_min."""
    debut = date(annee_min, 1, 1)
    return (debut + timedelta(days=random.randint(0, 729))).isoformat()


def creer_base():
    """Supprime l'ancienne base et la recrée vide à partir de schema.sql."""
    if os.path.exists(CHEMIN_BASE):
        os.remove(CHEMIN_BASE)
    db = sqlite3.connect(CHEMIN_BASE)
    db.execute("PRAGMA foreign_keys = ON")
    with open(CHEMIN_SCHEMA, encoding="utf-8") as fichier:
        db.executescript(fichier.read())
    return db


def inserer_enseignants_et_matieres(db):
    """Insère les enseignants (mots de passe hachés) et leurs matières."""
    ids_enseignants = {}
    for nom, login, mot_de_passe in ENSEIGNANTS:
        curseur = db.execute(
            "INSERT INTO enseignants (nom, login, mot_de_passe_hash) VALUES (?, ?, ?)",
            (nom, login, generate_password_hash(mot_de_passe)),
        )
        ids_enseignants[login] = curseur.lastrowid

    ids_matieres = []
    for nom, coefficient, login in MATIERES:
        curseur = db.execute(
            "INSERT INTO matieres (nom, coefficient, enseignant_id) VALUES (?, ?, ?)",
            (nom, coefficient, ids_enseignants[login]),
        )
        ids_matieres.append(curseur.lastrowid)
    return ids_matieres


def inserer_classes_et_eleves(db):
    """Insère les classes et 30 élèves par classe. Renvoie les comptes créés."""
    comptes = []  # liste de dicts : id, matricule, nom, prenom, code, classe
    numero = 0
    for nom_classe, filiere, effectif_max, annee_min in CLASSES:
        classe_id = db.execute(
            "INSERT INTO classes (nom, filiere, effectif_max) VALUES (?, ?, ?)",
            (nom_classe, filiere, effectif_max),
        ).lastrowid

        noms_utilises = set()
        for _ in range(ELEVES_PAR_CLASSE):
            # On évite deux élèves homonymes dans la même classe
            while True:
                nom, prenom = random.choice(NOMS), random.choice(PRENOMS)
                if (nom, prenom) not in noms_utilises:
                    noms_utilises.add((nom, prenom))
                    break
            numero += 1
            matricule = f"24GI{numero:04d}"
            code = f"{random.randint(0, 9999):04d}"  # code personnel à 4 chiffres
            eleve_id = db.execute(
                """INSERT INTO eleves (matricule, nom, prenom, classe_id,
                                       date_naissance, code_acces_hash)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (matricule, nom, prenom, classe_id,
                 date_naissance_aleatoire(annee_min), generate_password_hash(code)),
            ).lastrowid
            comptes.append({"id": eleve_id, "matricule": matricule, "nom": nom,
                            "prenom": prenom, "code": code, "classe": nom_classe,
                            "classe_id": classe_id})
    return comptes


def generer_notes(comptes, ids_matieres):
    """Construit le dictionnaire des notes {(eleve_id, matiere_id, sequence): note}."""
    notes = {}
    for eleve in comptes:
        niveau = random.gauss(0, 2.2)  # niveau propre à l'élève (bon / moyen / faible)
        for sequence in SEQUENCES_REMPLIES:
            for matiere_id in ids_matieres:
                notes[(eleve["id"], matiere_id, sequence)] = note_realiste(niveau)

    # Quelques valeurs extrêmes pour tester les bornes (chacune utilisée 2 fois)
    for index, cle in enumerate(random.sample(sorted(notes), 2 * len(NOTES_EXTREMES))):
        notes[cle] = NOTES_EXTREMES[index % len(NOTES_EXTREMES)]
    return notes


def creer_ex_aequo(notes, comptes, ids_matieres):
    """Copie les notes d'un élève sur un autre de la même classe : moyennes identiques.

    Dans chaque classe, le 6e élève reçoit exactement les notes du 11e.
    Dans la 1re classe, le 16e élève les reçoit aussi (triple égalité).
    Renvoie la liste des groupes d'élèves à égalité (pour l'affichage final).
    """
    groupes = []
    for debut in range(0, len(comptes), ELEVES_PAR_CLASSE):
        classe = comptes[debut:debut + ELEVES_PAR_CLASSE]
        modele, copies = classe[10], [classe[5]]
        if debut == 0:
            copies.append(classe[15])
        for copie in copies:
            for sequence in SEQUENCES_REMPLIES:
                for matiere_id in ids_matieres:
                    notes[(copie["id"], matiere_id, sequence)] = \
                        notes[(modele["id"], matiere_id, sequence)]
        groupes.append([modele] + copies)
    return groupes


def main():
    db = creer_base()
    ids_matieres = inserer_enseignants_et_matieres(db)
    comptes = inserer_classes_et_eleves(db)
    notes = generer_notes(comptes, ids_matieres)
    groupes_ex_aequo = creer_ex_aequo(notes, comptes, ids_matieres)

    db.executemany(
        "INSERT INTO notes (eleve_id, matiere_id, sequence, note) VALUES (?, ?, ?, ?)",
        [(e, m, s, n) for (e, m, s), n in sorted(notes.items())],
    )
    db.commit()

    # --- Affichage des comptes de test (codes en clair, uniquement ici) ---
    print("Comptes élèves de test (matricule / code) :")
    for debut in range(0, len(comptes), ELEVES_PAR_CLASSE):
        for eleve in comptes[debut:debut + 2]:
            print(f"  {eleve['matricule']}  code {eleve['code']}  "
                  f"{eleve['nom']} {eleve['prenom']} ({eleve['classe']})")
    print("Élèves à égalité exacte (ex æquo) :")
    for groupe in groupes_ex_aequo:
        print("  " + " = ".join(
            f"{e['matricule']} (code {e['code']})" for e in groupe))

    # --- Nombre de lignes de chaque table ---
    print("Nombre de lignes par table :")
    for table in ("classes", "eleves", "enseignants", "matieres", "notes"):
        # Nom de table issu d'une liste fixe du programme (aucune donnée utilisateur)
        total = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<12} {total}")
    db.close()


if __name__ == "__main__":
    main()
