// عکس‌برداری از بخش‌های مختلف سامانه فضایار۳۶۰ با Playwright (HashRouter)
// خروجی: /home/z/my-project/download/screenshots/*.png
const { chromium } = require("playwright");
const fs = require("fs");

const BASE = "http://127.0.0.1:8095";
const OUT = "/home/z/my-project/download/screenshots";

async function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await ctx.newPage();
  page.setDefaultTimeout(30000);

  const nav = async (path) => {
    await page.goto(BASE + "/#" + path);
    await page.waitForLoadState("networkidle");
  };
  const shot = async (name) => {
    await page.waitForTimeout(2400); // زمان رندر نمودارها
    await page.screenshot({ path: `${OUT}/${name}.png` });
    console.log("✓", name);
  };

  // ۱) صفحه ورود
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await shot("01-login");

  // ورود با کاربر مدیر
  await page.fill("#u", "admin");
  await page.fill("#p", "Faza360!");
  await page.click("form button.btn-primary");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(1200);

  // ۲) داشبورد
  await nav("/");
  await shot("02-dashboard");

  // ۳) ساختار دانشگاه
  await nav("/university");
  await shot("03-university");

  // شناسنامه فضا (دو فضا)
  const tok = await page.evaluate(() => localStorage.getItem("fazayar.token") || "");
  const res = await fetch(BASE + "/api/v1/spaces?size=3", {
    headers: { Authorization: "Bearer " + tok },
  }).then((r) => r.json());
  const sp = res.items[0];
  const sp2 = res.items[1];
  console.log("space:", sp.code, "| slug:", sp.public_slug);

  await nav("/spaces/" + sp.id);
  await shot("04-space-profile");

  // ۵) تقویم اشغال
  await nav("/calendar");
  await shot("05-calendar");

  // ۶) درخواست‌ها
  await nav("/requests");
  await shot("06-requests");

  // ۷) فرم رزرو جدید
  await nav("/booking-new");
  await shot("07-booking-new");

  // ۸) انسداد تعمیراتی
  await nav("/blocks");
  await shot("08-blocks");

  // ۹) تجهیزات
  await nav("/equipment");
  await shot("09-equipment");

  // ۱۰) تحلیل ظرفیت
  await nav("/analytics");
  await shot("10-analytics");

  // ۱۱) بهینه‌سازی
  await nav("/optimizer");
  await shot("11-optimizer");

  // ۱۲) دستیار جستجو
  await nav("/search");
  await shot("12-search");

  // ۱۳) مدیریت
  await nav("/admin");
  await shot("13-admin");

  // ۱۴) صفحه عمومی فضا
  await nav("/public/spaces/" + sp.public_slug);
  await shot("14-public-space");

  // صفحه دوم فضا برای تنوع تصاویر
  await nav("/spaces/" + sp2.id);
  await shot("15-space-profile-2");

  await browser.close();
  console.log("DONE");
}

main().catch((e) => {
  console.error("FAIL:", e.message);
  process.exit(1);
});
