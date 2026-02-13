/**
 * File: llm_insights.js
 *
 * Obiettivo
 * ---------
 * Gestire l’interazione della pagina "LLM Insights – Model analysis", includendo:
 * - renderizzazione dinamica delle barre percentuali (LLM vs Fallback) tramite `data-bar-pct`;
 * - apertura/chiusura di una modal che mostra il dettaglio di una decisione:
 *    - metadati dell’azione di coordinamento;
 *    - snapshot dell’evento originante.
 *
 * Ruolo nel sistema
 * -----------------
 * Questo script abilita la componente “analitica e ispezionabile” della vista LLM:
 * - traduce in UI i KPI percentuali già calcolati server-side (progress bars);
 * - consente il drill-down sulle singole decisioni senza chiamate di rete, usando dataset `data-decision-*`.
 * Mantiene quindi una separazione netta tra:
 * - derivazione/normalizzazione delle decisioni (server-side);
 * - consultazione e interazione utente (client-side).
 *
 * Contesto di utilizzo
 * --------------------
 * - Barre percentuali: elementi con `data-bar-pct="0..100"` (o valori convertibili a intero).
 * - Decision log: righe/carte cliccabili marcate con `data-decision-row`, contenenti `data-decision-*`.
 * - Modal: elemento `#decision-modal` con overlay `[data-modal-overlay]`, pulsanti `[data-modal-close]`
 *   e campi `dd[data-field="..."]`.
 *
 * Note di implementazione
 * -----------------------
 * - Le percentuali vengono normalizzate nel range [0, 100] e applicate come `style.width = "<pct>%"`.
 * - Fail-safe: se la modal non è presente, viene eseguita solo la parte relativa alle barre.
 * - Lock scroll durante la modal: uso di `overflow-hidden` su `document.body`.
 * - Fallback per valori assenti: visualizzazione “–”.
 */

document.addEventListener("DOMContentLoaded", () => {
  /**
   * Sezione A — Barre percentuali (LLM vs Fallback)
   *
   * Nota:
   * - Gli elementi con `data-bar-pct` sono div interni alle barre e ricevono la larghezza
   *   calcolata in percentuale.
   */
  const bars = document.querySelectorAll("[data-bar-pct]");
  bars.forEach((bar) => {
    const raw = bar.getAttribute("data-bar-pct") || "0";

    let pct = parseInt(raw, 10);
    if (Number.isNaN(pct)) {
      pct = 0;
    }

    pct = Math.max(0, Math.min(100, pct));
    bar.style.width = `${pct}%`;
  });

  /**
   * Sezione B — Modale "Decision details"
   *
   * La modale può non essere presente (ad esempio in pagine diverse o layout differenti);
   * in tal caso lo script prosegue senza errori.
   */
  const modal = document.getElementById("decision-modal");
  if (!modal) {
    return;
  }

  const overlay = modal.querySelector("[data-modal-overlay]");
  const closeButtons = modal.querySelectorAll("[data-modal-close]");
  const decisionRows = document.querySelectorAll("[data-decision-row]");

  /**
   * Imposta il valore del campo nella modale identificato da `data-field="..."`.
   * Se il valore non è definito o è vuoto, mostra "–".
   */
  const setField = (fieldName, value) => {
    const el = modal.querySelector(`[data-field="${fieldName}"]`);
    if (!el) {
      return;
    }

    if (value === undefined || value === null || value === "" || value === "undefined") {
      el.textContent = "–";
      return;
    }

    el.textContent = value;
  };

  /**
   * Disabilita lo scroll del body quando la modale è aperta.
   */
  const lockScroll = () => {
    document.body.classList.add("overflow-hidden");
  };

  /**
   * Ripristina lo scroll del body quando la modale è chiusa.
   */
  const unlockScroll = () => {
    document.body.classList.remove("overflow-hidden");
  };

  /**
   * Apre la modale e la popola con i dati estratti dal dataset della riga/card selezionata.
   *
   * Nota sui nomi delle chiavi:
   * - gli attributi HTML `data-decision-id`, `data-decision-created`, ecc. vengono mappati
   *   in `row.dataset.decisionId`, `row.dataset.decisionCreated`, ecc.
   */
  const openModalForRow = (row) => {
    const ds = row.dataset;

    // Dati dell’azione di coordinamento.
    setField("id", ds.decisionId);
    setField("created_at", ds.decisionCreated);
    setField("origin", ds.decisionOrigin);
    setField("source", ds.decisionSource);
    setField("target", ds.decisionTarget);
    setField("action_type", ds.decisionActionType);
    setField("reason", ds.decisionReason);

    // Valore evento: include unità se disponibile.
    let valueStr = "";
    if (ds.decisionEventValue && ds.decisionEventUnit) {
      valueStr = `${ds.decisionEventValue} ${ds.decisionEventUnit}`;
    } else if (ds.decisionEventValue) {
      valueStr = ds.decisionEventValue;
    }

    // Snapshot dell’evento originante.
    setField("event_district", ds.decisionEventDistrict);
    setField("event_sensor_type", ds.decisionEventSensor);
    setField("event_value", valueStr);
    setField("event_severity", ds.decisionEventSeverity);
    setField("event_timestamp", ds.decisionEventTimestamp);
    setField("event_topic", ds.decisionEventTopic);

    modal.classList.remove("hidden");
    lockScroll();
  };

  /**
   * Chiude la modale e ripristina lo scroll.
   */
  const hideModal = () => {
    modal.classList.add("hidden");
    unlockScroll();
  };

  // Apertura modale su click riga/card decisione.
  decisionRows.forEach((row) => {
    row.addEventListener("click", () => {
      openModalForRow(row);
    });
  });

  // Chiusura modale cliccando sull’overlay.
  if (overlay) {
    overlay.addEventListener("click", hideModal);
  }

  // Chiusura modale cliccando su uno dei pulsanti close.
  closeButtons.forEach((btn) => {
    btn.addEventListener("click", hideModal);
  });

  // Chiusura modale premendo ESC.
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      hideModal();
    }
  });
});