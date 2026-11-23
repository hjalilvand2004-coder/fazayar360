#!/usr/bin/env bash
# دانلود اجزای پرتیبل ویندوز: Python embeddable + باینری PostgreSQL ویندوز + ویل‌ها
set -u
STAGE=/home/z/my-project/download/portable-windows-staging
mkdir -p "$STAGE"
LOG="$STAGE/fetch.log"
exec > >(tee -a "$LOG") 2>&1

echo "== [1/4] Python embeddable =="
curl -sSL -o "$STAGE/python-embed.zip" \
  https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip \
  && ls -la "$STAGE/python-embed.zip"

echo "== [2/4] پیدا کردن باینری PostgreSQL ویندوز =="
# از ریلیزهای theseus-rs/postgresql-binaries نام asset واقعی را می‌گیریم
ASSET_URL=$(curl -s -m 30 "https://api.github.com/repos/theseus-rs/postgresql-binaries/releases" \
  | python3 -c "
import json,sys
rels = json.load(sys.stdin)
for r in rels:
    tag = r.get('tag_name','')
    if tag.startswith('16.'):
        for a in r.get('assets',[]):
            n = a['name']
            if 'windows' in n and n.endswith('.zip') and 'x86_64' in n:
                print(a['browser_download_url']); break
        break
" | head -1)
echo "ASSET_URL=$ASSET_URL"
if [ -n "${ASSET_URL:-}" ]; then
  curl -sSL -o "$STAGE/postgres-win.zip" "$ASSET_URL" && ls -la "$STAGE/postgres-win.zip"
else
  echo "theseus API نتیجه نداد؛ تلاش با Maven Central (zonky)"
  curl -sSL --retry 3 --retry-delay 8 -o "$STAGE/postgres-win.jar" \
    "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/16.4.0/embedded-postgres-binaries-windows-amd64-16.4.0.jar" \
    && ls -la "$STAGE/postgres-win.jar"
fi

echo "== [3/4] دانلود ویل‌های win_amd64 =="
/home/z/.venv/bin/pip download \
  --platform win_amd64 --python-version 3.12 --only-binary=:all: \
  -d "$STAGE/wheels" \
  fastapi "uvicorn" "h11" sqlalchemy psycopg2-binary pydantic pydantic-settings PyJWT python-multipart httpx \
  2>&1 | tail -4
ls "$STAGE/wheels" | wc -l

echo "== DONE =="
