// دیباگ: بررسی خطای Paged.js روی سند
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 900, height: 1100 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push("PAGEERROR: " + e.message.slice(0, 300)));
  page.on("requestfailed", (r) => errs.push("REQFAIL: " + r.url().slice(0, 140) + " :: " + (r.failure() || {}).errorText));
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning")
      errs.push(m.type().toUpperCase() + ": " + m.text().slice(0, 220));
  });
  await page.goto("file:///home/z/my-project/download/doc-source/fazayar360-technical-doc.html");
  await page.addScriptTag({ path: "/home/z/node_modules/pagedjs/dist/paged.polyfill.js" });
  await page.waitForTimeout(25000);
  const pages = await page.evaluate(() => document.querySelectorAll(".pagedjs_page").length);
  console.log("pagedjs_page count:", pages);
  console.log(errs.slice(0, 12).join("\n") || "no console errors");
  await browser.close();
})();
