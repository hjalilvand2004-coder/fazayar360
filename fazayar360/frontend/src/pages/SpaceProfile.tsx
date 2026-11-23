import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import QRCode from "qrcode";
import { api } from "../api";
import { addDays, hhmm, isoAt, jalali, SPACE_STATUS_FA, SPACE_TYPE_FA, thisSaturday, toFaDigits } from "../format";
import { Chip, EmptyState, ErrorState, Modal, Spinner, StatusChip } from "../ui";
import WeekGrid, { CalEvent } from "../components/WeekGrid";

type SpaceDetail = {
  id: string; code: string; name: string; space_type: string; status: string;
  campus_name: string; building_name: string;
  floor?: { number: number; name: string } | null;
  area_m2?: number; safe_capacity?: number | null;
  has_step_free_access: boolean; has_elevator_access: boolean; accessibility_notes?: string;
  needs_lab_manager: boolean; allowed_group_names?: string | null;
  responsible_unit?: string; responsible_person?: string; responsible_contact?: string;
  description?: string; min_prep_minutes: number; min_cleanup_minutes: number;
  public_slug: string; version: number;
  layouts: { name: string; capacity: number; seats_count?: number; tables_count?: number; is_default: boolean }[];
  features: { id: string; name: string; category: string; condition: string }[];
  equipment: { type_name: string; category: string; quantity: number; per_unit_capacity?: number; is_broken: boolean }[];
  availability_rules: { weekday: number; start_time: string; end_time: string; is_bookable: boolean }[];
};

