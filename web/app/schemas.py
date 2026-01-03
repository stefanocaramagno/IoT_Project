from typing import Any, Dict, Optional

from pydantic import BaseModel


class EventCreate(BaseModel):
    district: str
    sensor_type: str
    value: float
    unit: str
    severity: str
    timestamp: str
    topic: str


class EventRead(EventCreate):
    id: int

    class Config:
        orm_mode = True


class ActionCreate(BaseModel):
    source_district: str
    target_district: str
    action_type: str
    reason: Optional[str] = None
    event_snapshot: Dict[str, Any]


class ActionRead(ActionCreate):
    id: int

    class Config:
        orm_mode = True
