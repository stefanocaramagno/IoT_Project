import logging
from typing import Any, Dict

import requests

from . import config

logger = logging.getLogger(__name__)

EVENTS_ENDPOINT = f"{config.WEB_BACKEND_URL}/api/events"
ACTIONS_ENDPOINT = f"{config.WEB_BACKEND_URL}/api/actions"


def persist_sensor_event(event_data: Dict[str, Any]) -> None:
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
        response = requests.post(EVENTS_ENDPOINT, json=payload, timeout=2.0)
        if response.status_code not in (200, 201):
            logger.warning("Persistenza evento fallita: %s %s", response.status_code, response.text)
    except Exception as exc:
        logger.error("Errore durante la persistenza dell'evento: %s", exc)


def persist_action(
    source_district: str,
    target_district: str,
    action_type: str,
    reason: str,
    event_snapshot: Dict[str, Any],
) -> None:
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
