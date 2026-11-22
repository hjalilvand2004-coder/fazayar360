import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { USE_TYPE_FA, hhmm, jalali, toFaDigits } from "../format";
import { Chip, Field, Spinner } from "../ui";

type SpaceLite = { id: string; code: string; name: string; building_name: string; campus_name: string; space_type: string };

export default function BookingNew() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const [step, setStep] = useState<"form" | "preview">("form");
  const [preview, setPreview] = useState<{ ok: boolean; conflicts: any[]; hour_violations: string[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({
    use_type: "make_up_class",
    title: "",
    description: "",
    expected_attendees: 30,
    requested_space_id: params.get("space") || "",
    layout: "",
    course_offer_ref: "",
    mode: "single" as "single" | "series",
    start_at: "", end_at: "",
    weekday: 0, start_time: "10:00", end_time: "12:00", start_date: "", end_date: "",
    accessibility_required: false, needs_lab_manager: false,
  });

  const spaces = useQuery({ queryKey: ["spaces", "lite"], queryFn: () => api.get<{ items: SpaceLite[] }>("/spaces?size=200") });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    // اعتبارسنجی محلی
    if (!form.title.trim()) return setErr("عنوان درخواست لازم است");
    const body: any = {
      use_type: form.use_type, title: form.title, description: form.description || undefined,
      expected_attendees: Number(form.expected_attendees) || 0,
      requested_space_id: form.requested_space_id || undefined,
      layout: form.layout || undefined,
      course_offer_ref: form.course_offer_ref || undefined,
      accessibility_required: form.accessibility_required,
      needs_lab_manager: form.needs_lab_manager,
    };
    if (form.mode === "single") {
      if (!form.start_at || !form.end_at) return setErr("بازه زمانی جلسه را کامل کنید");
      body.start_at = new Date(form.start_at).toISOString();
      body.end_at = new Date(form.end_at).toISOString();
    } else {
      if (!form.start_date || !form.end_date) return setErr("بازه تاریخ‌های الگوی هفتگی لازم است");
      body.series = { weekday: form.weekday, start_time: form.start_time, end_time: form.end_time,
                      start_date: form.start_date, end_date: form.end_date };
    }
    setBusy(true);
    try {
      // پیش‌نمایش تعارض قبل از ذخیره
      const start = body.start_at || `${body.series.start_date}T${body.series.start_time}:00`;
      const end = body.end_at || `${body.series.start_date}T${body.series.end_time}:00`;
      if (body.requested_space_id && body.start_at) {
        const cp = await api.post<{ ok: boolean; conflicts: any[]; hour_violations: string[] }>(
          "/booking-requests/conflict-preview",
          { space_id: body.requested_space_id, start_at: body.start_at, end_at: body.end_at });
        setPreview(cp);
        setStep("preview");
      } else {
        await doCreate(body);
      }
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doCreate = async (body: any) => {
    const res = await api.post<any>("/booking-requests", body, crypto.randomUUID());
    await api.post(`/booking-requests/${res.id}/submit`).catch(() => undefined);
    nav("/requests");
  };

  const confirmCreate = async () => {
    // ساخت نهایی پس از مشاهده پیش‌نمایش
    const body: any = {
      use_type: form.use_type, title: form.title, description: form.description || undefined,
      expected_attendees: Number(form.expected_attendees) || 0,
      requested_space_id: form.requested_space_id || undefined,
      layout: form.layout || undefined,
      course_offer_ref: form.course_offer_ref || undefined,
      accessibility_required: form.accessibility_required, needs_lab_manager: form.needs_lab_manager,
    };
    if (form.mode === "single") {
      body.start_at = new Date(form.start_at).toISOString();
      body.end_at = new Date(form.end_at).toISOString();
    } else {
      body.series = { weekday: form.weekday, start_time: form.start_time, end_time: form.end_time,
                      start_date: form.start_date, end_date: form.end_date };
    }
    setBusy(true);
    try {
      const res = await api.post<any>("/booking-requests", body, crypto.randomUUID());
      await api.post(`/booking-requests/${res.id}/submit`).catch(() => undefined);
      nav("/requests");
    } catch (e: any) {
      setErr(e.message);
      setStep("form");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-xl font-bold text-[#172033]">درخواست جدید استفاده از فضا</h1>
      {spaces.isLoading && <Spinner />}

      {step === "form" && (
        <form className="card p-5 space-y-4" onSubmit={submit}>
          <div className="grid md:grid-cols-2 gap-3">
            <Field label="نوع استفاده">
              <select className="input" value={form.use_type} onChange={(e) => setForm({ ...form, use_type: e.target.value })}>
                {Object.entries(USE_TYPE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
            </Field>
            <Field label="عنوان"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} required /></Field>
            <Field label="شناسه ارائه درس در زیست‌بوم (اختیاری)">
              <input className="input" dir="ltr" placeholder="مثل CO-4021" value={form.course_offer_ref}
                     onChange={(e) => setForm({ ...form, course_offer_ref: e.target.value })} />
            </Field>
            <Field label="تعداد افراد برنامه‌ریزی‌شده">
              <input type="number" min={1} className="input" value={form.expected_attendees}
                     onChange={(e) => setForm({ ...form, expected_attendees: Number(e.target.value) })} />
            </Field>
            <Field label="فضای درخواستی">
              <select className="input" value={form.requested_space_id}
                      onChange={(e) => setForm({ ...form, requested_space_id: e.target.value })}>
                <option value="">— انتخاب فضا (یا از جست‌وجو) —</option>
                {spaces.data?.items.map((s) => (
                  <option key={s.id} value={s.id}>{s.name} — {s.building_name}</option>
                ))}
              </select>
            </Field>
            <Field label="توضیح"><textarea className="input" rows={1} value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          </div>

          <div className="border-t pt-3">
            <div className="flex gap-2 mb-3">
              <button type="button" onClick={() => setForm({ ...form, mode: "single" })}
                className={`rounded-xl px-3 py-1.5 text-sm border ${form.mode === "single" ? "bg-[#3563E9] text-white border-blue-600" : "border-slate-300"}`}>تک‌جلسه‌ای</button>
              <button type="button" onClick={() => setForm({ ...form, mode: "series" })}
                className={`rounded-xl px-3 py-1.5 text-sm border ${form.mode === "series" ? "bg-[#3563E9] text-white border-blue-600" : "border-slate-300"}`}>تکرار هفتگی</button>
            </div>
            {form.mode === "single" ? (
              <div className="grid md:grid-cols-2 gap-3">
                <Field label="از"><input type="datetime-local" className="input" value={form.start_at}
                  onChange={(e) => setForm({ ...form, start_at: e.target.value })} /></Field>
                <Field label="تا"><input type="datetime-local" className="input" value={form.end_at}
                  onChange={(e) => setForm({ ...form, end_at: e.target.value })} /></Field>
              </div>
            ) : (
              <div className="grid md:grid-cols-3 gap-3">
                <Field label="روز هفته">
                  <select className="input" value={form.weekday} onChange={(e) => setForm({ ...form, weekday: Number(e.target.value) })}>
                    {["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"].map((d, i) => <option key={i} value={i}>{d}</option>)}
                  </select>
                </Field>
                <Field label="از ساعت"><input type="time" className="input" value={form.start_time}
                  onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></Field>
                <Field label="تا ساعت"><input type="time" className="input" value={form.end_time}
                  onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></Field>
                <Field label="تاریخ شروع"><input type="date" className="input" value={form.start_date}
                  onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
                <Field label="تاریخ پایان"><input type="date" className="input" value={form.end_date}
                  onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></Field>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.accessibility_required}
              onChange={(e) => setForm({ ...form, accessibility_required: e.target.checked })} /> نیاز به دسترس‌پذیری (مسیر بدون پله)</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.needs_lab_manager}
              onChange={(e) => setForm({ ...form, needs_lab_manager: e.target.checked })} /> نیاز به مسئول آزمایشگاه</label>
          </div>

          {err && <div className="card p-3 border-red-200 bg-red-50 text-red-800 text-sm" role="alert">⚠️ {err}</div>}
          <button className="btn-primary" disabled={busy}>{busy ? "…" : "بررسی و ثبت"}</button>
        </form>
      )}

      {step === "preview" && preview && (
        <div className="card p-5 space-y-3">
          <h2 className="font-bold text-slate-800">پیش‌نمایش تعارض — قبل از ذخیره</h2>
          {preview.ok ? (
            <div className="rounded-xl bg-emerald-50 border border-emerald-300 p-3 text-emerald-900 text-sm">
              ✓ تعارضی برای بازه و فضای انتخابی دیده نمی‌شود.
            </div>
          ) : (
            <div className="space-y-2">
              {preview.conflicts.map((c, i) => (
                <div key={i} className="rounded-xl bg-red-50 border border-red-300 p-3 text-red-900 text-sm">
                  ✕ هم‌پوشانی با {c.kind === "maintenance" ? "انسداد" : "رزرو"}: {jalali(c.start)} {hhmm(c.start)}–{hhmm(c.end)}
                </div>
              ))}
              {preview.hour_violations.map((v, i) => (
                <div key={i} className="rounded-xl bg-amber-50 border border-amber-300 p-3 text-amber-900 text-sm">
                  ⚠ {v}
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <button className="btn-ghost" onClick={() => setStep("form")}>بازگشت به فرم</button>
            <button className="btn-primary" disabled={busy || !preview.ok} onClick={confirmCreate}>
              {busy ? "…" : "ثبت و ارسال درخواست"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
