import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, require_roles
from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..db import get_db
from ..models import (EquipmentAllocation, EquipmentAsset, EquipmentPool, EquipmentStatus,
                      EquipmentType, ResourceAllocation, User)

router = APIRouter(prefix="/equipment", tags=["equipment"])


def asset_dict(a: EquipmentAsset) -> dict:
    return {"id": str(a.id), "asset_tag": a.asset_tag, "name": a.name, "model": a.model,
            "serial_number": a.serial_number, "status": a.status,
            "type": {"id": str(a.type_id), "name": a.type.name, "category": a.type.category},
            "location_space_id": str(a.location_space_id) if a.location_space_id else None,
            "last_service_date": a.last_service_date.isoformat() if a.last_service_date else None,
            "next_calibration_due": a.next_calibration_due.isoformat() if a.next_calibration_due else None,
            "usage_restriction": a.usage_restriction,
            "responsible_person": a.responsible_person,
            "bookable_independently": a.bookable_independently,
            "docs": json.loads(a.docs) if a.docs else []}


@router.get("/types")
def types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [{"id": str(t.id), "code": t.code, "name": t.name, "category": t.category,
             "default_lead_minutes": t.default_lead_minutes}
            for t in db.query(EquipmentType).order_by(EquipmentType.name).all()]


class TypeIn(BaseModel):
    code: str
    name: str
    category: str = "fixed"
    default_lead_minutes: int = 0


@router.post("/types", status_code=201)
def create_type(body: TypeIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("sys_admin", "lab_manager"))):
    if body.category not in ("fixed", "portable", "consumable"):
        raise ValidationError("دسته تجهیز نامعتبر است")
    t = EquipmentType(code=body.code, name=body.name, category=body.category,
                      default_lead_minutes=body.default_lead_minutes)
    db.add(t)
    db.flush()
    write_audit(db, user, "create", "equipment_type", t.id, after={"code": t.code})
    return {"id": str(t.id)}


@router.get("/assets")
def assets(db: Session = Depends(get_db), user: User = Depends(get_current_user),
           status: str | None = None, type_id: str | None = None,
           page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=500)):
    q = db.query(EquipmentAsset)
    if status:
        q = q.filter(EquipmentAsset.status == status)
    if type_id:
        q = q.filter(EquipmentAsset.type_id == type_id)
    total = q.count()
    rows = q.order_by(EquipmentAsset.name).offset((page - 1) * size).limit(size).all()
    return {"items": [asset_dict(a) for a in rows], "total": total, "page": page, "size": size}


class AssetIn(BaseModel):
    type_id: str
    asset_tag: str | None = None
    name: str
    model: str | None = None
    serial_number: str | None = None
    location_space_id: str | None = None
    usage_restriction: str | None = None
    responsible_person: str | None = None
    next_calibration_due: str | None = None
    bookable_independently: bool = False


@router.post("/assets", status_code=201)
def create_asset(body: AssetIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "lab_manager"))):
    if db.get(EquipmentType, body.type_id) is None:
        raise NotFoundError("نوع تجهیز یافت نشد")
    a = EquipmentAsset(type_id=body.type_id, asset_tag=body.asset_tag, name=body.name,
                       model=body.model, serial_number=body.serial_number,
                       location_space_id=body.location_space_id,
                       usage_restriction=body.usage_restriction,
                       responsible_person=body.responsible_person,
                       next_calibration_due=body.next_calibration_due,
                       bookable_independently=body.bookable_independently)
    db.add(a)
    db.flush()
    write_audit(db, user, "create", "equipment_asset", a.id, after={"name": a.name})
    return asset_dict(a)


class AssetPatch(BaseModel):
    status: str | None = None
    location_space_id: str | None = None
    usage_restriction: str | None = None
    next_calibration_due: str | None = None
    last_service_date: str | None = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v):
        if v is not None and v not in [t.value for t in EquipmentStatus]:
            raise ValueError("وضعیت نامعتبر است")
        return v


@router.patch("/assets/{asset_id}")
def patch_asset(asset_id: str, body: AssetPatch, db: Session = Depends(get_db),
                user: User = Depends(require_roles("sys_admin", "lab_manager"))):
    a = db.get(EquipmentAsset, asset_id)
    if a is None:
        raise NotFoundError("تجهیز یافت نشد")
    before = {"status": a.status}
    data = body.model_dump(exclude_none=True)
    for k, v in data.items():
        setattr(a, k, v)
    db.flush()
    # خروج تجهیز از دسترس → ثبت خرابی در تجهیزات فضاهای مرتبط برای جست‌وجو
    if body.status == EquipmentStatus.broken.value and a.location_space_id:
        from ..models import SpaceEquipment
        db.query(SpaceEquipment).filter(SpaceEquipment.space_id == a.location_space_id,
                                        SpaceEquipment.type_id == a.type_id).update(
            {SpaceEquipment.is_broken: True}, synchronize_session=False)
    write_audit(db, user, "update", "equipment_asset", a.id, before=before, after=data)
    db.commit()
    return asset_dict(a)


@router.get("/pools")
def pools(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    out = []
    for p in db.query(EquipmentPool).all():
        active = db.query(EquipmentAllocation).filter(
            EquipmentAllocation.pool_id == p.id,
            EquipmentAllocation.status == "active").count()
        out.append({"id": str(p.id), "name": p.name, "total_quantity": p.total_quantity,
                    "type": {"id": str(p.type_id), "name": p.type.name},
                    "active_allocations": active})
    return out
