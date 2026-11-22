import { useMemo } from "react";
import { addDays, FA_WEEKDAYS, faWeekdayOf, hhmm, isoDate, jalali, toFaDigits } from "../format";

export type CalEvent = {
  allocation_id: string;
  space?: { id: string; name: string; code: string };
  kind: string;
  start: string;
  end: string;
  title: string;
  request_number?: string | null;
  use_type?: string | null;
};

const START_HOUR = 7;
const END_HOUR = 22;
const HOUR_PX = 52;

/** تقویم هفتگی (شنبه تا جمعه) با نمایش رزرو و انسداد — پشتیبانی از کلیک روی رخداد و خانه‌ی خالی */
export default function WeekGrid({ weekStart, events, onEventClick, onSlotClick, highlightSpace }: {
  weekStart: Date;
  events: CalEvent[];
  onEventClick?: (e: CalEvent) => void;
  onSlotClick?: (day: Date, hour: number) => void;
  highlightSpace?: string | null;
}) {
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)), [weekStart]);
  const rows = END_HOUR - START_HOUR;
  const todayIso = isoDate(new Date());

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[860px]" role="table" aria-label="تقویم هفتگی">
        {/* سرستون روزها */}
        <div className="grid" style={{ gridTemplateColumns: "64px repeat(7, 1fr)" }}>
          <div />
          {days.map((d) => (
            <div key={d.toISOString()} className={`text-center text-sm py-2 rounded-t-xl border-b ${
              isoDate(d) === todayIso ? "bg-blue-50 font-bold text-blue-800" : "bg-slate-50 text-slate-600"}`}>
              <div>{FA_WEEKDAYS[faWeekdayOf(d)]}</div>
              <div className="text-[10px] text-slate-400 font-normal">{jalali(d)}</div>
            </div>
          ))}
        </div>

        {/* بدنه */}
        <div className="grid relative" style={{ gridTemplateColumns: "64px repeat(7, 1fr)" }}>
          {/* ستون ساعت‌ها */}
          <div>
            {Array.from({ length: rows }, (_, i) => (
              <div key={i} className="h-[52px] text-[10px] text-slate-400 text-left pr-1 border-b border-slate-100 pt-0.5">
                {toFaDigits(String(i + START_HOUR).padStart(2, "0"))}:۰۰
              </div>
            ))}
          </div>

          {days.map((d) => {
            const dayIso = isoDate(d);
            const dayEvents = events.filter((e) => e.start.slice(0, 10) === dayIso);
            return (
              <div key={d.toISOString()} className={`relative border-r border-slate-100 ${isoDate(d) === todayIso ? "bg-blue-50/40" : ""}`}
                   style={{ height: rows * HOUR_PX }}>
                {/* خطوط ساعت */}
                {Array.from({ length: rows }, (_, i) => (
                  <div key={i} className="absolute left-0 right-0 border-b border-slate-100"
                       style={{ top: i * HOUR_PX, height: HOUR_PX }}
                       onClick={() => onSlotClick?.(d, i + START_HOUR)} />
                ))}
                {/* رخدادها */}
                {dayEvents.map((e) => {
                  const st = new Date(e.start);
                  const en = new Date(e.end);
                  const top = ((st.getHours() + st.getMinutes() / 60) - START_HOUR) * HOUR_PX;
                  const height = Math.max(((en.getTime() - st.getTime()) / 3600000) * HOUR_PX - 4, 20);
                  const isBlock = e.kind === "maintenance";
                  return (
                    <button key={e.allocation_id}
                      onClick={(ev) => { ev.stopPropagation(); onEventClick?.(e); }}
                      className={`absolute left-1 right-1 rounded-lg px-1.5 py-1 text-[11px] text-right overflow-hidden border ${
                        isBlock
                          ? "bg-red-50 border-red-300 text-red-800"
                          : e.use_type === "exam" ? "bg-violet-50 border-violet-300 text-violet-900"
                          : "bg-teal-50 border-teal-300 text-teal-900"
                      } hover:shadow-md transition text-start`}
                      style={{ top: top + 2, height }}
                      title={`${e.title} — ${hhmm(e.start)} تا ${hhmm(e.end)}`}>
                      <div className="font-bold truncate">{isBlock ? "🚧 " : ""}{e.title}</div>
                      <div className="opacity-70 truncate">{hhmm(e.start)}–{hhmm(e.end)}</div>
                      {highlightSpace && e.space && e.space.id === highlightSpace && (
                        <div className="text-[10px] opacity-80 truncate">{e.space.name}</div>
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
