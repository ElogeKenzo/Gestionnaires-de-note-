/**
 * Note View - Scripts communs
 * Gestion des boutons d'impression et fermeture des messages flash.
 */
document.addEventListener("DOMContentLoaded", () => {
  // Boutons d'impression
  document.querySelectorAll('[data-action="imprimer"]').forEach((bouton) => {
    bouton.addEventListener("click", () => {
      window.print();
    });
  });

  // Possibilité de cliquer sur un message flash pour le masquer
  document.querySelectorAll(".flash").forEach((flash) => {
    flash.setAttribute("title", "Cliquer pour masquer");
    flash.style.cursor = "pointer";
    flash.addEventListener("click", () => {
      flash.remove();
    });
  });
});
