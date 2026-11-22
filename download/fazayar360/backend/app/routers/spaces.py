import json
import uuid
from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, in_scope, require_roles, require_space_scope, scope_filter
from ..core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from ..db import get_db
from ..models import (AvailabilityRule, Building, Feature, Floor, Space, SpaceFeature,
                      SpaceLayout, SpaceStatus, SpaceType, User)
from ..services import conflict as cf
from ..services.capacity import space_effective_capacity

router = APIRouter(prefix="/spaces", tags=["spaces"])


def space_dict(db: Session, s: Space, brief: bool = False) -> dict:
    d = {
        "id": str(s.id), "code": s.code, "name": s.name, "space_type": s.space_type,
        "status": s.status, "campus_id": str(s.campus_id), "building_id": str(s.building_id),
        "building_name": s.building.name, "campus_name": s.campus.name,
        "floor": {"id": str(s.floor.id), "number": s.floor.number, "name": s.floor.name} if s.floor else None,
        "safe_capacity": s.safe_capacity, "area_m2": float(s.area_m2) if s.area_m2 else None,
        "has_step_free_access": s.has_step_free_access, "has_elevator_access": s.has_elevator_access,
        "accessibility_notes": s.accessibility_notes,
        "needs_lab_manager": s.needs_lab_manager, "allowed_group_names": s.allowed_group_names,
        "responsible_unit": s.responsible_unit, "responsible_person": s.responsible_person,
        "responsible_contact": s.responsible_contact, "description": s.description,
        "min_prep_minutes": s.min_prep_minutes, "min_cleanup_minutes": s.min_cleanup_minutes,
        "public_slug": s.public_slug, "image_file_id": str(s.image_file_id) if s.image_file_id else None,
        "map": {"x": s.map_x, "y": s.map_y, "w": s.map_w, "h": s.map_h},
        "version": s.version,
        "owner_faculty": s.owner_faculty,
    }
    if brief:
        return d
    d.update({
        "layouts": [{"id": str(l.id), "name": l.name, "capacity": l.capacity, "seats_count": l.seats_count,
                     "tables_count": l.tables_count, "is_default": l.is_default} for l in s.layouts],
        "features": [{"id": str(sf.feature_id), "name": sf.feature.name, "code": sf.feature.code,
                      "category": sf.feature.category, "condition": sf.condition, "note": sf.note}
                     for sf in s.space_features],
        "equipment": [{"type_id": str(se.type_id), "type_name": se.type.name, "category": se.type.category,
                       "quantity": se.quantity, "per_unit_capacity": se.per_unit_capacity, "is_broken": se.is_broken}
                      for se in s.space_equipment],
        "availability_rules": [{"weekday": r.weekday, "start_time": r.start_time.strftime("%H:%M"),
                                "end_time": r.end_time.strftime("%H:%M"), "is_bookable": r.is_bookable}
                               for r in s.availability_rules],
        "docs": json.loads(s.docs) if s.docs else [],
    })
    return d


