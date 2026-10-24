"""
Note View - Script d'exportation de la base de données.

Exporte l'intégralité du schéma et des données de projet.db dans un fichier
SQL autonome (export_projet.sql) à l'aide de la méthode standard iterdump().

Lancement : python exporter.py
"""

import os
import sqlite3

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_BASE = os.path.join(DOSSIER, "projet.db")
CHEMIN_EXPORT = os.path.join(DOSSIER, "export_projet.sql")


def exporter_base():
    """Génère l'export SQL complet de projet.db via db.iterdump()."""
    if not os.path.exists(CHEMIN_BASE):
        raise FileNotFoundError(
            f"Base de données introuvable ({CHEMIN_BASE}). Lancez d'abord « python donnees_test.py »."
        )

    db = sqlite3.connect(CHEMIN_BASE)
    db.execute("PRAGMA foreign_keys = ON")

    with open(CHEMIN_EXPORT, "w", encoding="utf-8") as f:
        f.write("-- =====================================================================\n")
        f.write("-- Note View - Export complet de la base de données projet.db\n")
        f.write("-- Généré automatiquement via sqlite3 iterdump()\n")
        f.write("-- =====================================================================\n\n")
        f.write("PRAGMA foreign_keys = ON;\n\n")
        for ligne in db.iterdump():
            f.write(f"{ligne}\n")

    db.close()
    taille = os.path.getsize(CHEMIN_EXPORT)
    print(f"Export réussi : {CHEMIN_EXPORT} ({taille} octets)")


if __name__ == "__main__":
    exporter_base()
