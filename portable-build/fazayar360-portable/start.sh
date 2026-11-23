#!/usr/bin/env bash
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
