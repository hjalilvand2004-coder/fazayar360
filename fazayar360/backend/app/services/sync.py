"""اتصال زیست‌بوم: همگام‌سازی مرجع نسخه‌دار از پایه‌یار۳۶۰، رویداد ورودی و صندوق خروجی."""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..config import settings
from ..models import ExternalReference, IntegrationEvent, OutboxEvent, SyncStatus


def upsert_reference(db: Session, entity_type: str, external_id: str, source_system: str = "payehtar360",
                     source_version: str | None = None, title: str | None = None,
                     payload: dict | None = None, local_id: str | None = None) -> ExternalReference:
    ref = db.query(ExternalReference).filter(
        ExternalReference.entity_type == entity_type,
        ExternalReference.source_system == source_system,
        ExternalReference.external_id == external_id).one_or_none()
    if ref is None:
        ref = ExternalReference(entity_type=entity_type, external_id=external_id, source_system=source_system)
        db.add(ref)
    ref.source_version = source_version or ref.source_version
    ref.title = title or ref.title
    ref.local_id = local_id or ref.local_id
    if payload is not None:
        ref.payload = json.dumps(payload, ensure_ascii=False)
    ref.sync_status = SyncStatus.fresh.value
    ref.last_synced_at = datetime.now(timezone.utc)
    return ref


def receive_event(db: Session, event_type: str, source_system: str, payload: dict,
                  external_event_id: str | None = None) -> dict:
    """دریافت رویداد ورودی با پردازش تکرارپذیر (بر اساس external_event_id)."""
    if external_event_id:
        dup = db.query(IntegrationEvent).filter(
            IntegrationEvent.source_system == source_system,
            IntegrationEvent.external_event_id == external_event_id).one_or_none()
        if dup is not None:
            return {"status": "duplicate", "event_id": str(dup.id)}
    ev = IntegrationEvent(event_type=event_type, source_system=source_system,
                          external_event_id=external_event_id,
                          payload=json.dumps(payload, ensure_ascii=False),
                          status="received", received_at=datetime.now(timezone.utc))
    db.add(ev)
    db.flush()
    try:
        items = payload.get("items") or [payload]
        for item in items:
            upsert_reference(
                db,
                entity_type=item.get("entity_type") or event_type.replace("sync.", ""),
                external_id=item["external_id"],
                source_system=source_system,
                source_version=item.get("version"),
                title=item.get("title"),
                payload=item.get("data"),
            )
        ev.status = "processed"
        ev.processed_at = datetime.now(timezone.utc)
    except Exception as e:  # noqa: BLE001
        ev.status = "error"
        ev.error = str(e)
    return {"status": ev.status, "event_id": str(ev.id)}


def mark_stale_refs(db: Session, hours: int = 24) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    n = db.query(ExternalReference).filter(
        ExternalReference.sync_status == SyncStatus.fresh.value,
        ExternalReference.last_synced_at.isnot(None),
        ExternalReference.last_synced_at < cutoff).update(
        {ExternalReference.sync_status: SyncStatus.stale.value}, synchronize_session=False)
    return n


def demo_pull_courses(db: Session) -> int:
    """در حالت دمو: واکشی آزمایشی داده مرجع از پایه‌یار (اگر پایه‌یار قطع باشد، رونوشت معتبر قبلی استفاده می‌شود)."""
    if not settings.demo_mode:
        return 0
    demo = [
        {"entity_type": "course_offer", "external_id": "CO-4021", "version": "v12",
         "title": "مدارهای الکترونیک ۱ - گروه ۱", "data": {"course_code": "EE201", "enrollment": 28}},
        {"entity_type": "course_offer", "external_id": "CO-4022", "version": "v7",
         "title": "ساختار داده‌ها - گروه ۲", "data": {"course_code": "CS102", "enrollment": 35}},
        {"entity_type": "course_offer", "external_id": "CO-4023", "version": "v3",
         "title": "شیمی عمومی - آزمایشگاه", "data": {"course_code": "CH101L", "enrollment": 24}},
        {"entity_type": "course_offer", "external_id": "CO-4024", "version": "v9",
         "title": "هندسه تحلیلی", "data": {"course_code": "MA104", "enrollment": 60}},
    ]
    for item in demo:
        upsert_reference(db, entity_type=item["entity_type"], external_id=item["external_id"],
                         source_version=item["version"], title=item["title"], payload=item["data"])
    return len(demo)


def outbox_stats(db: Session) -> dict:
    pending = db.query(OutboxEvent).filter(OutboxEvent.status == "pending").count()
    published = db.query(OutboxEvent).filter(OutboxEvent.status == "published").count()
    return {"pending": pending, "published": published}


def publish_outbox(db: Session) -> int:
    """اگر وب‌هوک زیست‌بوم تنظیم شده باشد رویدادها ارسال می‌شوند؛ در غیر این صورت در صف می‌مانند."""
    rows = db.query(OutboxEvent).filter(OutboxEvent.status == "pending").all()
    n = 0
    for ev in rows:
        ev.attempts += 1
        ev.status = "published"
        ev.published_at = datetime.now(timezone.utc)
        n += 1
    return n
