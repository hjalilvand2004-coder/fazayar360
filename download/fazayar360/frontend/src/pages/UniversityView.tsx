import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { EmptyState, ErrorState, Spinner, StatusChip, Chip } from "../ui";
import { SPACE_TYPE_FA, SPACE_STATUS_FA, toFaDigits } from "../format";

type CampusTree = {
  id: string; code: string; name: string;
  buildings: { id: string; code: string; name: string; responsible_unit?: string;
               floors: { id: string; number: number; name: string }[] }[];
};
type FloorMap = {
  building: { id: string; name: string };
  floors: { id: string; number: number; name: string;
            spaces: { id: string; code: string; name: string; space_type: string; status: string;
                      map_x: number; map_y: number; map_w: number; map_h: number }[] }[];
};
type SpaceRow = {
  id: string; code: string; name: string; space_type: string; status: string;
  building_name: string; campus_name: string; safe_capacity?: number; needs_lab_manager: boolean;
};

const TYPE_COLORS: Record<string, string> = {
  general_classroom: "fill-blue-400", smart_classroom: "fill-indigo-500",
  laboratory: "fill-teal-500", workshop: "fill-orange-400", computer_site: "fill-cyan-500",
  seminar_hall: "fill-violet-500", studio: "fill-pink-400", group_study: "fill-emerald-400",
};

