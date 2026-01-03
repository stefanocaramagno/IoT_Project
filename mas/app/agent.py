import logging
import queue
import threading
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    """Messaggio di alto livello scambiato tra agenti interni al MAS."""
    msg_type: str        # es. 'ESCALATION_REQUEST', 'COORDINATION_COMMAND'
    source: str          # es. 'quartiere1', 'CityCoordinator'
    target: str          # es. 'CityCoordinator', 'quartiere2'
    payload: Dict[str, Any]


class DistrictMonitoringAgent(threading.Thread):
    """Agente di monitoraggio per un singolo quartiere.

    - Consuma eventi sensore dalla propria coda (sensor_queue).
    - In caso di evento critico, invia una richiesta di escalation all'agente centrale.
    - Riceve comandi di coordinamento dall'agente centrale tramite control_queue.
    """

    def __init__(
        self,
        district: str,
        sensor_queue: "queue.Queue[SensorEvent]",
        control_queue: "queue.Queue[Message]",
        coordinator_inbox: "queue.Queue[Message]",
    ) -> None:
        super().__init__(name=f"DistrictAgent-{district}", daemon=True)
        self._district = district
        self._sensor_queue = sensor_queue
        self._control_queue = control_queue
        self._coordinator_inbox = coordinator_inbox
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:
        logger.info("Agente di quartiere %s avviato.", self._district)
        while self._running.is_set():
            # 1) Gestione dei messaggi di controllo (non blocca)
            self._process_control_messages()

            # 2) Gestione degli eventi sensore (bloccante con timeout)
            try:
                event = self._sensor_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            self._handle_sensor_event(event)

    def stop(self) -> None:
        logger.info("Richiesta di arresto per l'agente di quartiere %s...", self._district)
        self._running.clear()

    def _process_control_messages(self) -> None:
        while True:
            try:
                msg: Message = self._control_queue.get_nowait()
            except queue.Empty:
                break

            self._handle_control_message(msg)

    def _handle_sensor_event(self, event: SensorEvent) -> None:
        base_msg = (
            f"[{event.timestamp}] topic={event.topic} | "
            f"district={event.district} | type={event.sensor_type} | "
            f"value={event.value} {event.unit} | severity={event.severity}"
        )

        if event.is_critical():
            logger.warning("EVENTO CRITICO in %s: %s", self._district, base_msg)
            # Invia richiesta di escalation all'agente centrale
            escalation_msg = Message(
                msg_type="ESCALATION_REQUEST",
                source=self._district,
                target="CityCoordinator",
                payload={
                    "event": event.to_dict(),
                    "reason": "severity_high",
                },
            )
            try:
                self._coordinator_inbox.put_nowait(escalation_msg)
                logger.info("Inviata ESCALATION_REQUEST da %s al CityCoordinator.", self._district)
            except queue.Full:
                logger.error("Coda inbox del CityCoordinator piena: impossibile inviare escalation da %s.", self._district)
        else:
            logger.info("Evento non critico in %s: %s", self._district, base_msg)

    def _handle_control_message(self, msg: Message) -> None:
        if msg.msg_type == "COORDINATION_COMMAND":
            action = msg.payload.get("action", "unknown")
            from_district = msg.payload.get("from_district", "unknown")
            logger.info(
                "Agente di %s ha ricevuto COORDINATION_COMMAND dal CityCoordinator: action=%s, from_district=%s",
                self._district,
                action,
                from_district,
            )
        else:
            logger.info(
                "Agente di %s ha ricevuto messaggio di tipo %s da %s",
                self._district,
                msg.msg_type,
                msg.source,
            )


class CityCoordinatorAgent(threading.Thread):
    """Agente centrale di coordinamento della città.

    - Riceve richieste di escalation dai quartieri.
    - Decide azioni di coordinamento (es. richiesta di supporto ad altri quartieri).
    - Invia COORDINATION_COMMAND agli agenti di quartiere interessati.
    """

    def __init__(
        self,
        inbox_queue: "queue.Queue[Message]",
        district_control_queues: Dict[str, "queue.Queue[Message]"],
    ) -> None:
        super().__init__(name="CityCoordinatorAgent", daemon=True)
        self._inbox_queue = inbox_queue
        self._district_control_queues = district_control_queues
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:
        logger.info("CityCoordinatorAgent avviato.")
        while self._running.is_set():
            try:
                msg: Message = self._inbox_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            self._handle_message(msg)

    def stop(self) -> None:
        logger.info("Richiesta di arresto per CityCoordinatorAgent...")
        self._running.clear()

    def _handle_message(self, msg: Message) -> None:
        if msg.msg_type == "ESCALATION_REQUEST":
            self._handle_escalation_request(msg)
        else:
            logger.info("CityCoordinatorAgent ha ricevuto messaggio di tipo %s da %s", msg.msg_type, msg.source)

    def _handle_escalation_request(self, msg: Message) -> None:
        event = msg.payload.get("event", {})
        source_district = msg.source
        logger.warning(
            "CityCoordinatorAgent ha ricevuto ESCALATION_REQUEST da %s per evento: %s",
            source_district,
            event,
        )

        # Semplice politica di coordinamento:
        # - chiede supporto a tutti i quartieri diversi da quello sorgente
        for district, control_queue in self._district_control_queues.items():
            if district == source_district:
                continue

            command = Message(
                msg_type="COORDINATION_COMMAND",
                source="CityCoordinator",
                target=district,
                payload={
                    "action": "REROUTE_TRAFFIC",
                    "from_district": source_district,
                    "original_event": event,
                },
            )
            try:
                control_queue.put_nowait(command)
                logger.info(
                    "CityCoordinatorAgent ha inviato COORDINATION_COMMAND a %s per supportare %s.",
                    district,
                    source_district,
                )
            except queue.Full:
                logger.error(
                    "Coda di controllo per il distretto %s è piena: impossibile inviare comando di coordinamento.",
                    district,
                )
