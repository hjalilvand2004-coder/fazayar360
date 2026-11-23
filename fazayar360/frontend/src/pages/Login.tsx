import { FormEvent, useState } from "react";
import { useAuth } from "../auth";
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

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("Faza360!");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between bg-[#172033] text-white p-10">
        <div className="flex items-center gap-3">
          <div className="h-12 w-12 rounded-2xl bg-[#3563E9] grid place-items-center text-2xl font-bold">ف</div>
          <div>
            <div className="text-xl font-bold">فضایار۳۶۰</div>
            <div className="text-xs text-slate-400">زیرسیستم مدیریت و بهینه‌سازی فضاهای آموزشی</div>
          </div>
        </div>
        <div>
          <h1 className="text-3xl font-bold leading-relaxed">دانشگاه را زنده ببینید</h1>
          <p className="mt-4 text-slate-300 leading-7">
            مرجع عملیاتی شناخت، دسترس‌پذیری، رزرو و بهره‌برداری از فضاهای آموزشی؛
            با تقویم واحد، کنترل قطعی تعارض، تحلیل ظرفیت و پیشنهاد بهینه‌سازیِ قابل توضیح.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-slate-300">
            <li>✓ تقویم اشغال واحد و بدون تعارض</li>
            <li>✓ ظرفیت مؤثر بر اساس چیدمان، ایمنی و تجهیزات</li>
            <li>✓ مرکز اقدام مدیریتی و سناریوسازی جابه‌جایی</li>
          </ul>
        </div>
        <div className="text-xs text-slate-500">زیست‌بوم دانشجو۳۶۰ · پایه‌یار۳۶۰ · برنامه‌ریزی درسی</div>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="card w-full max-w-md p-8">
          <h2 className="text-xl font-bold text-[#172033]">ورود به سامانه</h2>
          <p className="text-sm text-slate-500 mt-1">با حساب یکپارچه‌ی زیست‌بوم وارد شوید</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="label" htmlFor="u">نام کاربری</label>
              <input id="u" className="input" value={username} onChange={(e) => setUsername(e.target.value)} required />
            </div>
            <div>
              <label className="label" htmlFor="p">گذرواژه</label>
              <input id="p" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            {error && <div className="text-sm text-red-600 bg-red-50 rounded-xl p-3" role="alert">⚠️ {error}</div>}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? "در حال ورود…" : "ورود"}
            </button>
          </form>
          <div className="mt-6 border-t border-slate-200 pt-4">
            <div className="text-xs text-slate-500 mb-2">
              کاربران آزمایشی (گذرواژه همه: <span className="font-mono">Faza360!</span>) — {toFaDigits(DEMO_USERS.length)} نقش
            </div>
            <div className="flex flex-wrap gap-1.5">
              {DEMO_USERS.map(([u, label]) => (
                <button key={u} onClick={() => { setUsername(u); setPassword("Faza360!"); }}
                        className="text-xs rounded-full border border-slate-300 px-2.5 py-1 hover:bg-blue-50 hover:border-blue-400">
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
