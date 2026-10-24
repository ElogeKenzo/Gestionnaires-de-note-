# Note View — Portail de notes d'un lycée technique

**Note View** est une application web complète permettant aux enseignants d'un lycée technique de saisir rapidement les notes des élèves et à chaque élève de consulter son bulletin officiel, son classement avec gestion des ex æquo et son historique de progression sous forme de graphique.

---

## 1. Choix d'implémentation et arbitrage des ambiguïtés

1. **Rangs et ex æquo** : Deux ou plusieurs élèves ayant la même moyenne coefficientée arrondie à 2 décimales partagent le même rang (ex. 5e, 5e et 5e). L'élève suivant prend le rang correspondant à son classement réel (ici 8e), selon la règle standard (1, 2, 2, 4 ou 5, 5, 5, 8).
2. **Identification de l'élève** : L'identité de l'élève provient **strictement de la session** côté serveur (`session['eleve_id']`). Aucun identifiant d'élève n'apparaît dans l'URL du bulletin ; un élève ne peut en aucun cas consulter les notes d'un camarade.
3. **Périmètre des enseignants** : Un enseignant ne peut saisir ou corriger les notes que pour les matières dont il est le responsable attitré (`matieres.enseignant_id`). Toute tentative d'accès à une matière tierce est bloquée côté serveur.
4. **Calcul de la moyenne coefficientée** : Seules les matières effectivement notées sont prises en compte dans le diviseur des coefficients. Si un élève n'a aucune note pour une séquence, son statut est affiché « Non évalué » sans provoquer d'erreur arithmétique.
5. **Chart.js autonome** : La bibliothèque graphique est présente localement dans `static/js/chart.umd.js` pour garantir un fonctionnement complet hors ligne.

---

## 2. Prérequis et Stack technique

- **Python** : version 3.10 ou supérieure (testé sous Python 3.13)
- **Framework** : Flask (Werkzeug inclus)
- **Base de données** : SQLite 3 via le module natif `sqlite3` (sans ORM)
- **Gabarits** : Jinja2 (avec échappement automatique anti-XSS)
- **Front-end** : HTML5 sémantique, Vanilla CSS (mobile-first, avec `print.css`), JavaScript natif (`fetch`, `textContent`, Chart.js UMD)

---

## 3. Installation et Lancement

### Étape 1 : Création de l'environnement virtuel

Ouvrez un terminal dans le dossier `projet/` :

```bash
# Windows / Linux / macOS
python -m venv venv
```

### Étape 2 : Activation de l'environnement virtuel

- **Sous Windows (PowerShell)** :
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
- **Sous Windows (Invite de commandes cmd)** :
  ```cmd
  venv\Scripts\activate.bat
  ```
- **Sous Linux / macOS (Bash / Zsh)** :
  ```bash
  source venv/bin/activate
  ```

### Étape 3 : Installation des dépendances

```bash
pip install -r requirements.txt
```

### Étape 4 : Lancement de l'application

La base `projet.db` est déjà préremplie et prête à l'emploi.

```bash
python app.py
```

Ouvrez ensuite votre navigateur à l'adresse :
👉 **http://127.0.0.1:5000**

---

## 4. Recréation des données de test et export

Si vous souhaitez régénérer une base de données propre avec des données aléatoires mais reproductibles (`seed 42`) :

```bash
python donnees_test.py
```

Pour régénérer l'export SQL complet (`export_projet.sql`) via `sqlite3.iterdump()` :

```bash
python exporter.py
```

---

## 5. Comptes de test

### Enseignants

Tous les mots de passe sont hachés en base (algorithme scrypt via Werkzeug) :

| Nom enseignant | Login | Mot de passe | Matière(s) enseignée(s) |
|---|---|---|---|
| **Paul ABENA** | `prof` | `Prof!2026` | Mathématiques (coef 4), Informatique (coef 3) |
| **Mireille NGONO** | `ngono` | `Ngono!2026` | Français (coef 3) |
| **Hervé TCHOUPO** | `tchoupo` | `Tchoupo!2026` | Anglais (coef 2) |
| **Clarisse ESSOMBA** | `essomba` | `Essomba!2026` | Histoire-Géographie (coef 2) |
| **Ibrahim OUMAROU** | `oumarou` | `Oumarou!2026` | Économie générale (coef 2) |
| **Landry FOTSO** | `fotso` | `Fotso!2026` | Technologie professionnelle (coef 5) |
| **Grâce MBALLA** | `mballa` | `Mballa!2026` | Éducation physique et sportive (coef 1) |

