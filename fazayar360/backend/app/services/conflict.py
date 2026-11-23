"""کنترل تعارض و ثبت تخصیص — مرجع واحد تقویم اشغال فضا."""
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ..config import settings
from ..core.errors import ConflictError, NotFoundError
from ..models import (AllocationKind, AllocationStatus, AvailabilityRule, BookingOccurrence,
                      BookingRequest, ResourceAllocation, Space, SpaceStatus)

try:
    tz = ZoneInfo(settings.timezone)
except Exception:
    tz = timezone.utc


def fa_weekday_to_py(w: int) -> int:
    """۰=شنبه … ۶=جمعه  →  weekday پایتون (دوشنبه=۰)."""
    return (5 + w) % 7


def effective_window(space: Space, start: datetime, end: datetime) -> tuple[datetime, datetime]:
    return (start - timedelta(minutes=space.min_prep_minutes or 0),
            end + timedelta(minutes=space.min_cleanup_minutes or 0))


def space_conflicts(db: Session, space_id: uuid.UUID, start: datetime, end: datetime,
                    exclude_allocation_id: uuid.UUID | None = None) -> list[ResourceAllocation]:
    q = db.query(ResourceAllocation).filter(
        ResourceAllocation.space_id == space_id,
        ResourceAllocation.status == AllocationStatus.active.value,
        ResourceAllocation.effective_start < end,
        ResourceAllocation.effective_end > start,
    )
    if exclude_allocation_id:
        q = q.filter(ResourceAllocation.id != exclude_allocation_id)
    return q.order_by(ResourceAllocation.effective_start).all()


def _describe_conflict(alloc: ResourceAllocation) -> str:
    if alloc.kind == AllocationKind.maintenance.value:
        return "انسداد تعمیراتی/آماده‌سازی"
    if alloc.kind == AllocationKind.hold.value:
        return "نگهداشت موقت برای درخواست در حال بررسی"
    return "رزرو تأییدشده دیگر"


def assert_space_free(db: Session, space: Space, start: datetime, end: datetime,
                      exclude_allocation_id: uuid.UUID | None = None) -> None:
    """تعارض‌ها: هم‌پوشانی زمانی، انسداد، وضعیت فضا، ساعات غیرمجاز، زمان آماده‌سازی/پاک‌سازی."""
    if space.status in (SpaceStatus.under_repair.value, SpaceStatus.inactive.value, SpaceStatus.retired.value):
        raise ConflictError("SPACE_UNAVAILABLE", f"فضای «{space.name}» خارج از سرویس است (وضعیت: {space.status})")

    conflicts = space_conflicts(db, space.id, start, end, exclude_allocation_id)
    if conflicts:
        details = []
        for a in conflicts[:5]:
            details.append({
                "allocation_id": str(a.id),
                "kind": a.kind,
                "reason": _describe_conflict(a),
                "window": [a.scheduled_start.isoformat(), a.scheduled_end.isoformat()],
            })
        raise ConflictError(
            "SPACE_DOUBLE_BOOKED",
            f"بازه انتخابی با اشغال فعلی فضای «{space.name}» هم‌پوشانی دارد؛ بازه مؤثر شامل زمان آماده‌سازی و پاک‌سازی است",
            details,
        )


def allowed_hours_violations(db: Session, space: Space, start: datetime, end: datetime) -> list[str]:
    """بررسی قواعد ساعات مجاز برای بازه (بازه‌های یک‌روزه فرض شده‌اند)."""
    rules = db.query(AvailabilityRule).filter(AvailabilityRule.space_id == space.id).all()
    if not rules:
        rules = db.query(AvailabilityRule).filter(AvailabilityRule.space_id.is_(None)).all()
    if not rules:
        return []  # بدون قاعده، پیش‌فرض سراسری از تنظیمات
    local_start = start.astimezone(tz)
    weekday = (local_start.weekday() - 5) % 7  # 0=شنبه
    day_rules = [r for r in rules if r.weekday == weekday]
    if not day_rules:
        return [f"برای روز {['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه'][weekday]} بازه مجازی تعریف نشده است"]
    t0, t1 = local_start.time(), (end.astimezone(tz)).time()
    ok = any(r.is_bookable and r.start_time <= t0 and t1 <= r.end_time for r in day_rules)
    if ok:
        return []
    windows = ", ".join(f"{r.start_time.strftime('%H:%M')} تا {r.end_time.strftime('%H:%M')}" for r in day_rules if r.is_bookable)
    return [f"ساعات مجاز این فضا در این روز: {windows}"]


