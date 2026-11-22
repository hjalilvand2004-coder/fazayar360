import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.audit import write_audit
from ..core.deps import get_current_user, require_roles
from ..core.errors import ConflictError, NotFoundError
from ..core.security import hash_password
from ..db import get_db
from ..models import AuditLog, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def users(db: Session = Depends(get_db), user: User = Depends(require_roles("sys_admin", "university_admin"))):
    return [{"id": str(u.id), "username": u.username, "display_name": u.display_name, "role": u.role,
             "faculty": u.faculty, "is_active": u.is_active,
             "scope_building_id": str(u.scope_building_id) if u.scope_building_id else None}
            for u in db.query(User).order_by(User.username).all()]


class UserIn(BaseModel):
    username: str
    password: str
    display_name: str
    role: str
    faculty: str | None = None
    scope_building_id: str | None = None


ALLOWED_ROLES = {"sys_admin", "education_expert", "education_manager", "lab_manager",
                 "facility_manager", "professor", "student", "university_admin", "service"}


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db),
                user: User = Depends(require_roles("sys_admin"))):
    if body.role not in ALLOWED_ROLES:
        raise ConflictError("BAD_ROLE", "نقش نامعتبر است")
    if db.query(User).filter(User.username == body.username).count():
        raise ConflictError("DUPLICATE", "نام کاربری تکراری است")
    u = User(username=body.username, password_hash=hash_password(body.password),
             display_name=body.display_name, role=body.role, faculty=body.faculty,
             scope_building_id=body.scope_building_id)
    db.add(u)
    db.flush()
    write_audit(db, user, "create", "user", u.id, after={"username": u.username, "role": u.role})
    db.commit()
    return {"id": str(u.id)}


@router.get("/audit-logs")
def audit_logs(db: Session = Depends(get_db), user: User = Depends(require_roles("sys_admin", "university_admin")),
               entity_type: str | None = None, page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return {"items": [{
        "id": str(a.id), "actor_name": a.actor_name, "action": a.action,
        "entity_type": a.entity_type, "entity_id": a.entity_id,
        "before": json.loads(a.before) if a.before else None,
        "after": json.loads(a.after) if a.after else None,
        "request_id": a.request_id, "ip": a.ip,
        "at": a.created_at.isoformat(),
    } for a in rows], "total": total, "page": page, "size": size}
