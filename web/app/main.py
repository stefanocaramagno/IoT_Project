from datetime import datetime, timedelta
import json

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import models, schemas
from .database import Base, engine, get_db


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Urban Monitoring MAS - Web Backend")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.get("/", include_in_schema=False)
async def root_redirect():
  return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
  request: Request,
  window_minutes: int = 0,
  db: Session = Depends(get_db),
):

  now_utc = datetime.utcnow()
  time_filtered = window_minutes > 0

  if time_filtered:
    window_minutes = max(5, min(window_minutes, 240))
    window_start = now_utc - timedelta(minutes=window_minutes)
    recent_events_q = db.query(models.Event).filter(models.Event.created_at >= window_start)
    recent_actions_q = db.query(models.Action).filter(models.Action.created_at >= window_start)
  else:
    window_start = None
    recent_events_q = db.query(models.Event)
    recent_actions_q = db.query(models.Action)

  total_events = recent_events_q.count()
  critical_events = recent_events_q.filter(models.Event.severity == "high").count()
  total_actions = recent_actions_q.count()

  recent_actions = recent_actions_q.all()
  escalation_keys = set()
  for a in recent_actions:
    try:
      snapshot = json.loads(a.event_snapshot) if a.event_snapshot else {}
    except json.JSONDecodeError:
      snapshot = {}
    district = snapshot.get("district") or a.source_district or "unknown"
    ts = snapshot.get("timestamp") or (a.created_at.isoformat() if a.created_at else "")
    key = f"{district}|{ts}"
    escalation_keys.add(key)
  escalations_triggered = len(escalation_keys)

  districts = [d[0] for d in db.query(models.Event.district).distinct().all() if d[0]]

  district_cards = []
  for district in districts:
    dq = recent_events_q.filter(models.Event.district == district)
    total = dq.count()
    high = dq.filter(models.Event.severity == "high").count()
    medium = dq.filter(models.Event.severity == "medium").count()
    low = dq.filter(models.Event.severity == "low").count()
    last_event = dq.order_by(models.Event.id.desc()).first()

    if high > 0:
      status = "critical"
    elif medium > 0:
      status = "alert"
    elif total > 0:
      status = "normal"
    else:
      status = "inactive"

    district_cards.append(
      {
        "name": district,
        "status": status,
        "total": total,
        "high": high,
        "medium": medium,
        "low": low,
        "last_event": last_event,
      }
    )

  crit_q = db.query(models.Event).filter(models.Event.severity == "high")
  if time_filtered and window_start is not None:
    crit_q = crit_q.filter(models.Event.created_at >= window_start)
  latest_critical_events = crit_q.order_by(models.Event.id.desc()).limit(10).all()

  actions_q = db.query(models.Action)
  if time_filtered and window_start is not None:
    actions_q = actions_q.filter(models.Action.created_at >= window_start)
  latest_actions = actions_q.order_by(models.Action.id.desc()).limit(10).all()

  if time_filtered and window_start is not None:
    chart_window_start = window_start
    chart_window_minutes = window_minutes
  else:
    oldest_event = db.query(models.Event).order_by(models.Event.created_at.asc()).first()
    latest_event = db.query(models.Event).order_by(models.Event.created_at.desc()).first()
    if oldest_event and latest_event and oldest_event.created_at and latest_event.created_at:
      diff = latest_event.created_at - oldest_event.created_at
      total_minutes = max(1, int(diff.total_seconds() / 60))
      chart_window_minutes = min(total_minutes, 240)
      chart_window_start = latest_event.created_at - timedelta(minutes=chart_window_minutes)
    else:
      chart_window_minutes = 60
      chart_window_start = now_utc - timedelta(minutes=chart_window_minutes)

  bucket_size_minutes = max(5, chart_window_minutes // 6)
  if bucket_size_minutes == 0:
    bucket_size_minutes = 5
  num_buckets = (chart_window_minutes + bucket_size_minutes - 1) // bucket_size_minutes

  labels: list[str] = []
  for i in range(num_buckets):
    bucket_start = chart_window_start + timedelta(minutes=i * bucket_size_minutes)
    labels.append(bucket_start.strftime("%H:%M"))

  series = {
    "low": [0] * num_buckets,
    "medium": [0] * num_buckets,
    "high": [0] * num_buckets,
  }

  chart_events_q = db.query(models.Event).filter(models.Event.created_at >= chart_window_start)
  events_for_chart = chart_events_q.all()
  for e in events_for_chart:
    if not e.created_at:
      continue
    delta = e.created_at - chart_window_start
    minutes_from_start = delta.total_seconds() / 60.0
    if minutes_from_start < 0:
      continue
    bucket_index = int(minutes_from_start // bucket_size_minutes)
    if 0 <= bucket_index < num_buckets:
      sev = (e.severity or "").lower()
      if sev in series:
        series[sev][bucket_index] += 1

  events_over_time_data = {
    "labels": labels,
    "series": series,
  }
  events_over_time_json = json.dumps(events_over_time_data)

  district_labels = [d["name"] for d in district_cards]
  district_low = [d["low"] for d in district_cards]
  district_medium = [d["medium"] for d in district_cards]
  district_high = [d["high"] for d in district_cards]

  district_events_data = {
    "labels": district_labels,
    "series": {
      "low": district_low,
      "medium": district_medium,
      "high": district_high,
    },
  }
  district_events_json = json.dumps(district_events_data)

  pipeline_data = {
    "labels": ["Critical events", "Escalations", "Coordinated actions"],
    "values": [critical_events, escalations_triggered, total_actions],
  }
  pipeline_json = json.dumps(pipeline_data)

  low_events_count = recent_events_q.filter(models.Event.severity == "low").count()
  medium_events_count = recent_events_q.filter(models.Event.severity == "medium").count()
  high_events_count = critical_events

  severity_distribution_data = {
    "labels": ["Low", "Medium", "High"],
    "values": [low_events_count, medium_events_count, high_events_count],
  }
  severity_distribution_json = json.dumps(severity_distribution_data)

  sensor_types = [
    t[0] for t in db.query(models.Event.sensor_type).distinct().all() if t[0]
  ]

  sensor_labels: list[str] = []
  sensor_low: list[int] = []
  sensor_medium: list[int] = []
  sensor_high: list[int] = []

  for s_type in sensor_types:
    sq = recent_events_q.filter(models.Event.sensor_type == s_type)
    sensor_labels.append(s_type)
    sensor_low.append(sq.filter(models.Event.severity == "low").count())
    sensor_medium.append(sq.filter(models.Event.severity == "medium").count())
    sensor_high.append(sq.filter(models.Event.severity == "high").count())

  sensor_events_data = {
    "labels": sensor_labels,
    "series": {
      "low": sensor_low,
      "medium": sensor_medium,
      "high": sensor_high,
    },
  }
  events_by_sensor_type_severity_json = json.dumps(sensor_events_data)

  sensor_type_counts = (
    recent_events_q.with_entities(
      models.Event.sensor_type,
      func.count(models.Event.id),
    )
    .group_by(models.Event.sensor_type)
    .all()
  )

  sensor_type_counts_sorted = sorted(
    sensor_type_counts, key=lambda r: r[1], reverse=True
  )

  sensor_dist_labels: list[str] = []
  sensor_dist_values: list[int] = []

  for s_type, cnt in sensor_type_counts_sorted:
    label = s_type if s_type else "UNKNOWN"
    sensor_dist_labels.append(label)
    sensor_dist_values.append(cnt)

  sensor_type_distribution_data = {
    "labels": sensor_dist_labels,
    "values": sensor_dist_values,
  }
  sensor_type_distribution_json = json.dumps(sensor_type_distribution_data)

  actions_by_type_rows = (
    recent_actions_q.with_entities(
      models.Action.action_type,
      func.count(models.Action.id),
    )
    .group_by(models.Action.action_type)
    .all()
  )

  sorted_rows = sorted(actions_by_type_rows, key=lambda r: r[1], reverse=True)
  max_types = 8
  main_rows = sorted_rows[:max_types]
  extra_rows = sorted_rows[max_types:]

  action_type_labels: list[str] = []
  action_type_values: list[int] = []

  for atype, cnt in main_rows:
    label = atype or "UNKNOWN"
    action_type_labels.append(label)
    action_type_values.append(cnt)

  if extra_rows:
    other_count = sum(cnt for _, cnt in extra_rows)
    if other_count > 0:
      action_type_labels.append("Other")
      action_type_values.append(other_count)

  actions_type_data = {
    "labels": action_type_labels,
    "values": action_type_values,
  }
  actions_type_json = json.dumps(actions_type_data)

  events_preview = (
    recent_events_q.order_by(models.Event.id.desc())
    .limit(20)
    .all()
  )

  actions_preview_db = (
    recent_actions_q.order_by(models.Action.id.desc())
    .limit(20)
    .all()
  )

  actions_preview = []
  for a in actions_preview_db:
    try:
      snapshot = json.loads(a.event_snapshot) if a.event_snapshot else {}
    except json.JSONDecodeError:
      snapshot = {}

    sdistrict = snapshot.get("district")
    ssensor = snapshot.get("sensor_type") or snapshot.get("type")
    svalue = snapshot.get("value")
    sunit = snapshot.get("unit")
    sseverity = snapshot.get("severity")

    parts = []
    if sdistrict:
      parts.append(str(sdistrict))
    if ssensor:
      parts.append(str(ssensor))
    if sseverity:
      parts.append(str(sseverity))
    if svalue is not None:
      if sunit:
        parts.append(f"{svalue} {sunit}")
      else:
        parts.append(str(svalue))
    snapshot_summary = " · ".join(parts) if parts else "—"

    actions_preview.append(
      {
        "id": a.id,
        "source_district": a.source_district,
        "target_district": a.target_district,
        "action_type": a.action_type,
        "reason": a.reason,
        "created_at_str": a.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if a.created_at else "",
        "snapshot_summary": snapshot_summary,
      }
    )

  return templates.TemplateResponse(
    "dashboard.html",
    {
      "request": request,
      "now_utc": now_utc,
      "window_minutes": window_minutes,
      "time_filtered": time_filtered,
      "total_events": total_events,
      "critical_events": critical_events,
      "escalations_triggered": escalations_triggered,
      "total_actions": total_actions,
      "district_cards": district_cards,
      "latest_critical_events": latest_critical_events,
      "latest_actions": latest_actions,
      "events_over_time_json": events_over_time_json,
      "events_by_district_severity_json": district_events_json,
      "critical_pipeline_json": pipeline_json,
      "severity_distribution_json": severity_distribution_json,
      "events_by_sensor_type_severity_json": events_by_sensor_type_severity_json,
      "sensor_type_distribution_json": sensor_type_distribution_json,
      "actions_by_type_json": actions_type_json,
      "events_preview": events_preview,
      "actions_preview": actions_preview,
    },
  )

@app.get("/events", response_class=HTMLResponse)
def events_page(
  request: Request,
  district: str | None = None,
  severity: str | None = None,
  sensor_type: str | None = None,
  q: str | None = None,
  window_minutes: int = 0,
  limit: int = 0,
  db: Session = Depends(get_db),
):

  now_utc = datetime.utcnow()
  time_filtered = window_minutes > 0

  if time_filtered:
    window_minutes = max(5, min(window_minutes, 240))
    window_start = now_utc - timedelta(minutes=window_minutes)
    base_query = db.query(models.Event).filter(models.Event.created_at >= window_start)
  else:
    window_start = None
    base_query = db.query(models.Event)

  filtered_query = base_query

  if district:
    filtered_query = filtered_query.filter(models.Event.district == district)
  if severity:
    filtered_query = filtered_query.filter(models.Event.severity == severity)
  if sensor_type:
    filtered_query = filtered_query.filter(models.Event.sensor_type == sensor_type)
  if q:
    like_pattern = f"%{q}%"
    filtered_query = filtered_query.filter(
      or_(
        models.Event.district.ilike(like_pattern),
        models.Event.sensor_type.ilike(like_pattern),
        models.Event.topic.ilike(like_pattern),
      )
    )

  filtered_events_count = filtered_query.count()
  filtered_critical_count = filtered_query.filter(models.Event.severity == "high").count()
  total_events_count = db.query(models.Event).count()

  ordered_query = filtered_query.order_by(models.Event.id.desc())
  if limit > 0:
    events = ordered_query.limit(limit).all()
  else:
    events = ordered_query.all()

  distinct_districts = [d[0] for d in db.query(models.Event.district).distinct().all() if d[0]]
  distinct_severities = [s[0] for s in db.query(models.Event.severity).distinct().all() if s[0]]
  distinct_sensor_types = [t[0] for t in db.query(models.Event.sensor_type).distinct().all() if t[0]]

  return templates.TemplateResponse(
    "events.html",
    {
      "request": request,
      "events": events,
      "districts": distinct_districts,
      "severities": distinct_severities,
      "sensor_types": distinct_sensor_types,
      "selected_district": district or "",
      "selected_severity": severity or "",
      "selected_sensor_type": sensor_type or "",
      "q": q or "",
      "limit": limit,
      "now_utc": now_utc,
      "window_minutes": window_minutes,
      "time_filtered": time_filtered,
      "filtered_events_count": filtered_events_count,
      "filtered_critical_count": filtered_critical_count,
      "total_events_count": total_events_count,
    },
  )

@app.get("/actions", response_class=HTMLResponse)
def actions_page(
  request: Request,
  source_district: str | None = None,
  target_district: str | None = None,
  action_type: str | None = None,
  q: str | None = None,
  window_minutes: int = 0,
  limit: int = 0,
  db: Session = Depends(get_db),
):

  now_utc = datetime.utcnow()
  time_filtered = window_minutes > 0

  if time_filtered:
    window_minutes = max(5, min(window_minutes, 240))
    window_start = now_utc - timedelta(minutes=window_minutes)
    base_query = db.query(models.Action).filter(models.Action.created_at >= window_start)
  else:
    window_start = None
    base_query = db.query(models.Action)

  filtered_query = base_query

  if source_district:
    filtered_query = filtered_query.filter(models.Action.source_district == source_district)
  if target_district:
    filtered_query = filtered_query.filter(models.Action.target_district == target_district)
  if action_type:
    filtered_query = filtered_query.filter(models.Action.action_type == action_type)
  if q:
    like_pattern = f"%{q}%"
    filtered_query = filtered_query.filter(
      or_(
        models.Action.reason.ilike(like_pattern),
        models.Action.event_snapshot.ilike(like_pattern),
      )
    )

  filtered_actions_count = filtered_query.count()

  distinct_links_count = (
    filtered_query.with_entities(
      models.Action.source_district,
      models.Action.target_district,
    )
    .distinct()
    .count()
  )

  actions_by_type = (
    filtered_query.with_entities(
      models.Action.action_type,
      func.count(models.Action.id),
    )
    .group_by(models.Action.action_type)
    .all()
  )

  total_actions_count = db.query(models.Action).count()

  ordered_query = filtered_query.order_by(models.Action.id.desc())
  if limit > 0:
    actions_db = ordered_query.limit(limit).all()
  else:
    actions_db = ordered_query.all()

  distinct_sources = [d[0] for d in db.query(models.Action.source_district).distinct().all() if d[0]]
  distinct_targets = [t[0] for t in db.query(models.Action.target_district).distinct().all() if t[0]]
  distinct_action_types = [t[0] for t in db.query(models.Action.action_type).distinct().all() if t[0]]

  actions_view = []
  for a in actions_db:
    try:
      snapshot = json.loads(a.event_snapshot) if a.event_snapshot else {}
    except json.JSONDecodeError:
      snapshot = {}

    sdistrict = snapshot.get("district")
    ssensor = snapshot.get("sensor_type") or snapshot.get("type")
    svalue = snapshot.get("value")
    sunit = snapshot.get("unit")
    sseverity = snapshot.get("severity")
    stimestamp = snapshot.get("timestamp")
    stopic = snapshot.get("topic")

    sevent_id = snapshot.get("id") or snapshot.get("event_id")
    screated_at = snapshot.get("created_at") or snapshot.get("timestamp")

    parts = []
    if sdistrict:
      parts.append(str(sdistrict))
    if ssensor:
      parts.append(str(ssensor))
    if sseverity:
      parts.append(str(sseverity))
    if svalue is not None:
      if sunit:
        parts.append(f"{svalue} {sunit}")
      else:
        parts.append(str(svalue))
    snapshot_summary = " · ".join(parts) if parts else "—"

    actions_view.append(
      {
        "id": a.id,
        "source_district": a.source_district,
        "target_district": a.target_district,
        "action_type": a.action_type,
        "reason": a.reason,
        "created_at_str": a.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if a.created_at else "",
        "snapshot_district": sdistrict or "",
        "snapshot_sensor_type": ssensor or "",
        "snapshot_value": "" if svalue is None else str(svalue),
        "snapshot_unit": sunit or "",
        "snapshot_severity": sseverity or "",
        "snapshot_timestamp": stimestamp or "",
        "snapshot_topic": stopic or "",
        "snapshot_summary": snapshot_summary,
        "snapshot_event_id": "" if sevent_id is None else str(sevent_id),
        "snapshot_created_at": screated_at or "",
      }
    )

  return templates.TemplateResponse(
    "actions.html",
    {
      "request": request,
      "now_utc": now_utc,
      "time_filtered": time_filtered,
      "window_minutes": window_minutes,
      "actions": actions_view,
      "filtered_actions_count": filtered_actions_count,
      "distinct_links_count": distinct_links_count,
      "actions_by_type": actions_by_type,
      "total_actions_count": total_actions_count,
      "sources": distinct_sources,
      "targets": distinct_targets,
      "action_types": distinct_action_types,
      "selected_source_district": source_district or "",
      "selected_target_district": target_district or "",
      "selected_action_type": action_type or "",
      "q": q or "",
      "limit": limit,
    },
  )

@app.get("/llm-insights", response_class=HTMLResponse)
def llm_insights_page(
  request: Request,
  origin: str = "all",
  source_district: str | None = None,
  target_district: str | None = None,
  action_type: str | None = None,
  window_minutes: int = 0,
  limit: int = 0,
  db: Session = Depends(get_db),
):

  now_utc = datetime.utcnow()
  time_filtered = window_minutes > 0

  if time_filtered:
    window_minutes = max(5, min(window_minutes, 240))
    window_start = now_utc - timedelta(minutes=window_minutes)
    base_query = db.query(models.Action).filter(models.Action.created_at >= window_start)
  else:
    window_start = None
    base_query = db.query(models.Action)

  filtered_query = base_query

  if source_district:
    filtered_query = filtered_query.filter(models.Action.source_district == source_district)
  if target_district:
    filtered_query = filtered_query.filter(models.Action.target_district == target_district)
  if action_type:
    filtered_query = filtered_query.filter(models.Action.action_type == action_type)

  if origin == "llm":
    filtered_query = filtered_query.filter(models.Action.reason != "support_escalation_fallback")
  elif origin == "fallback":
    filtered_query = filtered_query.filter(models.Action.reason == "support_escalation_fallback")

  total_actions_count = db.query(models.Action).count()
  filtered_actions = filtered_query.all()
  filtered_actions_count = len(filtered_actions)

  llm_actions = [a for a in filtered_actions if a.reason != "support_escalation_fallback"]
  fallback_actions = [a for a in filtered_actions if a.reason == "support_escalation_fallback"]

  llm_actions_count = len(llm_actions)
  fallback_actions_count = len(fallback_actions)

  if filtered_actions_count > 0:
    llm_pct = int(round(llm_actions_count * 100.0 / filtered_actions_count))
    fallback_pct = 100 - llm_pct
  else:
    llm_pct = 0
    fallback_pct = 0

  district_stats_map: dict[str, dict] = {}
  for a in filtered_actions:
    dname = a.target_district or "unknown"
    row = district_stats_map.setdefault(
      dname,
      {"district": dname, "llm": 0, "fallback": 0, "total": 0},
    )
    if a.reason == "support_escalation_fallback":
      row["fallback"] += 1
    else:
      row["llm"] += 1
    row["total"] += 1

  district_stats = sorted(district_stats_map.values(), key=lambda r: r["district"])

  districts_impacted_by_llm = len({a.target_district for a in llm_actions if a.target_district})
  total_districts_with_actions = len({a.target_district for a in filtered_actions if a.target_district})

  action_type_stats_map: dict[str, dict] = {}
  for a in filtered_actions:
    key = a.action_type or "UNKNOWN"
    row = action_type_stats_map.setdefault(
      key,
      {"action_type": key, "llm": 0, "fallback": 0, "total": 0},
    )
    if a.reason == "support_escalation_fallback":
      row["fallback"] += 1
    else:
      row["llm"] += 1
    row["total"] += 1

  action_type_stats = sorted(action_type_stats_map.values(), key=lambda r: r["action_type"])

  ordered_for_decisions = filtered_query.order_by(
    models.Action.created_at.desc(), models.Action.id.desc()
  )
  if limit > 0:
    actions_for_decisions = ordered_for_decisions.limit(limit).all()
  else:
    actions_for_decisions = ordered_for_decisions.all()

  decisions = []
  for a in actions_for_decisions:
    try:
      snapshot = json.loads(a.event_snapshot) if a.event_snapshot else {}
    except json.JSONDecodeError:
      snapshot = {}

    origin_label = "fallback" if a.reason == "support_escalation_fallback" else "llm"

    sdistrict = snapshot.get("district")
    ssensor = snapshot.get("sensor_type") or snapshot.get("type")
    svalue = snapshot.get("value")
    sunit = snapshot.get("unit")
    sseverity = snapshot.get("severity")
    stimestamp = snapshot.get("timestamp")
    stopic = snapshot.get("topic")
    sevent_id = snapshot.get("id") or snapshot.get("event_id")
    screated_at = snapshot.get("created_at") or snapshot.get("timestamp")

    decisions.append(
      {
        "id": a.id,
        "origin": origin_label,
        "source_district": a.source_district,
        "target_district": a.target_district,
        "action_type": a.action_type,
        "reason": a.reason,
        "created_at": a.created_at,
        "event_sensor_type": ssensor or "",
        "event_severity": sseverity or "",
        "event_district": sdistrict or "",
        "event_timestamp": stimestamp or "",
        "event_value": "" if svalue is None else str(svalue),
        "event_unit": sunit or "",
        "event_topic": stopic or "",
        "event_id": "" if sevent_id is None else str(sevent_id),
        "event_created_at": screated_at or "",
      }
    )

  source_districts = [d[0] for d in db.query(models.Action.source_district).distinct().all() if d[0]]
  target_districts = [d[0] for d in db.query(models.Action.target_district).distinct().all() if d[0]]
  action_types = [t[0] for t in db.query(models.Action.action_type).distinct().all() if t[0]]

  return templates.TemplateResponse(
    "llm_insights.html",
    {
      "request": request,
      "now_utc": now_utc,
      "time_filtered": time_filtered,
      "window_minutes": window_minutes,
      "selected_origin": origin,
      "selected_source_district": source_district or "",
      "selected_target_district": target_district or "",
      "selected_action_type": action_type or "",
      "limit": limit,
      "filtered_actions_count": filtered_actions_count,
      "total_actions_count": total_actions_count,
      "llm_actions_count": llm_actions_count,
      "fallback_actions_count": fallback_actions_count,
      "llm_pct": llm_pct,
      "fallback_pct": fallback_pct,
      "districts_impacted_by_llm": districts_impacted_by_llm,
      "total_districts_with_actions": total_districts_with_actions,
      "district_stats": district_stats,
      "action_type_stats": action_type_stats,
      "decisions": decisions,
      "source_districts": source_districts,
      "target_districts": target_districts,
      "action_types": action_types,
    },
  )

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