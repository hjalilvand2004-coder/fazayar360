import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { addDays, isoAt, jalali, thisSaturday, hhmm, REQ_STATUS_FA } from "../format";
import { Chip, EmptyState, Modal, Spinner } from "../ui";
import WeekGrid, { CalEvent } from "../components/WeekGrid";

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(thisSaturday());
  const [buildingId, setBuildingId] = useState("");
  const [detail, setDetail] = useState<CalEvent | null>(null);

  const campuses = useQuery({ queryKey: ["campuses"], queryFn: () => api.get<any[]>("/structure/campuses") });
  const cal = useQuery({
    queryKey: ["global-cal", isoAt(weekStart).slice(0, 10), buildingId],
    queryFn: () => api.get<{ events: CalEvent[] }>(
      `/calendar/global?date_from=${isoAt(weekStart).slice(0, 10)}&date_to=${isoAt(addDays(weekStart, 6)).slice(0, 10)}${
        buildingId ? `&building_id=${buildingId}` : ""}`),
  });

  const buildings = useMemo(() => campuses.data?.flatMap((c) => c.buildings) || [], [campuses.data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-[#172033]">تقویم عملیاتی — هفته‌ی {jalali(weekStart)}</h1>
        <div className="flex flex-wrap gap-2">
          <select className="input max-w-56" value={buildingId} onChange={(e) => setBuildingId(e.target.value)}>
            <option value="">همه ساختمان‌ها</option>
            {buildings.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(addDays(weekStart, -7))}>هفته قبل</button>
          <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(thisSaturday())}>هفته جاری</button>
          <button className="btn-ghost !py-1.5 text-xs" onClick={() => setWeekStart(addDays(weekStart, 7))}>هفته بعد</button>
        </div>
      </div>

      <div className="card p-4">
        {cal.isLoading ? <Spinner /> : (cal.data?.events.length || 0) === 0
          ? <EmptyState title="رخدادی در این هفته ثبت نشده" icon="🗓" />
          : <WeekGrid weekStart={weekStart} events={cal.data!.events} onEventClick={setDetail} />}
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-teal-100 border border-teal-300 inline-block" aria-hidden /> رزرو تأییدشده</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-red-100 border border-red-300 inline-block" aria-hidden /> انسداد تعمیراتی/آماده‌سازی</span>
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-violet-100 border border-violet-300 inline-block" aria-hidden /> آزمون</span>
      </div>

      <Modal open={!!detail} onClose={() => setDetail(null)} title="جزئیات رخداد">
        {detail && (
          <div className="text-sm space-y-2">
            <div className="font-bold text-slate-800">{detail.title}</div>
            <div className="text-slate-600">فضا: {detail.space?.name} ({detail.space?.code})</div>
            <div className="text-slate-600">{jalali(detail.start)} — ساعت {hhmm(detail.start)} تا {hhmm(detail.end)}</div>
            <div className="flex gap-2">
              <Chip tone={detail.kind === "maintenance" ? "red" : "teal"}>
                {detail.kind === "maintenance" ? "انسداد" : detail.kind === "hold" ? "نگهداشت موقت" : "رزرو قطعی"}
              </Chip>
              {detail.request_number && <Chip tone="slate">{detail.request_number}</Chip>}
            </div>
            <p className="text-xs text-slate-500">
              تقویم اشغال فضا یک مرجع واحد است؛ تغییر این رخداد تنها از طریق درخواست‌ها (جابه‌جایی جلسه با بررسی مجدد تعارض) انجام می‌شود.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
