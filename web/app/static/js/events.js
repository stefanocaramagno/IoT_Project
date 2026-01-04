document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("event-modal");
  if (!modal) {
    return;
  }

  const overlay = modal.querySelector("[data-modal-overlay]");
  const closeBtn = modal.querySelector("[data-modal-close]");

  const setField = (fieldName, value) => {
    const el = modal.querySelector(`[data-field="${fieldName}"]`);
    if (el) {
      el.textContent = value && value !== "undefined" ? value : "–";
    }
  };

  const disableBodyScroll = () => {
    document.body.classList.add("overflow-hidden");
  };

  const enableBodyScroll = () => {
    document.body.classList.remove("overflow-hidden");
  };

  const openModalForDataset = (dataset) => {
    setField("id", dataset.eventId || "");
    setField("district", dataset.eventDistrict || "");
    setField("sensor_type", dataset.eventSensor || "");

    const valueStr =
      dataset.eventValue && dataset.eventUnit
        ? `${dataset.eventValue} ${dataset.eventUnit}`
        : dataset.eventValue || "";

    setField("value", valueStr);
    setField("severity", dataset.eventSeverity || "");
    setField("timestamp", dataset.eventTimestamp || "");
    setField("topic", dataset.eventTopic || "");
    setField("created_at", dataset.eventCreated || "");

    modal.classList.remove("hidden");
    disableBodyScroll();
  };

  const hideModal = () => {
    modal.classList.add("hidden");
    enableBodyScroll();
  };

  const clickableRows = document.querySelectorAll("[data-event-row]");
  clickableRows.forEach((row) => {
    row.addEventListener("click", () => {
      openModalForDataset(row.dataset);
    });
  });

  if (overlay) {
    overlay.addEventListener("click", hideModal);
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", hideModal);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) {
      hideModal();
    }
  });
});