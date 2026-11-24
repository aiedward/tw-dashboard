"""輸出前端用 JSON 到 docs/data/。"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .config import OUT_DIR
from .scoring import DIMS

TZ = timezone(timedelta(hours=8))


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (o is None or math.isnan(o) or math.isinf(o)) else round(float(o), 4)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return o.strftime("%Y-%m-%d")
    return o


def write(name: str, obj) -> None:
    p = OUT_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_clean(obj), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _series(df: pd.DataFrame, cols: list[str], n: int) -> dict:
    t = df.tail(n)
    out = {"date": list(t.index)}
    for c in cols:
        out[c] = [None if pd.isna(v) else round(float(v), 4) for v in t[c].values]
    return out


def export_all(d: dict, frames: dict, S: pd.DataFrame, news: dict, mlight: dict,
               port: dict, weights: dict, holdings: dict) -> None:
    uni = d["universe"].set_index("code")
    fac = S.attrs["factors"]
    T, C, F, R = fac["tech"], fac["chip"], fac["fund"], fac["risk"]
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

    # ---- scores.json（排行榜） ----
    rows = []
    for code, s in S.iterrows():
        u = uni.loc[code]
        g = lambda df, col: df.loc[code, col] if (code in df.index and col in df.columns) else None
        rows.append({
            "code": code, "name": u["name"], "industry": u["industry"], "tags": list(u["tags"]),
            "mcap": u["mcap"], "mcap_rank": u["mcap_rank"],
            "close": s["close"], "chg_pct": s["chg_pct"],
            "volume": float(frames[code]["volume"].iloc[-1]) / 1000,
            "scores": {k: s[k] for k in DIMS}, "total": s["total"], "signal": s["signal"],
            "stop": s["stop"], "target": s["target"], "atr": g(T, "atr"),
            "k": {"ret20": g(T, "ret20"), "rsi": g(T, "rsi"), "vol_ratio": g(T, "vol_ratio"),
                  "f5": g(C, "f5_lots"), "t5": g(C, "t5_lots"), "trust_streak": g(C, "trust_streak"),
                  "pe": g(F, "pe"), "yield": g(F, "yield"), "rev_yoy": g(F, "rev_yoy"),
                  "vol20": g(R, "vol20"), "beta": g(R, "beta"),
                  "news": news.get(code, {}).get("score", 0)},
        })
    write("scores.json", {"updated": now, "date": d["latest"], "rows": rows})

    # ---- stocks/{code}.json（個股頁） ----
    for old in (OUT_DIR / "stocks").glob("*.json"):  # 移除已不在股票池的舊檔
        if old.stem not in S.index:
            old.unlink()
    ch = d["chips"]
    for code in S.index:
        f = frames[code]
        u = uni.loc[code]
        cs = ch[ch["code"] == code].sort_values("date").set_index("date") if not ch.empty else pd.DataFrame()
        chips = _series(cs, [c for c in ["foreign", "trust", "dealer", "margin_bal", "short_bal"] if c in cs], 60) if not cs.empty else {}
        for k in ("foreign", "trust", "dealer"):
            if k in chips:
                chips[k] = [None if v is None else round(v / 1000) for v in chips[k]]  # 股 → 張
        fac_d = lambda df: {k: v for k, v in df.loc[code].items()} if code in df.index else {}
        write(f"stocks/{code}.json", {
            "code": code, "name": u["name"], "industry": u["industry"], "tags": list(u["tags"]),
            "updated": now, "date": d["latest"],
            "ohlc": _series(f, ["open", "high", "low", "close", "volume", "ma5", "ma20", "ma60", "ma120",
                                "bb_up", "bb_dn", "macd", "macd_sig", "macd_hist", "rsi", "k", "d"], 250),
            "chips": chips,
            "scores": {k: S.loc[code, k] for k in DIMS}, "total": S.loc[code, "total"],
            "signal": S.loc[code, "signal"], "stop": S.loc[code, "stop"], "target": S.loc[code, "target"],
            "factors": {"tech": fac_d(T), "chip": fac_d(C), "fund": fac_d(F), "risk": fac_d(R)},
            "news": news.get(code, {}),
            "events": {
                "disposition": d["events"]["disposition"].query("code == @code").to_dict("records")
                if not d["events"]["disposition"].empty else [],
                "attention": d["events"]["attention"].query("code == @code").to_dict("records")
                if not d["events"]["attention"].empty else [],
            },
        })

    # ---- market.json（大盤總覽） ----
    m = d["market"]
    tx = m["taiex"].sort_values("date").set_index("date")
    tx["ma20"], tx["ma60"] = tx["close"].rolling(20).mean(), tx["close"].rolling(60).mean()
    inst = m.get("inst_total", pd.DataFrame())
    sector = (pd.DataFrame([{"industry": r["industry"], "chg": r["chg_pct"], "mcap": r["mcap"]} for r in rows])
              .assign(w=lambda x: x["chg"] * x["mcap"]).groupby("industry")
              .agg(w=("w", "sum"), mcap=("mcap", "sum"), n=("chg", "size")))
    sector["chg"] = sector["w"] / sector["mcap"]
    write("market.json", {
        "updated": now, "date": d["latest"],
        "taiex": _series(tx, ["close", "ma20", "ma60"], 250),
        "light": mlight,
        "inst_total": inst.tail(20).to_dict("records") if not inst.empty else [],
        "fut_oi": m["fut_oi"].tail(60).to_dict("records") if not m["fut_oi"].empty else [],
        "usd": m["usd"].tail(60).to_dict("records") if not m["usd"].empty else [],
        "vix": m["vix"].tail(60).to_dict("records") if not m["vix"].empty else [],
        "sectors": [{"industry": k, "chg": round(v["chg"], 2), "mcap": v["mcap"], "n": int(v["n"])}
                    for k, v in sector.sort_values("mcap", ascending=False).iterrows()],
        "disposition": d["events"]["disposition"].to_dict("records"),
        "material": d["events"]["material"][d["events"]["material"]["code"].isin(S.index)]
        .head(40).to_dict("records") if not d["events"]["material"].empty else [],
    })

    write("portfolio.json", port)
    write("holdings.json", holdings)
    write("meta.json", {"updated": now, "date": d["latest"], "count": len(S), "weights": weights,
                        "version": 1, "dims": {"tech": "技術", "chip": "籌碼", "fund": "基本", "news": "消息", "risk": "風險"}})
    if not (OUT_DIR / "live.json").exists():
        write("live.json", {"url": None, "started": None})
