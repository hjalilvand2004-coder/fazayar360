import secrets

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..config import settings
from ..core.audit import write_audit
from ..core.deps import get_current_user
from ..core.errors import AppError
from ..core.security import create_access_token, verify_password
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/auth", tags=["auth"])

ROLE_LABELS = {
    "student": "دانشجو", "professor": "استاد", "education_expert": "کارشناس آموزش",
    "education_manager": "مدیر آموزش", "lab_manager": "مدیر آزمایشگاه",
    "facility_manager": "مدیر نگهداری و تعمیرات", "university_admin": "مدیر دانشگاه",
    "sys_admin": "مدیر سامانه",
}


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginIn, db=Depends(get_db), request: Request = None):
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise AppError(401, "BAD_CREDENTIALS", "نام کاربری یا گذرواژه نادرست است")
    write_audit(db, user, "LOGIN", "user", user.id, after={"via": "password"},
                ip=request.client.host if request else None)
    db.commit()
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


# ───────────────────────── ورود یکپارچه سازمانی (SSO/OIDC) ─────────────────────────

def _sso_urls() -> tuple[str, str, str]:
    """نشانی سه نقطهٔ اتصال OIDC؛ اگر پیکربندی نشده باشد قالب استاندارد Keycloak ساخته می‌شود."""
    base = settings.sso_issuer.rstrip("/")
    authorize = settings.sso_authorize_url or f"{base}/protocol/openid-connect/auth"
    token = settings.sso_token_url or f"{base}/protocol/openid-connect/token"
    userinfo = settings.sso_userinfo_url or f"{base}/protocol/openid-connect/userinfo"
    return authorize, token, userinfo


def _sso_redirect_default(request: Request) -> str:
    """مسیر بازگشت پیش‌فرض از جنس همین استقرار (برای صفحهٔ callback تک‌صفحه‌ای)."""
    if settings.sso_redirect_uri:
        return settings.sso_redirect_uri
    root = str(request.base_url).rstrip("/")
    return f"{root}/#/sso/callback"


@router.get("/sso/config")
def sso_config(request: Request = None):
    """پیکربندی عمومی SSO برای صفحهٔ ورود (بدون هیچ راز)."""
    enabled = bool(settings.sso_enabled)
    authorize, _, _ = _sso_urls() if enabled else ("", "", "")
    demo_available = bool(settings.demo_mode)
    return {
        "enabled": enabled,
        "demo_available": demo_available,
        "authorize_url": authorize if enabled else "",
        "client_id": settings.sso_client_id if enabled else "",
        "scopes": settings.sso_scopes if enabled else "",
        "redirect_hint": _sso_redirect_default(request) if enabled and request else "",
        "org_name": "حساب سازمانی زیست‌بوم",
    }


class SsoExchangeIn(BaseModel):
    code: str
    redirect_uri: str
    state: str | None = None


def _get_or_create_sso_user(db, userinfo: dict, request: Request) -> User:
    sub = str(userinfo.get("sub") or "").strip()
    email = str(userinfo.get("email") or userinfo.get("preferred_username") or "").strip().lower()
    name = str(userinfo.get("name") or userinfo.get("given_name") or email or "کاربر سازمانی")
    if not sub and not email:
        raise AppError(400, "SSO_PROFILE_INCOMPLETE", "پروفایل کاربر سازمانی ناقص است")

    role = settings.sso_role_default
    if settings.sso_admin_email and email and email == settings.sso_admin_email.strip().lower():
        role = "sys_admin"

    user = None
    if sub:
        user = db.query(User).filter(User.external_id == sub).one_or_none()
    if user is None and email:
        user = db.query(User).filter(User.username == email).one_or_none()
    if user is None:
        username = email or f"sso-{sub[:12]}"
        user = User(username=username, password_hash=secrets.token_urlsafe(32),
                    display_name=name, role=role, external_id=sub or None, is_active=True)
        db.add(user)
        db.flush()
        write_audit(db, user, "SSO_USER_PROVISIONED", "user", user.id,
                    after={"username": username, "role": role},
                    ip=request.client.host if request else None)
    else:
        changed = False
        if sub and user.external_id != sub:
            user.external_id = sub
            changed = True
        if not user.is_active:
            raise AppError(403, "USER_INACTIVE", "حساب کاربری غیرفعال است")
        if changed:
            write_audit(db, user, "SSO_IDENTITY_LINKED", "user", user.id,
                        after={"external_id": sub}, ip=request.client.host if request else None)
    return user


