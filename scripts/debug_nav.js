// دیباگ ناوبری بعد از ورود SSO: چرا calendar-dark تصویر لاگین شد؟
const { chromium } = require("playwright");
const BASE = "http://127.0.0.1:8095";
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const events = [];
  page.on("response", (r) => { if (r.url().includes("/api/")) events.push(`${r.status()} ${r.url().slice(-30)}`); });
  page.on("pageerror", (e) => events.push("PAGEERROR " + e.message.slice(0, 120)));

  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await page.fill("#u", "admin");
  await page.fill("#p", "Faza360!");
  await page.click("form button.btn-primary");
  await page.waitForTimeout(1500);
  console.log("after login url:", page.url());
  console.log("token:", await page.evaluate(() => localStorage.getItem("fazayar.token")?.slice(0, 12)));

  await page.goto(BASE + "/#/calendar", { waitUntil: "networkidle" }).catch((e) => console.log("goto err:", e.message));
  await page.waitForTimeout(2000);
  console.log("after goto url:", page.url());
  console.log("token:", await page.evaluate(() => localStorage.getItem("fazayar.token")?.slice(0, 12)));
  const marker = await page.evaluate(() => document.body.innerText.slice(0, 120).replace(/\n/g, " | "));
  console.log("page text:", marker);
  console.log("events:", events.slice(0, 10).join(" ;; "));
  await browser.close();
})();
