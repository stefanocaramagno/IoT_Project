"""
Modulo core degli agenti del Multi-Agent System (MAS) per il monitoraggio urbano.

Obiettivo
---------
Definire le strutture dati e le logiche operative dei due agenti principali:
- DistrictMonitoringAgent: agente locale per distretto/quartiere, responsabile di
  consumo eventi sensoriali, persistenza, decisione di escalation (anche via LLM) e
  gestione di comandi di coordinamento.
- CityCoordinatorAgent: agente centrale cittadino, responsabile di ricezione delle
  escalation, mantenimento di uno stato sintetico della città, pianificazione di
  coordinamento (anche via LLM) e invio di comandi ai distretti.

Ruolo nel sistema
-----------------
Questo modulo rappresenta il "cuore decisionale" del MAS, orchestrando il flusso:
MQTT Listener -> sensor_queue -> DistrictMonitoringAgent -> (eventuale) escalation ->
CityCoordinatorAgent -> control_queue -> DistrictMonitoringAgent.

Integrazioni
------------
- persistence: persistenza eventi/azioni per tracciabilità e dashboarding.
- llm_client: accesso al gateway LLM per decisioni di escalation e coordinamento,
  con fallback deterministico in caso di indisponibilità o output non valido.

Note progettuali
----------------
- Gli agenti sono implementati come thread daemon, e comunicano tramite code thread-safe
  (queue.Queue) per evitare accoppiamento diretto e favorire un modello event-driven.
- Le code vengono usate in modalità non bloccante per l’invio (put_nowait) dove opportuno,
  così da evitare blocchi sistemici in presenza di backlog.
"""

import logging
import queue
import threading
from dataclasses import dataclass, asdict
from typing import Any, Dict, Dict as DictType, List

from . import persistence
from . import llm_client

# Logger di modulo: consente tracciamento consistente per agenti e componenti MAS.
logger = logging.getLogger(__name__)


@dataclass
class SensorEvent:
    """
    Rappresentazione normalizzata di un evento sensoriale ricevuto via MQTT.

    Obiettivo
    ---------
    Convertire payload eterogenei (tipicamente JSON) in una struttura interna uniforme,
    facilmente serializzabile e persistibile.

    Attributi
    ---------
    topic:
        Topic MQTT da cui proviene l'evento (utile per tracciamento/routing).
    district:
        Identificativo del distretto/quartiere sorgente.
    sensor_type:
        Tipo di sensore/misura (es. traffic, pollution, ecc.).
    value:
        Valore numerico della misura.
    unit:
        Unità di misura associata al valore.
    severity:
        Severità associata all'evento (es. low/medium/high); può essere aggiornata
        (es. normalizzazione tramite LLM).
    timestamp:
        Timestamp dell'evento (stringa; tipicamente ISO 8601 o formato equivalente).
    """
    topic: str
    district: str
    sensor_type: str
    value: float
    unit: str
    severity: str
    timestamp: str

    @classmethod
    def from_raw(cls, topic: str, payload: Dict[str, Any]) -> "SensorEvent":
        """
        Costruisce un SensorEvent a partire da un payload grezzo (tipicamente JSON).

        Motivazione
        -----------
        I producer (simulatori o sensori reali) possono fornire campi mancanti o
        con tipi non garantiti; questa funzione applica casting e default sicuri
        per ottenere sempre un oggetto interno consistente.

        Args:
            topic: Topic MQTT dell'evento.
            payload: Dizionario risultante dal parsing JSON del messaggio MQTT.

        Returns:
            SensorEvent: Istanza normalizzata con valori di default ove necessario.
        """
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
        """
        Determina se l'evento è critico secondo una regola deterministica locale.

        Nota
        ----
        Questa regola funge anche da fallback nel caso in cui l'LLM Gateway non sia
        disponibile o restituisca output non valido.

        Returns:
            bool: True se la severità è "high" (case-insensitive), altrimenti False.
        """
        return self.severity.lower() == "high"

    def to_dict(self) -> Dict[str, Any]:
        """
        Serializza l'evento in dict.

        Returns:
            Dict[str, Any]: Rappresentazione dizionario (utile per persistenza e messaggistica).
        """
        return asdict(self)


