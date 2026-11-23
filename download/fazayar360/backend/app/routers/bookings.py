import json
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, in_scope, require_roles, require_space_scope
from ..core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..db import get_db
from ..models import (AllocationKind, ApprovalAction, BookingOccurrence, BookingRequest,
                      BlockReason, BlockStatus, MaintenanceBlock, OccurrenceStatus, RequestStatus,
                      ResourceAllocation, Space, SpaceStatus, UseType, User)
from ..services import booking as booking_svc
from ..services import conflict as cf
from ..services import search as search_svc
from ..services.search import serialize_match, serialize_near_miss

router = APIRouter(prefix="/booking-requests", tags=["bookings"])


def req_dict(db: Session, r: BookingRequest) -> dict:
    occs = sorted(r.occurrences, key=lambda o: o.start_at)
    allocations = []
    for o in occs:
        a = next((al for al in o.allocations if al.status == "active"), None)
        if a is not None:
            sp = db.get(Space, a.space_id)
            allocations.append({"occurrence_id": str(o.id), "allocation_id": str(a.id),
                                "space": {"id": str(sp.id), "name": sp.name, "code": sp.code} if sp else None,
                                "start": a.scheduled_start.isoformat(), "end": a.scheduled_end.isoformat()})
    space = None
    if r.requested_space_id:
        sp = db.get(Space, r.requested_space_id)
        if sp is not None:
            space = {"id": str(sp.id), "name": sp.name, "code": sp.code, "building_name": sp.building.name}
    return {
        "id": str(r.id), "request_number": r.request_number, "title": r.title,
        "description": r.description, "use_type": r.use_type, "status": r.status,
        "requester": {"id": str(r.requester_id)},
        "course_offer_ref": r.course_offer_ref,
        "expected_attendees": r.expected_attendees, "enrollment_count": r.enrollment_count,
        "required_feature_ids": json.loads(r.required_feature_ids or "[]"),
        "required_equipment_type_ids": json.loads(r.required_equipment_type_ids or "[]"),
        "layout": r.layout_requested,
        "accessibility_required": r.accessibility_required,
        "needs_lab_manager": r.needs_lab_manager,
        "requested_space": space,
        "portable_needs": json.loads(r.portable_needs or "[]"),
        "decision_note": r.decision_note, "cancel_reason": r.cancel_reason,
        "occurrences": [{"id": str(o.id), "start": o.start_at.isoformat(), "end": o.end_at.isoformat(),
                         "status": o.status, "note": o.exception_note} for o in occs],
        "allocations": allocations,
        "version": r.version,
        "created_at": r.created_at.isoformat(),
    }


class BookingIn(BaseModel):
    use_type: str
    title: str
    description: str | None = None
    course_offer_ref: str | None = None
    expected_attendees: int = 0
    requested_space_id: str | None = None
    layout: str | None = None
    required_feature_ids: list[str] = []
    required_equipment_type_ids: list[str] = []
    accessibility_required: bool = False
    needs_lab_manager: bool = False
    preferred_campus_id: str | None = None
    preferred_building_id: str | None = None
    portable_needs: list[dict] = []
    start_at: str | None = None   # تک‌جلسه‌ای
    end_at: str | None = None
    series: dict | None = None    # الگوی تکرار: {weekday,start_time,end_time,start_date,end_date}

    @field_validator("use_type")
    @classmethod
    def valid_use(cls, v):
        if v not in [t.value for t in UseType]:
            raise ValueError("نوع استفاده نامعتبر است")
        return v


def _check_request_scope(user: User, body: BookingIn, db: Session):
    if body.requested_space_id:
        s = db.get(Space, body.requested_space_id)
        if s is None:
            raise NotFoundError("فضای درخواستی یافت نشد")
        require_space_scope(user, s)


@router.post("", status_code=201)
def create_booking(body: BookingIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                   request: Request = None, idempotency_key: str | None = None):
    """Idempotency-Key برای عملیات حساس: تکرار همان کلید همان پاسخ را برمی‌گرداند."""
    from ..models import IdempotencyKey
    key = idempotency_key or request.headers.get("Idempotency-Key") if request else idempotency_key
    if key:
        existing = db.query(IdempotencyKey).filter(IdempotencyKey.key == key).one_or_none()
        if existing is not None:
            import json as _json
            raise ConflictError("IDEMPOTENT_REPLAY", "این عملیات قبلاً با همین کلید ثبت شده است",
                                [{"request": existing.response_body}])
    _check_request_scope(user, body, db)
    r = booking_svc.create_request(db, body.model_dump(), user, idempotency_key=key)
    if key:
        db.add(IdempotencyKey(key=key, endpoint="/api/v1/booking-requests",
                              response_body=r.request_number))
    db.flush()
    write_audit(db, user, "create", "booking_request", r.id, after={"number": r.request_number})
    return req_dict(db, r)


