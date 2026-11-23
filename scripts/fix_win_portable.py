"""اصلاح بستهٔ پرتیبل ویندوز → نسخهٔ ۱.۱.۱

ریشهٔ خطای نسخهٔ ۱.۱.۰:
  1) site-packages ناقص بود — با pip و --no-deps فقط ۱۴ بستهٔ صریح نصب شد در حالی که
     ۲۳ ویل دانلود شده بود (annotated_doc، pydantic_core، httpcore، python-dotenv و ... جا ماندند).
  2) run.bat با BOM نوشته شده بود و خط اول به «ي╗┐@echo» تبدیل می‌شد.

اصلاحات این نسخه:
  * site-packages با استخراج مستقیمِ «همهٔ» ویل‌ها بازسازی می‌شود (بدون pip تا چیزی جا نیفتد)
  * راستی‌آزمایی بسته‌بودن: همهٔ Requires-Dist ها از METADATA چک می‌شوند؛ اگر چیزی کم باشد ساخت متوقف می‌شود
  * اسکن import های کد برنامه در برابر site-packages
  * run.bat/stop.bat کاملاً ASCII بدون BOM + PYTHONUTF8=1
"""
import os
import re
import shutil
import sys
import zipfile

STAGE = "/home/z/my-project/download/portable-windows-staging"
BUNDLE = os.path.join(STAGE, "bundle", "fazayar360-portable-windows-x64")
OLD_ZIP = "/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.0.zip"
NEW_ZIP = "/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.1.zip"
WHEELS = os.path.join(STAGE, "wheels")
SP = os.path.join(BUNDLE, "site-packages")

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
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

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

start "" cmd /c "timeout /t 8 >nul & start http://localhost:%APPPORT%"
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


def norm(name: str) -> str:
    return name.lower().replace("_", "-")


def step(msg):
    print(f"[fix] {msg}", flush=True)


def extract_bundle():
    step("extract existing v1.1.0 bundle")
    if os.path.exists(BUNDLE):
        shutil.rmtree(BUNDLE)
    os.makedirs(os.path.dirname(BUNDLE), exist_ok=True)
    with zipfile.ZipFile(OLD_ZIP) as z:
        z.extractall(os.path.dirname(BUNDLE))


def rebuild_site_packages():
    step("rebuild site-packages from ALL wheels")
    if os.path.exists(SP):
        shutil.rmtree(SP)
    wheels = sorted(f for f in os.listdir(WHEELS) if f.endswith(".whl"))
    for w in wheels:
        with zipfile.ZipFile(os.path.join(WHEELS, w)) as z:
            z.extractall(SP)
    print(f"[fix] unpacked {len(wheels)} wheels -> {SP}")


def check_dependency_closure():
    from pip._vendor.packaging.markers import Marker

    step("verify dependency closure from METADATA")
    # محیط هدف: ویندوز x64، پایتون 3.12
    env = {
        "os_name": "nt", "sys_platform": "win32", "platform_system": "Windows",
        "platform_machine": "AMD64", "platform_python_implementation": "CPython",
        "implementation_name": "cpython", "python_version": "3.12",
        "python_full_version": "3.12.10",
    }
    installed = {}
    for di in os.listdir(SP):
        if di.endswith(".dist-info"):
            meta = os.path.join(SP, di, "METADATA")
            if os.path.exists(meta):
                for line in open(meta, encoding="utf-8", errors="replace"):
                    if line.startswith("Name:"):
                        installed[norm(line.split(":", 1)[1].strip())] = di
                        break
    missing = []
    for di in sorted(installed.values()):
        meta = os.path.join(SP, di, "METADATA")
        for line in open(meta, encoding="utf-8", errors="replace"):
            if not line.startswith("Requires-Dist:"):
                continue
            req = line[len("Requires-Dist:"):].strip()
            if ";" in req:
                base, marker = req.split(";", 1)
                try:
                    if not Marker(marker.strip()).evaluate(env):
                        continue
                except Exception:
                    pass  # marker غیرقابل‌ارزیابی → محتاطانه نگهش می‌داریم
                req = base.strip()
            name = re.split(r"[<>=!~\[; ]", req)[0].strip()
            if name and norm(name) not in installed:
                missing.append(f"{di}: {name}")
    if missing:
        print("[fix] MISSING DEPENDENCIES:")
        for m in missing:
            print("   -", m)
        return False
    print(f"[fix] closure OK — {len(installed)} dists, all Requires-Dist satisfied (win/py3.12)")
    return True


def check_app_imports():
    step("scan app imports vs site-packages")
    stdlib = sys.stdlib_module_names
    top = {d.lower() for d in os.listdir(SP) if not d.endswith(".dist-info")}
    top |= {d[:-len(".dist-info")].lower() for d in os.listdir(SP) if d.endswith(".dist-info")}
    warn = []
    for root, _, files in os.walk(os.path.join(BUNDLE, "app", "app")):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            for line in open(os.path.join(root, fn), encoding="utf-8", errors="replace"):
                m = re.match(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", line)
                if not m:
                    continue
                mod = m.group(1).split(".")[0].lower()
                if mod in stdlib or mod in ("app",):
                    continue
                if mod not in top and mod.replace("_", "-") not in top:
                    warn.append(f"{fn}: {mod}")
    if warn:
        print("[fix] IMPORT WARNINGS (module dir not found):")
        for w in sorted(set(warn)):
            print("   -", w)
        return False
    print("[fix] app imports OK")
    return True


def write_scripts():
    step("write run.bat / stop.bat (ASCII, no BOM)")
    for name, content in (("run.bat", RUN_BAT), ("stop.bat", STOP_BAT)):
        with open(os.path.join(BUNDLE, name), "w", encoding="ascii", newline="\r\n") as f:
            f.write(content)
    raw = open(os.path.join(BUNDLE, "run.bat"), "rb").read()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM still present!"
    print("[fix] run.bat BOM-free verified")


def rezip():
    step("create v1.1.1 zip")
    if os.path.exists(NEW_ZIP):
        os.remove(NEW_ZIP)
    build_root = os.path.dirname(BUNDLE)
    with zipfile.ZipFile(NEW_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(BUNDLE):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, build_root))
    print(f"[fix] DONE -> {NEW_ZIP} ({os.path.getsize(NEW_ZIP)//1_000_000} MB)")


def main():
    extract_bundle()
    rebuild_site_packages()
    ok1 = check_dependency_closure()
    ok2 = check_app_imports()
    if not (ok1 and ok2):
        print("[fix] FAILED closure checks — bundle NOT zipped")
        return 1
    write_scripts()
    rezip()
    os.remove(OLD_ZIP)
    print("[fix] broken v1.1.0 zip removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
