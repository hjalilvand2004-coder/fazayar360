/** قالب‌بندی فارسی: تاریخ شمسی با Intl، ارقام فارسی، ساعت */

export const FA_WEEKDAYS = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"];

export function toFaDigits(s: string | number): string {
  return String(s).replace(/\d/g, (d) => "۰۱۲۳۴۵۶۷۸۹"[Number(d)]);
}

export function jalali(d: string | Date | undefined | null): string {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  if (isNaN(date.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", { year: "numeric", month: "2-digit", day: "2-digit" }).format(date);
  } catch {
    return date.toISOString().slice(0, 10);
  }
}

export function jalaliFull(d: string | Date | undefined | null): string {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  try {
    return new Intl.DateTimeFormat("fa-IR", { dateStyle: "full" }).format(date);
  } catch {
    return jalali(date);
  }
}

export function hhmm(d: string | Date | undefined | null): string {
  if (!d) return "—";
  const date = typeof d === "string" ? new Date(d) : d;
  return new Intl.DateTimeFormat("fa-IR", { hour: "2-digit", minute: "2-digit" }).format(date);
}

/** شنبه‌ی هفته‌ی جاری */
export function thisSaturday(d = new Date()): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const delta = (5 - x.getDay() + 7) % 7; // JS: 6=شنبه
  x.setDate(x.getDate() - delta);
  return x;
}

export function faWeekdayOf(d: Date): number {
  return (d.getDay() + 1) % 7; // شنبه=0
}

export function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function isoAt(d: Date, hour: number, minute = 0): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${isoDate(d)}T${p(hour)}:${p(minute)}:00`;
}

export function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}

export const SPACE_TYPE_FA: Record<string, string> = {
  general_classroom: "کلاس عمومی",
  smart_classroom: "کلاس هوشمند",
  laboratory: "آزمایشگاه",
  workshop: "کارگاه",
  computer_site: "سایت رایانه",
  seminar_hall: "سالن سمینار",
  studio: "استودیو آموزشی",
  group_study: "فضای مطالعه گروهی",
};

export const SPACE_STATUS_FA: Record<string, string> = {
  active: "فعال",
  limited: "محدود",
  under_repair: "در تعمیر",
  inactive: "غیرفعال",
  retired: "بازنشسته",
};

export const REQ_STATUS_FA: Record<string, string> = {
  draft: "پیش‌نویس",
  submitted: "ارسال‌شده",
  under_review: "در بررسی",
  approved: "تأییدشده",
  rejected: "ردشده",
  cancelled: "لغوشده",
  completed: "خاتمه‌یافته",
  no_show: "بدون حضور",
};

export const USE_TYPE_FA: Record<string, string> = {
  scheduled_class: "کلاس برنامه‌ریزی‌شده",
  make_up_class: "کلاس جبرانی",
  lab_session: "جلسه آزمایشگاه",
  workshop: "کارگاه آموزشی",
  exam: "آزمون",
  research_meeting: "جلسه پژوهشی آموزشی",
};

export const BLOCK_STATUS_FA: Record<string, string> = {
  reported: "گزارش خرابی — نیازمند بررسی",
  active: "انسداد فعال",
  resolved: "رفع شد",
  rejected: "ردشده",
};

export const ROLE_FA: Record<string, string> = {
  sys_admin: "مدیر سامانه",
  education_expert: "کارشناس آموزش",
  education_manager: "مدیر آموزشی",
  lab_manager: "مسئول آزمایشگاه",
  facility_manager: "مسئول ساختمان/تأسیسات",
  professor: "استاد",
  student: "دانشجو",
  university_admin: "مدیر دانشگاه",
  service: "کاربر سرویس",
};
