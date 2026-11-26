"""離線單元測試：指標、評分範圍、JSON 清理、數字解析。不連網。"""
import json

import numpy as np
import pandas as pd
import pytest

from backend import indicators as ind
from backend import scoring
from backend.export import _clean
from backend.net import num, roc_to_iso


def fake_prices(code, n=260, seed=0, drift=0.0005):
    rng = np.random.default_rng(seed)
    c = 100 * np.exp(np.cumsum(rng.normal(drift, 0.02, n)))
    dates = pd.bdate_range("2025-06-01", periods=n).strftime("%Y-%m-%d")
    return pd.DataFrame({"date": dates, "code": code, "open": c * 0.995, "high": c * 1.01,
                         "low": c * 0.99, "close": c, "volume": rng.integers(1e6, 5e6, n).astype(float)})


def test_num_and_roc():
    assert num("1,234.5") == 1234.5
    assert num("--") is None and num("") is None and num(None) is None
    assert num("-0.76") == -0.76
    assert roc_to_iso("1151123") == "2026-11-23"
    assert roc_to_iso("115/01/05") == "2026-01-05"


def test_rsi_bounds_and_trend():
    up = pd.Series(np.linspace(10, 20, 50))
    assert ind.rsi(up).iloc[-1] > 95
    r = ind.rsi(pd.Series(np.random.default_rng(1).normal(0, 1, 300).cumsum() + 100))
    assert r.between(0, 100).all()


def test_add_all_columns():
    df = ind.add_all(fake_prices("A").set_index("date"))
    for c in ["ma20", "macd_hist", "rsi", "bb_pct", "atr", "adx", "k", "d", "vol_ratio"]:
        assert c in df and df[c].iloc[-1] == df[c].iloc[-1]  # 非 NaN
    assert (df["atr"].dropna() > 0).all()
    # MA20 與 pandas rolling 一致
    assert df["ma20"].iloc[-1] == pytest.approx(df["close"].tail(20).mean())


def test_pr_and_scores_range():
    s = pd.Series([1, 2, 3, np.nan])
    p = scoring.pr(s)
    assert p.iloc[2] == 100 and p.iloc[3] == 50
    assert scoring.pr(s, False).iloc[0] == 100


def make_d(codes):
    px = pd.concat([fake_prices(c, seed=i, drift=0.002 * (i - 2)) for i, c in enumerate(codes)])
    dates = sorted(px["date"].unique())
    chips = pd.DataFrame([{"date": d, "code": c, "foreign": (i - 2) * 1e5, "trust": i * 1e4, "dealer": 0,
                           "margin_bal": 1000 + j, "short_bal": 50, "margin_use": 10.0 + i}
                          for j, d in enumerate(dates[-30:]) for i, c in enumerate(codes)])
    uni = pd.DataFrame({"code": codes, "name": codes, "industry": ["半導體", "半導體", "航運", "航運", "金融保險"],
                        "shares": 1e9, "mcap": 1e11, "mcap_rank": range(1, 6), "tags": [["自選"]] * 5})
    fund = pd.DataFrame({"code": codes, "rev_yoy": [10, 20, -5, 3, 0], "rev_mom": 1.0, "rev_cum_yoy": [5, 8, -2, 1, 0],
                         "eps_q": [3, 2, 1, 0.5, 0.2], "op_margin": [40, 20, 10, 5, 30], "pe": [20, 15, 8, 30, 12],
                         "yield": [2, 3, 6, 1, 5], "pb": [5, 3, 1, 2, 1]})
    taiex = pd.DataFrame({"date": dates, "close": np.linspace(20000, 23000, len(dates))})
    ev = {"disposition": pd.DataFrame({"code": ["E"]}), "attention": pd.DataFrame(), "material": pd.DataFrame()}
    return {"prices": px, "chips": chips, "qfiis": pd.DataFrame(), "universe": uni, "fund": fund,
            "events": ev, "market": {"taiex": taiex}}


