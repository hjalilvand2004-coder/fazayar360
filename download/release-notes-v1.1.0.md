# ریلیز v1.1.0 — فضایار۳۶۰ (آماده برای پوش)

## وضعیت فعلی
- کامیت `bcff4d9` روی شاخهٔ `main` و تگ `v1.1.0` به‌صورت محلی ساخته شده است.
- پوش به GitHub در این نشست انجام نشد چون **هیچ توکن گیت‌هاب (PAT) در محیط موجود نیست**
  (`/tmp/.ghtoken` جلسهٔ قبل پاک شده و `GITHUB_TOKEN`/`GH_TOKEN` تنظیم نیست و gh/ssh هم در دسترس نیست).
- با یک توکن با دسترسی `repo`، پوش و ریلیز با همین دستورها یک‌جا انجام می‌شود:

```bash
cd /home/z/my-project/fazayar360
git push origin main --follow-tags

# ساخت ریلیز با REST API (بدون نیاز به gh):
TOKEN="ghp_..." curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/hjalilvand2004-coder/fazayar360/releases \
  -d "$(python3 - <<'PY'
import json
body = open('/home/z/my-project/download/release-notes-v1.1.0.md', encoding='utf-8').read()
print(json.dumps({"tag_name": "v1.1.0", "name": "فضایار۳۶۰ — نگارش ۱.۱.۰",
                  "body": body, "draft": False, "prerelease": False}))
PY
)"
# سپس آپلود دو دارایی:
#   fazayar360-portable-windows-x64-v1.1.0.zip
#   fazayar360-v1.1.0-source-with-ui.zip
# با POST https://uploads.github.com/repos/hjalilvand2004-coder/fazayar360/releases/<id>/assets?name=...
```

(یا اگر `gh` نصب شد: `gh auth login` سپس `gh release create v1.1.0 --notes-file ... <asset‌ها>`)

---

## فضایار۳۶۰ — نسخهٔ ۱.۱.۰ (ورود یکپارچه سازمانی + تم روز و شب + پرتیبل ویندوز)

### ✨ تازه‌های این نسخه
- 🔐 **ورود یکپارچه سازمانی (SSO/OIDC)**: دکمهٔ «ورود سازمانی» در صفحهٔ لاگین؛ جریان استاندارد OAuth2 Authorization Code (هم‌ساز با Keycloak و هر OIDC استاندارد)، تهیهٔ خودکار کاربر از پروفایل سازمانی، پیوند شناسهٔ بیرونی (`external_id`)، نقش پیش‌فرض/مدیر با متغیرهای `FAZAYAR_SSO_*` و ثبت کامل ورودها در ممیزی. در محیط دمو، ورود سازمانی شبیه‌سازی می‌شود تا بدون سرور هویت هم قابل آموزش باشد. صفحهٔ بازگشت: `#/sso/callback` با اعتبارسنجی `state`.
- 🌗 **تم روز و شب**: بازطراحی امروزی با متغیرهای CSS دو-تمی، کلید تغییر تم در نوار بالا و صفحهٔ ورود، نوار کناری با حالت فعال گرادیانی، topbar شیشه‌ای، دکمه‌ها/ورودی‌های جدید و ریمپ ابزارهای Tailwind در حالت شب — همهٔ صفحه‌ها در هر دو تم با مرورگر خودکار اسکرین‌شات و بازبینی شدند.
- 🪟 **بستهٔ پرتیبل ویندوز (x64)**: پایتون embeddable 3.12 + PostgreSQL 16.9 ویندوز + همهٔ وابستگی‌ها (ویل‌های win_amd64)؛ اجرا با دوبار کلیک روی `run.bat` روی پورت ۸۰۹۵ — بدون نصب پایتون، PostgreSQL یا Docker. داده‌ها در پوشهٔ `data/` ماندگار است. `stop.bat` هم برای خاموش‌کردن تمیز.

### 🚀 اجرا (ویندوز)
```bat
unzip fazayar360-portable-windows-x64-v1.1.0.zip
cd fazayar360-portable-windows-x64
run.bat
:: → http://localhost:8095
```

### 👤 کاربران نمونه
`admin / expert / edu_manager / lab_manager / facility / professor / student / rector` — گذرواژهٔ همه: `Faza360!`
+ دکمهٔ ورود سازمانی (کاربر دموی `sso.demo`).

### 🧪 کیفیت
- جریان کامل SSO دمو (لاگین سازمانی ← نشست ← داشبورد) با آزمون مرورگر تأیید شد.
- نقاط اتصال `/auth/sso/config`، `/auth/sso/demo` و `/auth/me` با curl سبز.
- همهٔ صفحه‌ها در دو تم اسکرین‌شات و بازبینی بصری شدند (`screenshots-v11/`).
- بستهٔ ویندوز از نظر ساختار (python.exe، initdb.exe، psycopg2، dist، CRLF و BOM در bat) به‌صورت خودکار راستی‌آزمایی شد؛ اجرای واقعی روی ویندوز به دلیل نبود ویندوز در محیط ساخت، تست نشده است — اگر خطایی دیدید لاگ‌ها در `data\initdb.log` و `data\pg.log` داخل بسته است.
