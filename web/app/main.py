from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db

# Creazione delle tabelle al primo avvio
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Urban Monitoring MAS - Web Backend")

# Static & templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


# ----------------------
# Pagina principale (redirect a dashboard)
# ----------------------
@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/dashboard")


# ----------------------
# Pagine HTML (Jinja2)
# ----------------------
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
):
    # Ultimi eventi e ultime azioni
    latest_events = db.query(models.Event).order_by(models.Event.id.desc()).limit(50).all()
    latest_actions = db.query(models.Action).order_by(models.Action.id.desc()).limit(20).all()

    # Statistiche semplici per quartiere e severità
    from sqlalchemy import func

    events_per_district = (
        db.query(models.Event.district, func.count(models.Event.id))
        .group_by(models.Event.district)
        .all()
    )
    events_per_severity = (
        db.query(models.Event.severity, func.count(models.Event.id))
        .group_by(models.Event.severity)
        .all()
    )

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "events": latest_events,
            "actions": latest_actions,
            "events_per_district": events_per_district,
            "events_per_severity": events_per_severity,
        },
    )


@app.get("/events", response_class=HTMLResponse)
def events_page(
    request: Request,
    district: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.Event).order_by(models.Event.id.desc())
    if district:
        query = query.filter(models.Event.district == district)
    if severity:
        query = query.filter(models.Event.severity == severity)

    events = query.limit(limit).all()

    # Valori distinti per i filtri
    distinct_districts = [d[0] for d in db.query(models.Event.district).distinct().all() if d[0]]
    distinct_severities = [s[0] for s in db.query(models.Event.severity).distinct().all() if s[0]]

    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "events": events,
            "selected_district": district or "",
            "selected_severity": severity or "",
            "districts": distinct_districts,
            "severities": distinct_severities,
        },
    )


@app.get("/actions", response_class=HTMLResponse)
def actions_page(
    request: Request,
    source_district: str | None = None,
    target_district: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.Action).order_by(models.Action.id.desc())
    if source_district:
        query = query.filter(models.Action.source_district == source_district)
    if target_district:
        query = query.filter(models.Action.target_district == target_district)

    actions = query.limit(limit).all()

    # Valori distinti per i filtri
    distinct_sources = [d[0] for d in db.query(models.Action.source_district).distinct().all() if d[0]]
    distinct_targets = [d[0] for d in db.query(models.Action.target_district).distinct().all() if d[0]]

    return templates.TemplateResponse(
        "actions.html",
        {
            "request": request,
            "actions": actions,
            "selected_source": source_district or "",
            "selected_target": target_district or "",
            "sources": distinct_sources,
            "targets": distinct_targets,
        },
    )


# ----------------------
# API REST esistenti
# ----------------------
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
