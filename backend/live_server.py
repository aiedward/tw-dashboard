"""即時模式：FastAPI 提供 /health、/quotes；cloudflared 快速通道（免帳號）對外公開。

Colab：
    from backend import live_server
    url = live_server.start()          # 啟動並回傳 https://xxxx.trycloudflare.com
    live_server.stop()                 # 結束
"""
from __future__ import annotations

import os
import platform
import re
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from . import fetch_twse as tw
from .net import get, num

TZ = timezone(timedelta(hours=8))
app = FastAPI(title="tw-dashboard live")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

_cache: dict = {"t": 0.0, "key": "", "data": None}
_lock = threading.Lock()


def _taiex() -> dict | None:
    try:
        j = get("https://mis.twse.com.tw/stock/api/getStockInfo.jsp", {"ex_ch": "tse_t00.tw", "json": "1", "delay": "0"}, timeout=10)
        m = j["msgArray"][0]
        z, y = num(m.get("z")), num(m.get("y"))
        return {"price": z, "prev": y, "chg_pct": (z / y - 1) * 100 if z and y else None, "time": m.get("t")}
    except Exception:
        return None


@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(TZ).strftime("%H:%M:%S")}


@app.get("/quotes")
def quotes(codes: str = Query(..., max_length=2000)):
    cl = [c for c in codes.split(",") if re.fullmatch(r"\d{4,6}[A-Z]?", c)][:300]
    key = ",".join(cl)
    with _lock:
        if _cache["data"] and _cache["key"] == key and time.time() - _cache["t"] < 8:
            return _cache["data"]
        data = {"time": datetime.now(TZ).strftime("%H:%M:%S"), "market": _taiex(), "quotes": tw.realtime(cl)}
        _cache.update(t=time.time(), key=key, data=data)
        return data


# ---------- 啟動 ----------
_procs: dict = {}


def _cloudflared() -> str:
    path = "/tmp/cloudflared" if platform.system() != "Windows" else os.path.join(os.environ.get("TEMP", "."), "cloudflared.exe")
    if not os.path.exists(path):
        arch = "arm64" if platform.machine() in ("aarch64", "arm64") else "amd64"
        name = f"cloudflared-windows-{arch}.exe" if platform.system() == "Windows" else f"cloudflared-linux-{arch}"
        urllib.request.urlretrieve(f"https://github.com/cloudflare/cloudflared/releases/latest/download/{name}", path)
        os.chmod(path, 0o755)
    return path


def start(port: int = 8765, tunnel: bool = True, timeout: int = 40) -> str:
    import uvicorn
    stop()
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    _procs["server"] = server
    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    local = f"http://127.0.0.1:{port}"
    if not tunnel:
        return local
    p = subprocess.Popen([_cloudflared(), "tunnel", "--no-autoupdate", "--url", local],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _procs["tunnel"] = p
    t0 = time.time()
    while time.time() - t0 < timeout:
        line = p.stdout.readline()
        m = re.search(r"https://[-a-z0-9]+\.trycloudflare\.com", line or "")
        if m:
            url = m.group(0)
            # 等 DNS 生效
            for _ in range(20):
                try:
                    urllib.request.urlopen(f"{url}/health", timeout=5)
                    break
                except Exception:
                    time.sleep(1.5)
            threading.Thread(target=lambda: [None for _ in p.stdout], daemon=True).start()  # 持續讀取避免阻塞
            return url
    raise RuntimeError("cloudflared 通道建立逾時")


def stop() -> None:
    if (p := _procs.pop("tunnel", None)):
        p.terminate()
    if (s := _procs.pop("server", None)):
        s.should_exit = True