def test_compute_full():
    codes = list("ABCDE")
    d = make_d(codes)
    frames = scoring.stock_frames(d["prices"])
    S = scoring.compute(d, frames, {"A": 2.0, "B": -2.0}, {"tech": 30, "chip": 30, "fund": 20, "news": 10, "risk": 10})
    for k in scoring.DIMS + ["total"]:
        assert S[k].between(0, 100).all(), k
    assert S.loc["A", "news"] == 100 and S.loc["B", "news"] == 0
    assert S.loc["E", "signal"] == "處置"
    assert S.loc["E", "risk"] <= 60
    assert (S["stop"] < S["close"]).all() and (S["target"] > S["close"]).all()
    # 權重全給技術 → 總分 = 技術分
    S2 = scoring.compute(d, frames, {}, {"tech": 1, "chip": 0, "fund": 0, "news": 0, "risk": 0})
    assert (S2["total"] - S2["tech"]).abs().max() < 0.11


def test_portfolio_and_light():
    from backend import risk
    codes = list("ABCDE")
    d = make_d(codes)
    frames = scoring.stock_frames(d["prices"])
    S = scoring.compute(d, frames, {}, {"tech": 1, "chip": 1, "fund": 1, "news": 1, "risk": 1})
    h = {"capital": 1e6, "positions": [{"code": "A", "shares": 1000, "cost": 90}, {"code": "Z", "shares": 1, "cost": 1}]}
    p = risk.portfolio(h, frames, S, d["universe"])
    assert p["positions"][1]["error"]
    assert sum(r["weight"] for r in p["positions"] if "weight" in r) == pytest.approx(100)
    m = risk.market_light({"taiex": d["market"]["taiex"]}, None)
    assert m["light"] in ("green", "yellow", "red")


def test_clean_json():
    o = _clean({"a": np.float64("nan"), "b": np.int64(3), "c": [np.bool_(True), 1.23456789]})
    assert json.loads(json.dumps(o)) == {"a": None, "b": 3, "c": [True, 1.2346]}


def _strip_tags(s):
    return s.replace("<b>", "").replace("</b>", "")


def test_digest_html_safe():
    from backend import notify, risk
    codes = list("ABCDE")
    d = make_d(codes)
    d["universe"].loc[0, "name"] = "A&B<測試>"
    frames = scoring.stock_frames(d["prices"])
    S = scoring.compute(d, frames, {}, {"tech": 1, "chip": 1, "fund": 1, "news": 1, "risk": 1})
    p = risk.portfolio({"capital": 1e6, "positions": [{"code": "A", "shares": 1000, "cost": 90, "stop": 1e9}]},
                       frames, S, d["universe"])
    vix = pd.DataFrame({"date": ["2026-11-25"], "vix": [20.0]})
    m = risk.market_light({"taiex": d["market"]["taiex"], "vix": vix}, None)
    assert any("<" in it["note"] for it in m["items"])  # 重現原本的 "< 18" 問題
    msg = notify.daily_digest("2026-11-25", S, m, p, "https://x.github.io/y/?a=1&b=2")
    body = _strip_tags(msg)
    assert "<" not in body and ">" not in body
    import re
    assert not re.search(r"&(?!amp;|lt;|gt;)", body)
    assert "&lt; 18" in msg and "A&amp;B&lt;測試&gt;" in msg


def test_send_chunks_by_line(monkeypatch):
    from backend import notify
    sent = []

    class R:
        ok, status_code, text = True, 200, "{}"

    monkeypatch.setattr(notify, "get_secret", lambda n: " tok \n" if "TOKEN" in n else " 123 ")
    monkeypatch.setattr(notify.requests, "post", lambda url, json, timeout: (sent.append((url, json)), R())[1])
    text = "\n".join(f"<b>標題 {i}</b> " + "字" * 50 for i in range(200))
    assert notify.send(text)
    assert len(sent) > 1
    for url, j in sent:
        assert "/bottok/" in url and j["chat_id"] == "123"
        assert len(j["text"]) <= notify.LIMIT
        assert j["text"].count("<b>") == j["text"].count("</b>")


def test_send_falls_back_to_plain(monkeypatch):
    from backend import notify
    sent = []

    class Bad:
        ok, status_code, text = False, 400, '{"description":"Bad Request: can\'t parse entities"}'

    class Good:
        ok, status_code, text = True, 200, "{}"

    monkeypatch.setattr(notify, "get_secret", lambda n: "x")
    monkeypatch.setattr(notify.requests, "post",
                        lambda url, json, timeout: (sent.append(json), Bad() if "parse_mode" in json else Good())[1])
    assert notify.send("<b>hi</b> 1 &lt; 2")
    assert sent[-1]["text"] == "hi 1 < 2" and "parse_mode" not in sent[-1]
