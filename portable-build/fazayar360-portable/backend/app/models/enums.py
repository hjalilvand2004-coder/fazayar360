from enum import Enum


class SpaceType(str, Enum):
    general_classroom = "general_classroom"   # کلاس عمومی
    smart_classroom = "smart_classroom"       # کلاس هوشمند
    laboratory = "laboratory"                 # آزمایشگاه
    workshop = "workshop"                     # کارگاه
    computer_site = "computer_site"           # سایت رایانه
    seminar_hall = "seminar_hall"             # سالن سمینار
    studio = "studio"                         # استودیو آموزشی
    group_study = "group_study"               # فضای مطالعه گروهی


class SpaceStatus(str, Enum):
    active = "active"           # فعال
    limited = "limited"         # محدود
    under_repair = "under_repair"  # در تعمیر
    inactive = "inactive"       # غیرفعال
    retired = "retired"         # بازنشسته


class EquipmentCategory(str, Enum):
    fixed = "fixed"        # ثابت
    portable = "portable"  # قابل‌حمل
    consumable = "consumable"  # مصرفی


class EquipmentStatus(str, Enum):
    operational = "operational"
    needs_service = "needs_service"
    broken = "broken"
    retired = "retired"


class UseType(str, Enum):
    scheduled_class = "scheduled_class"   # کلاس برنامه‌ریزی‌شده
    make_up_class = "make_up_class"       # کلاس جبرانی
    lab_session = "lab_session"           # جلسه آزمایشگاه
    workshop = "workshop"                 # کارگاه آموزشی
    exam = "exam"                         # آزمون
    research_meeting = "research_meeting" # جلسه پژوهشی آموزشی


class RequestStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"
    completed = "completed"
    no_show = "no_show"


class OccurrenceStatus(str, Enum):
    scheduled = "scheduled"
    executed = "executed"
    cancelled = "cancelled"
    moved = "moved"
    no_show = "no_show"


class AllocationKind(str, Enum):
    booking = "booking"
    maintenance = "maintenance"
    hold = "hold"          # نگهداشت موقت با انقضا


class AllocationStatus(str, Enum):
    active = "active"
    released = "released"


class BlockStatus(str, Enum):
    reported = "reported"    # گزارش خرابی ثبت‌شده (نیازمند بررسی)
    active = "active"        # انسداد فعال
    resolved = "resolved"
    rejected = "rejected"


class BlockReason(str, Enum):
    repair = "repair"                # تعمیر
    preparation = "preparation"      # آماده‌سازی
    safety = "safety"                # ایمنی
    event = "event"                  # رویداد خاص
    other = "other"


class UserRole(str, Enum):
    sys_admin = "sys_admin"                # مدیر سامانه
    education_expert = "education_expert"  # کارشناس آموزش
    education_manager = "education_manager"  # مدیر آموزشی
    lab_manager = "lab_manager"            # مسئول آزمایشگاه
    facility_manager = "facility_manager"  # مسئول ساختمان/تأسیسات
    professor = "professor"                # استاد
    student = "student"                    # دانشجو
    university_admin = "university_admin"  # مدیر دانشگاه
    service = "service"                    # کاربر سرویس (API)


class SyncStatus(str, Enum):
    fresh = "fresh"
    stale = "stale"
    error = "error"


class OptimRunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class SolutionStatus(str, Enum):
    optimal = "optimal"
    feasible = "feasible"
    partial = "partial"       # بخشی از جلسات بدون پاسخ مجاز
    no_solution = "no_solution"


class AssignStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    applied = "applied"
    failed = "failed"
    rejected = "rejected"
