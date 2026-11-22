import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, require_roles
from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..db import get_db
from ..models import (AllocationStatus, BookingOccurrence, BookingRequest, OptimizationAssignment,
                      OptimizationRun, OccurrenceStatus, RequestStatus, ResourceAllocation, Space,
                      User)
from ..services import conflict as cf
from ..services import optimizer as optimizer_svc

router = APIRouter(prefix="/optimization-runs", tags=["optimization"])


class SessionIn(BaseModel):
    ref: str
    title: str | None = None
    attendees: int
    start_at: str
    end_at: str
    required_feature_ids: list[str] = []
    required_equipment_type_ids: list[str] = []
    layout: str | None = None
    accessibility_required: bool = False
    needs_lab_manager: bool = False
    preferred_campus_id: str | None = None
    preferred_building_id: str | None = None
    space_types: list[str] = []
    current_space_id: str | None = None


class RunIn(BaseModel):
    title: str
    sessions: list[SessionIn]


@router.post("", status_code=201)
def create_run(body: RunIn, db: Session = Depends(get_db), user: User = Depends(get_current_user),
               run_async: bool = True):
    """ایجاد اجرای بهینه‌سازی؛ اجرا پس‌زمینه‌ای است تا API مسدود نشود."""
    if not body.sessions:
        raise ValidationError("حداقل یک جلسه در سناریو لازم است")
    run = OptimizationRun(title=body.title, status="queued", solver="rule_ranker",
                          scenario=json.dumps({"sessions": [s.model_dump() for s in body.sessions]},
                                              ensure_ascii=False),
                          created_by=user.id)
    db.add(run)
    db.flush()
    db.commit()
    if run_async:
        # اجرای پس‌زمینه (Worker هم‌ارز Celery در نسخه تک‌پردازشی)
        from ..db import SessionLocal
        run_id = run.id

        def _job():
            s2 = SessionLocal()
            try:
                r2 = s2.get(OptimizationRun, run_id)
                optimizer_svc.run_optimization(s2, r2)
                s2.commit()
            except Exception as e:  # noqa: BLE001
                s2.rollback()
                r2 = s2.get(OptimizationRun, run_id)
                if r2 is not None:
                    r2.status = "failed"
                    r2.error = str(e)
                    s2.commit()
            finally:
                s2.close()

        import threading
        threading.Thread(target=_job, daemon=True).start()
    else:
        optimizer_svc.run_optimization(db, run)
        db.commit()
    return {"id": str(run.id), "status": run.status}


@router.get("/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise NotFoundError("اجرا یافت نشد")
    assigns = db.query(OptimizationAssignment).filter(
        OptimizationAssignment.run_id == run.id).order_by(OptimizationAssignment.start_at).all()
    spaces = {str(s.id): s for s in db.query(Space).all()}

    def sp_ref(sid):
        if not sid:
            return None
        s = spaces.get(str(sid))
        return {"id": str(s.id), "name": s.name, "code": s.code, "building_name": s.building.name} if s else None

    return {
        "id": str(run.id), "title": run.title, "status": run.status,
        "solver": run.solver, "solution_status": run.solution_status,
        "metrics": json.loads(run.metrics) if run.metrics else None,
        "constraints_summary": json.loads(run.constraints_summary) if run.constraints_summary else None,
        "error": run.error,
        "assignments": [{
            "id": str(a.id), "session_ref": a.session_ref, "title": a.title,
            "start": a.start_at.isoformat(), "end": a.end_at.isoformat(),
            "current_space": sp_ref(a.current_space_id),
            "proposed_space": sp_ref(a.proposed_space_id),
            "status": a.status,
            "score_breakdown": json.loads(a.score_breakdown) if a.score_breakdown else None,
            "blockers": json.loads(a.blockers) if a.blockers else None,
        } for a in assigns],
    }


class ApplyIn(BaseModel):
    assignment_ids: list[str] = []   # خالی = همه پیشنهادهای تأییدشده


@router.post("/{run_id}/apply")
def apply_run(run_id: str, body: ApplyIn, db: Session = Depends(get_db),
              user: User = Depends(require_roles("sys_admin", "education_manager", "education_expert"))):
    """اعمال پیشنهاد نیازمند تأیید است و در لحظه اعمال، اعتبارسنجی مجدد می‌شود."""
    run = db.get(OptimizationRun, run_id)
    if run is None:
        raise NotFoundError("اجرا یافت نشد")
    if run.status != "completed":
        raise ConflictError("NOT_READY", "اجرا هنوز کامل نشده است")
    q = db.query(OptimizationAssignment).filter(OptimizationAssignment.run_id == run.id)
    if body.assignment_ids:
        q = q.filter(OptimizationAssignment.id.in_([uuid.UUID(i) for i in body.assignment_ids]))
    assigns = q.all()
    results = []
    for a in assigns:
        if a.status not in ("proposed", "approved") or a.proposed_space_id is None:
            continue
        req = db.query(BookingRequest).filter(BookingRequest.request_number == a.session_ref).one_or_none()
        occ = None
        if req is not None:
            occ = next((o for o in req.occurrences
                        if o.start_at == a.start_at and o.status != OccurrenceStatus.cancelled.value), None)
        try:
            if occ is not None:
                booking_move(db, occ, a, user)
                a.status = "applied"
            else:
                # تخصیص مستقیم (سناریوی آزاد): فقط وقتی بازه آزاد است
                space = db.get(Space, a.proposed_space_id)
                cf.assert_space_free(db, space, a.start_at, a.end_at)
                cf.assert_hours_allowed(db, space, a.start_at, a.end_at)
                cf.create_allocation(db, space, user, a.start_at, a.end_at, kind="booking",
                                     note=f"از بهینه‌سازی: {run.title}")
                a.status = "applied"
        except Exception as e:  # noqa: BLE001
            a.status = "failed"
            a.blockers = json.dumps({"error": str(e)}, ensure_ascii=False)
        results.append({"assignment_id": str(a.id), "status": a.status})
    write_audit(db, user, "apply_optimization", "optimization_run", run.id,
                after={"applied": sum(1 for r in results if r["status"] == "applied")})
    db.commit()
    return {"run_id": str(run.id), "results": results}


def booking_move(db: Session, occ, assignment, user):
    from ..services import booking as booking_svc
    booking_svc.move_occurrence(db, occ, user, new_space_id=assignment.proposed_space_id,
                                note=f"پیشنهاد بهینه‌سازی «{assignment.run.title}»")


@router.post("/{run_id}/assignments/{assignment_id}/approve")
def approve_assignment(run_id: str, assignment_id: str, db: Session = Depends(get_db),
                       user: User = Depends(require_roles("sys_admin", "education_manager"))):
    a = db.get(OptimizationAssignment, assignment_id)
    if a is None or str(a.run_id) != run_id:
        raise NotFoundError("پیشنهاد یافت نشد")
    a.status = "approved"
    db.commit()
    return {"id": str(a.id), "status": a.status}


@router.post("/{run_id}/assignments/{assignment_id}/reject")
def reject_assignment(run_id: str, assignment_id: str, db: Session = Depends(get_db),
                      user: User = Depends(require_roles("sys_admin", "education_manager"))):
    a = db.get(OptimizationAssignment, assignment_id)
    if a is None or str(a.run_id) != run_id:
        raise NotFoundError("پیشنهاد یافت نشد")
    a.status = "rejected"
    db.commit()
    return {"id": str(a.id), "status": a.status}
