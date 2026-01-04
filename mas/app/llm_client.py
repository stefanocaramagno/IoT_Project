import logging
from typing import Any, Dict, List

import requests

from . import config

logger = logging.getLogger(__name__)

DECIDE_ESCALATION_ENDPOINT = f"{config.LLM_GATEWAY_URL.rstrip('/')}/llm/decide_escalation"
PLAN_COORDINATION_ENDPOINT = f"{config.LLM_GATEWAY_URL.rstrip('/')}/llm/plan_coordination"


def decide_escalation(
    district: str,
    recent_events: List[Dict[str, Any]],
    current_event: Dict[str, Any],
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Invoca il microservizio LLM Gateway per decidere l'escalation.

    Restituisce un dizionario atteso con le chiavi:
    - escalate: bool
    - normalized_severity: str
    - reason: str

    In caso di errore di rete o risposta non valida, rilancia l'eccezione,
    lasciando al chiamante la responsabilità del fallback.
    """
    payload: Dict[str, Any] = {
        "district": district,
        "recent_events": recent_events,
        "current_event": current_event,
    }

    logger.debug("Chiamata a LLM Gateway /llm/decide_escalation con payload=%s", payload)

    response = requests.post(DECIDE_ESCALATION_ENDPOINT, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Risposta LLM non in formato dizionario: {data!r}")

    # Verifica minima delle chiavi attese
    if "escalate" not in data or "normalized_severity" not in data:
        raise ValueError(f"Risposta LLM priva di chiavi attese: {data!r}")

    return data


def plan_coordination(
    source_district: str,
    critical_event: Dict[str, Any],
    city_state: List[Dict[str, Any]],
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Invoca il microservizio LLM Gateway per ottenere un piano di coordinamento.

    Restituisce un dizionario atteso con la chiave:
    - plan: lista di entry, ognuna con target_district, action_type, reason.

    In caso di errore di rete o risposta non valida, rilancia l'eccezione,
    lasciando al chiamante la responsabilità del fallback.
    """
    payload: Dict[str, Any] = {
        "source_district": source_district,
        "critical_event": critical_event,
        "city_state": city_state,
    }

    logger.debug("Chiamata a LLM Gateway /llm/plan_coordination con payload=%s", payload)

    response = requests.post(PLAN_COORDINATION_ENDPOINT, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Risposta LLM (plan_coordination) non in formato dizionario: {data!r}")

    if "plan" not in data or not isinstance(data["plan"], list):
        raise ValueError(f"Risposta LLM (plan_coordination) priva di chiave 'plan' valida: {data!r}")

    return data