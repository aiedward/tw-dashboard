"""產生 Colab 筆記本 tw_dashboard.ipynb。執行：python tools/build_notebook.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(keepends=True)}


def code(s, title=None):
    meta = {"cellView": "form"} if "#@" in s else {}
    return {"cell_type": "code", "metadata": meta, "execution_count": None, "outputs": [],
            "source": s.strip("\n").splitlines(keepends=True)}


cells = [
md("""
# 📊 台股即時互動儀表操盤系統（tw-dashboard）

**每日流程：** 盤後（建議 21:30 後，融資券資料已公布）開啟本筆記本 → 「執行階段 › 全部執行」→ 約 3–8 分鐘後網站自動更新。

| 格 | 功能 |
|---|---|
| ① | 掛載 Google 雲端硬碟、下載／更新程式碼 |
| ② | 參數設定（自選股、AI、推播、持股） |
| ③ | 執行每日更新（抓資料 → 五面向評分 → 輸出 JSON） |
| ④ | 發佈到 GitHub Pages 網站 |
| ⑤ | Telegram 推播 |
| ⑥ | （選用）盤中即時模式：Colab 開著時網站每 10 秒更新報價 |

**第一次使用：** 在左側 🔑「密鑰（Secrets）」新增下列項目，並開啟「筆記本存取權」：

| 名稱 | 說明 | 必要 |
|---|---|---|
| `GH_TOKEN` | GitHub Personal Access Token（repo 權限） | ✅ |
| `ANTHROPIC_API_KEY` | Claude API key，消息面 AI 摘要 | 建議 |
| `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID` | Telegram 推播 | 選用 |
| `FINMIND_TOKEN` | FinMind 免費註冊 token，提高額度 | 選用 |

