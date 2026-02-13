"""
Modelli ORM (SQLAlchemy) per il Web Backend del progetto Urban Monitoring MAS.

Obiettivo
---------
Definire le tabelle principali del database SQLite utilizzate dal Web Backend:
- events: eventi sensoriali prodotti dai simulatori e gestiti dagli agenti di distretto;
- actions: azioni di coordinamento emesse dal CityCoordinatorAgent (LLM o fallback).

Ruolo nel sistema
-----------------
Questi modelli costituiscono lo "schema persistente" su cui si basano:
- la persistenza via API REST (/api/events, /api/actions);
- le query e le aggregazioni per la dashboard e le pagine di analisi;
- la produzione di statistiche e dataset per i grafici.

Note progettuali
----------------
- I campi created_at sono valorizzati lato server con timestamp UTC, per garantire
  coerenza temporale indipendentemente dal fuso orario del runtime/container.
- Alcuni campi sono indicizzati (index=True) per migliorare prestazioni su filtri tipici
  (district, sensor_type, severity, action_type, source/target).
- `event_snapshot` in Action è memorizzato come testo JSON serializzato, così da conservare
  il contesto dell'evento che ha causato l'azione senza imporre uno schema rigido.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from .database import Base


def utcnow() -> datetime:
    """
    Utility per ottenere l'istante corrente in UTC.

    Motivazione
    -----------
    - Standardizza la gestione temporale nel DB, evitando ambiguità dovute al timezone locale.
    - Consente aggregazioni e filtri temporali coerenti (dashboard, window_minutes, grafici).

    Returns:
        datetime: Timestamp timezone-aware in UTC.
    """
    return datetime.now(timezone.utc)


class Event(Base):
    """
    Tabella events: rappresenta un evento sensoriale persistito dal sistema.

    Origine dati
    ------------
    - Simulatori (MQTT) -> MAS -> persistenza via Web Backend (/api/events)

    Campi principali
    ----------------
    - district, sensor_type, value, unit, severity, timestamp, topic
    - created_at: timestamp di inserimento nel DB (UTC)
    """
    __tablename__ = "events"

    # Primary key autoincrementale.
    id = Column(Integer, primary_key=True, index=True)

    # Dimensioni principali per query e filtri.
    district = Column(String, index=True)
    sensor_type = Column(String, index=True)

    # Valore numerico e unità di misura (es. veh/min, µg/m3).
    value = Column(Float)
    unit = Column(String)

    # Severità normalizzata (low/medium/high), utilizzata per KPI e grafici.
    severity = Column(String, index=True)

    # Timestamp originario dell'evento (tipicamente ISO 8601 generato dal simulatore).
    timestamp = Column(String)

    # Topic MQTT originale, utile per audit/diagnostica.
    topic = Column(String)

    # Timestamp di creazione record nel DB (timezone-aware UTC).
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
    )


class Action(Base):
    """
    Tabella actions: rappresenta un'azione di coordinamento registrata dal sistema.

    Origine dati
    ------------
    - CityCoordinatorAgent (LLM o fallback) -> persistenza via Web Backend (/api/actions)

    Campi principali
    ----------------
    - source_district: distretto che ha generato l'escalation/trigger
    - target_district: distretto destinatario della coordinazione
    - action_type: codice azione (es. REROUTE_TRAFFIC)
    - reason: motivazione (LLM o fallback marker)
    - event_snapshot: JSON serializzato dell'evento che ha originato la decisione
    - created_at: timestamp di inserimento nel DB (UTC)
    """
    __tablename__ = "actions"

    # Primary key autoincrementale.
    id = Column(Integer, primary_key=True, index=True)

    # Distretti coinvolti nell'azione (source -> target).
    source_district = Column(String, index=True)
    target_district = Column(String, index=True)

    # Tipo azione (codice), indicizzato per aggregazioni e filtri UI.
    action_type = Column(String, index=True)

    # Motivazione sintetica:
    # - può contenere una frase LLM,
    # - oppure un marker deterministico (es. "support_escalation_fallback") per distinguere le origini.
    reason = Column(String)

    # Snapshot dell'evento in formato JSON (string) per conservare contesto completo.
    event_snapshot = Column(Text)

    # Timestamp di creazione record nel DB (timezone-aware UTC).
    created_at = Column(
        DateTime(timezone=True),
        default=utcnow,
    )