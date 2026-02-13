"""
Layer di persistenza del MAS verso il Web Backend (FastAPI).

Obiettivo
---------
Fornire funzioni semplici e riusabili per salvare su backend web:
- eventi sensoriali rilevati dai distretti (sensor events)
- azioni di coordinamento decise dal CityCoordinator (actions)

Ruolo nel sistema
-----------------
Questo modulo viene invocato dagli agenti del MAS per registrare dati su un servizio
esterno (web-backend) che:
- persiste su database (es. SQLite) gli eventi e le azioni,
- espone API per consultazione e dashboarding.

Integrazione
------------
- WEB_BACKEND_URL (configurato in mas/app/config.py) è la base URL del servizio backend.
- Gli endpoint utilizzati sono:
    - POST /api/events   (EVENTS_ENDPOINT)
    - POST /api/actions  (ACTIONS_ENDPOINT)

Note progettuali
----------------
- Le chiamate HTTP usano timeout molto basso (2s) per non bloccare i thread degli agenti.
- Gli errori vengono gestiti a log senza propagare eccezioni: la persistenza è
  un "side effect" utile, ma il MAS deve continuare a funzionare anche se il backend
  è temporaneamente indisponibile.
- Il payload viene normalizzato per garantire coerenza di campi anche in presenza
  di dati parziali in ingresso.
"""

import logging
from typing import Any, Dict

import requests

from . import config

# Logger di modulo: usato per tracciare esito della persistenza e problemi di connettività.
logger = logging.getLogger(__name__)

# Endpoint REST del backend per persistenza eventi e azioni.
EVENTS_ENDPOINT = f"{config.WEB_BACKEND_URL}/api/events"
ACTIONS_ENDPOINT = f"{config.WEB_BACKEND_URL}/api/actions"


def persist_sensor_event(event_data: Dict[str, Any]) -> None:
    """
    Persiste un evento sensoriale sul web-backend.

    Args:
        event_data: Dizionario con i dati dell'evento (proveniente tipicamente da SensorEvent.to_dict()).

    Comportamento
    -------------
    - Costruisce un payload normalizzato con default sicuri.
    - Effettua una POST verso EVENTS_ENDPOINT.
    - Logga warning se il backend risponde con status diverso da 200/201.
    - In caso di eccezioni (rete, timeout, ecc.) logga errore e prosegue.
    """
    # Normalizzazione dei campi: si usa .get() con default per garantire payload completo.
    payload = {
        "district": event_data.get("district", "unknown"),
        "sensor_type": event_data.get("sensor_type", "unknown"),
        "value": event_data.get("value", 0.0),
        "unit": event_data.get("unit", ""),
        "severity": event_data.get("severity", "unknown"),
        "timestamp": event_data.get("timestamp", ""),
        "topic": event_data.get("topic", ""),
    }
    try:
        # Timeout corto: evita blocchi prolungati nei thread degli agenti.
        response = requests.post(EVENTS_ENDPOINT, json=payload, timeout=2.0)
        if response.status_code not in (200, 201):
            logger.warning("Persistenza evento fallita: %s %s", response.status_code, response.text)
    except Exception as exc:
        # Error handling conservativo: la persistenza non deve interrompere la pipeline MAS.
        logger.error("Errore durante la persistenza dell'evento: %s", exc)


def persist_action(
    source_district: str,
    target_district: str,
    action_type: str,
    reason: str,
    event_snapshot: Dict[str, Any],
) -> None:
    """
    Persiste un'azione di coordinamento sul web-backend.

    Args:
        source_district: Distretto che ha generato l'escalation (origine dell'azione).
        target_district: Distretto a cui viene inviato il comando di coordinamento.
        action_type: Codice dell'azione (es. "REROUTE_TRAFFIC").
        reason: Motivazione sintetica (LLM o fallback) associata alla decisione.
        event_snapshot: Snapshot dell'evento che ha originato il coordinamento.

    Comportamento
    -------------
    - Costruisce il payload con i campi essenziali per auditing e dashboard.
    - Effettua una POST verso ACTIONS_ENDPOINT.
    - Logga warning se status diverso da 200/201.
    - Logga errore e prosegue in caso di eccezioni.
    """
    payload = {
        "source_district": source_district,
        "target_district": target_district,
        "action_type": action_type,
        "reason": reason,
        "event_snapshot": event_snapshot,
    }
    try:
        response = requests.post(ACTIONS_ENDPOINT, json=payload, timeout=2.0)
        if response.status_code not in (200, 201):
            logger.warning("Persistenza azione fallita: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.error("Errore durante la persistenza dell'azione: %s", exc)
