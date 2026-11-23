"""ساخت بستهٔ پرتیبل ویندوز x64 برای فضایار۳۶۰ — نسخهٔ ۱.۱.۰

ترکیب بسته:
  python-embed/    → CPython 3.12.10 embeddable amd64 (+ ._pth سفارشی)
  site-packages/   → همهٔ ویل‌های win_amd64 از پیش دانلودشده
  pgsql/           → باینری PostgreSQL 16.9 ویندوز (از EDB binaries zip)
  app/app/         → کد FastAPI
  app/frontend-dist/ → فرانت‌اند ساخته‌شده
  run.bat / stop.bat / README-FA.md
خروجی: download/fazayar360-portable-windows-x64-v1.1.0.zip
"""
import os
import shutil
import subprocess
import sys
import zipfile

STAGE = "/home/z/my-project/download/portable-windows-staging"
SRC = "/home/z/my-project/fazayar360"
BUILD = os.path.join(STAGE, "bundle")
BUNDLE = os.path.join(BUILD, "fazayar360-portable-windows-x64")
OUT = "/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.0.zip"

RUN_BAT = r"""@echo off
chcp 65001 >nul
title Fazayar360 - Portable
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%python-embed\python.exe"
set "PGBIN=%ROOT%pgsql\bin"
set "PGDATA=%ROOT%data\pgdata"
set "PGPORT=8098"
set "APPPORT=8095"
set "PGPASSWORD=fazayar"

if not exist "%PY%" ( echo python-embed not found & pause & exit /b 1 )
if not exist "%PGBIN%\initdb.exe" ( echo pgsql binaries not found & pause & exit /b 1 )

if not exist "%ROOT%data" mkdir "%ROOT%data"

if not exist "%PGDATA%\PG_VERSION" (
  echo [1/3] Initialising PostgreSQL data directory ^(first run^)...
  echo fazayar>"%ROOT%data\pwfile.txt"
  "%PGBIN%\initdb.exe" -D "%PGDATA%" -U fazayar --pwfile="%ROOT%data\pwfile.txt" -E UTF8 -A scram-sha-256 > "%ROOT%data\initdb.log" 2>&1
  del "%ROOT%data\pwfile.txt" 2>nul
)

echo [2/3] Starting PostgreSQL on port %PGPORT%...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -l "%ROOT%data\pg.log" -o "-p %PGPORT%" start

set /a WAIT=0
:waitpg
"%PGBIN%\pg_isready.exe" -h 127.0.0.1 -p %PGPORT% >nul 2>&1
if %errorlevel%==0 goto pgready
timeout /t 1 >nul
set /a WAIT+=1
if %WAIT% LSS 30 goto waitpg
echo PostgreSQL did not become ready - see data\pg.log
pause & exit /b 1

:pgready
"%PGBIN%\psql.exe" -h 127.0.0.1 -p %PGPORT% -U fazayar -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='fazayar'" | findstr "1" >nul
if %errorlevel% NEQ 0 "%PGBIN%\createdb.exe" -h 127.0.0.1 -p %PGPORT% -U fazayar fazayar

echo [3/3] Starting Fazayar360 on port %APPPORT% ...
set "FAZAYAR_DATABASE_URL=postgresql+psycopg2://fazayar:fazayar@127.0.0.1:%PGPORT%/fazayar"
set "FAZAYAR_DIST_DIR=%ROOT%app\frontend-dist"
set "FAZAYAR_UPLOAD_DIR=%ROOT%data\uploads"
set "FAZAYAR_JWT_SECRET=change-me-in-production"

start "" cmd /c "timeout /t 5 >nul & start http://localhost:%APPPORT%"
cd /d "%ROOT%app"
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port %APPPORT%
pause
endlocal
"""

STOP_BAT = r"""@echo off
chcp 65001 >nul
title Fazayar360 - Stop
setlocal
set "ROOT=%~dp0"
set "PGBIN=%ROOT%pgsql\bin"
set "PGDATA=%ROOT%data\pgdata"
echo Stopping Fazayar360 PostgreSQL...
"%PGBIN%\pg_ctl.exe" -D "%PGDATA%" -m fast stop
echo Done.
endlocal
"""

