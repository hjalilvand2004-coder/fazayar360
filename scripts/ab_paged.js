// آزمون A/B: منشأ شکست صفحه‌بندی Paged.js در سند RTL
const { chromium } = require("playwright");
const fs = require("fs");

const SRC = "/home/z/my-project/download/doc-source/fazayar360-technical-doc.html";

async function countPages(browser, html, name) {
  const file = "/home/z/my-project/download/doc-source/_test_" + name.replace(/[^A-D]/g, "") + ".html";
  fs.writeFileSync(file, html);
  const page = await browser.newPage({ viewport: { width: 900, height: 1100 } });
  await page.goto("file://" + file);
  await page.addScriptTag({ path: "/home/z/node_modules/pagedjs/dist/paged.polyfill.js" });
  await page.waitForTimeout(20000);
  const n = await page.evaluate(() => document.querySelectorAll(".pagedjs_page").length);
  await page.close();
  fs.unlinkSync(file);
  return n;
}

(async () => {
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const base = fs.readFileSync(SRC, "utf-8");

  const variants = {
    "A: همان نسخه (مرجع)": base,
    "B: بدون counter-reset": base.replace("counter-reset: page 0; ", ""),
    "C: dir=rtl فقط روی کانتینرها": base
      .replace('<html lang="fa" dir="rtl">', '<html lang="fa">')
      .replace('<div class="cover">', '<div class="cover" dir="rtl">')
      .replace('<div class="toc-page">', '<div class="toc-page" dir="rtl">')
      .replace('<div class="main-content">', '<div class="main-content" dir="rtl">')
      .replace('<div class="ending">', '<div class="ending" dir="rtl">'),
    "D: B + C": base
      .replace("counter-reset: page 0; ", "")
      .replace('<html lang="fa" dir="rtl">', '<html lang="fa">')
      .replace('<div class="cover">', '<div class="cover" dir="rtl">')
      .replace('<div class="toc-page">', '<div class="toc-page" dir="rtl">')
      .replace('<div class="main-content">', '<div class="main-content" dir="rtl">')
      .replace('<div class="ending">', '<div class="ending" dir="rtl">'),
  };

  for (const [name, html] of Object.entries(variants)) {
    const n = await countPages(browser, html, name);
    console.log(name, "→", n, "pages");
  }
  await browser.close();
})();
