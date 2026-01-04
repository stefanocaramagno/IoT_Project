const bars = document.querySelectorAll("[data-bar-pct]");
bars.forEach((bar) => {
  const raw = bar.getAttribute("data-bar-pct") || "0";
  let pct = parseInt(raw, 10);
  if (Number.isNaN(pct)) {
    pct = 0;
  }
  pct = Math.max(0, Math.min(100, pct));
  bar.style.width = pct + "%";
});

const modal = document.getElementById("decision-modal");

if (modal) {
  const overlay = modal.querySelector("[data-modal-overlay]");
  const closeButtons = modal.querySelectorAll("[data-modal-close]");
  const decisionRows = document.querySelectorAll("[data-decision-row]");

  const setField = (fieldName, value) => {
    const el = modal.querySelector(`[data-field="${fieldName}"]`);
    if (!el) return;
    if (value === undefined || value === null || value === "" || value === "undefined") {
      el.textContent = "–";
    } else {
      el.textContent = value;
    }
  };

  const lockScroll = () => {
    document.body.classList.add("overflow-hidden");
  };

  const unlockScroll = () => {
    document.body.classList.remove("overflow-hidden");
  };

  const openModalForRow = (row) => {
    const ds = row.dataset;

    setField("id", ds.decisionId);
    setField("created_at", ds.decisionCreated);
    setField("origin", ds.decisionOrigin);
    setField("source", ds.decisionSource);
    setField("target", ds.decisionTarget);
    setField("action_type", ds.decisionActionType);
    setField("reason", ds.decisionReason);

    let valueStr = "";
    if (ds.decisionEventValue && ds.decisionEventUnit) {
      valueStr = `${ds.decisionEventValue} ${ds.decisionEventUnit}`;
    } else if (ds.decisionEventValue) {
      valueStr = ds.decisionEventValue;
    }

    setField("event_district", ds.decisionEventDistrict);
    setField("event_sensor_type", ds.decisionEventSensor);
    setField("event_value", valueStr);
    setField("event_severity", ds.decisionEventSeverity);
    setField("event_timestamp", ds.decisionEventTimestamp);
    setField("event_topic", ds.decisionEventTopic);

    modal.classList.remove("hidden");
    lockScroll();
  };

  const hideModal = () => {
    modal.classList.add("hidden");
    unlockScroll();
  };

  decisionRows.forEach((row) => {
    row.addEventListener("click", () => {
      openModalForRow(row);
    });
  });

  if (overlay) {
    overlay.addEventListener("click", hideModal);
  }

  closeButtons.forEach((btn) => {
    btn.addEventListener("click", hideModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      hideModal();
    }
  });
}