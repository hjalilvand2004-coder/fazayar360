"""ساخت بسته پرتیبل لینوکس x86_64 فضایار۳۶۰ — قابل اجرا بدون پایتون/پای‌چارم/دیتابیس نصب‌شده.

ترکیب بسته:
  python/           → مفسر مستقل CPython 3.12 (python-build-standalone از uv)
  backend/          → کد FastAPI
  ui/               → فرانت‌اند ساخته‌شده (frontend/dist)
  scripts/          → راه‌انداز PostgreSQL توکار (pgserver)
  start.sh          → اجرای کامل سامانه روی پورت 8095 (یا FAZAYAR_PORT)
خروجی: download/fazayar360-portable-linux-x64-v1.0.0.tar.gz
"""
import os
import shutil
import subprocess
import sys

SRC = "/home/z/my-project/fazayar360"
PY_SRC = "/home/z/.local/share/uv/python/cpython-3.12.16-linux-x86_64-gnu"
VENV_PG = "/home/z/.venv/lib/python3.12/site-packages/pgserver/pginstall"
BUILD = "/home/z/my-project/portable-build"
BUNDLE = os.path.join(BUILD, "fazayar360-portable")
OUT = "/home/z/my-project/download/fazayar360-portable-linux-x64-v1.0.0.tar.gz"

START_SH = r"""#!/usr/bin/env bash
# ── اجرای پرتیبل فضایار۳۶۰ ─────────────────────────────────────────────
# بدون نیاز به نصب پایتون یا PostgreSQL؛ همه‌چیز داخل همین پوشه است.
# اجرا:  ./start.sh          (پورت 8095)   یا  FAZAYAR_PORT=8090 ./start.sh
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${FAZAYAR_PORT:-8095}"
PY="$DIR/python/bin/python"

export FAZAYAR_DIST_DIR="$DIR/ui"
export FAZAYAR_UPLOAD_DIR="$DIR/data/uploads"
export FAZAYAR_SEED_ON_START="${FAZAYAR_SEED_ON_START:-true}"
mkdir -p "$DIR/data/uploads"

# ۱) راه‌اندازی PostgreSQL توکار (pgserver)
"$PY" "$DIR/scripts/run_local_db.py" "$DIR/data/pgdata" --hold \
  > "$DIR/data/db.url" 2> "$DIR/data/db.log" &
HOLDER_PID=$!
trap 'kill $HOLDER_PID 2>/dev/null || true' EXIT

for i in $(seq 1 120); do
  [ -s "$DIR/data/db.url" ] && break
  if ! kill -0 $HOLDER_PID 2>/dev/null; then
    echo "❌ راه‌اندازی پایگاه داده ناموفق بود — لاگ: $DIR/data/db.log"
    cat "$DIR/data/db.log" | tail -20
    exit 1
  fi
  sleep 0.5
done
export FAZAYAR_DATABASE_URL="$(head -n 1 "$DIR/data/db.url")"

echo "════════════════════════════════════════════════"
echo "  فضایار۳۶۰ — نسخه پرتیبل"
echo "  آدرس: http://localhost:$PORT"
echo "  کاربر مدیر: admin / Faza360!   (داده نمونه)"
echo "  توقف: Ctrl+C  (پایگاه داده هم بسته می‌شود)"
echo "════════════════════════════════════════════════"

# ۲) اجرای سامانه در پیش‌زمینه
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --app-dir "$DIR/backend"
"""


def sh(cmd: str, **kw) -> None:
    print(f"$ {cmd[:120]}")
    subprocess.run(cmd, shell=True, check=True, **kw)


