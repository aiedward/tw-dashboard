"""證交所資料（全市場批次端點）。日期參數格式 'YYYYMMDD'，回傳 DataFrame。"""
from __future__ import annotations

import re

import pandas as pd

from .config import INDUSTRY
from .net import get, num, roc_to_iso

OAPI = "https://openapi.twse.com.tw/v1"
RWD = "https://www.twse.com.tw/rwd/zh"


def _ok(j) -> bool:
    return isinstance(j, dict) and j.get("stat") == "OK"


# ---------- 基本資料 ----------
def company_info() -> pd.DataFrame:
    """上市公司：代號、簡稱、產業、發行股數。"""
    rows = get(f"{OAPI}/opendata/t187ap03_L")
    out = []
    for r in rows:
        code = r.get("公司代號", "").strip()
        ind = str(r.get("產業別", "")).strip()
        out.append({
            "code": code,
            "name": r.get("公司簡稱", "").strip(),
            "industry": INDUSTRY.get(ind, ind or "其他"),
            "shares": num(r.get("已發行普通股數或TDR原股發行股數")),
        })
    return pd.DataFrame(out)


# ---------- 價格 ----------
def latest_day_all() -> pd.DataFrame:
    """最近一個交易日全部上市證券收盤行情（openapi，不需日期）。"""
    rows = get(f"{OAPI}/exchangeReport/STOCK_DAY_ALL")
    out = []
    for r in rows:
        c = num(r.get("ClosingPrice"))
        if not c:
            continue
        out.append({
            "date": roc_to_iso(r["Date"]), "code": r["Code"].strip(),
            "open": num(r.get("OpeningPrice")), "high": num(r.get("HighestPrice")),
            "low": num(r.get("LowestPrice")), "close": c,
            "volume": num(r.get("TradeVolume")), "value": num(r.get("TradeValue")),
            "change": num(r.get("Change")),
        })
    return pd.DataFrame(out)


def daily_by_date(d: str):
    """指定日全部股票 OHLCV + 加權指數 + 漲跌家數。非交易日回傳 None。"""
    j = get(f"{RWD}/afterTrading/MI_INDEX", {"date": d, "type": "ALLBUT0999", "response": "json"})
    if not _ok(j):
        return None
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    prices, taiex, breadth = [], None, {}
    for t in j.get("tables", []):
        title = t.get("title") or ""
        f, data = t.get("fields") or [], t.get("data") or []
        if "每日收盤行情" in title:
            ix = {k: i for i, k in enumerate(f)}
            for r in data:
                c = num(r[ix["收盤價"]])
                if not c:
                    continue
                prices.append({
                    "date": iso, "code": r[ix["證券代號"]].strip(),
                    "open": num(r[ix["開盤價"]]), "high": num(r[ix["最高價"]]),
                    "low": num(r[ix["最低價"]]), "close": c,
                    "volume": num(r[ix["成交股數"]]), "value": num(r[ix["成交金額"]]),
                })
        elif "價格指數(臺灣證券交易所)" in title:
            for r in data:
                if r[0] == "發行量加權股價指數":
                    taiex = num(r[1])
        elif "漲跌證券數" in title:
            for r in data:  # ['上漲(漲停)', '1,354(49)', '16(4)']
                breadth[r[0]] = r[2]
    return {"prices": pd.DataFrame(prices), "taiex": taiex, "breadth": breadth}


# ---------- 籌碼 ----------
def t86(d: str) -> pd.DataFrame | None:
    """三大法人買賣超（股）。"""
    j = get(f"{RWD}/fund/T86", {"date": d, "selectType": "ALLBUT0999", "response": "json"})
    if not _ok(j):
        return None
    ix = {k: i for i, k in enumerate(j["fields"])}
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    out = []
    for r in j["data"]:
        fo = (num(r[ix["外陸資買賣超股數(不含外資自營商)"]]) or 0) + (num(r[ix["外資自營商買賣超股數"]]) or 0)
        out.append({"date": iso, "code": r[0].strip(), "foreign": fo,
                    "trust": num(r[ix["投信買賣超股數"]]) or 0,
                    "dealer": num(r[ix["自營商買賣超股數"]]) or 0})
    return pd.DataFrame(out)


def margin(d: str) -> pd.DataFrame | None:
    """融資融券餘額（張）。使用率 ≈ 融資餘額 / (融資餘額 + 次一營業日限額)。"""
    j = get(f"{RWD}/marginTrading/MI_MARGN", {"date": d, "selectType": "STOCK", "response": "json"})
    if not _ok(j):
        return None
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    out = []
    for t in j.get("tables", []):
        if not t.get("fields") or "代號" not in t["fields"]:
            continue
        for r in t.get("data", []):
            code = r[0].strip()
            if not code or not code[0].isdigit():
                continue
            mb, mlim, sb = num(r[6]) or 0, num(r[7]) or 0, num(r[12]) or 0
            out.append({"date": iso, "code": code, "margin_bal": mb, "short_bal": sb,
                        "margin_use": mb / (mb + mlim) * 100 if (mb + mlim) > 0 else None})
    return pd.DataFrame(out) if out else None


