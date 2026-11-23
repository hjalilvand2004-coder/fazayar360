import { FormEvent, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { hhmm, SPACE_TYPE_FA, toFaDigits, USE_TYPE_FA } from "../format";
import { Chip, ErrorState, Field, Spinner, StatusChip } from "../ui";

type Passport = {
  code: string; name: string; space_type: string; status: string;
  building: { name: string }; campus: { name: string }; floor?: { number: number } | null;
  layouts: { name: string; capacity: number }[]; safe_capacity?: number | null;
  features: { name: string }[]; equipment: { name: string; quantity: number }[];
  accessibility: { step_free: boolean; elevator: boolean; notes?: string };
  responsible_unit?: string; responsible_contact?: string; description?: string;
  today_schedule: { kind: string; start: string; end: string; use_type?: string | null }[];
};

/** صفحه عمومی QR — بدون احراز هویت؛ نام افراد و جزئیات حساس رزرو نمایش داده نمی‌شود */
export default function PublicSpace() {
  const { slug } = useParams();
  const [sent, setSent] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", reporter_name: "" });
  const [err, setErr] = useState<string | null>(null);

  const sp = useQuery({
    queryKey: ["public-space", slug],
    queryFn: () => api.get<Passport>(`/public/spaces/${slug}`),
  });

  const report = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    try {
      await api.post(`/public/spaces/${slug}/report-issue`, form);
      setSent(true);
    } catch (e: any) {
      setErr(e.message);
    }
  };

  if (sp.isLoading) return <Spinner />;
  if (sp.isError) return <ErrorState message={(sp.error as any).message} />;
  const s = sp.data!;

  return (
    <div className="min-h-screen bg-[#F5F7FB] py-6 px-4">
      <div className="max-w-3xl mx-auto space-y-4">
        <div className="card overflow-hidden">
          <div className="h-28 bg-gradient-to-tr from-[#3563E9] via-teal-400/60 to-amber-200/70 relative">
            <div className="absolute bottom-3 right-4 text-white">
              <div className="text-xl font-bold drop-shadow">{s.name}</div>
              <div className="text-xs opacity-90">{s.campus.name} · {s.building.name}{s.floor ? ` · طبقه ${toFaDigits(s.floor.number)}` : ""}</div>
            </div>
          </div>
          <div className="p-4 flex flex-wrap gap-2 items-center">
            <StatusChip value={s.status} fa={s.status === "active" ? "فعال" : s.status === "under_repair" ? "در تعمیر" : s.status} />
            <Chip tone="blue">{SPACE_TYPE_FA[s.space_type]}</Chip>
            {s.layouts.map((l) => <Chip key={l.name} tone="slate">{l.name}: {toFaDigits(l.capacity)} نفر</Chip>)}
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="card p-4">
            <h2 className="font-bold text-slate-800 mb-2">برنامه امروز</h2>
            {s.today_schedule.length === 0 ? (
              <p className="text-sm text-slate-500">رزروی برای امروز ثبت نشده است.</p>
            ) : (
              <ul className="text-sm space-y-1.5">
                {s.today_schedule.map((e, i) => (
                  <li key={i} className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500 w-24">{toFaDigits(e.start)}–{toFaDigits(e.end)}</span>
                    <span className={`h-2 w-2 rounded-full ${e.kind === "maintenance" ? "bg-red-500" : "bg-teal-500"}`} aria-hidden />
                    <span>{e.kind === "maintenance" ? "انسداد/آماده‌سازی" : e.use_type ? USE_TYPE_FA[e.use_type] : "استفاده آموزشی"}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-[11px] text-slate-400 mt-2">برنامه عمومی بدون نام افراد نمایش داده می‌شود.</p>
          </div>

          <div className="card p-4">
            <h2 className="font-bold text-slate-800 mb-2">امکانات و تجهیزات</h2>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {s.features.map((f, i) => <Chip key={i} tone="teal">{f.name}</Chip>)}
              {s.accessibility.step_free && <Chip tone="green" icon="♿">مسیر بدون پله</Chip>}
            </div>
            {s.equipment.length > 0 && (
              <ul className="text-xs text-slate-600">
                {s.equipment.map((e, i) => <li key={i}>{e.name} × {toFaDigits(e.quantity)}</li>)}
              </ul>
            )}
            <div className="text-xs text-slate-500 mt-3">
              مسئول: {s.responsible_unit || "—"} {s.responsible_contact ? `· ${s.responsible_contact}` : ""}
            </div>
          </div>
        </div>

        <div className="card p-4">
          <h2 className="font-bold text-slate-800 mb-2">ثبت گزارش خرابی</h2>
          {sent ? (
            <div className="rounded-xl bg-emerald-50 border border-emerald-300 p-3 text-emerald-900 text-sm">
              ✓ گزارش شما ثبت شد و برای مسئول ساختمان ارسال می‌شود. سپاس از همکاری شما.
            </div>
          ) : (
            <form className="grid md:grid-cols-2 gap-3" onSubmit={report}>
              <Field label="عنوان مشکل"><input className="input" required value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
              <Field label="نام (اختیاری)"><input className="input" value={form.reporter_name}
                onChange={(e) => setForm({ ...form, reporter_name: e.target.value })} /></Field>
              <div className="md:col-span-2"><Field label="توضیح"><textarea className="input" rows={2} value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field></div>
              {err && <div className="md:col-span-2 text-sm text-red-700" role="alert">⚠️ {err}</div>}
              <div className="md:col-span-2"><button className="btn-primary w-full md:w-auto">ارسال گزارش</button></div>
            </form>
          )}
        </div>
        <div className="text-center text-xs text-slate-400 pb-4">فضایار۳۶۰ — شناسنامه عمومی فضا</div>
      </div>
    </div>
  );
}
