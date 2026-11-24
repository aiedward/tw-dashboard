"""發佈網站到 GitHub Pages：把 docs/（含 data/）以單一 commit 強制推到 gh-pages 分支。

main 分支只放程式碼；gh-pages 每次覆蓋、不留歷史，repo 不會因每日資料膨脹。
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import ROOT, get_secret


def _git(args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(a if 'x-access-token' not in a else '***' for a in args)}：{r.stderr.strip()[-300:]}")
    return r.stdout


def publish(repo: str, message: str = "update data", token: str | None = None, remote: str | None = None) -> str:
    """repo 格式 '帳號/tw-dashboard'。回傳 Pages 網址。"""
    token = token or get_secret("GH_TOKEN")
    if not token and not remote:
        raise RuntimeError("未設定 GH_TOKEN（Colab 左側 🔑 Secrets）")
    tmp = Path(tempfile.mkdtemp())
    try:
        shutil.copytree(ROOT / "docs", tmp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("_*.html"))
        (tmp / ".nojekyll").touch()
        _git(["init", "-q", "-b", "gh-pages"], tmp)
        _git(["config", "user.name", "tw-dashboard bot"], tmp)
        _git(["config", "user.email", "bot@users.noreply.github.com"], tmp)
        _git(["add", "-A"], tmp)
        _git(["commit", "-q", "-m", message], tmp)
        _git(["push", "-q", "-f", remote or f"https://x-access-token:{token}@github.com/{repo}.git", "gh-pages"], tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    user, name = repo.split("/")
    return f"https://{user.lower()}.github.io/{name}/"
