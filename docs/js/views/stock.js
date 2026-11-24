import { esc, fmt, fmt0, pct, cls, scoreBg, sigClass, radar, cssVar, store, signed } from "../util.js";
import * as D from "../data.js";

const FAC = {
  tech: [["ret20", "20 日報酬", (v) => pct(v * 100)], ["ret60", "60 日報酬", (v) => pct(v * 100)], ["ma_align", "均線多頭排列", (v) => fmt0(v * 4) + " / 4"],
    ["rsi", "RSI(14)", (v) => fmt(v, 1)], ["kd_k", "KD-K", (v) => fmt(v, 1)], ["bb_pct", "布林 %b", (v) => fmt(v, 2)],
    ["adx_dir", "ADX（方向）", (v) => fmt(v, 1)], ["vol_ratio", "量比（/20 日均量）", (v) => fmt(v, 2)], ["new_high20", "創 20 日新高", (v) => (v ? "是" : "否")]],
  chip: [["f5_lots", "外資 5 日（張）", fmt0], ["t5_lots", "投信 5 日（張）", fmt0], ["f20", "外資 20 日占股本", (v) => pct(v, 3)], ["t20", "投信 20 日占股本", (v) => pct(v, 3)],
    ["trust_streak", "投信連買（日）", fmt0], ["foreign_streak", "外資連買（日）", fmt0], ["margin_chg5", "融資 5 日增減", (v) => pct(v)],
    ["short_margin", "券資比", (v) => pct(v)], ["foreign_ratio", "外資持股比", (v) => fmt(v, 2) + "%"], ["foreign_ratio_chg", "外資持股 20 日變化", (v) => signed(v, 2) + "%"]],
  fund: [["rev_ym", "營收月份", (v) => v], ["rev_yoy", "月營收 YoY", (v) => pct(v)], ["rev_mom", "月營收 MoM", (v) => pct(v)], ["rev_cum_yoy", "累計營收 YoY", (v) => pct(v)],
    ["eps_period", "財報季度", (v) => v], ["eps_q", "單季 EPS", (v) => fmt(v)], ["op_margin", "營益率", (v) => pct(v)],
    ["pe", "本益比", (v) => fmt(v, 1)], ["pb", "股價淨值比", (v) => fmt(v, 2)], ["yield", "殖利率", (v) => fmt(v, 2) + "%"]],
  risk: [["vol20", "20 日年化波動", (v) => fmt(v, 1) + "%"], ["beta", "Beta（120 日）", (v) => fmt(v, 2)], ["mdd60", "60 日最大回撤", (v) => pct(v)],
    ["var95", "1 日 VaR 95%", (v) => fmt(v, 2) + "%"], ["disposition", "處置股", (v) => (v ? "⛔ 是" : "否")], ["attention", "注意股", (v) => (v ? "⚠️ 是" : "否")]],
};

