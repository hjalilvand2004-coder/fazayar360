#!/usr/bin/env bash
set -u
STAGE=/home/z/my-project/download/portable-windows-staging
URLS=(
  "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/16.4.0/embedded-postgres-binaries-windows-amd64-16.4.0.jar"
  "https://repo.maven.apache.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/16.4.0/embedded-postgres-binaries-windows-amd64-16.4.0.jar"
  "https://repo1.maven.org/maven2/io/zonky/test/postgres/embedded-postgres-binaries-windows-amd64/16.2.0/embedded-postgres-binaries-windows-amd64-16.2.0.jar"
)
for i in 1 2 3 4 5 6; do
  for u in "${URLS[@]}"; do
    echo "[try $i] $u"
    if curl -sSL --fail -m 600 -o "$STAGE/postgres-win.jar.part" "$u"; then
      size=$(stat -c%s "$STAGE/postgres-win.jar.part")
      echo "downloaded size=$size"
      if [ "$size" -gt 10000000 ]; then mv "$STAGE/postgres-win.jar.part" "$STAGE/postgres-win.jar"; echo SUCCESS; exit 0; fi
    fi
    sleep 20
  done
done
echo FAILED_ALL
