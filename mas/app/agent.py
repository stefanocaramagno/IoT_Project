import logging
import queue
import threading
from dataclasses import dataclass, asdict
from typing import Any, Dict, Dict as DictType, List

from . import persistence
from . import llm_client

logger = logging.getLogger(__name__)


@dataclass
class SensorEvent:
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
        return self.severity.lower() == "high"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Message:
    msg_type: str
    source: str
    target: str
    payload: Dict[str, Any]


class DistrictMonitoringAgent(threading.Thread):
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
        self._recent_events: List[SensorEvent] = []
        self._max_recent_events: int = 20

    def run(self) -> None:
        logger.info("Agente di quartiere %s avviato.", self._district)
        while self._running.is_set():
            self._process_control_messages()

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

        # Persistenza dell'evento grezzo come prima cosa
        event_dict = event.to_dict()
        persistence.persist_sensor_event(event_dict)

        # Costruzione dei riassunti per l'LLM (solo campi essenziali)
        recent_summaries = [
            {
                "timestamp": e.timestamp,
                "sensor_type": e.sensor_type,
                "value": float(e.value),
                "unit": e.unit,
                "severity": e.severity,
            }
            for e in self._recent_events
        ]
        current_summary = {
            "timestamp": event.timestamp,
            "sensor_type": event.sensor_type,
            "value": float(event.value),
            "unit": event.unit,
            "severity": event.severity,
        }

        # Decidiamo se utilizzare l'LLM: in questo esempio solo per severità almeno medium
        use_llm = event.severity.lower() in {"medium", "high"}

        escalate: bool
        reason: str
        normalized_severity = event.severity.lower()

        if use_llm:
            try:
                llm_response = llm_client.decide_escalation(
                    district=self._district,
                    recent_events=recent_summaries,
                    current_event=current_summary,
                )
                escalate = bool(llm_response.get("escalate", False))
                normalized_severity = str(
                    llm_response.get("normalized_severity", normalized_severity)
                ).lower()
                reason = str(llm_response.get("reason", "llm_decision"))
                # Aggiorniamo eventualmente la severità con quella normalizzata
                event.severity = normalized_severity
                logger.info(
                    "Decisione LLM per %s: escalate=%s, normalized_severity=%s, reason=%s",
                    self._district,
                    escalate,
                    normalized_severity,
                    reason,
                )
            except Exception as exc:  # noqa: BLE001
                # Fallback sicuro: usiamo la regola deterministica originale
                logger.warning(
                    "LLM Gateway non disponibile o risposta non valida (%s). "
                    "Uso regola deterministica basata sulla severità.",
                    exc,
                )
                escalate = event.is_critical()
                reason = "fallback_rule"
        else:
            # Per eventi di severità bassa non interpelliamo l'LLM
            escalate = event.is_critical()
            reason = "low_severity_no_llm"

        if escalate:
            logger.warning("EVENTO CRITICO in %s (decisione LLM=%s): %s", self._district, use_llm, base_msg)
            escalation_msg = Message(
                msg_type="ESCALATION_REQUEST",
                source=self._district,
                target="CityCoordinator",
                payload={"event": event.to_dict(), "reason": reason},
            )
            try:
                self._coordinator_inbox.put_nowait(escalation_msg)
                logger.info("Inviata ESCALATION_REQUEST da %s al CityCoordinator.", self._district)
            except queue.Full:
                logger.error(
                    "Coda inbox CityCoordinator piena, impossibile inviare escalation da %s.",
                    self._district,
                )
        else:
            logger.info("Evento non critico in %s (decisione LLM=%s): %s", self._district, use_llm, base_msg)

        # Aggiorniamo il buffer degli eventi recenti (dopo l'elaborazione)
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)

    def _handle_control_message(self, msg: Message) -> None:
        if msg.msg_type == "COORDINATION_COMMAND":
            action = msg.payload.get("action", "unknown")
            from_district = msg.payload.get("from_district", "unknown")
            logger.info(
                "Agente di %s ha ricevuto COORDINATION_COMMAND: action=%s, from_district=%s",
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
    def __init__(
        self,
        inbox_queue: "queue.Queue[Message]",
        district_control_queues: DictType[str, "queue.Queue[Message]"],
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
                persistence.persist_action(
                    source_district=source_district,
                    target_district=district,
                    action_type="REROUTE_TRAFFIC",
                    reason="support_escalation",
                    event_snapshot=event,
                )
            except queue.Full:
                logger.error(
                    "Coda controllo per distretto %s piena, impossibile inviare comando di coordinamento.",
                    district,
                )