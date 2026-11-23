"""گردش‌کار درخواست: پیش‌نویس → ارسال → بررسی → تأیید/رد → اجرا/لغو، با اعتبارسنجی قطعی در لحظه تأیید."""
import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ConflictError, NotFoundError
from ..core.security import hash_password  # noqa: F401 (نگه‌داشت واردات برای سازگاری)
from ..models import (ApprovalAction, BookingOccurrence, BookingRequest, BookingSeries,
                      EquipmentAllocation, EquipmentPool, EquipmentType, OutboxEvent,
                      RequestStatus, OccurrenceStatus, Space, UseType)
from . import conflict as cf
from .capacity import parse_json_ids, space_effective_capacity


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _add_action(db: Session, request_id: uuid.UUID, actor, action: str, comment: str | None = None):
    db.add(ApprovalAction(request_id=request_id, actor_id=actor.id if actor else None,
                          action=action, comment=comment, created_at=_now()))


def push_outbox(db: Session, topic: str, payload: dict):
    db.add(OutboxEvent(topic=topic, payload=json.dumps(payload, ensure_ascii=False, default=str),
                       status="pending", attempts=0, created_at=_now()))


def create_request(db: Session, payload: dict, user, idempotency_key: str | None = None) -> BookingRequest:
    try:
        use_type = payload["use_type"]
        UseType(use_type)
    except ValueError:
        raise ConflictError("BAD_USE_TYPE", "نوع استفاده نامعتبر است")

    req = BookingRequest(
        request_number=f"REQ-{_now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}",
        requester_id=user.id,
        use_type=use_type,
        title=payload.get("title") or "بدون عنوان",
        description=payload.get("description"),
        status=RequestStatus.draft.value,
        course_offer_ref=payload.get("course_offer_ref"),
        expected_attendees=int(payload.get("expected_attendees") or 0),
        enrollment_count=payload.get("enrollment_count"),
        required_feature_ids=json.dumps(payload.get("required_feature_ids") or []),
        required_equipment_type_ids=json.dumps(payload.get("required_equipment_type_ids") or []),
        layout_requested=payload.get("layout"),
        accessibility_required=bool(payload.get("accessibility_required")),
        needs_lab_manager=bool(payload.get("needs_lab_manager")),
        preferred_campus_id=payload.get("preferred_campus_id"),
        preferred_building_id=payload.get("preferred_building_id"),
        requested_space_id=payload.get("requested_space_id"),
        portable_needs=json.dumps(payload.get("portable_needs") or []),
        idempotency_key=idempotency_key,
    )
    db.add(req)
    db.flush()

    series = None
    single = None
    if payload.get("series"):
        s = payload["series"]
        from datetime import time as _time
        series = BookingSeries(
            request_id=req.id, weekday=int(s["weekday"]),
            start_time=_time.fromisoformat(s["start_time"]), end_time=_time.fromisoformat(s["end_time"]),
            start_date=s["start_date"], end_date=s["end_date"], pattern="weekly",
        )
        db.add(series)
        db.flush()
    elif payload.get("start_at"):
        single = {"start_at": payload["start_at"], "end_at": payload["end_at"]}

    cf.generate_occurrences(db, req, series, single)
    db.flush()
    return req


def get_request(db: Session, request_id: uuid.UUID) -> BookingRequest:
    req = db.get(BookingRequest, request_id)
    if req is None:
        raise NotFoundError("درخواست یافت نشد")
    return req


def submit(db: Session, req: BookingRequest, user, comment: str | None = None):
    if req.status != RequestStatus.draft.value:
        raise ConflictError("BAD_TRANSITION", "فقط پیش‌نویس قابل ارسال است")
    req.status = RequestStatus.submitted.value
    _add_action(db, req.id, user, "submit", comment)


def start_review(db: Session, req: BookingRequest, user, comment: str | None = None):
    if req.status != RequestStatus.submitted.value:
        raise ConflictError("BAD_TRANSITION", "فقط درخواست ارسال‌شده قابل بررسی است")
    req.status = RequestStatus.under_review.value
    _add_action(db, req.id, user, "review", comment)


