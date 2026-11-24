"""每日 pipeline 進入點（Colab 與本機共用）。

本機：python -m backend.run_daily --mode watchlist --no-ai
Colab：from backend.run_daily import main; main(mode="all")
"""
from __future__ import annotations

import argparse
import sys
import time

from . import data, fetch_news, notify, risk, scoring
from .config import load_json, load_universe_cfg
from .export import export_all


def main(mode: str = "all", use_ai: bool = True, push_notify: bool = False,
         site_url: str | None = None, log=print) -> dict:
    t0 = time.time()
    cfg = load_universe_cfg()
    weights = load_json("weights.json", {"tech": 30, "chip": 30, "fund": 20, "news": 10, "risk": 10})
    holdings = load_json("holdings.json", {"capital": 1_000_000, "positions": []})

    d = data.update_all(cfg, mode, log)
    log("⑥ 技術指標…")
    frames = scoring.stock_frames(d["prices"])
    uni = d["universe"][d["universe"]["code"].isin(frames)]
    d["universe"] = uni

    log("⑦ 消息面…")
    news = fetch_news.collect(uni, d["events"]["material"], use_ai=use_ai, log=log)

    log("⑧ 評分 / 風險…")
    S = scoring.compute(d, frames, {c: v["score"] for c, v in news.items()}, weights)
    mlight = risk.market_light(d["market"], d["last_all"])
    port = risk.portfolio(holdings, frames, S, uni)

    log("⑨ 輸出 JSON…")
    export_all(d, frames, S, news, mlight, port, weights, holdings)

    if push_notify:
        log("⑩ Telegram 推播…")
        notify.send(notify.daily_digest(d["latest"], S, mlight, port, site_url))

    log(f"✅ 完成，耗時 {time.time() - t0:.0f} 秒｜資料日 {d['latest']}｜{len(S)} 檔｜大盤 {mlight['label']}")
    return {"scores": S, "market": mlight, "portfolio": port, "latest": d["latest"]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="all", choices=["all", "watchlist"])
    ap.add_argument("--no-ai", action="store_true")
    ap.add_argument("--notify", action="store_true")
    a = ap.parse_args()
    r = main(a.mode, use_ai=not a.no_ai, push_notify=a.notify)
    cols = ["total", "tech", "chip", "fund", "news", "risk", "close", "chg_pct", "signal"]
    print(r["scores"][cols].head(20).to_string())
