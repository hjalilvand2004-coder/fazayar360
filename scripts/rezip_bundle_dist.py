"""به‌روزرسانی frontend-dist داخل bundle و ساخت مجدد ZIP پرتیبل ویندوز v1.1.1"""
import os
import shutil
import zipfile

BUNDLE = "/home/z/my-project/portable-windows-staging/bundle/fazayar360-portable-windows-x64"
DIST_SRC = "/home/z/my-project/fazayar360/frontend/dist"
BUILD = os.path.dirname(BUNDLE)
OUT = "/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.1.zip"

dst = os.path.join(BUNDLE, "app", "frontend-dist")
shutil.rmtree(dst, ignore_errors=True)
shutil.copytree(DIST_SRC, dst)
print("[rezip] dist updated:", len(os.listdir(dst)), "entries")

if os.path.exists(OUT):
    os.remove(OUT)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for root, _, files in os.walk(BUNDLE):
        for fn in files:
            full = os.path.join(root, fn)
            z.write(full, os.path.relpath(full, BUILD))
print(f"[rezip] DONE -> {OUT} ({os.path.getsize(OUT)//1_000_000} MB)")
