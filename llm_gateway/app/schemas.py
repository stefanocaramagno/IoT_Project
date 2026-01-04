from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SensorEventSummary(BaseModel):
    """Rappresentazione compatta di un evento sensore per l'LLM."""

    timestamp: str
    sensor_type: str
    value: float
    unit: str
    severity: str

class CityStateEntry(BaseModel):
    """Stato sintetico di un quartiere per il coordinamento."""

    district: str
    traffic_index: Optional[float] = None
    pollution_index: Optional[float] = None
    other_metrics: Dict[str, float] = Field(default_factory=dict)

class DecideEscalationRequest(BaseModel):
    district: str
    recent_events: List[SensorEventSummary] = Field(default_factory=list)
    current_event: SensorEventSummary

class DecideEscalationResponse(BaseModel):
    escalate: bool
    normalized_severity: str = Field(
        ...,
        description="Severità normalizzata, ad es. 'low', 'medium', 'high'.",
    )
    reason: str = Field(..., description="Breve motivazione in linguaggio naturale.")

class PlanCoordinationRequest(BaseModel):
    source_district: str
    critical_event: SensorEventSummary
    city_state: List[CityStateEntry] = Field(
        default_factory=list,
        description="Stato sintetico dei quartieri della città.",
    )

class PlanEntry(BaseModel):
    target_district: str
    action_type: str
    reason: str

class PlanCoordinationResponse(BaseModel):
    plan: List[PlanEntry] = Field(
        default_factory=list,
        description="Lista di azioni di coordinamento proposte dall'LLM.",
    )
    