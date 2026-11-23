"""داده مصرفی نمونه: درخواست‌های رزرو در وضعیت‌های مختلف، انسداد تعمیراتی، شواهد استفاده و مراجع همگام‌شده."""
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from .config import settings
from .models import (BookingOccurrence, MaintenanceBlock, OccurrenceStatus, RequestStatus,
                      Space, SpaceStatus, User, BlockStatus, BlockReason, UseType)
from .services import booking as booking_svc
from .services import sync as sync_svc

try:
    tz = ZoneInfo(settings.timezone)
except ZoneInfoNotFoundError:
    # ویندوز بدون بستهٔ tzdata — بازگشت به آفست ثابت تهران (+03:30)
    tz = timezone(timedelta(hours=3, minutes=30))


def _this_saturday(today) -> "datetime.date":
    # شنبه‌ی همین هفته (پس‌رو به شنبه): شنبه پایتون = weekday() == 5
    delta = (today.weekday() - 5) % 7
    return today - timedelta(days=delta)


def seed_usage(db: Session) -> None:
    if db.query(BookingOccurrence).count() > 0:
        return
    users = {u.username: u for u in db.query(User).all()}
    spaces = {s.code: s for s in db.query(Space).all()}
    today = datetime.now(tz).date()
    sat = _this_saturday(today)

    def day(week_offset: int, day_offset: int) -> str:
        return (sat + timedelta(weeks=week_offset, days=day_offset)).isoformat()

    expert = users["expert"]
    professor = users["professor"]
    student = users["student"]

    # ۱) کلاس هفتگی برنامه‌ریزی‌شده: مدار الکترونیک ۱ — کلاس هوشمند ۲۰۱، ۳۵ نفر
    r1 = booking_svc.create_request(db, {
        "use_type": UseType.scheduled_class.value,
        "title": "مدارهای الکترونیک ۱ - گروه ۱ (پایه‌یار: CO-4021)",
        "course_offer_ref": "CO-4021",
        "expected_attendees": 35, "enrollment_count": 28,
        "requested_space_id": spaces["ENG-201"].id,
        "layout": "سخنرانی",
        "series": {"weekday": 1, "start_time": "10:00", "end_time": "12:00",
                   "start_date": day(0, 1), "end_date": day(6, 1)},  # یکشنبه‌ها
    }, professor)
    r1.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r1.id, professor, "submit")
    booking_svc.approve(db, r1, expert, "هماهنگ با برنامه دانشکده")

    # ۲) کلاس هفتگی کم‌ظرفیت: هندسه تحلیلی ۶۰ نفره در کلاس ۳۵ نفره → سناریوی بهینه‌سازی
    r2 = booking_svc.create_request(db, {
        "use_type": UseType.scheduled_class.value,
        "title": "هندسه تحلیلی (پایه‌یار: CO-4024)",
        "course_offer_ref": "CO-4024",
        "expected_attendees": 30, "enrollment_count": 60,
        "requested_space_id": spaces["ENG-202"].id,
        "series": {"weekday": 2, "start_time": "08:00", "end_time": "10:00",
                   "start_date": day(0, 2), "end_date": day(6, 2)},  # دوشنبه‌ها
    }, professor)
    r2.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r2.id, professor, "submit")
    booking_svc.approve(db, r2, expert)

    # ۳) جلسه آزمایشگاه در انتظار بررسی: شیمی عمومی، ۲۴ نفر
    r3 = booking_svc.create_request(db, {
        "use_type": UseType.lab_session.value,
        "title": "جلسه آزمایشگاه شیمی عمومی (پایه‌یار: CO-4023)",
        "course_offer_ref": "CO-4023",
        "expected_attendees": 24, "enrollment_count": 24,
        "requested_space_id": spaces["LABC-CH"].id,
        "needs_lab_manager": True,
        "start_at": f"{day(0, 4)}T14:00:00+03:30", "end_at": f"{day(0, 4)}T17:00:00+03:30",  # چهارشنبه این هفته
    }, professor)
    r3.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r3.id, professor, "submit")

    # ۴) درخواست کلاس جبرانی از استاد در پیش‌نویس
    r4 = booking_svc.create_request(db, {
        "use_type": UseType.make_up_class.value,
        "title": "کلاس جبرانی ساختار داده‌ها",
        "expected_attendees": 32,
        "requested_space_id": spaces["ENG-104"].id,
        "start_at": f"{day(1, 3)}T16:00:00+03:30", "end_at": f"{day(1, 3)}T18:00:00+03:30",
    }, professor)

    # ۵) درخواست لغوشده
    r5 = booking_svc.create_request(db, {
        "use_type": UseType.workshop.value,
        "title": "کارگاه آماده‌سازی پایان‌نامه",
        "expected_attendees": 15,
        "requested_space_id": spaces["CONV-ROOM-A"].id,
        "start_at": f"{day(0, 5)}T09:00:00+03:30", "end_at": f"{day(0, 5)}T11:00:00+03:30",
    }, professor)
    r5.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r5.id, professor, "submit")
    booking_svc.approve(db, r5, expert)
    booking_svc.cancel(db, r5, professor, "هماهنگی لازم با مشاور فراهم نشد")

    # ۶) جلسه اجراشده با شواهد استفاده واقعی
    r6 = booking_svc.create_request(db, {
        "use_type": UseType.research_meeting.value,
        "title": "جلسه گروه پژوهشی پردازش سیگنال",
        "expected_attendees": 12,
        "requested_space_id": spaces["CONV-ROOM-A"].id,
        "start_at": f"{day(-1, 5)}T10:00:00+03:30", "end_at": f"{day(-1, 5)}T12:00:00+03:30",  # پنجشنبه هفته قبل
    }, professor)
    r6.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r6.id, professor, "submit")
    booking_svc.approve(db, r6, expert)
    occ6 = r6.occurrences[0]
    occ6.status = OccurrenceStatus.executed.value
    from .models import UsageObservation
    db.add(UsageObservation(space_id=spaces["CONV-ROOM-A"].id, occurrence_id=occ6.id,
                            observed_at=occ6.start_at, observed_headcount=9, source="manual",
                            observer_id=expert.id))
    db.add(UsageObservation(space_id=spaces["CONV-ROOM-A"].id, occurrence_id=occ6.id,
                            observed_at=occ6.start_at + timedelta(minutes=45), observed_headcount=8,
                            source="manual", observer_id=expert.id))

    # ۷) جلسه بدون حضور (no_show)
    r7 = booking_svc.create_request(db, {
        "use_type": UseType.scheduled_class.value,
        "title": "سمینار ناظران صنعت",
        "expected_attendees": 20,
        "requested_space_id": spaces["ENG-104"].id,
        "start_at": f"{day(-1, 2)}T14:00:00+03:30", "end_at": f"{day(-1, 2)}T16:00:00+03:30",
    }, professor)
    r7.status = RequestStatus.submitted.value
    booking_svc._add_action(db, r7.id, professor, "submit")
    booking_svc.approve(db, r7, expert)
    occ7 = r7.occurrences[0]
    occ7.status = OccurrenceStatus.no_show.value
    occ7.exception_note = "استاد حضور نیافت"

    # انسداد تعمیراتی فعال: کلاس ۱۰۵ مهندسی برای تعمیر پروژکتور
    blk = MaintenanceBlock(
        space_id=spaces["ENG-105"].id, reason_code=BlockReason.repair.value,
        title="تعمیر پروژکتور سقفی", description="تعویض لامپ و سرویس سیستم نمایش",
        reporter_id=users["facility"].id, status=BlockStatus.active.value,
        start_at=datetime.fromisoformat(f"{day(0, 2)}T07:00:00+03:30"),
        end_at=datetime.fromisoformat(f"{day(0, 3)}T21:00:00+03:30"),
    )
    db.add(blk)
    db.flush()
    from .services import conflict as cf
    cf.block_allocation(db, blk, users["facility"])

    # گزارش خرابی عمومی (از QR) در انتظار بررسی
    db.add(MaintenanceBlock(
        space_id=spaces["SCI-112"].id, reason_code=BlockReason.repair.value,
        title="صندلی شماره ۱۲ شکسته است", reporter_name="گزارش از طریق QR",
        status=BlockStatus.reported.value,
        start_at=datetime.now(tz), end_at=datetime.now(tz) + timedelta(days=1),
    ))

    # همگام‌سازی نمونه مراجع زیست‌بوم (پایه‌یار۳۶۰)
    sync_svc.demo_pull_courses(db)

    # خروجی صندوق رویداد نمونه
    booking_svc.push_outbox(db, "space.blocked", {"space_code": "ENG-105", "reason": "repair"})
    db.flush()
