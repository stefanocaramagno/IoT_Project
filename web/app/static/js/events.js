/**
 * File: events.js
 *
 * Obiettivo
 * ---------
 * Gestire l’interazione della pagina "Events – Event Explorer":
 * - al click su una riga (desktop) o card (mobile) marcata con `data-event-row`, apre una modal;
 * - popola la modal con i dettagli dell’evento usando i valori presenti nel dataset (`data-event-*`);
 * - abilita chiusura della modal tramite overlay, pulsante close e tasto ESC;
 * - disabilita lo scroll della pagina durante l’apertura della modal.
 *
 * Ruolo nel sistema
 * -----------------
 * Questo script fornisce una funzionalità di ispezione puntuale degli eventi (drill-down) a partire
 * dai risultati già filtrati e renderizzati dal backend. Non modifica lo stato applicativo e non
 * effettua query lato client: migliora la UX rendendo immediata la consultazione del dettaglio.
 *
 * Contesto di utilizzo
 * --------------------
 * - La pagina `events.html` rende una tabella (desktop) e una lista di card (mobile).
 * - Ogni riga/card includa `data-event-row` e data-attributes coerenti (id, district, sensor, value, unit, ecc.).
 * - La modal è identificata da `#event-modal` e contiene campi `dd[data-field="..."]`.
 *
 * Note di implementazione
 * -----------------------
 * - Fail-safe: se `#event-modal` non è presente, lo script termina immediatamente.
 * - Fallback per valori assenti o non valorizzati: visualizzazione “–”.
 * - Lock scroll: aggiunta/rimozione di `overflow-hidden` su `document.body`.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Recupera la modale degli eventi.
  const modal = document.getElementById("event-modal");
  if (!modal) {
    // Se non siamo nella pagina events (o la modale non è presente), esce senza errori.
    return;
  }

  // Elementi di controllo della modale.
  const overlay = modal.querySelector("[data-modal-overlay]");
  const closeBtn = modal.querySelector("[data-modal-close]");

  /**
   * Imposta il testo dell’elemento nella modale associato al data-field richiesto.
   * Se il valore non è presente o risulta "undefined", mostra un placeholder "–".
   */
  const setField = (fieldName, value) => {
    const el = modal.querySelector(`[data-field="${fieldName}"]`);
    if (el) {
      el.textContent = value && value !== "undefined" ? value : "–";
    }
  };

  /**
   * Disabilita lo scroll del body quando la modale è aperta.
   * (Pattern tipico per evitare lo scroll della pagina dietro l’overlay.)
   */
  const disableBodyScroll = () => {
    document.body.classList.add("overflow-hidden");
  };

  /**
   * Ripristina lo scroll del body quando la modale è chiusa.
   */
  const enableBodyScroll = () => {
    document.body.classList.remove("overflow-hidden");
  };

  /**
   * Popola la modale a partire dal dataset dell’elemento cliccato.
   *
   * Nota sui nomi delle chiavi:
   * - `row.dataset` mappa gli attributi HTML `data-event-xxx="..."` in chiavi camelCase:
   *   es: data-event-id -> dataset.eventId
   *       data-event-sensor -> dataset.eventSensor
   */
  const openModalForDataset = (dataset) => {
    setField("id", dataset.eventId || "");
    setField("district", dataset.eventDistrict || "");
    setField("sensor_type", dataset.eventSensor || "");

    // Valore formattato con unità (se disponibile).
    const valueStr =
      dataset.eventValue && dataset.eventUnit
        ? `${dataset.eventValue} ${dataset.eventUnit}`
        : dataset.eventValue || "";

    setField("value", valueStr);
    setField("severity", dataset.eventSeverity || "");
    setField("timestamp", dataset.eventTimestamp || "");
    setField("topic", dataset.eventTopic || "");
    setField("created_at", dataset.eventCreated || "");

    // Apertura modale: rimuove "hidden" e blocca lo scroll della pagina.
    modal.classList.remove("hidden");
    disableBodyScroll();
  };

  /**
   * Chiude la modale e ripristina lo scroll.
   */
  const hideModal = () => {
    modal.classList.add("hidden");
    enableBodyScroll();
  };

  // Attacca l’handler di apertura modale a tutte le righe/card evento.
  const clickableRows = document.querySelectorAll("[data-event-row]");
  clickableRows.forEach((row) => {
    row.addEventListener("click", () => {
      openModalForDataset(row.dataset);
    });
  });

  // Chiusura cliccando sull’overlay.
  if (overlay) {
    overlay.addEventListener("click", hideModal);
  }

  // Chiusura cliccando sul bottone "X".
  if (closeBtn) {
    closeBtn.addEventListener("click", hideModal);
  }

  // Chiusura premendo ESC, solo se la modale è attualmente visibile.
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      hideModal();
    }
  });
});