@router.get("")
def list_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                  status: str | None = None, mine: bool = False,
                  page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    q = db.query(BookingRequest)
    if status:
        q = q.filter(BookingRequest.status == status)
    if mine and user.role not in ("sys_admin", "university_admin", "education_expert",
                                  "education_manager", "service"):
        q = q.filter(BookingRequest.requester_id == user.id)
    total = q.count()
    rows = q.order_by(BookingRequest.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [req_dict(db, r) for r in rows], "total": total, "page": page, "size": size}


@router.get("/{request_id}")
def get_booking(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = booking_svc.get_request(db, request_id)
    if r.requester_id != user.id and user.role not in ("sys_admin", "university_admin", "education_expert",
                                                       "education_manager", "service", "facility_manager",
                                                       "lab_manager"):
        raise ForbiddenError("این درخواست متعلق به شما نیست")
    return req_dict(db, r)


class DecisionIn(BaseModel):
    comment: str | None = None
    force_capacity: bool = False


@router.post("/{request_id}/submit")
def submit(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = booking_svc.get_request(db, request_id)
    if r.requester_id != user.id and user.role not in ("sys_admin", "education_expert"):
        raise ForbiddenError("فقط درخواست‌دهنده می‌تواند ارسال کند")
    booking_svc.submit(db, r, user)
    db.commit()
    return req_dict(db, r)


@router.post("/{request_id}/review")
def start_review(request_id: str, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "education_expert"))):
    r = booking_svc.get_request(db, request_id)
    booking_svc.start_review(db, r, user)
    db.commit()
    return req_dict(db, r)


@router.post("/{request_id}/approve")
def approve(request_id: str, body: DecisionIn, db: Session = Depends(get_db),
            user: User = Depends(require_roles("sys_admin", "education_expert", "education_manager"))):
    r = booking_svc.get_request(db, request_id)
    if r.requested_space_id and not in_scope(user, building_id=None, campus_id=None):
        pass
    booking_svc.approve(db, r, user, body.comment, force_capacity=body.force_capacity)
    db.commit()   # تراکنش اتمیک: قید EXCLUDE در همین Commit دو رزرو متعارض را می‌بندد
    write_audit(db, user, "approve", "booking_request", r.id, after={"status": r.status})
    db.commit()
    return req_dict(db, r)


@router.post("/{request_id}/reject")
def reject(request_id: str, body: DecisionIn, db: Session = Depends(get_db),
           user: User = Depends(require_roles("sys_admin", "education_expert", "education_manager"))):
    r = booking_svc.get_request(db, request_id)
    booking_svc.reject(db, r, user, body.comment)
    write_audit(db, user, "reject", "booking_request", r.id, after={"status": r.status})
    db.commit()
    return req_dict(db, r)


class CancelIn(BaseModel):
    reason: str


