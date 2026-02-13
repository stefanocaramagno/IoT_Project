"""
Router MQTT del MAS (Multi-Agent System) per il monitoraggio urbano.

Obiettivo
---------
Consumare gli eventi "raw" prodotti dal listener MQTT (MQTTEventListener) e
instradarli verso la coda sensoriale del distretto corretto, trasformandoli
in oggetti SensorEvent normalizzati.

Ruolo nel sistema
-----------------
Questo thread rappresenta lo strato di "routing" tra:
- mqtt_event_queue: coda centrale con eventi grezzi del tipo {"topic": ..., "payload": ...}
- district_queues: code per distretto che alimentano i DistrictMonitoringAgent

Il router realizza quindi un disaccoppiamento tra:
- arrivo dei messaggi MQTT (potenzialmente bursty e non controllato),
- elaborazione locale per distretto (parallelizzata tramite più agenti).

Note progettuali
----------------
- Il router è un thread daemon che opera in loop con timeout, così da poter essere
  arrestato in modo cooperativo tramite flag threading.Event.
- L'inserimento nelle code dei distretti avviene in modalità non bloccante (put_nowait),
  prevenendo blocchi sistemici nel caso in cui un distretto sia sovraccarico.
- Se un evento arriva per un distretto non noto (non configurato), viene scartato e loggato.
"""

import logging
import queue
import threading
from typing import Dict

from .agent import SensorEvent

# Logger di modulo: utile per tracciare routing, scarti e condizioni di overload.
logger = logging.getLogger(__name__)


class MQTTRouterThread(threading.Thread):
    """
    Thread di routing degli eventi MQTT verso le code per distretto.

    Responsabilità
    --------------
    - Consumare eventi raw dalla mqtt_event_queue.
    - Estrarre distretto dal payload.
    - Validare che il distretto sia tra quelli gestiti.
    - Convertire payload raw in SensorEvent (normalizzazione).
    - Inserire l'evento nella coda del distretto corrispondente.
    """

    def __init__(
        self,
        mqtt_event_queue: "queue.Queue[dict]",
        district_queues: Dict[str, "queue.Queue[SensorEvent]"],
    ) -> None:
        """
        Inizializza il router.

        Args:
            mqtt_event_queue: Coda centrale contenente eventi raw dal listener MQTT.
            district_queues: Mapping distretto -> coda eventi (SensorEvent) per l'agente locale.
        """
        super().__init__(name="MQTTRouterThread", daemon=True)
        self._mqtt_event_queue = mqtt_event_queue
        self._district_queues = district_queues

        # Flag di esecuzione per stop cooperativo.
        self._running = threading.Event()
        self._running.set()

    def run(self) -> None:
        """
        Main loop del router.

        Flusso
        ------
        - Attende un evento raw con timeout per mantenere responsività allo stop.
        - Estrae topic e payload.
        - Ricava il distretto dal payload.
        - Se distretto non configurato: scarta e logga.
        - Altrimenti: crea SensorEvent e inserisce nella coda del distretto in modo non bloccante.
        """
        logger.info("MQTTRouterThread avviato.")
        while self._running.is_set():
            try:
                # Attesa di un evento raw (timeout per permettere stop reattivo).
                event = self._mqtt_event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            topic = event.get("topic", "")
            payload = event.get("payload", {})
            district = str(payload.get("district", "unknown"))

            # Validazione: si instradano solo eventi per distretti noti/configurati.
            if district not in self._district_queues:
                logger.warning(
                    "Evento per distretto sconosciuto '%s' su topic %s: %s",
                    district,
                    topic,
                    payload,
                )
                continue

            # Normalizzazione del payload in oggetto SensorEvent coerente con il MAS.
            sensor_event = SensorEvent.from_raw(topic, payload)
            try:
                # Inserimento non bloccante: evita che un distretto congestionato blocchi l'intero routing.
                self._district_queues[district].put_nowait(sensor_event)
                logger.debug("Instradato evento verso %s: %s", district, sensor_event)
            except queue.Full:
                # Overload localizzato: la coda del distretto è satura (consumer troppo lento o burst eccessivo).
                logger.error(
                    "Coda eventi per distretto %s piena, impossibile instradare evento.",
                    district,
                )

    def stop(self) -> None:
        """
        Richiede l'arresto cooperativo del router.

        Nota
        ----
        Il loop `run()` verifica periodicamente `_running.is_set()` e usa timeout su get(),
        quindi lo stop avviene senza necessità di interrompere forzatamente il thread.
        """
        logger.info("Richiesta di arresto per MQTTRouterThread...")
        self._running.clear()
