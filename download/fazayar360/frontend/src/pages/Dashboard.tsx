import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { api, HttpError } from "../api";
import { Chip, EmptyState, ErrorState, Kpi, Spinner } from "../ui";
import { jalaliFull, hhmm, REQ_STATUS_FA, SPACE_TYPE_FA } from "../format";

type Alert = {
  code: string; severity: string; title: string; detail?: string;
  actions?: { code: string; label: string; target: string }[];
  sessions?: any[];
};

type ReqItem = {
  id: string; request_number: string; title: string; status: string;
  use_type: string; expected_attendees: number;
  requested_space?: { name: string } | null;
  occurrences: { start: string }[];
};

export default function Dashboard() {
  const nav = useNavigate();
  const alerts = useQuery({
    queryKey: ["action-center"],
    queryFn: () => api.get<Alert[]>("/analytics/action-center"),
    refetchInterval: 120_000,
  });
  const spaces = useQuery({ queryKey: ["spaces", "brief"], queryFn: () => api.get<{ items: any[]; total: number }>("/spaces?size=1") });
  const pending = useQuery({
    queryKey: ["requests", "submitted"],
    queryFn: () => api.get<{ items: ReqItem[]; total: number }>("/booking-requests?status=submitted&size=5"),
  });
  const today = new Date();
  const cal = useQuery({
    queryKey: ["global-cal", today.toISOString().slice(0, 10)],
    queryFn: () => api.get<{ events: any[] }>(
      `/calendar/global?date_from=${today.toISOString().slice(0, 10)}&date_to=${today.toISOString().slice(0, 10)}`),
  });

  if (alerts.isLoading) return <Spinner />;
  if (alerts.isError) return <ErrorState message={(alerts.error as HttpError).message} />;

  const events = cal.data?.events || [];

  return (
    <div className="space-y-6">
      {/* جست‌وجوی سریع / دستیار */}
      <section className="card p-5 bg-gradient-to-l from-blue-50 to-white">
        <h2 className="font-bold text-[#172033]">دستیار «فضای مناسب پیدا کن»</h2>
        <p className="text-xs text-slate-500 mt-1">به زبان ساده بنویسید؛ مثلاً: «برای سه‌شنبه ساعت ۱۰، یک کلاس برای ۳۲ نفر با نمایشگر می‌خواهم»</p>
        <div className="mt-3 flex gap-2">
          <input id="quick-search" className="input" placeholder="مثال: فردا ساعت ۱۴ کارگاه برای ۲۵ نفر با ویدئوپروژکتور"
                 onKeyDown={(e) => {
                   if (e.key === "Enter") nav(`/search?q=${encodeURIComponent((e.target as HTMLInputElement).value)}`);
                 }} />
          <button className="btn-primary" onClick={() => {
            const v = (document.getElementById("quick-search") as HTMLInputElement).value;
            nav(`/search?q=${encodeURIComponent(v)}`);
          }}>جست‌وجو</button>
        </div>
      </section>

      {/* شاخص‌های کلی */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Kpi title="فضاهای آموزشی ثبت‌شده" value={spaces.data?.total ? spaces.data.total : "—"} />
        <Kpi title="جلسات امروز" value={events.filter((e) => e.kind === "booking").length} tone="teal" />
        <Kpi title="انسداد فعال امروز" value={events.filter((e) => e.kind === "maintenance").length} tone="amber" />
        <Kpi title="درخواست‌های در انتظار بررسی" value={pending.data?.total ?? "—"} tone="red" />
      </section>

      {/* مرکز اقدام */}
      <section>
        <h2 className="font-bold text-[#172033] mb-2">مرکز اقدام</h2>
        {alerts.data!.length === 0 ? (
          <div className="card"><EmptyState title="هشدار قابل اقدامی نیست" hint="همه چیز در وضعیت مطلوب است." icon="✅" /></div>
        ) : (
          <div className="grid md:grid-cols-2 gap-3">
            {alerts.data!.map((a) => (
              <div key={a.code} className={`card p-4 border-r-4 ${
                a.severity === "danger" ? "border-r-red-500" : a.severity === "warning" ? "border-r-amber-500" : "border-r-blue-500"
              }`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium text-slate-800">
                      {a.severity === "danger" ? "🔴 " : a.severity === "warning" ? "🟠 " : "🔵 "}{a.title}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">{a.detail}</div>
                  </div>
                </div>
                {a.actions?.length ? (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {a.actions.map((act) => (
                      <button key={act.code} className="btn-primary !py-1.5 !px-3 text-xs" onClick={() => nav(act.target)}>
                        {act.label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* درخواست‌های نیازمند بررسی + برنامه امروز */}
      <section className="grid lg:grid-cols-2 gap-4">
        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-[#172033]">درخواست‌های نیازمند بررسی</h3>
            <Link to="/requests" className="text-xs text-blue-600 hover:underline">همه →</Link>
          </div>
          {pending.data?.items.length === 0 ? (
            <EmptyState title="درخواست بازی ندارید" icon="📭" />
          ) : (
            <ul className="divide-y divide-slate-100">
              {pending.data?.items.map((r) => (
                <li key={r.id} className="py-2.5 flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{r.title}</div>
                    <div className="text-xs text-slate-500">
                      {r.request_number} · {SPACE_TYPE_FA[r.use_type] || r.use_type} · {r.requested_space?.name || "بدون فضا"}
                    </div>
                  </div>
                  <Chip tone="amber">{REQ_STATUS_FA[r.status]}</Chip>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-[#172033]">برنامه امروز — {jalaliFull(today)}</h3>
            <Link to="/calendar" className="text-xs text-blue-600 hover:underline">تقویم →</Link>
          </div>
          {events.length === 0 ? (
            <EmptyState title="امروز جلسه‌ای ثبت نشده" icon="🌤" />
          ) : (
            <ul className="divide-y divide-slate-100 max-h-72 overflow-auto">
              {events.sort((a, b) => a.start.localeCompare(b.start)).map((e) => (
                <li key={e.allocation_id} className="py-2 flex items-center gap-3 text-sm">
                  <span className="font-mono text-xs text-slate-500 w-24">{hhmm(e.start)}–{hhmm(e.end)}</span>
                  <span className={`h-2 w-2 rounded-full ${e.kind === "maintenance" ? "bg-red-500" : "bg-teal-500"}`} aria-hidden />
                  <span className="truncate flex-1">{e.title}</span>
                  <span className="text-xs text-slate-500 hidden sm:block">{e.space.name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
