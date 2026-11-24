"""資料層總管：更新快取並回傳計算所需的所有 DataFrame。

更新策略（節省 API 額度）：
- K 線：股票首次出現 → FinMind 回補 N 年；之後缺幾天就用 TWSE MI_INDEX 逐日補（一次請求含全市場）
- 籌碼：T86 + MI_MARGN 逐日（全市場），保留 chip_days 個交易日
- 外資持股：MI_QFIIS 取最新日與 20 個交易日前
- 基本面 / 事件：openapi 每次重抓（各 1 次請求）
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from . import fetch_finmind as fm
from . import fetch_twse as tw
from . import store


def _d8(iso: str) -> str:
    return iso.replace("-", "")


def build_universe(info: pd.DataFrame, last: pd.DataFrame, cfg: dict, mode: str) -> pd.DataFrame:
    """mode: 'all' = 自選股 + 市值前 N；'watchlist' = 只有自選股。"""
    df = info.merge(last[["code", "close"]], on="code", how="inner")
    df = df[df["code"].str.fullmatch(r"\d{4}")]          # 普通股
    df["mcap"] = df["close"] * df["shares"]
    df = df.sort_values("mcap", ascending=False).reset_index(drop=True)
    df["mcap_rank"] = df.index + 1
    wl = set(cfg["watchlist"])
    n = cfg["top_n_by_mcap"] if mode == "all" else 0
    sel = df[(df["mcap_rank"] <= n) | df["code"].isin(wl)].copy()
    sel["tags"] = sel.apply(lambda r: [t for t, ok in [
        ("自選", r.code in wl), ("市值前50", r.mcap_rank <= 50),
        ("中型100", 50 < r.mcap_rank <= 150)] if ok], axis=1)
    missing = wl - set(sel["code"])
    if missing:
        print(f"⚠ 自選股不在上市普通股清單（可能是上櫃或代號錯誤），略過：{sorted(missing)}")
    return sel.drop(columns=["close"]).reset_index(drop=True)


def update_prices(codes: list[str], trade_dates: list[str], years: int, log=print) -> pd.DataFrame:
    px = store.load("prices")
    start = (date.today() - timedelta(days=365 * years + 10)).isoformat()
    have = px.groupby("code")["date"].agg(["min", "max", "count"]) if not px.empty else pd.DataFrame()
    need_backfill = [c for c in codes if c not in have.index or have.loc[c, "count"] < 120]
    if need_backfill:
        log(f"  K 線回補 {len(need_backfill)} 檔（FinMind，自 {start}）…")
        parts = []
        for i, c in enumerate(need_backfill, 1):
            try:
                parts.append(fm.price_history(c, start))
            except Exception as e:
                log(f"    {c} 回補失敗：{e}")
            if i % 25 == 0:
                log(f"    {i}/{len(need_backfill)}")
        px = store.upsert("prices", pd.concat(parts) if parts else None, ["code", "date"])

    # 逐日補齊：以「全部股票共同最新日」為準
    sub = px[px["code"].isin(codes)]
    last_common = sub.groupby("code")["date"].max().min() if not sub.empty else start
    missing = [d for d in trade_dates if d > last_common]
    if len(missing) > 25:  # 太久沒跑 → 對每檔用 FinMind 增量
        log(f"  落後 {len(missing)} 個交易日，改用 FinMind 增量…")
        parts = [fm.price_history(c, last_common) for c in codes]
        px = store.upsert("prices", pd.concat(parts), ["code", "date"])
    elif missing:
        log(f"  逐日補 K 線 {len(missing)} 天（TWSE）…")
        for d in missing:
            r = tw.daily_by_date(_d8(d))
            if r is not None and not r["prices"].empty:
                px = store.upsert("prices", r["prices"][r["prices"]["code"].isin(codes)], ["code", "date"])
    return px[px["code"].isin(codes)].copy()


def update_chips(trade_dates: list[str], days: int, log=print) -> pd.DataFrame:
    want = trade_dates[-days:]
    ch = store.load("chips")
    have = set(ch["date"]) if not ch.empty else set()
    missing = [d for d in want if d not in have]
    if missing:
        log(f"  籌碼補 {len(missing)} 天（T86 + 融資券，每天 2 次請求，約 {len(missing) * 5 // 60 + 1} 分鐘）…")
    for i, d in enumerate(missing, 1):
        a, m = tw.t86(_d8(d)), tw.margin(_d8(d))
        if a is None and m is None:
            continue
        df = a if m is None else (m if a is None else a.merge(m, on=["date", "code"], how="outer"))
        ch = store.upsert("chips", df, ["date", "code"])
        if i % 10 == 0:
            log(f"    {i}/{len(missing)}")
    ch = ch[ch["date"].isin(want)] if not ch.empty else ch
    store.save("chips", ch)
    return ch


def update_qfiis(trade_dates: list[str], log=print) -> pd.DataFrame:
    want = [trade_dates[-21], trade_dates[-1]] if len(trade_dates) > 21 else trade_dates[-1:]
    q = store.load("qfiis")
    for d in want:
        if q.empty or d not in set(q["date"]):
            r = tw.qfiis(_d8(d))
            if r is not None:
                q = store.upsert("qfiis", r, ["date", "code"])
    q = q[q["date"].isin(want)]
    store.save("qfiis", q)
    return q


def update_market(trade_start: str, log=print) -> dict:
    tx = store.upsert("taiex", fm.taiex_history(trade_start), ["date"])
    start60 = (date.today() - timedelta(days=120)).isoformat()
    out = {"taiex": tx}
    for name, fn in [("fut_oi", fm.futures_foreign_oi), ("usd", fm.usd_twd),
                     ("inst_total", fm.total_institutional), ("vix", fm.vix)]:
        try:
            out[name] = fn(start60)
        except Exception as e:
            log(f"  {name} 取得失敗：{e}")
            out[name] = pd.DataFrame()
    if out["vix"].empty:
        log("  VIX 無法取得（yfinance），將略過此項")
    return out


def update_all(cfg: dict, mode: str = "all", log=print) -> dict:
    log("① 公司基本資料 / 最新收盤…")
    info = tw.company_info()
    last = tw.latest_day_all()
    latest = last["date"].max()
    uni = build_universe(info, last, cfg, mode)
    codes = uni["code"].tolist()
    log(f"  最新交易日 {latest}｜股票池 {len(codes)} 檔")

    log("② 大盤（加權指數、期貨外資、匯率、VIX）…")
    start = (date.today() - timedelta(days=365 * cfg["history_years"] + 10)).isoformat()
    mkt = update_market(start, log)
    trade_dates = sorted(set(mkt["taiex"]["date"]) | {latest})
    trade_dates = [d for d in trade_dates if d <= latest]
    if mkt["taiex"]["date"].max() < latest:  # FinMind 尚未更新 → 用 TWSE 補當日指數
        r = tw.daily_by_date(_d8(latest))
        if r and r["taiex"]:
            mkt["taiex"] = store.upsert("taiex", pd.DataFrame([{"date": latest, "close": r["taiex"]}]), ["date"])

    log("③ K 線…")
    px = update_prices(codes, trade_dates, cfg["history_years"], log)
    # 最新一天用 STOCK_DAY_ALL 覆蓋（最即時）
    px = pd.concat([px, last[last["code"].isin(codes)]]).drop_duplicates(["code", "date"], keep="last")

    log("④ 籌碼（法人、融資券、外資持股）…")
    chips = update_chips(trade_dates, cfg["chip_days"], log)
    qf = update_qfiis(trade_dates, log)

    log("⑤ 基本面、事件…")
    fund = tw.revenue().merge(tw.eps(), on="code", how="outer").merge(tw.valuation(), on="code", how="outer")
    events = {"material": tw.material_news(), "disposition": tw.disposition(), "attention": tw.attention()}

    # 全市場漲跌家數（以最新日全部普通股計）
    common = last[last["code"].str.fullmatch(r"\d{4}")]
    return {"info": info, "universe": uni, "prices": px.sort_values(["code", "date"]),
            "chips": chips, "qfiis": qf, "fund": fund, "events": events, "market": mkt,
            "latest": latest, "trade_dates": trade_dates, "last_all": common}
