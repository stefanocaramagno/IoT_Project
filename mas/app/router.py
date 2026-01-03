import logging
import queue
import threading
from typing import Dict

from .agent import SensorEvent

logger = logging.getLogger(__name__)


class MQTTRouterThread(threading.Thread):
    def __init__(
        self,
        mqtt_event_queue: "queue.Queue[dict]",
        district_queues: Dict[str, "queue.Queue[SensorEvent]"],
    ) -> None:
        super().__init__(name="MQTTRouterThread", daemon=True)
        self._mqtt_event_queue = mqtt_event_queue
        self._district_queues = district_queues
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:
        logger.info("MQTTRouterThread avviato.")
        while self._running.is_set():
            try:
                event = self._mqtt_event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            topic = event.get("topic", "")
            payload = event.get("payload", {})
            district = str(payload.get("district", "unknown"))

            if district not in self._district_queues:
                logger.warning("Evento per distretto sconosciuto '%s' su topic %s: %s", district, topic, payload)
                continue

            sensor_event = SensorEvent.from_raw(topic, payload)
            try:
                self._district_queues[district].put_nowait(sensor_event)
                logger.debug("Instradato evento verso %s: %s", district, sensor_event)
            except queue.Full:
                logger.error("Coda eventi per distretto %s piena, impossibile instradare evento.", district)

    def stop(self) -> None:
        logger.info("Richiesta di arresto per MQTTRouterThread...")
        self._running.clear()
