"""انتشار ریلیز GitHub v1.1.0 فضایار۳۶۰ — پوش + ریلیز + دارایی‌ها.

توکن از /tmp/.ghtoken خوانده می‌شود (اگر موجود باشد). بدون توکن: فقط زیپ‌ها ساخته می‌شوند
و پوش/ریلیز با پیام روشن شکست می‌خورد تا وضعیت دقیق گزارش شود.
"""
import json
import os
import subprocess
import sys
import urllib.request
import zipfile

REPO = "hjalilvand2004-coder/fazayar360"
TOKEN_FILE = "/tmp/.ghtoken"
WIN_ZIP = "/home/z/my-project/download/fazayar360-portable-windows-x64-v1.1.0.zip"
SRC_ZIP = "/home/z/my-project/download/fazayar360-v1.1.0-source-with-ui.zip"

BODY = """## فضایار۳۶۰ — نسخهٔ ۱.۱.۰ (ورود یکپارچه سازمانی + تم روز و شب + پرتیبل ویندوز)

### ✨ تازه‌های این نسخه
- 🔐 **ورود یکپارچه سازمانی (SSO/OIDC)**: دکمهٔ «ورود سازمانی» در صفحهٔ لاگین؛ جریان استاندارد OAuth2 Authorization Code (هم‌ساز با Keycloak و هر OIDC استاندارد)، تهیهٔ خودکار کاربر از پروفایل سازمانی، پیوند شناسهٔ بیرونی، نقش پیش‌فرض/مدیر از طریق `FAZAYAR_SSO_*` و ثبت کامل ورودها در ممیزی. در محیط دمو، ورود سازمانی شبیه‌سازی می‌شود تا بدون سرور هویت هم قابل آموزش باشد.
- 🌗 **تم روز و شب**: بازطراحی امروزی با متغیرهای CSS دو-تمی، کلید تغییر تم (روز/شب) در نوار بالا و صفحهٔ ورود، نوار کناری با حالت فعال گرادیانی، topbar شیشه‌ای و دکمه‌ها/ورودی‌های جدید — همهٔ صفحه‌ها در هر دو تم آزمایش بصری شده‌اند.
- 🪟 **بستهٔ پرتیبل ویندوز (x64)**: پایتون embeddable + PostgreSQL 16.9 ویندوز + همهٔ وابستگی‌ها؛ اجرا با دوبار کلیک روی `run.bat` — بدون نصب پایتون، PostgreSQL یا Docker.

### 🚀 اجرا (ویندوز)
```bat
unzip fazayar360-portable-windows-x64-v1.1.0.zip
cd fazayar360-portable-windows-x64
run.bat
:: → http://localhost:8095
```

### 👤 کاربران نمونه
`admin / expert / edu_manager / lab_manager / facility / professor / student / rector` — گذرواژهٔ همه: `Faza360!`
+ کاربر دموی SSO با دکمهٔ ورود سازمانی.

### 🧪 کیفیت
تمام صفحه‌ها در هر دو تم با مرورگر خودکار اسکرین‌شات و بازبینی شدند؛ جریان کامل SSO دمو (لاگین ← نشست ← داشبورد) با آزمون مرورگر تأیید شد؛ نقاط اتصال SSO با curl آزمون شدند.
"""


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd="/home/z/my-project/fazayar360",
                       capture_output=True)
    out = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
    return r.returncode, out


def make_source_zip():
    if os.path.exists(SRC_ZIP):
        os.remove(SRC_ZIP)
    rc, out = git("archive", "--format=zip", "--prefix=fazayar360/", "HEAD")
    if rc != 0:
        print("archive failed:", out)
        sys.exit(1)
    with open(SRC_ZIP, "wb") as f:
        f.write(out.encode())
    print(f"source zip: {os.path.getsize(SRC_ZIP)//1_000_000} MB")


def api(method, path, token=None, data=None, raw=None, content_type=None):
    url = f"https://api.github.com/{path}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "fazayar-release"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        raw = json.dumps(data).encode()
        content_type = content_type or "application/json"
    req = urllib.request.Request(url, data=raw, headers=headers, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def upload_asset(upload_url, file_path, name, token):
    base = upload_url.split("{")[0] + f"?name={name}"
    with open(file_path, "rb") as f:
        raw = f.read()
    status, _ = api("POST", "dummy", token=token, raw=raw,
                    content_type="application/zip")  # placeholder not used
    return status


def upload_asset_real(upload_url, file_path, name, token):
    import urllib.request as u
    base = upload_url.split("{")[0] + f"?name={name}"
    req = u.Request(base, data=open(file_path, "rb").read(), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/zip")
    req.add_header("User-Agent", "fazayar-release")
    try:
        with u.urlopen(req) as res:
            return res.status
    except u.HTTPError as e:
        return e.code


def main():
    make_source_zip()

    token = None
    if os.path.exists(TOKEN_FILE):
        token = open(TOKEN_FILE).read().strip()

    # پوش
    rc, out = git("push", "origin", "main", "--follow-tags")
    print("push:", out.strip()[:400])

    if not token:
        if rc == 0:
            print("PUSH_OK but no token for release API — ریلیز باید دستی ساخته شود")
        else:
            print("PUSH_FAILED: توکن گیت‌هاب در دسترس نیست")
        print("STATUS=PARTIAL")
        return

    status, rel = api("POST", f"repos/{REPO}/releases", token=token, data={
        "tag_name": "v1.1.0", "name": "فضایار۳۶۰ — نگارش ۱.۱.۰",
        "body": BODY, "draft": False, "prerelease": False,
    })
    print("release create:", status)
    if status not in (201, 422):
        print("STATUS=RELEASE_FAILED"); return
    upload_url = rel.get("upload_url", "")
    for path, name in ((WIN_ZIP, "fazayar360-portable-windows-x64-v1.1.0.zip"),
                       (SRC_ZIP, "fazayar360-v1.1.0-source-with-ui.zip")):
        if os.path.exists(path):
            s = upload_asset_real(upload_url, path, name, token)
            print(f"asset {name}: {s}")
    print("STATUS=OK")


if __name__ == "__main__":
    main()
