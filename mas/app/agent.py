import logging
import queue
import threading
from dataclasses import dataclass
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class SensorEvent:
    """Rappresenta un evento proveniente da un sensore urbano."""
    topic: str
    district: str
    sensor_type: str
    value: float
    unit: str
    severity: str
    timestamp: str

    @classmethod
    def from_raw(cls, topic: str, payload: Dict[str, Any]) -> "SensorEvent":
        return cls(
            topic=topic,
            district=str(payload.get("district", "unknown")),
            sensor_type=str(payload.get("type", "unknown")),
            value=float(payload.get("value", 0.0)),
            unit=str(payload.get("unit", "")),
            severity=str(payload.get("severity", "unknown")),
            timestamp=str(payload.get("timestamp", "")),
        )

    def is_critical(self) -> bool:
        """Definizione semplice di evento critico: severity == 'high'."""
        return self.severity.lower() == "high"


class DistrictMonitoringAgent(threading.Thread):
    """Primo prototipo di agente di monitoraggio urbano.

    Agente Python semplice che consuma eventi da una coda (riempita dal bridge MQTT)
    e applica una logica di base per rilevare eventi critici.
    """

    def __init__(self, name: str, event_queue: "queue.Queue[dict]") -> None:
        super().__init__(name=name, daemon=True)
        self._queue = event_queue
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:
        logger.info("Agente %s avviato. In attesa di eventi dalla coda...", self.name)
        while self._running.is_set():
            try:
                event = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            topic = event.get("topic", "")
            payload = event.get("payload", {})

            sensor_event = SensorEvent.from_raw(topic, payload)
            self._handle_event(sensor_event)

    def stop(self) -> None:
        logger.info("Richiesta di arresto per l'agente %s...", self.name)
        self._running.clear()

    def _handle_event(self, event: SensorEvent) -> None:
        base_msg = (
            f"[{event.timestamp}] topic={event.topic} | "
            f"district={event.district} | type={event.sensor_type} | "
            f"value={event.value} {event.unit} | severity={event.severity}"
        )

        if event.is_critical():
            logger.warning("EVENTO CRITICO rilevato: %s", base_msg)
        else:
            logger.info("Evento non critico: %s", base_msg)
