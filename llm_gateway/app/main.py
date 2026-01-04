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


@app.post("/llm/decide_escalation", response_model=schemas.DecideEscalationResponse)
def decide_escalation(body: schemas.DecideEscalationRequest) -> Any:
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_decide_escalation(payload_dict)

    try:
        return schemas.DecideEscalationResponse.model_validate(raw_response)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per decide_escalation: {exc} | raw={raw_response!r}",
        )


@app.post("/llm/plan_coordination", response_model=schemas.PlanCoordinationResponse)
def plan_coordination(body: schemas.PlanCoordinationRequest) -> Any:
    payload_dict: Dict[str, Any] = body.model_dump()
    raw_response = call_llm_for_plan_coordination(payload_dict)

    try:
        return schemas.PlanCoordinationResponse.model_validate(raw_response)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Risposta LLM non valida per plan_coordination: {exc} | raw={raw_response!r}",
        )
