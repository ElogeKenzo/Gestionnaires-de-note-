"""
Note View - Portail de notes d'un lycée technique.

Application Flask (Python 3, SQLite via sqlite3, gabarits Jinja2).
Lancement : python app.py puis ouvrir http://127.0.0.1:5000
"""

import math
import os
import re
import secrets
import sqlite3
import time
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_BASE = os.path.join(DOSSIER, "projet.db")

SEQUENCE_MIN, SEQUENCE_MAX = 1, 6
NOTE_MIN, NOTE_MAX = 0, 20

# Formats attendus à la connexion élève : matricule 24GI0001, code à 4 chiffres
MOTIF_MATRICULE = re.compile(r"\d{2}[A-Z]{2}\d{4}")
MOTIF_CODE = re.compile(r"\d{4}")

# Format strict de note : 1 ou 2 chiffres, suivi optionnellement de 1 ou 2 décimales
MOTIF_NOTE = re.compile(r"^\d{1,2}([.,]\d{1,2})?$")

# Anti-bruteforce : 5 échecs consécutifs -> blocage 5 minutes (300 secondes)
ECHECS_MAX = 5
DUREE_BLOCAGE_SECONDES = 300

# En mémoire : { (type_compte, identifiant): {"nb_echecs": int, "bloque_jusqu_a": float} }
TENTATIVES_CONNEXION = {}


def verifier_tentatives(type_compte, identifiant, maintenant=None):
    """Vérifie si un identifiant est bloqué temporairement après 5 échecs consécutifs."""
    if not identifiant:
        return None
    if maintenant is None:
        maintenant = time.time()
    cle = (type_compte, identifiant)
    info = TENTATIVES_CONNEXION.get(cle)
    if not info:
        return None
    bloque_jusqu_a = info.get("bloque_jusqu_a", 0)
    if maintenant < bloque_jusqu_a:
        secondes_restantes = bloque_jusqu_a - maintenant
        minutes = max(1, math.ceil(secondes_restantes / 60))
        return f"Trop de tentatives, réessayez dans {minutes} minute(s)."
    if bloque_jusqu_a and maintenant >= bloque_jusqu_a:
        TENTATIVES_CONNEXION.pop(cle, None)
    return None


def enregistrer_echec(type_compte, identifiant, maintenant=None):
    """Enregistre un échec de connexion. Active le blocage de 5 min au bout de 5 échecs."""
    if not identifiant:
        return
    if maintenant is None:
        maintenant = time.time()
    cle = (type_compte, identifiant)
    info = TENTATIVES_CONNEXION.get(cle, {"nb_echecs": 0, "bloque_jusqu_a": 0})
    if info.get("bloque_jusqu_a") and maintenant >= info["bloque_jusqu_a"]:
        info = {"nb_echecs": 0, "bloque_jusqu_a": 0}
    info["nb_echecs"] = info.get("nb_echecs", 0) + 1
    if info["nb_echecs"] >= ECHECS_MAX:
        info["bloque_jusqu_a"] = maintenant + DUREE_BLOCAGE_SECONDES
    TENTATIVES_CONNEXION[cle] = info


def reinitialiser_tentatives(type_compte, identifiant):
    """Réinitialise le compteur d'échecs après une connexion réussie."""
    if identifiant:
        TENTATIVES_CONNEXION.pop((type_compte, identifiant), None)


app = Flask(__name__)
# Clé secrète de signature des cookies de session : variable d'environnement
# si elle existe, sinon clé aléatoire (les sessions expirent au redémarrage).
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")


# ---------------------------------------------------------------------------
# Protection CSRF sans nouvelle dépendance
# ---------------------------------------------------------------------------

def generer_csrf_token():
    """Génère ou récupère le jeton CSRF de la session."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]


@app.before_request
def verifier_csrf():
    """Initialise le jeton CSRF et valide toute requête POST."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    if request.method == "POST":
        jeton_recu = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        jeton_session = session.get("csrf_token")
        if not jeton_recu or not jeton_session or not secrets.compare_digest(str(jeton_recu), str(jeton_session)):
            abort(400, description="Jeton CSRF invalide ou manquant.")


# ---------------------------------------------------------------------------
# Accès à la base de données
# ---------------------------------------------------------------------------

def get_db():
    """Renvoie la connexion SQLite de la requête en cours (créée au besoin)."""
    if "db" not in g:
        g.db = sqlite3.connect(CHEMIN_BASE)
        g.db.row_factory = sqlite3.Row          # accès aux colonnes par leur nom
        g.db.execute("PRAGMA foreign_keys = ON")  # à activer à CHAQUE connexion
    return g.db


