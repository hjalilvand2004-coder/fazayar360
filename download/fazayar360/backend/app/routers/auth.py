from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..core.deps import get_current_user
from ..core.errors import AppError
from ..core.security import create_access_token, verify_password
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db=Depends(get_db), request: Request = None):
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise AppError(401, "BAD_CREDENTIALS", "نام کاربری یا گذرواژه نادرست است")
    return {
        "access_token": create_access_token(user.id, user.role, user.username),
        "token_type": "bearer",
        "user": {"id": str(user.id), "username": user.username, "display_name": user.display_name,
                 "role": user.role, "faculty": user.faculty,
                 "scope_building_id": str(user.scope_building_id) if user.scope_building_id else None},
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "username": user.username, "display_name": user.display_name,
            "role": user.role, "faculty": user.faculty,
            "scope_campus_id": str(user.scope_campus_id) if user.scope_campus_id else None,
            "scope_building_id": str(user.scope_building_id) if user.scope_building_id else None}
