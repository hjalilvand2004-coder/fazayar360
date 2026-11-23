from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, in_scope, require_roles
from ..core.errors import ForbiddenError, NotFoundError
from ..db import get_db
from ..models import Building, Campus, Floor, Space, User

router = APIRouter(prefix="/structure", tags=["structure"])


@router.get("/campuses")
def campuses(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Campus).order_by(Campus.name).all()
    out = []
    for c in rows:
        out.append({
            "id": str(c.id), "code": c.code, "name": c.name, "address": c.address,
            "buildings": [
                {"id": str(b.id), "code": b.code, "name": b.name, "campus_id": str(c.id),
                 "responsible_unit": b.responsible_unit,
                 "floors": [{"id": str(f.id), "number": f.number, "name": f.name}
                            for f in (b.floors or [])]}
                for b in db.query(Building).filter(Building.campus_id == c.id).all()
            ],
        })
    return out


class CampusIn(BaseModel):
    code: str
    name: str
    address: Optional[str] = None


class BuildingIn(BaseModel):
    campus_id: str
    code: str
    name: str
    responsible_unit: Optional[str] = None


class FloorIn(BaseModel):
    building_id: str
    number: int
    name: Optional[str] = None


@router.post("/campuses")
def create_campus(body: CampusIn, db: Session = Depends(get_db),
                  user: User = Depends(require_roles("sys_admin", "university_admin"))):
    c = Campus(code=body.code, name=body.name, address=body.address)
    db.add(c)
    db.flush()
    write_audit(db, user, "create", "campus", c.id, after={"code": c.code, "name": c.name})
    return {"id": str(c.id)}


@router.post("/buildings")
def create_building(body: BuildingIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("sys_admin", "university_admin"))):
    b = Building(campus_id=body.campus_id, code=body.code, name=body.name,
                 responsible_unit=body.responsible_unit)
    db.add(b)
    db.flush()
    write_audit(db, user, "create", "building", b.id, after={"code": b.code, "name": b.name})
    return {"id": str(b.id)}


@router.post("/floors")
def create_floor(body: FloorIn, db: Session = Depends(get_db),
                 user: User = Depends(require_roles("sys_admin", "university_admin"))):
    f = Floor(building_id=body.building_id, number=body.number, name=body.name)
    db.add(f)
    db.flush()
    return {"id": str(f.id)}


@router.get("/buildings/{building_id}/floormap")
def floormap(building_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """نقشه دوبعدی طبقات: هر طبقه با کادرهای قابل‌کلیک فضاها."""
    b = db.get(Building, building_id)
    if b is None:
        raise NotFoundError("ساختمان یافت نشد")
    if not in_scope(user, building_id=b.id, campus_id=b.campus_id):
        raise ForbiddenError("این ساختمان خارج از حوزه سازمانی شماست")
    floors = db.query(Floor).filter(Floor.building_id == b.id).order_by(Floor.number).all()
    out = []
    for f in floors:
        spaces = db.query(Space).filter(Space.floor_id == f.id, Space.status != "retired").all()
        out.append({
            "id": str(f.id), "number": f.number, "name": f.name,
            "spaces": [{
                "id": str(s.id), "code": s.code, "name": s.name, "space_type": s.space_type,
                "status": s.status, "map_x": s.map_x or 40, "map_y": s.map_y or 40,
                "map_w": s.map_w or 120, "map_h": s.map_h or 80,
            } for s in spaces],
        })
    return {"building": {"id": str(b.id), "name": b.name, "campus_id": str(b.campus_id)}, "floors": out}
