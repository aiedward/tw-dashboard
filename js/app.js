import { $, h, esc, store } from "./util.js";
import * as D from "./data.js";
import overview from "./views/overview.js";
import ranking from "./views/ranking.js";
import stock from "./views/stock.js";
import portfolio from "./views/portfolio.js";
import settings from "./views/settings.js";

const I = {
  overview: '<path d="M3 13h4v8H3zM10 8h4v13h-4zM17 3h4v18h-4z"/>',
  ranking: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  stock: '<path d="M3 3v18h18"/><path d="M7 14l4-4 3 3 6-6"/>',
  portfolio: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
};
const ROUTES = [
  ["overview", "大盤總覽", overview], ["ranking", "評分排行", ranking], ["stock", "個股分析", stock],
  ["portfolio", "持股管理", portfolio], ["settings", "設定", settings],
];
const svg = (k) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${I[k]}</svg>`;

function buildNav() {
  const links = ROUTES.map(([k, t]) => `<a href="#/${k}" data-k="${k}">${svg(k)}<span>${t}</span></a>`).join("");
  $("#nav").innerHTML = links;
  $("#tabbar").innerHTML = links;
}

let cleanup = null;
async function route() {
  const [, k = "overview", arg] = location.hash.split("/");
  const r = ROUTES.find((x) => x[0] === k) || ROUTES[0];
  document.querySelectorAll("[data-k]").forEach((a) => a.classList.toggle("on", a.dataset.k === r[0]));
  $("#title").textContent = r[1];
  document.title = `${r[1]}｜台股操盤儀表板`;
  if (cleanup) { try { cleanup(); } catch {} cleanup = null; }
  const view = $("#view");
  view.innerHTML = '<div class="loading">載入中…</div>';
  try {
    cleanup = (await r[2](view, arg && decodeURIComponent(arg))) || null;
  } catch (e) {
    console.error(e);
    view.innerHTML = `<div class="card empty">載入失敗：${esc(e.message)}</div>`;
  }
  window.scrollTo(0, 0);
}

function pill() {
  const s = D.S(), m = s.meta, lv = s.live;
  const p = $("#datapill");
  p.innerHTML = lv.on
    ? `<span class="dot live"></span><span>即時 ${esc(lv.time || "")}</span>`
    : `<span class="dot"></span><span>收盤 ${esc(m?.date || "")}</span>`;
  p.title = lv.on ? `Colab 即時模式：${lv.url}` : `資料更新：${m?.updated}`;
  $("#foot").innerHTML = `資料日 ${esc(m?.date)}<br>更新 ${esc(m?.updated)}<br>股票池 ${m?.count} 檔<br><span class="small">僅供研究參考，非投資建議</span>`;
}

$("#themebtn").onclick = () => {
  const cur = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = cur;
  store.set("theme", cur); localStorage.setItem("theme", cur);
  window.dispatchEvent(new Event("themechange"));
};

(async function init() {
  buildNav();
  try {
    await D.loadCore();
  } catch (e) {
    $("#view").innerHTML = `<div class="card empty">尚無資料：請先在 Colab 執行一次每日更新。<br><span class="small">${esc(e.message)}</span></div>`;
    return;
  }
  pill();
  D.onChange((w) => (w === "live" || w === "quotes") && pill());
  window.addEventListener("hashchange", route);
  await route();
  D.startLive();
  if ("serviceWorker" in navigator && location.protocol !== "file:") navigator.serviceWorker.register("sw.js").catch(() => {});
})();
