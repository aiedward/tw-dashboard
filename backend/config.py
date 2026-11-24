"""全域設定：路徑、股票池設定、權重、Secrets（Colab userdata 或環境變數）。"""
from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CACHE_DIR = ROOT / "cache"          # parquet 快取（不推上 GitHub，Colab 上存在 Drive）
OUT_DIR = ROOT / "docs" / "data"    # 前端讀取的 JSON（GitHub Pages）

for _d in (CACHE_DIR, OUT_DIR, OUT_DIR / "stocks"):
    _d.mkdir(parents=True, exist_ok=True)

INDUSTRY = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織纖維", "05": "電機機械", "06": "電器電纜",
    "08": "玻璃陶瓷", "09": "造紙", "10": "鋼鐵", "11": "橡膠", "12": "汽車", "14": "建材營造",
    "15": "航運", "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "19": "綜合", "20": "其他",
    "21": "化學", "22": "生技醫療", "23": "油電燃氣", "24": "半導體", "25": "電腦週邊",
    "26": "光電", "27": "通信網路", "28": "電子零組件", "29": "電子通路", "30": "資訊服務",
    "31": "其他電子", "32": "文化創意", "33": "農業科技", "34": "電子商務", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "存託憑證",
}


def load_universe_cfg() -> dict:
    with open(CONFIG_DIR / "universe.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["watchlist"] = [str(c).strip() for c in cfg.get("watchlist", []) if str(c).strip()]
    cfg.setdefault("top_n_by_mcap", 150)
    cfg.setdefault("history_years", 2)
    cfg.setdefault("chip_days", 60)
    return cfg


def load_json(name: str, default=None):
    p = CONFIG_DIR / name
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def get_secret(name: str, default: str | None = None) -> str | None:
    """先找 Colab Secrets，再找環境變數。"""
    try:
        from google.colab import userdata  # type: ignore
        v = userdata.get(name)
        if v:
            return v
    except Exception:
        pass
    return os.environ.get(name, default)