def main() -> int:
    shutil.rmtree(BUILD, ignore_errors=True)
    os.makedirs(BUNDLE)

    # ۱) مفسر مستقل پایتون (بدون کش‌ها و ماژول‌های تست)
    print("→ کپی مفسر مستقل پایتون…")
    sh(f"rsync -a --exclude '**/__pycache__' --exclude 'lib/python3.12/test' "
       f"--exclude 'lib/python3.12/turtledemo' --exclude 'lib/python3.12/idlelib' "
       f"--exclude 'lib/python3.12/config-3.12*lambda' "
       f"'{PY_SRC}/' '{BUNDLE}/python/'")

    # ۲) نصب وابستگی‌ها با pip خود بسته
    print("→ نصب وابستگی‌ها در بسته…")
    marker = os.path.join(BUNDLE, "python", "lib", "python3.12", "EXTERNALLY-MANAGED")
    if os.path.exists(marker):
        os.remove(marker)  # این نسخه، کپی اختصاصی بسته است (نه محیط سیستم)
    sh(f"'{BUNDLE}/python/bin/python3' -m pip install --no-cache-dir --quiet "
       "fastapi 'uvicorn[standard]' sqlalchemy psycopg2-binary pydantic pydantic-settings "
       "PyJWT python-multipart pgserver")

    # ۳) افزونه btree_gist کامپایل‌شده را از محیط توسعه کپی کن (اگر موجود باشد)
    print("→ افزودن btree_gist به pgserver بسته…")
    pgdst = None
    for root, dirs, files in os.walk(os.path.join(BUNDLE, "python", "lib", "python3.12", "site-packages")):
        if root.endswith(os.path.join("pgserver", "pginstall")):
            pgdst = root
            break
    if pgdst:
        # share/postgresql/extension/*  و  lib/postgresql/*.so  (pkglibdir)
        pairs = [("share/postgresql/extension", "btree_gist"), ("lib/postgresql", "btree_gist")]
        for rel, prefix in pairs:
            src_dir = os.path.join(VENV_PG, rel)
            dst_dir = os.path.join(pgdst, rel)
            os.makedirs(dst_dir, exist_ok=True)
            if os.path.isdir(src_dir):
                for f in os.listdir(src_dir):
                    if f.startswith(prefix):
                        shutil.copy2(os.path.join(src_dir, f), os.path.join(dst_dir, f))
                        print(f"   + {rel}/{f}")
            else:
                print(f"   ⚠ یافت نشد: {src_dir}")

    # ۴) کد سامانه، فرانت ساخته‌شده، اسکریپت‌ها
    print("→ کپی کد سامانه و UI…")
    sh(f"mkdir -p '{BUNDLE}/backend'")
    sh(f"rsync -a --exclude '__pycache__' '{SRC}/backend/app/' '{BUNDLE}/backend/app/'")
    sh(f"mkdir -p '{BUNDLE}/backend/data/uploads' '{BUNDLE}/scripts'")
    sh(f"cp '{SRC}/scripts/run_local_db.py' '{BUNDLE}/scripts/'")
    sh(f"rsync -a '{SRC}/frontend/dist/' '{BUNDLE}/ui/'")

    # ۵) راه‌انداز
    print("→ نوشتن start.sh و README…")
    with open(os.path.join(BUNDLE, "start.sh"), "w") as f:
        f.write(START_SH)
    os.chmod(os.path.join(BUNDLE, "start.sh"), 0o755)
    readme = """# فضایار۳۶۰ — نسخه پرتیبل (لینوکس x86_64)

این بسته **هیچ پیش‌نیازی ندارد**: نه پایتون، نه پای‌چارم، نه PostgreSQL، نه Docker.
مفسر پایتون مستقل و پایگاه‌داده PostgreSQL توکار (pgserver) داخل همین پوشه است.

## اجرا
```bash
tar xzf fazayar360-portable-linux-x64-v1.0.0.tar.gz
cd fazayar360-portable
./start.sh
```
سپس در مرورگر: http://localhost:8095

- کاربر مدیر نمونه: `admin` / گذرواژه `Faza360!` (و ۷ کاربر دیگر نقش‌محور)
- داده نمونه در اولین اجرا ساخته می‌شود (`FAZAYAR_SEED_ON_START=false` برای غیرفعال‌کردن)
- تغییر پورت: `FAZAYAR_PORT=8090 ./start.sh`
- داده‌ها در پوشه‌ی `data/` می‌ماند؛ با `Ctrl+C` همه‌چیز متوقف می‌شود.
- برای انتقال به سیستم دیگر، کل پوشه را کپی کنید و دوباره `./start.sh` بزنید.

## محدودیت نسخه پرتیبل
- مناسب استفاده عملیاتی تیم‌ها و دمو؛ برای استقرار سازمانیِ چندکاربره، نسخه Docker
  با PostgreSQL اختصاصی و پشتیبان‌گیری منظم توصیه می‌شود.
- نیازمند لینوکس x86_64 با glibc ≥ 2.17 است (اکثر توزیع‌های مدرن).
- اگر افزونه btree_gist بارگذاری نشود، سامانه با هشدار اجرا می‌شود و جلوگیری از
  رزرو متعارض به قفل تراکنشی سپرده می‌شود (قید دیتابیس لایه دوم دفاع است).
"""
    with open(os.path.join(BUNDLE, "README-PORTABLE.md"), "w") as f:
        f.write(readme)

    # ۶) فشرده‌سازی
    print("→ ساخت فایل tar.gz …")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    sh(f"tar czf '{OUT}' -C '{BUILD}' fazayar360-portable")

    size = os.path.getsize(OUT) / 1024 / 1024
    print(f"✅ ساخته شد: {OUT} ({size:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
