"""داده نمونه واقع‌نما برای راه‌اندازی اولیه (فقط وقتی پایگاه داده خالی است)."""
import json
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from .core.security import hash_password
from .config import settings
from .models import (AvailabilityRule, Building, Campus, EquipmentAsset, EquipmentPool,
                      EquipmentType, Feature, Floor, Space, SpaceEquipment, SpaceFeature,
                      SpaceLayout, SpaceStatus, SpaceType, User)

tz = ZoneInfo(settings.timezone)


def seed_if_empty(db: Session) -> bool:
    if db.query(Campus).count() > 0:
        return False
    _seed(db)
    return True


def _slug() -> str:
    return uuid.uuid4().hex[:16]


def _seed(db: Session) -> None:
    # ── پردیس و ساختمان‌ها ─────────────────────────────────────────────
    campus_main = Campus(code="MAIN", name="پردیس مرکزی", address="خیابان دانشگاه، سمت شرقی")
    campus_north = Campus(code="NORTH", name="پردیس شمالی", address="بزرگراه شمال، کیلومتر ۳")
    db.add_all([campus_main, campus_north])
    db.flush()

    b_eng = Building(campus_id=campus_main.id, code="ENG", name="دانشکده مهندسی برق و کامپیوتر",
                     responsible_unit="معاونت ساختمان مهندسی")
    b_sci = Building(campus_id=campus_main.id, code="SCI", name="دانشکده علوم پایه",
                     responsible_unit="معاونت ساختمان علوم")
    b_lab = Building(campus_id=campus_main.id, code="LABC", name="ساختمان آزمایشگاه‌های مرکزی",
                     responsible_unit="مرکز آزمایشگاه‌ها")
    b_conv = Building(campus_id=campus_north.id, code="CONV", name="مرکز همایش‌ها و آموزش‌های آزاد",
                      responsible_unit="اداره همایش‌ها")
    db.add_all([b_eng, b_sci, b_lab, b_conv])
    db.flush()

    floors = {}
    for b in [b_eng, b_sci, b_lab]:
        for n in [1, 2, 3]:
            f = Floor(building_id=b.id, number=n, name=f"طبقه {n}")
            db.add(f)
            floors[(b.code, n)] = f
    f_conv1 = Floor(building_id=b_conv.id, number=1, name="همکف")
    db.add(f_conv1)
    floors[(b_conv.code, 1)] = f_conv1
    db.flush()

    # ── فرهنگ ویژگی‌ها ────────────────────────────────────────────────
    features = {}
    for code, name, cat in [
        ("display", "نمایشگر", "display"), ("projector", "ویدئوپروژکتور", "display"),
        ("smart_board", "تخته هوشمند", "board"), ("whiteboard", "تخته وایت‌برد", "board"),
        ("sound", "سیستم صوتی", "specialized"), ("internet", "اینترنت پرسرعت", "network"),
        ("power_per_seat", "پریز برق هر میز", "power"), ("ac", "تهویه مطبوع", "other"),
        ("recording", "دوربین ضبط جلسه", "specialized"),
    ]:
        features[code] = Feature(code=code, name=name, category=cat)
    db.add_all(features.values())
    db.flush()

    # ── انواع تجهیزات ────────────────────────────────────────────────
    eq_types = {}
    for code, name, cat in [
        ("oscope", "اسیلوسکوپ", "fixed"), ("psu", "منبع تغذیه آزمایشگاهی", "fixed"),
        ("hood", "هود شیمیایی", "fixed"), ("microscope", "میکروسکوپ", "fixed"),
        ("desktop", "کامپیوتر رومیزی", "fixed"),
        ("laptop", "لپ‌تاپ قابل‌حمل", "portable"), ("camera", "دوربین قابل‌حمل", "portable"),
        ("mproj", "پروژکتور سیار", "portable"),
    ]:
        eq_types[code] = EquipmentType(code=code, name=name, category=cat)
    db.add_all(eq_types.values())
    db.flush()

    # ── فضاها ─────────────────────────────────────────────────────────
    def layout_rows(space_id: int, variants: list[tuple[str, int, bool]]):
        return [SpaceLayout(space_id=space_id, name=n, capacity=c, is_default=d,
                            seats_count=c, tables_count=max(c // 2, 1) if n == "کارگاهی" else c)
                for (n, c, d) in variants]

    spaces: list[Space] = []

    def add_space(code, name, stype, building, floor_no, area, safe_cap, layouts,
                  feature_codes, extra=None):
        f = floors[(building.code, floor_no)]
        sp = Space(code=code, name=name, space_type=stype, status=SpaceStatus.active.value,
                   campus_id=building.campus_id, building_id=building.id, floor_id=f.id,
                   area_m2=area, safe_capacity=safe_cap,
                   responsible_unit=building.responsible_unit, responsible_person="دفتر ساختمان",
                   responsible_contact="داخلی ۲۱۰", min_prep_minutes=10, min_cleanup_minutes=10,
                   public_slug=_slug(), map_x=None, map_y=None,
                   description=f"فضای آموزشی {name} در {building.name}")
        if extra:
            for k, v in extra.items():
                setattr(sp, k, v)
        db.add(sp)
        db.flush()
        sp.layouts = layout_rows(sp.id, layouts)
        sp.space_features = [SpaceFeature(space_id=sp.id, feature_id=features[c].id) for c in feature_codes]
        spaces.append(sp)
        return sp

    # دانشکده مهندسی - طبقه ۱ و ۲
    sp1 = add_space("ENG-104", "کلاس ۱۰۴ مهندسی", SpaceType.general_classroom.value, b_eng, 1, 48, 45,
                    [("سخنرانی", 45, True), ("کارگاهی", 24, False)], ["projector", "whiteboard", "internet", "power_per_seat"],
                    {"map_x": 40, "map_y": 60, "map_w": 150, "map_h": 90})
    sp2 = add_space("ENG-105", "کلاس ۱۰۵ مهندسی", SpaceType.general_classroom.value, b_eng, 1, 48, 45,
                    [("سخنرانی", 45, True), ("کارگاهی", 24, False)], ["projector", "whiteboard", "internet"],
                    {"map_x": 210, "map_y": 60, "map_w": 150, "map_h": 90})
    sp3 = add_space("ENG-201", "کلاس هوشمند ۲۰۱", SpaceType.smart_classroom.value, b_eng, 2, 62, 55,
                    [("سخنرانی", 55, True), ("کارگاهی", 30, False), ("آزمون", 36, False)],
                    ["display", "smart_board", "sound", "internet", "power_per_seat", "recording"],
                    {"map_x": 40, "map_y": 170, "map_w": 170, "map_h": 100})
    sp4 = add_space("ENG-202", "کلاس ۲۰۲ مهندسی", SpaceType.general_classroom.value, b_eng, 2, 48, 45,
                    [("سخنرانی", 35, True), ("آزمون", 28, False)], ["projector", "internet"],
                    {"map_x": 230, "map_y": 170, "map_w": 150, "map_h": 90})
    sp5 = add_space("ENG-SITE1", "سایت رایانه ۱ مهندسی", SpaceType.computer_site.value, b_eng, 2, 70, 30,
                    [("سخنرانی", 30, True)], ["display", "internet", "power_per_seat"],
                    {"map_x": 420, "map_y": 170, "map_w": 180, "map_h": 110})
    sp6 = add_space("ENG-WORK", "کارگاه برق و الکترونیک", SpaceType.workshop.value, b_eng, 1, 90, 28,
                    [("کارگاهی", 28, True)], ["power_per_seat", "internet"],
                    {"needs_lab_manager": True, "map_x": 420, "map_y": 60, "map_w": 180, "map_h": 110})

    # دانشکده علوم - طبقه ۱ و ۲
    sp7 = add_space("SCI-112", "کلاس ۱۱۲ علوم", SpaceType.general_classroom.value, b_sci, 1, 50, 40,
                    [("سخنرانی", 40, True), ("آزمون", 30, False)], ["projector", "whiteboard"],
                    {"map_x": 40, "map_y": 60, "map_w": 160, "map_h": 95})
    sp8 = add_space("SCI-213", "کلاس ۲۱۳ علوم", SpaceType.general_classroom.value, b_sci, 2, 55, 42,
                    [("سخنرانی", 42, True)], ["display", "internet"],
                    {"has_step_free_access": True, "has_elevator_access": True,
                     "accessibility_notes": "دسترسی با آسانسور شرقی، ورودی بدون پله",
                     "map_x": 220, "map_y": 170, "map_w": 160, "map_h": 95})
    sp9 = add_space("SCI-STUDIO", "استودیو تولید محتوای آموزشی", SpaceType.studio.value, b_sci, 2, 60, 12,
                    [("سخنرانی", 12, True)], ["sound", "recording", "internet", "ac"],
                    {"needs_lab_manager": True, "map_x": 400, "map_y": 170, "map_w": 170, "map_h": 110})

    # آزمایشگاه‌های مرکزی
    sp10 = add_space("LABC-CH", "آزمایشگاه شیمی عمومی", SpaceType.laboratory.value, b_lab, 1, 95, 24,
                     [("کارگاهی", 24, True)], ["power_per_seat", "internet"],
                     {"needs_lab_manager": True,
                      "description": "۱۲ ایستگاه آزمایش؛ هر ایستگاه حداکثر ۲ نفر. استفاده فقط با آموزش ایمنی.",
                      "allowed_group_names": "شیمی,مهندسی شیمی,پزشکی"})
    sp11 = add_space("LABC-EE", "آزمایشگاه الکترونیک", SpaceType.laboratory.value, b_lab, 2, 85, 24,
                     [("کارگاهی", 24, True)], ["power_per_seat"],
                     {"needs_lab_manager": True, "description": "۱۲ ایستگاه دو نفره؛ تجهیزات اندازه‌گیری کالیبره‌شده.",
                      "allowed_group_names": "مهندسی برق,مهندسی کامپیوتر"})
    sp12 = add_space("LABC-PC", "آزمایشگاه فیزیولوژی", SpaceType.laboratory.value, b_lab, 3, 80, 16,
                     [("کارگاهی", 16, True)], ["power_per_seat"],
                     {"needs_lab_manager": True, "description": "۸ ایستگاه دو نفره."})

    # سالن سمینار و مطالعه
    sp13 = add_space("CONV-HALL", "سالن سمینار اصلی", SpaceType.seminar_hall.value, b_conv, 1, 240, 80,
                     [("سخنرانی", 80, True), ("کارگاهی", 40, False), ("آزمون", 30, False)],
                     ["display", "sound", "recording", "internet", "ac"],
                     {"has_step_free_access": True, "has_elevator_access": True, "min_prep_minutes": 30,
                      "min_cleanup_minutes": 30, "map_x": 60, "map_y": 80, "map_w": 320, "map_h": 180})
    sp14 = add_space("CONV-ROOM-A", "اتاق جلسات A", SpaceType.group_study.value, b_conv, 1, 40, 16,
                     [("کارگاهی", 16, True)], ["display", "internet"], {"map_x": 420, "map_y": 90, "map_w": 130, "map_h": 90})
    sp15 = add_space("ENG-203", "کلاس ۲۰۳ مهندسی", SpaceType.general_classroom.value, b_eng, 2, 48, 45,
                     [("سخنرانی", 45, True), ("کارگاهی", 24, False)], ["projector", "whiteboard", "internet"],
                     {"map_x": 40, "map_y": 290, "map_w": 150, "map_h": 90})
    sp16 = add_space("SCI-STUDY", "فضای مطالعه گروهی علوم", SpaceType.group_study.value, b_sci, 1, 45, 18,
                     [("کارگاهی", 18, True)], ["internet", "whiteboard"],
                     {"map_x": 220, "map_y": 60, "map_w": 150, "map_h": 95})
    db.flush()

    # تجهیزات ثابت/شمارشی فضاها (ظرفیت تجهیزاتی)
    def add_space_eq(space, type_code, qty, per_unit=None):
        db.add(SpaceEquipment(space_id=space.id, type_id=eq_types[type_code].id,
                              quantity=qty, per_unit_capacity=per_unit))

    add_space_eq(sp10, "hood", 4)
    add_space_eq(sp10, "microscope", 12, 2)     # ۱۲ ایستگاه × ۲ نفر = ۲۴
    add_space_eq(sp11, "oscope", 12, 2)
    add_space_eq(sp11, "psu", 12, 2)
    add_space_eq(sp12, "microscope", 8, 2)
    add_space_eq(sp5, "desktop", 30, 1)
    db.flush()

    # تجهیزات قابل‌حمل با شناسه مستقل + استخر شمارشی
    cam = EquipmentAsset(type_id=eq_types["camera"].id, asset_tag="AM-10231", name="دوربین Sony ZV-E10",
                         model="ZV-E10", serial_number="SN-88213", status="operational",
                         bookable_independently=True, responsible_person="انبار تجهیزات", location_space_id=sp9.id)
    db.add(cam)
    db.add(EquipmentPool(type_id=eq_types["laptop"].id, name="استخر لپ‌تاپ دانشجویی", total_quantity=20,
                         home_space_id=sp5.id))
    db.add(EquipmentAsset(type_id=eq_types["mproj"].id, asset_tag="AM-10445", name="پروژکتور سیار Epson",
                          status="operational", bookable_independently=True, location_space_id=None))
    db.flush()

    # قواعد ساعات مجاز پیش‌فرض (سراسری): شنبه تا چهارشنبه ۷–۲۱، پنجشنبه ۸–۱۴
    for wd in range(5):
        db.add(AvailabilityRule(space_id=None, weekday=wd, start_time=time(7, 0), end_time=time(21, 0)))
    db.add(AvailabilityRule(space_id=None, weekday=5, start_time=time(8, 0), end_time=time(14, 0)))

    # ── کاربران نقش‌ها ───────────────────────────────────────────────
    demo_pw = hash_password("Faza360!")
    users = [
        User(username="admin", password_hash=demo_pw, display_name="مدیر سامانه", role="sys_admin"),
        User(username="expert", password_hash=demo_pw, display_name="سارا کارشناس آموزش", role="education_expert"),
        User(username="edu_manager", password_hash=demo_pw, display_name="دکتر رضایی - مدیر آموزشی", role="education_manager"),
        User(username="lab_manager", password_hash=demo_pw, display_name="مهندس موسوی - مسئول آزمایشگاه",
             role="lab_manager", faculty="مهندسی برق", scope_building_id=b_lab.id),
        User(username="facility", password_hash=demo_pw, display_name="مهندس کاظمی - تأسیسات", role="facility_manager"),
        User(username="professor", password_hash=demo_pw, display_name="دکتر احمدی - استاد", role="professor",
             faculty="مهندسی برق"),
        User(username="student", password_hash=demo_pw, display_name="علی دانشجو", role="student"),
        User(username="rector", password_hash=demo_pw, display_name="مدیر دانشگاه", role="university_admin"),
    ]
    db.add_all(users)
    db.flush()
    return