@app.teardown_appcontext
def fermer_db(_exception):
    """Ferme la connexion à la fin de chaque requête."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Calculs : moyennes et rangs (réutilisés par le bulletin, la liste de classe,
# l'historique, l'API et les statistiques)
# ---------------------------------------------------------------------------

# Moyenne coefficientée de chaque élève pour UNE séquence :
#   somme(note × coefficient) / somme(coefficients des matières notées),
# arrondie à 2 décimales. Les matières sans note ne comptent pas.
# Cette requête constante sert de base (sous-requête) à tous les calculs :
# l'arrondi est ainsi identique partout. Le seul paramètre (?) est la séquence.
SQL_MOYENNES = """
    SELECT n.eleve_id                                            AS eleve_id,
           e.classe_id                                           AS classe_id,
           ROUND(SUM(n.note * m.coefficient) * 1.0 / SUM(m.coefficient), 2)
                                                                 AS moyenne
    FROM notes n
    JOIN eleves   e ON e.id = n.eleve_id
    JOIN matieres m ON m.id = n.matiere_id
    WHERE n.sequence = ?
    GROUP BY n.eleve_id
"""


def attribuer_rangs(resultats):
    """Trie les élèves par moyenne décroissante et ajoute 'rang' et 'ex_aequo'.

    Classement « avec ex æquo » : deux élèves à 12,50 ont le même rang et le
    suivant prend le rang correspondant à sa position (1, 2, 2, 4).
    Les moyennes comparées sont déjà arrondies à 2 décimales.
    Les élèves sans moyenne (aucune note) sont placés à la fin, sans rang.
    """
    notes = sorted((r for r in resultats if r["moyenne"] is not None),
                   key=lambda r: r["moyenne"], reverse=True)
    sans_note = [r for r in resultats if r["moyenne"] is None]

    rang, moyenne_precedente = 0, None
    for position, eleve in enumerate(notes, start=1):
        if eleve["moyenne"] != moyenne_precedente:
            rang, moyenne_precedente = position, eleve["moyenne"]
        eleve["rang"] = rang

    # Un élève est ex æquo si un autre élève partage exactement son rang
    occurrences = {}
    for eleve in notes:
        occurrences[eleve["rang"]] = occurrences.get(eleve["rang"], 0) + 1
    for eleve in notes:
        eleve["ex_aequo"] = occurrences[eleve["rang"]] > 1
    for eleve in sans_note:
        eleve["rang"], eleve["ex_aequo"] = None, False
    return notes + sans_note


def resultats_classe(classe_id, sequence):
    """Moyenne et rang de tous les élèves d'une classe pour une séquence.

    Renvoie une liste de dictionnaires triée par rang :
    {eleve_id, matricule, nom, prenom, moyenne, rang, ex_aequo}.
    """
    lignes = get_db().execute(
        f"""SELECT e.id AS eleve_id, e.matricule, e.nom, e.prenom, mo.moyenne
            FROM eleves e
            LEFT JOIN ({SQL_MOYENNES}) mo ON mo.eleve_id = e.id
            WHERE e.classe_id = ?
            ORDER BY e.nom, e.prenom""",
        (sequence, classe_id),
    ).fetchall()
    return attribuer_rangs([dict(ligne) for ligne in lignes])


def resultat_eleve(eleve_id, classe_id, sequence):
    """Moyenne, rang et effectif classé d'un élève pour une séquence.

    Renvoie {moyenne, rang, ex_aequo, effectif} ; moyenne et rang valent None
    si l'élève n'a aucune note pour cette séquence.
    """
    resultats = resultats_classe(classe_id, sequence)
    effectif = sum(1 for r in resultats if r["moyenne"] is not None)
    for r in resultats:
        if r["eleve_id"] == eleve_id:
            return {"moyenne": r["moyenne"], "rang": r["rang"],
                    "ex_aequo": r["ex_aequo"], "effectif": effectif}
    return {"moyenne": None, "rang": None, "ex_aequo": False, "effectif": effectif}


def appreciation(moyenne):
    """Appréciation automatique selon la moyenne sur 20."""
    if moyenne is None:
        return "Non évalué"
    paliers = [(18, "Excellent"), (16, "Très bien"), (14, "Bien"),
               (12, "Assez bien"), (10, "Passable"), (8, "Insuffisant")]
    for seuil, texte in paliers:
        if moyenne >= seuil:
            return texte
    return "Très insuffisant"


def format_rang(rang):
    """Met un rang en forme à la française : 1er, 2e, 3e..."""
    if rang is None:
        return "—"
    return "1er" if rang == 1 else f"{rang}e"


def format_note(valeur):
    """Affiche une note ou une moyenne à la française : 12,50 (ou « — »)."""
    if valeur is None:
        return "—"
    return f"{valeur:.2f}".replace(".", ",")


def valeur_champ(valeur):
    """Valeur d'une note pour pré-remplir un champ de saisie (12.5, 14, ...)."""
    return "" if valeur is None else f"{valeur:g}"