@router.post("/{request_id}/cancel")
def cancel(request_id: str, body: CancelIn, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    r = booking_svc.get_request(db, request_id)
    if r.requester_id != user.id and user.role not in ("sys_admin", "education_expert", "education_manager"):
        raise ForbiddenError("اجازه لغو این درخواست را ندارید")
    booking_svc.cancel(db, r, user, body.reason)
    write_audit(db, user, "cancel", "booking_request", r.id, after={"reason": body.reason})
    db.commit()
    return req_dict(db, r)


class ConflictPreviewIn(BaseModel):
    """پیش‌نمایش تعارض قبل از ذخیره — بدون هیچ تخصیصی."""
    space_id: str
    start_at: str
    end_at: str
    exclude_allocation_id: str | None = None


@router.post("/conflict-preview")
def conflict_preview(body: ConflictPreviewIn, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    s = db.get(Space, body.space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    st = datetime.fromisoformat(body.start_at)
    en = datetime.fromisoformat(body.end_at)
    conflicts = [{"kind": c.kind, "start": c.scheduled_start.isoformat(), "end": c.scheduled_end.isoformat()}
                 for c in cf.space_conflicts(db, s.id, st, en, body.exclude_allocation_id)]
    violations = cf.allowed_hours_violations(db, s, st, en)
    return {"conflicts": conflicts, "hour_violations": violations, "ok": not conflicts and not violations}


class MoveIn(BaseModel):
    space_id: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    note: str | None = None


@router.post("/occurrences/{occurrence_id}/move")
def move_occurrence(occurrence_id: str, body: MoveIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("sys_admin", "education_expert", "education_manager"))):
    occ = db.get(BookingOccurrence, occurrence_id)
    if occ is None:
        raise NotFoundError("جلسه یافت نشد")
    booking_svc.move_occurrence(db, occ, user,
                                uuid.UUID(body.space_id) if body.space_id else None,
                                body.start_at, body.end_at, body.note)
    write_audit(db, user, "move", "occurrence", occ.id, after={"note": body.note})
    db.commit()
    return req_dict(db, occ.request)


class MarkIn(BaseModel):
    status: str  # executed | no_show
    note: str | None = None


@router.post("/occurrences/{occurrence_id}/mark")
def mark_occurrence(occurrence_id: str, body: MarkIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("sys_admin", "education_expert", "education_manager"))):
    occ = db.get(BookingOccurrence, occurrence_id)
    if occ is None:
        raise NotFoundError("جلسه یافت نشد")
    booking_svc.mark_executed(db, occ, user, body.status, body.note)
    db.commit()
    return req_dict(db, occ.request)


@router.get("/{request_id}/history")
def history(request_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    r = booking_svc.get_request(db, request_id)
    actions = db.query(ApprovalAction).filter(ApprovalAction.request_id == r.id).order_by(ApprovalAction.created_at).all()
    return [{"action": a.action, "actor_id": str(a.actor_id), "comment": a.comment,
             "at": a.created_at.isoformat()} for a in actions]


# ── انسداد تعمیراتی + پیشنهاد جایگزین ────────────────────────────────
blocks_router = APIRouter(prefix="/maintenance-blocks", tags=["blocks"])


class BlockIn(BaseModel):
    space_id: str | None = None
    asset_id: str | None = None
    reason_code: str = "repair"
    title: str
    description: str | None = None
    start_at: str
    end_at: str

    @field_validator("reason_code")
    @classmethod
    def valid_reason(cls, v):
        if v not in [t.value for t in BlockReason]:
            raise ValueError("دلیل انسداد نامعتبر است")
        return v


@blocks_router.post("", status_code=201)
def create_block(body: BlockIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "facility_manager", "lab_manager"))):
    if not body.space_id and not body.asset_id:
        raise ValidationError("انسداد باید برای فضا یا تجهیز ثبت شود")
    st = datetime.fromisoformat(body.start_at)
    en = datetime.fromisoformat(body.end_at)
    if en <= st:
        raise ValidationError("بازه انسداد نامعتبر است")
    if body.space_id:
        s = db.get(Space, body.space_id)
        if s is None:
            raise NotFoundError("فضا یافت نشد")
        require_space_scope(user, s)
    blk = MaintenanceBlock(space_id=body.space_id, asset_id=body.asset_id,
                           reason_code=body.reason_code, title=body.title, description=body.description,
                           reporter_id=user.id, status=BlockStatus.active.value, start_at=st, end_at=en)
    db.add(blk)
    db.flush()
    alloc = cf.block_allocation(db, blk, user)
    affected = []
    if body.space_id:
        rows = db.query(ResourceAllocation).filter(
            ResourceAllocation.space_id == body.space_id,
            ResourceAllocation.status == "active", ResourceAllocation.kind == "booking",
            ResourceAllocation.scheduled_start < en, ResourceAllocation.scheduled_end > st).all()
        for a in rows:
            if a.request_id:
                req = db.get(BookingRequest, a.request_id)
                affected.append({"request_id": str(req.id), "request_number": req.request_number,
                                 "title": req.title, "start": a.scheduled_start.isoformat(),
                                 "end": a.scheduled_end.isoformat(), "attendees": req.expected_attendees})
    booking_svc.push_outbox(db, "space.blocked", {"space_id": body.space_id, "block_id": str(blk.id)})
    write_audit(db, user, "create", "maintenance_block", blk.id, after={"title": blk.title})
    db.commit()
    return {"id": str(blk.id), "affected_sessions": affected}