@dataclass
class Message:
    """
    Messaggio di controllo interno tra agenti (non MQTT).

    Obiettivo
    ---------
    Modellare comunicazioni interne al MAS (es. escalation e comandi di coordinamento)
    tramite code thread-safe (queue.Queue).

    Attributi
    ---------
    msg_type:
        Tipo di messaggio (es. "ESCALATION_REQUEST", "COORDINATION_COMMAND").
    source:
        Identificativo sorgente (distretto o "CityCoordinator").
    target:
        Identificativo destinatario (distretto o "CityCoordinator").
    payload:
        Contenuto del messaggio (dizionari JSON-like).
    """
    msg_type: str
    source: str
    target: str
    payload: Dict[str, Any]


class DistrictMonitoringAgent(threading.Thread):
    """
    Agente di monitoraggio locale per un singolo distretto.

    Responsabilità
    --------------
    - Consuma eventi sensoriali da una coda (sensor_queue) popolata dal listener MQTT.
    - Persiste gli eventi ricevuti (persistence.persist_sensor_event).
    - Decide se effettuare escalation al CityCoordinator:
        - preferenzialmente tramite consultazione LLM per severità medium/high;
        - fallback deterministico basato su severità in caso di indisponibilità LLM.
    - Riceve messaggi di controllo (control_queue), tipicamente comandi di coordinamento.
    - Mantiene una finestra scorrevole di eventi recenti per fornire contesto all'LLM.
    """

    def __init__(
        self,
        district: str,
        sensor_queue: "queue.Queue[SensorEvent]",
        control_queue: "queue.Queue[Message]",
        coordinator_inbox: "queue.Queue[Message]",
    ) -> None:
        # Thread daemon per garantire che la chiusura del processo non resti bloccata su agenti.
        super().__init__(name=f"DistrictAgent-{district}", daemon=True)
        self._district = district
        self._sensor_queue = sensor_queue
        self._control_queue = control_queue
        self._coordinator_inbox = coordinator_inbox

        # Flag di esecuzione: consente stop cooperativo del thread.
        self._running = threading.Event()
        self._running.set()

        # Buffer di contesto: eventi recenti (sliding window) utilizzati per decisione LLM.
        self._recent_events: List[SensorEvent] = []
        self._max_recent_events: int = 20

    def run(self) -> None:
        """
        Main loop dell'agente.

        Flusso
        ------
        - Processa eventuali messaggi di controllo (non bloccante).
        - Attende eventi sensoriali con timeout (per permettere stop responsivo).
        - Gestisce l'evento: persistenza, decisione escalation, eventuale invio al coordinatore.
        """
        logger.info("Agente di quartiere %s avviato.", self._district)
        while self._running.is_set():
            # Gestione dei comandi ricevuti dal coordinatore (non deve bloccare).
            self._process_control_messages()

            try:
                # Attesa di un evento sensoriale con timeout: evita deadlock su stop.
                event = self._sensor_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            self._handle_sensor_event(event)

    def stop(self) -> None:
        """
        Richiede l'arresto cooperativo dell'agente.

        Nota
        ----
        Il loop `run()` verifica periodicamente `_running.is_set()` e usa timeout sulle get(),
        quindi lo stop è responsivo senza necessità di segnali esterni.
        """
        logger.info("Richiesta di arresto per l'agente di quartiere %s...", self._district)
        self._running.clear()

    def _process_control_messages(self) -> None:
        """
        Svuota la coda di controllo processando tutti i messaggi disponibili.

        Motivazione
        -----------
        Si usa `get_nowait()` in loop per evitare blocchi: i comandi di coordinamento
        devono essere gestiti "opportunisticamente" mentre si continua a consumare sensori.
        """
        while True:
            try:
                msg: Message = self._control_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_control_message(msg)

    def _handle_sensor_event(self, event: SensorEvent) -> None:
        """
        Gestisce un singolo evento sensoriale.

        Passi principali
        ----------------
        1) Log e persistenza dell'evento.
        2) Costruzione del contesto (recent_events + current_event) in formato JSON-like.
        3) Decisione escalation:
           - consultazione LLM per severità medium/high;
           - fallback deterministico in caso di errore/indisponibilità.
        4) In caso di escalation, invio del messaggio al CityCoordinator tramite inbox queue.
        5) Aggiornamento della sliding window degli eventi recenti.

        Args:
            event: Evento sensoriale normalizzato proveniente dal listener MQTT.
        """
        # Messaggio base per logging: utile per tracciamento e correlazione.
        base_msg = (
            f"[{event.timestamp}] topic={event.topic} | "
            f"district={event.district} | type={event.sensor_type} | "
            f"value={event.value} {event.unit} | severity={event.severity}"
        )

        # Persistenza evento sensoriale: consente consultazione storica e dashboarding.
        event_dict = event.to_dict()
        persistence.persist_sensor_event(event_dict)

        # Preparazione del contesto per l'LLM:
        # - recent_summaries: finestra scorrevole di eventi precedenti (contesto)
        # - current_summary: evento corrente (focus)
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

        # Strategia di uso LLM:
        # - per eventi low, si evita costo/latency e si usa regola deterministica;
        # - per medium/high, si richiede normalizzazione e decisione più informata.
        use_llm = event.severity.lower() in {"medium", "high"}

        escalate: bool
        reason: str
        normalized_severity = event.severity.lower()

        if use_llm:
            try:
                # Invocazione del gateway LLM per decidere escalation e normalizzare severità.
                llm_response = llm_client.decide_escalation(
                    district=self._district,
                    recent_events=recent_summaries,
                    current_event=current_summary,
                )
                # Lettura robusta dei campi per evitare crash su output parziale.
                escalate = bool(llm_response.get("escalate", False))
                normalized_severity = str(
                    llm_response.get("normalized_severity", normalized_severity)
                ).lower()
                reason = str(llm_response.get("reason", "llm_decision"))

                # Aggiornamento dell'evento con severità normalizzata per coerenza di sistema.
                event.severity = normalized_severity
                logger.info(
                    "Decisione LLM per %s: escalate=%s, normalized_severity=%s, reason=%s",
                    self._district,
                    escalate,
                    normalized_severity,
                    reason,
                )
            except Exception as exc:
                # Fallback conservativo: in caso di indisponibilità o output non valido,
                # si mantiene una regola deterministica basata su severità.
                logger.warning(
                    "LLM Gateway non disponibile o risposta non valida per decide_escalation (%s). "
                    "Uso regola deterministica basata sulla severità.",
                    exc,
                )
                escalate = event.is_critical()
                reason = "fallback_rule"
        else:
            # Per severità bassa: scelta deterministica e tracciabile (nessuna consultazione LLM).
            escalate = event.is_critical()
            reason = "low_severity_no_llm"

        if escalate:
            # Logging in warning per evidenziare eventi critici/escalation nel flusso di log.
            logger.warning(
                "EVENTO CRITICO in %s (decisione LLM=%s): %s",
                self._district,
                use_llm,
                base_msg,
            )
            escalation_msg = Message(
                msg_type="ESCALATION_REQUEST",
                source=self._district,
                target="CityCoordinator",
                payload={"event": event.to_dict(), "reason": reason},
            )
            try:
                # Invio non bloccante: evita che un backlog sul coordinatore blocchi l'agente locale.
                self._coordinator_inbox.put_nowait(escalation_msg)
                logger.info("Inviata ESCALATION_REQUEST da %s al CityCoordinator.", self._district)
            except queue.Full:
                # La coda del coordinatore è satura: l'escalation non viene consegnata.
                # In un sistema reale si potrebbe introdurre retry/backoff o una DLQ.
                logger.error(
                    "Coda inbox CityCoordinator piena, impossibile inviare escalation da %s.",
                    self._district,
                )
        else:
            logger.info(
                "Evento non critico in %s (decisione LLM=%s): %s",
                self._district,
                use_llm,
                base_msg,
            )

        # Aggiornamento contesto eventi recenti (sliding window).
        self._recent_events.append(event)
        if len(self._recent_events) > self._max_recent_events:
            self._recent_events.pop(0)

    def _handle_control_message(self, msg: Message) -> None:
        """
        Gestisce un messaggio di controllo rivolto all'agente di distretto.

        Attualmente gestisce:
        - COORDINATION_COMMAND: comando inviato dal CityCoordinator per attuare
          un'azione locale o supportare un altro distretto.

        Args:
            msg: Messaggio di controllo ricevuto tramite control_queue.
        """
        if msg.msg_type == "COORDINATION_COMMAND":
            # Lettura dei campi: 'action' identifica l'azione da intraprendere.
            action = msg.payload.get("action", "unknown")
            from_district = msg.payload.get("from_district", "unknown")
            logger.info(
                "Agente di %s ha ricevuto COORDINATION_COMMAND: action=%s, from_district=%s",
                self._district,
                action,
                from_district,
            )
        else:
            # Messaggi non previsti vengono loggati per diagnosi e possibili estensioni future.
            logger.info(
                "Agente di %s ha ricevuto messaggio di tipo %s da %s",
                self._district,
                msg.msg_type,
                msg.source,
            )


