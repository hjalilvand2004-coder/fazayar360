"""ایجاد ریلیز GitHub v1.0.0 برای فضایار۳۶۰ و آپلود دارایی‌ها."""
import json
import sys
import urllib.request

REPO = "hjalilvand2004-coder/fazayar360"
TOKEN_FILE = "/tmp/.ghtoken"
PORTABLE = "/home/z/my-project/download/fazayar360-portable-linux-x64-v1.0.0.tar.gz"
SRCZIP = "/home/z/my-project/download/fazayar360.zip"
SRCZIP_NAME = "fazayar360-v1.0.0-source-with-ui.zip"

BODY = """## فضایار۳۶۰ — نسخه ۱.۰.۰ (هسته عملیاتی + آزمایشگاه + تحلیل + بهینه‌سازی)

زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی در زیست‌بوم **دانشجو۳۶۰**

### ✨ امکانات این نسخه
- شناسنامه جامع فضا با ساختار سلسله‌مراتبی (دانشگاه → پردیس → ساختمان → طبقه → فضا) و ظرفیت مؤثر بر اساس چیدمان/ایمنی/تجهیزات
- تقویم اشغال واحد و **جلوگیری قطعی از رزرو متعارض** (قید `EXCLUDE USING gist` + قفل تراکنشی؛ بازه مؤثر شامل آماده‌سازی و پاک‌سازی)
- رزرو تکرارشونده → رخدادهای تاریخ‌دار، جابه‌جایی جلسه با بررسی مجدد تعارض، انسداد تعمیراتی و پیشنهاد جایگزین
- تجهیزات ثابت/قابل‌حمل/شمارشی با کنترل تراکنشی موجودی و ظرفیت تجهیزاتی آزمایشگاه
- تحلیل ظرفیت: نرخ اشغال، صندلی‌ـ‌ساعت، نقشه حرارتی، کیفیت داده و **مرکز اقدام**
- سناریوسازی و بهینه‌سازی تخصیص (قواعد رتبه‌بندی قیدمحور) با تأیید انسانی و اعتبارسنجی مجدد
- دستیار «فضای مناسب پیدا کن» با متن فارسی (بدون وابستگی به LLM)، QR کنار در و صفحه عمومی فضا
- اتصال نسخه‌دار به پایه‌یار۳۶۰ (رونوشت مرجع + رویداد تکرارپذیر + Outbox) و ممیزی کامل
- React+TS با RTL، فونت وزیرمتن، تقویم شمسی، نقشه دوبعدی طبقات و ECharts

### 🚀 اجرا

**۱) Docker (سرور 188.212.96.235:8095):**
```bash
unzip fazayar360-v1.0.0-source-with-ui.zip && cd fazayar360
FAZAYAR_JWT_SECRET="کلید-قوی" docker compose up -d --build
# → http://188.212.96.235:8095
```

**۲) نسخه پرتیبل لینوکس (بدون پایتون/پای‌چارم/PostgreSQL/Docker):**
```bash
tar xzf fazayar360-portable-linux-x64-v1.0.0.tar.gz
cd fazayar360-portable && ./start.sh
# → http://localhost:8095
```

**۳) اجرا از سورس:** `backend`: `pip install -r requirements.txt && uvicorn app.main:app --port 8095` — `frontend`: `npm install && npm run build`

### 👤 کاربران نمونه (داده دمو)
`admin / expert / edu_manager / lab_manager / facility / professor / student / rector` — گذرواژه همه: `Faza360!`

### ✅ کیفیت
۳۸ سناریوی آزمون API سبز (از جمله دو تأیید هم‌زمان روی یک فضا: یکی ۲۰۰ و دیگری ۴۰۹)،
آزمون پشتیبان‌گیری/بازیابی و بررسی بصری رابط — روی نسخه Docker و روی بسته پرتیبل.

### 📦 دارایی‌ها
| فایل | کاربرد |
| --- | --- |
| `fazayar360-portable-linux-x64-v1.0.0.tar.gz` (~۷۲MB) | اجرا بدون هیچ پیش‌نیازی روی لینوکس x86_64 |
| `fazayar360-v1.0.0-source-with-ui.zip` | کد کامل + UI ساخته‌شده (برای Docker/توسعه) |
| Source code (zip/tar.gz) | سورس مخزن |

### ⚠️ یادداشت‌ها
- در استقرار واقعی `FAZAYAR_JWT_SECRET` را تغییر و `FAZAYAR_SEED_ON_START=false` کنید و کاربران نمونه را حذف/بازنویسی نمایید.
- موتور بهینه‌سازی در این نسخه قواعد رتبه‌بندی است (طبق طرح برای مسائل کوچک کفایت می‌کند)؛ جایگزینی با OR-Tools CP-SAT در `services/optimizer.py` پیش‌بینی شده است.
- احراز هویت JWT محلی است و نقطه‌ی جایگزینی با OIDC سرویس هویت زیست‌بوم در `core/security.py` مشخص است.
"""


def api(url: str, method: str = "GET", data: dict | None = None,
        headers: dict | None = None, raw: bytes | None = None):
    token = open(TOKEN_FILE).read().strip()
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
         "User-Agent": "fazayar360-release"}
    if headers:
        h.update(headers)
    body = raw if raw is not None else (json.dumps(data).encode() if data else None)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    # اگر ریلیز موجود است، حذف کن (اجرای مجدد)
    st, existing = api(f"https://api.github.com/repos/{REPO}/releases/tags/v1.0.0")
    if st == 200:
        print("ریلیز قبلی حذف می‌شود…")
        api(f"https://api.github.com/repos/{REPO}/releases/{existing['id']}", method="DELETE")

    st, rel = api(f"https://api.github.com/repos/{REPO}/releases", method="POST", data={
        "tag_name": "v1.0.0",
        "target_commitish": "main",
        "name": "فضایار۳۶۰ v1.0.0 — هسته عملیاتی",
        "body": BODY,
        "draft": False,
        "prerelease": False,
    })
    if st != 201:
        print("RELEASE ERROR:", st, json.dumps(rel, ensure_ascii=False)[:500])
        return 1
    rid = rel["id"]
    print(f"ریلیز ساخته شد: id={rid} html={rel['html_url']}")

    assets = [(PORTABLE, "fazayar360-portable-linux-x64-v1.0.0.tar.gz", "application/gzip"),
              (SRCZIP, SRCZIP_NAME, "application/zip")]
    for path, name, ctype in assets:
        print(f"→ آپلود {name} …")
        st, res = api(f"https://uploads.github.com/repos/{REPO}/releases/{rid}/assets?name={name}",
                      method="POST", raw=open(path, "rb").read(),
                      headers={"Content-Type": ctype})
        if st != 201:
            print("ASSET ERROR:", st, json.dumps(res, ensure_ascii=False)[:300])
            return 1
        print(f"   ✓ {res['name']} ({res['size'] // 1024 // 1024}MB) state={res['state']}")
    print("تمام شد:", rel["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
