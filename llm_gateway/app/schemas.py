"""
Schemi Pydantic del microservizio "LLM Gateway".

Obiettivo
---------
Definire in modo rigoroso (tipizzato e validabile) i payload di input/output
degli endpoint esposti dal gateway verso il sistema Urban Monitoring MAS.

Ruolo nel sistema
-----------------
Questi modelli vengono utilizzati da FastAPI per:
- validare i payload in ingresso (request body) prima di invocare il runtime LLM;
- documentare automaticamente l'API (OpenAPI/Swagger) con tipi e descrizioni;
- validare le risposte prodotte dal runtime LLM (dopo parsing JSON), garantendo
  che l'output sia consumabile dagli agenti del MAS senza ambiguità.

Nota progettuale
----------------
La presenza di schemi di risposta (ResponseModel) è particolarmente importante
in un contesto LLM: l'output del modello può essere non deterministico o non
conforme; la validazione blocca immediatamente risposte non strutturate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SensorEventSummary(BaseModel):
    """
    Rappresentazione sintetica di un evento sensoriale rilevato in un distretto.

    Attributi
    ---------
    timestamp:
        Timestamp dell'evento (formato stringa; es. ISO 8601).
    sensor_type:
        Tipo di sensore o metrica (es. traffic, pollution, noise, ecc.).
    value:
        Valore numerico rilevato.
    unit:
        Unità di misura del valore (es. "ppm", "index", "vehicles/min", ecc.).
    severity:
        Severità associata all'evento (valore testuale, tipicamente derivato
        da regole locali del MAS o dal layer di pre-processing).
    """
    timestamp: str
    sensor_type: str
    value: float
    unit: str
    severity: str


class CityStateEntry(BaseModel):
    """
    Voce di stato sintetico di un distretto, utile per decisioni di coordinamento.

    Attributi
    ---------
    district:
        Identificativo/nome del distretto.
    traffic_index:
        Indice di traffico sintetico (opzionale se non disponibile per quel distretto).
    pollution_index:
        Indice di inquinamento sintetico (opzionale se non disponibile per quel distretto).
    other_metrics:
        Dizionario di metriche aggiuntive non standardizzate, dove la chiave è il nome
        della metrica e il valore è un float; utile per estendere il sistema senza
        modificare lo schema principale.
    """
    district: str
    traffic_index: Optional[float] = None
    pollution_index: Optional[float] = None
    other_metrics: Dict[str, float] = Field(default_factory=dict)


class DecideEscalationRequest(BaseModel):
    """
    Payload di input per la decisione di escalation.

    Contiene:
    - distretto sorgente;
    - una finestra di eventi recenti (contesto);
    - l'evento corrente da valutare (focus principale).
    """
    district: str
    recent_events: List[SensorEventSummary] = Field(default_factory=list)
    current_event: SensorEventSummary


class DecideEscalationResponse(BaseModel):
    """
    Risposta strutturata per la decisione di escalation prodotta dall'LLM.

    Il gateway valida questa struttura per garantire che l'output possa essere
    consumato dagli agenti del MAS in modo deterministico.
    """
    escalate: bool
    normalized_severity: str = Field(
        ...,
        description="Severità normalizzata, ad es. 'low', 'medium', 'high'.",
    )
    reason: str = Field(..., description="Breve motivazione in linguaggio naturale.")


class PlanCoordinationRequest(BaseModel):
    """
    Payload di input per la generazione di un piano di coordinamento.

    Contiene:
    - distretto sorgente che segnala l'evento critico;
    - evento critico (oggetto SensorEventSummary);
    - stato sintetico della città (lista di distretti con indicatori principali).
    """
    source_district: str
    critical_event: SensorEventSummary
    city_state: List[CityStateEntry] = Field(
        default_factory=list,
        description="Stato sintetico dei quartieri della città.",
    )


class PlanEntry(BaseModel):
    """
    Singola azione di coordinamento proposta dall'LLM.

    Attributi
    ---------
    target_district:
        Distretto destinatario dell'azione (deve essere diverso dal source_district
        secondo i vincoli imposti dal prompt nel client LLM).
    action_type:
        Codice dell'azione da intraprendere (es. invio risorse, deviazione flussi, ecc.).
    reason:
        Motivazione sintetica della scelta.
    """
    target_district: str
    action_type: str
    reason: str


class PlanCoordinationResponse(BaseModel):
    """
    Risposta strutturata contenente un piano di coordinamento.

    Il piano è modellato come lista di PlanEntry per permettere la proposta di più
    azioni coordinate verso distretti diversi.
    """
    plan: List[PlanEntry] = Field(
        default_factory=list,
        description="Lista di azioni di coordinamento proposte dall'LLM.",
    )