# Filtres et variables disponibles dans tous les gabarits Jinja
app.jinja_env.filters.update(rang=format_rang, note=format_note,
                             appreciation=appreciation, champ=valeur_champ)


@app.context_processor
def injecter_utilisateur():
    """Rend le jeton CSRF, le rôle et le nom de l'utilisateur accessibles aux gabarits."""
    return {"csrf_token": generer_csrf_token(),
            "role": session.get("role"), "nom_utilisateur": session.get("nom"),
            "SEQUENCES": range(SEQUENCE_MIN, SEQUENCE_MAX + 1)}


# ---------------------------------------------------------------------------
# Validation des données reçues (toujours revérifiées côté serveur)
# ---------------------------------------------------------------------------

def lire_sequence(valeur):
    """Convertit une valeur en numéro de séquence (1 à 6) ; None si invalide."""
    try:
        sequence = int(valeur)
    except (TypeError, ValueError):
        return None
    return sequence if SEQUENCE_MIN <= sequence <= SEQUENCE_MAX else None


def sequence_demandee(defaut):
    """Lit le paramètre ?sequence=N : defaut s'il est absent, None s'il est invalide."""
    if "sequence" not in request.args:
        return defaut
    return lire_sequence(request.args["sequence"])


def lire_note(texte):
    r"""Convertit le texte saisi en note sur 20.

    Accepte uniquement les formats ^\d{1,2}([.,]\d{1,2})?$ puis vérifie entre 0 et 20.
    Refuse la notation scientifique, les underscores, nan, inf, -0, les espaces internes.
    """
    if texte is None:
        return None, "La note est obligatoire."
    texte_str = str(texte).strip()
    if not MOTIF_NOTE.fullmatch(texte_str):
        return None, "La note doit être un nombre compris entre 0 et 20."
    try:
        note = float(texte.replace(",", "."))
    except ValueError:
        return None, "La note doit être un nombre."
    if not NOTE_MIN <= note <= NOTE_MAX:
        return None, "La note doit être comprise entre 0 et 20."
    return round(note, 2), None


def derniere_sequence(eleve_id=None):
    """Dernière séquence contenant des notes (pour un élève ou pour tout le lycée)."""
    if eleve_id is None:
        ligne = get_db().execute("SELECT MAX(sequence) FROM notes").fetchone()
    else:
        ligne = get_db().execute(
            "SELECT MAX(sequence) FROM notes WHERE eleve_id = ?", (eleve_id,)).fetchone()
    return ligne[0] or SEQUENCE_MIN


# ---------------------------------------------------------------------------
# Contrôle d'accès
# ---------------------------------------------------------------------------

def connexion_requise(vue):
    """Décorateur des pages enseignant : refuse l'accès sans connexion enseignant.

    Charge l'enseignant connecté dans g.enseignant. Sans connexion valide :
    redirection vers la page de connexion (ou erreur JSON 401 pour l'API).
    """
    @wraps(vue)
    def vue_protegee(*args, **kwargs):
        enseignant = None
        if session.get("role") == "enseignant":
            enseignant = get_db().execute(
                "SELECT id, nom, login FROM enseignants WHERE id = ?",
                (session.get("enseignant_id"),)).fetchone()
        if enseignant is None:
            if request.path.startswith("/api/"):
                return jsonify(erreur="Connexion enseignant requise."), 401
            flash("Veuillez vous connecter avec un compte enseignant.", "erreur")
            return redirect(url_for("connexion_enseignant"))
        g.enseignant = enseignant
        return vue(*args, **kwargs)
    return vue_protegee


def eleve_requis(vue):
    """Décorateur des pages élève : l'identité vient UNIQUEMENT de la session.

    Charge l'élève connecté (et sa classe) dans g.eleve.
    """
    @wraps(vue)
    def vue_protegee(*args, **kwargs):
        eleve = None
        if session.get("role") == "eleve":
            eleve = get_db().execute(
                """SELECT e.id, e.matricule, e.nom, e.prenom, e.date_naissance,
                          e.classe_id, c.nom AS classe, c.filiere
                   FROM eleves e JOIN classes c ON c.id = e.classe_id
                   WHERE e.id = ?""",
                (session.get("eleve_id"),)).fetchone()
        if eleve is None:
            if request.path.startswith("/api/"):
                return jsonify(erreur="Connexion élève requise."), 401
            flash("Veuillez vous connecter avec votre matricule et votre code.", "erreur")
            return redirect(url_for("connexion"))
        g.eleve = eleve
        return vue(*args, **kwargs)
    return vue_protegee


