from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, require_roles
from ..core.errors import ValidationError
from ..db import get_db
from ..models import ExternalReference, IntegrationEvent, User
from ..services import sync as sync_svc

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/references")
def references(db: Session = Depends(get_db), user: User = Depends(get_current_user),
               entity_type: str | None = None):
    q = db.query(ExternalReference)
    if entity_type:
        q = q.filter(ExternalReference.entity_type == entity_type)
    rows = q.order_by(ExternalReference.entity_type, ExternalReference.external_id).limit(200).all()
    return [{
        "entity_type": r.entity_type, "external_id": r.external_id,
        "source_system": r.source_system, "source_version": r.source_version,
        "local_id": r.local_id, "title": r.title,
        "sync_status": r.sync_status,
        "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        "payload": r.payload and __import__("json").loads(r.payload),
    } for r in rows]


class EventIn(BaseModel):
    event_type: str
    source_system: str = "payehtar360"
    external_event_id: str | None = None
    payload: dict


@router.post("/events")
def receive_event(body: EventIn, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("sys_admin", "service"))):
    """دریافت رویداد نسخه‌دار از زیرسیستم‌های زیست‌بوم (پردازش تکرارپذیر با external_event_id)."""
    if not body.payload:
        raise ValidationError("payload لازم است")
    result = sync_svc.receive_event(db, body.event_type, body.source_system, body.payload,
                                    body.external_event_id)
    write_audit(db, user, "integration_event", "integration_event", result.get("event_id"),
                after={"type": body.event_type, "status": result["status"]})
    db.commit()
    return result


@router.post("/sync/demo-pull")
def demo_pull(db: Session = Depends(get_db), user: User = Depends(require_roles("sys_admin", "service"))):
    """در حالت دمو: واکشی آزمایشی داده مرجع پایه‌یار و به‌روزرسانی رونوشت همگام‌شده."""
    n = sync_svc.demo_pull_courses(db)
    stale = sync_svc.mark_stale_refs(db)
    db.commit()
    return {"upserted": n, "marked_stale": stale}


@router.get("/outbox")
def outbox(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return sync_svc.outbox_stats(db)


@router.post("/outbox/publish")
def outbox_publish(db: Session = Depends(get_db), user: User = Depends(require_roles("sys_admin", "service"))):
    n = sync_svc.publish_outbox(db)
    db.commit()
    return {"published": n}


@router.get("/events")
def events(db: Session = Depends(get_db), user: User = Depends(get_current_user),
           page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    q = db.query(IntegrationEvent).order_by(IntegrationEvent.received_at.desc())
    total = q.count()
    rows = q.offset((page - 1) * size).limit(size).all()
    return {"items": [{"id": str(e.id), "event_type": e.event_type, "source_system": e.source_system,
                       "status": e.status, "error": e.error, "received_at": e.received_at.isoformat()}
                      for e in rows], "total": total, "page": page, "size": size}
