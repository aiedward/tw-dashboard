import { esc, fmt, fmt0, fmtBig, pct, cls, heatBg, scoreBg, sigClass, spark, signed } from "../util.js";
import * as D from "../data.js";

export default async function overview(el) {
  const s = D.S(), m = s.market, L = m.light;
  const tx = m.taiex, n = tx.close.length;
  const last = tx.close[n - 1], prev = tx.close[n - 2];
  const chg = (last / prev - 1) * 100;
  const inst = m.inst_total.at(-1) || {};
  const fo = (inst.Foreign_Investor || 0) + (inst.Foreign_Dealer_Self || 0);
  const it = inst.Investment_Trust || 0, dl = (inst.Dealer_self || 0) + (inst.Dealer_Hedging || 0);
  const vix = m.vix.at(-1), usd = m.usd.at(-1), oi = m.fut_oi.at(-1);
  const rows = s.scores.rows;
  const buys = rows.filter((r) => r.signal === "關注買點").sort((a, b) => b.total_w - a.total_w).slice(0, 8);
  const top = [...rows].sort((a, b) => b.total_w - a.total_w).slice(0, 10);
  const movers = [...rows].sort((a, b) => b.chg_pct - a.chg_pct);
  const icon = { 1: "▲", 0: "●", "-1": "▼" };

  el.innerHTML = `
  <div class="grid g4">
    <div class="card kpi"><h3>加權指數<span class="r">${esc(s.meta.date)}</span></h3>
      <div class="v ${cls(chg)}" data-live="taiex">${fmt(last)}</div>
      <div class="s ${cls(chg)}">${signed(last - prev, 2)}（${pct(chg)}）</div>
      ${spark(tx.close.slice(-120), 240, 46, chg >= 0 ? "var(--up)" : "var(--down)")}</div>
    <div class="card kpi"><h3>三大法人（現股）</h3>
      <div class="v ${cls(fo + it + dl)}">${fmtBig(fo + it + dl)}</div>
      <div class="s small">外資 <span class="${cls(fo)}">${fmtBig(fo)}</span>｜投信 <span class="${cls(it)}">${fmtBig(it)}</span>｜自營 <span class="${cls(dl)}">${fmtBig(dl)}</span></div></div>
    <div class="card kpi"><h3>外資台指期淨未平倉</h3>
      <div class="v ${cls(oi?.net_oi)}">${oi ? fmt0(oi.net_oi) : "—"}<span class="small muted"> 口</span></div>
      ${spark(m.fut_oi.map((x) => x.net_oi).slice(-40), 240, 46)}</div>
    <div class="card kpi"><h3>VIX／美元台幣</h3>
      <div class="v">${vix ? fmt(vix.vix) : "—"}<span class="small muted"> ／ ${usd ? fmt(usd.rate, 3) : "—"}</span></div>
      <div class="s small muted">VIX &lt;18 平靜、&gt;25 恐慌</div></div>

    <div class="card span2"><h3>大盤風險燈號</h3>
      <div class="light"><div class="lamp ${L.light}">${signed(L.score)}</div>
        <div><div style="font-size:18px;font-weight:700">${esc(L.label)}</div>
        <div class="muted small">五項指標各 +1／0／−1，≥ +2 綠燈、≤ −2 紅燈</div></div></div>
      <div class="risk-items">${L.items.map((i) => `<div><b class="${i.score > 0 ? "up" : i.score < 0 ? "down" : "flat"}">${icon[i.score]}</b><span style="min-width:150px">${esc(i.label)}</span><span class="muted">${esc(i.note)}</span></div>`).join("")}</div>
    </div>
    <div class="card span2"><h3>🎯 關注買點<span class="r">總分 ≥70 且技術面翻多</span></h3>
      ${buys.length ? table(buys) : '<div class="empty">今日無符合條件個股</div>'}</div>

    <div class="card spanall"><h3>產業漲跌熱力圖<span class="r">面積 ∝ 股票池市值，色 = 市值加權漲跌</span></h3>
      <div class="heat">${m.sectors.map((x) => `<a href="#/ranking/${encodeURIComponent(x.industry)}" style="flex-grow:${Math.max(1, Math.sqrt(x.mcap / 1e11))};background:${heatBg(x.chg)}"><b>${esc(x.industry)}</b><span class="num">${pct(x.chg)}</span><span class="small" style="opacity:.8">${x.n} 檔</span></a>`).join("")}</div></div>

    <div class="card span2"><h3>🏆 綜合評分前 10<span class="r"><a href="#/ranking" class="muted">全部 →</a></span></h3>${table(top)}</div>
    <div class="card"><h3>📈 漲幅前 5</h3>${mini(movers.slice(0, 5))}</div>
    <div class="card"><h3>📉 跌幅前 5</h3>${mini(movers.slice(-5).reverse())}</div>

    <div class="card span2"><h3>📢 股票池重大訊息</h3>
      ${m.material.length ? `<ul class="news">${m.material.slice(0, 12).map((x) => `<li><span class="s" style="background:var(--card2)">${esc(x.code)}</span><div><a href="#/stock/${x.code}">${esc(x.title)}</a><div class="meta">${esc(x.name)}｜${esc(x.date)}</div></div></li>`).join("")}</ul>` : '<div class="empty">近期無</div>'}</div>
    <div class="card span2"><h3>⛔ 處置股</h3>
      ${m.disposition.length ? `<ul class="news">${m.disposition.slice(0, 12).map((x) => `<li><span class="s" style="background:var(--r);color:#fff">!</span><div><a href="#/stock/${x.code}">${esc(x.code)} ${esc(x.name || "")}</a>｜${esc(x.measure)}<div class="meta">${esc(x.period)}｜${esc(x.reason)}</div></div></li>`).join("")}</ul>` : '<div class="empty">今日無</div>'}</div>
  </div>`;
}

function table(rows) {
  return `<div class="tablewrap"><table><thead><tr><th class="l">股票</th><th>收盤</th><th>漲跌</th><th>總分</th><th class="hide-m">技/籌/基</th><th class="l">訊號</th></tr></thead><tbody>
  ${rows.map((r) => `<tr onclick="location.hash='#/stock/${r.code}'"><td class="l"><b>${esc(r.code)}</b> ${esc(r.name)}</td>
    <td class="num">${fmt(r.close)}</td><td class="num ${cls(r.chg_pct)}">${pct(r.chg_pct)}</td>
    <td><span class="score" style="background:${scoreBg(r.total_w)}">${fmt0(r.total_w)}</span></td>
    <td class="num muted hide-m">${fmt0(r.scores.tech)}/${fmt0(r.scores.chip)}/${fmt0(r.scores.fund)}</td>
    <td class="l">${r.signal ? `<span class="sig ${sigClass(r.signal)}">${esc(r.signal)}</span>` : ""}</td></tr>`).join("")}</tbody></table></div>`;
}
function mini(rows) {
  return `<table><tbody>${rows.map((r) => `<tr onclick="location.hash='#/stock/${r.code}'"><td class="l"><b>${esc(r.code)}</b> ${esc(r.name)}</td><td class="num">${fmt(r.close)}</td><td class="num ${cls(r.chg_pct)}">${pct(r.chg_pct)}</td></tr>`).join("")}</tbody></table>`;
}
