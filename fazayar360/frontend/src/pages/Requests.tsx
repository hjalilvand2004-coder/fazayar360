import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, HttpError } from "../api";
import { jalali, hhmm, REQ_STATUS_FA, USE_TYPE_FA, toFaDigits } from "../format";
import { Chip, EmptyState, ErrorState, Field, Modal, Spinner, StatusChip } from "../ui";

type ReqItem = {
  id: string; request_number: string; title: string; description?: string;
  use_type: string; status: string; expected_attendees: number; enrollment_count?: number;
  requested_space?: { id: string; name: string; code: string; building_name: string } | null;
  occurrences: { id: string; start: string; end: string; status: string; note?: string }[];
  allocations: { occurrence_id: string; space: { name: string }; start: string; end: string }[];
  decision_note?: string; cancel_reason?: string; version: number;
};

const REVIEW_ROLES = ["sys_admin", "education_expert", "education_manager"];

export default function Requests() {
  const [status, setStatus] = useState("");
  const qc = useQueryClient();
  const [detail, setDetail] = useState<ReqItem | null>(null);
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const reqs = useQuery({
    queryKey: ["requests", status],
    queryFn: () => api.get<{ items: ReqItem[]; total: number }>(
      `/booking-requests?size=100${status ? `&status=${status}` : ""}`),
  });

  const transition = useMutation({
    mutationFn: ({ id, action, body }: { id: string; action: string; body?: any }) =>
      api.post(`/booking-requests/${id}/${action}`, body || {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["requests"] }); setDetail(null); setComment(""); setErr(null); },
    onError: (e: any) => setErr(e.message + (e.requestId ? ` (رهگیری: ${e.requestId})` : "")),
  });

  if (reqs.isLoading) return <Spinner />;
  if (reqs.isError) return <ErrorState message={(reqs.error as HttpError).message} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-[#172033]">درخواست‌ها</h1>
        <select className="input max-w-48" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(REQ_STATUS_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {reqs.data!.items.length === 0 ? (
        <div className="card"><EmptyState title="درخواستی یافت نشد" hint="از صفحه «درخواست جدید» می‌توانید ثبت کنید." icon="📭" /></div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[720px]">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-right p-3">شماره</th>
                <th className="text-right p-3">عنوان</th>
                <th className="text-right p-3 hidden md:table-cell">نوع</th>
                <th className="text-right p-3 hidden md:table-cell">فضا</th>
                <th className="text-right p-3 hidden sm:table-cell">اولین جلسه</th>
                <th className="text-right p-3">وضعیت</th>
                <th className="text-right p-3">عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {reqs.data!.items.map((r) => (
                <tr key={r.id} className="hover:bg-slate-50 cursor-pointer" onClick={() => { setDetail(r); setErr(null); }}>
                  <td className="p-3 font-mono text-xs">{r.request_number}</td>
                  <td className="p-3 font-medium">{r.title}</td>
                  <td className="p-3 hidden md:table-cell">{USE_TYPE_FA[r.use_type]}</td>
                  <td className="p-3 hidden md:table-cell">{r.requested_space?.name || "—"}</td>
                  <td className="p-3 hidden sm:table-cell text-xs">{r.occurrences[0] ? `${jalali(r.occurrences[0].start)} ${hhmm(r.occurrences[0].start)}` : "—"}</td>
                  <td className="p-3"><StatusChip value={r.status} fa={REQ_STATUS_FA[r.status]} /></td>
                  <td className="p-3">
                    {REVIEW_ROLES.length > 0 && ["submitted", "under_review"].includes(r.status) && (
                      <span className="text-xs text-blue-600">بررسی</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={!!detail} onClose={() => setDetail(null)} title={`درخواست ${detail?.request_number || ""}`} wide>
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <StatusChip value={detail.status} fa={REQ_STATUS_FA[detail.status]} />
              <Chip tone="slate">{USE_TYPE_FA[detail.use_type]}</Chip>
              <Chip tone="blue">{toFaDigits(detail.expected_attendees)} نفر برنامه‌ریزی‌شده</Chip>
              {detail.enrollment_count != null && <Chip tone="teal">{toFaDigits(detail.enrollment_count)} ثبت‌نام (از زیرسیستم آموزش)</Chip>}
            </div>
            <div><b>عنوان:</b> {detail.title}</div>
            {detail.description && <div className="text-slate-600">{detail.description}</div>}
            <div><b>فضای درخواستی:</b> {detail.requested_space ? `${detail.requested_space.name} — ${detail.requested_space.building_name}` : "—"}</div>

            <h3 className="font-bold text-slate-700">جلسات (رخدادهای تاریخ‌دار)</h3>
            <ul className="space-y-1">
              {detail.occurrences.map((o) => (
                <li key={o.id} className="flex flex-wrap items-center gap-2 border rounded-xl p-2">
                  <span className="text-xs">{jalali(o.start)} · {hhmm(o.start)}–{hhmm(o.end)}</span>
                  <StatusChip value={o.status} fa={REQ_STATUS_FA[o.status] || o.status} />
                  {o.note && <span className="text-xs text-slate-500">{o.note}</span>}
                </li>
              ))}
            </ul>

            {detail.allocations.length > 0 && (
              <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-emerald-900 text-xs">
                ✓ تخصیص قطعی ثبت شد: {detail.allocations.map((a) => `${a.space.name} (${hhmm(a.start)}–${hhmm(a.end)})`).join("، ")}
              </div>
            )}

            {detail.decision_note && <div className="text-xs text-slate-600">یادداشت تصمیم: {detail.decision_note}</div>}
            {detail.cancel_reason && <div className="text-xs text-red-700">دلیل لغو: {detail.cancel_reason}</div>}

            {err && <div className="card p-3 border-red-200 bg-red-50 text-red-800 text-xs" role="alert">⚠️ {err}</div>}

            {["submitted", "under_review"].includes(detail.status) && (
              <div className="space-y-3 border-t pt-3">
                <Field label="یادداشت بررسی (اختیاری)">
                  <textarea className="input" rows={2} value={comment} onChange={(e) => setComment(e.target.value)} />
                </Field>
                <div className="flex flex-wrap gap-2">
                  <button className="btn-primary" disabled={transition.isPending}
                          onClick={() => transition.mutate({ id: detail.id, action: "approve", body: { comment } })}>تأیید و تخصیص</button>
                  <button className="btn-danger" disabled={transition.isPending}
                          onClick={() => transition.mutate({ id: detail.id, action: "reject", body: { comment } })}>رد</button>
                </div>
                <p className="text-[11px] text-slate-500">تأیید، تخصیص قطعی را با اعتبارسنجی مجدد تعارض/ظرفیت/ساعات مجاز ثبت می‌کند؛ در صورت تعارض، خطای ۴۰۹ ساختاریافته دریافت می‌شود.</p>
              </div>
            )}
            {detail.status === "draft" && (
              <button className="btn-primary" disabled={transition.isPending}
                      onClick={() => transition.mutate({ id: detail.id, action: "submit" })}>ارسال برای بررسی</button>
            )}
            {!["cancelled", "rejected", "completed"].includes(detail.status) && (
              <button className="btn-ghost" disabled={transition.isPending}
                      onClick={() => {
                        const reason = window.prompt("دلیل لغو:");
                        if (reason) transition.mutate({ id: detail.id, action: "cancel", body: { reason } });
                      }}>لغو درخواست</button>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
