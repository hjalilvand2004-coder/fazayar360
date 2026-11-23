import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "./auth";
import { useTheme } from "./theme";
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

function ThemeButton() {
  const { toggle } = useTheme();
  const [isDark, setIsDark] = useState(document.documentElement.dataset.theme === "dark");
  useEffect(() => {
    const sync = () => setIsDark(document.documentElement.dataset.theme === "dark");
    window.addEventListener("fazayar:theme", sync);
    return () => window.removeEventListener("fazayar:theme", sync);
  }, []);
  return (
    <button className="theme-toggle" onClick={toggle}
            title={isDark ? "حالت روز" : "حالت شب"} aria-label="تغییر تم روز و شب">
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const items = NAV.filter((n) => !n.roles || (user && n.roles.includes(user.role)));

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <aside className="sidebar lg:w-64 shrink-0 lg:min-h-screen lg:sticky lg:top-0 flex flex-col">
        <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
          <div className="h-10 w-10 rounded-2xl grid place-items-center text-white font-black text-lg"
               style={{ background: "linear-gradient(135deg, var(--primary), #1D4ED8)", boxShadow: "0 3px 10px var(--primary-ring)" }}>ف</div>
          <div>
            <div className="font-bold text-white">فضایار۳۶۰</div>
            <div className="text-[10px] opacity-70">زیست‌بوم دانشجو۳۶۰</div>
          </div>
        </div>
        <nav className="px-3 py-4 flex lg:flex-col gap-1.5 overflow-x-auto flex-1" aria-label="منوی اصلی">
          {items.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === "/"}
              className={({ isActive }) => `sidebar-item ${isActive ? "active" : ""}`}>
              <span aria-hidden>{n.icon}</span>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-white/10 text-[10px] opacity-60">
          نگارش ۱.۱.۱ · تم روز و شب
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="topbar sticky top-0 z-20 px-4 lg:px-6 py-3 flex items-center justify-between gap-3">
          <div className="text-sm hidden md:block" style={{ color: "var(--muted)" }}>
            «فضای مناسب، در زمان مناسب، با تجهیزات آماده و تخصیص قابلیت‌اعتماد»
          </div>
          <div className="flex items-center gap-3">
            <ThemeButton />
            <div className="text-right">
              <div className="text-sm font-medium">{user?.display_name}</div>
              <div className="text-xs" style={{ color: "var(--muted)" }}>{ROLE_FA[user?.role || ""]}</div>
            </div>
            <Chip tone="blue" icon="👤">{user?.username}</Chip>
            <button className="btn-ghost !py-1.5" onClick={() => { logout(); nav("/"); }}>خروج</button>
          </div>
        </header>
        <main className="p-4 lg:p-6 flex-1 min-w-0">
          <Outlet />
        </main>
        <footer className="px-6 py-3 text-xs border-t" style={{ color: "var(--muted)", borderColor: "var(--border)" }}>
          فضایار۳۶۰ — زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی · نگارش ۱.۱.۱
        </footer>
      </div>
    </div>
  );
}
