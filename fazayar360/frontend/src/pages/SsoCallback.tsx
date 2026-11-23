import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, setToken } from "../api";

/** بازگشت از سرور هویت سازمانی: تبادل کد OAuth2 با توکن نشست فضایار۳۶۰ */
export default function SsoCallback() {
  const loc = useLocation();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(loc.search);
    const code = params.get("code");
    const state = params.get("state");
    const savedState = sessionStorage.getItem("fazayar.sso.state");
    if (!code) {
      setError("پارامتر کد ورود از سرور سازمانی دریافت نشد");
      return;
    }
    if (savedState && state && savedState !== state) {
      setError("اعتبارسنجی state ناموفق بود — درخواست را از ابتدا آغاز کنید");
      return;
    }
    sessionStorage.removeItem("fazayar.sso.state");
    const redirect_uri = window.location.origin + window.location.pathname + "#/sso/callback";
    api.post<{ access_token: string }>("/auth/sso/exchange", { code, redirect_uri })
      .then((res) => {
        setToken(res.access_token);
        window.location.href = "./#/";
      })
      .catch((err) => setError(err.message || "تبادل کد سازمانی ناموفق بود"));
  }, []);

  return (
    <div className="min-h-screen grid place-items-center p-6">
      <div className="card w-full max-w-md p-8 text-center">
        <div className="h-12 w-12 rounded-2xl mx-auto grid place-items-center text-white font-black mb-4"
             style={{ background: "linear-gradient(135deg, var(--primary), #1D4ED8)" }}>ف</div>
        {error ? (
          <>
            <h2 className="text-lg font-bold">ورود سازمانی ناموفق بود</h2>
            <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>{error}</p>
            <button className="btn-primary mt-5" onClick={() => nav("/")}>بازگشت به صفحهٔ ورود</button>
          </>
        ) : (
          <>
            <h2 className="text-lg font-bold">در حال تکمیل ورود سازمانی…</h2>
            <p className="text-sm mt-2" style={{ color: "var(--muted)" }}>تبدیل کد امنیتی به نشست شما کمی زمان می‌برد</p>
          </>
        )}
      </div>
    </div>
  );
}
