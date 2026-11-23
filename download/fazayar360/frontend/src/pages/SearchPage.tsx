import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, HttpError } from "../api";
import { hhmm, isoAt, jalali, FA_WEEKDAYS, SPACE_TYPE_FA, toFaDigits } from "../format";
import { Chip, ErrorState, Field, Modal, Spinner } from "../ui";

type Match = {
  id: string; code: string; name: string; space_type: string; capacity: number; layout?: string;
  reasons: string[]; warnings: string[]; same_building: boolean;
  building: { name: string }; campus: { name: string }; floor?: { number: number } | null;
  has_step_free_access: boolean; needs_lab_manager: boolean;
};
type NearMiss = { id: string; name: string; blocker: string; capacity?: number; building: string };
type SearchRes = { matches: Match[]; near_misses: NearMiss[]; count: number };
type Parsed = { understood: string[]; missing: string[]; target_date?: string; start_time?: string };

export default function SearchPage() {
  const [params] = useSearchParams();
  const nav = useNavigate();
  const qc = useQueryClient();

  const [assistantText, setAssistantText] = useState(params.get("q") || "");
  const [assistant, setAssistant] = useState<{ parsed: Parsed; matches: Match[]; near_misses: NearMiss[] } | null>(null);
  const [form, setForm] = useState({
    start_at: "", end_at: "", attendees: 30, space_types: "", feature_ids: [] as string[],
    accessibility_required: false, needs_lab_manager: false,
  });
  const [result, setResult] = useState<SearchRes | null>(null);
  const [bookTarget, setBookTarget] = useState<{ m: Match; start: string; end: string } | null>(null);
  const [bookErr, setBookErr] = useState<string | null>(null);

  const features = useQuery({ queryKey: ["features"], queryFn: () => api.get<{ id: string; name: string }[]>("/features") });

  // اگر از خانه با دستیار آمده‌اند، خودکار اجرا شود
  useEffect(() => {
    const q = params.get("q");
    if (q) runAssistant(q);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const runAssistant = async (text: string) => {
    setAssistant(null);
    try {
      const res = await api.post<{ parsed: Parsed; matches: Match[]; near_misses: NearMiss[] }>("/assistant/search", { text });
      setAssistant(res);
      // پرکردن فرم از فیلترهای دستیار
      const p = res.parsed as any;
      if (p.target_date && p.start_time) {
        const start = `${p.target_date}T${p.start_time}:00`;
        const end = p.duration_min ? new Date(new Date(start).getTime() + p.duration_min * 60000).toISOString() : "";
        setForm((f) => ({ ...f, start_at: start, end_at: end.slice(0, 19), attendees: p.attendees || f.attendees }));
      }
    } catch (e: any) {
      setAssistant({ parsed: { understood: [], missing: [e.message] }, matches: [], near_misses: [] });
    }
  };

  const search = async (e?: FormEvent) => {
    e?.preventDefault();
    setAssistant(null);
    setBookErr(null);
    try {
      const res = await api.post<SearchRes>("/availability/search", {
        start_at: form.start_at ? new Date(form.start_at).toISOString() : undefined,
        end_at: form.end_at ? new Date(form.end_at).toISOString() : undefined,
        attendees: Number(form.attendees) || 0,
        space_types: form.space_types ? [form.space_types] : [],
        feature_ids: form.feature_ids,
        accessibility_required: form.accessibility_required,
        needs_lab_manager: form.needs_lab_manager,
      });
      setResult(res);
    } catch (err: any) {
      setBookErr(err.message);
    }
  };

  const quickBook = useMutation({
    mutationFn: async () => {
      if (!bookTarget) return;
      const t = bookTarget;
      return api.post<any>("/booking-requests", {
        use_type: "make_up_class", title: `استفاده از ${t.m.name}`, expected_attendees: Number(form.attendees) || 0,
        requested_space_id: t.m.id,
        start_at: new Date(t.start).toISOString(), end_at: new Date(t.end).toISOString(),
      }, undefined);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] });
      setBookTarget(null);
      nav("/requests");
    },
    onError: (e: any) => setBookErr(e.message),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-[#172033]">جست‌وجوی فضای مناسب</h1>

      {/* دستیار */}
      <section className="card p-4">
        <h2 className="font-bold text-slate-800">دستیار هوشمند (متن فارسی → فیلتر)</h2>
        <div className="mt-2 flex flex-wrap gap-2">
          <input className="input flex-1 min-w-64" value={assistantText} onChange={(e) => setAssistantText(e.target.value)}
                 placeholder="مثلاً: برای سه‌شنبه ساعت ۱۰، یک کلاس برای ۳۲ نفر با نمایشگر نزدیک دانشکده علوم" />
          <button className="btn-teal" onClick={() => runAssistant(assistantText)} disabled={!assistantText.trim()}>تبدیل و جست‌وجو</button>
        </div>
        {assistant && (
          <div className="mt-3 text-sm space-y-2">
            <div className="flex flex-wrap gap-1.5">
              {assistant.parsed.understood.map((u, i) => <Chip key={i} tone="green" icon="✓">{u}</Chip>)}
              {assistant.parsed.missing.map((u, i) => <Chip key={`m${i}`} tone="amber" icon="?">مشخص نشده: {u}</Chip>)}
            </div>
            {assistant.matches.length > 0 ? (
              <MatchList matches={assistant.matches} onPick={(m) => {
                const p = assistant.parsed as any;
                if (p.target_date && p.start_time) {
                  const start = `${p.target_date}T${p.start_time}:00`;
                  const end = p.duration_min ? new Date(new Date(start).getTime() + (p.duration_min || 90) * 60000).toISOString().slice(0, 19) : "";
                  setBookTarget({ m, start, end });
                } else setBookErr("روز و ساعت در متن مشخص نشد؛ از فرم پایین استفاده کنید");
              }} />
            ) : <div className="text-slate-500 text-sm">موردی واجد شرایط یافت نشد.</div>}
          </div>
        )}
      </section>

      {/* فرم جست‌وجو */}
      <form className="card p-4 grid md:grid-cols-3 gap-3" onSubmit={search}>
        <Field label="از (تاریخ و ساعت)"><input type="datetime-local" className="input" required value={form.start_at}
          onChange={(e) => setForm({ ...form, start_at: e.target.value })} /></Field>
        <Field label="تا"><input type="datetime-local" className="input" required value={form.end_at}
          onChange={(e) => setForm({ ...form, end_at: e.target.value })} /></Field>
        <Field label="تعداد افراد"><input type="number" min={1} className="input" value={form.attendees}
          onChange={(e) => setForm({ ...form, attendees: Number(e.target.value) })} /></Field>
        <Field label="نوع فضا">
          <select className="input" value={form.space_types} onChange={(e) => setForm({ ...form, space_types: e.target.value })}>
            <option value="">همه</option>
            {Object.entries(SPACE_TYPE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <Field label="تجهیزات ضروری">
          <div className="flex flex-wrap gap-2 pt-1">
            {features.data?.map((f) => (
              <label key={f.id} className="text-xs flex items-center gap-1 cursor-pointer">
                <input type="checkbox" checked={form.feature_ids.includes(f.id)}
                  onChange={(e) => setForm({ ...form, feature_ids: e.target.checked ? [...form.feature_ids, f.id] : form.feature_ids.filter((x) => x !== f.id) })} />
                {f.name}
              </label>
            ))}
          </div>
        </Field>
        <Field label="شرایط دیگر">
          <div className="flex flex-col gap-1 pt-1 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.accessibility_required}
              onChange={(e) => setForm({ ...form, accessibility_required: e.target.checked })} /> مسیر بدون پله</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={form.needs_lab_manager}
              onChange={(e) => setForm({ ...form, needs_lab_manager: e.target.checked })} /> با مسئول آزمایشگاه</label>
          </div>
        </Field>
        <div className="flex items-end">
          <button className="btn-primary w-full md:w-auto">جست‌وجو</button>
        </div>
      </form>

      {bookErr && <div className="card p-4 border-red-200 bg-red-50 text-red-800 text-sm" role="alert">⚠️ {bookErr}</div>}

      {result && (
        <>
          <h2 className="font-bold text-slate-800">{toFaDigits(result.matches.length)} فضای واجد شرایط یافت شد</h2>
          <MatchList matches={result.matches} onPick={(m) => setBookTarget({ m, start: form.start_at, end: form.end_at })} />
          {result.near_misses.length > 0 && (
            <details className="card p-4">
              <summary className="font-bold text-slate-700 cursor-pointer">گزینه‌های نزدیک که شرایط کامل ندارند ({toFaDigits(result.near_misses.length)})</summary>
              <ul className="mt-3 text-sm space-y-1.5">
                {result.near_misses.map((n) => (
                  <li key={n.id} className="text-slate-600">• {n.name} ({n.building}) — <span className="text-amber-700">{n.blocker}</span></li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}

      {/* تأیید نهایی رزرو — دستیار هرگز مرجع آزادبودن فضا نیست */}
      <Modal open={!!bookTarget} onClose={() => { setBookTarget(null); setBookErr(null); }} title="ثبت درخواست رزرو">
        {bookTarget && (
          <div className="space-y-3 text-sm">
            <div className="rounded-xl bg-blue-50 p-3">
              <div className="font-bold">{bookTarget.m.name}</div>
              <div className="text-slate-600 text-xs mt-1">{bookTarget.m.building.name} · ظرفیت مؤثر {toFaDigits(bookTarget.m.capacity)}</div>
            </div>
            <ul className="text-xs text-slate-600 list-disc pr-5">
              {bookTarget.m.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
            <div className="text-slate-600">
              بازه: <b>{jalali(bookTarget.start)} ساعت {hhmm(bookTarget.start)} تا {hhmm(bookTarget.end)}</b>
            </div>
            <p className="text-xs text-slate-500">درخواست به‌صورت «ارسال‌شده» ثبت می‌شود و پس از بررسی کارشناس آموزش با اعتبارسنجی قطعی تعارض، تخصیص می‌یابد.</p>
            <button className="btn-primary w-full" disabled={quickBook.isPending}
                    onClick={() => quickBook.mutate()}>
              {quickBook.isPending ? "در حال ثبت…" : "ثبت درخواست"}
            </button>
          </div>
        )}
      </Modal>
    </div>
  );
}

function MatchList({ matches, onPick }: { matches: Match[]; onPick: (m: Match) => void }) {
  return (
    <div className="grid md:grid-cols-2 gap-3">
      {matches.map((m, idx) => (
        <div key={m.id} className="card p-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="font-bold text-slate-800">{toFaDigits(idx + 1)}. {m.name}</div>
              <div className="text-xs text-slate-500">{m.building.name}{m.floor ? ` · طبقه ${toFaDigits(m.floor.number)}` : ""}</div>
            </div>
            <Chip tone={idx === 0 ? "teal" : "blue"}>ظرفیت مؤثر {toFaDigits(m.capacity)}</Chip>
          </div>
          <ul className="text-xs text-slate-600 mt-2 space-y-1">
            {m.reasons.map((r, i) => <li key={i} className="flex gap-1"><span className="text-emerald-600" aria-hidden>✓</span>{r}</li>)}
            {m.warnings.map((w, i) => <li key={`w${i}`} className="flex gap-1"><span className="text-amber-600" aria-hidden>⚠</span>{w}</li>)}
          </ul>
          <button className="btn-primary mt-3 !py-1.5 text-xs" onClick={() => onPick(m)}>رزرو این فضا</button>
        </div>
      ))}
    </div>
  );
}