# ---------------------------------------------------------------------------
# Partie publique et élève
# ---------------------------------------------------------------------------

@app.route("/")
def accueil():
    """Page d'accueil."""
    return render_template("index.html")


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    """Connexion élève avec matricule + code personnel (vérifié par hachage)."""
    matricule = ""
    if request.method == "POST":
        matricule = request.form.get("matricule", "").strip().upper()
        code = request.form.get("code", "").strip()

        # Blocage anti-bruteforce (s'applique même avec le bon code si bloqué)
        msg_blocage = verifier_tentatives("eleve", matricule)
        if msg_blocage:
            flash(msg_blocage, "erreur")
            return render_template("connexion.html", matricule=matricule)

        eleve = None
        if MOTIF_MATRICULE.fullmatch(matricule) and MOTIF_CODE.fullmatch(code):
            eleve = get_db().execute(
                "SELECT id, nom, prenom, code_acces_hash FROM eleves WHERE matricule = ?",
                (matricule,)).fetchone()
        if eleve and check_password_hash(eleve["code_acces_hash"], code):
            reinitialiser_tentatives("eleve", matricule)
            session.clear()
            session["csrf_token"] = secrets.token_hex(32)
            session.update(role="eleve", eleve_id=eleve["id"],
                           nom=f"{eleve['prenom']} {eleve['nom']}")
            flash(f"Bienvenue {eleve['prenom']} !", "succes")
            return redirect(url_for("bulletin"))

        enregistrer_echec("eleve", matricule)
        msg_blocage = verifier_tentatives("eleve", matricule)
        if msg_blocage:
            flash(msg_blocage, "erreur")
        else:
            flash("Matricule ou code d'accès incorrect.", "erreur")
    return render_template("connexion.html", matricule=matricule)


@app.route("/deconnexion", methods=["POST"])
def deconnexion():
    """Déconnexion élève : vide la session (méthode POST avec jeton CSRF)."""
    session.clear()
    session["csrf_token"] = secrets.token_hex(32)
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("accueil"))


@app.route("/bulletin")
@eleve_requis
def bulletin():
    """Bulletin de l'élève connecté pour la séquence ?sequence=N."""
    eleve = g.eleve
    sequence = sequence_demandee(derniere_sequence(eleve["id"]))
    if sequence is None:
        flash("Séquence invalide : choisissez une séquence de 1 à 6.", "erreur")
        return redirect(url_for("bulletin"))

    # Toutes les matières, avec la note de l'élève si elle existe
    lignes = get_db().execute(
        """SELECT m.nom AS matiere, m.coefficient, n.note, ens.nom AS enseignant
           FROM matieres m
           JOIN enseignants ens ON ens.id = m.enseignant_id
           LEFT JOIN notes n ON n.matiere_id = m.id AND n.eleve_id = ? AND n.sequence = ?
           ORDER BY m.coefficient DESC, m.nom""",
        (eleve["id"], sequence)).fetchall()
    notees = [l for l in lignes if l["note"] is not None]
    total_points = sum(l["note"] * l["coefficient"] for l in notees)
    total_coefficients = sum(l["coefficient"] for l in notees)

    # Moyenne et rang via les fonctions de calcul communes
    classe = resultats_classe(eleve["classe_id"], sequence)
    moyennes = [r["moyenne"] for r in classe if r["moyenne"] is not None]
    resultat = next(r for r in classe if r["eleve_id"] == eleve["id"])
    return render_template(
        "bulletin.html", eleve=eleve, sequence=sequence, lignes=lignes,
        total_points=total_points, total_coefficients=total_coefficients,
        resultat=resultat, effectif=len(moyennes),
        moyenne_classe=round(sum(moyennes) / len(moyennes), 2) if moyennes else None,
        moyenne_max=max(moyennes, default=None), moyenne_min=min(moyennes, default=None))


def evolution_eleve(eleve):
    """Moyenne, rang et effectif de l'élève pour chaque séquence notée."""
    sequences = get_db().execute(
        "SELECT DISTINCT sequence FROM notes WHERE eleve_id = ? ORDER BY sequence",
        (eleve["id"],)).fetchall()
    evolution = []
    for (sequence,) in sequences:
        resultat = resultat_eleve(eleve["id"], eleve["classe_id"], sequence)
        resultat["sequence"] = sequence
        evolution.append(resultat)
    return evolution


@app.route("/historique")
@eleve_requis
def historique():
    """Moyenne et rang de l'élève connecté pour chaque séquence."""
    return render_template("historique.html", eleve=g.eleve,
                           evolution=evolution_eleve(g.eleve))


