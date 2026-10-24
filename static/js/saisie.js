/**
 * Note View - Contrôle interactif de la saisie des notes.
 * - Refus immédiat de toute valeur hors de 0 à 20 (champ rouge, message, bouton bloqué)
 * - Calcul en direct de la moyenne de la classe
 * - Aucun innerHTML utilisé (sécurité XSS)
 */
document.addEventListener("DOMContentLoaded", () => {
  const formSaisie = document.getElementById("form-saisie");
  if (!formSaisie) return;

  const champs = Array.from(formSaisie.querySelectorAll(".champ-note"));
  const boutonEnregistrer = document.getElementById("bouton-enregistrer");
  const elMoyenneDirect = document.getElementById("moyenne-direct");
  const elNombreNotes = document.getElementById("nombre-notes");
  const elMessageForm = document.getElementById("message-formulaire");

  const MOTIF_NOTE = /^\d{1,2}([.,]\d{1,2})?$/;

  /**
   * Analyse une valeur textuelle et renvoie { valide, vide, note, erreur }
   */
  function evaluerValeur(texte) {
    const brut = (texte === null || texte === undefined) ? "" : String(texte).trim();
    if (!brut) {
      return { valide: true, vide: true, note: null, erreur: "" };
    }
    if (!MOTIF_NOTE.test(brut)) {
      return { valide: false, vide: false, note: null, erreur: "Format invalide (ex: 12 ou 14.5)." };
    }
    const nombre = parseFloat(brut.replace(",", "."));
    if (isNaN(nombre) || !isFinite(nombre) || nombre < 0 || nombre > 20) {
      return { valide: false, vide: false, note: null, erreur: "La note doit être entre 0 et 20." };
    }
    return { valide: true, vide: false, note: nombre, erreur: "" };
  }

  /**
   * Valide un champ individuel et met à jour son style et son message.
   */
  function validerChamp(input) {
    const messageId = input.getAttribute("aria-describedby");
    const messageEl = messageId ? document.getElementById(messageId) : null;
    const res = evaluerValeur(input.value);

    if (res.valide) {
      input.classList.remove("champ--invalide");
      input.removeAttribute("aria-invalid");
      if (messageEl) messageEl.textContent = "";
      return true;
    } else {
      input.classList.add("champ--invalide");
      input.setAttribute("aria-invalid", "true");
      if (messageEl) messageEl.textContent = res.erreur;
      return false;
    }
  }

  /**
   * Recalcule la moyenne en direct et actualise l'état du bouton d'envoi.
   */
  function recalculerDirect() {
    let nbInvalides = 0;
    let sommeNotes = 0;
    let nbNotes = 0;

    champs.forEach((champ) => {
      const res = evaluerValeur(champ.value);
      if (!res.valide) {
        nbInvalides++;
      } else if (!res.vide) {
        sommeNotes += res.note;
        nbNotes++;
      }
    });

    // Mise à jour de la moyenne en direct
    if (elMoyenneDirect) {
      if (nbNotes > 0) {
        const moyenne = (sommeNotes / nbNotes).toFixed(2).replace(".", ",");
        elMoyenneDirect.textContent = `${moyenne}/20`;
      } else {
        elMoyenneDirect.textContent = "—";
      }
    }

    if (elNombreNotes) {
      if (nbNotes > 0) {
        elNombreNotes.textContent = ` (${nbNotes} note${nbNotes > 1 ? "s" : ""} renseignée${nbNotes > 1 ? "s" : ""})`;
      } else {
        elNombreNotes.textContent = "";
      }
    }

    // Gestion du bouton d'envoi et du message global
    if (nbInvalides > 0) {
      if (boutonEnregistrer) {
        boutonEnregistrer.disabled = true;
        boutonEnregistrer.setAttribute("aria-disabled", "true");
      }
      if (elMessageForm) {
        elMessageForm.textContent = `${nbInvalides} note(s) invalide(s) : corrigez les champs en rouge avant d'enregistrer.`;
      }
    } else {
      if (boutonEnregistrer) {
        boutonEnregistrer.disabled = false;
        boutonEnregistrer.removeAttribute("aria-disabled");
      }
      if (elMessageForm) {
        elMessageForm.textContent = "";
      }
    }
  }

  // Écouteurs sur chaque champ de note
  champs.forEach((champ) => {
    champ.addEventListener("input", () => {
      validerChamp(champ);
      recalculerDirect();
    });
    champ.addEventListener("blur", () => {
      validerChamp(champ);
      recalculerDirect();
    });
  });

  // Blocage à la soumission si un champ est invalide
  formSaisie.addEventListener("submit", (e) => {
    let tousValides = true;
    champs.forEach((champ) => {
      if (!validerChamp(champ)) {
        tousValides = false;
      }
    });
    recalculerDirect();
    if (!tousValides) {
      e.preventDefault();
      const premierInvalide = formSaisie.querySelector(".champ--invalide");
      if (premierInvalide) premierInvalide.focus();
    }
  });

  // Calcul initial au chargement de la page
  champs.forEach((champ) => validerChamp(champ));
  recalculerDirect();

  // --- Formulaires de correction individuelle (section pliante) ---
  document.querySelectorAll(".form-correction").forEach((form) => {
    const input = form.querySelector(".champ-note");
    const bouton = form.querySelector("button[type='submit']");
    const messageId = input ? input.getAttribute("aria-describedby") : null;
    const messageEl = messageId ? document.getElementById(messageId) : null;

    if (!input || !bouton) return;

    function verifierCorrection() {
      const res = evaluerValeur(input.value);
      if (!res.valide || res.vide) {
        input.classList.add("champ--invalide");
        bouton.disabled = true;
        if (messageEl) {
          messageEl.textContent = res.vide ? "Saisissez une note." : res.erreur;
        }
        return false;
      }
      input.classList.remove("champ--invalide");
      bouton.disabled = false;
      if (messageEl) messageEl.textContent = "";
      return true;
    }

    input.addEventListener("input", verifierCorrection);
    form.addEventListener("submit", (e) => {
      if (!verifierCorrection()) {
        e.preventDefault();
        input.focus();
      }
    });
  });
});
