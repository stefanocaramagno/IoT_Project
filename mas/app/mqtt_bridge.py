import json
import logging
import queue
from typing import Any

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTEventListener:
    """Client MQTT che ascolta i topic dei sensori e inoltra i messaggi a una coda locale.

    La coda funge da canale di comunicazione tra il mondo MQTT (IoT) e il router
    degli eventi, che a sua volta smista gli eventi verso gli agenti di quartiere.
    """

    def __init__(self, broker_host: str, broker_port: int, topic_filter: str, event_queue: "queue.Queue[dict]") -> None:
        self._broker_host = broker_host
        self._broker_port = broker_port
        self._topic_filter = topic_filter
        self._queue = event_queue

        self._client = mqtt.Client(clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int) -> None:
        if rc == 0:
            logger.info("Connesso con successo al broker MQTT (%s:%s)", self._broker_host, self._broker_port)
            logger.info("Sottoscrizione al filtro di topic: %s", self._topic_filter)
            client.subscribe(self._topic_filter)
        else:
            logger.error("Connessione al broker MQTT fallita, rc=%s", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        payload_str = msg.payload.decode("utf-8", errors="ignore")
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning("Payload non valido su topic %s: %s", msg.topic, payload_str)
            return

        event = {
            "topic": msg.topic,
            "payload": payload,
        }

        try:
            self._queue.put_nowait(event)
            logger.debug("Evento MQTT messo in coda raw: %s", event)
        except queue.Full:
            logger.error("Coda eventi MQTT raw piena: impossibile inserire nuovo evento da topic %s", msg.topic)

    def start(self) -> None:
        logger.info("Connessione al broker MQTT %s:%s ...", self._broker_host, self._broker_port)
        self._client.connect(self._broker_host, self._broker_port, keepalive=60)
        self._client.loop_start()
        logger.info("Loop MQTT avviato in background.")

    def stop(self) -> None:
        logger.info("Arresto client MQTT...")
        self._client.loop_stop()
        self._client.disconnect()
        logger.info("Client MQTT disconnesso.")
