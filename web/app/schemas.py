"""
Schema Pydantic (request/response) per il Web Backend del progetto Urban Monitoring MAS.

Obiettivo
---------
Definire i modelli di validazione e serializzazione utilizzati dagli endpoint REST:
- /api/events   (creazione e lettura eventi)
- /api/actions  (creazione e lettura azioni)

Ruolo nel sistema
-----------------
Questi schemi costituiscono il “contratto” dell'API tra:
- MAS core (che invia eventi e azioni al backend via HTTP),
- Web Backend (che valida input e serializza output),
- eventuali consumer (dashboard, strumenti di test, client esterni).

Note progettuali
----------------
- Gli schemi sono separati in Create (input) e Read (output) per distinguere:
  - campi forniti dal client (Create)
  - campi generati dal database (Read), come l'id.
- `orm_mode = True` abilita la conversione da oggetti ORM SQLAlchemy a Pydantic,
  consentendo di restituire direttamente istanze di modello dal DB.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class EventCreate(BaseModel):
    """
    Payload di creazione evento (POST /api/events).

    Campi
    -----
    - district: nome distretto (es. "quartiere1")
    - sensor_type: tipo sensore (es. "traffic", "pollution")
    - value: valore numerico rilevato
    - unit: unità di misura associata al valore
    - severity: severità normalizzata (low/medium/high)
    - timestamp: timestamp originario dell'evento (tipicamente ISO 8601)
    - topic: topic MQTT sorgente dell'evento
    """
    district: str
    sensor_type: str
    value: float
    unit: str
    severity: str
    timestamp: str
    topic: str


class EventRead(EventCreate):
    """
    Schema di lettura evento (GET /api/events e response di POST /api/events).

    Estende EventCreate aggiungendo:
    - id: identificativo univoco generato dal DB
    """
    id: int

    class Config:
        # Permette a Pydantic di leggere attributi da oggetti ORM SQLAlchemy.
        orm_mode = True


class ActionCreate(BaseModel):
    """
    Payload di creazione azione (POST /api/actions).

    Campi
    -----
    - source_district: distretto che ha originato l'escalation/trigger
    - target_district: distretto destinatario dell'azione di coordinamento
    - action_type: codice tipo azione (es. "REROUTE_TRAFFIC")
    - reason: motivazione (testo o marker fallback), opzionale
    - event_snapshot: snapshot dell'evento che ha portato alla decisione (dict)
    """
    source_district: str
    target_district: str
    action_type: str
    reason: Optional[str] = None
    event_snapshot: Dict[str, Any]


class ActionRead(ActionCreate):
    """
    Schema di lettura azione (GET /api/actions e response di POST /api/actions).

    Estende ActionCreate aggiungendo:
    - id: identificativo univoco generato dal DB
    """
    id: int

    class Config:
        # Permette a Pydantic di leggere attributi da oggetti ORM SQLAlchemy.
        orm_mode = True
