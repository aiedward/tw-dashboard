"""五面向評分：每個因子在股票池內取百分位（0–100），面向分數 = 因子加權平均。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind

DIMS = ["tech", "chip", "fund", "news", "risk"]
DIM_NAMES = {"tech": "技術", "chip": "籌碼", "fund": "基本", "news": "消息", "risk": "風險"}


def pr(s: pd.Series, higher_better: bool = True) -> pd.Series:
    """百分位分數，缺值給 50。"""
    r = s.rank(pct=True, ascending=higher_better) * 100
    return r.fillna(50)


def wavg(parts: list[tuple[pd.Series, float]]) -> pd.Series:
    tot = sum(w for _, w in parts)
    return sum(s * w for s, w in parts) / tot


def stock_frames(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for code, g in prices.groupby("code"):
        g = g.sort_values("date").set_index("date")
        if len(g) >= 30:
            out[code] = ind.add_all(g)
    return out


def tech_factors(frames: dict) -> pd.DataFrame:
    rows = []
    for code, df in frames.items():
        r = df.iloc[-1]
        c = r["close"]
        align = np.mean([c > r["ma5"], r["ma5"] > r["ma20"], r["ma20"] > r["ma60"], c > r["ma60"]])
        rows.append({
            "code": code,
            "ret5": c / df["close"].iloc[-6] - 1 if len(df) > 6 else np.nan,
            "ret20": c / df["close"].iloc[-21] - 1 if len(df) > 21 else np.nan,
            "ret60": c / df["close"].iloc[-61] - 1 if len(df) > 61 else np.nan,
            "ma_align": align,
            "macd_n": r["macd_hist"] / c,
            "rsi": r["rsi"], "kd_k": r["k"], "bb_pct": r["bb_pct"],
            "adx_dir": r["adx"] * np.sign(r["pdi"] - r["ndi"]),
            "vol_ratio": r["vol_ratio"],
            "new_high20": float(c >= r["high20"] * 0.999),
            "bull_turn": ind.bullish_turn(df),
            "atr": r["atr"],
        })
    return pd.DataFrame(rows).set_index("code")


def chip_factors(chips: pd.DataFrame, qfiis: pd.DataFrame, shares: pd.Series) -> pd.DataFrame:
    if chips.empty:
        return pd.DataFrame(index=shares.index)
    ch = chips.sort_values("date")
    dates = sorted(ch["date"].unique())
    d5, d20 = set(dates[-5:]), set(dates[-20:])
    g5 = ch[ch["date"].isin(d5)].groupby("code")[["foreign", "trust", "dealer"]].sum()
    g20 = ch[ch["date"].isin(d20)].groupby("code")[["foreign", "trust", "dealer"]].sum()
    sh = shares.reindex(g20.index)
    f = pd.DataFrame(index=g20.index)
    f["f5"], f["t5"] = g5["foreign"] / sh * 100, g5["trust"] / sh * 100      # 占股本 %
    f["f20"], f["t20"] = g20["foreign"] / sh * 100, g20["trust"] / sh * 100
    f["d5"] = g5["dealer"] / sh * 100
    f["f5_lots"], f["t5_lots"] = g5["foreign"] / 1000, g5["trust"] / 1000      # 張

    def streak(s: pd.Series) -> int:
        n = 0
        for v in s.values[::-1]:
            if v > 0: n += 1
            else: break
        return n
    f["trust_streak"] = ch.groupby("code")["trust"].apply(streak)
    f["foreign_streak"] = ch.groupby("code")["foreign"].apply(streak)

    if "margin_bal" in ch:
        last = ch[ch["date"] == dates[-1]].set_index("code")
        prev = ch[ch["date"] == dates[-6]].set_index("code") if len(dates) > 5 else last
        f["margin_chg5"] = (last["margin_bal"] / prev["margin_bal"].replace(0, np.nan) - 1) * 100
        f["short_margin"] = last["short_bal"] / last["margin_bal"].replace(0, np.nan) * 100
        f["margin_use"] = last["margin_use"]
        f["margin_bal"] = last["margin_bal"]
    if not qfiis.empty:
        qd = sorted(qfiis["date"].unique())
        q1 = qfiis[qfiis["date"] == qd[-1]].set_index("code")["foreign_ratio"]
        q0 = qfiis[qfiis["date"] == qd[0]].set_index("code")["foreign_ratio"]
        f["foreign_ratio"] = q1
        f["foreign_ratio_chg"] = q1 - q0
    return f


def risk_factors(frames: dict, taiex: pd.DataFrame, events: dict) -> pd.DataFrame:
    mret = taiex.set_index("date")["close"].pct_change()
    disp = set(events["disposition"]["code"]) if not events["disposition"].empty else set()
    att = set(events["attention"]["code"]) if not events["attention"].empty else set()
    rows = []
    for code, df in frames.items():
        r = df["ret"].dropna()
        j = pd.concat([r, mret], axis=1, join="inner").tail(120).dropna()
        beta = np.cov(j.iloc[:, 0], j.iloc[:, 1])[0, 1] / j.iloc[:, 1].var() if len(j) > 30 else np.nan
        c60 = df["close"].tail(60)
        mdd = (c60 / c60.cummax() - 1).min()
        rows.append({"code": code,
                     "vol20": r.tail(20).std() * np.sqrt(252) * 100,
                     "beta": beta, "mdd60": mdd * 100,
                     "var95": -np.percentile(r.tail(250), 5) * 100 if len(r) > 60 else np.nan,
                     "disposition": code in disp, "attention": code in att})
    return pd.DataFrame(rows).set_index("code")


def compute(d: dict, frames: dict, news_scores: dict[str, float], weights: dict) -> pd.DataFrame:
    uni = d["universe"].set_index("code")
    T = tech_factors(frames)
    C = chip_factors(d["chips"], d["qfiis"], uni["shares"]).reindex(T.index)
    F = d["fund"].drop_duplicates("code").set_index("code").reindex(T.index)
    R = risk_factors(frames, d["market"]["taiex"], d["events"]).reindex(T.index)
    ind_ = uni["industry"].reindex(T.index)

    tech = wavg([(pr(T["ret20"]), 2), (pr(T["ret60"]), 1), (T["ma_align"] * 100, 2), (pr(T["macd_n"]), 1.5),
                 ((1 - (T["rsi"] - 60).abs() / 40).clip(0, 1) * 100, 1), (pr(T["adx_dir"]), 1),
                 (pr(T["vol_ratio"].clip(upper=3)), 0.5), (T["new_high20"] * 100, 1)])

    cz = lambda col, hb=True: pr(C[col], hb) if col in C else pd.Series(50, index=T.index)
    chip = wavg([(cz("f5"), 2), (cz("f20"), 1.5), (cz("t5"), 2), (cz("t20"), 1.5),
                 ((C.get("trust_streak", 0).clip(upper=5) * 20).fillna(0), 1),
                 (cz("margin_chg5", False), 1), (cz("short_margin"), 0.5), (cz("foreign_ratio_chg"), 1)])

    # 本益比 / 淨值比在同產業內比較
    pe = F["pe"].where(F["pe"] > 0)
    rel = lambda s, hb: s.groupby(ind_).transform(lambda x: x.rank(pct=True, ascending=hb) * 100).fillna(50)
    fund = wavg([(pr(F["rev_yoy"]), 2), (pr(F["rev_mom"]), 0.5), (pr(F["rev_cum_yoy"]), 1.5),
                 (pr(F["eps_q"]), 1), (pr(F["op_margin"]), 1), (rel(pe, False), 1),
                 (pr(F["yield"]), 0.5), (rel(F["pb"].where(F["pb"] > 0), False), 0.5)])

    news = pd.Series({c: 50 + 25 * news_scores.get(c, 0.0) for c in T.index}).clip(0, 100)

    risk = wavg([(pr(R["vol20"], False), 2), (pr(R["beta"], False), 1), (pr(R["mdd60"]), 1.5),
                 (pr(R["var95"], False), 1), (pr(C.get("margin_use", pd.Series(np.nan, index=T.index)), False), 1)])
    risk = risk - R["disposition"].astype(float) * 40 - R["attention"].astype(float) * 20
    risk = risk.clip(0, 100)

    S = pd.DataFrame({"tech": tech, "chip": chip, "fund": fund, "news": news, "risk": risk}).round(1)
    w = {k: weights.get(k, 0) for k in DIMS}
    S["total"] = (sum(S[k] * w[k] for k in DIMS) / sum(w.values())).round(1)

    last = {c: frames[c].iloc[-1] for c in T.index}
    S["close"] = [last[c]["close"] for c in T.index]
    S["chg_pct"] = [round(last[c]["ret"] * 100, 2) for c in T.index]
    S["stop"] = [round(last[c]["close"] - 2 * last[c]["atr"], 2) for c in T.index]
    S["target"] = [round(last[c]["close"] + 3 * last[c]["atr"], 2) for c in T.index]

    def signal(c):
        if R.loc[c, "disposition"]:
            return "處置"
        if S.loc[c, "total"] >= 70 and T.loc[c, "bull_turn"]:
            return "關注買點"
        if S.loc[c, "total"] >= 65 and T.loc[c, "ma_align"] >= 0.75:
            return "多頭續抱"
        weak = last[c]["close"] < last[c]["ma60"] and T.loc[c, "macd_n"] < 0
        if S.loc[c, "total"] < 40 or (weak and S.loc[c, "total"] < 50):
            return "警示"
        return ""
    S["signal"] = [signal(c) for c in S.index]
    S.attrs["factors"] = {"tech": T, "chip": C, "fund": F, "risk": R}
    return S.sort_values("total", ascending=False)
