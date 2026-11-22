"""تحلیل ظرفیت و بهره‌برداری — تفکیک استفاده برنامه‌ریزی‌شده از استفاده واقعی؛ شفاف درباره کیفیت داده."""
import json
import statistics
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (AvailabilityRule, BookingOccurrence, BookingRequest, ExternalReference,
                      MaintenanceBlock, OccurrenceStatus, ResourceAllocation, Space, SpaceLayout,
                      SpaceStatus, UsageObservation, RequestStatus)

try:
    tz = ZoneInfo(settings.timezone)
except Exception:
    tz = timezone.utc


def _bookable_hours_per_weekday(db: Session, space_id) -> dict[int, float]:
    rules = db.query(AvailabilityRule).filter(AvailabilityRule.space_id == space_id).all()
    if not rules:
        rules = db.query(AvailabilityRule).filter(AvailabilityRule.space_id.is_(None)).all()
    out: dict[int, float] = {}
    for r in rules:
        if not r.is_bookable:
            continue
        hours = (datetime.combine(datetime(2000, 1, 3), r.end_time) -
                 datetime.combine(datetime(2000, 1, 3), r.start_time)).total_seconds() / 3600
        out[r.weekday] = out.get(r.weekday, 0) + hours
    return out


def _default_bookable() -> dict[int, float]:
    """پیش‌فرض: شنبه تا چهارشنبه ۷–۲۱، پنجشنبه ۸–۱۴، جمعه تعطیل."""
    return {0: 14, 1: 14, 2: 14, 3: 14, 4: 14, 5: 6}


