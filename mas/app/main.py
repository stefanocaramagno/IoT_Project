"""
Entry point del MAS (Multi-Agent System) per il monitoraggio urbano.

Obiettivo
---------
Avviare e orchestrare i componenti runtime del sistema:
- Listener MQTT: sottoscrive i topic e inserisce eventi grezzi in una coda centrale.
- Router MQTT: smista gli eventi verso le code dei distretti (SensorEvent).
- DistrictMonitoringAgent: agenti locali (uno per distretto) che processano eventi,
  persistono dati e decidono eventuali escalation al coordinatore.
- CityCoordinatorAgent: agente centrale che gestisce escalation e comandi di coordinamento.

Ruolo nel sistema
-----------------
Questo modulo funge da "bootstrap" del MAS e definisce:
- configurazione logging;
- creazione delle code thread-safe utilizzate per la comunicazione tra componenti;
- creazione e avvio dei thread (listener, router, agenti);
- gestione di shutdown pulito tramite segnali (SIGINT/SIGTERM).

Note progettuali
----------------
- Il sistema è progettato in stile event-driven: ogni componente lavora su code queue.Queue
  che garantiscono thread-safety e disaccoppiamento.
- Lo shutdown è cooperativo: ogni thread espone stop() e il main thread gestisce la terminazione
  in modo controllato, riducendo rischio di corruzione dello stato o perdita di log.
"""

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
    """
    Configura il logging globale del processo.

    Scelte
    ------
    - livello INFO per fornire una traccia operativa leggibile senza eccessivo rumore;
    - formato con timestamp, livello e nome logger per facilitare diagnosi in ambiente container.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    )


def main() -> None:
    """
    Funzione principale di avvio del MAS.

    Flusso
    ------
    1) Setup logging e logger locale.
    2) Inizializzazione code di comunicazione:
       - mqtt_event_queue: eventi grezzi dal listener MQTT (dict).
       - district_event_queues: code per distretto (SensorEvent).
       - district_control_queues: comandi per distretto (Message).
       - coordinator_inbox: inbox per il CityCoordinator (Message).
    3) Avvio listener MQTT e router.
    4) Avvio CityCoordinatorAgent.
    5) Avvio DistrictMonitoringAgent (uno per distretto).
    6) Registrazione handler segnali per shutdown (SIGINT/SIGTERM).
    7) Loop di keep-alive fino a terminazione.
    """
    setup_logging()
    logger = logging.getLogger(__name__)

    # Log descrittivo di avvio: utile per versioning/fasi del progetto e diagnosi.
    logger.info("Avvio MAS core - Fase 4: persistenza su SQLite via FastAPI.")

    # Coda centrale di eventi grezzi (tipicamente dict ricavati dal payload MQTT).
    # Viene consumata dal router per smistamento verso distretti.
    mqtt_event_queue: "queue.Queue[dict]" = queue.Queue(maxsize=1000)

    # Code sensoriali per distretto: contengono SensorEvent già normalizzati.
    district_event_queues: Dict[str, "queue.Queue[SensorEvent]"] = {
        district: queue.Queue(maxsize=200) for district in config.DISTRICTS
    }

    # Code di controllo per distretto: comandi dal coordinatore (Message).
    district_control_queues: Dict[str, "queue.Queue[Message]"] = {
        district: queue.Queue(maxsize=200) for district in config.DISTRICTS
    }

    # Inbox del CityCoordinator: riceve escalation dai distretti (Message).
    coordinator_inbox: "queue.Queue[Message]" = queue.Queue(maxsize=500)

    # Listener MQTT: sottoscrive topic_filter e inserisce eventi grezzi in mqtt_event_queue.
    mqtt_listener = MQTTEventListener(
        broker_host=config.MQTT_BROKER_HOST,
        broker_port=config.MQTT_BROKER_PORT,
        topic_filter=config.MQTT_TOPIC_FILTER,
        event_queue=mqtt_event_queue,
    )
    mqtt_listener.start()

    # Router: trasforma e smista eventi dalla coda centrale verso le code dei distretti.
    router = MQTTRouterThread(
        mqtt_event_queue=mqtt_event_queue,
        district_queues=district_event_queues,
    )
    router.start()

    # CityCoordinatorAgent: gestisce escalation e invia comandi di coordinamento ai distretti.
    coordinator_agent = CityCoordinatorAgent(
        inbox_queue=coordinator_inbox,
        district_control_queues=district_control_queues,
    )
    coordinator_agent.start()

    # Avvio degli agenti di distretto: uno per ogni distretto configurato.
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
        """
        Handler di terminazione per SIGINT/SIGTERM.

        Obiettivo
        ---------
        Arrestare in modo ordinato tutti i thread, riducendo la probabilità di:
        - perdita di messaggi ancora in elaborazione;
        - log incompleti;
        - risorse esterne non rilasciate (socket MQTT, ecc.).

        Args:
            signum: Segnale ricevuto (SIGINT o SIGTERM).
            frame: Frame stack (non utilizzato; richiesto dalla signature signal handler).
        """
        logger.info("Segnale di terminazione ricevuto (%s). Arresto in corso...", signum)

        # Stop cooperativo: ogni agente terminerà il loop principale al prossimo check.
        for agent in district_agents:
            agent.stop()

        coordinator_agent.stop()
        router.stop()
        mqtt_listener.stop()

        # Piccola attesa per consentire flush log e uscita ordinata dai loop con timeout.
        time.sleep(1.0)
        sys.exit(0)

    # Registrazione degli handler: Ctrl+C (SIGINT) e stop container (SIGTERM).
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Loop di keep-alive: il main thread resta in esecuzione mentre i thread daemon lavorano.
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        # Ridondanza difensiva: in caso di KeyboardInterrupt, si forza lo stesso flusso di shutdown.
        handle_sigterm(signal.SIGINT, None)


if __name__ == "__main__":
    # Esecuzione standalone (python -m mas.app.main oppure python mas/app/main.py).
    main()
    