"""大盤系統風險燈號 + 持股組合風險。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def market_light(mkt: dict, last_all: pd.DataFrame) -> dict:
    """五項指標各給 +1（安全）/0/-1（危險），總分 ≥2 綠、≤-2 紅，其餘黃。"""
    tx = mkt["taiex"].sort_values("date").copy()
    c = tx["close"]
    ma20, ma60 = c.rolling(20).mean().iloc[-1], c.rolling(60).mean().iloc[-1]
    items = []

    def add(key, label, val, score, note):
        items.append({"key": key, "label": label, "value": val, "score": score, "note": note})

    last = c.iloc[-1]
    s = (1 if last > ma20 else -1) + (1 if last > ma60 else -1)
    add("trend", "指數趨勢", round(last, 2), int(np.sign(s)),
        f"{'站上' if last > ma20 else '跌破'}月線 {ma20:,.0f}｜{'站上' if last > ma60 else '跌破'}季線 {ma60:,.0f}")

    oi = mkt.get("fut_oi", pd.DataFrame())
    if not oi.empty:
        oi = oi.sort_values("date")
        v, chg = int(oi["net_oi"].iloc[-1]), int(oi["net_oi"].iloc[-1] - oi["net_oi"].iloc[-6]) if len(oi) > 5 else 0
        add("fut", "外資台指期淨未平倉", v, 1 if v > 0 else (-1 if v < -20000 else 0), f"5 日變化 {chg:+,} 口")

    vx = mkt.get("vix", pd.DataFrame())
    if not vx.empty:
        v = float(vx["vix"].iloc[-1])
        add("vix", "VIX 恐慌指數", v, 1 if v < 18 else (-1 if v > 25 else 0), "< 18 平靜、> 25 恐慌")

    fx = mkt.get("usd", pd.DataFrame())
    if not fx.empty and len(fx) > 20:
        fx = fx.sort_values("date")
        r, r20 = fx["rate"].iloc[-1], fx["rate"].iloc[-21]
        chg = (r / r20 - 1) * 100
        add("fx", "美元/新台幣", round(r, 3), 1 if chg < -0.5 else (-1 if chg > 1 else 0),
            f"20 日 {chg:+.2f}%（台幣{'升' if chg < 0 else '貶'}值）")

    if last_all is not None and not last_all.empty and "change" in last_all:
        up, dn = int((last_all["change"] > 0).sum()), int((last_all["change"] < 0).sum())
        ratio = up / max(up + dn, 1)
        add("breadth", "市場寬度（上漲家數比）", round(ratio * 100, 1), 1 if ratio > 0.6 else (-1 if ratio < 0.35 else 0),
            f"上漲 {up}／下跌 {dn}")

    tot = sum(i["score"] for i in items)
    light = "green" if tot >= 2 else ("red" if tot <= -2 else "yellow")
    return {"light": light, "score": tot, "items": items,
            "label": {"green": "偏多 — 可積極操作", "yellow": "中性 — 控制部位", "red": "偏空 — 降低持股"}[light]}


def portfolio(holdings: dict, frames: dict, scores: pd.DataFrame, universe: pd.DataFrame) -> dict:
    """持股損益、停損距離、產業曝險、集中度、組合 Beta/波動/VaR、建議部位。"""
    pos = holdings.get("positions", [])
    capital = holdings.get("capital", 1_000_000)
    risk_pct = holdings.get("risk_per_trade_pct", 1.0)
    ind = universe.set_index("code")["industry"].to_dict()
    names = universe.set_index("code")["name"].to_dict()
    rows, rets = [], {}
    for p in pos:
        c = str(p["code"])
        f = frames.get(c)
        if f is None:
            rows.append({**p, "code": c, "name": names.get(c, c), "error": "不在股票池，無資料"})
            continue
        last = f.iloc[-1]
        price, atr = float(last["close"]), float(last["atr"])
        stop = p.get("stop") or round(max(p["cost"] * 0.92, price - 2 * atr), 2)
        target = p.get("target") or round(price + 3 * atr, 2)
        mv = price * p["shares"]
        rows.append({**p, "code": c, "name": names.get(c, c), "industry": ind.get(c, ""),
                     "price": price, "value": round(mv), "pnl": round((price - p["cost"]) * p["shares"]),
                     "pnl_pct": round((price / p["cost"] - 1) * 100, 2), "stop": stop, "target": target,
                     "stop_dist_pct": round((price / stop - 1) * 100, 2),
                     "hit_stop": price <= stop, "hit_target": price >= target,
                     "score": float(scores.loc[c, "total"]) if c in scores.index else None,
                     "signal": scores.loc[c, "signal"] if c in scores.index else ""})
        rets[c] = f["ret"].tail(250)
    valid = [r for r in rows if "value" in r]
    tot = sum(r["value"] for r in valid)
    for r in valid:
        r["weight"] = round(r["value"] / tot * 100, 2) if tot else 0
    sector = {}
    for r in valid:
        sector[r["industry"]] = sector.get(r["industry"], 0) + r["weight"]
    hhi = sum((r["weight"] / 100) ** 2 for r in valid)
    stats = {}
    if rets:
        R = pd.DataFrame(rets).dropna()
        w = np.array([next(r["weight"] for r in valid if r["code"] == c) / 100 for c in R.columns])
        pr_ = R.values @ w
        stats = {"vol_annual_pct": round(float(np.std(pr_) * np.sqrt(252) * 100), 2),
                 "var95_1d_pct": round(float(-np.percentile(pr_, 5) * 100), 2),
                 "var95_1d_amt": round(float(-np.percentile(pr_, 5) * tot))}
    # 建議部位：單筆風險 = 資金 × risk% ；停損距離 = 2 × ATR
    sizing = {}
    for c in scores.index:
        f = frames.get(c)
        if f is None:
            continue
        atr = float(f["atr"].iloc[-1])
        price = float(f["close"].iloc[-1])
        lots = int(capital * risk_pct / 100 / (2 * atr) // 1000) if atr > 0 else 0
        sizing[c] = {"lots": lots, "amount": round(lots * 1000 * price)}
    return {"capital": capital, "risk_per_trade_pct": risk_pct, "positions": rows,
            "total_value": round(tot), "total_pnl": round(sum(r["pnl"] for r in valid)),
            "cash": round(capital - sum(r["cost"] * r["shares"] for r in valid)),
            "sector": {k: round(v, 2) for k, v in sorted(sector.items(), key=lambda x: -x[1])},
            "hhi": round(hhi, 3), "concentration": "高" if hhi > 0.3 else ("中" if hhi > 0.15 else "低"),
            **stats, "sizing": sizing}