README = """# فضایار۳۶۰ — بستهٔ پرتیبل ویندوز (x64) — نگارش ۱.۱.۰

## اجرا
۱. پوشهٔ `fazayar360-portable-windows-x64` را روی دیسک ویندوز باز کنید (مسیر بدون فاصله بهتر است؛ مثلا `C:\\fazayar360`).
۲. روی **`run.bat`** دوبار کلیک کنید.
۳. پس از چند ثانیه مرورگر روی `http://localhost:8095` باز می‌شود.
۴. برای خاموش‌کردن پنجرهٔ سامانه را ببندید و **`stop.bat`** را اجرا کنید.

## چه چیزی داخل بسته است؟
- `python-embed/` — مفسر مستقل پایتون ۳.۱۲ (بدون نیاز به نصب پایتون)
- `site-packages/` — تمام وابستگی‌ها (FastAPI، SQLAlchemy، psycopg2 و ...)
- `pgsql/` — باینری PostgreSQL 16.9 ویندوز (بدون نیاز به نصب PostgreSQL)
- `app/` — کد بک‌اند + رابط کاربری ساخته‌شده
- داده‌ها در `data/` ساخته می‌شود (پایگاه داده در اولین اجرا مقداردهی می‌شود)

## ورود
- کاربران آزمایشی: `admin / expert / edu_manager / lab_manager / facility / professor / student / rector`
- گذرواژهٔ همه: `Faza360!`
- دکمهٔ «ورود یکپارچه سازمانی (SSO)» در محیط دمو، ورود سازمانی را شبیه‌سازی می‌کند.
- برای اتصال به سرور هویت واقعی، متغیرهای `FAZAYAR_SSO_ENABLED`, `FAZAYAR_SSO_ISSUER`,
  `FAZAYAR_SSO_CLIENT_ID`, `FAZAYAR_SSO_CLIENT_SECRET` را پیش از اجرا تنظیم کنید.

## نکات
- پورت‌ها: سامانه ۸۰۹۵، پایگاه دادهٔ توکار ۸۰۹۸
- در استقرار واقعی `FAZAYAR_JWT_SECRET` را حتماً عوض کنید.
- کل داده‌ها در پوشهٔ `data/` است؛ برای انتقال کامل، همین پوشه را همراه ببرید.
- اگر پورت ۸۰۹۵ اشغال است: در `run.bat` مقدار `APPPORT` را تغییر دهید.
- مشکل اجرا؟ لاگ‌ها در `data\\initdb.log` و `data\\pg.log`.
"""

PYTH_PTH = """python312.zip
.
..\\site-packages
..\\app
import site
"""


def step(msg):
    print(f"[build] {msg}", flush=True)


def copytree(src, dst, ignore=None):
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def main():
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(BUNDLE, exist_ok=True)

    # 1) پایتون embeddable
    py_dir = os.path.join(BUNDLE, "python-embed")
    if not os.path.exists(os.path.join(py_dir, "python.exe")):
        step("extract python-embed")
        with zipfile.ZipFile(os.path.join(STAGE, "python-embed.zip")) as z:
            z.extractall(py_dir)
        with open(os.path.join(py_dir, "python312._pth"), "w", encoding="ascii") as f:
            f.write(PYTH_PTH)

    # 2) site-packages از ویل‌های win_amd64
    sp_dst = os.path.join(BUNDLE, "site-packages")
    if not os.path.exists(sp_dst):
        step("copy site-packages")
        shutil.copytree(os.path.join(STAGE, "site-packages"), sp_dst)

    # 3) کد بک‌اند و فرانت ساخته‌شده
    step("copy app source + dist")
    copytree(os.path.join(SRC, "backend", "app"), os.path.join(BUNDLE, "app", "app"))
    shutil.copy2(os.path.join(SRC, "backend", "requirements.txt"), os.path.join(BUNDLE, "app", "requirements.txt"))
    copytree(os.path.join(SRC, "frontend", "dist"), os.path.join(BUNDLE, "app", "frontend-dist"))

    # 4) باینری PostgreSQL ویندوز
    edb = os.path.join(STAGE, "edb-pgsql.zip")
    pg_dst = os.path.join(BUNDLE, "pgsql")
    if not os.path.exists(os.path.join(pg_dst, "bin", "initdb.exe")):
        if not os.path.exists(edb) or os.path.getsize(edb) < 100_000_000:
            step("EDB zip not ready — skip pgsql (rerun later)")
            return 1
        step("extract postgresql windows binaries (subset: bin/lib/share)")
        with zipfile.ZipFile(edb) as z:
            names = [n for n in z.namelist()
                     if any(n.startswith(p) for p in ("pgsql/bin/", "pgsql/lib/", "pgsql/share/"))]
            z.extractall(os.path.join(STAGE, "edb-extract"), members=names)
        extracted = os.path.join(STAGE, "edb-extract", "pgsql")
        copytree(extracted, pg_dst)

    # 5) فایل‌های اجرایی و راهنما (CRLF برای ویندوز)
    step("write run.bat / stop.bat / README")
    for name, content in (("run.bat", RUN_BAT), ("stop.bat", STOP_BAT)):
        with open(os.path.join(BUNDLE, name), "w", encoding="utf-8-sig", newline="\r\n") as f:
            f.write(content)
    with open(os.path.join(BUNDLE, "README-FA.md"), "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(README)

    # 6) ZIP نهایی
    step("create zip (این مرحله چند دقیقه طول می‌کشد)")
    if os.path.exists(OUT):
        os.remove(OUT)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(BUNDLE):
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, BUILD)
                z.write(full, rel)
    size_mb = os.path.getsize(OUT) / 1_000_000
    step(f"DONE → {OUT} ({size_mb:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
