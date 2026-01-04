document.addEventListener("DOMContentLoaded", () => {
  const modal = document.getElementById("action-modal");
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
    setField("id", dataset.actionId || "");
    setField("created_at", dataset.actionCreated || "");
    setField("source", dataset.actionSource || "");
    setField("target", dataset.actionTarget || "");
    setField("action_type", dataset.actionType || "");
    setField("reason", dataset.actionReason || "");

    const valueStr =
      dataset.snapshotValue && dataset.snapshotUnit
        ? `${dataset.snapshotValue} ${dataset.snapshotUnit}`
        : dataset.snapshotValue || "";

    setField("snap_district", dataset.snapshotDistrict || "");
    setField("snap_sensor_type", dataset.snapshotSensorType || "");
    setField("snap_value", valueStr);
    setField("snap_severity", dataset.snapshotSeverity || "");
    setField("snap_timestamp", dataset.snapshotTimestamp || "");
    setField("snap_topic", dataset.snapshotTopic || "");

    modal.classList.remove("hidden");
    disableBodyScroll();
  };

  const hideModal = () => {
    modal.classList.add("hidden");
    enableBodyScroll();
  };

  const clickableRows = document.querySelectorAll("[data-action-row]");
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