"""محاسبه ظرفیت مؤثر: کمینه ظرفیت ایمن، ظرفیت چیدمان و ظرفیت تجهیزات موردنیاز."""
import json
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Space, SpaceEquipment


def parse_json_ids(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def space_effective_capacity(db: Session, space: Space, layout_name: str | None = None,
                             required_equipment_type_ids: list[str] | None = None) -> dict:
    """
    ظرفیت مؤثر هر جلسه با توجه به چیدمان، ایمنی و تجهیزات قابل‌استفاده محاسبه می‌شود.
    خروجی شامل ظرفیت، مولفه‌های محدودکننده و تجهیزات ناقص است.
    """
    limits: list[dict] = []

    layouts = list(space.layouts)
    chosen = None
    if layout_name:
        chosen = next((l for l in layouts if l.name == layout_name), None)
    if chosen is None:
        chosen = next((l for l in layouts if l.is_default), None)
    if chosen is None and layouts:
        chosen = layouts[0]
    if chosen is not None:
        limits.append({"source": "layout", "label": f"ظرفیت چیدمان «{chosen.name}»", "value": chosen.capacity})

    if space.safe_capacity is not None:
        limits.append({"source": "safety", "label": "ظرفیت ایمن", "value": space.safe_capacity})

    missing_equipment: list[str] = []
    if required_equipment_type_ids:
        rows = db.query(SpaceEquipment).filter(SpaceEquipment.space_id == space.id,
                                               SpaceEquipment.is_broken.is_(False)).all()
        by_type: dict[str, list[SpaceEquipment]] = {}
        for r in rows:
            by_type.setdefault(str(r.type_id), []).append(r)
        for tid in required_equipment_type_ids:
            lst = by_type.get(tid)
            if not lst:
                missing_equipment.append(tid)
                continue
            eq_cap = 0
            for r in lst:
                if r.per_unit_capacity:
                    eq_cap += r.quantity * r.per_unit_capacity
            if eq_cap > 0:
                limits.append({"source": "equipment", "label": "ظرفیت تجهیزاتی", "value": eq_cap})

    capacity = min((l["value"] for l in limits if l["value"] is not None), default=None)
    return {"capacity": capacity, "limits": limits, "missing_equipment": missing_equipment,
            "layout": chosen.name if chosen else None}
