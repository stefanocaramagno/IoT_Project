from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

# Creazione delle tabelle al primo avvio
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Urban Monitoring MAS - Web Backend")


@app.get("/", response_class=HTMLResponse)
async def root():
    return '''
    <html>
      <head>
        <title>Urban Monitoring MAS</title>
      </head>
      <body>
        <h1>Urban Monitoring MAS - Web Backend è in esecuzione</h1>
        <p>Fase 4: persistenza degli eventi e delle azioni in SQLite tramite SQLAlchemy.</p>
        <p>Endpoint: POST /api/events, POST /api/actions, GET /api/events, GET /api/actions</p>
      </body>
    </html>
    '''


@app.post("/api/events", response_model=schemas.EventRead)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    db_event = models.Event(
        district=event.district,
        sensor_type=event.sensor_type,
        value=event.value,
        unit=event.unit,
        severity=event.severity,
        timestamp=event.timestamp,
        topic=event.topic,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.get("/api/events", response_model=list[schemas.EventRead])
def list_events(db: Session = Depends(get_db), limit: int = 100):
    return db.query(models.Event).order_by(models.Event.id.desc()).limit(limit).all()


@app.post("/api/actions", response_model=schemas.ActionRead)
def create_action(action: schemas.ActionCreate, db: Session = Depends(get_db)):
    import json

    # Salviamo lo snapshot come stringa JSON nel DB
    db_action = models.Action(
        source_district=action.source_district,
        target_district=action.target_district,
        action_type=action.action_type,
        reason=action.reason or "",
        event_snapshot=json.dumps(action.event_snapshot),
    )
    db.add(db_action)
    db.commit()
    db.refresh(db_action)

    # Ma restituiamo un ActionRead con event_snapshot come dict
    snapshot_dict = json.loads(db_action.event_snapshot) if db_action.event_snapshot else {}
    return schemas.ActionRead(
        id=db_action.id,
        source_district=db_action.source_district,
        target_district=db_action.target_district,
        action_type=db_action.action_type,
        reason=db_action.reason,
        event_snapshot=snapshot_dict,
    )


@app.get("/api/actions", response_model=list[schemas.ActionRead])
def list_actions(db: Session = Depends(get_db), limit: int = 100):
    import json

    actions = db.query(models.Action).order_by(models.Action.id.desc()).limit(limit).all()
    result: list[schemas.ActionRead] = []
    for a in actions:
        snapshot = json.loads(a.event_snapshot) if a.event_snapshot else {}
        result.append(
            schemas.ActionRead(
                id=a.id,
                source_district=a.source_district,
                target_district=a.target_district,
                action_type=a.action_type,
                reason=a.reason,
                event_snapshot=snapshot,
            )
        )
    return result