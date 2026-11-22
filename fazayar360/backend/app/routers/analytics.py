from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..db import get_db
from ..models import Space, UsageObservation, User
from ..services import analytics as analytics_svc

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/utilization")
def utilization(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                date_from: str = Query(...), date_to: str = Query(...),
                group_by: str = Query("building", pattern="^(building|campus|space_type|space)$")):
    """نرخ اشغال زمانی برنامه‌ریزی‌شده، استفاده واقعی، صندلی‌ـ‌ساعت، لغو، غیبت و ازکارافتادگی."""
    if group_by == "space":
        rows = analytics_svc.utilization(db, date_from, date_to, "space")
        spaces = {str(s.id): s for s in db.query(Space).all()}
        for r in rows["rows"]:
            sp = spaces.get(r["key"])
            if sp:
                r["key_label"] = f"{sp.name} ({sp.code})"
        return rows
    return analytics_svc.utilization(db, date_from, date_to, group_by)


@router.get("/heatmap")
def heatmap(db: Session = Depends(get_db), user: User = Depends(get_current_user),
            date_from: str = Query(...), date_to: str = Query(...)):
    """نقشه حرارتی استفاده در روزهای هفته و ساعت‌ها."""
    return analytics_svc.heatmap(db, date_from, date_to)


@router.get("/quality")
def quality(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """گزارش کیفیت و کامل‌بودن داده — گزارش‌ها منبع و کیفیت داده را مشخص می‌کنند."""
    return analytics_svc.data_quality(db)


@router.get("/action-center")
def action_center(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """مرکز اقدام مدیر آموزشی: هشدارهای قابل اقدام، نه فقط نمودار."""
    return analytics_svc.action_center(db)


@router.post("/usage-observations")
def add_observation(body: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """ثبت شواهد استفاده واقعی (داده مشاهده‌شده جدا از داده استنباط‌شده ذخیره می‌شود)."""
    obs = UsageObservation(
        space_id=body["space_id"],
        occurrence_id=body.get("occurrence_id"),
        observed_at=datetime.fromisoformat(body.get("observed_at") or datetime.utcnow().isoformat()),
        observed_headcount=int(body["observed_headcount"]),
        source=body.get("source") or "manual",
        observer_id=user.id,
        note=body.get("note"),
    )
    db.add(obs)
    db.commit()
    return {"id": str(obs.id)}
