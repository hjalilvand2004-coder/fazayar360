// اسکرین‌شات تم شب فضایی جدید — لاگین و صفحهٔ خانه + اطمینان از دست‌نخوردگی تم روز
const { chromium } = require("playwright");
const OUT = "/home/z/my-project/download/screenshots-v112";
(async () => {
  const browser = await chromium.launch({
    executablePath: "/home/z/.cache/ms-playwright/chromium-1200/chrome-linux64/chrome",
  });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  page.setDefaultTimeout(25000);
  const shot = async (n) => { await page.waitForTimeout(2000); await page.screenshot({ path: `${OUT}/${n}.png` }); console.log("OK", n); };

  await page.goto("http://127.0.0.1:8095/", { waitUntil: "networkidle" });
  // تم شب
  await page.click(".theme-toggle");
  await shot("login-dark");
  // ورود
  await page.fill("#u", "admin");
  await page.fill("#p", "Faza360!");
  await page.click("form button.btn-primary");
  await shot("home-dark");
  // اطمینان: تم روز دست‌نخورده
  await page.click(".theme-toggle");
  await shot("home-light");
  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error(e.message); process.exit(1); });