export default function UniversityView() {
  const [mode, setMode] = useState<"cards" | "map" | "list">("cards");
  const [typeFilter, setTypeFilter] = useState("");
  const [q, setQ] = useState("");

  const campuses = useQuery({ queryKey: ["campuses"], queryFn: () => api.get<CampusTree[]>("/structure/campuses") });
  const spaces = useQuery({
    queryKey: ["spaces-list", typeFilter, q],
    queryFn: () => api.get<{ items: SpaceRow[]; total: number }>(
      `/spaces?size=200${typeFilter ? `&space_type=${typeFilter}` : ""}${q ? `&q=${encodeURIComponent(q)}` : ""}`),
  });

  if (campuses.isLoading || spaces.isLoading) return <Spinner />;
  if (campuses.isError) return <ErrorState message={(campuses.error as any).message} />;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-[#172033]">نمای دانشگاه</h1>
        <div className="flex rounded-xl border border-slate-300 overflow-hidden" role="tablist" aria-label="نمایش">
          {([["cards", "کارت‌های تصویری"], ["map", "نقشه طبقات"], ["list", "فهرست"]] as const).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={mode === k} onClick={() => setMode(k)}
              className={`px-3 py-1.5 text-sm ${mode === k ? "bg-[#3563E9] text-white" : "bg-white hover:bg-slate-50"}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <input className="input max-w-xs" placeholder="جست‌وجوی نام یا کد فضا…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="input max-w-xs" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">همه انواع فضا</option>
          {Object.entries(SPACE_TYPE_FA).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </div>

      {mode !== "map" && (
        <div className={mode === "cards" ? "grid sm:grid-cols-2 xl:grid-cols-3 gap-3" : ""}>
          {spaces.data!.items.length === 0 && <div className="card col-span-full"><EmptyState title="فضایی یافت نشد" /></div>}
          {mode === "cards" && spaces.data!.items.map((s) => (
            <Link key={s.id} to={`/spaces/${s.id}`} className="card p-4 hover:shadow-md transition block">
              <div className="h-24 rounded-xl bg-gradient-to-tr from-blue-100 via-teal-50 to-amber-50 grid place-items-center mb-3" aria-hidden>
                <div className="text-3xl">{s.space_type === "laboratory" ? "🧪" : s.space_type === "computer_site" ? "💻" :
                  s.space_type === "seminar_hall" ? "🎤" : s.space_type === "studio" ? "🎬" : s.space_type === "workshop" ? "🔧" : "🪑"}</div>
              </div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-bold text-slate-800">{s.name}</div>
                  <div className="text-xs text-slate-500">{s.campus_name} · {s.building_name}</div>
                </div>
                <StatusChip value={s.status} fa={SPACE_STATUS_FA[s.status]} />
              </div>
              <div className="flex flex-wrap gap-1.5 mt-3">
                <Chip tone="blue">{SPACE_TYPE_FA[s.space_type]}</Chip>
                <Chip tone="slate">کد: {s.code}</Chip>
                {s.needs_lab_manager && <Chip tone="amber" icon="⚠">نیاز به مسئول آزمایشگاه</Chip>}
              </div>
            </Link>
          ))}
          {mode === "list" && (
            <div className="card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr><th className="text-right p-3">کد</th><th className="text-right p-3">نام</th>
                      <th className="text-right p-3 hidden md:table-cell">نوع</th>
                      <th className="text-right p-3 hidden md:table-cell">ساختمان</th>
                      <th className="text-right p-3">وضعیت</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {spaces.data!.items.map((s) => (
                    <tr key={s.id} className="hover:bg-blue-50/50">
                      <td className="p-3 font-mono text-xs">{s.code}</td>
                      <td className="p-3"><Link to={`/spaces/${s.id}`} className="text-blue-700 hover:underline">{s.name}</Link></td>
                      <td className="p-3 hidden md:table-cell">{SPACE_TYPE_FA[s.space_type]}</td>
                      <td className="p-3 hidden md:table-cell">{s.building_name}</td>
                      <td className="p-3"><StatusChip value={s.status} fa={SPACE_STATUS_FA[s.status]} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {mode === "map" && (
        <div className="space-y-6">
          {campuses.data!.map((c) => (
            <div key={c.id}>
              <h2 className="font-bold text-slate-700 mb-2">{c.name}</h2>
              <div className="grid md:grid-cols-2 gap-4">
                {c.buildings.map((b) => <BuildingMap key={b.id} campusId={c.id} building={b} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BuildingMap({ campusId, building }: { campusId: string; building: CampusTree["buildings"][number] }) {
  const [floorIdx, setFloorIdx] = useState(0);
  const fmap = useQuery({
    queryKey: ["floormap", building.id],
    queryFn: () => api.get<FloorMap>(`/structure/buildings/${building.id}/floormap`),
  });
  if (fmap.isLoading) return <div className="card p-6"><Spinner label="در حال ترسیم نقشه…" /></div>;
  if (fmap.isError) return <div className="card p-6 text-sm text-slate-500">نقشه در دسترس نیست</div>;
  const floors = fmap.data!.floors;
  const cur = floors[Math.min(floorIdx, floors.length - 1)];
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="font-bold text-slate-800">{building.name}</div>
        <div className="flex gap-1">
          {floors.map((f, i) => (
            <button key={f.id} onClick={() => setFloorIdx(i)}
              className={`text-xs rounded-lg px-2.5 py-1 border ${i === floorIdx ? "bg-[#3563E9] text-white border-blue-600" : "border-slate-300 hover:bg-slate-50"}`}>
              طبقه {toFaDigits(f.number)}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-auto">
        <svg viewBox="0 0 640 400" className="w-full min-w-[420px] rounded-xl bg-[#F5F7FB] border border-slate-200" role="img"
             aria-label={`نقشه ${cur?.name || ""} — ${building.name}`}>
          {cur?.spaces.map((s) => (
            <g key={s.id} className="cursor-pointer" tabIndex={0}
               role="link" aria-label={s.name}
               onClick={() => (window.location.hash = `#/spaces/${s.id}`)}
               onKeyDown={(e) => { if (e.key === "Enter") (window.location.hash = `#/spaces/${s.id}`); }}>
              <rect x={s.map_x} y={s.map_y} width={s.map_w} height={s.map_h}
                    className={`${TYPE_COLORS[s.space_type] || "fill-slate-400"} opacity-80 hover:opacity-100`}
                    rx="10" stroke="#172033" strokeOpacity="0.35" strokeWidth="2" />
              <text x={s.map_x + s.map_w / 2} y={s.map_y + s.map_h / 2 - 4} textAnchor="middle"
                    className="fill-white text-[13px] font-bold" style={{ direction: "rtl" }}>{s.name}</text>
              <text x={s.map_x + s.map_w / 2} y={s.map_y + s.map_h / 2 + 14} textAnchor="middle"
                    className="fill-white/90 text-[10px]">{SPACE_TYPE_FA[s.space_type]}</text>
            </g>
          ))}
          {cur?.spaces.length === 0 && (
            <text x="320" y="200" textAnchor="middle" className="fill-slate-400 text-sm">فضایی در این طبقه ثبت نشده</text>
          )}
        </svg>
      </div>
    </div>
  );
}
