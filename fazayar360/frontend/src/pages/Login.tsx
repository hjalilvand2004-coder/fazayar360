import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { toFaDigits } from "../format";

const DEMO_USERS = [
  ["admin", "مدیر سامانه"],
  ["expert", "کارشناس آموزش"],
  ["edu_manager", "مدیر آموزشی"],
  ["lab_manager", "مسئول آزمایشگاه"],
  ["facility", "مسئول تأسیسات"],
  ["professor", "استاد"],
  ["student", "دانشجو"],
  ["rector", "مدیر دانشگاه"],
] as const;

type SsoConf = {
  enabled: boolean;
  demo_available: boolean;
  authorize_url: string;
  client_id: string;
  scopes: string;
  org_name: string;
};

function ThemeButton() {
  const { toggle } = useTheme();
  const [isDark, setIsDark] = useState(document.documentElement.dataset.theme === "dark");
  useEffect(() => {
    const sync = () => setIsDark(document.documentElement.dataset.theme === "dark");
    window.addEventListener("fazayar:theme", sync);
    return () => window.removeEventListener("fazayar:theme", sync);
  }, []);
  return (
    <button className="theme-toggle !absolute top-5 left-5 z-10" onClick={toggle}
            title={isDark ? "حالت روز" : "حالت شب"} aria-label="تغییر تم روز و شب">
      {isDark ? "☀️" : "🌙"}
    </button>
  );
}

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("Faza360!");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ssoBusy, setSsoBusy] = useState(false);
  const [sso, setSso] = useState<SsoConf | null>(null);

  useEffect(() => {
    api.get<SsoConf>("/auth/sso/config").then(setSso).catch(() => setSso(null));
  }, []);

  const showSso = !!(sso && (sso.enabled || sso.demo_available));

  const startSso = async () => {
    if (!sso) return;
    setError(null);
    // استقرار واقعی: هدایت به سرور هویت سازمانی (OAuth2 Authorization Code)
    if (sso.enabled && sso.authorize_url) {
      const state = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem("fazayar.sso.state", state);
      const redirect = window.location.origin + window.location.pathname + "#/sso/callback";
      const url = `${sso.authorize_url}?response_type=code&client_id=${encodeURIComponent(sso.client_id)}`
        + `&redirect_uri=${encodeURIComponent(redirect)}&scope=${encodeURIComponent(sso.scopes)}&state=${state}`;
      window.location.href = url;
      return;
    }
    // محیط دمو: شبیه‌سازی ورود سازمانی بدون سرور بیرونی
    setSsoBusy(true);
    try {
      const res = await api.post<{ access_token: string }>("/auth/sso/demo");
      setToken(res.access_token);
      window.location.href = "./#/";
    } catch (err: any) {
      setError(err.message || "ورود سازمانی ناموفق بود");
    } finally {
      setSsoBusy(false);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err: any) {
      setError(err.message || "ورود ناموفق بود");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2 relative">
      <ThemeButton />

      {/* پنل معرفی */}
      <div className="hidden lg:flex flex-col justify-between p-10 text-white relative overflow-hidden"
           style={{ background: "linear-gradient(160deg, #101828 0%, #172033 55%, #1D2B4E 100%)" }}>
        <div className="absolute -bottom-32 -left-24 h-96 w-96 rounded-full opacity-10"
             style={{ background: "radial-gradient(circle, var(--primary) 0%, transparent 70%)" }} />
        <div className="flex items-center gap-3 relative">
          <div className="h-12 w-12 rounded-2xl grid place-items-center text-2xl font-black"
               style={{ background: "linear-gradient(135deg, var(--primary), #1D4ED8)", boxShadow: "0 4px 14px var(--primary-ring)" }}>ف</div>
          <div>
            <div className="text-xl font-bold">فضایار۳۶۰</div>
            <div className="text-xs opacity-60">زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی</div>
          </div>
        </div>
        <div className="relative">
          <h1 className="text-3xl font-bold leading-relaxed">دانشگاه را زنده ببینید</h1>
          <p className="mt-4 opacity-80 leading-7">
            مرجع عملیاتی شناخت، دسترس‌پذیری، رزرو و بهره‌برداری از فضاهای آموزشی؛
            با تقویم واحد، کنترل قطعی تعارض، تحلیل ظرفیت و پیشنهاد بهینه‌سازیِ قابل توضیح.
          </p>
          <ul className="mt-6 space-y-2 text-sm opacity-85">
            <li>✓ تقویم اشغال واحد و بدون تعارض</li>
            <li>✓ ظرفیت مؤثر بر اساس چیدمان، ایمنی و تجهیزات</li>
            <li>✓ مرکز اقدام مدیریتی و سناریوسازی جابه‌جایی</li>
            <li>✓ تم روز و شب و ورود یکپارچه سازمانی</li>
          </ul>
        </div>
        <div className="text-xs opacity-50 relative">زیست‌بوم دانشجو۳۶۰ · پایه‌یار۳۶۰ · برنامه‌ریزی درسی</div>
      </div>

      {/* فرم ورود */}
      <div className="flex items-center justify-center p-6">
        <div className="card w-full max-w-md p-8" style={{ boxShadow: "var(--shadow-md)" }}>
          <div className="h-11 w-11 lg:hidden rounded-2xl grid place-items-center text-white font-black mb-4"
               style={{ background: "linear-gradient(135deg, var(--primary), #1D4ED8)" }}>ف</div>
          <h2 className="text-xl font-bold">ورود به سامانه</h2>
          <p className="text-sm mt-1" style={{ color: "var(--muted)" }}>با حساب سازمانی یا حساب محلی وارد شوید</p>

          {showSso && (
            <>
              <button className="btn-primary" onClick={startSso} disabled={ssoBusy}
                      style={{ width: "100%", padding: "11px 16px", fontSize: "14px", marginTop: 0 }}>
                {ssoBusy ? "در حال ورود سازمانی…" : "🔐 ورود یکپارچه سازمانی (SSO)"}
              </button>
              <div className="flex items-center gap-3 my-5">
                <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
                <span className="text-xs" style={{ color: "var(--muted)" }}>یا با حساب محلی</span>
                <div className="flex-1 h-px" style={{ background: "var(--border)" }} />
              </div>
            </>
          )}

          <form onSubmit={submit} className={showSso ? "" : "mt-6"} style={{ display: "grid", gap: 16 }}>
            <div>
              <label className="label" htmlFor="u">نام کاربری</label>
              <input id="u" className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="p">گذرواژه</label>
              <input id="p" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <div className="text-sm rounded-xl p-3" role="alert"
                            style={{ color: "var(--danger)", background: "var(--danger-soft)" }}>⚠️ {error}</div>}
            <button className="btn-primary" disabled={busy} style={{ padding: "11px 16px", fontSize: "14px" }}>
              {busy ? "در حال ورود…" : "ورود"}
            </button>
          </form>

          <div className="mt-6 pt-4" style={{ borderTop: "1px solid var(--border)" }}>
            <div className="text-xs mb-2" style={{ color: "var(--muted)" }}>
              کاربران آزمایشی (گذرواژه همه: <span className="font-mono">Faza360!</span>) — {toFaDigits(DEMO_USERS.length)} نقش
            </div>
            <div className="flex flex-wrap gap-1.5">
              {DEMO_USERS.map(([u, label]) => (
                <button key={u} onClick={() => { setUsername(u); setPassword("Faza360!"); }}
                        className="text-xs rounded-full px-2.5 py-1 transition"
                        style={{ border: "1px solid var(--border)", color: "var(--muted)" }}>
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
