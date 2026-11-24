"""Telegram 推播。需要 Secrets：TELEGRAM_BOT_TOKEN、TELEGRAM_CHAT_ID。"""
from __future__ import annotations

import requests

from .config import get_secret


def send(text: str) -> bool:
    tok, chat = get_secret("TELEGRAM_BOT_TOKEN"), get_secret("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        print("  未設定 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID，略過推播")
        return False
    ok = True
    for i in range(0, len(text), 3800):  # Telegram 單則上限 4096 字
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": text[i:i + 3800], "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=20)
        ok &= r.ok
        if not r.ok:
            print(f"  Telegram 失敗：{r.status_code} {r.text[:200]}")
    return ok


def daily_digest(date: str, S, mlight: dict, port: dict, site_url: str | None = None) -> str:
    icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[mlight["light"]]
    lines = [f"<b>📊 台股儀表板 {date}</b>", f"{icon} 大盤：{mlight['label']}（{mlight['score']:+d}）"]
    for it in mlight["items"]:
        lines.append(f"  · {it['label']}：{it['note']}")

    buy = S[S["signal"] == "關注買點"].head(8)
    if len(buy):
        lines.append("\n<b>🎯 關注買點</b>")
        lines += [f"  {c} 總分 {r.total:.0f}｜收 {r.close}｜停損 {r.stop}" for c, r in buy.iterrows()]
    lines.append("\n<b>🏆 綜合評分前 5</b>")
    lines += [f"  {c} {r.total:.0f}（技{r.tech:.0f} 籌{r.chip:.0f} 基{r.fund:.0f}）" for c, r in S.head(5).iterrows()]

    alerts = []
    for p in port.get("positions", []):
        if "price" not in p:
            continue
        if p["hit_stop"]:
            alerts.append(f"  ⛔ {p['code']} {p['name']} 跌破停損 {p['stop']}（現價 {p['price']}）")
        elif p["hit_target"]:
            alerts.append(f"  ✅ {p['code']} {p['name']} 達停利 {p['target']}（現價 {p['price']}）")
        elif p.get("signal") in ("警示", "處置"):
            alerts.append(f"  ⚠️ {p['code']} {p['name']} 訊號：{p['signal']}（總分 {p['score']:.0f}）")
    if alerts:
        lines.append("\n<b>💼 持股警示</b>")
        lines += alerts
    if port.get("positions"):
        lines.append(f"\n持股市值 {port['total_value']:,}｜損益 {port['total_pnl']:+,}"
                     + (f"｜1 日 VaR95 {port.get('var95_1d_amt', 0):,}" if port.get("var95_1d_amt") else ""))
    if site_url:
        lines.append(f"\n🔗 {site_url}")
    return "\n".join(lines)