export default function SpaceProfile() {
  const { id } = useParams();
  const nav = useNavigate();
  const [weekStart, setWeekStart] = useState(thisSaturday());
  const [qrOpen, setQrOpen] = useState(false);
  const [qrUrl, setQrUrl] = useState<string>("");

  const space = useQuery({
    queryKey: ["space", id],
    queryFn: () => api.get<SpaceDetail>(`/spaces/${id}`),
  });
  const cal = useQuery({
    queryKey: ["space-cal", id, isoAt(weekStart)],
    queryFn: () => api.get<{ events: CalEvent[] }>(
      `/spaces/${id}/calendar?date_from=${isoAt(weekStart).slice(0, 10)}&date_to=${isoAt(addDays(weekStart, 6)).slice(0, 10)}`),
  });

  const publicUrl = useMemo(() => `${window.location.origin}${window.location.pathname}#/public/spaces/${space.data?.public_slug || ""}`,
    [space.data?.public_slug]);

  if (space.isLoading) return <Spinner />;
  if (space.isError) return <ErrorState message={(space.error as any).message} />;
  const s = space.data!;

  const openQr = async () => {
    setQrUrl(await QRCode.toDataURL(publicUrl, { width: 320, margin: 1, color: { dark: "#172033", light: "#FFFFFF" } }));
    setQrOpen(true);
  };

  const cur = cal.data?.events || [];

  return (
    <div className="space-y-4">
      {/* گذرنامه تصویری فضا */}
      <div className="card overflow-hidden">
        <div className="h-40 bg-gradient-to-tr from-[#3563E9] via-teal-400/60 to-amber-200/70 relative">
          <div className="absolute bottom-3 right-4 text-white">
            <div className="text-2xl font-bold drop-shadow">{s.name}</div>
            <div className="text-xs opacity-90">{s.campus_name} · {s.building_name}{s.floor ? ` · طبقه ${toFaDigits(s.floor.number)}` : ""} · کد {s.code}</div>
          </div>
          <div className="absolute top-3 left-4 flex gap-2">
            <button className="btn-ghost !py-1.5 text-xs bg-white/90" onClick={openQr}>QR کنار در</button>
          </div>
        </div>
        <div className="p-4 flex flex-wrap gap-2 items-center">
          <StatusChip value={s.status} fa={SPACE_STATUS_FA[s.status]} />
          <Chip tone="blue">{SPACE_TYPE_FA[s.space_type]}</Chip>
          {s.safe_capacity && <Chip tone="slate">ظرفیت ایمن: {toFaDigits(s.safe_capacity)} نفر</Chip>}
          {s.has_step_free_access && <Chip tone="green" icon="♿">مسیر بدون پله</Chip>}
          {s.needs_lab_manager && <Chip tone="amber" icon="⚠">نیاز به تأیید مسئول آزمایشگاه</Chip>}
          <div className="flex-1" />
          <button className="btn-primary" onClick={() => nav(`/booking-new?space=${s.id}`)}>درخواست استفاده از فضا</button>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card p-4 space-y-4 lg:col-span-2">
          <h2 className="font-bold text-[#172033]">شناسنامه</h2>
          <p className="text-sm text-slate-600 leading-6">{s.description || "توضیحی ثبت نشده است."}</p>

          <div className="grid sm:grid-cols-2 gap-3 text-sm">
            <InfoRow label="مساحت" value={s.area_m2 ? `${toFaDigits(s.area_m2)} متر مربع` : "—"} />
            <InfoRow label="زمان آماده‌سازی/پاک‌سازی" value={`${toFaDigits(s.min_prep_minutes)} / ${toFaDigits(s.min_cleanup_minutes)} دقیقه`} />
            <InfoRow label="واحد متولی" value={s.responsible_unit || "—"} />
            <InfoRow label="مسئول پاسخ‌گو" value={`${s.responsible_person || "—"} ${s.responsible_contact ? `(${s.responsible_contact})` : ""}`} />
            <InfoRow label="گروه‌های مجاز" value={s.allowed_group_names || "بدون محدودیت"} />
            <InfoRow label="دسترس‌پذیری" value={s.accessibility_notes || (s.has_step_free_access ? "مسیر بدون پله" : "—")} />
          </div>

          <h3 className="font-bold text-slate-700 pt-2">چیدمان‌ها و ظرفیت‌ها</h3>
          <div className="flex flex-wrap gap-2">
            {s.layouts.map((l) => (
              <div key={l.name} className={`rounded-xl border p-3 text-center min-w-32 ${l.is_default ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}>
                <div className="text-xs text-slate-500">{l.name}{l.is_default ? " (پیش‌فرض)" : ""}</div>
                <div className="text-lg font-bold text-[#172033]">{toFaDigits(l.capacity)} نفر</div>
                {l.seats_count && <div className="text-[10px] text-slate-400">{toFaDigits(l.seats_count)} صندلی</div>}
              </div>
            ))}
          </div>

          <h3 className="font-bold text-slate-700 pt-2">امکانات</h3>
          <div className="flex flex-wrap gap-1.5">
            {s.features.map((f) => (
              <Chip key={f.id} tone={f.condition === "active" ? "teal" : "red"}>
                {f.name}{f.condition !== "active" ? " (خراب)" : ""}
              </Chip>
            ))}
          </div>

          <h3 className="font-bold text-slate-700 pt-2">تجهیزات فضا</h3>
          {s.equipment.length === 0 ? <div className="text-sm text-slate-500">تجهیز ثبت نشده است.</div> : (
            <ul className="text-sm space-y-1">
              {s.equipment.map((e, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${e.is_broken ? "bg-red-500" : "bg-emerald-500"}`} aria-hidden />
                  {e.type_name} × {toFaDigits(e.quantity)}
                  {e.per_unit_capacity && <span className="text-xs text-slate-500">(ظرفیت تجهیزاتی: {toFaDigits(e.quantity * e.per_unit_capacity)} نفر)</span>}
                </li>
              ))}
            </ul>
          )}

          <h3 className="font-bold text-slate-700 pt-2">ساعات مجاز</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            {["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"].map((name, wd) => {
              const rules = s.availability_rules.filter((r) => r.weekday === wd);
              return (
                <div key={wd} className={`rounded-lg border p-2 ${rules.length === 0 ? "border-slate-200 text-slate-400" : "border-emerald-300 bg-emerald-50 text-emerald-900"}`}>
                  <div className="font-medium">{name}</div>
                  <div>{rules.filter((r) => r.is_bookable).map((r) => `${toFaDigits(r.start_time)}–${toFaDigits(r.end_time)}`).join("، ") || "تعطیل"}</div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-4">
          <div className="card p-4">
            <h3 className="font-bold text-[#172033] mb-2">خلاصه وضعیت</h3>
            <ul className="text-sm space-y-2 text-slate-600">
              <li className="flex justify-between"><span>تعداد چیدمان</span><b>{toFaDigits(s.layouts.length)}</b></li>
              <li className="flex justify-between"><span>امکانات فعال</span><b>{toFaDigits(s.features.filter((f) => f.condition === "active").length)}</b></li>
              <li className="flex justify-between"><span>جلسات این هفته</span><b>{toFaDigits(cur.filter((e) => e.kind === "booking").length)}</b></li>
              <li className="flex justify-between"><span>انسداد این هفته</span><b>{toFaDigits(cur.filter((e) => e.kind === "maintenance").length)}</b></li>
            </ul>
            <Link className="text-xs text-blue-600 hover:underline" to={`/search?exclude=${s.id}`}>جست‌وجوی جایگزین‌ها →</Link>
          </div>
          <div className="card p-4">
            <h3 className="font-bold text-[#172033] mb-2">گزارش مشکل</h3>
            <p className="text-xs text-slate-500 leading-5">
              اگر ایرادی در این فضا می‌بینید (خرابی، نظافت، تجهیز)، از طریق صفحه‌ی عمومی QR کنار در یا با مسئول فضا گزارش دهید.
            </p>
            <button className="btn-ghost mt-3 text-xs" onClick={openQr}>نمایش QR و لینک عمومی</button>
          </div>
        </div>
      </div>

      {/* تقویم هفتگی */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="font-bold text-[#172033]">تقویم اشغال — هفته‌ی {jalali(weekStart)}</h2>
          <div className="flex gap-2">
            <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(addDays(weekStart, -7))}>هفته قبل</button>
            <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(thisSaturday())}>هفته جاری</button>
            <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(addDays(weekStart, 7))}>هفته بعد</button>
          </div>
        </div>
        {cal.isLoading ? <Spinner /> : cur.length === 0 ? <EmptyState title="هیچ رزرو یا انسدادی این هفته نیست" icon="🗓" /> :
          <WeekGrid weekStart={weekStart} events={cur} highlightSpace={s.id} />}
      </div>

      <Modal open={qrOpen} onClose={() => setQrOpen(false)} title="QR کنار در فضا">
        <div className="text-center space-y-3">
          {qrUrl && <img src={qrUrl} alt="QR فضا" className="mx-auto rounded-xl border border-slate-200" />}
          <div className="text-xs text-slate-500 break-all" dir="ltr">{publicUrl}</div>
          <p className="text-xs text-slate-500 leading-5 text-right">
            با اسکن: شناسنامه فضا، برنامه امروز (بدون نام افراد)، تجهیزات، راه ارتباط با مسئول و ثبت گزارش خرابی.
          </p>
        </div>
      </Modal>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2 border-b border-dashed border-slate-200 pb-1.5">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800 text-left">{value}</span>
    </div>
  );
}