export default async function stock(el, code) {
  const rows = D.S().scores.rows;
  code = code || store.get("lastStock", null) || rows[0]?.code;
  if (!rows.find((r) => r.code === code)) {
    el.innerHTML = `<div class="card empty">${esc(code)} 不在股票池。可到 Colab 設定的自選股加入後重新執行。</div>`;
    return;
  }
  store.set("lastStock", code);
  const s = await D.loadStock(code);
  const row = rows.find((r) => r.code === code);
  const favs = D.favs();
  const q = D.quote(code);
  const sz = sizing(s);
  const N = s.news || {};

  el.innerHTML = `
  <div class="toolbar">
    <input class="input" id="pick" list="codes" placeholder="輸入代號或名稱跳轉" style="width:220px">
    <datalist id="codes">${rows.map((r) => `<option value="${r.code} ${esc(r.name)}">`).join("")}</datalist>
  </div>
  <div class="grid g3">
    <div class="card span2">
      <div class="stock-head">
        <h2 style="margin:0">${esc(s.code)} ${esc(s.name)}</h2>
        <span class="tag">${esc(s.industry)}</span>${s.tags.map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
        <span id="fav" style="cursor:pointer;font-size:20px;color:${favs.has(code) ? "var(--accent)" : "var(--muted)"}" title="加入／移除星號">★</span>
      </div>
      <div class="stock-head" style="margin-top:6px">
        <span class="px ${cls(q.chg_pct)}" id="px">${fmt(q.price)}</span>
        <span class="${cls(q.chg_pct)} num" id="chg" style="font-size:18px">${pct(q.chg_pct)}</span>
        ${s.signal ? `<span class="sig ${sigClass(s.signal)}">${esc(s.signal)}</span>` : ""}
        <span class="muted small" id="pxtime">${q.live ? "即時 " + esc(q.time) : "收盤 " + esc(s.date)}</span>
      </div>
      <div class="legend" style="margin-top:10px"><span><i style="background:#f5b301"></i>MA5</span><span><i style="background:#3b82f6"></i>MA20</span><span><i style="background:#a855f7"></i>MA60</span><span><i style="background:#64748b"></i>布林通道</span></div>
      <div class="chart" id="kc"></div>
      <div class="tabs" id="subtabs">${["法人", "MACD", "KD", "RSI", "融資券"].map((t, i) => `<button class="${i ? "" : "on"}" data-t="${t}">${t}</button>`).join("")}</div>
      <div class="chart sub" id="sc"></div>
    </div>
    <div class="grid" style="align-content:start">
      <div class="card"><h3>五面向評分<span class="r">總分 <span class="score" style="background:${scoreBg(row.total_w)}">${fmt0(row.total_w)}</span></span></h3>
        ${radar(s.scores, D.DIMS)}</div>
      <div class="card"><h3>操作參考<span class="r">ATR ${fmt(row.atr)}</span></h3>
        <dl class="kv">
          <dt>建議停損（收盤 − 2×ATR）</dt><dd class="down">${fmt(s.stop)}</dd>
          <dt>參考停利（收盤 + 3×ATR）</dt><dd class="up">${fmt(s.target)}</dd>
          <dt>風險報酬比</dt><dd>1 : 1.5</dd>
          <dt>建議部位（單筆風險 ${sz.riskPct}%）</dt><dd>${sz.shares >= 1000 ? fmt0(sz.shares / 1000) + " 張" : fmt0(sz.shares) + " 股（零股）"}（約 ${fmt(sz.amount / 1e4, 1)} 萬）</dd>
        </dl></div>
    </div>

    <div class="card span2"><h3>📰 消息面<span class="r">${esc(N.engine === "lexicon" ? "關鍵字評分" : N.engine || "")}｜分數 ${signed(N.score, 2)}</span></h3>
      ${N.summary ? `<div class="ai">🤖 ${esc(N.summary)}</div>` : ""}
      ${N.items?.length ? `<ul class="news">${N.items.map((n) => `<li><span class="s" style="background:${n.sentiment > 0 ? "color-mix(in srgb,var(--up) 25%,transparent)" : n.sentiment < 0 ? "color-mix(in srgb,var(--down) 25%,transparent)" : "var(--card2)"}">${signed(n.sentiment)}</span>
        <div><a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}</a>${n.summary ? `<div class="small">${esc(n.summary)}</div>` : ""}<div class="meta">${n.kind === "material" ? "📢 重大訊息｜" : ""}${esc(n.source)}｜${esc(n.time)}</div></div></li>`).join("")}</ul>` : '<div class="empty">近 7 日無相關新聞</div>'}
    </div>
    <div class="card"><h3>⚠️ 風險指標<span class="r">風險分 ${fmt0(s.scores.risk)}</span></h3>${kv("risk", s.factors.risk)}
      ${s.events.disposition.map((d) => `<div class="ai" style="border-color:var(--r);margin-top:10px">⛔ 處置：${esc(d.measure)}｜${esc(d.period)}<br><span class="small">${esc(d.reason)}</span></div>`).join("")}</div>

    <div class="card"><h3>📈 技術面<span class="r">${fmt0(s.scores.tech)}</span></h3>${kv("tech", s.factors.tech)}</div>
    <div class="card"><h3>💰 籌碼面<span class="r">${fmt0(s.scores.chip)}</span></h3>${kv("chip", s.factors.chip)}</div>
    <div class="card"><h3>🏭 基本面<span class="r">${fmt0(s.scores.fund)}</span></h3>${kv("fund", s.factors.fund)}</div>
  </div>
  <p class="muted small">評分為股票池內百分位排名（0–100），僅供研究參考，不構成投資建議。</p>`;

  el.querySelector("#pick").onchange = (e) => { const c = e.target.value.trim().split(/\s+/)[0]; if (c) location.hash = `#/stock/${c}`; };
  el.querySelector("#fav").onclick = (e) => { D.toggleFav(code); e.target.style.color = D.favs().has(code) ? "var(--accent)" : "var(--muted)"; };

  const charts = draw(el, s);
  const onTheme = () => { charts.destroy(); Object.assign(charts, draw(el, s)); };
  window.addEventListener("themechange", onTheme);
  const off = D.onChange((w) => {
    if (w !== "quotes") return;
    const q2 = D.quote(code);
    el.querySelector("#px").textContent = fmt(q2.price);
    el.querySelector("#px").className = `px ${cls(q2.chg_pct)}`;
    el.querySelector("#chg").textContent = pct(q2.chg_pct);
    el.querySelector("#chg").className = `num ${cls(q2.chg_pct)}`;
    el.querySelector("#pxtime").textContent = q2.live ? `即時 ${q2.time}` : `收盤 ${s.date}`;
    charts.live(q2);
  });
  return () => { off(); window.removeEventListener("themechange", onTheme); charts.destroy(); };
}

