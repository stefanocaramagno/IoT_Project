import logging
import queue
import signal
import sys
import time
from typing import Dict

from . import config
from .agent import CityCoordinatorAgent, DistrictMonitoringAgent, Message, SensorEvent
from .mqtt_bridge import MQTTEventListener
from .router import MQTTRouterThread


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Avvio MAS core - Fase 4: persistenza su SQLite via FastAPI.")

    mqtt_event_queue: "queue.Queue[dict]" = queue.Queue(maxsize=1000)

    district_event_queues: Dict[str, "queue.Queue[SensorEvent]"] = {
        district: queue.Queue(maxsize=200) for district in config.DISTRICTS
    }

    district_control_queues: Dict[str, "queue.Queue[Message]"] = {
        district: queue.Queue(maxsize=200) for district in config.DISTRICTS
    }

    coordinator_inbox: "queue.Queue[Message]" = queue.Queue(maxsize=500)

    mqtt_listener = MQTTEventListener(
        broker_host=config.MQTT_BROKER_HOST,
        broker_port=config.MQTT_BROKER_PORT,
        topic_filter=config.MQTT_TOPIC_FILTER,
        event_queue=mqtt_event_queue,
    )
    mqtt_listener.start()

    router = MQTTRouterThread(
        mqtt_event_queue=mqtt_event_queue,
        district_queues=district_event_queues,
    )
    router.start()

    coordinator_agent = CityCoordinatorAgent(
        inbox_queue=coordinator_inbox,
        district_control_queues=district_control_queues,
    )
    coordinator_agent.start()

    district_agents = []
    for district in config.DISTRICTS:
        agent = DistrictMonitoringAgent(
            district=district,
            sensor_queue=district_event_queues[district],
            control_queue=district_control_queues[district],
            coordinator_inbox=coordinator_inbox,
        )
        agent.start()
        district_agents.append(agent)

    def handle_sigterm(signum, frame):
        logger.info("Segnale di terminazione ricevuto (%s). Arresto in corso...", signum)

        for agent in district_agents:
            agent.stop()

        coordinator_agent.stop()
        router.stop()
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
