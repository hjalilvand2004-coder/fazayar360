// عکس‌برداری از نمودار معماری (۲× برای کیفیت چاپ)
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 900, height: 900 },
    deviceScaleFactor: 2,
  });
  await page.goto("file:///home/z/my-project/download/doc-source/architecture.html");
  await page.waitForTimeout(800); // بارگذاری فونت
  const el = await page.locator(".canvas");
  await el.screenshot({ path: "/home/z/my-project/download/doc-source/images/architecture.png" });
  await browser.close();
  console.log("diagram OK");
})();
