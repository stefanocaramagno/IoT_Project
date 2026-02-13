"""
Client HTTP del MAS verso il microservizio "LLM Gateway".

Obiettivo
---------
Incapsulare le chiamate HTTP agli endpoint interni del gateway LLM, utilizzati dal
Multi-Agent System per:
- decidere se effettuare escalation (DistrictMonitoringAgent -> CityCoordinator);
- generare un piano di coordinamento tra distretti (CityCoordinatorAgent).

Ruolo nel sistema
-----------------
Questo modulo è invocato dagli agenti del MAS (thread) per ottenere decisioni
assistite dal modello, mantenendo separata la logica di business degli agenti
dai dettagli di comunicazione HTTP.

Dipendenze esterne
------------------
- LLM Gateway (FastAPI): espone endpoint:
    - POST /llm/decide_escalation
    - POST /llm/plan_coordination
- requests: client HTTP sincrono utilizzato per invocare tali endpoint.

Configurazione
--------------
Gli URL degli endpoint sono composti a partire da `config.LLM_GATEWAY_URL`,
che può essere configurato via variabili d'ambiente nel modulo `mas/app/config.py`.

Note progettuali
----------------
- Le funzioni applicano una validazione minima della risposta (tipo e chiavi attese),
  lasciando agli agenti la gestione dei fallback in caso di eccezioni.
- `response.raise_for_status()` solleva eccezioni su status 4xx/5xx, rendendo
  immediata la gestione dell'indisponibilità del gateway o di errori applicativi.
"""

import logging
from typing import Any, Dict, List

import requests

from . import config

# Logger di modulo per tracciare chiamate e diagnostica del canale LLM.
logger = logging.getLogger(__name__)

# Endpoint del gateway LLM:
# - rstrip('/') evita doppi slash in caso di base URL che termina con '/'.
DECIDE_ESCALATION_ENDPOINT = f"{config.LLM_GATEWAY_URL.rstrip('/')}/llm/decide_escalation"
PLAN_COORDINATION_ENDPOINT = f"{config.LLM_GATEWAY_URL.rstrip('/')}/llm/plan_coordination"


def decide_escalation(
    district: str,
    recent_events: List[Dict[str, Any]],
    current_event: Dict[str, Any],
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Richiede al LLM Gateway una decisione di escalation per un evento di distretto.

    Contratto atteso (in base agli schemi del gateway)
    --------------------------------------------------
    Risposta JSON (dict) contenente almeno:
    - "escalate": bool
    - "normalized_severity": str
    - "reason": str (può essere presente e viene gestita dal chiamante)

    Args:
        district: Identificativo del distretto che richiede la valutazione.
        recent_events: Lista di eventi recenti (contesto) in formato JSON-like.
        current_event: Evento corrente da valutare (focus).
        timeout_seconds: Timeout della chiamata HTTP verso il gateway.

    Returns:
        Dict[str, Any]: Dizionario con decisione di escalation e severità normalizzata.

    Raises:
        requests.HTTPError:
            Sollevata da response.raise_for_status() in caso di status 4xx/5xx.
        ValueError:
            Se la risposta non è un dizionario o non contiene le chiavi minime attese.
    """
    # Payload conforme al request model del gateway (DecideEscalationRequest).
    payload: Dict[str, Any] = {
        "district": district,
        "recent_events": recent_events,
        "current_event": current_event,
    }

    # Logging in debug per analisi e tuning; utile in fase di test e validazione.
    logger.debug("Chiamata a LLM Gateway /llm/decide_escalation con payload=%s", payload)

    # Chiamata sincrona: in caso di timeout o errori di rete, requests solleverà eccezioni.
    response = requests.post(DECIDE_ESCALATION_ENDPOINT, json=payload, timeout=timeout_seconds)
    response.raise_for_status()

    # Decodifica JSON della risposta del gateway.
    data = response.json()
    if not isinstance(data, dict):
        # Il gateway dovrebbe sempre restituire un oggetto JSON; in caso contrario la risposta è inutilizzabile.
        raise ValueError(f"Risposta LLM non in formato dizionario: {data!r}")

    # Validazione minima: garantisce che i campi fondamentali esistano.
    if "escalate" not in data or "normalized_severity" not in data:
        raise ValueError(f"Risposta LLM priva di chiavi attese: {data!r}")

    return data


def plan_coordination(
    source_district: str,
    critical_event: Dict[str, Any],
    city_state: List[Dict[str, Any]],
    timeout_seconds: float = 30.0,
) -> Dict[str, Any]:
    """
    Richiede al LLM Gateway un piano di coordinamento inter-distrettuale.

    Contratto atteso (in base agli schemi del gateway)
    --------------------------------------------------
    Risposta JSON (dict) contenente:
    - "plan": list (lista di entry), dove ogni entry contiene tipicamente:
        - "target_district": str
        - "action_type": str
        - "reason": str

    Args:
        source_district: Distretto sorgente che ha generato l'evento critico.
        critical_event: Evento critico normalizzato da usare come input al modello.
        city_state: Stato sintetico della città (lista di distretti con metriche).
        timeout_seconds: Timeout della chiamata HTTP verso il gateway.

    Returns:
        Dict[str, Any]: Dizionario con chiave "plan" contenente una lista di azioni proposte.

    Raises:
        requests.HTTPError:
            Sollevata da response.raise_for_status() in caso di status 4xx/5xx.
        ValueError:
            Se la risposta non è un dizionario o non contiene una chiave "plan" valida.
    """
    # Payload conforme al request model del gateway (PlanCoordinationRequest).
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

    # Validazione minima: la chiave "plan" deve essere presente e deve essere una lista.
    if "plan" not in data or not isinstance(data["plan"], list):
        raise ValueError(f"Risposta LLM (plan_coordination) priva di chiave 'plan' valida: {data!r}")

    return data