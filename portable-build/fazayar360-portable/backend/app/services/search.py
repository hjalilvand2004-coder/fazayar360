"""جست‌وجوی فضای واجد شرایط + دلیل مناسب‌بودن — «فضای مناسب، در زمان مناسب، با تجهیزات آماده»."""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (Building, Campus, EquipmentType, Feature, Space, SpaceEquipment,
                      SpaceFeature, SpaceStatus, SpaceType)
from . import conflict as cf
from .capacity import parse_json_ids, space_effective_capacity


def _feature_names(db: Session, ids: list[str]) -> list[str]:
    if not ids:
        return []
    rows = db.query(Feature).filter(Feature.id.in_([uuid.UUID(i) for i in ids])).all()
    return [r.name for r in rows]


def search_spaces(db: Session, f: dict, include_near_misses: bool = True) -> list[dict]:
    """فقط موارد واجد شرایط (مرتب‌شده بر اساس امتیاز)."""
    return _search(db, f)[0]


def search_with_near_misses(db: Session, f: dict) -> dict:
    matches, near_misses = _search(db, f)
    return {"matches": matches, "near_misses": near_misses}


def _search(db: Session, f: dict) -> tuple[list[dict], list[dict]]:
    """
    فیلترها: بازه زمانی، تعداد افراد، پردیس/ساختمان، نوع فضا، تجهیزات ضروری، چیدمان،
    دسترس‌پذیری، ساختمان مقصد (برای فاصله) و نیاز به مسئول آزمایشگاه.
    """
    exclude_space_id = f.get("exclude_space_id")
    start = datetime.fromisoformat(f["start_at"]) if f.get("start_at") else None
    end = datetime.fromisoformat(f["end_at"]) if f.get("end_at") else None
    attendees = int(f.get("attendees") or 0)
    feature_ids = [str(i) for i in (f.get("feature_ids") or [])]
    equipment_type_ids = [str(i) for i in (f.get("equipment_type_ids") or [])]
    space_types = f.get("space_types") or []
    layout = f.get("layout")
    need_accessibility = bool(f.get("accessibility_required"))
    need_lab_manager = bool(f.get("needs_lab_manager"))
    target_building_id = f.get("target_building_id")

    q = db.query(Space).filter(Space.status == SpaceStatus.active.value)
    if space_types:
        q = q.filter(Space.space_type.in_(space_types))
    if f.get("campus_id"):
        q = q.filter(Space.campus_id == f["campus_id"])
    if f.get("building_id"):
        q = q.filter(Space.building_id == f["building_id"])
    if need_accessibility:
        q = q.filter(Space.has_step_free_access.is_(True))
    if need_lab_manager:
        q = q.filter(Space.needs_lab_manager.is_(True))
    if feature_ids:
        rows = (db.query(SpaceFeature.space_id)
                .filter(SpaceFeature.feature_id.in_([uuid.UUID(i) for i in feature_ids]),
                        SpaceFeature.condition == "active").all())
        ok_space_ids = {r[0] for r in rows}
        q = q.filter(Space.id.in_(ok_space_ids))

    target_building = db.get(Building, target_building_id) if target_building_id else None

    matches: list[dict] = []
    near_misses: list[dict] = []
    spaces = q.all()
    for space in spaces:
        if exclude_space_id and str(space.id) == str(exclude_space_id):
            continue
        cap = space_effective_capacity(db, space, layout, equipment_type_ids)
        if cap["missing_equipment"]:
            near_misses.append({"space": space, "blocker": "تجهیزات الزامی موجود/سالم نیست", "capacity": cap["capacity"]})
            continue
        if attendees and (cap["capacity"] is None or cap["capacity"] < attendees):
            near_misses.append({"space": space, "blocker": f"ظرفیت مؤثر {cap['capacity']} برای {attendees} نفر کافی نیست",
                                "capacity": cap["capacity"]})
            continue

        reasons: list[str] = []
        warnings: list[str] = []
        reasons.append(f"ظرفیت مؤثر {cap['capacity']} نفر" + (f" در چیدمان «{cap['layout']}»" if cap["layout"] else ""))
        for l in cap["limits"]:
            if l["source"] == "equipment":
                reasons.append(f"{l['label']}: {l['value']} نفر")
        reasons += [f"امکانات فعال: {n}" for n in _feature_names(db, feature_ids)]

        if need_lab_manager or space.needs_lab_manager:
            warnings.append("نیازمند تأیید حضور مسئول آزمایشگاه")
        if space.allowed_group_names:
            warnings.append(f"محدود به گروه‌های: {space.allowed_group_names}")

        same_building = False
        same_campus = False
        if target_building is not None:
            if space.building_id == target_building.id:
                same_building = True
                reasons.append(f"همان ساختمان مقصد ({target_building.name})")
            elif space.building.campus_id == target_building.campus_id:
                same_campus = True
                reasons.append(f"همان پردیس مقصد، فاصله پیاده چند دقیقه از «{target_building.name}»")

        blockers: list[str] = []
        if start is not None and end is not None:
            violations = cf.allowed_hours_violations(db, space, start, end)
            if violations:
                blockers = violations
            else:
                conflicts = cf.space_conflicts(db, space.id, start, end)
                if conflicts:
                    blockers = [f"اشغال در بازه: {_kind_fa(c.kind)} ({c.scheduled_start:%H:%M}–{c.scheduled_end:%H:%M})"
                                for c in conflicts[:3]]
            if blockers:
                near_misses.append({"space": space, "blocker": "؛ ".join(blockers), "capacity": cap["capacity"]})
                continue

        empty_capacity = (cap["capacity"] - attendees) if (cap["capacity"] and attendees) else (cap["capacity"] or 0)
        score = empty_capacity * 1.0
        if same_building:
            score -= 25
        elif same_campus:
            score -= 10
        if space.needs_lab_manager:
            score += 5

        matches.append({
            "space": space, "capacity": cap["capacity"], "limits": cap["limits"],
            "layout": cap["layout"], "reasons": reasons, "warnings": warnings,
            "empty_capacity": empty_capacity, "score": score,
            "same_building": same_building,
        })

    matches.sort(key=lambda m: m["score"])
    return matches, near_misses


def _kind_fa(kind: str) -> str:
    return {"booking": "رزرو تأییدشده", "maintenance": "انسداد", "hold": "نگهداشت موقت"}.get(kind, kind)


def serialize_match(db: Session, m: dict) -> dict:
    space: Space = m["space"]
    return {
        "id": str(space.id), "code": space.code, "name": space.name,
        "space_type": space.space_type, "status": space.status,
        "capacity": m["capacity"], "layout": m["layout"],
        "limits": m["limits"], "reasons": m["reasons"], "warnings": m["warnings"],
        "same_building": m["same_building"],
        "has_step_free_access": space.has_step_free_access,
        "needs_lab_manager": space.needs_lab_manager,
        "building": {"id": str(space.building_id), "name": space.building.name},
        "campus": {"id": str(space.campus_id), "name": space.campus.name},
        "floor": {"number": space.floor.number, "name": space.floor.name} if space.floor else None,
    }


def serialize_near_miss(nm: dict) -> dict:
    space: Space = nm["space"]
    return {"id": str(space.id), "code": space.code, "name": space.name,
            "blocker": nm["blocker"], "capacity": nm["capacity"],
            "building": space.building.name}
