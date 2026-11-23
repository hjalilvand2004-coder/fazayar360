import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { jalali, ROLE_FA, toFaDigits } from "../format";
import { Chip, EmptyState, Field, Modal, Spinner, StatusChip } from "../ui";

type AuditRow = {
  id: string; actor_name?: string; action: string; entity_type: string; entity_id?: string;
  before?: any; after?: any; request_id?: string; ip?: string; at: string;
};
type ExtRef = {
  entity_type: string; external_id: string; source_system: string; source_version?: string;
  title?: string; sync_status: string; last_synced_at?: string;
};

export default function Admin() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"audit" | "integrations" | "users">("audit");
  const [newUser, setNewUser] = useState<{ open: boolean }>({ open: false });

  const audit = useQuery({
    queryKey: ["audit"], queryFn: () => api.get<{ items: AuditRow[]; total: number }>("/admin/audit-logs?size=60"),
    refetchInterval: 60_000,
  });
  const refs = useQuery({ queryKey: ["ext-refs"], queryFn: () => api.get<ExtRef[]>("/integrations/references") });
  const outbox = useQuery({ queryKey: ["outbox"], queryFn: () => api.get<{ pending: number; published: number }>("/integrations/outbox") });
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get<any[]>("/admin/users") });

  const demoPull = useMutation({
    mutationFn: () => api.post("/integrations/sync/demo-pull"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ext-refs"] }),
  });
  const publish = useMutation({
    mutationFn: () => api.post("/integrations/outbox/publish"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outbox"] }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-[#172033]">مدیریت، یکپارچگی و ممیزی</h1>
      <div className="flex gap-2 flex-wrap" role="tablist">
        {([["audit", "تاریخچه تغییرات"], ["integrations", "اتصال زیست‌بوم"], ["users", "کاربران و نقش‌ها"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}
            className={`rounded-xl px-4 py-2 text-sm border ${tab === k ? "bg-[#3563E9] text-white border-blue-600" : "bg-white border-slate-300"}`}>{l}</button>
        ))}
      </div>

      {tab === "audit" && (
        <div className="card overflow-hidden overflow-x-auto">
          {audit.isLoading ? <Spinner /> : (
            <table className="w-full text-sm min-w-[760px]">
              <thead className="bg-slate-50 text-slate-600">
                <tr><th className="text-right p-3">زمان</th><th className="text-right p-3">کاربر</th>
                    <th className="text-right p-3">اقدام</th><th className="text-right p-3">موجودیت</th>
                    <th className="text-right p-3 hidden md:table-cell">رهگیری</th><th className="text-right p-3 hidden md:table-cell">تغییر</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {audit.data!.items.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="p-3 text-xs">{jalali(a.at)}</td>
                    <td className="p-3">{a.actor_name || "—"}</td>
                    <td className="p-3"><Chip tone="blue">{a.action}</Chip></td>
                    <td className="p-3 text-xs">{a.entity_type} {a.entity_id?.slice(0, 8)}</td>
                    <td className="p-3 hidden md:table-cell font-mono text-[11px]">{a.request_id}</td>
                    <td className="p-3 hidden md:table-cell text-[11px] text-slate-500 max-w-64 truncate" dir="ltr">
                      {a.after ? JSON.stringify(a.after).slice(0, 90) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "integrations" && (
        <div className="space-y-4">
          <div className="card p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-bold text-slate-800">داده مرجع از پایه‌یار۳۶۰ (رونوشت همگام‌شده)</h2>
                <p className="text-xs text-slate-500 mt-1">
                  داده مرجع با API/رویداد نسخه‌داری دریافت می‌شود، نه اتصال مستقیم به جداول پایه‌یار؛ اگر پایه‌یار قطع باشد، رونوشت معتبر قبلی استفاده می‌شود.
                </p>
              </div>
              <div className="flex gap-2">
                <button className="btn-ghost" disabled={demoPull.isPending} onClick={() => demoPull.mutate()}>همگام‌سازی آزمایشی</button>
                <button className="btn-teal" disabled={publish.isPending} onClick={() => publish.mutate()}>انتشار رویدادهای خروجی</button>
              </div>
            </div>
            <div className="flex gap-2 mt-3">
              <Chip tone={outbox.data?.pending ? "amber" : "green"}>صندوق خروجی: {toFaDigits(outbox.data?.pending ?? 0)} در صف، {toFaDigits(outbox.data?.published ?? 0)} منتشرشده</Chip>
            </div>
          </div>
          {refs.isLoading ? <Spinner /> : (
            <div className="card overflow-hidden overflow-x-auto">
              <table className="w-full text-sm min-w-[700px]">
                <thead className="bg-slate-50 text-slate-600">
                  <tr><th className="text-right p-3">نوع</th><th className="text-right p-3">شناسه خارجی</th>
                      <th className="text-right p-3 hidden md:table-cell">نسخه</th><th className="text-right p-3">عنوان</th>
                      <th className="text-right p-3">وضعیت همگام‌سازی</th><th className="text-right p-3 hidden md:table-cell">آخرین همگام‌سازی</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {refs.data!.map((r, i) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="p-3"><Chip tone="slate">{r.entity_type}</Chip></td>
                      <td className="p-3 font-mono text-xs">{r.external_id}</td>
                      <td className="p-3 hidden md:table-cell text-xs">{r.source_version || "—"}</td>
                      <td className="p-3">{r.title || "—"}</td>
                      <td className="p-3"><StatusChip value={r.sync_status} fa={r.sync_status === "fresh" ? "به‌روز" : r.sync_status === "stale" ? "کهنه" : "خطا"} /></td>
                      <td className="p-3 hidden md:table-cell text-xs">{r.last_synced_at ? jalali(r.last_synced_at) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "users" && (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[560px]">
            <thead className="bg-slate-50 text-slate-600">
              <tr><th className="text-right p-3">نام کاربری</th><th className="text-right p-3">نام</th>
                  <th className="text-right p-3">نقش</th><th className="text-right p-3 hidden md:table-cell">حوزه/دانشکده</th><th className="text-right p-3">فعال</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.data?.map((u) => (
                <tr key={u.id}>
                  <td className="p-3 font-mono text-xs">{u.username}</td>
                  <td className="p-3">{u.display_name}</td>
                  <td className="p-3"><Chip tone="blue">{ROLE_FA[u.role]}</Chip></td>
                  <td className="p-3 hidden md:table-cell text-xs">{u.faculty || (u.scope_building_id ? "محدود به ساختمان" : "کل دانشگاه")}</td>
                  <td className="p-3">{u.is_active ? "✓" : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={newUser.open} onClose={() => setNewUser({ open: false })} title="ایجاد کاربر">
        <div className="text-sm text-slate-600">ایجاد کاربر از طریق API در دسترس است: <code dir="ltr">POST /api/v1/admin/users</code></div>
      </Modal>
    </div>
  );
}
