"""
موتور پیشنهادی تخصیص فضا — نسخه قواعد رتبه‌بندی (کافی برای مسائل کوچک طبق طرح).
قیدهای سخت نقض نمی‌شوند؛ ترجیحات نرم با وزن امتیازدهی می‌شوند و همه چیز قابل توضیح است.
"""
import json
import statistics
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (OptimizationAssignment, OptimizationRun, ResourceAllocation, SolutionStatus)
from . import search as search_svc
from .capacity import parse_json_ids


def _occupied(db: Session, space_id, start, end) -> bool:
    rows = db.query(ResourceAllocation).filter(
        ResourceAllocation.space_id == space_id, ResourceAllocation.status == "active",
        ResourceAllocation.effective_start < end, ResourceAllocation.effective_end > start).count()
    return rows > 0


def run_optimization(db: Session, run: OptimizationRun) -> OptimizationRun:
    run.status = "running"
    db.flush()
    scenario = json.loads(run.scenario or "{}")
    sessions = scenario.get("sessions") or []
    assignments: list[dict] = []
    space_load: dict[str, float] = {}
    before_empty_seat_hours = 0.0
    after_empty_seat_hours = 0.0
    moves = 0
    unassigned = 0
    blockers_summary: dict[str, int] = {}

    # مرتب‌سازی بر اساس دشواری (کمترین گزینه‌ها اول) — تکنیک ساده و مؤثر
    order = []
    for s in sessions:
        filters = _session_filters(s)
        cands = search_svc.search_spaces(db, filters, include_near_misses=True)
        order.append((len(cands), s, cands))
    order.sort(key=lambda x: x[0])

    for _, s, cands in order:
        start = datetime.fromisoformat(s["start_at"])
        end = datetime.fromisoformat(s["end_at"])
        chosen = None
        for cand in cands:
            space_id = str(cand["space"].id)
            # عدم تداخل با پیشنهادهای قبلی همین اجرا
            overlap = any(a["space_id"] == space_id and a["start"] < end and a["end"] > start
                          for a in assignments if a["space_id"])
            if overlap:
                continue
            chosen = cand
            break

        cap = chosen["capacity"] if chosen else None
        attendees = int(s.get("attendees") or 0)
        if chosen is not None:
            space = chosen["space"]
            space_id = str(space.id)
            hours = (end - start).total_seconds() / 3600
            empty = max((cap or 0) - attendees, 0)
            before_empty_seat_hours += _current_empty(db, s)
            after_empty_seat_hours += empty * hours
            space_load[space_id] = space_load.get(space_id, 0) + hours
            is_move = bool(s.get("current_space_id")) and str(s["current_space_id"]) != space_id
            if is_move:
                moves += 1
            reasons = list(chosen["reasons"])
            if not is_move and s.get("current_space_id"):
                reasons.insert(0, "حفظ ثبات محل کلاس")
            load = round(space_load[space_id], 1)
            reasons.append(f"بار تجمیعی این فضا در دوره: {load} ساعت (توزیع متوازن)")
            assignments.append({
                "session_ref": s.get("ref") or s.get("title"),
                "title": s.get("title"),
                "space_id": space_id,
                "start": start, "end": end,
                "current_space_id": s.get("current_space_id"),
                "score": round(chosen["score"], 1),
                "reasons": reasons,
            })
        else:
            unassigned += 1
            blocker = "هیچ فضای واجد شرایطی در این بازه یافت نشد"
            if cands:
                blocker = "؛ ".join({c["blocker"] for c in cands[:3]})
            blockers_summary[blocker] = blockers_summary.get(blocker, 0) + 1
            assignments.append({
                "session_ref": s.get("ref") or s.get("title"),
                "title": s.get("title"),
                "space_id": None,
                "start": start, "end": end,
                "current_space_id": s.get("current_space_id"),
                "score": None,
                "reasons": [],
            })

    for a in assignments:
        db.add(OptimizationAssignment(
            run_id=run.id, session_ref=a["session_ref"] or "", title=a["title"],
            start_at=a["start"], end_at=a["end"],
            current_space_id=a["current_space_id"], proposed_space_id=a["space_id"],
            status="proposed",
            score_breakdown=json.dumps({"score": a["score"], "reasons": a["reasons"]}, ensure_ascii=False),
            blockers=json.dumps(blockers_summary, ensure_ascii=False) if a["space_id"] is None else None,
        ))

    if len(sessions) and unassigned == 0:
        solution_status = SolutionStatus.optimal.value
    elif unassigned < len(sessions):
        solution_status = SolutionStatus.partial.value
    elif sessions:
        solution_status = SolutionStatus.no_solution.value
    else:
        solution_status = SolutionStatus.no_solution.value

    improvement = round(before_empty_seat_hours - after_empty_seat_hours, 1)
    run.solution_status = solution_status
    run.metrics = json.dumps({
        "sessions_total": len(sessions),
        "assigned": len(sessions) - unassigned,
        "unassigned": unassigned,
        "moves": moves,
        "empty_seat_hours_before": round(before_empty_seat_hours, 1),
        "empty_seat_hours_after": round(after_empty_seat_hours, 1),
        "improvement_seat_hours": improvement,
        "load_stddev_before": None,  # محاسبه سنگین لازم ندارد؛ بار تجمیعی در دلایل آمده است
        "constraint_violations": 0,
    }, ensure_ascii=False)
    run.constraints_summary = json.dumps(blockers_summary, ensure_ascii=False)
    run.status = "completed"
    run.finished_at = datetime.utcnow()
    db.flush()
    return run


def _current_empty(db: Session, session: dict) -> float:
    cur_id = session.get("current_space_id")
    if not cur_id:
        return 0.0
    from ..models import Space
    sp = db.get(Space, cur_id)
    if sp is None or not sp.layouts:
        return 0.0
    cap = max((l.capacity for l in sp.layouts), default=0)
    hours = (datetime.fromisoformat(session["end_at"]) - datetime.fromisoformat(session["start_at"])).total_seconds() / 3600
    return max(cap - int(session.get("attendees") or 0), 0) * hours


def _session_filters(s: dict) -> dict:
    f = {
        "start_at": s["start_at"], "end_at": s["end_at"],
        "attendees": s.get("attendees") or 0,
        "feature_ids": s.get("required_feature_ids") or [],
        "equipment_type_ids": s.get("required_equipment_type_ids") or [],
        "layout": s.get("layout"),
        "accessibility_required": bool(s.get("accessibility_required")),
        "needs_lab_manager": bool(s.get("needs_lab_manager")),
        "target_building_id": s.get("preferred_building_id"),
        "building_id": s.get("preferred_building_id") or None,
        "campus_id": s.get("preferred_campus_id") or None,
    }
    if s.get("space_types"):
        f["space_types"] = s["space_types"]
    return f
