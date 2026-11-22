"""دستیار «فضای مناسب پیدا کن» — تبدیل متن فارسی به فیلتر؛ نتیجه فقط از داده واقعی، رزرو پس از تأیید کاربر."""
import datetime as dt
import re

from ..config import settings

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
WEEKDAY_ALTS = {"یک‌شنبه": 1, "دو شنبه": 2, "سه شنبه": 3, "چهار شنبه": 4, "پنج‌شنبه": 5, "پنج شنبه": 5, "جمعه": 6}

FEATURE_PATTERNS = [
    (r"نمایشگر|مانیتور|ال ای دی|LED", "display"),
    (r"ویدئو ?پروژکتور|پروژکتور|ودئوپروژکتور", "projector"),
    (r"تخته ?هوشمند|سمارت برد", "smart_board"),
    (r"وایت ?برد|وایتبرد|تخته سفید", "whiteboard"),
    (r"سیستم ?صوت|میکروفن|صوتی", "sound"),
    (r"اینترنت|وای ?فای|wifi", "internet"),
    (r"کامپیوتر|رایانه|پی سی|pc", "computer"),
    (r"دوربین|ضبط", "camera"),
]

TYPE_PATTERNS = [
    (r"آزمایشگاه|لابراتوار", "laboratory"),
    (r"کارگاه", "workshop"),
    (r"سایت رایانه|سایت کامپیوتر", "computer_site"),
    (r"سالن سمینار|سمینار|همایش", "seminar_hall"),
    (r"استودیو", "studio"),
    (r"مطالعه گروهی", "group_study"),
    (r"کلاس هوشمند", "smart_classroom"),
]

WORD_TO_NUM = {"یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
               "یازده": 11, "دوازده": 12, "نیم": 30, "ربع": 15}


def _fa_num(s: str) -> int | None:
    s = s.translate(FA_DIGITS).strip()
    if s.isdigit():
        return int(s)
    return WORD_TO_NUM.get(s)


def parse_request(text: str, today: dt.date | None = None) -> dict:
    """متن آزاد فارسی → فیلتر جست‌وجو. هرگز مرجع آزادبودن فضا نیست؛ فقط فیلتر می‌سازد."""
    if today is None:
        today = dt.date.today()
    t = text.translate(FA_DIGITS)
    filters: dict = {"feature_codes": [], "notes": []}

    # روز هفته / امروز / فردا
    target_date = None
    low = t.lower()
    if re.search(r"امروز", t):
        target_date = today
    elif re.search(r"فردا", t):
        target_date = today + dt.timedelta(days=1)
    else:
        for name, idx in [(w, i) for i, w in enumerate(WEEKDAYS)] + list(WEEKDAY_ALTS.items()):
            if name in t:
                delta = (idx - today.weekday() - 2) % 7  # python: دوشنبه=۰، شنبه=۵
                if delta == 0:
                    delta = 7
                target_date = today + dt.timedelta(days=delta)
                break

    # ساعت شروع
    start_time = None
    m = re.search(r"ساعت\s*(\d{1,2})(?::(\d{2}))?", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            start_time = f"{hour:02d}:{minute:02d}"
    if start_time is None:
        m = re.search(r"(\d{1,2}):(\d{2})", t)
        if m:
            start_time = f"{int(m.group(1)):02d}:{m.group(2)}"

    # مدت
    duration_min = None
    m = re.search(r"(\d+)\s*ساعت", t)
    if m:
        duration_min = int(m.group(1)) * 60
    if duration_min is None:
        m = re.search(r"(\d+)\s*دقیقه", t)
        if m:
            duration_min = int(m.group(1))
    if duration_min is None:
        for w, v in WORD_TO_NUM.items():
            if re.search(rf"\b{w}\s+ساعت", t):
                duration_min = v * 60
                break
    if duration_min is None and start_time:
        duration_min = 90

    # تعداد افراد
    attendees = None
    m = re.search(r"(\d+)\s*نفر", t)
    if m:
        attendees = int(m.group(1))
    if attendees is None:
        m = re.search(r"ظرفیت\s*(\d+)", t)
        if m:
            attendees = int(m.group(1))

    # امکانات (کد فرهنگ ویژگی)
    feature_codes = []
    for pat, code in FEATURE_PATTERNS:
        if re.search(pat, t):
            feature_codes.append(code)

    # نوع فضا
    space_types = []
    for pat, stype in TYPE_PATTERNS:
        if re.search(pat, t):
            space_types.append(stype)
    if space_types:
        filters["space_types"] = space_types

    # ساختمان مقصد (نزدیک دانشکده X / در دانشکده X)
    building_query = None
    m = re.search(r"(?:نزدیک|در|جوار|سمت)\s+(?:دانشکده|ساختمان|مرکز)\s+([\u0600-\u06FF ]+)", t)
    if m:
        building_query = m.group(1).strip()

    accessibility = bool(re.search(r"معیول|معلول|ویلچر|بدون پله|دسترس‌پذیر", t))

    filters.update({
        "target_date": target_date.isoformat() if target_date else None,
        "start_time": start_time,
        "duration_min": duration_min,
        "attendees": attendees,
        "feature_codes": feature_codes,
        "building_query": building_query,
        "accessibility_required": accessibility,
    })

    understood = []
    if target_date:
        understood.append("روز: " + target_date.strftime("%Y-%m-%d"))
    if start_time:
        understood.append("شروع: " + start_time)
    if duration_min:
        understood.append(f"مدت: {duration_min} دقیقه")
    if attendees:
        understood.append(f"ظرفیت: {attendees} نفر")
    if feature_codes:
        understood.append("امکانات: " + "، ".join(feature_codes))
    if building_query:
        understood.append("نزدیک: " + building_query)
    if accessibility:
        understood.append("مسیر بدون پله")

    missing = []
    if not target_date:
        missing.append("روز/تاریخ")
    if not start_time:
        missing.append("ساعت")
    if not attendees:
        missing.append("تعداد افراد")
    filters["understood"] = understood
    filters["missing"] = missing
    filters["original_text"] = text
    return filters
