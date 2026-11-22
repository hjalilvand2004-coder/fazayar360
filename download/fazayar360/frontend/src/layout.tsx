import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "./auth";
import { ROLE_FA } from "./format";
import { Chip } from "./ui";

const NAV = [
  { to: "/", label: "خانه و مرکز اقدام", icon: "🏠", roles: null },
  { to: "/university", label: "نمای دانشگاه", icon: "🏛", roles: null },
  { to: "/search", label: "فضای مناسب پیدا کن", icon: "🔎", roles: null },
  { to: "/calendar", label: "تقویم عملیاتی", icon: "🗓", roles: null },
  { to: "/requests", label: "درخواست‌ها", icon: "📥", roles: null },
  { to: "/booking-new", label: "درخواست جدید", icon: "➕", roles: null },
  { to: "/blocks", label: "انسداد و خرابی‌ها", icon: "🚧", roles: ["sys_admin", "facility_manager", "lab_manager", "education_expert", "education_manager"] },
  { to: "/equipment", label: "تجهیزات", icon: "🧪", roles: ["sys_admin", "lab_manager", "education_expert", "education_manager", "university_admin"] },
  { to: "/analytics", label: "تحلیل ظرفیت", icon: "📊", roles: ["sys_admin", "education_manager", "education_expert", "university_admin", "facility_manager", "lab_manager"] },
  { to: "/optimizer", label: "سناریوسازی و بهینه‌سازی", icon: "🧠", roles: ["sys_admin", "education_manager", "education_expert"] },
  { to: "/admin", label: "مدیریت و ممیزی", icon: "⚙️", roles: ["sys_admin", "university_admin"] },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const items = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)));

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="lg:w-60 shrink-0 bg-[#172033] text-slate-200 lg:min-h-screen">
        <div className="flex items-center gap-2 px-5 py-4 border-b border-white/10">
          <div className="h-9 w-9 rounded-xl bg-[#3563E9] grid place-items-center text-white font-bold">ف</div>
          <div>
            <div className="font-bold text-white">فضایار۳۶۰</div>
            <div className="text-[10px] text-slate-400">زیست‌بوم دانشجو۳۶۰</div>
          </div>
        </div>
        <nav className="px-2 py-3 flex lg:flex-col gap-1 overflow-x-auto" aria-label="منوی اصلی">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2 rounded-xl px-3 py-2 text-sm whitespace-nowrap transition ${
                  isActive ? "bg-[#3563E9] text-white font-medium" : "hover:bg-white/10 text-slate-300"
                }`}>
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="sticky top-0 z-20 bg-white/90 backdrop-blur border-b border-slate-200 px-4 lg:px-6 py-3 flex items-center justify-between gap-3">
          <div className="text-sm text-slate-500 hidden md:block">
            «فضای مناسب، در زمان مناسب، با تجهیزات آماده و تخصیص قابل‌اعتماد»
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-sm font-medium text-slate-800">{user?.display_name}</div>
              <div className="text-xs text-slate-500">{ROLE_FA[user?.role || ""]}</div>
            </div>
            <Chip tone="blue" icon="👤">{user?.username}</Chip>
            <button className="btn-ghost !py-1.5" onClick={() => { logout(); nav("/"); }}>خروج</button>
          </div>
        </header>
        <main className="p-4 lg:p-6 flex-1 min-w-0">
          <Outlet />
        </main>
        <footer className="px-6 py-3 text-xs text-slate-400 border-t border-slate-200">
          فضایار۳۶۰ — زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی · نسخه ۱
        </footer>
      </div>
    </div>
  );
}