def _allocate_portable(db: Session, req: BookingRequest, alloc, start, end):
    """کنترل تراکنشی موجودی تجهیزات شمارشی: قفل ردیف استخر، بررسی هم‌پوشانی، ثبت تخصیص."""
    needs = []
    try:
        needs = json.loads(req.portable_needs or "[]")
    except Exception:
        pass
    for need in needs:
        pool = db.get(EquipmentPool, uuid.UUID(need["pool_id"]))
        if pool is None:
            raise NotFoundError("استخر تجهیز یافت نشد")
        # قفل تخصیصی ردیف برای جلوگیری از مصرف بیش از موجودی در تراکنش هم‌زمان
        pool_row = db.execute(select(EquipmentPool).where(EquipmentPool.id == pool.id).with_for_update()).scalar_one()
        used = 0
        rows = db.query(EquipmentAllocation).filter(
            EquipmentAllocation.pool_id == pool_row.id,
            EquipmentAllocation.status == "active",
        ).all()
        for row in rows:
            parent = db.get(ResourceAllocation, row.allocation_id)
            if parent is None or parent.status != "active":
                continue
            if parent.effective_start < end and parent.effective_end > start:
                used += row.quantity
        qty = int(need.get("quantity") or 1)
        if used + qty > pool_row.total_quantity:
            raise ConflictError("EQUIPMENT_POOL_EXHAUSTED",
                                f"موجودی «{pool_row.name}» کافی نیست ({used} از {pool_row.total_quantity} در این بازه مصرف شده است)")
        db.add(EquipmentAllocation(allocation_id=alloc.id, pool_id=pool_row.id, quantity=qty))


def approve(db: Session, req: BookingRequest, user, comment: str | None = None,
            force_capacity: bool = False):
    """تأیید = ثبت تخصیص قطعی با اعتبارسنجی مجدد هر رخداد (پیشنهاد قدیمی مستقیم اعمال نمی‌شود)."""
    if req.status not in (RequestStatus.submitted.value, RequestStatus.under_review.value):
        raise ConflictError("BAD_TRANSITION", "این درخواست در وضعیت قابل تأیید نیست")

    if req.requested_space_id is None:
        raise ConflictError("NO_SPACE", "برای تأیید باید فضای مقصد انتخاب شده باشد")
    space = db.get(Space, req.requested_space_id)
    if space is None:
        raise NotFoundError("فضای درخواستی یافت نشد")

    # قفل تراکنشی ردیف فضا: دو تأیید هم‌زمان روی یک فضا سری می‌شوند تا هر دو، تعارض را ببینند
    db.execute(select(Space).where(Space.id == space.id).with_for_update())

    req_features = parse_json_ids(req.required_feature_ids)
    req_equipment = parse_json_ids(req.required_equipment_type_ids)

    cap = space_effective_capacity(db, space, req.layout_requested, req_equipment)
    if cap["missing_equipment"]:
        raise ConflictError("MISSING_EQUIPMENT",
                            "تجهیزات الزامی در این فضا موجود یا سالم نیستند",
                            [{"equipment_type_id": t} for t in cap["missing_equipment"]])
    if (not force_capacity) and req.expected_attendees:
        if cap["capacity"] is None or cap["capacity"] < req.expected_attendees:
            raise ConflictError("INSUFFICIENT_CAPACITY",
                                f"ظرفیت مؤثر ({cap['capacity']}) برای {req.expected_attendees} نفر کافی نیست",
                                cap["limits"])

    allocations = []
    for occ in req.occurrences:
        if occ.status != OccurrenceStatus.scheduled.value:
            continue
        # ۱) تعارض زمانی/انسداد — بازه مؤثر شامل آماده‌سازی و پاک‌سازی
        cf.assert_space_free(db, space, occ.start_at, occ.end_at)
        # ۲) ساعات مجاز
        cf.assert_hours_allowed(db, space, occ.start_at, occ.end_at)
        # ۳) ثبت تخصیص قطعی (قید EXCLUDE دیتابیس آخرین خط دفاع است)
        alloc = cf.create_allocation(db, space, user, occ.start_at, occ.end_at,
                                     occurrence=occ, request=req, kind="booking")
        # ۴) تجهیزات قابل‌حمل
        _allocate_portable(db, req, alloc, occ.start_at, occ.end_at)
        allocations.append(alloc)

    req.status = RequestStatus.approved.value
    req.decision_note = comment
    req.decided_by = user.id
    req.decided_at = _now()
    _add_action(db, req.id, user, "approve", comment)
    push_outbox(db, "booking.confirmed", {
        "request_number": req.request_number, "space_code": space.code,
        "occurrences": [o.id.__str__() for o in req.occurrences],
    })
    return allocations