def qfiis(d: str) -> pd.DataFrame | None:
    """外資持股比率（%）。"""
    j = get(f"{RWD}/fund/MI_QFIIS", {"date": d, "selectType": "ALLBUT0999", "response": "json"})
    if not _ok(j):
        return None
    ix = {k: i for i, k in enumerate(j["fields"])}
    iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return pd.DataFrame([{"date": iso, "code": r[0].strip(),
                          "foreign_ratio": num(r[ix["全體外資及陸資持股比率"]])} for r in j["data"]])


# ---------- 基本面 ----------
def revenue() -> pd.DataFrame:
    rows = get(f"{OAPI}/opendata/t187ap05_L")
    return pd.DataFrame([{
        "code": r["公司代號"].strip(), "rev_ym": r["資料年月"],
        "rev": num(r["營業收入-當月營收"]),
        "rev_mom": num(r["營業收入-上月比較增減(%)"]),
        "rev_yoy": num(r["營業收入-去年同月增減(%)"]),
        "rev_cum_yoy": num(r["累計營業收入-前期比較增減(%)"]),
    } for r in rows])


def eps() -> pd.DataFrame:
    rows = get(f"{OAPI}/opendata/t187ap14_L")
    out = []
    for r in rows:
        rev, op = num(r.get("營業收入")), num(r.get("營業利益"))
        out.append({"code": r["公司代號"].strip(), "eps_q": num(r.get("基本每股盈餘(元)")),
                    "eps_period": f"{int(r['年度']) + 1911}Q{r['季別']}",
                    "op_margin": op / rev * 100 if rev and op is not None else None})
    return pd.DataFrame(out)


def valuation() -> pd.DataFrame:
    rows = get(f"{OAPI}/exchangeReport/BWIBBU_ALL")
    return pd.DataFrame([{"code": r["Code"].strip(), "pe": num(r.get("PEratio")),
                          "yield": num(r.get("DividendYield")), "pb": num(r.get("PBratio"))} for r in rows])


# ---------- 事件 / 風險 ----------
def material_news() -> pd.DataFrame:
    rows = get(f"{OAPI}/opendata/t187ap04_L")
    out = []
    for r in rows:
        subj = next((v for k, v in r.items() if k.strip() == "主旨"), "")
        out.append({"code": r["公司代號"].strip(), "name": r.get("公司名稱", "").strip(),
                    "date": roc_to_iso(r["發言日期"]), "title": str(subj).strip(),
                    "detail": str(r.get("說明", ""))[:600]})
    return pd.DataFrame(out)


def disposition() -> pd.DataFrame:
    """處置股。"""
    rows = get(f"{OAPI}/announcement/punish")
    return pd.DataFrame([{"code": r["Code"].strip(), "name": r.get("Name", "").strip(),
                          "reason": r.get("ReasonsOfDisposition", ""),
                          "period": r.get("DispositionPeriod", ""), "measure": r.get("DispositionMeasures", "")}
                         for r in rows if re.fullmatch(r"\d{4}", (r.get("Code") or "").strip())])


def attention() -> pd.DataFrame:
    """注意股。"""
    rows = get(f"{OAPI}/announcement/notice")
    return pd.DataFrame([{"code": r["Code"].strip(), "name": r.get("Name", "").strip(),
                          "reason": r.get("TradingInfoForAttention", "")}
                         for r in rows if re.fullmatch(r"\d{4}", (r.get("Code") or "").strip())])


# ---------- 盤中即時（MIS） ----------
def realtime(codes: list[str]) -> list[dict]:
    """盤中即時報價，一次最多 50 檔。上櫃代號請用 'otc_' 前綴，否則視為上市。"""
    out = []
    for i in range(0, len(codes), 50):
        chunk = codes[i:i + 50]
        ex = "|".join(c if c.startswith(("tse_", "otc_")) else f"tse_{c}.tw" for c in chunk)
        j = get("https://mis.twse.com.tw/stock/api/getStockInfo.jsp",
                {"ex_ch": ex, "json": "1", "delay": "0"}, timeout=15)
        for m in j.get("msgArray", []):
            # 成交價 z 在「近 5 秒無成交」或鎖漲跌停時為 '-' 或 0 → 依序改用最佳買價、最佳賣價、鎖價
            h_, l_ = num(m.get("h")), num(m.get("l"))
            cands = [num(m.get("z")), num((m.get("b") or "").split("_")[0]),
                     num((m.get("a") or "").split("_")[0]), h_ if h_ and h_ == l_ else None]
            z = next((c for c in cands if c), None)
            y = num(m.get("y"))
            out.append({"code": m.get("c"), "name": m.get("n"), "price": z, "prev": y,
                        "open": num(m.get("o")), "high": num(m.get("h")), "low": num(m.get("l")),
                        "volume": num(m.get("v")), "time": m.get("t"), "date": m.get("d"),
                        "chg_pct": (z / y - 1) * 100 if z and y else None})
    return out
