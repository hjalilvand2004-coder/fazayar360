"""ساخت بستهٔ پرتیبل ویندوز x64 فضایار۳۶۰ (نسخهٔ اصلاح‌شدهٔ v1.1.1)

پیش‌نیازها در download/portable-windows-staging/:
  python-embed.zip  → python-3.12.10-embed-amd64.zip از python.org
  wheels/           → pip download --platform win_amd64 --python-version 3.12 --only-binary=:all:
                      (همهٔ وابستگی‌ها شامل colorama؛ تحویلِ pip را کامل بپذیرید)
  edb-pgsql.zip     → باینری PostgreSQL 16.9 ویندوز از get.enterprisedb.com

نکات کلیدی این نسخه (اصلاح خطای v1.1.0):
  * site-packages با استخراج «همهٔ» ویل‌ها ساخته می‌شود، نه زیرمجموعهٔ دستی (annotated_doc و
    pydantic_core و httpcore و ... در v1.1.0 جا مانده بودند)
  * بسته‌بودن وابستگی‌ها با ارزیابی markerها برای محیط win/py3.12 راستی‌آزمایی می‌شود
  * run.bat بدون BOM (UTF-8 BOM باعث خطای «ي╗┐@echo» می‌شود)
"""
import os, re, shutil, sys, zipfile

STAGE = os.environ.get("STAGE", "/home/z/my-project/download/portable-windows-staging")
SRC = "/home/z/my-project/fazayar360"
BUILD = os.path.join(STAGE, "bundle")
BUNDLE = os.path.join(BUILD, "fazayar360-portable-windows-x64")
OUT = os.environ.get("OUT", "/home/z/my-project/download/fazayar360-portable-windows-x64.zip")
SP = os.path.join(BUNDLE, "site-packages")

def norm(s): return s.lower().replace("_", "-")
def step(m): print(f"[build] {m}", flush=True)

def copytree(src, dst):
    shutil.copytree(src, dst, dirs_exist_ok=True)

def build():
    os.makedirs(BUNDLE, exist_ok=True)
    # پایتون embeddable + ._pth
    py_dir = os.path.join(BUNDLE, "python-embed")
    if not os.path.exists(os.path.join(py_dir, "python.exe")):
        with zipfile.ZipFile(os.path.join(STAGE, "python-embed.zip")) as z:
            z.extractall(py_dir)
        open(os.path.join(py_dir, "python312._pth"), "w", encoding="ascii").write(
            "python312.zip\n.\n..\\site-packages\n..\\app\nimport site\n")
    # همهٔ ویل‌ها
    if os.path.exists(SP): shutil.rmtree(SP)
    wheels = sorted(f for f in os.listdir(os.path.join(STAGE, "wheels")) if f.endswith(".whl"))
    for w in wheels:
        with zipfile.ZipFile(os.path.join(STAGE, "wheels", w)) as z:
            z.extractall(SP)
    step(f"unpacked {len(wheels)} wheels")
    # کد + dist
    copytree(os.path.join(SRC, "backend", "app"), os.path.join(BUNDLE, "app", "app"))
    copytree(os.path.join(SRC, "frontend", "dist"), os.path.join(BUNDLE, "app", "frontend-dist"))
    # pgsql (subset bin/lib/share)
    pg_dst = os.path.join(BUNDLE, "pgsql")
    if not os.path.exists(os.path.join(pg_dst, "bin", "initdb.exe")):
        edb = os.path.join(STAGE, "edb-pgsql.zip")
        with zipfile.ZipFile(edb) as z:
            names = [n for n in z.namelist() if any(n.startswith(p) for p in ("pgsql/bin/", "pgsql/lib/", "pgsql/share/"))]
            z.extractall(os.path.join(STAGE, "edb-extract"), members=names)
        copytree(os.path.join(STAGE, "edb-extract", "pgsql"), pg_dst)
    # bat ها بدون BOM + راستی‌آزمایی وابستگی‌ها
    here = os.path.dirname(os.path.abspath(__file__))
    for name in ("run.bat", "stop.bat"):
        src = os.path.join(here, name)
        raw = open(src, "rb").read()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"BOM in {name}!"
        open(os.path.join(BUNDLE, name), "wb").write(raw)
    sys.path.insert(0, "/home/z/my-project/scripts")
    from fix_win_portable import check_dependency_closure, check_app_imports  # بازاستفاده از راستی‌آزمایی
    if not (check_dependency_closure() and check_app_imports()):
        step("FAILED closure"); return 1
    # zip
    if os.path.exists(OUT): os.remove(OUT)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _, files in os.walk(BUNDLE):
            for fn in files:
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, BUILD))
    step(f"DONE -> {OUT} ({os.path.getsize(OUT)//1_000_000} MB)")
    return 0

if __name__ == "__main__":
    sys.exit(build())
