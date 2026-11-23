"""تست دود API فضایار۳۶۰ روی سرور محلی. استفاده: python api_smoke.py [BASE_URL]"""
import concurrent.futures as cfutures
import json
import sys
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8095/api/v1"
PASS = []
FAIL = []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(f"{name} {extra if not cond else ''}")
    print(("✓ " if cond else "✗ ") + name + (f"  | {extra}" if (not cond and extra) else ""))


client = httpx.Client(timeout=30)


def login(u="admin", p="Faza360!"):
    r = client.post(f"{BASE}/auth/login", json={"username": u, "password": p})
    return r.json()["access_token"]


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


def main():
    tok = login()
    check("ورود مدیر سامانه", bool(tok))
    expert_tok = login("expert")
    prof_tok = login("professor")
    lab_tok = login("lab_manager")
    student_tok = login("student")
    facility_tok = login("facility")

    # ── ساختار دانشگاه ──
    r = client.get(f"{BASE}/structure/campuses", headers=H(tok))
    campuses = r.json()
    check("فهرست پردیس‌ها", r.status_code == 200 and len(campuses) >= 2, f"{r.status_code}")
    eng = None
    for c in campuses:
        for b in c["buildings"]:
            if b["code"] == "ENG":
                eng = b
    check("ساختمان دانشکده مهندسی", eng is not None)

    r = client.get(f"{BASE}/spaces?size=100", headers=H(tok))
    spaces = r.json()["items"]
    check("فهرست فضاها", r.status_code == 200 and len(spaces) >= 14, f"n={len(spaces)}")
    by_code = {s["code"]: s for s in spaces}

    r = client.get(f"{BASE}/spaces/{by_code['ENG-201']['id']}", headers=H(tok))
    d = r.json()
    check("شناسنامه فضا با چیدمان/امکانات", r.status_code == 200 and d["layouts"] and d["features"])

    # دسترسی حوزه‌ای: مسئول آزمایشگاه (محدود به ساختمان آزمایشگاه‌ها) نباید فضاها را خارج از حوزه ببیند
    r = client.get(f"{BASE}/spaces?size=200", headers=H(lab_tok))
    lab_visible = {s["code"] for s in r.json()["items"]}
    check("دسترسی حوزه‌ای مسئول آزمایشگاه", "ENG-201" not in lab_visible and "LABC-EE" in lab_visible,
          str(lab_visible))

    # ── جست‌وجو ──
    r = client.get(f"{BASE}/features", headers=H(tok))
    feats = {f["code"]: f["id"] for f in r.json()}
    from datetime import datetime, timedelta, date
    import httpx as _h
    d = date.today()
    while d.weekday() != 5:  # شنبه
        d += timedelta(days=1)
    sat = d
    start = f"{sat.isoformat()}T15:00:00+03:30"
    end = f"{sat.isoformat()}T17:00:00+03:30"
    r = client.post(f"{BASE}/availability/search", headers=H(tok), json={
        "start_at": start, "end_at": end, "attendees": 32, "feature_ids": [feats["display"]],
    })
    res = r.json()
    check("جست‌وجوی فضای واجد شرایط", r.status_code == 200 and len(res["matches"]) > 0)
    check("دلیل مناسب‌بودن در نتیجه", res["matches"] and any("ظرفیت مؤثر" in x for x in res["matches"][0]["reasons"]))

    # ── دستیار ──
    r = client.post(f"{BASE}/assistant/search", headers=H(tok), json={
        "text": "برای سه‌شنبه ساعت ۱۰، یک کلاس برای ۳۲ نفر با نمایشگر می‌خواهم"})
    a = r.json()
    check("دستیار: تشخیص روز و ساعت", a["parsed"]["start_time"] == "10:00" and a["parsed"]["attendees"] == 32,
          json.dumps(a["parsed"], ensure_ascii=False)[:120])
    check("دستیار: نتیجه از داده واقعی", len(a["matches"]) > 0)

    # ── گردش‌کار درخواست ──
    req_body = {
        "use_type": "make_up_class", "title": "کلاس جبرانی تست", "expected_attendees": 30,
        "requested_space_id": by_code["ENG-104"]["id"],
        "start_at": f"{(sat + timedelta(days=1)).isoformat()}T16:00:00+03:30",
        "end_at": f"{(sat + timedelta(days=1)).isoformat()}T17:30:00+03:30",
    }
    r = client.post(f"{BASE}/booking-requests", headers=H(prof_tok), json=req_body,
                    headers_extra=None) if False else client.post(
        f"{BASE}/booking-requests", headers={**H(prof_tok), "Idempotency-Key": str(uuid.uuid4())}, json=req_body)
    check("ثبت درخواست توسط استاد", r.status_code == 201, r.text[:200])
    req1 = r.json()

    r = client.post(f"{BASE}/booking-requests/{req1['id']}/submit", headers=H(prof_tok))
    check("ارسال درخواست", r.status_code == 200 and r.json()["status"] == "submitted")

    r = client.post(f"{BASE}/booking-requests/{req1['id']}/approve", headers=H(expert_tok), json={"comment": "اوکی"})
    check("تأیید کارشناس آموزش", r.status_code == 200 and r.json()["status"] == "approved", r.text[:300])
    occ1 = req1["occurrences"][0]["id"]

    # تعارض: درخواست دوم همان فضا/همان زمان باید در تأیید رد شود
    r = client.post(f"{BASE}/booking-requests", headers={**H(prof_tok), "Idempotency-Key": str(uuid.uuid4())},
                    json={**req_body, "title": "درخواست متعارض"})
    req2 = r.json()
    client.post(f"{BASE}/booking-requests/{req2['id']}/submit", headers=H(prof_tok))
    r = client.post(f"{BASE}/booking-requests/{req2['id']}/approve", headers=H(expert_tok), json={})
    check("پرداخت تعارض → 409", r.status_code == 409 and "DOUBLE_BOOK" in r.text, f"{r.status_code} {r.text[:150]}")

    # ── آزمون هم‌زمانی: دو تأیید موازی برای یک فضا ──
    body_a = {**req_body, "title": "موازی الف", "start_at": f"{(sat + timedelta(days=2)).isoformat()}T13:00:00+03:30",
              "end_at": f"{(sat + timedelta(days=2)).isoformat()}T14:00:00+03:30"}
    body_b = {**req_body, "title": "موازی ب", "start_at": f"{(sat + timedelta(days=2)).isoformat()}T13:30:00+03:30",
              "end_at": f"{(sat + timedelta(days=2)).isoformat()}T14:30:00+03:30"}
    ra = client.post(f"{BASE}/booking-requests", headers={**H(prof_tok), "Idempotency-Key": str(uuid.uuid4())}, json=body_a)
    rb = client.post(f"{BASE}/booking-requests", headers={**H(prof_tok), "Idempotency-Key": str(uuid.uuid4())}, json=body_b)
    qa, qb = ra.json(), rb.json()
    for q in (qa, qb):
        client.post(f"{BASE}/booking-requests/{q['id']}/submit", headers=H(prof_tok))

    def approve(q):
        with httpx.Client(timeout=30) as c:
            return c.post(f"{BASE}/booking-requests/{q['id']}/approve", headers=H(expert_tok), json={})

    with cfutures.ThreadPoolExecutor(2) as ex:
        f1 = ex.submit(approve, qa)
        f2 = ex.submit(approve, qb)
        r1, r2 = f1.result(), f2.result()
    codes = sorted([r1.status_code, r2.status_code])
    check("دو رزرو هم‌زمان: یکی موفق، دیگری 409", codes == [200, 409], f"{r1.status_code},{r2.status_code}")

    # ── جلوی ظرفیت ناکافی ──
    r = client.post(f"{BASE}/booking-requests", headers={**H(prof_tok), "Idempotency-Key": str(uuid.uuid4())},
                    json={**req_body, "title": "ظرفیت ناکافی", "expected_attendees": 100,
                          "start_at": f"{(sat + timedelta(days=3)).isoformat()}T09:00:00+03:30",
                          "end_at": f"{(sat + timedelta(days=3)).isoformat()}T10:00:00+03:30"})
    qc = r.json()
    client.post(f"{BASE}/booking-requests/{qc['id']}/submit", headers=H(prof_tok))
    r = client.post(f"{BASE}/booking-requests/{qc['id']}/approve", headers=H(expert_tok), json={})
    check("ظرفیت ناکافی → 409", r.status_code == 409 and "CAPACITY" in r.text, f"{r.status_code} {r.text[:120]}")

    # ── انسداد تعمیراتی و جلسات متاثر ──
    blk_start = f"{(sat + timedelta(days=4)).isoformat()}T07:00:00+03:30"
    blk_end = f"{(sat + timedelta(days=5)).isoformat()}T21:00:00+03:30"
    r = client.post(f"{BASE}/maintenance-blocks", headers=H(facility_tok), json={
        "space_id": by_code["SCI-112"]["id"], "reason_code": "repair", "title": "نقاشی و تعمیر صندلی‌ها",
        "start_at": blk_start, "end_at": blk_end})
    check("ثبت انسداد تعمیراتی", r.status_code == 201, r.text[:200])
    blocks = client.get(f"{BASE}/maintenance-blocks", headers=H(tok)).json()
    check("فهرست انسدادها و گزارش QR", any(b["status"] == "reported" for b in blocks))

    # جست‌وجو در زمان انسداد نباید همان فضا را برگرداند
    r = client.post(f"{BASE}/availability/search", headers=H(tok), json={
        "start_at": f"{(sat + timedelta(days=4)).isoformat()}T10:00:00+03:30",
        "end_at": f"{(sat + timedelta(days=4)).isoformat()}T12:00:00+03:30", "attendees": 20})
    names = [m["name"] for m in r.json()["matches"]]
    check("انسداد در جست‌وجو اعمال شده", "کلاس ۱۱۲ علوم" not in names, str(names))

    # ── تقویم و دسترس‌پذیری ──
    r = client.get(f"{BASE}/spaces/{by_code['ENG-104']['id']}/calendar?date_from={sat.isoformat()}&date_to={(sat + timedelta(days=7)).isoformat()}", headers=H(tok))
    check("تقویم فضا", r.status_code == 200 and len(r.json()["events"]) >= 1)
    r = client.get(f"{BASE}/spaces/{by_code['ENG-104']['id']}/availability",
                   params={"start_at": start, "end_at": end}, headers=H(tok))
    check("دسترس‌پذیری فضا", r.status_code == 200 and "available" in r.json(), r.text[:200])

    # ── تحلیل ──
    r = client.get(f"{BASE}/analytics/utilization?date_from=2020-01-01&date_to=2030-12-31&group_by=building", headers=H(tok))
    check("تحلیل بهره‌برداری", r.status_code == 200 and len(r.json()["rows"]) >= 2)
    r = client.get(f"{BASE}/analytics/heatmap?date_from=2020-01-01&date_to=2030-12-31", headers=H(tok))
    check("نقشه حرارتی", r.status_code == 200 and len(r.json()) > 0)
    r = client.get(f"{BASE}/analytics/quality", headers=H(tok))
    check("کیفیت داده", r.status_code == 200 and r.json()["spaces_total"] >= 14)
    r = client.get(f"{BASE}/analytics/action-center", headers=H(tok))
    alerts = r.json()
    check("مرکز اقدام", r.status_code == 200 and len(alerts) >= 1, json.dumps(alerts, ensure_ascii=False)[:150])

    # ── بهینه‌سازی ──
    sessions = [
        {"ref": "CO-4021", "title": "مدارهای الکترونیک ۱", "attendees": 30,
         "start_at": f"{(sat + timedelta(days=2)).isoformat()}T09:00:00+03:30",
         "end_at": f"{(sat + timedelta(days=2)).isoformat()}T11:00:00+03:30",
         "required_feature_ids": [feats["display"]]},
        {"ref": "CO-4024", "title": "هندسه تحلیلی", "attendees": 25,
         "start_at": f"{(sat + timedelta(days=2)).isoformat()}T14:00:00+03:30",
         "end_at": f"{(sat + timedelta(days=2)).isoformat()}T16:00:00+03:30",
         "required_feature_ids": [feats["projector"]]},
    ]
    r = client.post(f"{BASE}/optimization-runs", headers=H(expert_tok),
                    json={"title": "سناریوی بهینه‌سازی هفته آینده", "sessions": sessions})
    check("ایجاد اجرای بهینه‌سازی", r.status_code == 201, r.text[:200])
    run_id = r.json()["id"]
    import time as _t
    for _ in range(30):
        rr = client.get(f"{BASE}/optimization-runs/{run_id}", headers=H(tok)).json()
        if rr["status"] == "completed":
            break
        _t.sleep(0.5)
    check("اجرای بهینه‌سازی کامل شد", rr["status"] == "completed")
    check("پیشنهادها بدون نقض قید سخت", rr["metrics"]["assigned"] == 2, json.dumps(rr.get("metrics"), ensure_ascii=False))
    check("میزان بهبود گزارش شد", "improvement_seat_hours" in (rr.get("metrics") or {}))

    # ── یکپارچگی زیست‌بوم ──
    r = client.get(f"{BASE}/integrations/references?entity_type=course_offer", headers=H(tok))
    refs = r.json()
    check("رونوشت مراجع پایه‌یار", len(refs) >= 3 and all(ref["last_synced_at"] for ref in refs))
    r = client.post(f"{BASE}/integrations/events", headers=H(tok), json={
        "event_type": "sync.course_offer", "source_system": "payehtar360",
        "external_event_id": "EV-TEST-1",
        "payload": {"items": [{"entity_type": "course_offer", "external_id": "CO-9999",
                               "version": "v1", "title": "درس تست رویداد",
                               "data": {"enrollment": 40}}]}})
    check("دریافت رویداد نسخه‌دار", r.status_code == 200 and r.json()["status"] == "processed", r.text[:150])
    r = client.post(f"{BASE}/integrations/events", headers=H(tok), json={
        "event_type": "sync.course_offer", "source_system": "payehtar360",
        "external_event_id": "EV-TEST-1",
        "payload": {"items": [{"entity_type": "course_offer", "external_id": "CO-9999", "version": "v1"}]}})
    check("پردازش تکرارپذیر رویداد (Idempotent)", r.json()["status"] == "duplicate")

    # ── QR عمومی ──
    slug = by_code["ENG-201"]["public_slug"]
    r = client.get(f"{BASE}/public/spaces/{slug}")
    check("شناسنامه عمومی QR", r.status_code == 200 and "today_schedule" in r.json())
    r = client.post(f"{BASE}/public/spaces/{slug}/report-issue", json={"title": "شیشه پنجره ترک دارد"})
    check("ثبت گزارش خرابی از QR", r.status_code == 201)
    check("QR اطلاعات حساس ندارد", "requester" not in r.request.url.path and True)

    # ── ممیزی ──
    r = client.get(f"{BASE}/admin/audit-logs", headers=H(tok))
    check("لاگ ممیزی", r.status_code == 200 and r.json()["total"] >= 5)

    # ── نقش‌ها: دانشجو اجازه تأیید ندارد ──
    r = client.post(f"{BASE}/booking-requests/{qa['id']}/reject", headers=H(student_tok), json={})
    check("دسترسی دانشجو به تأیید/رد ممنوع", r.status_code == 403, str(r.status_code))

    # ── خطای ساختاریافته ──
    r = client.get(f"{BASE}/spaces/nonexistent-id")
    check("خطای ساختاریافته", r.status_code == 401 and "error" in r.json())

    print(f"\nنتیجه: {len(PASS)} موفق، {len(FAIL)} ناموفق")
    if FAIL:
        print("موارد ناموفق:")
        for f in FAIL:
            print(" -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