class CityCoordinatorAgent(threading.Thread):
    """
    Agente coordinatore cittadino.

    Responsabilità
    --------------
    - Riceve richieste di escalation dai distretti (inbox_queue).
    - Mantiene uno stato sintetico della città (city_state) per supportare decisioni.
    - Richiede al gateway LLM un piano di coordinamento inter-distrettuale oppure
      usa un piano deterministico di fallback.
    - Invia comandi di coordinamento ai distretti tramite le rispettive control queues.
    - Persiste le azioni intraprese (persistence.persist_action) per tracciabilità e dashboard.
    """

    def __init__(
        self,
        inbox_queue: "queue.Queue[Message]",
        district_control_queues: DictType[str, "queue.Queue[Message]"],
    ) -> None:
        super().__init__(name="CityCoordinatorAgent", daemon=True)
        self._inbox_queue = inbox_queue
        self._district_control_queues = district_control_queues

        # Flag di esecuzione per stop cooperativo.
        self._running = threading.Event()
        self._running.set()

        # Stato sintetico della città: mapping distretto -> metriche (traffic_index, pollution_index, ...).
        self._city_state: DictType[str, Dict[str, Any]] = {}

    def run(self) -> None:
        """
        Main loop del coordinatore.

        Attende messaggi in ingresso dalla inbox queue con timeout, così da mantenere
        responsività allo stop.
        """
        logger.info("CityCoordinatorAgent avviato.")
        while self._running.is_set():
            try:
                msg: Message = self._inbox_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            self._handle_message(msg)

    def stop(self) -> None:
        """
        Richiede l'arresto cooperativo del coordinatore.
        """
        logger.info("Richiesta di arresto per CityCoordinatorAgent...")
        self._running.clear()

    def _handle_message(self, msg: Message) -> None:
        """
        Dispatch dei messaggi in ingresso per tipo.

        Args:
            msg: Messaggio ricevuto in inbox (es. escalation).
        """
        if msg.msg_type == "ESCALATION_REQUEST":
            self._handle_escalation_request(msg)
        else:
            logger.info(
                "CityCoordinatorAgent ha ricevuto messaggio di tipo %s da %s",
                msg.msg_type,
                msg.source,
            )

    def _update_city_state(self, district: str, event: Dict[str, Any]) -> None:
        """
        Aggiorna lo stato sintetico della città in base a un evento ricevuto.

        Motivazione
        -----------
        Il coordinatore mantiene una vista minimale (traffic_index/pollution_index)
        per fornire contesto all'LLM durante la pianificazione di coordinamento.

        Args:
            district: Distretto sorgente dell'evento.
            event: Snapshot dell'evento (dict) da cui estrarre sensor_type e value.
        """
        state = self._city_state.setdefault(district, {})
        sensor_type = event.get("sensor_type") or event.get("type")
        raw_value = event.get("value", 0.0)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = 0.0

        # Aggiornamento di metriche standardizzate note.
        if sensor_type == "traffic":
            state["traffic_index"] = value
        elif sensor_type == "pollution":
            state["pollution_index"] = value

    def _build_fallback_plan(self, source_district: str, critical_event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Costruisce un piano deterministico di fallback in assenza di LLM.

        Strategia
        ---------
        In caso di escalation da un distretto, tutti gli altri distretti ricevono
        un'azione generica di supporto (es. REROUTE_TRAFFIC).

        Args:
            source_district: Distretto che ha generato l'escalation.
            critical_event: Evento critico normalizzato (non usato direttamente nel piano attuale).

        Returns:
            List[Dict[str, Any]]: Lista di entry di piano coerenti con lo schema LLM.
        """
        plan: List[Dict[str, Any]] = []
        for district in self._district_control_queues.keys():
            if district == source_district:
                continue
            plan.append(
                {
                    "target_district": district,
                    "action_type": "REROUTE_TRAFFIC",
                    "reason": "support_escalation_fallback",
                }
            )
        return plan

    def _handle_escalation_request(self, msg: Message) -> None:
        """
        Gestisce una richiesta di escalation proveniente da un distretto.

        Flusso
        ------
        1) Estrae evento e distretto sorgente.
        2) Aggiorna lo stato sintetico cittadino.
        3) Prepara payload per LLM (critical_event + city_state).
        4) Invoca LLM per plan_coordination o usa fallback.
        5) Valida entry e invia COORDINATION_COMMAND ai distretti target.
        6) Persiste le azioni di coordinamento inviate.

        Args:
            msg: Messaggio di tipo ESCALATION_REQUEST con snapshot evento e motivazione.
        """
        event = msg.payload.get("event", {})
        source_district = msg.source
        logger.warning(
            "CityCoordinatorAgent ha ricevuto ESCALATION_REQUEST da %s per evento: %s",
            source_district,
            event,
        )

        # Aggiornamento vista sintetica della città con l'evento ricevuto.
        self._update_city_state(source_district, event)

        # Normalizzazione dei campi essenziali dell'evento critico.
        # Si supportano sia 'sensor_type' sia 'type' per compatibilità con formati diversi.
        sensor_type = event.get("sensor_type") or event.get("type") or "unknown"
        raw_value = event.get("value", 0.0)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = 0.0

        critical_event = {
            "timestamp": str(event.get("timestamp", "")),
            "sensor_type": str(sensor_type),
            "value": value,
            "unit": str(event.get("unit", "")),
            "severity": str(event.get("severity", "unknown")),
        }

        # Costruzione payload city_state da inviare al gateway LLM.
        city_state_payload: List[Dict[str, Any]] = []
        for district_name, metrics in self._city_state.items():
            city_state_payload.append(
                {
                    "district": district_name,
                    "traffic_index": metrics.get("traffic_index"),
                    "pollution_index": metrics.get("pollution_index"),
                    "other_metrics": {},
                }
            )

        try:
            # Invocazione LLM: produce un piano di coordinamento inter-distrettuale.
            llm_response = llm_client.plan_coordination(
                source_district=source_district,
                critical_event=critical_event,
                city_state=city_state_payload,
            )
            plan_entries = llm_response.get("plan", [])
            logger.info("Piano di coordinamento LLM per %s: %s", source_district, plan_entries)
        except Exception as exc:  # noqa: BLE001
            # Fallback deterministico: mantiene comportamento stabile in caso di dipendenza esterna down.
            logger.warning(
                "LLM Gateway non disponibile o risposta non valida per plan_coordination (%s). "
                "Uso piano di coordinamento deterministico di fallback.",
                exc,
            )
            plan_entries = self._build_fallback_plan(source_district, critical_event)

        # Traduzione delle entry di piano in comandi da inviare alle code dei distretti.
        for entry in plan_entries:
            target = entry.get("target_district")
            action_type = entry.get("action_type", "UNKNOWN_ACTION")
            reason = entry.get("reason", "llm_plan")

            # Validazioni minime:
            # - target esiste e non coincide con la sorgente
            # - target deve essere un distretto noto (presente nelle control queues)
            if not target or target == source_district or target not in self._district_control_queues:
                logger.warning(
                    "Entry di piano con target_district non valido: %s (entry=%s)",
                    target,
                    entry,
                )
                continue

            command = Message(
                msg_type="COORDINATION_COMMAND",
                source="CityCoordinator",
                target=target,
                payload={
                    "action": action_type,
                    "from_district": source_district,
                    "original_event": event,
                },
            )
            try:
                # Invio non bloccante del comando: evita blocchi del coordinatore su code sature.
                control_queue = self._district_control_queues[target]
                control_queue.put_nowait(command)
                logger.info(
                    "CityCoordinatorAgent ha inviato COORDINATION_COMMAND a %s per supportare %s (action=%s).",
                    target,
                    source_district,
                    action_type,
                )
                # Persistenza azione: utile per dashboard e tracciabilità post-mortem.
                persistence.persist_action(
                    source_district=source_district,
                    target_district=target,
                    action_type=action_type,
                    reason=reason,
                    event_snapshot=event,
                )
            except queue.Full:
                logger.error(
                    "Coda controllo per distretto %s piena, impossibile inviare comando di coordinamento.",
                    target,
                )