@blocks_router.get("")
def list_blocks(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                status: str | None = None):
    q = db.query(MaintenanceBlock)
    if status:
        q = q.filter(MaintenanceBlock.status == status)
    rows = q.order_by(MaintenanceBlock.created_at.desc()).limit(100).all()
    out = []
    for b in rows:
        sp = db.get(Space, b.space_id) if b.space_id else None
        out.append({"id": str(b.id), "title": b.title, "description": b.description,
                    "reason_code": b.reason_code, "status": b.status,
                    "space": {"id": str(sp.id), "name": sp.name, "code": sp.code} if sp else None,
                    "start": b.start_at.isoformat(), "end": b.end_at.isoformat(),
                    "reporter_name": b.reporter_name})
    return out


@blocks_router.post("/{block_id}/resolve")
def resolve_block(block_id: str, body: dict = None, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("sys_admin", "facility_manager", "lab_manager"))):
    blk = db.get(MaintenanceBlock, block_id)
    if blk is None:
        raise NotFoundError("انسداد یافت نشد")
    blk.status = BlockStatus.resolved.value
    blk.resolved_at = datetime.utcnow()
    blk.resolver_note = (body or {}).get("note")
    n = db.query(ResourceAllocation).filter(
        ResourceAllocation.block_id == blk.id, ResourceAllocation.status == "active").update(
        {ResourceAllocation.status: "released"}, synchronize_session=False)
    s = db.get(Space, blk.space_id) if blk.space_id else None
    if s is not None and s.status == SpaceStatus.under_repair.value:
        s.status = SpaceStatus.active.value
    write_audit(db, user, "resolve", "maintenance_block", blk.id)
    db.commit()
    return {"id": str(blk.id), "released_allocations": n}


@blocks_router.post("/{block_id}/report-approve")
def approve_report(block_id: str, body: dict = None, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("sys_admin", "facility_manager", "lab_manager"))):
    """تبدیل گزارش خرابی (از QR یا دانشجو) به انسداد فعال."""
    blk = db.get(MaintenanceBlock, block_id)
    if blk is None:
        raise NotFoundError("گزارش یافت نشد")
    st = body.get("start_at") if body else None
    en = body.get("end_at") if body else None
    blk.start_at = datetime.fromisoformat(st) if st else blk.start_at
    blk.end_at = datetime.fromisoformat(en) if en else blk.end_at
    blk.status = BlockStatus.active.value
    cf.block_allocation(db, blk, user)
    s = db.get(Space, blk.space_id) if blk.space_id else None
    if s is not None:
        s.status = SpaceStatus.under_repair.value
        s.version += 1
    write_audit(db, user, "activate_block", "maintenance_block", blk.id)
    db.commit()
    return {"id": str(blk.id)}


@blocks_router.post("/{block_id}/report-reject")
def reject_report(block_id: str, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("sys_admin", "facility_manager", "lab_manager"))):
    blk = db.get(MaintenanceBlock, block_id)
    if blk is None:
        raise NotFoundError("گزارش یافت نشد")
    blk.status = BlockStatus.rejected.value
    write_audit(db, user, "reject_report", "maintenance_block", blk.id)
    db.commit()
    return {"id": str(blk.id)}


class SuggestIn(BaseModel):
    request_id: str
    start_at: str | None = None
    end_at: str | None = None


@blocks_router.post("/suggest-alternatives")
def suggest_alternatives(body: SuggestIn, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """پیشنهاد فضاهای جایگزین واجد شرایط برای جلسات متاثر از خرابی."""
    r = booking_svc.get_request(db, body.request_id)
    attendees = r.expected_attendees
    filters = {
        "attendees": attendees,
        "feature_ids": json.loads(r.required_feature_ids or "[]"),
        "equipment_type_ids": json.loads(r.required_equipment_type_ids or "[]"),
        "layout": r.layout_requested,
        "accessibility_required": r.accessibility_required,
        "needs_lab_manager": r.needs_lab_manager,
    }
    occs = [o for o in r.occurrences if o.status == OccurrenceStatus.scheduled.value]
    results = []
    for occ in occs[:5]:
        f = dict(filters)
        f["start_at"] = body.start_at or occ.start_at.isoformat()
        f["end_at"] = body.end_at or occ.end_at.isoformat()
        if r.requested_space_id:
            f["exclude_space_id"] = str(r.requested_space_id)
        full = search_svc.search_with_near_misses(db, f)
        results.append({
            "occurrence_id": str(occ.id),
            "start": occ.start_at.isoformat(), "end": occ.end_at.isoformat(),
            "options": [serialize_match(db, m) for m in full["matches"][:5]],
            "near_misses": [serialize_near_miss(n) for n in full["near_misses"][:8]],
        })
    return {"request_number": r.request_number, "occurrences": results}
