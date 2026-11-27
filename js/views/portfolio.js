import { esc, fmt, fmt0, pct, cls, scoreBg, sigClass, toast } from "../util.js";
import * as D from "../data.js";

export default async function portfolio(el) {
  const render = async () => {
    const H = D.holdings();
    const rows = D.S().scores.rows;
    const byCode = Object.fromEntries(rows.map((r) => [r.code, r]));
    const pos = [];
    for (const p of H.positions) {
      const r = byCode[p.code], q = D.quote(p.code);
      if (!r || !q) { pos.push({ ...p, missing: true }); continue; }
      const stop = p.stop || +Math.max(p.cost * 0.92, r.close - 2 * (r.atr || 0)).toFixed(2);
      const target = p.target || r.target;
      const price = q.price, value = price * p.shares;
      pos.push({ ...p, name: r.name, industry: r.industry, price, chg: q.chg_pct, value, stop, target,
        pnl: (price - p.cost) * p.shares, pnl_pct: (price / p.cost - 1) * 100, dist: (price / stop - 1) * 100,
        total: r.total_w, signal: r.signal, hitStop: price <= stop, hitTarget: price >= target });
    }
    const ok = pos.filter((p) => !p.missing);
    const tv = ok.reduce((a, p) => a + p.value, 0), cost = ok.reduce((a, p) => a + p.cost * p.shares, 0);
    const pnl = tv - cost, cash = (H.capital || 0) - cost;
    ok.forEach((p) => (p.weight = tv ? (p.value / tv) * 100 : 0));
    const sector = {};
    ok.forEach((p) => (sector[p.industry] = (sector[p.industry] || 0) + p.weight));
    const hhi = ok.reduce((a, p) => a + (p.weight / 100) ** 2, 0);
    const risk = await portRisk(ok);
    const todayPnl = ok.reduce((a, p) => a + p.value * (p.chg / 100) / (1 + p.chg / 100), 0);

    el.innerHTML = `
    <div class="grid g4">
      <div class="card kpi"><h3>持股市值</h3><div class="v">${fmt0(tv)}</div><div class="s muted">現金 ${fmt0(cash)}｜資金 ${fmt0(H.capital)}</div></div>
      <div class="card kpi"><h3>未實現損益</h3><div class="v ${cls(pnl)}">${fmt0(pnl)}</div><div class="s ${cls(pnl)}">${pct(cost ? (pnl / cost) * 100 : 0)}</div></div>
      <div class="card kpi"><h3>今日損益（估）</h3><div class="v ${cls(todayPnl)}">${fmt0(todayPnl)}</div><div class="s muted">持股比重 ${pct((tv / (H.capital || 1)) * 100, 1).replace("+", "")}</div></div>
      <div class="card kpi"><h3>組合風險</h3><div class="v">${risk ? fmt(risk.var95, 2) + "%" : "—"}</div>
        <div class="s muted">1 日 VaR95 ≈ ${risk ? fmt0((risk.var95 / 100) * tv) : "—"} 元｜β ${risk ? fmt(risk.beta, 2) : "—"}｜年化波動 ${risk ? fmt(risk.vol, 1) + "%" : "—"}</div></div>

      <div class="card spanall"><h3>持股明細<span class="r"><button class="btn primary" id="add">＋ 新增持股</button></span></h3>
        ${ok.filter((p) => p.hitStop || p.hitTarget || p.signal === "警示" || p.signal === "處置").map((p) => `<div class="ai" style="border-color:${p.hitStop ? "var(--down)" : p.hitTarget ? "var(--up)" : "var(--y)"}">${p.hitStop ? "⛔ 跌破停損" : p.hitTarget ? "✅ 達到停利" : "⚠️ 訊號：" + esc(p.signal)}｜<b>${esc(p.code)} ${esc(p.name)}</b> 現價 ${fmt(p.price)}，停損 ${fmt(p.stop)}／停利 ${fmt(p.target)}</div>`).join("")}
        <div class="tablewrap"><table><thead><tr><th class="l">股票</th><th>股數</th><th>成本</th><th>現價</th><th>損益</th><th>報酬%</th><th>比重</th><th>停損</th><th>距停損</th><th>停利</th><th>總分</th><th class="l">訊號</th><th></th></tr></thead><tbody>
        ${pos.map((p, i) => p.missing ? `<tr><td class="l">${esc(p.code)}</td><td colspan="11" class="l muted">不在股票池（請在 Colab 自選股加入）</td><td><button class="btn" data-del="${i}">刪除</button></td></tr>` :
        `<tr><td class="l" onclick="location.hash='#/stock/${p.code}'"><b>${esc(p.code)}</b> ${esc(p.name)}</td><td class="num">${fmt0(p.shares)}</td><td class="num">${fmt(p.cost)}</td>
          <td class="num ${cls(p.chg)}">${fmt(p.price)}</td><td class="num ${cls(p.pnl)}">${fmt0(p.pnl)}</td><td class="num ${cls(p.pnl_pct)}">${pct(p.pnl_pct)}</td>
          <td class="num">${fmt(p.weight, 1)}%</td><td class="num down">${fmt(p.stop)}</td><td class="num ${p.dist < 3 ? "down" : ""}">${fmt(p.dist, 1)}%</td><td class="num up">${fmt(p.target)}</td>
          <td><span class="score" style="background:${scoreBg(p.total)}">${fmt0(p.total)}</span></td><td class="l">${p.signal ? `<span class="sig ${sigClass(p.signal)}">${esc(p.signal)}</span>` : ""}</td>
          <td><button class="btn" data-edit="${i}">編輯</button></td></tr>`).join("") || '<tr><td colspan="13" class="empty">尚無持股，按「新增持股」開始</td></tr>'}
        </tbody></table></div></div>

      <div class="card span2"><h3>產業曝險<span class="r">集中度 HHI ${fmt(hhi, 3)}（${hhi > 0.3 ? "高" : hhi > 0.15 ? "中" : "低"}）</span></h3>
        ${Object.entries(sector).sort((a, b) => b[1] - a[1]).map(([k, v]) => `<div style="display:grid;grid-template-columns:90px 1fr 56px;gap:8px;align-items:center;margin:6px 0;font-size:13px"><span>${esc(k)}</span><span class="bar" style="width:${v}%;background:${v > 40 ? "var(--y)" : "var(--accent2)"}"></span><span class="num" style="text-align:right">${fmt(v, 1)}%</span></div>`).join("") || '<div class="empty">—</div>'}
        <p class="muted small">單一產業 &gt; 40% 以黃色標示，建議分散。</p></div>
      <div class="card span2"><h3>資金與風險設定</h3>
        <div class="form" style="grid-template-columns:1fr 1fr">
          <label>總資金（元）<input class="input" id="cap" type="number" value="${H.capital}"></label>
          <label>單筆風險（% 資金）<input class="input" id="rp" type="number" step="0.1" value="${H.risk_per_trade_pct ?? 1}"></label>
        </div>
        <div class="toolbar" style="margin-top:12px">
          <button class="btn" id="save">儲存設定</button>
          <button class="btn" id="exp">匯出 JSON（貼回 Colab）</button>
          <button class="btn" id="imp">匯入 JSON</button>
          <button class="btn" id="rst">還原為 GitHub 版本</button>
        </div>
        <p class="muted small">持股只存在這台裝置的瀏覽器。要讓 Telegram 推播也用同一份持股，請匯出後貼到 Colab 的 holdings 欄位。</p></div>
    </div>
    <dialog id="dlg"></dialog>`;

    const dlg = el.querySelector("#dlg");
    const edit = (i) => {
      const p = i === null ? { code: "", shares: 1000, cost: "", stop: "", target: "", date: new Date().toISOString().slice(0, 10) } : H.positions[i];
      dlg.innerHTML = `<form method="dialog" class="form"><h3 style="margin:0">${i === null ? "新增" : "編輯"}持股</h3>
        <label>股票代號<input class="input" name="code" list="codes2" required value="${esc(p.code)}"><datalist id="codes2">${rows.map((r) => `<option value="${r.code}">${esc(r.name)}</option>`).join("")}</datalist></label>
        <label>股數<input class="input" name="shares" type="number" required value="${p.shares}"></label>
        <label>成本價<input class="input" name="cost" type="number" step="0.01" required value="${p.cost}"></label>
        <label>停損價（空白＝自動：成本 −8% 與 收盤 −2ATR 取高）<input class="input" name="stop" type="number" step="0.01" value="${p.stop ?? ""}"></label>
        <label>停利價（空白＝自動：收盤 +3ATR）<input class="input" name="target" type="number" step="0.01" value="${p.target ?? ""}"></label>
        <label>買進日期<input class="input" name="date" type="date" value="${esc(p.date || "")}"></label>
        <div class="toolbar"><button class="btn primary" value="ok">儲存</button>${i !== null ? '<button class="btn" value="del">刪除</button>' : ""}<button class="btn" value="cancel" formnovalidate>取消</button></div></form>`;
      dlg.onclose = () => {
        const v = dlg.returnValue;
        if (v === "cancel" || !v) return;
        const P = [...H.positions];
        if (v === "del") P.splice(i, 1);
        else {
          const f = new FormData(dlg.querySelector("form"));
          const n = { code: f.get("code").trim().split(/\s+/)[0], shares: +f.get("shares"), cost: +f.get("cost"),
            stop: f.get("stop") ? +f.get("stop") : null, target: f.get("target") ? +f.get("target") : null, date: f.get("date") };
          i === null ? P.push(n) : (P[i] = n);
        }
        D.setHoldings({ ...H, positions: P }); render();
      };
      dlg.showModal();
    };
    el.querySelector("#add").onclick = () => edit(null);
    el.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => edit(+b.dataset.edit)));
    el.querySelectorAll("[data-del]").forEach((b) => (b.onclick = () => { const P = [...H.positions]; P.splice(+b.dataset.del, 1); D.setHoldings({ ...H, positions: P }); render(); }));
    el.querySelector("#save").onclick = () => { D.setHoldings({ ...H, capital: +el.querySelector("#cap").value, risk_per_trade_pct: +el.querySelector("#rp").value }); toast("已儲存"); render(); };
    el.querySelector("#exp").onclick = async () => {
      const txt = JSON.stringify(D.holdings(), null, 2);
      try { await navigator.clipboard.writeText(txt); toast("已複製到剪貼簿"); } catch { prompt("複製以下內容：", txt); }
    };
    el.querySelector("#imp").onclick = () => {
      dlg.innerHTML = `<form method="dialog" class="form"><h3 style="margin:0">匯入持股 JSON</h3><textarea class="input" name="j">${esc(JSON.stringify(D.holdings(), null, 2))}</textarea><div class="toolbar"><button class="btn primary" value="ok">匯入</button><button class="btn" value="cancel">取消</button></div></form>`;
      dlg.onclose = () => {
        if (dlg.returnValue !== "ok") return;
        try { const j = JSON.parse(dlg.querySelector("textarea").value); if (!Array.isArray(j.positions)) throw 0; D.setHoldings(j); render(); toast("已匯入"); }
        catch { toast("JSON 格式錯誤"); }
      };
      dlg.showModal();
    };
    el.querySelector("#rst").onclick = () => { if (confirm("清除本機修改，還原為 GitHub 上的 holdings.json？")) { D.resetHoldings(); render(); } };
  };
  await render();
  return D.onChange((w) => w === "quotes" && render());
}

