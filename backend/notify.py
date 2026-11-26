"""Telegram 推播。需要 Secrets：TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID。"""
from __future__ import annotations

import html
import re

import requests

from .config import get_secret

LIMIT = 3800  # Telegram 單則上限 4096 字


def _e(x) -> str:
    """跳脫動態文字（Telegram HTML 模式下裸 < > & 會造成 400 can't parse entities）。"""
    return html.escape(str(x), quote=False)


def _chunks(text: str, limit: int = LIMIT) -> list[str]:
    """依行切段，避免把 <b>…</b> 切成兩半；單行超長才硬切。"""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:limit])
            line = line[limit:]
        cand = f"{cur}\n{line}" if cur else line
        if len(cand) > limit:
            out.append(cur)
            cur = line
        else:
            cur = cand
    if cur:
        out.append(cur)
    return out


def _hint(status: int, desc: str) -> str:
    d = desc.lower()
    if status == 401:
        return "TELEGRAM_BOT_TOKEN 錯誤（請到 @BotFather 重新複製）"
    if "chat not found" in d:
        return "找不到聊天室：請先對 bot 傳 /start，並確認 TELEGRAM_CHAT_ID（可開 https://api.telegram.org/bot<TOKEN>/getUpdates 查）"
    if status == 403:
        return "bot 被封鎖或未加入該群組"
    return ""


def _post(tok: str, chat: str, text: str, html_mode: bool) -> requests.Response:
    body = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if html_mode:
        body["parse_mode"] = "HTML"
    return requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", json=body, timeout=20)


def send(text: str) -> bool:
    tok, chat = get_secret("TELEGRAM_BOT_TOKEN"), get_secret("TELEGRAM_CHAT_ID")
    tok, chat = (tok or "").strip(), (chat or "").strip()
    if not tok or not chat:
        print("  未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，略過推播")
        return False
    ok = True
    for part in _chunks(text):
        try:
            r = _post(tok, chat, part, True)
            if r.status_code == 400 and "can't parse entities" in r.text:
                # 保險：HTML 解析失敗就改送純文字
                plain = html.unescape(re.sub(r"</?b>", "", part))
                r = _post(tok, chat, plain, False)
        except requests.RequestException as ex:
            print(f"  Telegram 連線失敗：{ex}")
            ok = False
            continue
        if not r.ok:
            ok = False
            try:
                desc = r.json().get("description", r.text)
            except ValueError:
                desc = r.text
            h = _hint(r.status_code, desc)
            print(f"  Telegram 失敗：{r.status_code} {desc[:200]}" + (f"\n  → {h}" if h else ""))
    return ok


def daily_digest(date: str, S, mlight: dict, port: dict, site_url: str | None = None) -> str:
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[mlight["light"]]
    lines = [f"<b>📊 台股儀表板 {_e(date)}</b>", f"{icon} 大盤：{_e(mlight['label'])}（{mlight['score']:+d}）"]
    for it in mlight["items"]:
        lines.append(f"  · {_e(it['label'])}：{_e(it['note'])}")

    buy = S[S["signal"] == "關注買點"].head(8)
    if len(buy):
        lines.append("\n<b>🎯 關注買點</b>")
        lines += [f"  {_e(c)} 總分 {r.total:.0f}｜收 {r.close}｜停損 {r.stop}" for c, r in buy.iterrows()]
    lines.append("\n<b>🏆 綜合評分前 5</b>")
    lines += [f"  {_e(c)} {r.total:.0f}（技{r.tech:.0f} 籌{r.chip:.0f} 基{r.fund:.0f}）" for c, r in S.head(5).iterrows()]

    alerts = []
    for p in port.get("positions", []):
        if "price" not in p:
            continue
        code, name = _e(p["code"]), _e(p["name"])
        if p["hit_stop"]:
            alerts.append(f"  ⛔ {code} {name} 跌破停損 {p['stop']}（現價 {p['price']}）")
        elif p["hit_target"]:
            alerts.append(f"  ✅ {code} {name} 達停利 {p['target']}（現價 {p['price']}）")
        elif p.get("signal") in ("警示", "處置"):
            alerts.append(f"  ⚠️ {code} {name} 訊號：{_e(p['signal'])}（總分 {p['score']:.0f}）")
    if alerts:
        lines.append("\n<b>💼 持股警示</b>")
        lines += alerts
    if port.get("positions"):
        lines.append(f"\n持股市值 {port['total_value']:,}｜損益 {port['total_pnl']:+,}"
                     + (f"｜1 日 VaR95 {port.get('var95_1d_amt', 0):,}" if port.get("var95_1d_amt") else ""))
    if site_url:
        lines.append(f"\n🔗 {_e(site_url)}")
    return "\n".join(lines)
