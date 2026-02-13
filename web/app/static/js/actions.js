/**
 * File: actions.js
 *
 * Obiettivo
 * ---------
 * Gestire l’interazione utente nella pagina "Actions – Coordination Explorer":
 * - al click su una riga/card (elementi con `data-action-row`), apre una modal di dettaglio;
 * - popola la modal con i metadati dell’azione e lo snapshot dell’evento associato;
 * - consente la chiusura della modal tramite overlay, pulsante close e tasto ESC;
 * - disabilita lo scroll della pagina durante l’apertura della modal.
 *
 * Ruolo nel sistema
 * -----------------
 * Questo script implementa il comportamento “drill-down” delle azioni di coordinamento:
 * valorizza l’ispezione dettagliata senza introdurre chiamate di rete, riutilizzando dati già
 * renderizzati dal backend nel DOM tramite attributi `data-*`. In tal modo:
 * - la generazione/filtraggio delle azioni resta server-side;
 * - la consultazione del dettaglio resta client-side, immediata e deterministica.
 *
 * Contesto di utilizzo
 * --------------------
 * Il template HTML deve:
 * - includere una modal con id `action-modal`;
 * - definire overlay e pulsante di chiusura via:
 *   * `[data-modal-overlay]`
 *   * `[data-modal-close]`
 * - includere placeholder nella modal tramite:
 *   * `dd[data-field="<nome_campo>"]`
 * - rendere cliccabili righe/card con `data-action-row` e dataset coerente con i nomi letti dallo script.
 *
 * Note di implementazione
 * -----------------------
 * - Nessuna chiamata di rete: la modal è popolata esclusivamente dai dataset delle righe/card.
 * - Fallback per campi mancanti: visualizzazione “–”.
 * - Lock scroll: aggiunta/rimozione della classe `overflow-hidden` su `document.body`.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Recupera la modal di dettaglio azione; se non esiste la pagina non richiede JS.
  const modal = document.getElementById("action-modal");
  if (!modal) {
    return;
  }

  // Overlay e pulsante di chiusura (opzionali, ma previsti dal template).
  const overlay = modal.querySelector("[data-modal-overlay]");
  const closeBtn = modal.querySelector("[data-modal-close]");

  /**
   * Imposta il testo dell’elemento che rappresenta un campo della modal.
   *
   * Convenzione:
   * - i campi della modal sono individuati da: [data-field="<fieldName>"]
   * - se il valore è vuoto o la stringa "undefined" (caso dataset mancante),
   *   viene mostrato un placeholder tipografico.
   */
  const setField = (fieldName, value) => {
    const el = modal.querySelector(`[data-field="${fieldName}"]`);
    if (el) {
      el.textContent = value && value !== "undefined" ? value : "–";
    }
  };

  /**
   * Disabilita lo scroll del body quando la modal è aperta,
   * per evitare che l’utente scrolli la pagina sottostante.
   */
  const disableBodyScroll = () => {
    document.body.classList.add("overflow-hidden");
  };

  /**
   * Riabilita lo scroll del body quando la modal viene chiusa.
   */
  const enableBodyScroll = () => {
    document.body.classList.remove("overflow-hidden");
  };

  /**
   * Popola e apre la modal leggendo i valori dal dataset della riga/card cliccata.
   *
   * Il dataset viene popolato lato template HTML tramite attributi data-*
   * (es. data-action-id="...", data-snapshot-value="...", ecc.) e viene letto qui
   * con le chiavi camelCase standard del DOM dataset (es. row.dataset.actionId).
   *
   * Oltre ai campi testuali, gestisce la formattazione del valore con unità:
   * - se value e unit sono presenti: "value unit"
   * - altrimenti: solo "value"
   */
  const openModalForDataset = (dataset) => {
    // Metadati dell’azione di coordinamento.
    setField("id", dataset.actionId || "");
    setField("created_at", dataset.actionCreated || "");
    setField("source", dataset.actionSource || "");
    setField("target", dataset.actionTarget || "");
    setField("action_type", dataset.actionType || "");
    setField("reason", dataset.actionReason || "");

    // Valore snapshot: combina value + unit quando disponibili.
    const valueStr =
      dataset.snapshotValue && dataset.snapshotUnit
        ? `${dataset.snapshotValue} ${dataset.snapshotUnit}`
        : dataset.snapshotValue || "";

    // Snapshot dell’evento associato.
    setField("snap_district", dataset.snapshotDistrict || "");
    setField("snap_sensor_type", dataset.snapshotSensorType || "");
    setField("snap_value", valueStr);
    setField("snap_severity", dataset.snapshotSeverity || "");
    setField("snap_timestamp", dataset.snapshotTimestamp || "");
    setField("snap_topic", dataset.snapshotTopic || "");

    // Apertura UI della modal.
    modal.classList.remove("hidden");
    disableBodyScroll();
  };

  /**
   * Chiude la modal e ripristina lo stato di scroll della pagina.
   */
  const hideModal = () => {
    modal.classList.add("hidden");
    enableBodyScroll();
  };

  /**
   * Registra i listener di click su tutte le righe/card marcate con `data-action-row`.
   * Ogni elemento deve avere nel proprio dataset le chiavi attese (actionId, actionCreated, ecc.).
   */
  const clickableRows = document.querySelectorAll("[data-action-row]");
  clickableRows.forEach((row) => {
    row.addEventListener("click", () => {
      openModalForDataset(row.dataset);
    });
  });

  // Click su overlay: chiusura modale (se presente nel DOM).
  if (overlay) {
    overlay.addEventListener("click", hideModal);
  }

  // Click sul pulsante di chiusura: chiusura modale (se presente nel DOM).
  if (closeBtn) {
    closeBtn.addEventListener("click", hideModal);
  }

  /**
   * Gestione accessibilità/UX:
   * - chiusura della modal con tasto ESC, solo se la modal è attualmente visibile.
   */
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      hideModal();
    }
  });
});