def reject(db: Session, req: BookingRequest, user, comment: str | None = None):
    if req.status not in (RequestStatus.submitted.value, RequestStatus.under_review.value):
        raise ConflictError("BAD_TRANSITION", "این درخواست در وضعیت قابل رد نیست")
    req.status = RequestStatus.rejected.value
    req.decision_note = comment
    req.decided_by = user.id
    req.decided_at = _now()
    for occ in req.occurrences:
        if occ.status == OccurrenceStatus.scheduled.value:
            occ.status = OccurrenceStatus.cancelled.value
            occ.exception_note = "درخواست رد شد"
    _add_action(db, req.id, user, "reject", comment)


def cancel(db: Session, req: BookingRequest, user, reason: str):
    if req.status in (RequestStatus.cancelled.value, RequestStatus.rejected.value):
        raise ConflictError("BAD_TRANSITION", "این درخواست قبلاً بسته شده است")
    req.status = RequestStatus.cancelled.value
    req.cancel_reason = reason
    alloc_ids = [a.id for a in req.allocations if a.status == "active"]
    cf.release_allocations(db, alloc_ids)
    # آزادسازی تجهیزات قابل‌حمل
    if alloc_ids:
        db.query(EquipmentAllocation).filter(EquipmentAllocation.allocation_id.in_(alloc_ids)).update(
            {EquipmentAllocation.status: "released"}, synchronize_session=False)
    for occ in req.occurrences:
        if occ.status == OccurrenceStatus.scheduled.value:
            occ.status = OccurrenceStatus.cancelled.value
            occ.exception_note = f"لغو با دلیل: {reason}"
    _add_action(db, req.id, user, "cancel", reason)


def move_occurrence(db: Session, occ: BookingOccurrence, user, new_space_id: uuid.UUID | None = None,
                    new_start: str | None = None, new_end: str | None = None, note: str | None = None):
    """جابه‌جایی یک جلسه با بررسی مجدد تعارض — پیش‌نمایش تعارض جداگانه در API موجود است."""
    if occ.status != OccurrenceStatus.scheduled.value:
        raise ConflictError("BAD_TRANSITION", "فقط جلسه برنامه‌ریزی‌شده قابل جابه‌جایی است")
    req = occ.request
    old_alloc = next((a for a in occ.allocations if a.status == "active"), None)
    space = db.get(Space, new_space_id) if new_space_id else (
        db.get(Space, old_alloc.space_id) if old_alloc else None)
    if space is None:
        raise NotFoundError("فضای مقصد یافت نشد")
    start = datetime.fromisoformat(new_start) if new_start else occ.start_at
    end = datetime.fromisoformat(new_end) if new_end else occ.end_at

    cf.assert_space_free(db, space, start, end,
                         exclude_allocation_id=old_alloc.id if old_alloc else None)
    cf.assert_hours_allowed(db, space, start, end)

    cap = space_effective_capacity(db, space, req.layout_requested, parse_json_ids(req.required_equipment_type_ids))
    if req.expected_attendees and cap["capacity"] is not None and cap["capacity"] < req.expected_attendees:
        raise ConflictError("INSUFFICIENT_CAPACITY",
                            f"ظرفیت مؤثر مقصد ({cap['capacity']}) برای {req.expected_attendees} نفر کافی نیست")

    if old_alloc:
        cf.release_allocations(db, [old_alloc.id])
        db.query(EquipmentAllocation).filter(EquipmentAllocation.allocation_id == old_alloc.id).update(
            {EquipmentAllocation.status: "released"}, synchronize_session=False)
    cf.create_allocation(db, space, user, start, end, occurrence=occ, request=req, kind="booking",
                         note=f"جابه‌جایی: {note or ''}")
    if start != occ.start_at or end != occ.end_at:
        occ.status = OccurrenceStatus.moved.value
        occ.exception_note = note or "جابه‌جایی جلسه"
    _add_action(db, req.id, user, "move", note)
    push_outbox(db, "booking.moved", {"request_number": req.request_number, "occurrence_id": str(occ.id)})


def mark_executed(db: Session, occ: BookingOccurrence, user, status: str, note: str | None = None):
    if status not in (OccurrenceStatus.executed.value, OccurrenceStatus.no_show.value):
        raise ConflictError("BAD_TRANSITION", "وضعیت نامعتبر")
    occ.status = status
    occ.exception_note = note
    _add_action(db, occ.request_id, user, "mark_" + status, note)
