import uuid

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .errors import AppError, ForbiddenError, NotFoundError
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise AppError(401, "UNAUTHENTICATED", "برای این عملیات باید وارد سامانه شوید")
    payload = decode_token(creds.credentials)
    if payload is None:
        raise AppError(401, "TOKEN_INVALID", "نشست معتبر نیست یا منقضی شده است")
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise AppError(401, "USER_INACTIVE", "کاربر فعال نیست")
    request.state.user = user
    return user


def optional_user(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                  db: Session = Depends(get_db)) -> User | None:
    """کاربر اختیاری برای نقاط عمومی (مثل صفحه QR)."""
    if creds is None:
        return None
    payload = decode_token(creds.credentials)
    if payload is None:
        return None
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user and user.is_active:
        request.state.user = user
        return user
    return None


def require_roles(*roles: str):
    """کنترل دسترسی نقش‌محور در بک‌اند (نه فقط فرانت)."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise ForbiddenError("این عملیات با نقش شما مجاز نیست")
        return user

    return checker


def in_scope(user: User, building_id: uuid.UUID | None = None, campus_id: uuid.UUID | None = None,
             faculty: str | None = None) -> bool:
    """دسترسی حوزه‌ای: مدیران کل دسترسی دارند؛ سایر نقش‌ها محدود به حوزه سازمانی‌شان."""
    if user.role in ("sys_admin", "university_admin", "service"):
        return True
    if campus_id is not None and user.scope_campus_id is not None and user.scope_campus_id != campus_id:
        return False
    if building_id is not None and user.scope_building_id is not None and user.scope_building_id != building_id:
        return False
    if faculty is not None and user.faculty is not None and user.faculty != faculty:
        return False
    return True


def scope_filter(query, model, user: User):
    """فیلتر خودکار فهرست‌ها بر اساس حوزه سازمانی کاربر."""
    if user.role in ("sys_admin", "university_admin", "service"):
        return query
    if user.scope_building_id is not None and hasattr(model, "building_id"):
        query = query.filter(model.building_id == user.scope_building_id)
    elif user.scope_campus_id is not None and hasattr(model, "campus_id"):
        query = query.filter(model.campus_id == user.scope_campus_id)
    return query


def require_space_scope(user: User, space) -> None:
    if not in_scope(user, building_id=space.building_id, campus_id=space.campus_id, faculty=space.owner_faculty):
        raise ForbiddenError("این فضا خارج از حوزه سازمانی شماست")
