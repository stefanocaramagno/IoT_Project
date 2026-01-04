from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import schemas
from .llm_client import (
    call_llm_for_decide_escalation,
    call_llm_for_plan_coordination,
)

app = FastAPI(
    title="LLM Gateway for Urban MAS",
    description=(
        "Microservizio che espone endpoint interni per delegare decisioni e spiegazioni "
        "a un modello LLM eseguito in locale (es. Mistral 7B via Ollama)."
    ),
    version="0.1.0",
)

# CORS aperto solo per semplicità; in un contesto reale si potrebbero restringere gli origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def root() -> Dict[str, str]:
    return {
        "service": "llm-gateway",
        "status": "ok",
        "message": "LLM Gateway for Urban MAS is running.",
    }


# -----------------------------
# /llm/decide_escalation
# -----------------------------


@app.post("/llm/decide_escalation", response_model=schemas.DecideEscalationResponse)
def decide_escalation(body: schemas.DecideEscalationRequest) -> Any:
    """Endpoint per decidere se effettuare un'escalation a partire da eventi sensore.

    Questo endpoint è pensato per essere chiamato dagli agenti di quartiere.
    """
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_decide_escalation(payload_dict)

    try:
        return schemas.DecideEscalationResponse.model_validate(raw_response)
    except Exception as exc:
        # Se la risposta dell'LLM non rispetta lo schema atteso,
        # solleviamo un errore esplicito.
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per decide_escalation: {exc} | raw={raw_response!r}",
        )


# -----------------------------
# /llm/plan_coordination
# -----------------------------


@app.post("/llm/plan_coordination", response_model=schemas.PlanCoordinationResponse)
def plan_coordination(body: schemas.PlanCoordinationRequest) -> Any:
    """Endpoint per ottenere un piano di coordinamento tra quartieri.

    Questo endpoint è pensato per essere chiamato dall'agente centrale.
    """
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_plan_coordination(payload_dict)

    try:
        return schemas.PlanCoordinationResponse.model_validate(raw_response)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per plan_coordination: {exc} | raw={raw_response!r}",
        )