def utilization(db: Session, date_from: str, date_to: str, group_by: str = "building") -> dict:
    start = datetime.fromisoformat(date_from).replace(tzinfo=tz)
    end = (datetime.fromisoformat(date_to) + timedelta(days=1)).replace(tzinfo=tz)

    spaces = db.query(Space).filter(Space.status != SpaceStatus.retired.value).all()
    allocs = db.query(ResourceAllocation).filter(
        ResourceAllocation.status == "active",
        ResourceAllocation.kind == "booking",
        ResourceAllocation.scheduled_start < end,
        ResourceAllocation.scheduled_end >= start,
    ).all()
    blocks = db.query(ResourceAllocation).filter(
        ResourceAllocation.status == "active",
        ResourceAllocation.kind == "maintenance",
        ResourceAllocation.scheduled_start < end,
        ResourceAllocation.scheduled_end >= start,
    ).all()
    observations = db.query(UsageObservation).filter(
        UsageObservation.observed_at >= start, UsageObservation.observed_at < end).all()

    obs_by_occ: dict[str, list[UsageObservation]] = {}
    for o in observations:
        if o.occurrence_id:
            obs_by_occ.setdefault(str(o.occurrence_id), []).append(o)

    # ثبت‌نام‌ها برای برآورد مبتنی بر ثبت‌نام
    reqs = {str(r.id): r for r in db.query(BookingRequest).all()}

    def days_in_range(weekday_py: int) -> int:
        n, d = 0, start.date()
        while d < end.date():
            if d.weekday() == weekday_py:
                n += 1
            d += timedelta(days=1)
        return n

    rows: dict[str, dict] = {}
    for sp in spaces:
        key = str(sp.building_id) if group_by == "building" else (
            str(sp.campus_id) if group_by == "campus" else sp.space_type)
        row = rows.setdefault(key, {
            "space_count": 0, "bookable_hours": 0.0, "scheduled_hours": 0.0,
            "actual_hours": 0.0, "actual_observed_hours": 0.0, "person_hours_planned": 0.0,
            "person_hours_actual": 0.0, "seat_hours": 0.0, "downtime_hours": 0.0,
            "cancellations": 0, "completions": 0, "no_shows": 0, "capacity_mismatches": 0,
        })
        row["space_count"] += 1

        bookable = _bookable_hours_per_weekday(db, sp.id)
        if not bookable:
            bookable = _default_bookable()
        weekly = 0.0
        for wd_fa, hours in bookable.items():
            weekly += hours * days_in_range((wd_fa + 5) % 7)
        row["bookable_hours"] += weekly

    for a in allocs:
        key = str(a.space_id) if group_by == "space" else None
        if key is None:
            sp = next((s for s in spaces if s.id == a.space_id), None)
            if sp is None:
                continue
            key = str(sp.building_id) if group_by == "building" else (
                str(sp.campus_id) if group_by == "campus" else sp.space_type)
        hours = (min(a.scheduled_end, end) - max(a.scheduled_start, start)).total_seconds() / 3600
        if hours <= 0:
            continue
        rows[key]["scheduled_hours"] += hours
        req = reqs.get(str(a.request_id)) if a.request_id else None
        cap_eff = 0
        if sp is not None and sp.layouts:
            cap_eff = max((l.capacity for l in sp.layouts), default=0)
        rows[key]["seat_hours"] += cap_eff * hours
        if req is not None:
            rows[key]["person_hours_planned"] += (req.enrollment_count or req.expected_attendees or 0) * hours
        if a.occurrence_id:
            occ_obs = obs_by_occ.get(str(a.occurrence_id))
            if occ_obs:
                avg = sum(o.observed_headcount for o in occ_obs) / len(occ_obs)
                rows[key]["actual_observed_hours"] += hours
                rows[key]["person_hours_actual"] += avg * hours
            elif req is not None:
                rows[key]["actual_hours"] += hours
                rows[key]["person_hours_actual"] += (req.enrollment_count or req.expected_attendees or 0) * hours

    for a in blocks:
        sp = next((s for s in spaces if s.id == a.space_id), None)
        if sp is None:
            continue
        key = str(sp.building_id) if group_by == "building" else (
            str(sp.campus_id) if group_by == "campus" else sp.space_type)
        hours = (min(a.scheduled_end, end) - max(a.scheduled_start, start)).total_seconds() / 3600
        if hours > 0 and key in rows:
            rows[key]["downtime_hours"] += hours

    occ_rows = db.query(BookingOccurrence).filter(
        BookingOccurrence.start_at < end, BookingOccurrence.start_at >= start).all()
    for occ in occ_rows:
        req = reqs.get(str(occ.request_id))
        if req is None:
            continue
        sp = None
        if req.requested_space_id:
            sp = next((s for s in spaces if s.id == req.requested_space_id), None)
        key = None
        if sp is not None:
            key = str(sp.building_id) if group_by == "building" else (
                str(sp.campus_id) if group_by == "campus" else sp.space_type)
        if key not in rows:
            continue
        if occ.status == OccurrenceStatus.cancelled.value and req.status == RequestStatus.cancelled.value:
            rows[key]["cancellations"] += 1
        elif occ.status == OccurrenceStatus.executed.value:
            rows[key]["completions"] += 1
        elif occ.status == OccurrenceStatus.no_show.value:
            rows[key]["no_shows"] += 1

    out = []
    for key, r in rows.items():
        util_planned = round(r["scheduled_hours"] / r["bookable_hours"] * 100, 1) if r["bookable_hours"] else 0
        has_observations = r["actual_observed_hours"] > 0
        actual_base = r["actual_observed_hours"] if has_observations else r["actual_hours"]
        util_actual = round(actual_base / r["bookable_hours"] * 100, 1) if r["bookable_hours"] else 0
        closed = r["completions"] + r["no_shows"] + r["cancellations"]
        out.append({
            "key": key,
            "space_count": r["space_count"],
            "bookable_hours": round(r["bookable_hours"], 1),
            "scheduled_hours": round(r["scheduled_hours"], 1),
            "planned_utilization_pct": util_planned,
            "actual_utilization_pct": util_actual,
            "actual_data_basis": "مشاهده واقعی" if has_observations else "برآورد مبتنی بر ثبت‌نام",
            "seat_utilization_pct": round(r["person_hours_actual"] / r["seat_hours"] * 100, 1) if r["seat_hours"] else 0,
            "cancellation_rate_pct": round(r["cancellations"] / closed * 100, 1) if closed else 0,
            "no_show_rate_pct": round(r["no_shows"] / max(closed - r["cancellations"], 1) * 100, 1),
            "downtime_hours": round(r["downtime_hours"], 1),
        })
    return {"from": date_from, "to": date_to, "group_by": group_by, "rows": out}


