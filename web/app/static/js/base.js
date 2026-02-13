/**
 * File: base.js
 *
 * Obiettivo
 * ---------
 * Gestire il comportamento della navigazione mobile (hamburger menu) definita nel layout base
 * della Web UI, garantendo:
 * - apertura/chiusura del menu su dispositivi mobile;
 * - aggiornamento dell’attributo ARIA `aria-expanded` per accessibilità;
 * - chiusura automatica del menu al click su un link di navigazione.
 *
 * Ruolo nel sistema
 * -----------------
 * Questo script fornisce una funzionalità “trasversale” e condivisa, utilizzata da tutte le pagine
 * che estendono `base.html`. È responsabile esclusivamente dell’esperienza di navigazione mobile
 * e non interagisce con dati applicativi (eventi/azioni) né con endpoint server-side.
 *
 * Contesto di utilizzo
 * --------------------
 * Il template HTML deve includere:
 * - un pulsante toggle con id `mobile-menu-toggle`;
 * - un contenitore menu con id `mobile-menu` (inizialmente hidden via Tailwind).
 *
 * Note di implementazione
 * -----------------------
 * - Nessuna dipendenza da librerie esterne.
 * - `"use strict"` abilita un comportamento più rigoroso del runtime JS (utile per prevenire
 *   errori comuni come variabili implicite o assegnazioni errate).
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
  initMobileNavigation();
});

/**
 * Inizializza la navigazione mobile:
 * - aggancia l’evento di click al toggle
 * - gestisce l’apertura/chiusura della sezione menu tramite la classe `hidden`
 * - mantiene coerente lo stato ARIA (`aria-expanded`)
 * - chiude il menu quando l’utente seleziona un link all’interno del menu
 */
function initMobileNavigation() {
  const toggle = document.getElementById("mobile-menu-toggle");
  const menu = document.getElementById("mobile-menu");

  // Se la pagina non contiene il layout atteso, termina senza errori.
  if (!toggle || !menu) {
    return;
  }

  // Stato iniziale coerente con l’HTML (menu nascosto).
  toggle.setAttribute("aria-expanded", "false");

  // Click sul pulsante hamburger: toggle della visibilità.
  toggle.addEventListener("click", () => {
    const isNowHidden = menu.classList.toggle("hidden");
    // aria-expanded deve essere true quando il menu è visibile (non hidden).
    toggle.setAttribute("aria-expanded", String(!isNowHidden));
  });

  // Click su uno dei link nel menu mobile: chiusura forzata del menu.
  const links = menu.querySelectorAll("a");
  links.forEach((link) => {
    link.addEventListener("click", () => {
      if (!menu.classList.contains("hidden")) {
        menu.classList.add("hidden");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  });
}