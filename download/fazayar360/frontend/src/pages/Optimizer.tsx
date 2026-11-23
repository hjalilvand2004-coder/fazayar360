import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { jalali, hhmm, toFaDigits } from "../format";
import { Chip, EmptyState, Field, Spinner } from "../ui";

type Run = {
  id: string; title: string; status: string; solution_status?: string | null; error?: string;
  metrics?: { sessions_total: number; assigned: number; unassigned: number; moves: number;
              empty_seat_hours_before: number; empty_seat_hours_after: number; improvement_seat_hours: number } | null;
  constraints_summary?: Record<string, number> | null;
  assignments: {
    id: string; session_ref: string; title?: string; start: string; end: string; status: string;
    current_space?: { name: string; code: string } | null;
    proposed_space?: { name: string; code: string; building_name: string } | null;
    score_breakdown?: { score?: number; reasons: string[] } | null;
    blockers?: { error?: string } | null;
  }[];
};

const SOLUTION_FA: Record<string, string> = {
  optimal: "بهینه", feasible: "قابل‌قبول", partial: "بخشی از جلسات بدون پاسخ", no_solution: "بدون پاسخ مجاز",
};

export default function Optimizer() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("سناریوی جابه‌جایی جلسات");
  const [sessions, setSessions] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);

  const spaces = useQuery({ queryKey: ["spaces", "lite"], queryFn: () => api.get<{ items: any[] }>("/spaces?size=200") });
  const run = useQuery({
    queryKey: ["opt-run", runId],
    queryFn: () => api.get<Run>(`/optimization-runs/${runId}`),
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data?.status === "completed" || q.state.data?.status === "failed" ? false : 1200),
  });

  const addRow = () => {
    const d = new Date(Date.now() + 3 * 86400000);
    const pad = (n: number) => String(n).padStart(2, "0");
    const day = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
    setSessions([...sessions, {
      ref: `S${sessions.length + 1}`, title: "", attendees: 30, day,
      start: "10:00", end: "12:00", current_space_id: "", preferred_building_id: "",
    }]);
  };

  const createRun = async () => {
    setRunning(true);
    try {
      const payload = {
        title,
        sessions: sessions.map((s) => ({
          ref: s.ref, title: s.title || s.ref, attendees: Number(s.attendees) || 0,
          start_at: `${s.day}T${s.start}:00`, end_at: `${s.day}T${s.end}:00`,
          current_space_id: s.current_space_id || undefined,
          preferred_building_id: s.preferred_building_id || undefined,
        })),
      };
      const res = await api.post<{ id: string }>("/optimization-runs", payload);
      setRunId(res.id);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setRunning(false);
    }
  };

  const applyAll = useMutation({
    mutationFn: () => api.post(`/optimization-runs/${runId}/apply`, { assignment_ids: [] }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["opt-run", runId] }),
  });

  const r = run.data;

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-[#172033]">سناریوسازی و بهینه‌سازی استفاده از فضا</h1>
      <p className="text-sm text-slate-500 leading-6">
        زمان و استاد جلسات ثابت فرض می‌شود؛ موتور فقط «فضای مناسب» را پیشنهاد می‌دهد. قیود سخت (تداخل، ظرفیت، تجهیزات، ساعات مجاز،
        دسترس‌پذیری، ایمنی و زمان آماده‌سازی) هرگز نقض نمی‌شوند و اعمال پیشنهاد نیازمند بررسی انسانی و اعتبارسنجی مجدد است.
      </p>

      {/* تعریف سناریو */}
      <div className="card p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <input className="input max-w-xs" value={title} onChange={(e) => setTitle(e.target.value)} />
          <button className="btn-ghost" onClick={addRow}>+ افزودن جلسه</button>
          <button className="btn-primary" disabled={sessions.length === 0 || running} onClick={createRun}>
            {running ? "در حال اجرا…" : "اجرای بهینه‌سازی"}
          </button>
        </div>
        {sessions.length === 0 ? (
          <div className="text-sm text-slate-500 py-6 text-center">جلسات سناریو را اضافه کنید؛ هر جلسه با زمان ثابت و تعداد نفرات.</div>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm min-w-[880px]">
              <thead className="text-slate-500 text-xs">
                <tr><th className="p-2 text-right">عنوان</th><th className="p-2 text-right">نفرات</th>
                    <th className="p-2 text-right">روز</th><th className="p-2 text-right">از</th><th className="p-2 text-right">تا</th>
                    <th className="p-2 text-right">فضای فعلی</th><th className="p-2 text-right">ترجیح ساختمان</th><th /></tr>
              </thead>
              <tbody className="divide-y">
                {sessions.map((s, i) => (
                  <tr key={i}>
                    <td className="p-1"><input className="input !py-1 min-w-40" value={s.title}
                      onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} /></td>
                    <td className="p-1"><input type="number" className="input !py-1 w-20" value={s.attendees}
                      onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, attendees: Number(e.target.value) } : x))} /></td>
                    <td className="p-1"><input type="date" className="input !py-1" value={s.day}
                      onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, day: e.target.value } : x))} /></td>
                    <td className="p-1"><input type="time" className="input !py-1" value={s.start}
                      onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, start: e.target.value } : x))} /></td>
                    <td className="p-1"><input type="time" className="input !py-1" value={s.end}
                      onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, end: e.target.value } : x))} /></td>
                    <td className="p-1">
                      <select className="input !py-1 min-w-36" value={s.current_space_id}
                        onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, current_space_id: e.target.value } : x))}>
                        <option value="">—</option>
                        {spaces.data?.items.map((sp) => <option key={sp.id} value={sp.id}>{sp.name}</option>)}
                      </select>
                    </td>
                    <td className="p-1">
                      <select className="input !py-1 min-w-36" value={s.preferred_building_id}
                        onChange={(e) => setSessions(sessions.map((x, j) => j === i ? { ...x, preferred_building_id: e.target.value } : x))}>
                        <option value="">—</option>
                        {[...new Map(spaces.data?.items.map((sp) => [sp.building_id, sp.building_name]) || []).entries()]
                          .map(([id, name]) => <option key={id} value={id}>{name}</option>)}
                      </select>
                    </td>
                    <td className="p-1"><button className="text-red-600 text-xs" onClick={() => setSessions(sessions.filter((_, j) => j !== i))}>حذف</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* نتیجه */}
      {r && (
        <div className="space-y-3">
          {r.status !== "completed" ? (
            <div className="card p-5"><Spinner label={`وضعیت حل: ${r.status === "failed" ? "خطا" : "در حال حل"}…`} /></div>
          ) : (
            <>
              <div className="card p-4">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <h2 className="font-bold text-[#172033]">مقایسه وضع موجود و پیشنهاد</h2>
                  <Chip tone={r.solution_status === "optimal" ? "green" : r.solution_status === "partial" ? "amber" : "red"}>
                    وضعیت حل: {SOLUTION_FA[r.solution_status || ""]}
                  </Chip>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <Metric label="ظرفیت خالی (صندلی‌ـ‌ساعت) — وضع موجود" value={toFaDigits(r.metrics?.empty_seat_hours_before ?? 0)} />
                  <Metric label="ظرفیت خالی — پیشنهاد" value={toFaDigits(r.metrics?.empty_seat_hours_after ?? 0)} tone="teal" />
                  <Metric label="میزان بهبود" value={`+${toFaDigits(r.metrics?.improvement_seat_hours ?? 0)}`} tone="teal" />
                  <Metric label="تعداد جابه‌جایی / فضاهای درگیر" value={`${toFaDigits(r.metrics?.moves ?? 0)} / ${toFaDigits(r.metrics?.assigned ?? 0)}`} />
                </div>
                {r.constraints_summary && Object.keys(r.constraints_summary).length > 0 && (
                  <div className="mt-3 text-xs text-amber-800 bg-amber-50 rounded-xl p-3">
                    <b>محدودیت‌های مانع تخصیص:</b>
                    <ul className="list-disc pr-5 mt-1">
                      {Object.entries(r.constraints_summary).map(([k, v]) => <li key={k}>{k} ({toFaDigits(v)} جلسه)</li>)}
                    </ul>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                {r.assignments.map((a) => (
                  <div key={a.id} className="card p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2 justify-between">
                      <div>
                        <b>{a.title || a.session_ref}</b>
                        <span className="text-slate-500 text-xs"> · {jalali(a.start)} {hhmm(a.start)}–{hhmm(a.end)}</span>
                      </div>
                      <div className="flex items-center gap-2 flex-wrap">
                        {a.current_space && <Chip tone="slate">وضع موجود: {a.current_space.name}</Chip>}
                        {a.proposed_space
                          ? <Chip tone={a.proposed_space.name !== a.current_space?.name ? "teal" : "green"}>
                              پیشنهاد: {a.proposed_space.name}</Chip>
                          : <Chip tone="red" icon="✕">بدون پاسخ مجاز</Chip>}
                      </div>
                    </div>
                    {a.score_breakdown?.reasons?.length ? (
                      <ul className="text-xs text-slate-600 mt-2 list-disc pr-5">
                        {a.score_breakdown.reasons.slice(0, 4).map((x, i) => <li key={i}>{x}</li>)}
                      </ul>
                    ) : null}
                    {a.status === "failed" && a.blockers?.error && (
                      <div className="text-xs text-red-700 mt-1">اعمال ناموفق: {a.blockers.error}</div>
                    )}
                  </div>
                ))}
              </div>

              <div className="card p-4 flex flex-wrap items-center gap-3">
                <button className="btn-primary" disabled={applyAll.isPending || r.metrics?.assigned === 0} onClick={() => applyAll.mutate()}>
                  اعمال پیشنهادها (با اعتبارسنجی مجدد)
                </button>
                <span className="text-xs text-slate-500">
                  پیشنهاد قدیمی مستقیم اعمال نمی‌شود؛ در فاصله محاسبه تا تأیید، اگر رزرو جدیدی ثبت شده باشد همان جلسه با خطای روشن علامت می‌خورد.
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: "teal" }) {
  return (
    <div className={`rounded-xl border p-3 ${tone === "teal" ? "border-teal-300 bg-teal-50" : "border-slate-200"}`}>
      <div className="text-[11px] text-slate-500 leading-4">{label}</div>
      <div className="text-lg font-bold text-[#172033] mt-1">{value}</div>
    </div>
  );
}