function kv(dim, f) {
  return `<dl class="kv">${FAC[dim].map(([k, t, fn]) => `<dt>${t}</dt><dd class="${typeof f[k] === "number" && /chg|ret|yoy|mom|f5|t5|f20|t20/.test(k) ? cls(f[k]) : ""}">${f[k] === null || f[k] === undefined ? "—" : esc(fn(f[k]))}</dd>`).join("")}</dl>`;
}

function sizing(s) {
  const h = D.holdings(), cap = h.capital || 1e6, rp = h.risk_per_trade_pct || 1;
  const atr = s.factors.tech.atr || 0, px = s.ohlc.close.at(-1);
  let shares = atr > 0 ? Math.floor((cap * rp) / 100 / (2 * atr)) : 0;
  shares = Math.min(shares, Math.floor(cap / px));            // 不超過總資金
  if (shares >= 1000) shares = Math.floor(shares / 1000) * 1000; // 整張
  return { shares, amount: shares * px, riskPct: rp };
}

function draw(el, s) {
  const LW = window.LightweightCharts;
  if (!LW) { el.querySelector("#kc").innerHTML = '<div class="empty">圖表元件載入失敗（離線？）</div>'; return { destroy() {}, live() {} }; }
  const up = cssVar("--up"), dn = cssVar("--down"), txt = cssVar("--muted"), line = cssVar("--line"), bg = cssVar("--card");
  const base = {
    layout: { background: { color: bg }, textColor: txt, fontFamily: cssVar("--font") },
    grid: { vertLines: { color: line }, horzLines: { color: line } },
    rightPriceScale: { borderColor: line }, timeScale: { borderColor: line, rightOffset: 3 },
    crosshair: { mode: 1 }, localization: { locale: "zh-TW" }, autoSize: true,
  };
  const o = s.ohlc, T = o.date;
  const ser = (vals) => T.map((t, i) => (vals[i] === null ? { time: t } : { time: t, value: vals[i] }));

  const kc = LW.createChart(el.querySelector("#kc"), base);
  const candle = kc.addCandlestickSeries({ upColor: up, downColor: dn, borderUpColor: up, borderDownColor: dn, wickUpColor: up, wickDownColor: dn });
  const bars = T.map((t, i) => ({ time: t, open: o.open[i], high: o.high[i], low: o.low[i], close: o.close[i] }));
  candle.setData(bars);
  candle.createPriceLine({ price: s.stop, color: dn, lineStyle: 2, lineWidth: 1, title: "停損" });
  candle.createPriceLine({ price: s.target, color: up, lineStyle: 2, lineWidth: 1, title: "停利" });
  [["ma5", "#f5b301"], ["ma20", "#3b82f6"], ["ma60", "#a855f7"]].forEach(([k, c]) => kc.addLineSeries({ color: c, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }).setData(ser(o[k])));
  ["bb_up", "bb_dn"].forEach((k) => kc.addLineSeries({ color: "#64748b", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false }).setData(ser(o[k])));
  const vol = kc.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
  kc.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  vol.setData(T.map((t, i) => ({ time: t, value: o.volume[i] / 1000, color: (o.close[i] >= o.open[i] ? up : dn) + "88" })));
  kc.timeScale().setVisibleLogicalRange({ from: T.length - 120, to: T.length + 2 });

  let sc = null;
  const sub = (tab) => {
    if (sc) sc.remove();
    sc = LW.createChart(el.querySelector("#sc"), { ...base, timeScale: { ...base.timeScale, visible: false } });
    const c = s.chips || {};
    if (tab === "法人" && c.date) {
      [["foreign", "#3b82f6", "外資"], ["trust", "#f5b301", "投信"], ["dealer", "#a855f7", "自營"]].forEach(([k, col, t]) =>
        sc.addHistogramSeries({ color: col, title: t, priceLineVisible: false }).setData(c.date.map((d, i) => ({ time: d, value: c[k][i] ?? 0, color: (c[k][i] ?? 0) >= 0 ? col : col + "88" }))));
    } else if (tab === "融資券" && c.date) {
      sc.addLineSeries({ color: up, title: "融資餘額", priceLineVisible: false }).setData(c.date.map((d, i) => ({ time: d, value: c.margin_bal[i] })));
      sc.addLineSeries({ color: dn, title: "融券餘額", priceScaleId: "left", priceLineVisible: false }).setData(c.date.map((d, i) => ({ time: d, value: c.short_bal[i] })));
      sc.applyOptions({ leftPriceScale: { visible: true, borderColor: line } });
    } else if (tab === "MACD") {
      sc.addHistogramSeries({ priceLineVisible: false }).setData(T.map((t, i) => ({ time: t, value: o.macd_hist[i] ?? 0, color: (o.macd_hist[i] ?? 0) >= 0 ? up : dn })));
      sc.addLineSeries({ color: "#f5b301", lineWidth: 1, priceLineVisible: false, title: "DIF" }).setData(ser(o.macd));
      sc.addLineSeries({ color: "#3b82f6", lineWidth: 1, priceLineVisible: false, title: "MACD" }).setData(ser(o.macd_sig));
    } else if (tab === "KD") {
      sc.addLineSeries({ color: "#f5b301", lineWidth: 1, title: "K" }).setData(ser(o.k));
      sc.addLineSeries({ color: "#3b82f6", lineWidth: 1, title: "D" }).setData(ser(o.d));
    } else if (tab === "RSI") {
      const r = sc.addLineSeries({ color: "#a855f7", lineWidth: 1, title: "RSI" }); r.setData(ser(o.rsi));
      [70, 30].forEach((p) => r.createPriceLine({ price: p, color: txt, lineStyle: 2, lineWidth: 1 }));
    }
    // 與主圖時間軸同步
    const rng = kc.timeScale().getVisibleRange();
    if (rng) try { sc.timeScale().setVisibleRange(rng); } catch {}
  };
  kc.timeScale().subscribeVisibleTimeRangeChange((r) => { if (r && sc) try { sc.timeScale().setVisibleRange(r); } catch {} });
  sub("法人");
  el.querySelector("#subtabs").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    el.querySelectorAll("#subtabs button").forEach((x) => x.classList.toggle("on", x === b));
    sub(b.dataset.t);
  };
  return {
    destroy() { try { kc.remove(); sc && sc.remove(); } catch {} },
    live(q) { // 即時模式：更新今日 K 棒
      if (!q.live || !q.price) return;
      const today = new Date().toISOString().slice(0, 10), lastBar = bars.at(-1);
      if (lastBar.time === today) candle.update({ ...lastBar, close: q.price, high: Math.max(lastBar.high, q.price), low: Math.min(lastBar.low, q.price) });
      else candle.update({ time: today, open: q.price, high: q.price, low: q.price, close: q.price });
    },
  };
}