### Élèves de test

Les codes d'accès à 4 chiffres sont hachés en base :

| Classe | Matricule | Code | Nom & Prénom |
|---|---|---|---|
| **1re année F3** | `24GI0001` | `0409` | Hervé FOUDA |
| **1re année F3** | `24GI0002` | `2286` | Christian NGONO |
| **2e année F3** | `24GI0031` | `7019` | Hadiza KOUOH |
| **2e année F3** | `24GI0032` | `3593` | Larissa SIMO |
| **1re année G1** | `24GI0061` | `9440` | Josiane YOMBI |
| **1re année G1** | `24GI0062` | `6669` | Laure NGONO |
| **2e année G2** | `24GI0091` | `8288` | Stéphane HAMADOU |
| **2e année G2** | `24GI0092` | `1127` | Mireille ESSOMBA |

### Élèves configurés à égalité exacte (test des ex æquo)

Pour constater la gestion conforme des ex æquo (même rang partagé, saut de position pour le suivant) :

- En **1re année F3** (triple égalité, rang 5e ex æquo à 13,19/20) :
  - `24GI0011` (code `1584`) = `24GI0006` (code `3257`) = `24GI0016` (code `0750`)
- En **2e année F3** (double égalité, rang 7e ex æquo à 13,72/20) :
  - `24GI0041` (code `8201`) = `24GI0036` (code `7668`)
- En **1re année G1** :
  - `24GI0071` (code `1528`) = `24GI0066` (code `1790`)
- En **2e année G2** :
  - `24GI0101` (code `0722`) = `24GI0096` (code `4333`)

---

## 6. Table des routes

| Méthode | Route URL | Rôle / Accès | Description |
|---|---|---|---|
| `GET` | `/` | Public | Page d'accueil avec présentation de Note View et liens d'accès |
| `GET`, `POST` | `/connexion` | Public / Élève | Authentification élève par matricule + code à 4 chiffres |
| `POST` | `/deconnexion` | Élève | Déconnexion élève (suppression de la session) |
| `GET` | `/bulletin?sequence=N` | Élève connecté | Bulletin officiel de la séquence (notes, coefs, moyenne, rang, appréciation) |
| `GET` | `/historique` | Élève connecté | Tableau de suivi des séquences et graphique d'évolution Chart.js |
| `GET`, `POST` | `/enseignant/connexion` | Public / Enseignant | Authentification enseignant par login + mot de passe |
| `POST` | `/enseignant/deconnexion` | Enseignant | Déconnexion enseignant (suppression de la session) |
| `GET` | `/enseignant` | Enseignant connecté | Tableau de bord : matières attribuées, avancement par classe/séquence |
| `GET`, `POST` | `/enseignant/saisie/<matiere_id>/<classe_id>/<sequence>` | Enseignant connecté | Saisie complète des notes d'une classe (contrôle de propriété de la matière) |
| `POST` | `/enseignant/note/<note_id>/corriger` | Enseignant connecté | Correction unitaire d'une note existante (revérifiée côté serveur) |
| `GET` | `/enseignant/classe/<classe_id>?sequence=N` | Enseignant connecté | Liste de classe avec moyennes calculées et rangs officiels |
| `GET` | `/enseignant/statistiques?sequence=N` | Enseignant connecté | Page des 4 statistiques officielles du lycée |
| `GET` | `/api/classe/<classe_id>/moyennes?sequence=N` | Enseignant connecté | JSON : liste ordonnée des moyennes et rangs d'une classe |
| `GET` | `/api/eleve/evolution` | Élève connecté | JSON : historique des moyennes et rangs pour le graphique Chart.js |
| `GET` | `/api/statistiques?sequence=N` | Enseignant connecté | JSON : indicateurs statistiques complets du lycée (accès réservé aux enseignants connectés, 401 sinon) |
| `*` | `404` | Tous | Gestionnaire d'erreur 404 personnalisé (HTML ou JSON selon la route) |

---

## 7. Fonctionnalités détaillées

