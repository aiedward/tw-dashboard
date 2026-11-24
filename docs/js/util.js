// 共用工具：DOM、格式化、顏色
export const $ = (s, r = document) => r.querySelector(s);
export const $$ = (s, r = document) => [...r.querySelectorAll(s)];

export function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function fmt(v, d = 2) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString("zh-TW", { minimumFractionDigits: d, maximumFractionDigits: d });
}
export const fmt0 = (v) => fmt(v, 0);
export function fmtBig(v) {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return fmt(v / 1e12, 2) + " 兆";
  if (a >= 1e8) return fmt(v / 1e8, 1) + " 億";
  if (a >= 1e4) return fmt(v / 1e4, 1) + " 萬";
  return fmt0(v);
}
export const pct = (v, d = 2) => (v === null || v === undefined ? "—" : (v > 0 ? "+" : "") + fmt(v, d) + "%");
export const signed = (v, d = 0) => (v === null || v === undefined ? "—" : (v > 0 ? "+" : "") + fmt(v, d));
export const cls = (v) => (v > 0 ? "up" : v < 0 ? "down" : "flat");

// 分數 0-100 → 背景色（低：綠/差，高：紅/強；配合台股紅漲綠跌的直覺）
export function scoreBg(s) {
  if (s === null || s === undefined) return "transparent";
  const t = Math.max(0, Math.min(1, (s - 30) / 50));
  const hue = 140 - 140 * t; // 140 綠 → 0 紅
  return `hsl(${hue} 65% 42% / .9)`;
}
export function heatBg(chg) {
  const t = Math.max(-1, Math.min(1, (chg ?? 0) / 4));
  if (t >= 0) return `hsl(0 70% ${48 - t * 18}% / ${0.35 + t * 0.6})`;
  return `hsl(145 65% ${42 + t * 14}% / ${0.35 - t * 0.6})`;
}
export function sigClass(s) {
  return { "關注買點": "buy", "多頭續抱": "hold", "警示": "warn", "處置": "bad" }[s] || "";
}

export function toast(msg, ms = 2400) {
  const t = h(`<div class="toast">${esc(msg)}</div>`);
  document.body.append(t);
  setTimeout(() => t.remove(), ms);
}

export const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

export function cssVar(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

// 五面向雷達圖（SVG）
export function radar(scores, labels, size = 220) {
  const keys = Object.keys(labels), n = keys.length, c = size / 2, R = size / 2 - 30;
  const pt = (i, r) => { const a = -Math.PI / 2 + (i * 2 * Math.PI) / n; return [c + r * Math.cos(a), c + r * Math.sin(a)]; };
  const rings = [0.25, 0.5, 0.75, 1].map((f) => `<polygon points="${keys.map((_, i) => pt(i, R * f).join(",")).join(" ")}" fill="none" stroke="var(--line)"/>`).join("");
  const axes = keys.map((_, i) => `<line x1="${c}" y1="${c}" x2="${pt(i, R)[0]}" y2="${pt(i, R)[1]}" stroke="var(--line)"/>`).join("");
  const poly = keys.map((k, i) => pt(i, (R * (scores[k] ?? 0)) / 100).join(",")).join(" ");
  const lab = keys.map((k, i) => { const [x, y] = pt(i, R + 16); return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="12" fill="var(--muted)">${labels[k]} <tspan fill="var(--text)" font-weight="700">${Math.round(scores[k] ?? 0)}</tspan></text>`; }).join("");
  return `<svg viewBox="0 0 ${size} ${size}" width="100%" style="max-width:${size + 40}px;display:block;margin:auto">${rings}${axes}<polygon points="${poly}" fill="color-mix(in srgb, var(--accent) 30%, transparent)" stroke="var(--accent)" stroke-width="2"/>${lab}</svg>`;
}

// 迷你走勢線（SVG）
export function spark(vals, w = 240, hgt = 60, color = "var(--accent2)") {
  const v = vals.filter((x) => x !== null && x !== undefined);
  if (v.length < 2) return "";
  const mn = Math.min(...v), mx = Math.max(...v), rg = mx - mn || 1;
  const pts = vals.map((x, i) => (x === null ? null : `${(i / (vals.length - 1)) * w},${hgt - ((x - mn) / rg) * (hgt - 4) - 2}`)).filter(Boolean).join(" ");
  return `<svg viewBox="0 0 ${w} ${hgt}" width="100%" height="${hgt}" preserveAspectRatio="none"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.8"/></svg>`;
}
