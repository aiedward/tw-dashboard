"""HTTP 工具：共用 session、依主機節流、重試、數字解析。"""
from __future__ import annotations

import re
import time
from urllib.parse import urlparse

import requests

_S = requests.Session()
_S.headers["User-Agent"] = "Mozilla/5.0 (tw-dashboard)"
_last: dict[str, float] = {}
# TWSE 對短時間大量請求會封 IP，間隔保守一點
GAP = {"www.twse.com.tw": 2.5, "api.finmindtrade.com": 0.3, "news.google.com": 0.6,
       "openapi.twse.com.tw": 0.3, "mis.twse.com.tw": 0.5}


def get(url: str, params: dict | None = None, *, headers: dict | None = None,
        retries: int = 3, timeout: int = 30, as_json: bool = True):
    host = urlparse(url).netloc
    gap = GAP.get(host, 0.0)
    for i in range(retries):
        wait = _last.get(host, 0.0) + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
        try:
            r = _S.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json() if as_json else r.text
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(4 * (i + 1))


_NUM = re.compile(r"[^\d.\-]")


def num(s) -> float | None:
    """'1,234.5' → 1234.5；'--'、''、'X' → None。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    t = _NUM.sub("", str(s))
    if t in ("", "-", ".", "-."):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def roc_to_iso(s: str) -> str:
    """'1151123' 或 '115/11/23' → '2026-11-23'。"""
    t = re.sub(r"\D", "", str(s))
    y, m, d = int(t[:-4]) + 1911, t[-4:-2], t[-2:]
    return f"{y}-{m}-{d}"
