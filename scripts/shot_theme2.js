// بازعکس تقویم و تحلیل در دو تم با ناوبری واقعی از منو
const { chromium } = require("playwright");
const OUT = "/home/z/my-project/download/screenshots-v11";
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  page.setDefaultTimeout(25000);
  const shot = async (n) => { await page.waitForTimeout(2200); await page.screenshot({ path: `${OUT}/${n}.png` }); console.log("✓", n); };

  await page.goto("http://127.0.0.1:8095/", { waitUntil: "networkidle" });
  await page.fill("#u", "admin");
  await page.fill("#p", "Faza360!");
  await page.click("form button.btn-primary");
  await page.waitForTimeout(1800);

  // تقویم — کلیک از منو (تم روز فعلی)
  await page.click('a:has-text("تقویم عملیاتی")');
  await shot("calendar-light");
  // تم شب
  await page.click(".theme-toggle");
  await shot("calendar-dark");
  // تحلیل — شب
  await page.click('a:has-text("تحلیل ظرفیت")');
  await shot("analytics-dark");
  // تحلیل — روز
  await page.click(".theme-toggle");
  await shot("analytics-light");

  await browser.close();
  console.log("DONE");
})().catch((e) => { console.error("FAIL:", e.message); process.exit(1); });