# ---------------------------------------------------------------------------
# Partie enseignant
# ---------------------------------------------------------------------------

@app.route("/enseignant/connexion", methods=["GET", "POST"])
def connexion_enseignant():
    """Connexion enseignant (login + mot de passe haché)."""
    login = ""
    if request.method == "POST":
        login = request.form.get("login", "").strip()
        mot_de_passe = request.form.get("mot_de_passe", "")

        # Blocage anti-bruteforce (s'applique même avec le bon mot de passe si bloqué)
        msg_blocage = verifier_tentatives("enseignant", login)
        if msg_blocage:
            flash(msg_blocage, "erreur")
            return render_template("enseignant_connexion.html", login=login)

        enseignant = get_db().execute(
            "SELECT id, nom, mot_de_passe_hash FROM enseignants WHERE login = ?",
            (login,)).fetchone()
        if enseignant and check_password_hash(enseignant["mot_de_passe_hash"], mot_de_passe):
            reinitialiser_tentatives("enseignant", login)
            session.clear()
            session["csrf_token"] = secrets.token_hex(32)
            session.update(role="enseignant", enseignant_id=enseignant["id"],
                           nom=enseignant["nom"])
            flash(f"Bienvenue {enseignant['nom']} !", "succes")
            return redirect(url_for("tableau_de_bord"))

        enregistrer_echec("enseignant", login)
        msg_blocage = verifier_tentatives("enseignant", login)
        if msg_blocage:
            flash(msg_blocage, "erreur")
        else:
            flash("Identifiant ou mot de passe incorrect.", "erreur")
    return render_template("enseignant_connexion.html", login=login)


@app.route("/enseignant/deconnexion", methods=["POST"])
def deconnexion_enseignant():
    """Déconnexion enseignant (méthode POST avec jeton CSRF)."""
    session.clear()
    session["csrf_token"] = secrets.token_hex(32)
    flash("Vous êtes déconnecté.", "info")
    return redirect(url_for("accueil"))


def liste_classes():
    """Toutes les classes avec leur effectif réel."""
    return get_db().execute(
        """SELECT c.id, c.nom, c.filiere, c.effectif_max, COUNT(e.id) AS effectif
           FROM classes c LEFT JOIN eleves e ON e.classe_id = c.id
           GROUP BY c.id ORDER BY c.nom""").fetchall()


@app.route("/enseignant")
@connexion_requise
def tableau_de_bord():
    """Tableau de bord : matières de l'enseignant, classes, avancement de la saisie."""
    db = get_db()
    matieres = db.execute(
        "SELECT id, nom, coefficient FROM matieres WHERE enseignant_id = ? ORDER BY nom",
        (g.enseignant["id"],)).fetchall()
    # Nombre de notes déjà saisies par (matière, classe, séquence)
    lignes = db.execute(
        """SELECT n.matiere_id, e.classe_id, n.sequence, COUNT(*) AS nombre
           FROM notes n
           JOIN eleves e ON e.id = n.eleve_id
           JOIN matieres m ON m.id = n.matiere_id
           WHERE m.enseignant_id = ?
           GROUP BY n.matiere_id, e.classe_id, n.sequence""",
        (g.enseignant["id"],)).fetchall()
    avancement = {(l["matiere_id"], l["classe_id"], l["sequence"]): l["nombre"]
                  for l in lignes}
    return render_template("enseignant_tableau_bord.html", matieres=matieres,
                           classes=liste_classes(), avancement=avancement)


def enregistrer_notes(matiere_id, sequence, notes):
    """Insère ou met à jour des notes, sans doublon, en une seule transaction.

    notes : liste de couples (eleve_id, note). Renvoie (nb_ajouts, nb_mises_a_jour).
    En cas d'erreur (ex : contrainte UNIQUE), tout est annulé et l'exception
    sqlite3.IntegrityError est transmise à l'appelant.
    """
    db = get_db()
    ajouts = mises_a_jour = 0
    with db:  # validation (commit) à la fin, ou annulation (rollback) si erreur
        for eleve_id, note in notes:
            curseur = db.execute(
                """UPDATE notes SET note = ?
                   WHERE eleve_id = ? AND matiere_id = ? AND sequence = ?""",
                (note, eleve_id, matiere_id, sequence))
            if curseur.rowcount:
                mises_a_jour += 1
            else:
                db.execute(
                    """INSERT INTO notes (eleve_id, matiere_id, sequence, note)
                       VALUES (?, ?, ?, ?)""",
                    (eleve_id, matiere_id, sequence, note))
                ajouts += 1
    return ajouts, mises_a_jour


