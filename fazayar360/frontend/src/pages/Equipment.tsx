import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";
import { jalali, toFaDigits } from "../format";
import { Chip, EmptyState, Field, Spinner, StatusChip } from "../ui";

type Asset = {
  id: string; asset_tag?: string; name: string; model?: string; serial_number?: string; status: string;
  type: { name: string; category: string };
  location_space_id?: string | null;
  last_service_date?: string | null; next_calibration_due?: string | null;
  usage_restriction?: string; responsible_person?: string; bookable_independently: boolean;
};

const CAT_FA: Record<string, string> = { fixed: "ثابت", portable: "قابل‌حمل", consumable: "مصرفی" };
const STATUS_FA: Record<string, string> = { operational: "عملیاتی", needs_service: "نیازمند سرویس", broken: "خراب", retired: "بازنشسته" };

export default function Equipment() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const assets = useQuery({
    queryKey: ["assets", status],
    queryFn: () => api.get<{ items: Asset[]; total: number }>(`/equipment/assets?size=200${status ? `&status=${status}` : ""}`),
  });
  const pools = useQuery({ queryKey: ["pools"], queryFn: () => api.get<any[]>("/equipment/pools") });

  const patch = useMutation({
    mutationFn: ({ id, body }: { id: string; body: any }) => api.patch(`/equipment/assets/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["assets"] }),
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-bold text-[#172033]">تجهیزات و آزمایشگاه</h1>
        <select className="input max-w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">همه وضعیت‌ها</option>
          {Object.entries(STATUS_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {/* استخرهای شمارشی */}
      <section className="grid md:grid-cols-3 gap-3">
        {pools.data?.map((p) => (
          <div key={p.id} className="card p-4">
            <div className="font-bold text-slate-800">{p.name}</div>
            <div className="text-xs text-slate-500">{p.type.name}</div>
            <div className="text-sm mt-2">موجودی کل: <b>{toFaDigits(p.total_quantity)}</b> · تخصیص فعال: <b>{toFaDigits(p.active_allocations)}</b></div>
            <div className="h-2 rounded-full bg-slate-200 mt-2 overflow-hidden">
              <div className="h-full bg-[#3563E9]" style={{ width: `${Math.min(100, (p.active_allocations / Math.max(p.total_quantity, 1)) * 100)}%` }} aria-hidden />
            </div>
          </div>
        ))}
      </section>

      {assets.isLoading ? <Spinner /> : assets.data!.items.length === 0 ? (
        <div className="card"><EmptyState title="تجهیزی یافت نشد" icon="🧪" /></div>
      ) : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[860px]">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-right p-3">نام</th><th className="text-right p-3 hidden md:table-cell">کد اموال</th>
                <th className="text-right p-3">نوع</th><th className="text-right p-3">وضعیت</th>
                <th className="text-right p-3 hidden lg:table-cell">کالیبراسیون بعدی</th>
                <th className="text-right p-3 hidden md:table-cell">مسئول</th>
                <th className="text-right p-3">اقدام</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {assets.data!.items.map((a) => {
                const overdue = a.next_calibration_due && new Date(a.next_calibration_due) < new Date();
                return (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="p-3">
                      <div className="font-medium">{a.name}</div>
                      {a.serial_number && <div className="text-[11px] text-slate-400 font-mono">SN: {a.serial_number}</div>}
                    </td>
                    <td className="p-3 hidden md:table-cell font-mono text-xs">{a.asset_tag || "—"}</td>
                    <td className="p-3"><Chip tone="slate">{a.type.name}</Chip> <Chip tone="blue">{CAT_FA[a.type.category]}</Chip></td>
                    <td className="p-3"><StatusChip value={a.status} fa={STATUS_FA[a.status]} /></td>
                    <td className="p-3 hidden lg:table-cell">
                      {a.next_calibration_due ? (
                        <span className={overdue ? "text-red-700 font-bold" : ""}>
                          {jalali(a.next_calibration_due)} {overdue ? "⚠ منقضی" : ""}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="p-3 hidden md:table-cell text-xs">{a.responsible_person || "—"}</td>
                    <td className="p-3">
                      <div className="flex gap-1.5">
                        {a.status !== "broken" && (
                          <button className="btn-ghost !py-1 text-[11px]" onClick={() => patch.mutate({ id: a.id, body: { status: "broken" } })}>
                            ثبت خرابی
                          </button>
                        )}
                        {a.status === "broken" && (
                          <button className="btn-teal !py-1 text-[11px]" onClick={() => patch.mutate({ id: a.id, body: { status: "operational" } })}>
                            بازگشت به سرویس
                          </button>
                        )}
                        {a.status === "operational" && (
                          <button className="btn-ghost !py-1 text-[11px]" onClick={() => patch.mutate({ id: a.id, body: { status: "needs_service" } })}>
                            نیازمند سرویس
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-slate-500">
        ثبت خرابی تجهیز ثابت، «ظرفیت تجهیزاتی» فضای استقرار را هم از جست‌وجو حذف می‌کند و در مرکز اقدام مدیر دیده می‌شود.
        موجودی تجهیزات شمارشی در لحظه تأیید رزرو، با قفل تراکنشی کنترل می‌شود.
      </p>
    </div>
  );
}
