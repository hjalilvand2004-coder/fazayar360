"""نقاط عمومی (بدون احراز هویت) برای QR Code کنار در فضا — بدون نمایش نام افراد یا جزئیات حساس."""
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..core.errors import AppError, NotFoundError
from ..models import (BlockStatus, Building, MaintenanceBlock, OccurrenceStatus,
                      ResourceAllocation, Space, SpaceStatus)

router = APIRouter(prefix="/public", tags=["public"])


def _passport(db: Session, space: Space) -> dict:
    from ..models import SpaceLayout
    today = datetime.now().astimezone().date()
    st = datetime(today.year, today.month, today.day).astimezone()
    en = st + timedelta(days=1)
    allocs = db.query(ResourceAllocation).filter(
        ResourceAllocation.space_id == space.id,
        ResourceAllocation.status == "active",
        ResourceAllocation.scheduled_start < en,
        ResourceAllocation.scheduled_end > st).order_by(ResourceAllocation.scheduled_start).all()
    # تقویم عمومی: فقط نوع استفاده و ساعت، نه نام افراد
    schedule = [{"kind": a.kind,
                 "start": a.scheduled_start.strftime("%H:%M"),
                 "end": a.scheduled_end.strftime("%H:%M"),
                 "use_type": a.request.use_type if (a.request_id and a.request) else None}
                for a in allocs]
    return {
        "code": space.code, "name": space.name, "space_type": space.space_type,
        "status": space.status,
        "building": {"name": space.building.name}, "campus": {"name": space.campus.name},
        "floor": {"number": space.floor.number} if space.floor else None,
        "layouts": [{"name": l.name, "capacity": l.capacity} for l in space.layouts],
        "safe_capacity": space.safe_capacity,
        "features": [{"name": sf.feature.name} for sf in space.space_features if sf.condition == "active"],
        "equipment": [{"name": se.type.name, "quantity": se.quantity} for se in space.space_equipment],
        "accessibility": {"step_free": space.has_step_free_access, "elevator": space.has_elevator_access,
                          "notes": space.accessibility_notes},
        "responsible_unit": space.responsible_unit,
        "responsible_contact": space.responsible_contact,
        "description": space.description,
        "today_schedule": schedule,
        "min_prep_minutes": space.min_prep_minutes,
    }


@router.get("/spaces/{slug}")
def public_space(slug: str, db: Session = Depends(get_db)):
    """شناسنامه عمومی + برنامه امروز + راه ارتباط با مسئول + ثبت گزارش خرابی."""
    space = db.query(Space).filter(Space.public_slug == slug).one_or_none()
    if space is None or space.status == SpaceStatus.retired.value:
        raise NotFoundError("فضا یافت نشد")
    return _passport(db, space)


class IssueIn(BaseModel):
    title: str
    description: str | None = None
    reporter_name: str | None = None


@router.post("/spaces/{slug}/report-issue", status_code=201)
def report_issue(slug: str, body: IssueIn, request: Request, db: Session = Depends(get_db)):
    """ثبت گزارش خرابی از اسکن QR — بدون احراز هویت، با محدودیت نرخ کلی."""
    space = db.query(Space).filter(Space.public_slug == slug).one_or_none()
    if space is None:
        raise NotFoundError("فضا یافت نشد")
    now = datetime.utcnow()
    blk = MaintenanceBlock(
        space_id=space.id, reason_code="repair", title=body.title[:200],
        description=body.description, reporter_name=body.reporter_name or "گزارش عمومی",
        status=BlockStatus.reported.value, start_at=now, end_at=now + timedelta(days=1))
    db.add(blk)
    db.flush()
    return {"id": str(blk.id), "message": "گزارش شما ثبت شد و برای مسئول ساختمان ارسال می‌شود"}