def heatmap(db: Session, date_from: str, date_to: str) -> list[dict]:
    start = datetime.fromisoformat(date_from).replace(tzinfo=tz)
    end = (datetime.fromisoformat(date_to) + timedelta(days=1)).replace(tzinfo=tz)
    allocs = db.query(ResourceAllocation).filter(
        ResourceAllocation.status == "active", ResourceAllocation.kind == "booking",
        ResourceAllocation.scheduled_start < end, ResourceAllocation.scheduled_end >= start).all()
    matrix: dict[tuple[int, int], float] = {}
    for a in allocs:
        s = max(a.scheduled_start, start).astimezone(tz)
        e = min(a.scheduled_end, end).astimezone(tz)
        cur = s
        while cur < e:
            nxt = min((cur.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)), e)
            wd = (cur.weekday() - 5) % 7
            hour = cur.hour
            h = (nxt - cur).total_seconds() / 3600
            matrix[(wd, hour)] = matrix.get((wd, hour), 0) + h
            cur = nxt
    return [{"weekday_fa": k[0], "hour": k[1], "hours": round(v, 2)} for k, v in matrix.items()]


def data_quality(db: Session) -> dict:
    spaces = db.query(Space).filter(Space.status != SpaceStatus.retired.value).all()
    missing_layouts = [s.name for s in spaces if not s.layouts]
    missing_features = [s.name for s in spaces if not s.space_features]
    missing_image = [s.name for s in spaces if not s.image_file_id]
    missing_responsible = [s.name for s in spaces if not (s.responsible_unit or s.responsible_person)]
    stale_refs = db.query(ExternalReference).filter(
        ExternalReference.sync_status != "fresh").count()
    total_refs = db.query(ExternalReference).count()
    return {
        "spaces_total": len(spaces),
        "missing_layouts": missing_layouts[:10], "missing_layouts_count": len(missing_layouts),
        "missing_features": missing_features[:10], "missing_features_count": len(missing_features),
        "missing_image_count": len(missing_image),
        "missing_responsible_count": len(missing_responsible),
        "external_refs_total": total_refs,
        "external_refs_stale": stale_refs,
        "completeness_pct": round(
            (len(spaces) - len(missing_layouts) - len(missing_features)) / max(len(spaces), 1) * 100, 1),
    }


