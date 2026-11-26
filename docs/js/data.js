// 資料層：讀取 data/*.json、權重、持股（localStorage 覆蓋）、即時模式
import { store } from "./util.js";

const DEFAULT_W = { tech: 30, chip: 30, fund: 20, news: 10, risk: 10 };
export const DIMS = { tech: "技術", chip: "籌碼", fund: "基本", news: "消息", risk: "風險" };

const state = { meta: null, scores: null, market: null, holdings: null, stocks: {}, live: { on: false, url: null, quotes: {}, time: null } };
const subs = new Set();
export const onChange = (fn) => (subs.add(fn), () => subs.delete(fn));
const emit = (what) => subs.forEach((f) => f(what));

async function getJSON(path, bust = true) {
  const v = bust && state.meta ? `?v=${encodeURIComponent(state.meta.updated)}` : `?t=${Date.now()}`;
  const r = await fetch(`data/${path}${v}`, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}

export async function loadCore() {
  state.meta = await getJSON("meta.json", false);
  [state.scores, state.market, state.holdings] = await Promise.all([
    getJSON("scores.json"), getJSON("market.json"), getJSON("holdings.json").catch(() => ({ capital: 1e6, positions: [] })),
  ]);
  rescore();
  return state;
}
export const S = () => state;

export async function loadStock(code) {
  if (!state.stocks[code]) state.stocks[code] = await getJSON(`stocks/${code}.json`);
  return state.stocks[code];
}

// ---------- 權重 ----------
export function weights() { return { ...DEFAULT_W, ...(state.meta?.weights || {}), ...store.get("weights", {}) }; }
export function setWeights(w) { store.set("weights", w); rescore(); emit("weights"); }
export function resetWeights() { store.del("weights"); rescore(); emit("weights"); }
export function rescore() {
  if (!state.scores) return;
  const w = weights(), tw = Object.values(w).reduce((a, b) => a + b, 0) || 1;
  for (const r of state.scores.rows) {
    r.total_w = Object.keys(DIMS).reduce((a, k) => a + (r.scores[k] ?? 50) * (w[k] || 0), 0) / tw;
  }
}

// ---------- 自選（前端額外標記，不影響後端股票池） ----------
export const favs = () => new Set(store.get("favs", []));
export function toggleFav(code) {
  const f = favs(); f.has(code) ? f.delete(code) : f.add(code);
  store.set("favs", [...f]); emit("favs");
}

// ---------- 持股（以本機修改優先，可匯出貼回 Colab config/holdings.json） ----------
export function holdings() { return store.get("holdings", null) || state.holdings || { capital: 1e6, risk_per_trade_pct: 1, positions: [] }; }
export function setHoldings(h) { store.set("holdings", h); emit("holdings"); }
export function resetHoldings() { store.del("holdings"); emit("holdings"); }

// ---------- 價格（即時優先） ----------
export function quote(code) {
  const q = state.live.on && state.live.quotes[code];
  const row = state.scores?.rows.find((r) => r.code === code);
  if (q && q.price) return { price: q.price, chg_pct: q.chg_pct, live: true, time: q.time };
  return row ? { price: row.close, chg_pct: row.chg_pct, live: false } : null;
}

// ---------- 即時模式：Colab 開著時 live.json 會有 tunnel 網址 ----------
let timer = null;
export async function startLive() {
  try {
    // 依序嘗試：Colab live.json（Quick tunnel 網址每次都變）→ 手動指定 → 同站 /api（部署在 Vercel 時常駐）
    const cfg = await getJSON("live.json", false).catch(() => ({}));
    const health = (u) => fetch(`${u}/health`, { signal: AbortSignal.timeout(4000) }).then((r) => r.ok).catch(() => false);
    const sameSite = new URL("api", location.href).href;
    let url = null;
    for (const u of [...new Set([cfg.url, store.get("liveUrl", null), sameSite].filter(Boolean))]) {
      if (await health(u)) { url = u; break; }
    }
    if (!url) return;
    state.live.url = url; state.live.on = true; emit("live");
    const codes = state.scores.rows.map((r) => r.code);
    const tick = async () => {
      try {
        const r = await fetch(`${url}/quotes?codes=${codes.join(",")}`, { signal: AbortSignal.timeout(8000) });
        if (!r.ok) throw new Error(r.status);
        const j = await r.json();
        for (const q of j.quotes) state.live.quotes[q.code] = q;
        state.live.time = j.time; state.live.on = true; state.live.market = j.market;
        emit("quotes");
      } catch {
        state.live.on = false; emit("live");
      }
    };
    await tick();
    timer = setInterval(() => document.visibilityState === "visible" && tick(), 10000);
  } catch { /* 沒有即時模式 */ }
}
export function stopLive() { clearInterval(timer); state.live.on = false; emit("live"); }
