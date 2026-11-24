"""消息面：Google News RSS + 證交所重大訊息 → Claude Haiku 摘要與利多/利空評分。

- 每檔股票一次 API 呼叫，結果以「新聞標題組合」雜湊快取，同樣的新聞不會重複計費
- 沒有 ANTHROPIC_API_KEY 時，改用關鍵字詞典評分（較粗糙）
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
from pydantic import BaseModel, Field

from .config import CACHE_DIR, get_secret
from .net import get

MODEL = "claude-haiku-5-5"
CACHE = CACHE_DIR / "news_ai.json"
TZ = timezone(timedelta(hours=8))

POS = ["創新高", "成長", "大增", "看好", "調升", "上修", "接單", "擴產", "買超", "漲停", "獲利", "利多", "加碼", "強勁", "突破", "受惠"]
NEG = ["衰退", "下滑", "虧損", "調降", "下修", "賣超", "跌停", "利空", "減碼", "疲弱", "砍單", "裁員", "火災", "違約", "處置", "警示", "停工"]


class NewsItem(BaseModel):
    idx: int = Field(description="新聞編號（輸入清單中的編號）")
    sentiment: int = Field(description="對股價影響：-2 重大利空、-1 偏空、0 中性、1 偏多、2 重大利多")
    summary: str = Field(description="15 字以內的繁體中文重點")


class StockNews(BaseModel):
    overall: float = Field(description="綜合影響分數 -2 ~ +2，考慮重要性與時效")
    summary: str = Field(description="40 字以內繁體中文總結，給波段交易者看")
    items: list[NewsItem]


SYSTEM = ("你是台股產業分析師。根據提供的新聞標題與公司重大訊息，判斷對該股未來 1~4 週股價的影響。"
          "只依據提供的內容判斷，不要臆測；與該公司無關的新聞給 0 分。用繁體中文回答。")


def google_news(query: str, days: int = 7, limit: int = 8) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote(query)}+when:{days}d&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        feed = feedparser.parse(get(url, as_json=False, timeout=15, retries=2))
    except Exception:
        return []
    out = []
    for e in feed.entries[:limit]:
        try:
            dt = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).astimezone(TZ)
        except Exception:
            dt = datetime.now(TZ)
        title = e.get("title", "")
        src = e.get("source", {}).get("title", "") if isinstance(e.get("source"), dict) else ""
        if src and title.endswith(f" - {src}"):
            title = title[: -len(src) - 3]
        out.append({"title": title, "link": e.get("link", ""), "source": src,
                    "time": dt.strftime("%Y-%m-%d %H:%M"), "kind": "news"})
    return sorted(out, key=lambda x: x["time"], reverse=True)


def _lexicon(items: list[dict]) -> dict:
    scored = []
    for i, it in enumerate(items):
        t = it["title"]
        s = sum(w in t for w in POS) - sum(w in t for w in NEG)
        scored.append({"idx": i, "sentiment": max(-2, min(2, s)), "summary": ""})
    ov = sum(x["sentiment"] for x in scored) / len(scored) if scored else 0.0
    return {"overall": round(ov, 2), "summary": "（關鍵字評分，未使用 AI）", "items": scored, "engine": "lexicon"}


def _claude(client, code: str, name: str, items: list[dict]) -> dict:
    lines = "\n".join(f"[{i}] ({it['time'][:10]}{'｜重訊' if it['kind'] == 'material' else ''}) {it['title']}"
                      for i, it in enumerate(items))
    r = client.messages.parse(
        model=MODEL, max_tokens=2000, output_config={"effort": "low"},
        system=SYSTEM,
        messages=[{"role": "user", "content": f"股票：{code} {name}\n新聞：\n{lines}"}],
        output_format=StockNews,
    )
    if r.stop_reason == "refusal" or r.parsed_output is None:
        return _lexicon(items)
    d = r.parsed_output.model_dump()
    d["overall"] = max(-2.0, min(2.0, d["overall"]))
    d["engine"] = MODEL
    return d


def collect(universe, material, use_ai: bool = True, log=print) -> dict[str, dict]:
    """回傳 {code: {score, summary, items:[{title, link, source, time, kind, sentiment, summary}]}}。"""
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    key = get_secret("ANTHROPIC_API_KEY") if use_ai else None
    client = None
    if key:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
    log(f"  新聞評分引擎：{MODEL if client else '關鍵字詞典（未設定 ANTHROPIC_API_KEY 或已關閉 AI）'}")

    mat = {}
    if material is not None and not material.empty:
        for r in material.itertuples():
            mat.setdefault(r.code, []).append({"title": r.title, "link": "https://mops.twse.com.tw/mops/#/web/t05sr01_1",
                                               "source": "公開資訊觀測站", "time": r.date + " 00:00", "kind": "material"})

    rows = list(universe[["code", "name"]].itertuples(index=False))
    log(f"  抓取 {len(rows)} 檔新聞 RSS…")
    raw = {}
    for code, name in rows:
        raw[code] = (mat.get(code, []) + google_news(f'"{name}" {code}'))[:10]

    stats = {"cached": 0, "ai": 0, "lexicon": 0, "empty": 0}

    def work(code_name):
        code, name = code_name
        items = raw[code]
        if not items:
            stats["empty"] += 1
            return code, {"overall": 0.0, "summary": "近期無相關新聞", "items": [], "engine": "none"}
        h = hashlib.md5(("|".join(i["title"] for i in items) + (MODEL if client else "lex")).encode()).hexdigest()
        if h in cache:
            stats["cached"] += 1
            return code, cache[h]
        if client:
            try:
                res = _claude(client, code, name, items)
                stats["ai"] += 1
            except Exception as e:
                log(f"    {code} AI 失敗改用關鍵字：{type(e).__name__}")
                res = _lexicon(items)
        else:
            res = _lexicon(items)
            stats["lexicon"] += 1
        res["hash"] = h
        cache[h] = res
        return code, res

    t = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        results = dict(ex.map(work, rows))
    log(f"  新聞完成 {time.time() - t:.0f}s：AI {stats['ai']}、快取 {stats['cached']}、關鍵字 {stats['lexicon']}、無新聞 {stats['empty']}")

    # 只保留最近用到的快取，避免無限成長
    keep = {r.get("hash") for r in results.values() if r.get("hash")}
    CACHE.write_text(json.dumps({k: v for k, v in cache.items() if k in keep}, ensure_ascii=False), encoding="utf-8")

    out = {}
    now = datetime.now(TZ)
    for code, res in results.items():
        items = raw[code]
        sent = {x["idx"]: x for x in res.get("items", [])}
        merged = []
        for i, it in enumerate(items):
            s = sent.get(i, {})
            merged.append({**it, "sentiment": s.get("sentiment", 0), "summary": s.get("summary", "")})
        # 時間衰減：近 3 日權重 1，之後每天 ×0.7
        num = den = 0.0
        for m in merged:
            try:
                age = (now - datetime.strptime(m["time"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)).days
            except Exception:
                age = 0
            w = 1.0 if age <= 3 else 0.7 ** (age - 3)
            num += w * m["sentiment"]
            den += w
        decayed = num / den if den else 0.0
        score = 0.5 * res.get("overall", 0.0) + 0.5 * decayed if res.get("engine") not in ("none",) else 0.0
        out[code] = {"score": round(score, 2), "summary": res.get("summary", ""),
                     "engine": res.get("engine"), "items": merged}
    return out