@app.route("/enseignant/saisie/<int:matiere_id>/<int:classe_id>/<int:sequence>",
           methods=["GET", "POST"])
@connexion_requise
def saisie_notes(matiere_id, classe_id, sequence):
    """Saisie des notes d'une matière pour toute une classe (un champ par élève)."""
    db = get_db()
    matiere = db.execute("SELECT id, nom, coefficient, enseignant_id FROM matieres WHERE id = ?",
                         (matiere_id,)).fetchone()
    classe = db.execute("SELECT id, nom FROM classes WHERE id = ?", (classe_id,)).fetchone()
    if matiere is None or classe is None or lire_sequence(sequence) is None:
        abort(404)
    # Contrôle côté serveur : la matière doit appartenir à l'enseignant connecté
    if matiere["enseignant_id"] != g.enseignant["id"]:
        flash("Accès refusé : vous ne pouvez saisir que les notes de vos matières.", "erreur")
        return redirect(url_for("tableau_de_bord"))

    eleves = db.execute(
        """SELECT e.id, e.matricule, e.nom, e.prenom, n.id AS note_id, n.note
           FROM eleves e
           LEFT JOIN notes n ON n.eleve_id = e.id AND n.matiere_id = ? AND n.sequence = ?
           WHERE e.classe_id = ?
           ORDER BY e.nom, e.prenom""",
        (matiere_id, sequence, classe_id)).fetchall()
    page_actuelle = url_for("saisie_notes", matiere_id=matiere_id,
                            classe_id=classe_id, sequence=sequence)
    valeurs, erreurs = {}, {}  # texte saisi et message d'erreur par élève

    if request.method == "POST":
        ids_classe = {e["id"] for e in eleves}
        # Chaque champ doit correspondre à UN élève de la classe, envoyé une seule fois
        for cle in request.form:
            if not cle.startswith("note_"):
                continue
            identifiant = cle[len("note_"):]
            if not identifiant.isdigit() or int(identifiant) not in ids_classe:
                flash("Formulaire refusé : élève inconnu ou absent de cette classe.", "erreur")
                return redirect(page_actuelle)
            if len(request.form.getlist(cle)) > 1:
                flash("Doublon refusé : plusieurs notes envoyées pour le même élève. "
                      "Aucune note n'a été enregistrée.", "erreur")
                return redirect(page_actuelle)

        a_enregistrer = []
        for eleve in eleves:
            texte = request.form.get(f"note_{eleve['id']}", "").strip()
            valeurs[eleve["id"]] = texte
            if not texte:
                continue  # champ vide : pas de note (ou note existante conservée)
            note, erreur = lire_note(texte)
            if erreur:
                erreurs[eleve["id"]] = erreur
            else:
                a_enregistrer.append((eleve["id"], note))

        if erreurs:
            flash(f"{len(erreurs)} note(s) invalide(s) : rien n'a été enregistré. "
                  "Corrigez les champs signalés.", "erreur")
        elif not a_enregistrer:
            flash("Aucune note saisie.", "info")
        else:
            try:
                ajouts, mises_a_jour = enregistrer_notes(matiere_id, sequence, a_enregistrer)
            except sqlite3.IntegrityError:
                flash("Enregistrement refusé : une note existe déjà pour cet élève, "
                      "cette matière et cette séquence. Rechargez la page.", "erreur")
            else:
                flash(f"Notes enregistrées : {ajouts} ajout(s), "
                      f"{mises_a_jour} mise(s) à jour.", "succes")
                return redirect(page_actuelle)

    return render_template("enseignant_saisie.html", matiere=matiere, classe=classe,
                           sequence=sequence, eleves=eleves, valeurs=valeurs,
                           erreurs=erreurs)


@app.route("/enseignant/note/<int:note_id>/corriger", methods=["POST"])
@connexion_requise
def corriger_note(note_id):
    """Correction d'une note existante (uniquement dans une matière de l'enseignant)."""
    db = get_db()
    ligne = db.execute(
        """SELECT n.id, n.matiere_id, n.sequence, e.classe_id, e.nom, e.prenom,
                  m.enseignant_id
           FROM notes n
           JOIN eleves e ON e.id = n.eleve_id
           JOIN matieres m ON m.id = n.matiere_id
           WHERE n.id = ?""", (note_id,)).fetchone()
    if ligne is None:
        abort(404)
    if ligne["enseignant_id"] != g.enseignant["id"]:
        flash("Accès refusé : cette note ne concerne pas une de vos matières.", "erreur")
        return redirect(url_for("tableau_de_bord"))

    note, erreur = lire_note(request.form.get("note"))
    if erreur:
        flash(f"Correction refusée pour {ligne['prenom']} {ligne['nom']} : {erreur}", "erreur")
    else:
        with db:
            db.execute("UPDATE notes SET note = ? WHERE id = ?", (note, note_id))
        flash(f"Note de {ligne['prenom']} {ligne['nom']} corrigée : "
              f"{format_note(note)}/20.", "succes")
    return redirect(url_for("saisie_notes", matiere_id=ligne["matiere_id"],
                            classe_id=ligne["classe_id"], sequence=ligne["sequence"]))


