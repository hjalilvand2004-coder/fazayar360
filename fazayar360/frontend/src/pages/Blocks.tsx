import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { BLOCK_STATUS_FA, jalali, hhmm, toFaDigits } from "../format";
import { Chip, EmptyState, Field, Modal, Spinner, StatusChip } from "../ui";

type Block = {
  id: string; title: string; description?: string; reason_code: string; status: string;
  space?: { id: string; name: string; code: string } | null;
  start: string; end: string; reporter_name?: string;
};

export default function Blocks() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [affected, setAffected] = useState<{ request_id: string; request_number: string; title: string; attendees: number }[]>([]);
  const [createdId, setCreatedId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ space_id: "", title: "", description: "", start_at: "", end_at: "", reason_code: "repair" });

  const blocks = useQuery({ queryKey: ["blocks"], queryFn: () => api.get<Block[]>("/maintenance-blocks") });
  const spaces = useQuery({ queryKey: ["spaces", "lite"], queryFn: () => api.get<{ items: any[] }>("/spaces?size=200") });

  const create = useMutation({
    mutationFn: () => api.post<{ id: string; affected_sessions: any[] }>("/maintenance-blocks", {
      space_id: form.space_id || undefined, reason_code: form.reason_code, title: form.title,
      description: form.description || undefined,
      start_at: new Date(form.start_at).toISOString(), end_at: new Date(form.end_at).toISOString(),
    }),
    onSuccess: (res) => {
      setAffected(res.affected_sessions || []);
      setCreatedId(res.id);
      qc.invalidateQueries({ queryKey: ["blocks"] });
      setOpen(false);
      setErr(null);
    },
    onError: (e: any) => setErr(e.message),
  });

  const act = useMutation({
    mutationFn: ({ id, action }: { id: string; action: string }) =>
      api.post(`/maintenance-blocks/${id}/${action}`, action === "report-approve" ? {} : undefined),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["blocks"] }),
    onError: (e: any) => setErr(e.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-[#172033]">انسداد تعمیراتی و گزارش خرابی</h1>
        <button className="btn-primary" onClick={() => setOpen(true)}>ثبت انسداد جدید</button>
      </div>
      {err && <div className="card p-3 border-red-200 bg-red-50 text-red-800 text-sm" role="alert">⚠️ {err}</div>}

      {createdId && affected.length > 0 && (
        <div className="card p-4 border-amber-300 bg-amber-50">
          <div className="font-bold text-amber-900">
            🚧 انسداد ثبت شد؛ {toFaDigits(affected.length)} جلسه متاثر است — پیشنهاد جایگزین بررسی شود
          </div>
          <ul className="mt-2 space-y-1 text-sm text-amber-900">
            {affected.map((a) => (
              <li key={a.request_id} className="flex items-center justify-between gap-2 flex-wrap">
                <span>{a.request_number} — {a.title} ({toFaDigits(a.attendees)} نفر)</span>
                <Link className="btn-ghost !py-1 text-xs" to={`/blocks`}>بررسی جلسات</Link>
              </li>
            ))}
          </ul>
          <p className="text-xs text-amber-800 mt-2">
            برای هر جلسه، گزینه‌های جایگزین واجد شرایط از طریق API «suggest-alternatives» در دسترس است؛ تأیید نهایی با مسئول مربوط است.
          </p>
        </div>
      )}

      {blocks.isLoading ? <Spinner /> : blocks.data!.length === 0 ? (
        <div className="card"><EmptyState title="انسدادی ثبت نشده" icon="🚧" /></div>
      ) : (
        <div className="grid md:grid-cols-2 gap-3">
          {blocks.data!.map((b) => (
            <div key={b.id} className={`card p-4 ${b.status === "reported" ? "border-amber-400 bg-amber-50/50" : b.status === "active" ? "border-red-300" : ""}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-slate-800">{b.title}</div>
                  <div className="text-xs text-slate-500 mt-0.5">{b.space?.name || "تجهیز"} · {jalali(b.start)} {hhmm(b.start)} تا {jalali(b.end)} {hhmm(b.end)}</div>
                  {b.reporter_name && <div className="text-xs text-slate-400 mt-1">گزارش‌دهنده: {b.reporter_name}</div>}
                </div>
                <StatusChip value={b.status} fa={BLOCK_STATUS_FA[b.status]} />
              </div>
              {b.description && <p className="text-sm text-slate-600 mt-2">{b.description}</p>}
              <div className="flex flex-wrap gap-2 mt-3">
                {b.status === "reported" && (
                  <>
                    <button className="btn-teal !py-1.5 text-xs" onClick={() => act.mutate({ id: b.id, action: "report-approve" })}>
                      تبدیل به انسداد فعال
                    </button>
                    <button className="btn-ghost !py-1.5 text-xs" onClick={() => act.mutate({ id: b.id, action: "report-reject" })}>رد گزارش</button>
                  </>
                )}
                {b.status === "active" && (
                  <button className="btn-primary !py-1.5 text-xs" onClick={() => act.mutate({ id: b.id, action: "resolve" })}>
                    بازگشایی فضا (رفع انسداد)
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal open={open} onClose={() => setOpen(false)} title="ثبت انسداد تعمیراتی/آماده‌سازی">
        <div className="space-y-3">
          <Field label="فضا">
            <select className="input" value={form.space_id} onChange={(e) => setForm({ ...form, space_id: e.target.value })}>
              <option value="">— انتخاب فضا —</option>
              {spaces.data?.items.map((s) => <option key={s.id} value={s.id}>{s.name} — {s.building_name}</option>)}
            </select>
          </Field>
          <Field label="عنوان"><input className="input" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="از"><input type="datetime-local" className="input" value={form.start_at}
              onChange={(e) => setForm({ ...form, start_at: e.target.value })} /></Field>
            <Field label="تا"><input type="datetime-local" className="input" value={form.end_at}
              onChange={(e) => setForm({ ...form, end_at: e.target.value })} /></Field>
          </div>
          <Field label="دلیل">
            <select className="input" value={form.reason_code} onChange={(e) => setForm({ ...form, reason_code: e.target.value })}>
              <option value="repair">تعمیر</option><option value="preparation">آماده‌سازی</option>
              <option value="safety">ایمنی</option><option value="event">رویداد خاص</option><option value="other">سایر</option>
            </select>
          </Field>
          <Field label="توضیح"><textarea className="input" rows={2} value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          <button className="btn-primary w-full" disabled={create.isPending || !form.space_id || !form.title || !form.start_at}
            onClick={() => create.mutate()}>ثبت انسداد و شناسایی جلسات متاثر</button>
        </div>
      </Modal>
    </div>
  );
}
