# 📊 台股即時互動儀表操盤系統（tw-dashboard）

以 **Google Colab** 為後端、**GitHub Pages** 為前端的台股操盤儀表板。前端是 PWA，網站、電腦和手機都能用，也可以安裝到主畫面。

- **五面向評分**：技術、籌碼、基本、消息（Claude AI 摘要）、風險，每個面向 0–100 分，前端可以用滑桿調整權重
- **大盤風險燈號**：指數趨勢、外資期貨未平倉、VIX、匯率、市場寬度
- **互動 K 線**：均線、布林通道、成交量，副圖可切換法人、MACD、KD、RSI、融資券；圖上標出停損停利線
- **持股管理**：損益、停損停利警示、產業曝險、組合 VaR 和 Beta、建議部位
- **Telegram 推播**：每日摘要、買點和持股警示
- **盤中即時模式**：Colab 開著時，網站每 10 秒更新報價

> 僅供研究參考，不構成投資建議。

## 架構

```
Colab（手動執行 tw_dashboard.ipynb）
 ├─ 程式碼與快取存在 Google 雲端硬碟 /MyDrive/tw-dashboard
 ├─ 抓資料：證交所 OpenAPI（全市場批次）、FinMind、Google News、yfinance
 ├─ 計算評分並輸出 docs/data/*.json
 ├─ 發佈：docs/ 以單一 commit 強制推到 gh-pages 分支（不留歷史，repo 不會膨脹）
 └─ 即時模式：FastAPI + cloudflared 免費通道，網址寫進 data/live.json
GitHub
 ├─ main 分支：程式碼
 └─ gh-pages 分支：網站 + 資料 → https://<帳號>.github.io/tw-dashboard/
```

## 第一次設定（約 15 分鐘）

### 1. 建立 GitHub repo 並上傳程式碼
1. 到 https://github.com/new 建立 **Public** repo，名稱填 `tw-dashboard`，**不要**勾選任何初始化選項。
2. 在本機專案資料夾執行：
   ```bash
   git remote add origin https://github.com/<帳號>/tw-dashboard.git
   git push -u origin main
   ```

### 2. 建立 GitHub Token（讓 Colab 能發佈）
到 GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token
- Repository access：Only select repositories → `tw-dashboard`
- Permissions → Repository → **Contents：Read and write**
- 複製產生的 token（`github_pat_...`）

### 3. 設定 Colab
1. 把 `tw_dashboard.ipynb` 上傳到 Google 雲端硬碟，用 Colab 開啟（或 Colab → 檔案 → 開啟筆記本 → GitHub 分頁 → 輸入 repo）。
2. 左側 🔑 **密鑰** 新增下列項目，並開啟「筆記本存取權」：
   - `GH_TOKEN`：上一步的 token
   - `ANTHROPIC_API_KEY`：Claude API key（消息面 AI 摘要；用 `claude-haiku-5-5`，150 檔每天約 0.01 美元）
   - `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`：見第 5 步（選用）
   - `FINMIND_TOKEN`：https://finmindtrade.com 免費註冊（選用，可以提高額度）
3. 把第 ① 格的 `GITHUB_REPO` 改成 `<帳號>/tw-dashboard`。
4. 「執行階段 → 全部執行」。第一次要回補 2 年 K 線和 60 天籌碼，約 8–10 分鐘；之後每天約 3 分鐘。

### 4. 啟用 GitHub Pages
第一次執行完後，到 repo → Settings → Pages → Source 選 **Deploy from a branch**，Branch 選 **gh-pages / (root)** → Save。約 1 分鐘後網站上線。

### 5. Telegram Bot（選用）
1. 在 Telegram 找 **@BotFather** → `/newbot` → 取得 token。
2. 對你的 bot 傳任意訊息，然後開啟 `https://api.telegram.org/bot<TOKEN>/getUpdates`，找 `"chat":{"id":...}` 的數字，就是 `TELEGRAM_CHAT_ID`。
3. 執行 Colab 的「🔧 工具 → 測試 Telegram」。

### 6. 安裝成 App
- Android 或電腦的 Chrome、Edge：網址列右側的「安裝」圖示
- iPhone Safari：分享 → 加入主畫面

## 每日使用
| 時間 | 動作 |
|---|---|
| 盤中（選用） | 執行第 ①、⑥ 格開啟即時模式 |
| 21:30 後 | 「全部執行」→ 更新網站並推播 |

資料公布時間：收盤價 14:30、三大法人約 15:00、融資券約 21:00。15:00 後執行也可以，只是融資券會是前一天的資料。

## 評分方法
每個因子先在股票池內取百分位（0–100），面向分數 = 因子的加權平均，總分 = 五個面向依權重加權。

| 面向 | 因子 |
|---|---|
| 技術 | 20/60 日報酬、均線多頭排列、MACD 柱、RSI 接近 60、ADX 方向、量比、創 20 日新高 |
| 籌碼 | 外資、投信 5/20 日買超占股本；投信連買；融資 5 日增減（反向）；券資比；外資持股變化 |
| 基本 | 月營收 YoY/MoM/累計 YoY、單季 EPS、營益率、同產業本益比與淨值比（反向）、殖利率 |
| 消息 | 近 7 日新聞和重大訊息，Claude Haiku 給 −2～+2 分，近 3 日權重最高 |
| 風險 | 20 日波動、Beta、60 日最大回撤、VaR、融資使用率；處置股扣 40、注意股扣 20 |

訊號：**關注買點** = 總分 ≥ 70 且近 3 日技術翻多；**多頭續抱** = 總分 ≥ 65 且均線多頭；**警示** = 總分 < 40，或跌破季線、MACD 為負且總分 < 50。

## 本機開發
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
python -m pytest tests                          # 單元測試（離線）
python -m backend.run_daily --mode watchlist --no-ai   # 跑 10 檔自選股
python tests/run_notebook.py watchlist          # 模擬執行整本筆記本（發佈推到本機暫存 repo）
cd docs && python -m http.server 8080           # 預覽網站
python tools/build_notebook.py                  # 重新產生筆記本
```
如果遇到 SSL 錯誤（防毒軟體攔截 HTTPS），把 certifi 和防毒軟體的憑證合併後，設定 `REQUESTS_CA_BUNDLE` 指向合併後的檔案。

## 檔案結構
```
backend/   config, net, store, fetch_twse, fetch_finmind, fetch_news, indicators,
           scoring, risk, export, notify, publish, live_server, run_daily
config/    universe.yaml（自選股、股票池）, weights.json, holdings.json
docs/      PWA 前端（index.html, js/, css/, sw.js, manifest）＋ data/（產生的資料，不進 main）
tests/     單元測試、筆記本模擬
tools/     build_notebook.py
```
