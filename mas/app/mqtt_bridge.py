"""
Bridge MQTT -> MAS (Multi-Agent System) per il monitoraggio urbano.

Obiettivo
---------
Sottoscrivere un topic filter MQTT e trasformare i messaggi ricevuti in eventi
"raw" (dizionari) da inserire in una coda thread-safe, che verrà successivamente
consumata dal router del MAS per lo smistamento verso i distretti.

Ruolo nel sistema
-----------------
Questo modulo implementa il listener MQTT (MQTTEventListener) che:
- si connette al broker MQTT configurato (host/porta),
- sottoscrive un filtro di topic (es. "city/+/+"),
- valida e decodifica il payload JSON dei messaggi ricevuti,
- inserisce gli eventi in una coda centrale (event_queue) in forma uniforme:
    {"topic": <topic>, "payload": <dict>}

Note progettuali
----------------
- La coda è usata per disaccoppiare il ritmo di arrivo dei messaggi MQTT dalla
  capacità di elaborazione del MAS (pattern producer/consumer).
- L'inserimento in coda avviene in modalità non bloccante (put_nowait) per evitare
  che il thread del client MQTT resti bloccato in caso di backlog (gestione overload).
- In caso di payload non JSON, l'evento viene scartato e tracciato a log.
"""

import json
import logging
import queue
from typing import Any

import paho.mqtt.client as mqtt

# Logger di modulo: consente diagnosi del canale MQTT (connessione, subscribe, parsing, overload).
logger = logging.getLogger(__name__)


class MQTTEventListener:
    """
    Listener MQTT che riceve messaggi e li inserisce in una coda centrale.

    Responsabilità
    --------------
    - Configurare callbacks del client MQTT (on_connect, on_message).
    - Gestire la sottoscrizione al topic filter in fase di connessione.
    - Effettuare parsing JSON del payload e produrre un evento raw uniforme.
    - Gestire overload della coda (queue.Full) senza bloccare il thread MQTT.
    """

    def __init__(self, broker_host: str, broker_port: int, topic_filter: str, event_queue: "queue.Queue[dict]") -> None:
        """
        Inizializza il listener MQTT.

        Args:
            broker_host: Hostname/IP del broker MQTT.
            broker_port: Porta del broker MQTT (tipicamente 1883).
            topic_filter: Filtro di sottoscrizione (wildcard MQTT consentite).
            event_queue: Coda thread-safe su cui pubblicare gli eventi raw ricevuti.
        """
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._topic_filter = topic_filter
        self._queue = event_queue

        # Creazione client MQTT.
        # `clean_session=True` avvia una sessione pulita (no state persistente sul broker).
        self._client = mqtt.Client(clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        """
        Callback invocata alla connessione al broker.

        Args:
            client: Istanza del client MQTT.
            userdata: User data associati al client (non usati).
            flags: Flag di connessione.
            rc: Return code (0 indica successo).
        """
        if rc == 0:
            logger.info("Connesso al broker MQTT (%s:%s)", self._broker_host, self._broker_port)
            logger.info("Sottoscrizione al filtro: %s", self._topic_filter)
            client.subscribe(self._topic_filter)
        else:
            # rc != 0: errore di connessione (es. auth fallita, broker non raggiungibile, ecc.).
            logger.error("Connessione al broker MQTT fallita, rc=%s", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """
        Callback invocata per ogni messaggio MQTT ricevuto.

        Flusso
        ------
        1) Decodifica bytes -> str (UTF-8 con error handling).
        2) Parsing JSON del payload.
        3) Creazione evento raw uniforme: {"topic": msg.topic, "payload": payload_dict}
        4) Inserimento non bloccante in coda centrale.

        Args:
            client: Istanza del client MQTT.
            userdata: User data associati al client (non usati).
            msg: Messaggio MQTT ricevuto.
        """
        # Decodifica robusta per evitare eccezioni su payload non UTF-8.
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            # Payload non JSON: in questo MAS si assume formato JSON; l'evento viene scartato.
            logger.warning("Payload non valido su topic %s: %s", msg.topic, payload_str)
            return

        # Evento raw: mantiene topic e payload già decodificato per il router del MAS.
        event = {"topic": msg.topic, "payload": payload}

        try:
            # Inserimento non bloccante: protegge il thread del client MQTT da backlog del MAS.
            self._queue.put_nowait(event)
            logger.debug("Evento MQTT messo in coda raw: %s", event)
        except queue.Full:
            # Overload: la coda centrale è satura (consumer troppo lento o burst di eventi).
            logger.error("Coda eventi MQTT raw piena, impossibile inserire evento da %s", msg.topic)

    def start(self) -> None:
        """
        Avvia la connessione al broker e il loop asincrono del client MQTT.

        Nota
        ----
        `loop_start()` avvia un thread interno gestito dalla libreria paho-mqtt,
        che invoca le callback (_on_connect, _on_message).
        """
        logger.info("Connessione al broker MQTT %s:%s ...", self._broker_host, self._broker_port)
        self._client.connect(self._broker_host, self._broker_port, keepalive=60)
        self._client.loop_start()
        logger.info("Loop MQTT avviato.")

    def stop(self) -> None:
        """
        Arresta il loop MQTT e disconnette il client dal broker.

        Motivazione
        -----------
        Permette shutdown pulito del sistema MAS (invocato dal main su SIGINT/SIGTERM).
        """
        logger.info("Arresto client MQTT...")
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Client MQTT disconnesso.")
