"""
Client LLM del servizio "LLM Gateway".

Obiettivo
---------
Fornire un livello di accesso centralizzato al runtime LLM (es. Ollama) per:
1) decidere se un evento debba essere escalato dal distretto al coordinatore città;
2) generare un piano di coordinamento tra distretti a seguito di un evento critico.

Ruolo nel sistema
-----------------
Questo modulo incapsula:
- la costruzione dei prompt (system + user),
- la chiamata HTTP verso l'endpoint di chat del runtime LLM,
- la validazione minima della risposta (es. presenza di `message.content`),
- l'estrazione di un oggetto JSON dalla risposta testuale del modello.

Note progettuali
------------------
- Le funzioni esposte producono e consumano dizionari Python, mantenendo il resto
  del gateway indipendente dalla forma testuale della risposta dell'LLM.
- Il contratto di output è imposto tramite prompt: l'LLM deve rispondere
  "strictly in JSON" secondo uno schema definito.
- In caso di errore verso il runtime LLM o risposta non valida, vengono sollevate
  HTTPException con codici 5xx (errore lato dipendenza esterna / gateway).
"""

from __future__ import annotations

import json
from typing import Any, Dict

import requests
from fastapi import HTTPException, status

from .config import settings


def _call_ollama_chat(system_prompt: str, user_prompt: str) -> str:
    """
    Effettua una chiamata sincrona all'endpoint di chat del runtime LLM.

    La funzione costruisce un payload compatibile con l'API /api/chat del runtime
    (es. Ollama) e restituisce la risposta testuale (`message.content`) del modello.

    Args:
        system_prompt: Prompt di sistema che definisce ruolo e vincoli dell'LLM.
        user_prompt: Prompt utente contenente contesto e input strutturato.

    Returns:
        str: Contenuto testuale della risposta del modello (message.content).

    Raises:
        HTTPException:
            - 503 in caso di errore di connessione / timeout / rete verso il runtime LLM.
            - 502 in caso di status non-200, JSON non valido, o struttura risposta inattesa.
    """
    # Normalizzazione del base URL per evitare doppi "/" nella composizione dell'endpoint.
    base_url = str(settings.api_base).rstrip("/")
    url = f"{base_url}/api/chat"

    # Payload conforme alla chat API del runtime LLM.
    # - `stream=False` richiede una risposta completa in un'unica risposta HTTP.
    # - `temperature` bassa per ridurre variabilità e favorire output strutturati (JSON).
    payload: Dict[str, Any] = {
        "model": settings.model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    try:
        resp = requests.post(url, json=payload, timeout=settings.timeout_seconds)
    except requests.RequestException as exc:
        # Errori di rete, timeout, DNS, connessione rifiutata, ecc.:
        # il gateway non può soddisfare la richiesta perché la dipendenza esterna è indisponibile.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Errore di connessione al runtime LLM: {exc}",
        ) from exc

    # Il runtime LLM deve restituire 200 OK; in caso contrario, l'errore è considerato "bad gateway".
    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Runtime LLM ha restituito status {resp.status_code}: {resp.text}",
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:
        # Il runtime ha risposto con contenuto non JSON: il gateway non può interpretare la risposta.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Risposta non valida dal runtime LLM (JSON decode error): {exc}",
        ) from exc

    # Struttura tipica: {"message": {"role": "...", "content": "..."}, ...}
    message = data.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        # Assenza di contenuto testuale: non è possibile proseguire con l'estrazione JSON.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Risposta dal runtime LLM priva di 'message.content' testuale.",
        )

    return content


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """
    Estrae un oggetto JSON da una risposta testuale del modello.

    Motivazione
    -----------
    Anche imponendo "strictly in JSON" nel prompt, alcuni modelli possono
    aggiungere testo extra. Questa funzione cerca quindi la prima '{' e l'ultima '}'
    per isolare la porzione JSON e decodificarla.

    Args:
        text: Testo grezzo restituito dal modello.

    Returns:
        Dict[str, Any]: Oggetto JSON decodificato come dizionario Python.

    Raises:
        HTTPException:
            - 502 se non viene individuato un oggetto JSON oppure se il JSON è invalido.
    """
    # Ricerca euristica dei delimitatori JSON nella risposta.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        # Nessuna porzione JSON identificabile: l'LLM non ha rispettato il vincolo richiesto.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nessun JSON individuato nella risposta del modello: {text!r}",
        )

    # Isolamento della sottostringa candidata a JSON.
    json_str = text[start : end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        # JSON sintatticamente non valido: errore imputabile all'output del modello.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JSON non valido nella risposta del modello: {exc} | raw={json_str!r}",
        ) from exc


