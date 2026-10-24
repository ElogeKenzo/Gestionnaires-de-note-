/**
 * Note View - Validation des formulaires de connexion (élève et enseignant).
 * Vérification avant envoi pour guider immédiatement l'utilisateur.
 * Aucun innerHTML utilisé (sécurité XSS).
 */
document.addEventListener("DOMContentLoaded", () => {
  // --- Formulaire élève ---
  const formEleve = document.getElementById("form-connexion-eleve");
  if (formEleve) {
    const inputMatricule = document.getElementById("matricule");
    const inputCode = document.getElementById("code");
    const msgMatricule = document.getElementById("erreur-matricule");
    const msgCode = document.getElementById("erreur-code");
    const btnSoumettre = document.getElementById("bouton-connexion-eleve");

    const motifMatricule = /^\d{2}[A-Za-z]{2}\d{4}$/;
    const motifCode = /^\d{4}$/;

    function validerChamp(input, messageEl, estValide, texteErreur) {
      if (estValide) {
        input.classList.remove("champ--invalide");
        input.removeAttribute("aria-invalid");
        if (messageEl) messageEl.textContent = "";
        return true;
      } else {
        input.classList.add("champ--invalide");
        input.setAttribute("aria-invalid", "true");
        if (messageEl) messageEl.textContent = texteErreur;
        return false;
      }
    }

    function verifierMatricule() {
      const valeur = inputMatricule.value.trim().toUpperCase();
      inputMatricule.value = valeur;
      if (!valeur) {
        return validerChamp(inputMatricule, msgMatricule, false, "Le matricule est obligatoire.");
      }
      if (!motifMatricule.test(valeur)) {
        return validerChamp(
          inputMatricule,
          msgMatricule,
          false,
          "Format attendu : 2 chiffres, 2 lettres, 4 chiffres (ex : 24GI0001)."
        );
      }
      return validerChamp(inputMatricule, msgMatricule, true, "");
    }

    function verifierCode() {
      const valeur = inputCode.value.trim();
      if (!valeur) {
        return validerChamp(inputCode, msgCode, false, "Le code d'accès est obligatoire.");
      }
      if (!motifCode.test(valeur)) {
        return validerChamp(inputCode, msgCode, false, "Le code doit comporter exactement 4 chiffres.");
      }
      return validerChamp(inputCode, msgCode, true, "");
    }

    inputMatricule.addEventListener("input", verifierMatricule);
    inputCode.addEventListener("input", verifierCode);

    formEleve.addEventListener("submit", (e) => {
      const matOk = verifierMatricule();
      const codeOk = verifierCode();
      if (!matOk || !codeOk) {
        e.preventDefault();
        if (!matOk) inputMatricule.focus();
        else inputCode.focus();
      }
    });
  }

  // --- Formulaire enseignant ---
  const formEnseignant = document.getElementById("form-connexion-enseignant");
  if (formEnseignant) {
    const inputLogin = document.getElementById("login");
    const inputMdp = document.getElementById("mot_de_passe");
    const msgLogin = document.getElementById("erreur-login");
    const msgMdp = document.getElementById("erreur-mot_de_passe");

    function verifierTexte(input, messageEl, champNom) {
      const valeur = input.value.trim();
      if (!valeur) {
        input.classList.add("champ--invalide");
        input.setAttribute("aria-invalid", "true");
        if (messageEl) messageEl.textContent = `${champNom} est obligatoire.`;
        return false;
      }
      input.classList.remove("champ--invalide");
      input.removeAttribute("aria-invalid");
      if (messageEl) messageEl.textContent = "";
      return true;
    }

    inputLogin.addEventListener("input", () => verifierTexte(inputLogin, msgLogin, "L'identifiant"));
    inputMdp.addEventListener("input", () => verifierTexte(inputMdp, msgMdp, "Le mot de passe"));

    formEnseignant.addEventListener("submit", (e) => {
      const logOk = verifierTexte(inputLogin, msgLogin, "L'identifiant");
      const mdpOk = verifierTexte(inputMdp, msgMdp, "Le mot de passe");
      if (!logOk || !mdpOk) {
        e.preventDefault();
        if (!logOk) inputLogin.focus();
        else inputMdp.focus();
      }
    });
  }
});
