import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..core.errors import NotFoundError
from ..db import get_db
from ..models import Building, Feature, Space, User
from ..services import assistant as assistant_svc
from ..services import search as search_svc
from ..services.search import serialize_match, serialize_near_miss

router = APIRouter(tags=["search"])


class SearchIn(BaseModel):
    start_at: str | None = None
    end_at: str | None = None
    attendees: int = 0
    campus_id: str | None = None
    building_id: str | None = None
    target_building_id: str | None = None
    space_types: list[str] = []
    feature_ids: list[str] = []
    equipment_type_ids: list[str] = []
    layout: str | None = None
    accessibility_required: bool = False
    needs_lab_manager: bool = False
    exclude_space_id: str | None = None
    limit: int = 12


@router.post("/availability/search")
def search(body: SearchIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    full = search_svc.search_with_near_misses(db, body.model_dump(exclude={"limit"}))
    return {
        "matches": [serialize_match(db, m) for m in full["matches"][:body.limit]],
        "near_misses": [serialize_near_miss(n) for n in full["near_misses"][:8]],
        "count": len(full["matches"]),
    }


class AssistantIn(BaseModel):
    text: str


@router.post("/assistant/parse")
def assistant_parse(body: AssistantIn, user: User = Depends(get_current_user)):
    """دستیار: متن فارسی → فیلتر. LLM مرجع آزادبودن فضا نیست؛ فقط فیلتر می‌سازد."""
    parsed = assistant_svc.parse_request(body.text)
    return parsed


@router.post("/assistant/search")
def assistant_search(body: AssistantIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    parsed = assistant_svc.parse_request(body.text)
    # نگاشت کدهای ویژگی به شناسه‌ها
    feature_ids = []
    if parsed.get("feature_codes"):
        feats = db.query(Feature).filter(Feature.code.in_(parsed["feature_codes"])).all()
        feature_ids = [str(f.id) for f in feats]
    building_id = None
    target_building_id = None
    if parsed.get("building_query"):
        b = db.query(Building).filter(Building.name.ilike(f"%{parsed['building_query'][:20]}%")).first()
        if b is not None:
            building_id = str(b.id)
            target_building_id = str(b.id)
    start_at = end_at = None
    if parsed.get("target_date") and parsed.get("start_time"):
        base = datetime.fromisoformat(f"{parsed['target_date']}T{parsed['start_time']}:00")
        start_at = base.isoformat()
        if parsed.get("duration_min"):
            end_at = (base + timedelta(minutes=parsed["duration_min"])).isoformat()
    filters = {
        "start_at": start_at, "end_at": end_at,
        "attendees": parsed.get("attendees") or 0,
        "feature_ids": feature_ids,
        "space_types": parsed.get("space_types") or [],
        "building_id": building_id,
        "target_building_id": target_building_id,
        "accessibility_required": bool(parsed.get("accessibility_required")),
    }
    full = search_svc.search_with_near_misses(db, filters)
    return {
        "parsed": parsed,
        "filters": {k: v for k, v in filters.items() if v},
        "matches": [serialize_match(db, m) for m in full["matches"][:8]],
        "near_misses": [serialize_near_miss(n) for n in full["near_misses"][:6]],
    }


@router.get("/calendar/global")
def global_calendar(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                    date_from: str = Query(...), date_to: str = Query(...),
                    building_id: str | None = None):
    """تقویم عملیاتی: همه رخدادها و انسدادها برای صفحه تقویم."""
    from ..models import BookingRequest, ResourceAllocation
    st = datetime.fromisoformat(date_from)
    en = datetime.fromisoformat(date_to) + timedelta(days=1)
    rows = db.query(ResourceAllocation).filter(
        ResourceAllocation.status == "active",
        ResourceAllocation.scheduled_start < en,
        ResourceAllocation.scheduled_end > st).all()
    spaces = {str(s.id): s for s in db.query(Space).all()}
    reqs = {str(r.id): r for r in db.query(BookingRequest).all()}
    events = []
    for a in rows:
        s = spaces.get(str(a.space_id))
        if s is None:
            continue
        if building_id and str(s.building_id) != building_id:
            continue
        req = reqs.get(str(a.request_id)) if a.request_id else None
        events.append({
            "allocation_id": str(a.id),
            "space": {"id": str(s.id), "name": s.name, "code": s.code,
                      "building_id": str(s.building_id)},
            "kind": a.kind,
            "start": a.scheduled_start.isoformat(), "end": a.scheduled_end.isoformat(),
            "title": req.title if req else (a.note or "انسداد"),
            "request_number": req.request_number if req else None,
            "use_type": req.use_type if req else None,
        })
    return {"events": events}