@router.post("/sso/exchange")
def sso_exchange(body: SsoExchangeIn, db=Depends(get_db), request: Request = None):
    """تبدیل کد موقت OAuth2 به نشست محلی: کد → توکن → userinfo → کاربر → JWT سامانه."""
    if not settings.sso_enabled:
        raise AppError(400, "SSO_DISABLED", "ورود یکپارچه سازمانی روی این استقرار فعال نیست")
    _, token_url, userinfo_url = _sso_urls()
    redirect_uri = body.redirect_uri or _sso_redirect_default(request)
    try:
        with httpx.Client(timeout=10.0) as client:
            tok_res = client.post(token_url, data={
                "grant_type": "authorization_code",
                "code": body.code,
                "redirect_uri": redirect_uri,
                "client_id": settings.sso_client_id,
                "client_secret": settings.sso_client_secret,
            })
            if tok_res.status_code != 200:
                raise AppError(401, "SSO_CODE_INVALID", "کد ورود سازمانی نامعتبر یا منقضی است")
            access = tok_res.json().get("access_token")
            if not access:
                raise AppError(401, "SSO_TOKEN_MISSING", "توکن از سرور هویت دریافت نشد")
            prof_res = client.get(userinfo_url, headers={"Authorization": f"Bearer {access}"})
            if prof_res.status_code != 200:
                raise AppError(401, "SSO_PROFILE_FAILED", "خواندن پروفایل از سرور هویت ناموفق بود")
            userinfo = prof_res.json()
    except httpx.HTTPError:
        raise AppError(502, "SSO_PROVIDER_UNREACHABLE", "سرور هویت سازمانی در دسترس نیست")

    user = _get_or_create_sso_user(db, userinfo, request)
    write_audit(db, user, "LOGIN", "user", user.id, after={"via": "sso"},
                ip=request.client.host if request else None)
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, user.username),
        "token_type": "bearer",
        "user": {"id": str(user.id), "username": user.username, "display_name": user.display_name,
                 "role": user.role, "faculty": user.faculty,
                 "scope_building_id": str(user.scope_building_id) if user.scope_building_id else None},
    }


@router.post("/sso/demo")
def sso_demo(db=Depends(get_db), request: Request = None):
    """شبیه‌سازی ورود یکپارچه برای دمو و آموزش در محیط بدون سرور هویت واقعی."""
    if not settings.demo_mode:
        raise AppError(403, "DEMO_DISABLED", "در این استقرار حالت دمو غیرفعال است")
    user = db.query(User).filter(User.username == "sso.demo").one_or_none()
    if user is None:
        user = User(username="sso.demo", password_hash=secrets.token_urlsafe(32),
                    display_name="کارشناس آموزش (ورود سازمانی)", role="education_expert",
                    external_id="demo-sso-sub", is_active=True, faculty="معاونت آموزشی")
        db.add(user)
        db.flush()
    write_audit(db, user, "LOGIN", "user", user.id, after={"via": "sso-demo"},
                ip=request.client.host if request else None)
    db.commit()
    return {
        "access_token": create_access_token(user.id, user.role, user.username),
        "token_type": "bearer",
        "user": {"id": str(user.id), "username": user.username, "display_name": user.display_name,
                 "role": user.role, "faculty": user.faculty,
                 "scope_building_id": str(user.scope_building_id) if user.scope_building_id else None},
    }


@router.get("/sso/whoami-note")
def sso_note():
    """یادداشت عمومی: نقش‌های مجاز SSO برای مستندسازی صفحهٔ ورود."""
    return {"default_role": settings.sso_role_default, "roles_fa": ROLE_LABELS}