def assert_hours_allowed(db: Session, space: Space, start: datetime, end: datetime) -> None:
    v = allowed_hours_violations(db, space, start, end)
    if v:
        raise ConflictError("OUTSIDE_ALLOWED_HOURS", v[0], v)


def create_allocation(db: Session, space: Space, user, start: datetime, end: datetime,
                      occurrence: BookingOccurrence | None = None, request: BookingRequest | None = None,
                      kind: str = AllocationKind.booking.value, note: str | None = None) -> ResourceAllocation:
    est, eee = effective_window(space, start, end)
    alloc = ResourceAllocation(
        space_id=space.id, occurrence_id=occurrence.id if occurrence else None,
        request_id=request.id if request else None,
        kind=kind, status=AllocationStatus.active.value,
        scheduled_start=start, scheduled_end=end, effective_start=est, effective_end=eee,
        created_by=user.id if user else None, note=note,
    )
    db.add(alloc)
    db.flush()
    return alloc


def release_allocations(db: Session, allocation_ids: list[uuid.UUID]) -> int:
    if not allocation_ids:
        return 0
    n = db.query(ResourceAllocation).filter(ResourceAllocation.id.in_(allocation_ids)).update(
        {ResourceAllocation.status: AllocationStatus.released.value}, synchronize_session=False)
    return n


def generate_occurrences(db: Session, request: BookingRequest, series, single: dict | None) -> list[BookingOccurrence]:
    """جلسات تکرارشونده به رخدادهای تاریخ‌دار تبدیل می‌شوند."""
    occurrences: list[BookingOccurrence] = []

    def add(start: datetime, end: datetime, series_id=None):
        if end <= start:
            raise ConflictError("BAD_INTERVAL", "زمان پایان جلسه باید پس از شروع آن باشد")
        occurrences.append(BookingOccurrence(request_id=request.id, series_id=series_id,
                                             start_at=start, end_at=end))

    if series:
        target_wd = fa_weekday_to_py(series.weekday)
        d = datetime.strptime(series.start_date, "%Y-%m-%d").date()
        d_end = datetime.strptime(series.end_date, "%Y-%m-%d").date()
        if d_end < d:
            raise ConflictError("BAD_INTERVAL", "تاریخ پایان الگو باید پس از شروع آن باشد")
        n = 0
        while d <= d_end:
            if d.weekday() == target_wd:
                st = datetime.combine(d, series.start_time, tzinfo=tz)
                en = datetime.combine(d, series.end_time, tzinfo=tz)
                add(st, en)
                n += 1
                if n > 200:
                    raise ConflictError("TOO_MANY_OCCURRENCES", "حداکثر ۲۰۰ جلسه در یک الگو مجاز است")
            d += timedelta(days=1)
        if n == 0:
            raise ConflictError("NO_OCCURRENCES", "در بازه انتخابی هیچ جلسه‌ای با این روز هفته وجود ندارد")
    if single:
        st = datetime.fromisoformat(single["start_at"])
        en = datetime.fromisoformat(single["end_at"])
        add(st, en)

    if not occurrences:
        raise ConflictError("NO_OCCURRENCES", "حداقل یک جلسه (تک‌جلسه‌ای یا الگوی تکرار) لازم است")
    for occ in occurrences:
        db.add(occ)
    db.flush()
    return occurrences


def block_allocation(db: Session, block, user) -> ResourceAllocation | None:
    """انسداد تعمیراتی هم در همان تقویم واحد ثبت می‌شود تا جست‌وجو و رزرو آن را ببینند."""
    if block.space_id is None:
        return None
    space = db.get(Space, block.space_id)
    if space is None:
        raise NotFoundError("فضای موردنظر یافت نشد")
    alloc = ResourceAllocation(
        space_id=space.id, block_id=block.id, kind=AllocationKind.maintenance.value,
        status=AllocationStatus.active.value,
        scheduled_start=block.start_at, scheduled_end=block.end_at,
        effective_start=block.start_at, effective_end=block.end_at,
        created_by=user.id if user else None,
        note=block.title,
    )
    db.add(alloc)
    db.flush()
    return alloc