@router.get("")
def list_spaces(db: Session = Depends(get_db), user: User = Depends(get_current_user),
                q: str | None = None, space_type: str | None = None, building_id: str | None = None,
                campus_id: str | None = None, status: str | None = None,
                page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    query = db.query(Space)
    if q:
        query = query.filter(Space.name.ilike(f"%{q}%") | Space.code.ilike(f"%{q}%"))
    if space_type:
        query = query.filter(Space.space_type == space_type)
    if building_id:
        query = query.filter(Space.building_id == building_id)
    if campus_id:
        query = query.filter(Space.campus_id == campus_id)
    if status:
        query = query.filter(Space.status == status)
    query = scope_filter(query, Space, user)
    total = query.count()
    rows = query.order_by(Space.code).offset((page - 1) * size).limit(size).all()
    return {"items": [space_dict(db, s, brief=True) for s in rows], "total": total, "page": page, "size": size}


class LayoutIn(BaseModel):
    name: str
    capacity: int
    seats_count: int | None = None
    tables_count: int | None = None
    is_default: bool = False


class SpaceIn(BaseModel):
    code: str
    name: str
    space_type: str
    building_id: str
    floor_id: str | None = None
    campus_id: str | None = None
    area_m2: float | None = None
    safe_capacity: int | None = None
    description: str | None = None
    responsible_unit: str | None = None
    responsible_person: str | None = None
    responsible_contact: str | None = None
    has_step_free_access: bool = False
    has_elevator_access: bool = False
    accessibility_notes: str | None = None
    needs_lab_manager: bool = False
    allowed_group_names: str | None = None
    min_prep_minutes: int = 0
    min_cleanup_minutes: int = 0
    owner_faculty: str | None = None
    map_x: int | None = None
    map_y: int | None = None
    map_w: int | None = None
    map_h: int | None = None
    layouts: list[LayoutIn] = []
    feature_ids: list[str] = []

    @field_validator("space_type")
    @classmethod
    def valid_type(cls, v):
        if v not in [t.value for t in SpaceType]:
            raise ValueError("نوع فضا نامعتبر است")
        return v


@router.post("", status_code=201)
def create_space(body: SpaceIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "education_expert"))):
    b = db.get(Building, body.building_id)
    if b is None:
        raise NotFoundError("ساختمان یافت نشد")
    if not in_scope(user, building_id=b.id, campus_id=b.campus_id):
        raise ForbiddenError("ایجاد فضا در این ساختمان خارج از حوزه سازمانی شماست")
    if db.query(Space).filter(Space.code == body.code).count():
        raise ConflictError("DUPLICATE_CODE", "کد فضا تکراری است")
    campus_id = body.campus_id or str(b.campus_id)
    s = Space(code=body.code, name=body.name, space_type=body.space_type,
              campus_id=campus_id, building_id=body.building_id, floor_id=body.floor_id,
              area_m2=body.area_m2, safe_capacity=body.safe_capacity,
              description=body.description, responsible_unit=body.responsible_unit,
              responsible_person=body.responsible_person, responsible_contact=body.responsible_contact,
              has_step_free_access=body.has_step_free_access, has_elevator_access=body.has_elevator_access,
              accessibility_notes=body.accessibility_notes, needs_lab_manager=body.needs_lab_manager,
              allowed_group_names=body.allowed_group_names,
              min_prep_minutes=body.min_prep_minutes, min_cleanup_minutes=body.min_cleanup_minutes,
              owner_faculty=body.owner_faculty, map_x=body.map_x, map_y=body.map_y,
              map_w=body.map_w or 120, map_h=body.map_h or 80, public_slug=uuid.uuid4().hex[:16])
    db.add(s)
    db.flush()
    for l in body.layouts:
        db.add(SpaceLayout(space_id=s.id, name=l.name, capacity=l.capacity,
                           seats_count=l.seats_count, tables_count=l.tables_count, is_default=l.is_default))
    for fid in body.feature_ids:
        if db.get(Feature, fid):
            db.add(SpaceFeature(space_id=s.id, feature_id=fid))
    db.flush()
    write_audit(db, user, "create", "space", s.id, after={"code": s.code, "name": s.name})
    return space_dict(db, s)


@router.get("/{space_id}")
def get_space(space_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    require_space_scope(user, s)
    return space_dict(db, s)


class SpacePatch(BaseModel):
    name: str | None = None
    space_type: str | None = None
    status: str | None = None
    safe_capacity: int | None = None
    area_m2: float | None = None
    description: str | None = None
    responsible_unit: str | None = None
    responsible_person: str | None = None
    responsible_contact: str | None = None
    has_step_free_access: bool | None = None
    has_elevator_access: bool | None = None
    accessibility_notes: str | None = None
    needs_lab_manager: bool | None = None
    allowed_group_names: str | None = None
    min_prep_minutes: int | None = None
    min_cleanup_minutes: int | None = None
    image_file_id: str | None = None
    version: int  # کنترل نسخه برای جلوگیری از بازنویسی هم‌زمان

    @field_validator("status")
    @classmethod
    def valid_status(cls, v):
        if v is not None and v not in [t.value for t in SpaceStatus]:
            raise ValueError("وضعیت نامعتبر است")
        return v


@router.patch("/{space_id}")
def patch_space(space_id: str, body: SpacePatch, db: Session = Depends(get_db),
                user: User = Depends(require_roles("sys_admin", "education_expert", "facility_manager",
                                                    "lab_manager"))):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    require_space_scope(user, s)
    if body.version != s.version:
        raise ConflictError("VERSION_CONFLICT",
                            "رکورد توسط کاربر دیگری تغییر کرده است؛ صفحه را نوسازی و دوباره تلاش کنید")
    data = body.model_dump(exclude={"version"})
    before = {k: getattr(s, k) for k in data if data.get(k) is not None}
    if body.status == SpaceStatus.retired.value and not s.layouts:
        pass  # بازنشستگی مجاز است
    for k, v in data.items():
        if v is not None:
            setattr(s, k, v)
    s.version += 1
    db.flush()
    write_audit(db, user, "update", "space", s.id, before=before, after=data)
    return space_dict(db, s)


@router.get("/{space_id}/capacity")
def capacity(space_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
             layout: str | None = None, equipment_type_ids: str | None = None):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    ids = [i for i in (equipment_type_ids or "").split(",") if i]
    return space_effective_capacity(db, s, layout, ids)


@router.get("/{space_id}/availability")
def availability(space_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
                 start_at: str = Query(...), end_at: str = Query(...)):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    st = datetime.fromisoformat(start_at)
    en = datetime.fromisoformat(end_at)
    conflicts = [{"kind": c.kind, "start": c.scheduled_start.isoformat(), "end": c.scheduled_end.isoformat(),
                  "note": c.note} for c in cf.space_conflicts(db, s.id, st, en)]
    violations = cf.allowed_hours_violations(db, s, st, en)
    cap = space_effective_capacity(db, s)
    return {"available": not conflicts and not violations,
            "conflicts": conflicts, "hour_violations": violations,
            "effective_capacity": cap["capacity"], "limits": cap["limits"]}


@router.get("/{space_id}/calendar")
def calendar(space_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
             date_from: str = Query(...), date_to: str = Query(...)):
    from ..models import BookingOccurrence, ResourceAllocation, SpaceStatus
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    st = datetime.fromisoformat(date_from)
    en = (datetime.fromisoformat(date_to) + timedelta(days=1))
    allocs = db.query(ResourceAllocation).filter(
        ResourceAllocation.space_id == s.id,
        ResourceAllocation.status == "active",
        ResourceAllocation.scheduled_start < en,
        ResourceAllocation.scheduled_end > st).all()
    events = []
    for a in allocs:
        title = a.note or ""
        req = a.request
        if req is not None:
            title = req.title
        events.append({
            "allocation_id": str(a.id), "kind": a.kind,
            "start": a.scheduled_start.isoformat(), "end": a.scheduled_end.isoformat(),
            "title": title or ("انسداد" if a.kind == "maintenance" else "رزرو"),
            "request_number": req.request_number if req else None,
            "use_type": req.use_type if req else None,
        })
    return {"space_id": str(s.id), "events": events}


# ── چیدمان‌ها، امکانات و قواعد ساعات مجاز ────────────────────────────
class LayoutSetIn(BaseModel):
    layouts: list[LayoutIn]


@router.put("/{space_id}/layouts")
def set_layouts(space_id: str, body: LayoutSetIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("sys_admin", "education_expert", "lab_manager"))):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    require_space_scope(user, s)
    if not body.layouts:
        raise ValidationError("حداقل یک چیدمان لازم است")
    db.query(SpaceLayout).filter(SpaceLayout.space_id == s.id).delete()
    has_default = any(l.is_default for l in body.layouts)
    for i, l in enumerate(body.layouts):
        db.add(SpaceLayout(space_id=s.id, name=l.name, capacity=l.capacity, seats_count=l.seats_count,
                           tables_count=l.tables_count, is_default=l.is_default or (not has_default and i == 0)))
    s.version += 1
    db.flush()
    write_audit(db, user, "update_layouts", "space", s.id, after={"layouts": len(body.layouts)})
    return space_dict(db, s)