@app.route("/enseignant/classe/<int:classe_id>")
@connexion_requise
def liste_classe(classe_id):
    """Liste d'une classe avec moyennes et rangs pour une séquence."""
    classe = get_db().execute("SELECT id, nom, filiere FROM classes WHERE id = ?",
                              (classe_id,)).fetchone()
    if classe is None:
        abort(404)
    sequence = sequence_demandee(derniere_sequence())
    if sequence is None:
        flash("Séquence invalide : choisissez une séquence de 1 à 6.", "erreur")
        return redirect(url_for("liste_classe", classe_id=classe_id))
    resultats = resultats_classe(classe_id, sequence)
    moyennes = [r["moyenne"] for r in resultats if r["moyenne"] is not None]
    return render_template(
        "enseignant_classe.html", classe=classe, sequence=sequence, resultats=resultats,
        effectif=len(moyennes),
        moyenne_classe=round(sum(moyennes) / len(moyennes), 2) if moyennes else None,
        nb_reussite=sum(1 for m in moyennes if m >= 10))


# ---------------------------------------------------------------------------
# Phase 5 : Statistiques (requêtes SQL paramétrées)
# ---------------------------------------------------------------------------

def calculer_statistiques(sequence):
    """Calcule les 4 statistiques du lycée pour une séquence donnée.

    1. Moyenne générale et taux de réussite (moyenne >= 10) par classe.
    2. Moyenne de chaque matière par classe.
    3. Les 3 premiers de chaque classe (avec gestion des ex æquo).
    4. Répartition des moyennes par tranches.
    """
    db = get_db()

    # 1. Moyenne générale et taux de réussite (>= 10) par classe
    lignes_reussite = db.execute(
        f"""SELECT c.id AS classe_id, c.nom AS classe, c.filiere,
                   COUNT(mo.eleve_id) AS effectif,
                   ROUND(AVG(mo.moyenne), 2) AS moyenne_generale,
                   SUM(CASE WHEN mo.moyenne >= 10 THEN 1 ELSE 0 END) AS nb_reussite,
                   CASE WHEN COUNT(mo.eleve_id) > 0
                        THEN ROUND(SUM(CASE WHEN mo.moyenne >= 10 THEN 1.0 ELSE 0.0 END) * 100.0 / COUNT(mo.eleve_id), 1)
                        ELSE 0.0 END AS taux_reussite
            FROM classes c
            LEFT JOIN ({SQL_MOYENNES}) mo ON mo.classe_id = c.id
            GROUP BY c.id
            ORDER BY c.nom""",
        (sequence,),
    ).fetchall()
    reussite_par_classe = [dict(l) for l in lignes_reussite]

    # 2. Moyenne de chaque matière par classe
    lignes_matieres = db.execute(
        """SELECT c.id AS classe_id, c.nom AS classe, m.id AS matiere_id, m.nom AS matiere,
                  m.coefficient,
                  ROUND(AVG(n.note), 2) AS moyenne
           FROM classes c
           CROSS JOIN matieres m
           LEFT JOIN eleves e ON e.classe_id = c.id
           LEFT JOIN notes n ON n.eleve_id = e.id AND n.matiere_id = m.id AND n.sequence = ?
           GROUP BY c.id, m.id
           ORDER BY c.nom, m.nom""",
        (sequence,),
    ).fetchall()
    matieres_par_classe = [dict(l) for l in lignes_matieres]

    # 3. Les 3 premiers de chaque classe (rang <= 3, gestion des ex æquo)
    trois_premiers = {}
    classes = db.execute("SELECT id, nom FROM classes ORDER BY nom").fetchall()
    for cl in classes:
        res = resultats_classe(cl["id"], sequence)
        trois_premiers[cl["nom"]] = [
            r for r in res if r["rang"] is not None and r["rang"] <= 3
        ]

    # 4. Répartition des moyennes par tranches
    lignes_tranches = db.execute(
        f"""SELECT c.id AS classe_id, c.nom AS classe,
                   SUM(CASE WHEN mo.moyenne < 8 THEN 1 ELSE 0 END) AS moins_de_8,
                   SUM(CASE WHEN mo.moyenne >= 8 AND mo.moyenne < 10 THEN 1 ELSE 0 END) AS de_8_a_10,
                   SUM(CASE WHEN mo.moyenne >= 10 AND mo.moyenne < 12 THEN 1 ELSE 0 END) AS de_10_a_12,
                   SUM(CASE WHEN mo.moyenne >= 12 AND mo.moyenne < 14 THEN 1 ELSE 0 END) AS de_12_a_14,
                   SUM(CASE WHEN mo.moyenne >= 14 THEN 1 ELSE 0 END) AS plus_de_14,
                   COUNT(mo.eleve_id) AS total
            FROM classes c
            LEFT JOIN ({SQL_MOYENNES}) mo ON mo.classe_id = c.id
            GROUP BY c.id
            ORDER BY c.nom""",
        (sequence,),
    ).fetchall()
    tranches_par_classe = [dict(l) for l in lignes_tranches]

    return {
        "sequence": sequence,
        "reussite_par_classe": reussite_par_classe,
        "matieres_par_classe": matieres_par_classe,
        "trois_premiers": trois_premiers,
        "tranches_par_classe": tranches_par_classe,
    }


