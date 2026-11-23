// آزمون بصری نسخهٔ ۱.۱.۰: دو تم + جریان ورود SSO
const { chromium } = require("playwright");
const fs = require("fs");
const BASE = "http://127.0.0.1:8095";
const OUT = "/home/z/my-project/download/screenshots-v11";

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(25000);
  const shot = async (n) => { await page.waitForTimeout(2100); await page.screenshot({ path: `${OUT}/${n}.png` }); console.log("✓", n); };

  // صفحه ورود — تم روز
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await shot("login-light");

  // کلید تم → شب
  await page.click('.theme-toggle');
  await shot("login-dark");

  // جریان SSO دمو: از صفحهٔ لاگین شب، دکمهٔ ورود سازمانی
  await page.click('button:has-text("ورود یکپارچه سازمانی")');
  await page.waitForTimeout(2500);
  await shot("sso-flow-after");

  // اگر وارد شد (درخواست‌ها ناخودکار)، صفحهٔ لاگین نیست
  const url = page.url();
  console.log("after SSO url:", url);

  // داشبورد شب
  await shot("dashboard-dark");

  // برگردیم به تم روز برای داشبورد
  await page.click('.theme-toggle');
  await shot("dashboard-light");

  // تقویم در شب و روز
  await page.click('.theme-toggle');
  await page.goto(BASE + "/#/calendar", { waitUntil: "networkidle" });
  await shot("calendar-dark");
  await page.click('.theme-toggle');
  await shot("calendar-light");

  // تحلیل در شب
  await page.click('.theme-toggle');
  await page.goto(BASE + "/#/analytics", { waitUntil: "networkidle" });
  await shot("analytics-dark");

  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error("FAIL:", e.message); process.exit(1); });