class FeatureSetIn(BaseModel):
    feature_ids: list[str]


@router.put("/{space_id}/features")
def set_features(space_id: str, body: FeatureSetIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "education_expert", "lab_manager"))):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    require_space_scope(user, s)
    db.query(SpaceFeature).filter(SpaceFeature.space_id == s.id).delete()
    for fid in body.feature_ids:
        if db.get(Feature, fid):
            db.add(SpaceFeature(space_id=s.id, feature_id=fid))
    s.version += 1
    db.flush()
    write_audit(db, user, "update_features", "space", s.id, after={"count": len(body.feature_ids)})
    return space_dict(db, s)


class RuleIn(BaseModel):
    weekday: int  # 0=شنبه
    start_time: str
    end_time: str
    is_bookable: bool = True

    @field_validator("weekday")
    @classmethod
    def valid_wd(cls, v):
        if not 0 <= v <= 6:
            raise ValueError("روز هفته باید بین ۰ تا ۶ باشد")
        return v


class RuleSetIn(BaseModel):
    rules: list[RuleIn]


@router.put("/{space_id}/availability-rules")
def set_rules(space_id: str, body: RuleSetIn, db: Session = Depends(get_db),
              user: User = Depends(require_roles("sys_admin", "education_expert", "facility_manager"))):
    s = db.get(Space, space_id)
    if s is None:
        raise NotFoundError("فضا یافت نشد")
    require_space_scope(user, s)
    db.query(AvailabilityRule).filter(AvailabilityRule.space_id == s.id).delete()
    for r in body.rules:
        t0 = time.fromisoformat(r.start_time)
        t1 = time.fromisoformat(r.end_time)
        if t1 <= t0:
            raise ValidationError(f"بازه روز {r.weekday} نامعتبر است")
        db.add(AvailabilityRule(space_id=s.id, weekday=r.weekday, start_time=t0, end_time=t1,
                                is_bookable=r.is_bookable))
    s.version += 1
    db.flush()
    write_audit(db, user, "update_rules", "space", s.id, after={"rules": len(body.rules)})
    return space_dict(db, s)


# ── فرهنگ ویژگی‌ها ──────────────────────────────────────────────────
features_router = APIRouter(prefix="/features", tags=["features"])


@features_router.get("")
def list_features(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": str(f.id), "code": f.code, "name": f.name, "category": f.category, "icon": f.icon}
            for f in db.query(Feature).order_by(Feature.category).all()]


class FeatureIn(BaseModel):
    code: str
    name: str
    category: str = "general"
    icon: str | None = None


@features_router.post("", status_code=201)
def create_feature(body: FeatureIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("sys_admin"))):
    f = Feature(code=body.code, name=body.name, category=body.category, icon=body.icon)
    db.add(f)
    db.flush()
    write_audit(db, user, "create", "feature", f.id, after={"code": f.code})
    return {"id": str(f.id)}
