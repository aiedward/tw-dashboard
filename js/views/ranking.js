import { esc, fmt, fmt0, pct, cls, scoreBg, sigClass, store } from "../util.js";
import * as D from "../data.js";

const COLS = [
  ["code", "股票", "l"], ["close", "收盤"], ["chg_pct", "漲跌%"], ["total_w", "總分"],
  ["tech", "技術"], ["chip", "籌碼"], ["fund", "基本"], ["news", "消息"], ["risk", "風險"],
  ["f5", "外資5日(張)", "", "hide-m"], ["t5", "投信5日(張)", "", "hide-m"], ["rev_yoy", "營收YoY", "", "hide-m"],
  ["pe", "本益比", "", "hide-m"], ["signal", "訊號", "l"],
];
const val = (r, k) => (k in r ? r[k] : k in r.scores ? r.scores[k] : r.k?.[k]);

export default async function ranking(el, preset) {
  const st = store.get("rankState", { sort: "total_w", dir: -1, ind: "", sig: "", q: "", tag: "" });
  if (preset) st.ind = preset;
  const rows = D.S().scores.rows;
  const inds = [...new Set(rows.map((r) => r.industry))].sort();
  const w = D.weights();

  el.innerHTML = `
  <div class="card" style="margin-bottom:14px"><h3>權重調整<span class="r"><button class="btn" id="wreset">恢復預設</button></span></h3>
    <div class="sliders">${Object.entries(D.DIMS).map(([k, t]) => `<div><label>${t}<b class="num" id="wv-${k}">${w[k]}</b></label><input type="range" min="0" max="60" step="5" value="${w[k]}" data-w="${k}"></div>`).join("")}</div>
  </div>
  <div class="card">
    <div class="toolbar">
      <input class="input" id="q" placeholder="搜尋代號／名稱" value="${esc(st.q)}" style="width:160px">
      <select class="input" id="ind"><option value="">全部產業</option>${inds.map((i) => `<option ${i === st.ind ? "selected" : ""}>${esc(i)}</option>`).join("")}</select>
      <div class="chips" id="sigs">${["", "關注買點", "多頭續抱", "警示", "處置"].map((s) => `<span class="chip ${s === st.sig ? "on" : ""}" data-s="${s}">${s || "全部訊號"}</span>`).join("")}</div>
      <div class="chips" id="tags">${["", "自選", "市值前50", "中型100", "★"].map((s) => `<span class="chip ${s === st.tag ? "on" : ""}" data-t="${s}">${s || "全部"}</span>`).join("")}</div>
      <span class="muted small" id="cnt" style="margin-left:auto"></span>
    </div>
    <div class="tablewrap"><table><thead><tr>${COLS.map(([k, t, a, x]) => `<th class="${a || ""} ${x || ""}" data-k="${k}">${t}</th>`).join("")}</tr></thead><tbody id="tb"></tbody></table></div>
  </div>`;

  const render = () => {
    store.set("rankState", { ...st, ind: preset ? "" : st.ind });
    const favs = D.favs();
    const q = st.q.trim().toLowerCase();
    let list = rows.filter((r) => (!st.ind || r.industry === st.ind) && (!st.sig || r.signal === st.sig)
      && (!st.tag || (st.tag === "★" ? favs.has(r.code) : r.tags.includes(st.tag)))
      && (!q || r.code.includes(q) || r.name.toLowerCase().includes(q)));
    list.sort((a, b) => {
      const x = val(a, st.sort), y = val(b, st.sort);
      if (typeof x === "string") return st.dir * String(x).localeCompare(String(y));
      return st.dir * ((x ?? -1e18) - (y ?? -1e18));
    });
    el.querySelector("#cnt").textContent = `${list.length} 檔`;
    el.querySelectorAll("th").forEach((th) => th.classList.toggle("sorted", th.dataset.k === st.sort));
    el.querySelector("#tb").innerHTML = list.map((r, i) => {
      const qt = D.quote(r.code);
      return `<tr data-c="${r.code}">
      <td class="l"><span class="muted small">${i + 1}</span> <span class="fav" data-f="${r.code}" style="cursor:pointer;color:${favs.has(r.code) ? "var(--accent)" : "var(--line)"}">★</span> <b>${esc(r.code)}</b> ${esc(r.name)}<span class="tag hide-m">${esc(r.industry)}</span></td>
      <td class="num">${fmt(qt.price)}${qt.live ? '<span class="dot live" style="display:inline-block;margin-left:4px"></span>' : ""}</td>
      <td class="num ${cls(qt.chg_pct)}">${pct(qt.chg_pct)}</td>
      <td><span class="score" style="background:${scoreBg(r.total_w)}">${fmt0(r.total_w)}</span></td>
      ${["tech", "chip", "fund", "news", "risk"].map((k) => `<td class="num" style="color:${scoreBg(r.scores[k])}">${fmt0(r.scores[k])}</td>`).join("")}
      <td class="num hide-m ${cls(r.k.f5)}">${fmt0(r.k.f5)}</td><td class="num hide-m ${cls(r.k.t5)}">${fmt0(r.k.t5)}</td>
      <td class="num hide-m ${cls(r.k.rev_yoy)}">${pct(r.k.rev_yoy, 1)}</td><td class="num hide-m">${fmt(r.k.pe, 1)}</td>
      <td class="l">${r.signal ? `<span class="sig ${sigClass(r.signal)}">${esc(r.signal)}</span>` : ""}</td></tr>`;
    }).join("") || `<tr><td colspan="14" class="empty">沒有符合條件的股票</td></tr>`;
  };

  el.querySelector("#tb").onclick = (e) => {
    const f = e.target.closest("[data-f]");
    if (f) { D.toggleFav(f.dataset.f); render(); return; }
    const tr = e.target.closest("tr[data-c]");
    if (tr) location.hash = `#/stock/${tr.dataset.c}`;
  };
  el.querySelectorAll("th").forEach((th) => (th.onclick = () => {
    st.dir = st.sort === th.dataset.k ? -st.dir : -1; st.sort = th.dataset.k; render();
  }));
  el.querySelector("#q").oninput = (e) => { st.q = e.target.value; render(); };
  el.querySelector("#ind").onchange = (e) => { st.ind = e.target.value; preset = null; render(); };
  el.querySelector("#sigs").onclick = (e) => { const c = e.target.closest("[data-s]"); if (!c) return; st.sig = c.dataset.s; el.querySelectorAll("#sigs .chip").forEach((x) => x.classList.toggle("on", x === c)); render(); };
  el.querySelector("#tags").onclick = (e) => { const c = e.target.closest("[data-t]"); if (!c) return; st.tag = c.dataset.t; el.querySelectorAll("#tags .chip").forEach((x) => x.classList.toggle("on", x === c)); render(); };
  el.querySelectorAll("[data-w]").forEach((inp) => (inp.oninput = () => {
    const nw = { ...D.weights(), [inp.dataset.w]: +inp.value };
    el.querySelector(`#wv-${inp.dataset.w}`).textContent = inp.value;
    D.setWeights(nw);
  }));
  el.querySelector("#wreset").onclick = () => {
    D.resetWeights();
    const w2 = D.weights();
    el.querySelectorAll("[data-w]").forEach((i) => { i.value = w2[i.dataset.w]; el.querySelector(`#wv-${i.dataset.w}`).textContent = i.value; });
  };
  render();
  return D.onChange((what) => (what === "weights" || what === "quotes") && render());
}