### Espace Élève
- **Connexion sécurisée** avec vérification côté client du format (matricule 8 caractères, code 4 chiffres) et côté serveur avec `check_password_hash`.
- **Bulletin de notes officiel** :
  - Affichage des notes par matière, coefficients et points pondérés.
  - Calcul de la moyenne coefficientée : $\frac{\sum (\text{note} \times \text{coef})}{\sum \text{coef}}$.
  - Rang dans la classe avec indication des ex æquo.
  - Appréciation automatisée selon le barème officiel du lycée technique.
  - Statistiques de comparaison (moyenne de classe, note max, note min).
  - Formule détaillée de calcul en pied de page pour transparence totale.
  - Bouton **« Imprimer le bulletin »** optimisé pour papier A4 via `print.css`.
- **Suivi d'évolution** :
  - Synthèse tabulaire séquence par séquence.
  - Graphique linéaire interactif Chart.js généré dynamiquement via `fetch('/api/eleve/evolution')`.

### Espace Enseignant
- **Tableau de bord ergonomique** :
  - Liste des matières enseignées.
  - Matrice des classes avec pastilles d'avancement colorées (vert = complet, orange = partiel, gris = vide).
- **Page de saisie collective des notes** :
  - Formulaire unique présentant l'ensemble des élèves de la classe.
  - Validation interactive instantanée en JavaScript : refus des valeurs hors de 0 à 20 (contour rouge, message ciblé, désactivation du bouton d'envoi).
  - Calcul en temps réel de la moyenne de la classe dans cette matière au fur et à mesure de la frappe.
  - Traitement transactionnel côté serveur : insertion ou mise à jour sans doublon.
  - Protection contre les doublons ou envois malveillants.
- **Statistiques d'établissement (Phase 5)** :
  1. Taux de réussite (moyenne $\ge$ 10) et moyenne générale par classe.
  2. Moyenne de chaque matière par classe (matrice croisée).
  3. Les 3 premiers de chaque classe avec gestion fidèle des ex æquo.
  4. Répartition des moyennes par tranches (<8, [8,10[, [10,12[, [12,14[, $\ge$14).

---

## 8. Dispositif de sécurité

- **Requêtes paramétrées** : 100 % des interactions SQLite utilisent des marqueurs `?`. Aucune f-string ni concaténation SQL n'est utilisée avec des données utilisateur.
- **Clés étrangères activées** : `PRAGMA foreign_keys = ON` est exécuté à chaque ouverture de connexion SQLite.
- **Contrôle d'accès strict** :
  - L'élève ne peut jamais accéder aux données d'un autre élève (l'identité vient de la session chiffrée côté serveur).
  - L'enseignant ne peut jamais saisir ou modifier des notes d'une matière appartenant à un confrère.
- **Hachage cryptographique** : Les mots de passe et codes d'accès sont hachés avec le standard Werkzeug (`scrypt`). Aucun mot de passe n'est stocké en clair.
- **Protection XSS** : Les gabarits Jinja2 n'utilisent aucun filtre `|safe`. Côté JavaScript, tout contenu dynamique est injecté avec `textContent` (aucun `innerHTML` sur des données variables).
- **Protection CSRF sans dépendance externe** : un jeton cryptographique aléatoire (`secrets.token_hex(32)`) est stocké en session et injecté dans tous les gabarits via un `context_processor`. Chaque formulaire POST (connexion élève, connexion enseignant, saisie des notes, corrections unitaires, déconnexions) inclut ce jeton en champ caché (`csrf_token`). Un hook global `@app.before_request` intercepte toutes les requêtes POST et valide le jeton avec `secrets.compare_digest` ; tout jeton manquant ou erroné est rejeté avec une erreur HTTP 400 personnalisée.
- **Limitation des tentatives de connexion (anti force-brute)** : après 5 échecs consécutifs sur un même matricule élève ou login enseignant, l'identifiant est temporairement verrouillé pendant 5 minutes avec le message clair « Trop de tentatives, réessayez dans X minute(s). ». Les tentatives sont mémorisées en mémoire (dictionnaire horodaté). Le compteur est remis à zéro dès qu'une authentification réussit. Le blocage reste actif même si le bon code/mot de passe est saisi tant que le délai n'est pas écoulé.
- **Session sécurisée et clé secrète** : Cookie de session configuré avec `HttpOnly=True` et `SameSite=Lax`. La clé secrète de session Flask est régénérée aléatoirement au démarrage (`secrets.token_hex(32)`) sauf si la variable d'environnement `SECRET_KEY` est définie.
