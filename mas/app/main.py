import logging
import queue
import signal
import sys
import time

from . import config
from .agent import DistrictMonitoringAgent
from .mqtt_bridge import MQTTEventListener


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Avvio MAS core - Primo prototipo: agente che ascolta MQTT")

    # Coda condivisa tra bridge MQTT e agente
    event_queue: "queue.Queue[dict]" = queue.Queue(maxsize=1000)

    # Bridge MQTT -> Coda
    mqtt_listener = MQTTEventListener(
        broker_host=config.MQTT_BROKER_HOST,
        broker_port=config.MQTT_BROKER_PORT,
        topic_filter=config.MQTT_TOPIC_FILTER,
        event_queue=event_queue,
    )
    mqtt_listener.start()

    # Agente di monitoraggio (per ora unico, gestisce tutti i district)
    agent = DistrictMonitoringAgent(name="DistrictMonitoringAgent", event_queue=event_queue)
    agent.start()

    def handle_sigterm(signum, frame):
        logger.info("Segnale di terminazione ricevuto (%s). Arresto in corso...", signum)
        agent.stop()
        mqtt_listener.stop()
        time.sleep(1.0)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        handle_sigterm(signal.SIGINT, None)


if __name__ == "__main__":
    main()
