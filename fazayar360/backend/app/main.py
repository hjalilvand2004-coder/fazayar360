import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError

from .config import settings
from .core.errors import AppError
from .db import SessionLocal, engine
from .ddl import apply_postgres_extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("fazayar")

_rate_bucket: dict[str, list[float]] = {}


def _rate_limited(client_ip: str) -> bool:
    now = time.time()
    window = _rate_bucket.setdefault(client_ip, [])
    while window and now - window[0] > 60:
        window.pop(0)
    if len(window) >= settings.rate_limit_per_minute:
        return True
    window.append(now)
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .models import Base, Campus
    Base.metadata.create_all(engine)
    apply_postgres_extras(engine)
    if settings.seed_on_start:
        db = SessionLocal()
        try:
            from .seed import seed_if_empty
            from .seed_usage import seed_usage
            if seed_if_empty(db):
                log.info("داده نمونه پایه ساخته شد")
            seed_usage(db)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            log.exception("خطا در ساخت داده نمونه")
        finally:
            db.close()
    yield


app = FastAPI(title=settings.app_name, description=settings.app_desc,
              version="1.1.0", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    if request.url.path.startswith("/api") and _rate_limited(request.client.host if request.client else "anon"):
        return JSONResponse({"error": {"code": "RATE_LIMITED", "message": "تعداد درخواست‌ها بیش از حد مجاز است",
                                       "details": []}, "request_id": request_id}, status_code=429)
    start = time.time()
    try:
        response = await call_next(request)
    except AppError as e:
        return JSONResponse({"error": {"code": e.code, "message": e.message, "details": e.details},
                             "request_id": request_id}, status_code=e.status)
    except IntegrityError:
        # نقض قیدهای دیتابیس (مثل EXCLUDE عدم هم‌پوشانی) → 409 ساختاریافته
        return JSONResponse({"error": {"code": "CONSTRAINT_CONFLICT",
                                       "message": "تراکنش با قید یکتایی یا عدم‌هم‌پوشانی سامانه تعارض دارد؛ داده نوسازی شده است",
                                       "details": []}, "request_id": request_id}, status_code=409)
    except Exception:  # noqa: BLE001
        log.exception("خطای غیرمنتظره در %s", request.url.path)
        return JSONResponse({"error": {"code": "INTERNAL", "message": "خطای داخلی سامانه؛ شناسه رهگیری را ذخیره کنید",
                                       "details": []}, "request_id": request_id}, status_code=500)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = str(int((time.time() - start) * 1000))
    return response


# ── Routerهای API ────────────────────────────────────────────────────
from .routers import (admin, analytics, auth, bookings, equipment, files, integrations,  # noqa: E402
                      optimization, public, search, spaces, structure)

api = app
api.include_router(auth.router, prefix="/api/v1")
api.include_router(structure.router, prefix="/api/v1")
api.include_router(spaces.router, prefix="/api/v1")
api.include_router(spaces.features_router, prefix="/api/v1")
api.include_router(bookings.router, prefix="/api/v1")
api.include_router(bookings.blocks_router, prefix="/api/v1")
api.include_router(search.router, prefix="/api/v1")
api.include_router(equipment.router, prefix="/api/v1")
api.include_router(analytics.router, prefix="/api/v1")
api.include_router(optimization.router, prefix="/api/v1")
api.include_router(integrations.router, prefix="/api/v1")
api.include_router(admin.router, prefix="/api/v1")
api.include_router(public.router, prefix="/api/v1")
api.include_router(files.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health():
    from sqlalchemy import text
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "app": settings.app_name, "db": db_ok}


# ── فرانت‌اند ساخته‌شده (SPA) ─────────────────────────────────────────
if settings.dist_dir:
    DIST = os.path.abspath(settings.dist_dir)
else:
    DIST = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "frontend", "dist"))

if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": {"code": "NOT_FOUND", "message": "مسیر API یافت نشد", "details": []},
                                 "request_id": ""}, status_code=404)
        index = os.path.join(DIST, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return JSONResponse({"error": {"code": "NO_UI", "message": "رابط کاربری ساخته نشده است", "details": []},
                             "request_id": ""}, status_code=200)
    log.info("SPA از %s سرو می‌شود", DIST)
