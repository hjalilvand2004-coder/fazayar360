"""ساخت Release رسمی v1.1.1 در گیت‌هاب و آپلود دارایی‌ها — توکن از /tmp/.ghtoken خوانده می‌شود"""
import json
import os
import time
import urllib.request
import urllib.error

TOKEN = open("/tmp/.ghtoken").read().strip()
REPO = "hjalilvand2004-coder/fazayar360"
TAG = "v1.1.1"
API = f"https://api.github.com/repos/{REPO}"
UP = f"https://uploads.github.com/repos/{REPO}"
LOG = "/tmp/release.log"

NOTES = "/home/z/my-project/download/release-notes-v1.1.1.md"
ASSETS = [
    ("/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.1.zip",
     "application/zip"),
    ("/home/z/my-project/download/fazayar360-v1.1.1-source.zip",
     "application/zip"),
    ("/home/z/my-project/download/screenshots-v112/home-dark.png",
     "image/png"),
]

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

def req(method, url, data=None, headers=None, auth=True):
    h = {"Accept": "application/vnd.github+json", "User-Agent": "fazayar-release"}
    if headers:
        h.update(headers)
    if auth:
        h["Authorization"] = f"token {TOKEN}"
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    return urllib.request.urlopen(r, timeout=900)

# ۱) بررسی ریلیز موجود برای تگ
release = None
try:
    with req("GET", f"{API}/releases/tags/{TAG}") as r:
        release = json.load(r)
    log(f"release exists: id={release['id']}")
except urllib.error.HTTPError as e:
    if e.code == 404:
        log("no existing release for tag — creating")
    else:
        raise

body = open(NOTES).read()
payload = {
    "tag_name": TAG,
    "name": "فضایار۳۶۰ — نسخهٔ ۱.۱.۱ (تم شب فضایی)",
    "body": body,
    "draft": False,
    "prerelease": False,
    "make_latest": "true",
}
if release is None:
    with req("POST", f"{API}/releases", json.dumps(payload).encode(),
             {"Content-Type": "application/json"}) as r:
        release = json.load(r)
    log(f"release created: id={release['id']}")
else:
    with req("PATCH", f"{API}/releases/{release['id']}",
             json.dumps(payload).encode(), {"Content-Type": "application/json"}) as r:
        release = json.load(r)
    log(f"release patched: id={release['id']}")

# ۲) آپلود دارایی‌ها — حذف نسخهٔ قبلی هم‌نام در صورت وجود
existing = {a["name"]: a["id"] for a in release.get("assets", [])}
for path, ctype in ASSETS:
    name = os.path.basename(path)
    size = os.path.getsize(path)
    if name in existing:
        with req("DELETE", f"{API}/releases/assets/{existing[name]}"):
            pass
        log(f"old asset deleted: {name}")
    url = f"{UP}/releases/{release['id']}/assets?name={name}"
    with open(path, "rb") as f:
        payload = f.read()  # ارسال بایت کامل تا Content-Length معتبر باشد
    try:
        with req("POST", url, payload, {"Content-Type": ctype}) as r:
            out = json.load(r)
        log(f"uploaded: {name} ({size//1000} KB) state={out.get('state')}")
    except urllib.error.HTTPError as e:
        log(f"UPLOAD FAILED {name}: {e.code} {e.read()[:200]}")

# ۳) راستی‌آزمایی نهایی
with req("GET", f"{API}/releases/tags/{TAG}") as r:
    rel = json.load(r)
log(f"FINAL: release={rel.get('name')} latest={rel.get('make_latest')}")
for a in rel.get("assets", []):
    log(f"  asset: {a['name']} {a['size']//1000} KB -> {a['browser_download_url']}")
log("DONE")
