"""
Entry point FastAPI del microservizio "LLM Gateway".

Obiettivo
---------
Esporre endpoint HTTP interni al sistema Urban Monitoring MAS per delegare a un
modello LLM (eseguito localmente, es. via Ollama) alcune decisioni di supporto:
- valutazione di escalation (distretto -> coordinatore città)
- pianificazione di coordinamento tra distretti a seguito di un evento critico

Ruolo nel sistema
-----------------
Questo servizio funge da "gateway" controllato verso il runtime LLM:
- riceve richieste validate via schemi Pydantic (schemas.*)
- costruisce un payload dizionario da inoltrare al client LLM
- invoca il runtime LLM tramite llm_client
- valida la risposta rispetto agli schemi di output attesi
- in caso di risposta non conforme, produce un errore esplicito (HTTP 500) con raw payload

Nota progettuale
----
La validazione dell'output è intenzionalmente demandata agli schemi Pydantic:
in tal modo, il sistema non accetta risposte non strutturate o fuori contratto,
riducendo l'impatto di comportamenti non deterministici del modello.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import schemas
from .llm_client import (
    call_llm_for_decide_escalation,
    call_llm_for_plan_coordination,
)

# Istanza dell'applicazione FastAPI.
# I metadati (title, description, version) migliorano la qualità della documentazione
# OpenAPI auto-generata e la leggibilità dell'architettura per revisori e manutentori.
app = FastAPI(
    title="LLM Gateway for Urban MAS",
    description=(
        "Microservizio che espone endpoint interni per delegare decisioni e spiegazioni "
        "a un modello LLM eseguito in locale (es. Mistral 7B via Ollama)."
    ),
    version="0.1.0",
)

# Middleware CORS: consente l'accesso anche da dashboard/servizi web esterni al container.
# In contesto di progetto accademico viene lasciato permissivo ("*") per semplicità di integrazione.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> Dict[str, str]:
    """
    Endpoint di health/status minimale.

    Returns:
        Dict[str, str]: Informazioni essenziali sul servizio, utili per smoke test e debug.
    """
    return {
        "service": "llm-gateway",
        "status": "ok",
        "message": "LLM Gateway for Urban MAS is running.",
    }


@app.post("/llm/decide_escalation", response_model=schemas.DecideEscalationResponse)
def decide_escalation(body: schemas.DecideEscalationRequest) -> Any:
    """
    Endpoint per la decisione di escalation di un evento di distretto.

    Flusso
    ------
    1) Validazione input tramite DecideEscalationRequest (Pydantic).
    2) Serializzazione in dict per passaggio al client LLM.
    3) Invocazione del runtime LLM tramite call_llm_for_decide_escalation.
    4) Validazione della risposta tramite DecideEscalationResponse.

    Args:
        body: Payload strutturato contenente informazioni su distretto ed eventi.

    Returns:
        Any: Oggetto validato conforme a DecideEscalationResponse.

    Raises:
        HTTPException:
            500 se la risposta dell'LLM non rispetta lo schema atteso, indicando
            esplicitamente l'errore di validazione e il contenuto grezzo ricevuto.
    """
    # Conversione in dict per un payload JSON-serializzabile e indipendente dal modello Pydantic.
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_decide_escalation(payload_dict)

    try:
        # Validazione "hard" dell'output: il sistema accetta solo risposte conformi allo schema.
        return schemas.DecideEscalationResponse.model_validate(raw_response)
    except Exception as exc:
        # L'errore viene riportato come 500 perché la risposta non è utilizzabile dal MAS.
        # `raw_response` è incluso nel detail per facilitare debug e tuning dei prompt.
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per decide_escalation: {exc} | raw={raw_response!r}",
        )


@app.post("/llm/plan_coordination", response_model=schemas.PlanCoordinationResponse)
def plan_coordination(body: schemas.PlanCoordinationRequest) -> Any:
    """
    Endpoint per la generazione di un piano di coordinamento inter-distrettuale.

    Flusso
    ------
    1) Validazione input tramite PlanCoordinationRequest (Pydantic).
    2) Serializzazione in dict per passaggio al client LLM.
    3) Invocazione del runtime LLM tramite call_llm_for_plan_coordination.
    4) Validazione della risposta tramite PlanCoordinationResponse.

    Args:
        body: Payload strutturato con distretto sorgente, evento critico e stato sintetico città.

    Returns:
        Any: Oggetto validato conforme a PlanCoordinationResponse.

    Raises:
        HTTPException:
            500 se la risposta dell'LLM non rispetta lo schema atteso.
    """
    # Conversione in dict per ottenere una struttura semplice e serializzabile.
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_plan_coordination(payload_dict)

    try:
        # Validazione della struttura del piano per garantire che l'output sia consumabile
        # dal CityCoordinatorAgent o da componenti equivalenti nel MAS.
        return schemas.PlanCoordinationResponse.model_validate(raw_response)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per plan_coordination: {exc} | raw={raw_response!r}",
        )