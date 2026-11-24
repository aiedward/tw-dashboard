"""技術指標（單檔 DataFrame，index 為日期，欄位 open/high/low/close/volume）。"""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14):
    """回傳 (ADX, +DI, -DI)。"""
    up = df["high"].diff()
    dn = -df["low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    ndi = 100 * pd.Series(ndm, index=df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean(), pdi, ndi


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c = df["close"]
    for n in (5, 10, 20, 60, 120):
        df[f"ma{n}"] = c.rolling(n).mean()
    df["macd"] = ema(c, 12) - ema(c, 26)
    df["macd_sig"] = ema(df["macd"], 9)
    df["macd_hist"] = df["macd"] - df["macd_sig"]
    df["rsi"] = rsi(c)
    sd = c.rolling(20).std()
    df["bb_up"], df["bb_dn"] = df["ma20"] + 2 * sd, df["ma20"] - 2 * sd
    df["bb_pct"] = (c - df["bb_dn"]) / (df["bb_up"] - df["bb_dn"])
    df["atr"] = atr(df)
    df["adx"], df["pdi"], df["ndi"] = adx(df)
    df["vol_ma20"] = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / df["vol_ma20"]
    df["high20"] = df["high"].rolling(20).max()
    # KD(9,3,3)
    lo9, hi9 = df["low"].rolling(9).min(), df["high"].rolling(9).max()
    rsv = ((c - lo9) / (hi9 - lo9).replace(0, np.nan) * 100).fillna(50)
    df["k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    df["d"] = df["k"].ewm(alpha=1 / 3, adjust=False).mean()
    df["ret"] = c.pct_change()
    return df


def bullish_turn(df: pd.DataFrame, lookback: int = 3) -> bool:
    """近 lookback 日內出現：站上月線 或 MACD 柱翻正 或 KD 黃金交叉。"""
    t = df.tail(lookback + 1)
    if len(t) < 2:
        return False
    above = t["close"] > t["ma20"]
    hist = t["macd_hist"] > 0
    kd = t["k"] > t["d"]
    cross = lambda s: bool((s & ~s.shift(fill_value=True)).iloc[1:].any())
    return cross(above) or cross(hist) or cross(kd)