def action_center(db: Session) -> list[dict]:
    """مرکز اقدام: هر هشدار دارای دکمه اقدام است؛ فقط نمودار نیست."""
    alerts: list[dict] = []
    now = datetime.now(tz)

    pending = db.query(BookingRequest).filter(
        BookingRequest.status.in_([RequestStatus.submitted.value, RequestStatus.under_review.value])).count()
    if pending:
        alerts.append({"code": "pending_requests", "severity": "info",
                       "title": f"{pending} درخواست در انتظار بررسی است",
                       "detail": "بررسی و تأیید/رد درخواست‌ها",
                       "actions": [{"code": "review", "label": "بررسی درخواست‌ها", "target": "/requests"}]})

    # جلسات با ظرفیت نامتناسب (برنامه‌ریزی‌شده کمتر از ۴۰٪ ظرفیت مؤثر)
    upcoming = db.query(BookingOccurrence).filter(
        BookingOccurrence.start_at >= now - timedelta(days=7),
        BookingOccurrence.start_at < now + timedelta(days=14),
        BookingOccurrence.status == OccurrenceStatus.scheduled.value).all()
    seats_freeable = 0.0
    mismatch_sessions = []
    for occ in upcoming:
        req = occ.request
        if req is None or req.requested_space_id is None or not req.expected_attendees:
            continue
        sp = db.get(Space, req.requested_space_id)
        if sp is None or not sp.layouts:
            continue
        cap_eff = max((l.capacity for l in sp.layouts), default=0)
        if cap_eff and req.expected_attendees <= cap_eff * 0.4:
            hours = (occ.end_at - occ.start_at).total_seconds() / 3600
            seats_freeable += (cap_eff - req.expected_attendees) * hours
            mismatch_sessions.append({"request": req.request_number, "space": sp.name,
                                      "attendees": req.expected_attendees, "capacity": cap_eff})
    if mismatch_sessions:
        alerts.append({"code": "capacity_mismatch", "severity": "warning",
                       "title": f"{len(mismatch_sessions)} جلسه در فضاهای با ظرفیت نامتناسب برگزار می‌شود",
                       "detail": f"بررسی جابه‌جایی ممکن است حدود {int(seats_freeable)} صندلی‌ـ‌ساعت ظرفیت آزاد کند",
                       "sessions": mismatch_sessions[:8],
                       "actions": [{"code": "simulate", "label": "شبیه‌سازی جابه‌جایی", "target": "/optimizer"}]})

    # فضاهای کم‌استفاده در ۱۴ روز گذشته
    frm = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    to = now.strftime("%Y-%m-%d")
    try:
        util_rows = utilization(db, frm, to, group_by="space")
        low = [r for r in util_rows["rows"] if r["planned_utilization_pct"] < 15 and r["bookable_hours"] > 20]
        if low:
            alerts.append({"code": "low_utilization", "severity": "info",
                           "title": f"{len(low)} فضا در دو هفته گذشته کمتر از ۱۵٪ استفاده شده است",
                           "detail": "احتمال اتلاف ظرفیت؛ پیش از تصمیم، علت و محدودیت‌ها (تجهیزات، موقعیت) بررسی شود",
                           "spaces": [r["key"] for r in low[:8]],
                           "actions": [{"code": "analyze", "label": "مشاهده تحلیل", "target": "/analytics"}]})
    except Exception:
        pass

    # جلسات متاثر از انسداد فعال
    blocks = db.query(MaintenanceBlock).filter(MaintenanceBlock.status == "active").all()
    affected = []
    for b in blocks:
        if b.space_id is None:
            continue
        cnt = db.query(ResourceAllocation).filter(
            ResourceAllocation.space_id == b.space_id,
            ResourceAllocation.status == "active",
            ResourceAllocation.kind == "booking",
            ResourceAllocation.scheduled_start < b.end_at,
            ResourceAllocation.scheduled_end > b.start_at).count()
        if cnt:
            affected.append({"block": b.title, "affected_sessions": cnt})
    if affected:
        alerts.append({"code": "maintenance_conflicts", "severity": "danger",
                       "title": f"{sum(a['affected_sessions'] for a in affected)} جلسه متاثر از انسداد تعمیراتی است",
                       "detail": "پیشنهاد جایگزین را بررسی و به مسئول مربوط ارجاع دهید",
                       "blocks": affected,
                       "actions": [{"code": "review", "label": "بررسی جلسات متاثر", "target": "/blocks"}]})

    # کالیبراسیون منقضی تجهیزات حساس
    from ..models import EquipmentAsset
    overdue = db.query(EquipmentAsset).filter(
        EquipmentAsset.next_calibration_due.isnot(None),
        EquipmentAsset.next_calibration_due < now.date(),
        EquipmentAsset.status != "retired").count()
    if overdue:
        alerts.append({"code": "calibration_overdue", "severity": "warning",
                       "title": f"کالیبراسیون {overdue} تجهیز منقضی شده است",
                       "detail": "استفاده از تجهیزات حساس با کالیبراسیون منقضی در رزروهای جدید باید محدود شود",
                       "actions": [{"code": "review", "label": "مشاهده تجهیزات", "target": "/equipment"}]})

    return alerts