def call_llm_for_decide_escalation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Richiede al modello la decisione di escalation di un evento di distretto.

    Contratto di output (imposto dal prompt)
    ---------------------------------------
    JSON con schema:
      {
        "escalate": true|false,
        "normalized_severity": "low|medium|high",
        "reason": "short explanation"
      }

    Args:
        payload: Dizionario contenente distretto, eventi recenti e evento corrente.

    Returns:
        Dict[str, Any]: Dizionario con decisione di escalation e severità normalizzata.
    """
    system_prompt = (
        "You are an AI assistant for an urban monitoring multi-agent system. "
        "Your task is to decide whether a local monitoring agent should escalate "
        "a situation to a city coordinator, based on recent sensor events in a district. "
        "You MUST answer strictly in JSON following the schema: "
        '{"escalate": true or false, "normalized_severity": "low|medium|high", '
        '"reason": "short explanation"}. '
        "Do not include any explanation outside of the JSON object."
    )

    # Il payload viene inserito nel prompt come JSON formattato per migliorare leggibilità
    # e ridurre ambiguità interpretativa da parte del modello.
    user_prompt = (
        "Here is the JSON input describing the district, recent events and the current event.\n"
        "Analyze the situation and decide if an escalation is needed.\n"
        "Input JSON:\n"
        f"{json.dumps(payload, indent=2)}"
    )

    raw_text = _call_ollama_chat(system_prompt, user_prompt)
    return _extract_json_from_text(raw_text)


def call_llm_for_plan_coordination(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Richiede al modello un piano di coordinamento inter-distrettuale.

    Contratto di output (imposto dal prompt)
    ---------------------------------------
    JSON con schema:
      {
        "plan": [
          {
            "target_district": "name",
            "action_type": "ACTION_CODE",
            "reason": "short explanation"
          }
        ]
      }

    Vincolo aggiuntivo:
    - target_district deve essere sempre diverso dal distretto sorgente.

    Args:
        payload: Dizionario contenente distretto sorgente, evento critico e stato sintetico città.

    Returns:
        Dict[str, Any]: Dizionario contenente una lista di azioni di coordinamento suggerite.
    """
    system_prompt = (
        "You are a coordination planner for an urban multi-agent system. "
        "A district has raised a critical event, and you must propose a coordination "
        "plan involving other districts. "
        "You MUST answer strictly in JSON following the schema: "
        '{"plan": [ {"target_district": "name", "action_type": "ACTION_CODE", '
        '"reason": "short explanation"} ] }. '
        "The target_district must always be different from the source district. "
        "Do not include any explanation outside of the JSON object."
    )

    # Il prompt fornisce contesto e vincoli, mentre l'input è espresso come JSON serializzato.
    user_prompt = (
        "Here is the JSON input describing the source district, the critical event "
        "and a synthetic view of the city state.\n"
        "Propose a coordination plan as a JSON object.\n"
        "Input JSON:\n"
        f"{json.dumps(payload, indent=2)}"
    )

    raw_text = _call_ollama_chat(system_prompt, user_prompt)
    return _extract_json_from_text(raw_text)