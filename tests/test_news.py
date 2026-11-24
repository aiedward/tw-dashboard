"""消息面 AI 呼叫：以假 client 驗證請求格式、解析、失敗時不寫快取。不連網。"""
import json
from types import SimpleNamespace as NS

import pandas as pd

from backend import fetch_news as fnews


class FakeClient:
    def __init__(self, fail_codes=()):
        self.calls, self.fail = [], set(fail_codes)
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if any(c in kw["messages"][0]["content"] for c in self.fail):
            raise RuntimeError("boom")
        body = {"overall": 3.0, "summary": "營收創高", "items": [{"idx": 0, "sentiment": 5, "summary": "利多"}]}
        return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(body, ensure_ascii=False))])


def test_request_shape_and_clamp():
    c = FakeClient()
    d = fnews._claude(c, "2330", "台積電", [{"time": "2026-11-24 10:00", "kind": "news", "title": "營收創高"}])
    kw = c.calls[0]
    assert kw["model"] == "claude-haiku-5-5"
    oc = kw["output_config"]
    assert oc["effort"] == "low" and oc["format"]["type"] == "json_schema"
    assert oc["format"]["schema"]["additionalProperties"] is False
    assert "output_format" not in kw and "temperature" not in kw and "thinking" not in kw
    assert kw["messages"][-1]["role"] == "user"          # 無 prefill
    assert d["overall"] == 2.0 and d["items"][0]["sentiment"] == 2  # 夾在 ±2


def test_failure_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(fnews, "CACHE", tmp_path / "news_ai.json")
    monkeypatch.setattr(fnews, "google_news", lambda q: [{"title": f"新聞 {q}", "link": "", "source": "s",
                                                          "time": "2026-11-24 10:00", "kind": "news"}])
    fake = FakeClient(fail_codes=["2317"])
    monkeypatch.setattr(fnews, "get_secret", lambda k: "x")
    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", lambda api_key: fake)
    uni = pd.DataFrame({"code": ["2330", "2317"], "name": ["台積電", "鴻海"]})
    out = fnews.collect(uni, None, use_ai=True, log=lambda *a: None)
    assert out["2330"]["engine"] == "claude-haiku-5-5"
    assert out["2317"]["engine"] == "lexicon"
    cache = json.loads((tmp_path / "news_ai.json").read_text(encoding="utf-8"))
    assert all(v["engine"] == "claude-haiku-5-5" for v in cache.values())  # 失敗的沒寫入
    # 再跑一次：2330 走快取，2317 會重試 AI
    n = len(fake.calls)
    fnews.collect(uni, None, use_ai=True, log=lambda *a: None)
    assert len(fake.calls) == n + 1
