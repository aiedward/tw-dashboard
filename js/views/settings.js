import { esc, store, toast } from "../util.js";
import * as D from "../data.js";

let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredPrompt = e; });

export default async function settings(el) {
  const s = D.S(), m = s.meta, lv = s.live, w = D.weights();
  el.innerHTML = `
  <div class="grid g2">
    <div class="card"><h3>資料狀態</h3>
      <dl class="kv"><dt>資料日</dt><dd>${esc(m.date)}</dd><dt>最後更新</dt><dd>${esc(m.updated)}</dd><dt>股票池</dt><dd>${m.count} 檔</dd>
      <dt>目前權重</dt><dd>${Object.entries(D.DIMS).map(([k, t]) => `${t}${w[k]}`).join("／")}</dd></dl>
      <p class="muted small">每日更新：盤後在 Google Colab 開啟 <b>tw_dashboard.ipynb</b>，按「執行全部」，約 3–8 分鐘後網站自動更新。法人資料約 15:00、融資券約 21:00 公布，建議 21:30 後執行最完整。</p></div>

    <div class="card"><h3>即時模式<span class="r"><span class="dot ${lv.on ? "live" : ""}" style="display:inline-block"></span> ${lv.on ? "連線中" : "未連線"}</span></h3>
      <p class="small">在 Colab 執行「⑥ 即時模式」那格後，網站會自動偵測並每 10 秒更新報價（證交所 MIS，延遲約 5 秒）。關閉 Colab 即自動回到收盤資料。</p>
      <div class="form"><label>手動指定即時伺服器網址（通常不必填）<input class="input" id="lu" placeholder="https://xxxx.trycloudflare.com" value="${esc(store.get("liveUrl", "") || "")}"></label></div>
      <div class="toolbar" style="margin-top:10px"><button class="btn" id="lsave">儲存並重新連線</button>${lv.on ? '<button class="btn" id="lstop">中斷</button>' : ""}</div>
      ${lv.on ? `<p class="muted small">伺服器：${esc(lv.url)}｜最後報價 ${esc(lv.time || "")}</p>` : ""}</div>

    <div class="card"><h3>安裝成 App</h3>
      <p class="small">• <b>Android / 電腦 Chrome、Edge</b>：按下方按鈕，或網址列右側的「安裝」圖示。<br>• <b>iPhone / iPad Safari</b>：分享 → 加入主畫面。<br>安裝後可全螢幕開啟、離線瀏覽最後一次的資料。</p>
      <button class="btn primary" id="inst">安裝 App</button></div>

    <div class="card"><h3>本機資料</h3>
      <p class="small">權重、星號自選、持股、深淺色都只存在這台裝置的瀏覽器中。</p>
      <div class="toolbar"><button class="btn" id="clr">清除所有本機設定</button></div></div>

    <div class="card spanall"><h3>評分方法</h3>
      <div class="small" style="line-height:1.8">
      每個因子在股票池內取百分位（0–100），面向分數＝因子加權平均；總分＝五面向依權重加權。<br>
      <b>技術</b>：20/60 日報酬、均線多頭排列、MACD 柱、RSI 接近 60、ADX 方向、量比、創 20 日新高。<br>
      <b>籌碼</b>：外資／投信 5、20 日買超占股本、投信連買、融資 5 日增減（越減越好）、券資比、外資持股變化。<br>
      <b>基本</b>：月營收 YoY／MoM／累計 YoY、單季 EPS、營益率、同產業本益比與淨值比（越低越好）、殖利率。<br>
      <b>消息</b>：近 7 日新聞與重大訊息，Claude Haiku 評 −2～+2 分，近 3 日權重最高；50 分為中性。<br>
      <b>風險</b>（越高越安全）：20 日波動、Beta、60 日最大回撤、VaR、融資使用率；處置股扣 40、注意股扣 20。<br>
      <b>訊號</b>：關注買點＝總分 ≥ 70 且近 3 日站上月線／MACD 翻正／KD 黃金交叉；警示＝總分 &lt; 40，或跌破季線且 MACD 為負且總分 &lt; 50。<br>
      <b>停損停利</b>：收盤 −2×ATR／+3×ATR；建議部位＝資金 × 單筆風險% ÷（2×ATR）。<br>
      <span class="muted">資料來源：臺灣證券交易所 OpenAPI、FinMind、Google News、Yahoo Finance（VIX）。本系統僅供研究，不構成投資建議。</span></div></div>
  </div>`;
  el.querySelector("#lsave").onclick = () => { const v = el.querySelector("#lu").value.trim().replace(/\/$/, ""); v ? store.set("liveUrl", v) : store.del("liveUrl"); D.stopLive(); D.startLive().then(() => settings(el)); toast("重新連線中…"); };
  el.querySelector("#lstop")?.addEventListener("click", () => { D.stopLive(); settings(el); });
  el.querySelector("#inst").onclick = async () => {
    if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; } else toast("此瀏覽器請用選單中的「安裝」或「加入主畫面」");
  };
  el.querySelector("#clr").onclick = () => { if (confirm("清除權重、星號、持股等本機設定？")) { ["weights", "favs", "holdings", "rankState", "lastStock", "liveUrl", "theme"].forEach(store.del); location.reload(); } };
}
