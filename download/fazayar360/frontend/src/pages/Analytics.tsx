import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { toFaDigits, FA_WEEKDAYS } from "../format";
import { Chip, EmptyState, ErrorState, Field, Spinner } from "../ui";

export default function Analytics() {
  const today = new Date();
  const monthAgo = new Date(today.getTime() - 30 * 86400000);
  const [range, setRange] = useState({
    from: monthAgo.toISOString().slice(0, 10),
    to: today.toISOString().slice(0, 10),
  });
  const [groupBy, setGroupBy] = useState("building");

  const util = useQuery({
    queryKey: ["util", range, groupBy],
    queryFn: () => api.get<any>(`/analytics/utilization?date_from=${range.from}&date_to=${range.to}&group_by=${groupBy}`),
    enabled: !!range.from && !!range.to,
  });
  const heat = useQuery({
    queryKey: ["heat", range],
    queryFn: () => api.get<any[]>(`/analytics/heatmap?date_from=${range.from}&date_to=${range.to}`),
  });
  const quality = useQuery({ queryKey: ["quality"], queryFn: () => api.get<any>("/analytics/quality") });

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-[#172033]">تحلیل ظرفیت و بهره‌برداری</h1>

      <div className="card p-4 grid md:grid-cols-4 gap-3">
        <Field label="از تاریخ"><input type="date" className="input" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field>
        <Field label="تا تاریخ"><input type="date" className="input" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field>
        <Field label="تجمیع بر اساس">
          <select className="input" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="building">ساختمان</option><option value="campus">پردیس</option>
            <option value="space_type">نوع فضا</option>
          </select>
        </Field>
      </div>

      {util.isLoading ? <Spinner /> : util.isError ? <ErrorState message={(util.error as any).message} /> : (
        <div className="card overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[880px]">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th className="text-right p-3">گروه</th>
                <th className="text-right p-3">ساعات قابل‌رزرو</th>
                <th className="text-right p-3">اشغال برنامه‌ریزی‌شده</th>
                <th className="text-right p-3">استفاده واقعی</th>
                <th className="text-right p-3 hidden md:table-cell">مبنا</th>
                <th className="text-right p-3 hidden md:table-cell">صندلی‌ـ‌ساعت</th>
                <th className="text-right p-3">نرخ لغو</th>
                <th className="text-right p-3 hidden md:table-cell">ازکارافتادگی</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {util.data!.rows.map((r: any) => (
                <tr key={r.key} className="hover:bg-slate-50">
                  <td className="p-3 font-medium">{r.key_label || r.key}</td>
                  <td className="p-3">{toFaDigits(r.bookable_hours)}</td>
                  <td className="p-3"><b className={r.planned_utilization_pct > 80 ? "text-amber-700" : ""}>{toFaDigits(r.planned_utilization_pct)}٪</b></td>
                  <td className="p-3">{toFaDigits(r.actual_utilization_pct)}٪</td>
                  <td className="p-3 hidden md:table-cell"><Chip tone={r.actual_data_basis === "مشاهده واقعی" ? "teal" : "amber"}>{r.actual_data_basis}</Chip></td>
                  <td className="p-3 hidden md:table-cell">{toFaDigits(r.seat_utilization_pct)}٪</td>
                  <td className="p-3">{toFaDigits(r.cancellation_rate_pct)}٪</td>
                  <td className="p-3 hidden md:table-cell">{toFaDigits(r.downtime_hours)} ساعت</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="p-3 text-xs text-slate-500 border-t">
            اگر داده حضور واقعی موجود نباشد، شاخص صریحاً «برآورد مبتنی بر ثبت‌نام» نمایش داده می‌شود.
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <h2 className="font-bold text-[#172033] mb-3">نقشه حرارتی استفاده (روز × ساعت)</h2>
          {heat.isLoading ? <Spinner /> : <HeatChart data={heat.data || []} />}
        </div>
        <div className="card p-4">
          <h2 className="font-bold text-[#172033] mb-3">کیفیت و کامل‌بودن داده</h2>
          {quality.isLoading ? <Spinner /> : quality.data && (
            <ul className="text-sm space-y-2">
              <li className="flex justify-between"><span>فضاهای بدون چیدمان</span><b>{toFaDigits(quality.data.missing_layouts_count)}</b></li>
              <li className="flex justify-between"><span>فضاهای بدون امکانات</span><b>{toFaDigits(quality.data.missing_features_count)}</b></li>
              <li className="flex justify-between"><span>فضاهای بدون تصویر</span><b>{toFaDigits(quality.data.missing_image_count)}</b></li>
              <li className="flex justify-between"><span>مراجع خارجی ناسازگار</span><b>{toFaDigits(quality.data.external_refs_stale)} / {toFaDigits(quality.data.external_refs_total)}</b></li>
              <li className="pt-2"><Chip tone={quality.data.completeness_pct > 80 ? "green" : "amber"}>کامل‌بودن چیدمان و امکانات: {toFaDigits(quality.data.completeness_pct)}٪</Chip></li>
            </ul>
          )}
          <p className="text-xs text-slate-500 mt-3">گزارش‌ها منبع داده (مشاهده/برآورد) و دوره را مشخص می‌کنند؛ پیش از تصمیم، علت و محدودیت‌ها بررسی شود.</p>
        </div>
      </div>
    </div>
  );
}

function HeatChart({ data }: { data: { weekday_fa: number; hour: number; hours: number }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let chart: any;
    import("echarts").then((echarts) => {
      if (!ref.current) return;
      chart = echarts.init(ref.current);
      const maxH = Math.max(1, ...data.map((d) => d.hours));
      chart.setOption({
        grid: { top: 24, left: 8, right: 8, bottom: 8, containLabel: true },
        tooltip: { formatter: (p: any) => `${FA_WEEKDAYS[p.data[0]]} ساعت ${p.data[1]}: ${p.data[2]} ساعت اشغال` },
        xAxis: { type: "category", data: FA_WEEKDAYS, inverse: true },
        yAxis: { type: "category", data: Array.from({ length: 15 }, (_, i) => i + 7) },
        visualMap: { min: 0, max: maxH, calculable: false, orient: "horizontal", show: false, inRange: { color: ["#F5F7FB", "#14B8A6", "#3563E9", "#172033"] } },
        series: [{ type: "heatmap", data: data.map((d) => [d.weekday_fa, d.hour, d.hours]),
                   label: { show: true, fontSize: 9, formatter: (p: any) => (p.data[2] >= 1 ? Math.round(p.data[2]) : "") } }],
      });
      window.addEventListener("resize", () => chart?.resize());
    });
    return () => { chart?.dispose?.(); };
  }, [data]);
  if (data.length === 0) return <EmptyState title="داده‌ای برای این دوره نیست" icon="📊" />;
  return <div ref={ref} className="h-72" dir="ltr" />;
}