// 用個股與大盤日報酬計算組合 VaR / Beta / 波動
async function portRisk(pos) {
  if (!pos.length) return null;
  const tv = pos.reduce((a, p) => a + p.value, 0);
  const st = await Promise.all(pos.map((p) => D.loadStock(p.code).catch(() => null)));
  const tx = D.S().market.taiex;
  const mret = new Map(tx.date.map((d, i) => [d, i ? tx.close[i] / tx.close[i - 1] - 1 : null]));
  const series = st.map((s) => s && new Map(s.ohlc.date.map((d, i) => [d, i ? s.ohlc.close[i] / s.ohlc.close[i - 1] - 1 : null])));
  const dates = (st[0]?.ohlc.date || []).slice(-250);
  const pr = [], mr = [];
  for (const d of dates) {
    let r = 0, ok = true;
    pos.forEach((p, i) => { const v = series[i]?.get(d); if (v === null || v === undefined) ok = false; else r += (p.value / tv) * v; });
    if (ok && mret.get(d) !== null && mret.get(d) !== undefined) { pr.push(r); mr.push(mret.get(d)); }
  }
  if (pr.length < 30) return null;
  const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
  const mp = mean(pr), mm = mean(mr);
  const cov = mean(pr.map((x, i) => (x - mp) * (mr[i] - mm))), vm = mean(mr.map((x) => (x - mm) ** 2));
  const sd = Math.sqrt(mean(pr.map((x) => (x - mp) ** 2)));
  const sorted = [...pr].sort((a, b) => a - b);
  return { var95: -sorted[Math.floor(sorted.length * 0.05)] * 100, beta: cov / vm, vol: sd * Math.sqrt(252) * 100 };
}
