/**
 * Note View - Graphique d'évolution des moyennes de l'élève (Chart.js).
 * Alimenté par la route JSON : /api/eleve/evolution (fetch).
 * Aucun innerHTML utilisé (sécurité XSS).
 */
document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("graphique-evolution");
  const elErreur = document.getElementById("erreur-graphique");
  if (!canvas) return;

  function afficherErreur(message) {
    if (elErreur) {
      elErreur.textContent = message;
    }
  }

  // Vérifie la présence de Chart.js
  if (typeof Chart === "undefined") {
    afficherErreur("La bibliothèque graphique Chart.js n'a pas pu être chargée.");
    return;
  }

  fetch("/api/eleve/evolution")
    .then((reponse) => {
      if (!reponse.ok) {
        throw new Error(`Erreur réseau (${reponse.status})`);
      }
      return reponse.json();
    })
    .then((donnees) => {
      const evolution = donnees.evolution || [];
      if (!Array.isArray(evolution) || evolution.length === 0) {
        afficherErreur("Aucune note enregistrée pour le moment.");
        return;
      }

      const labels = evolution.map((item) => `Séquence ${item.sequence}`);
      const valeurs = evolution.map((item) => item.moyenne);
      const rangs = evolution.map((item) => {
        const r = item.rang ? `${item.rang}e` : "—";
        const eq = item.ex_aequo ? " (ex æquo)" : "";
        return `${r} / ${item.effectif}${eq}`;
      });

      const ctx = canvas.getContext("2d");
      new Chart(ctx, {
        type: "line",
        data: {
          labels: labels,
          datasets: [
            {
              label: "Ma moyenne (/20)",
              data: valeurs,
              borderColor: "#1f3a68",
              backgroundColor: "rgba(31, 58, 104, 0.12)",
              fill: true,
              tension: 0.3,
              pointBackgroundColor: "#f2b84b",
              pointBorderColor: "#1f3a68",
              pointBorderWidth: 2,
              pointRadius: 6,
              pointHoverRadius: 9,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              display: true,
              position: "top",
              labels: {
                color: "#1e293b",
                font: {
                  family: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                  weight: "bold",
                },
              },
            },
            tooltip: {
              backgroundColor: "#1f3a68",
              titleColor: "#ffffff",
              bodyColor: "#f8fafc",
              padding: 10,
              callbacks: {
                label: function (context) {
                  const idx = context.dataIndex;
                  const note = context.parsed.y.toFixed(2).replace(".", ",");
                  return ` Moyenne : ${note}/20`;
                },
                afterLabel: function (context) {
                  const idx = context.dataIndex;
                  return ` Rang : ${rangs[idx]}`;
                },
              },
            },
          },
          scales: {
            y: {
              min: 0,
              max: 20,
              ticks: {
                stepSize: 2,
                color: "#475569",
                callback: function (valeur) {
                  return valeur + " /20";
                },
              },
              grid: {
                color: function (context) {
                  // Ligne de flottaison à 10/20 bien visible
                  return context.tick.value === 10 ? "rgba(225, 29, 72, 0.6)" : "rgba(148, 163, 184, 0.25)";
                },
                lineWidth: function (context) {
                  return context.tick.value === 10 ? 2 : 1;
                },
              },
            },
            x: {
              ticks: {
                color: "#475569",
              },
              grid: {
                display: false,
              },
            },
          },
        },
      });
    })
    .catch((err) => {
      afficherErreur("Impossible de charger les données d'évolution pour le graphique.");
      console.error(err);
    });
});
