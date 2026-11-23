import { createContext, useContext, useEffect, ReactNode } from "react";

/** سیستم تم روز/شب — انتخاب کاربر در localStorage ذخیره و روی <html> اعمال می‌شود */
export type Theme = "light" | "dark";

const KEY = "fazayar.theme";

function initial(): Theme {
  const saved = localStorage.getItem(KEY);
  if (saved === "light" || saved === "dark") return saved;
  if (window.matchMedia?.("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function apply(t: Theme) {
  document.documentElement.dataset.theme = t;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", t === "dark" ? "#0B1220" : "#F5F7FB");
}

const Ctx = createContext<{ theme: Theme; toggle: () => void }>(null as any);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = initial();
  useEffect(() => apply(theme), []);
  const toggle = () => {
    const next: Theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    localStorage.setItem(KEY, next);
    apply(next);
    // رفرش سبک برچسب بدون رفرش صفحه — رویداد سفارشی برای هم‌رسانی وضعیت
    window.dispatchEvent(new CustomEvent("fazayar:theme", { detail: next }));
  };
  return <Ctx.Provider value={{ theme, toggle }}>{children}</Ctx.Provider>;
}

export const useTheme = () => useContext(Ctx);