@app.route("/enseignant/statistiques")
@connexion_requise
def statistiques():
    """Page des statistiques du lycée pour une séquence donnée."""
    sequence = sequence_demandee(derniere_sequence())
    if sequence is None:
        flash("Séquence invalide : choisissez une séquence de 1 à 6.", "erreur")
        return redirect(url_for("statistiques"))
    stats = calculer_statistiques(sequence)
    classes = get_db().execute("SELECT id, nom FROM classes ORDER BY nom").fetchall()
    matieres = get_db().execute("SELECT id, nom, coefficient FROM matieres ORDER BY nom").fetchall()
    moy_mat = {(m["classe_id"], m["matiere_id"]): m["moyenne"] for m in stats["matieres_par_classe"]}
    return render_template(
        "enseignant_statistiques.html",
        sequence=sequence,
        stats=stats,
        classes=classes,
        matieres=matieres,
        moy_mat=moy_mat,
    )


# ---------------------------------------------------------------------------
# Phase 6 : API JSON (jsonify)
# ---------------------------------------------------------------------------

@app.route("/api/classe/<int:classe_id>/moyennes")
@connexion_requise
def api_classe_moyennes(classe_id):
    """Moyennes et rangs des élèves de la classe (réservée à l'enseignant)."""
    classe = get_db().execute("SELECT id, nom, filiere FROM classes WHERE id = ?", (classe_id,)).fetchone()
    if classe is None:
        return jsonify(erreur="Classe introuvable."), 404
    sequence = sequence_demandee(derniere_sequence())
    if sequence is None:
        return jsonify(erreur="Séquence invalide : choisissez une séquence entre 1 et 6."), 400
    resultats = resultats_classe(classe_id, sequence)
    return jsonify({
        "classe_id": classe["id"],
        "classe": classe["nom"],
        "filiere": classe["filiere"],
        "sequence": sequence,
        "eleves": resultats,
    })


@app.route("/api/eleve/evolution")
@eleve_requis
def api_eleve_evolution():
    """Moyennes de l'élève connecté par séquence (pour le graphique Chart.js)."""
    eleve = g.eleve
    evolution = evolution_eleve(eleve)
    return jsonify({
        "eleve_id": eleve["id"],
        "matricule": eleve["matricule"],
        "nom": f"{eleve['prenom']} {eleve['nom']}",
        "classe": eleve["classe"],
        "evolution": evolution,
    })


@app.route("/api/statistiques")
@connexion_requise
def api_statistiques():
    """Statistiques du lycée au format JSON (réservée à l'enseignant)."""
    sequence = sequence_demandee(derniere_sequence())
    if sequence is None:
        return jsonify(erreur="Séquence invalide : choisissez une séquence entre 1 et 6."), 400
    stats = calculer_statistiques(sequence)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Gestion des erreurs
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def requete_invalide(erreur):
    """Erreur 400 personnalisée (ex : jeton CSRF invalide ou manquant)."""
    description = getattr(erreur, "description", "Requête invalide.")
    if request.path.startswith("/api/"):
        return jsonify(erreur=description), 400
    return render_template("400.html", description=description), 400


@app.errorhandler(404)
def page_introuvable(_erreur):
    """Page 404 personnalisée (réponse JSON pour les adresses de l'API)."""
    if request.path.startswith("/api/"):
        return jsonify(erreur="Ressource introuvable."), 404
    return render_template("404.html"), 404


if __name__ == "__main__":
    if not os.path.exists(CHEMIN_BASE):
        print("Base projet.db introuvable : lancez d'abord « python donnees_test.py ».")
    else:
        app.run(debug=False)
