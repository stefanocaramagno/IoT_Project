from __future__ import annotations

import json
from typing import Any, Dict

import requests
from fastapi import HTTPException, status

from .config import settings


def _call_ollama_chat(system_prompt: str, user_prompt: str) -> str:
    """Invoca un runtime LLM compatibile con l'API /api/chat di Ollama.

    Restituisce il contenuto testuale della risposta del modello.
    """
    # settings.api_base è un AnyHttpUrl (Pydantic), lo convertiamo esplicitamente a stringa
    base_url = str(settings.api_base).rstrip("/")
    url = f"{base_url}/api/chat"

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
    except requests.RequestException as exc:  # noqa: PERF203, BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Errore di connessione al runtime LLM: {exc}",
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Runtime LLM ha restituito status {resp.status_code}: {resp.text}",
        )

    try:
        data = resp.json()
    except json.JSONDecodeError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Risposta non valida dal runtime LLM (JSON decode error): {exc}",
        ) from exc

    message = data.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Risposta dal runtime LLM priva di 'message.content' testuale.",
        )

    return content


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    """Estrae un oggetto JSON da una risposta testuale.

    Cerca il primo '{' e l'ultima '}' e prova a fare il parse.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Nessun JSON individuato nella risposta del modello: {text!r}",
        )

    json_str = text[start : end + 1]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"JSON non valido nella risposta del modello: {exc} | raw={json_str!r}",
        ) from exc


def call_llm_for_decide_escalation(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Chiama l'LLM per decidere se effettuare un'escalation."""
    system_prompt = (
        "You are an AI assistant for an urban monitoring multi-agent system. "
        "Your task is to decide whether a local monitoring agent should escalate "
        "a situation to a city coordinator, based on recent sensor events in a district. "
        "You MUST answer strictly in JSON following the schema: "
        '{"escalate": true or false, "normalized_severity": "low|medium|high", '
        '"reason": "short explanation"}. '
        "Do not include any explanation outside of the JSON object."
    )

    user_prompt = (
        "Here is the JSON input describing the district, recent events and the current event.\n"
        "Analyze the situation and decide if an escalation is needed.\n"
        "Input JSON:\n"
        f"{json.dumps(payload, indent=2)}"
    )

    raw_text = _call_ollama_chat(system_prompt, user_prompt)
    return _extract_json_from_text(raw_text)


def call_llm_for_plan_coordination(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Chiama l'LLM per proporre un piano di coordinamento tra quartieri."""
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

    user_prompt = (
        "Here is the JSON input describing the source district, the critical event "
        "and a synthetic view of the city state.\n"
        "Propose a coordination plan as a JSON object.\n"
        "Input JSON:\n"
        f"{json.dumps(payload, indent=2)}"
    )

    raw_text = _call_ollama_chat(system_prompt, user_prompt)
    return _extract_json_from_text(raw_text)