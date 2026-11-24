"""FinMind：歷史 K 線回補、加權指數、期貨法人、匯率；VIX 走 yfinance（失敗回傳空）。"""
from __future__ import annotations

import pandas as pd

from .config import get_secret
from .net import get

API = "https://api.finmindtrade.com/api/v4/data"


def _q(dataset: str, data_id: str | None, start: str, end: str | None = None) -> pd.DataFrame:
    p = {"dataset": dataset, "start_date": start}
    if data_id:
        p["data_id"] = data_id
    if end:
        p["end_date"] = end
    tok = get_secret("FINMIND_TOKEN")
    j = get(API, p, headers={"Authorization": f"Bearer {tok}"} if tok else None)
    if j.get("status") not in (200, None) and j.get("msg") != "success":
        raise RuntimeError(f"FinMind {dataset}: {j.get('msg')}")
    return pd.DataFrame(j.get("data") or [])


def price_history(code: str, start: str) -> pd.DataFrame:
    df = _q("TaiwanStockPrice", code, start)
    if df.empty:
        return df
    df = df.rename(columns={"stock_id": "code", "max": "high", "min": "low",
                            "Trading_Volume": "volume", "Trading_money": "value"})
    df = df[df["close"] > 0]
    return df[["date", "code", "open", "high", "low", "close", "volume", "value"]]


def taiex_history(start: str) -> pd.DataFrame:
    df = _q("TaiwanStockPrice", "TAIEX", start)
    return df.rename(columns={"max": "high", "min": "low", "Trading_money": "value"})[
        ["date", "open", "high", "low", "close", "value"]] if not df.empty else df


def futures_foreign_oi(start: str) -> pd.DataFrame:
    """台指期外資未平倉淨口數。"""
    df = _q("TaiwanFuturesInstitutionalInvestors", "TX", start)
    if df.empty:
        return df
    df = df[df["institutional_investors"] == "外資"].copy()
    df["net_oi"] = df["long_open_interest_balance_volume"] - df["short_open_interest_balance_volume"]
    return df[["date", "net_oi"]]


def usd_twd(start: str) -> pd.DataFrame:
    df = _q("TaiwanExchangeRate", "USD", start)
    if df.empty:
        return df
    df["rate"] = (df["spot_buy"] + df["spot_sell"]) / 2
    return df[df["rate"] > 0][["date", "rate"]]


def total_institutional(start: str) -> pd.DataFrame:
    """全市場三大法人買賣超金額（元）。"""
    df = _q("TaiwanStockTotalInstitutionalInvestors", None, start)
    if df.empty:
        return df
    df["net"] = df["buy"] - df["sell"]
    return df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").reset_index()


def vix(start: str) -> pd.DataFrame:
    try:
        import yfinance as yf
        h = yf.Ticker("^VIX").history(start=start, auto_adjust=False)
        if h.empty:
            return pd.DataFrame()
        return pd.DataFrame({"date": h.index.strftime("%Y-%m-%d"), "vix": h["Close"].round(2).values})
    except Exception:
        return pd.DataFrame()