> 僅供研究參考，不構成投資建議。
"""),
code(r'''
#@title ① 掛載雲端硬碟、取得程式碼 { display-mode: "form" }
GITHUB_REPO = "aiedward/tw-dashboard"  #@param {type:"string"}
DRIVE_DIR = "/content/drive/MyDrive/tw-dashboard"  #@param {type:"string"}

import os, subprocess, sys
from google.colab import drive, userdata
drive.mount("/content/drive")

def _token():
    try: return userdata.get("GH_TOKEN")
    except Exception: return None

tok = _token()
url = f"https://x-access-token:{tok}@github.com/{GITHUB_REPO}.git" if tok else f"https://github.com/{GITHUB_REPO}.git"
if not os.path.exists(f"{DRIVE_DIR}/.git"):
    print("首次下載程式碼到雲端硬碟…")
    subprocess.run(["git", "clone", "-q", url, DRIVE_DIR], check=True)
    # 不把 token 留在雲端硬碟的 .git/config
    subprocess.run(["git", "-C", DRIVE_DIR, "remote", "set-url", "origin", f"https://github.com/{GITHUB_REPO}.git"], check=True)
else:
    r = subprocess.run(["git", "-C", DRIVE_DIR, "pull", "-q", "--ff-only", url, "main"], capture_output=True, text=True)
    print("程式碼已更新" if r.returncode == 0 else f"⚠ git pull 失敗（沿用雲端硬碟版本）：{r.stderr[-200:]}")

os.chdir(DRIVE_DIR)
if DRIVE_DIR not in sys.path: sys.path.insert(0, DRIVE_DIR)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], check=True)
print("✅ 環境就緒：", DRIVE_DIR)
'''),
code(r'''
#@title ② 參數設定 { display-mode: "form" }
#@markdown **自選股**（逗號分隔，上市普通股）
WATCHLIST = "2330,2317,2454,2382,3231,2603,2881,1519,2308,3017"  #@param {type:"string"}
#@markdown **股票池**：all = 自選股 + 市值前 N 檔（前50≈0050、51~150≈中型100）；watchlist = 只算自選股（最快）
MODE = "all"  #@param ["all", "watchlist"]
TOP_N = 150  #@param {type:"integer"}
#@markdown **功能開關**
USE_AI = True  #@param {type:"boolean"}
PUBLISH = True  #@param {type:"boolean"}
NOTIFY = True  #@param {type:"boolean"}
#@markdown **持股**（選填）：網站「持股管理 → 匯出 JSON」貼上，空白 = 沿用上次
HOLDINGS_JSON = ""  #@param {type:"string"}

import json, yaml
cfg_path = "config/universe.yaml"
cfg = yaml.safe_load(open(cfg_path, encoding="utf-8"))
cfg["watchlist"] = [c.strip() for c in WATCHLIST.split(",") if c.strip()]
cfg["top_n_by_mcap"] = int(TOP_N)
yaml.safe_dump(cfg, open(cfg_path, "w", encoding="utf-8"), allow_unicode=True, sort_keys=False)
if HOLDINGS_JSON.strip():
    h = json.loads(HOLDINGS_JSON)
    assert isinstance(h.get("positions"), list), "持股 JSON 需含 positions 陣列"
    json.dump(h, open("config/holdings.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"已更新持股 {len(h['positions'])} 筆")
print("自選股：", cfg["watchlist"], "｜模式：", MODE, "｜前 N：", TOP_N)
'''),
code(r'''
#@title ③ 執行每日更新 { display-mode: "form" }
import importlib, backend.run_daily as rd
for m in list(sys.modules):
    if m.startswith("backend."): importlib.reload(sys.modules[m])
user, name = GITHUB_REPO.split("/")
SITE_URL = f"https://{user.lower()}.github.io/{name}/"
result = rd.main(mode=MODE, use_ai=USE_AI, push_notify=False, site_url=SITE_URL)

S = result["scores"]
from IPython.display import display
print(f"\n大盤：{result['market']['label']}")
display(S[["total", "tech", "chip", "fund", "news", "risk", "close", "chg_pct", "signal"]].head(20))
'''),
code(r'''
#@title ④ 發佈到 GitHub Pages { display-mode: "form" }
from backend.publish import publish
if PUBLISH:
    site = publish(GITHUB_REPO, f"data {result['latest']}")
    print("✅ 已發佈，約 1 分鐘後生效：", site)
else:
    print("PUBLISH 未勾選，略過")
'''),
code(r'''
#@title ⑤ Telegram 推播 { display-mode: "form" }
from backend import notify
if NOTIFY:
    msg = notify.daily_digest(result["latest"], result["scores"], result["market"], result["portfolio"], SITE_URL)
    print("已推播" if notify.send(msg) else "推播未送出")
    print("—" * 40); print(msg.replace("<b>", "").replace("</b>", ""))
'''),
md("""
### ⑥ 盤中即時模式（選用）
執行後，網站會自動切換為即時報價（每 10 秒，證交所 MIS 約 5 秒延遲）。**此格會持續執行**，按 ■ 停止即結束即時模式。
Colab 免費版閒置約 90 分鐘會斷線，盤中請保持分頁開啟。
"""),
code(r'''
#@title ⑥ 啟動即時模式 { display-mode: "form" }
import time, json
from datetime import datetime
from backend import live_server
from backend.config import OUT_DIR
from backend.publish import publish

live_url = live_server.start()
print("即時伺服器：", live_url)
json.dump({"url": live_url, "started": datetime.now().isoformat(timespec="seconds")},
          open(OUT_DIR / "live.json", "w"), ensure_ascii=False)
publish(GITHUB_REPO, "live on")
print("✅ 網站將在約 1 分鐘內偵測到即時模式。按 ■ 停止。")
try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    pass
finally:
    live_server.stop()
    json.dump({"url": None, "started": None}, open(OUT_DIR / "live.json", "w"))
    publish(GITHUB_REPO, "live off")
    print("即時模式已結束")
'''),
code(r'''
#@title 🔧 工具：測試 Telegram／清除快取 { display-mode: "form" }
ACTION = "測試 Telegram"  #@param ["測試 Telegram", "清除新聞 AI 快取", "清除全部快取（重新回補）"]
import shutil
from backend.config import CACHE_DIR
if ACTION == "測試 Telegram":
    from backend import notify; print("成功" if notify.send("✅ tw-dashboard 推播測試") else "失敗")
elif ACTION == "清除新聞 AI 快取":
    (CACHE_DIR / "news_ai.json").unlink(missing_ok=True); print("已清除")
else:
    shutil.rmtree(CACHE_DIR); CACHE_DIR.mkdir(); print("已清除，下次執行會重新回補（約 10 分鐘）")
'''),
]

nb = {"cells": cells, "metadata": {"colab": {"provenance": [], "toc_visible": True},
      "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 0}
(ROOT / "tw_dashboard.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print("written", ROOT / "tw_dashboard.ipynb")
