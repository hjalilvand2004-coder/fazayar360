import { ReactNode } from "react";

export function Spinner({ label = "در حال بارگذاری…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-500">
      <div className="h-8 w-8 rounded-full border-4 border-blue-200 border-t-[#3563E9] animate-spin" aria-hidden />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({ title, hint, icon = "🗂" }: { title: string; hint?: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 gap-2 text-center">
      <div className="text-4xl" aria-hidden>{icon}</div>
      <div className="font-medium text-slate-700">{title}</div>
      {hint && <div className="text-sm text-slate-500 max-w-md">{hint}</div>}
    </div>
  );
}

export function ErrorState({ message, requestId }: { message: string; requestId?: string }) {
  return (
    <div className="card p-5 border-red-200 bg-red-50 text-red-800" role="alert">
      <div className="font-medium">⚠️ خطا در دریافت داده</div>
      <div className="text-sm mt-1">{message}</div>
      {requestId && <div className="text-xs mt-2 opacity-70">شناسه رهگیری: {requestId}</div>}
    </div>
  );
}

const CHIP_STYLES: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-800 border-emerald-300",
  blue: "bg-blue-50 text-blue-800 border-blue-300",
  amber: "bg-amber-50 text-amber-900 border-amber-300",
  red: "bg-red-50 text-red-800 border-red-300",
  slate: "bg-slate-100 text-slate-700 border-slate-300",
  teal: "bg-teal-50 text-teal-800 border-teal-300",
};

export function Chip({ tone = "slate", children, icon }: { tone?: keyof typeof CHIP_STYLES; children: ReactNode; icon?: string }) {
  return (
    <span className={`status-chip ${CHIP_STYLES[tone]}`}>
      {icon && <span aria-hidden>{icon}</span>}
      {children}
    </span>
  );
}

export function StatusChip({ value, fa }: { value: string; fa: string }) {
  const tone =
    ["active", "approved", "executed", "operational", "resolved"].includes(value) ? "green"
    : ["submitted", "under_review", "scheduled", "limited", "needs_service"].includes(value) ? "amber"
    : ["rejected", "cancelled", "broken", "under_repair", "no_show", "inactive"].includes(value) ? "red"
    : ["reported"].includes(value) ? "amber"
    : "slate";
  const icon =
    tone === "green" ? "●" : tone === "amber" ? "▲" : tone === "red" ? "✕" : "○";
  return <Chip tone={tone} icon={icon}>{fa}</Chip>;
}

export function Modal({ open, onClose, title, children, wide }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40" onClick={onClose} aria-hidden />
      <div role="dialog" aria-modal="true" aria-label={title}
           className={`relative bg-white rounded-2xl shadow-xl w-full ${wide ? "max-w-3xl" : "max-w-lg"} max-h-[90vh] overflow-auto p-5`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-[#172033]">{title}</h2>
          <button onClick={onClose} className="btn-ghost !px-3 !py-1" aria-label="بستن">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}

export function Kpi({ title, value, hint, tone = "blue" }: {
  title: string; value: ReactNode; hint?: string; tone?: "blue" | "teal" | "amber" | "red";
}) {
  const ring = { blue: "border-blue-200", teal: "border-teal-200", amber: "border-amber-200", red: "border-red-200" }[tone];
  return (
    <div className={`card p-4 border-r-4 ${ring}`}>
      <div className="text-xs text-slate-500">{title}</div>
      <div className="text-2xl font-bold text-[#172033] mt-1">{value}</div>
      {hint && <div className="text-xs text-slate-400 mt-1">{hint}</div>}
    </div>
  );
}
