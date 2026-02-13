"""
Configurazione database e sessioni SQLAlchemy per il Web Backend (FastAPI).

Obiettivo
---------
Centralizzare l'inizializzazione del layer di accesso al database, definendo:
- URL di connessione (SQLite locale su file);
- engine SQLAlchemy;
- session factory (SessionLocal);
- Base declarativa per i modelli ORM;
- dependency provider `get_db()` per l'iniezione della sessione nei path operation di FastAPI.

Ruolo nel sistema
-----------------
Il Web Backend espone API REST (es. /api/events, /api/actions) e persiste dati su SQLite.
Questo modulo fornisce il "plumbing" necessario affinché:
- i modelli ORM possano ereditare da `Base`;
- i router FastAPI possano ottenere una sessione DB tramite dependency injection,
  garantendo apertura/chiusura corretta della connessione a ogni request.

Note progettuali
----------------
- SQLite è usato come storage leggero e portabile, adatto al contesto di progetto e demo.
- `check_same_thread=False` è necessario con SQLite quando l'app usa più thread:
  consente l'uso della stessa connessione in contesti multi-thread (FastAPI/uvicorn).
- `SessionLocal` crea sessioni isolate per request, evitando condivisione indesiderata di stato.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# URL di connessione al database.
# "sqlite:///./data/urban_monitoring.db" indica un file SQLite relativo alla working directory del container/app.
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/urban_monitoring.db"

# Engine SQLAlchemy: gestisce connessioni e dialetto DB.
# connect_args include check_same_thread=False per supportare l'accesso multi-thread con SQLite.
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Factory per creare sessioni DB.
# - autocommit=False: commit esplicito (controllo transazioni).
# - autoflush=False: flush esplicito o implicito su commit, riducendo side effects inattesi.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base declarativa: i modelli ORM (es. Event, Action) erediteranno da questa classe.
Base = declarative_base()


def get_db():
    """
    Dependency provider per FastAPI: fornisce una sessione SQLAlchemy per request.

    Flusso
    ------
    - Crea una sessione tramite SessionLocal().
    - La rende disponibile al chiamante tramite yield (pattern dependency generator).
    - Garantisce la chiusura della sessione nel blocco finally.

    Yields:
        Session: Sessione SQLAlchemy pronta per query e transazioni.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Chiusura sessione: rilascia connessioni e risorse associate.
        db.close()
