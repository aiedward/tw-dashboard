"""parquet 快取：讀、寫、依鍵 upsert。"""
from __future__ import annotations

import pandas as pd

from .config import CACHE_DIR


def load(name: str) -> pd.DataFrame:
    p = CACHE_DIR / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def save(name: str, df: pd.DataFrame) -> None:
    df.reset_index(drop=True).to_parquet(CACHE_DIR / f"{name}.parquet", index=False)


def upsert(name: str, new: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    old = load(name)
    if new is None or new.empty:
        return old
    df = pd.concat([old, new], ignore_index=True) if not old.empty else new.copy()
    df = df.drop_duplicates(keys, keep="last").sort_values(keys).reset_index(drop=True)
    save(name, df)
    return df
