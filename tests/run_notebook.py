"""本機模擬執行 tw_dashboard.ipynb（略過 Colab 專用的第 ① 格；發佈改推到本機 bare repo）。
用法：python tests/run_notebook.py [watchlist|all]
"""
import json, os, subprocess, sys, tempfile, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT); sys.path.insert(0, ROOT)
mode = sys.argv[1] if len(sys.argv) > 1 else "watchlist"
bare = tempfile.mkdtemp(); subprocess.run(["git", "init", "-q", "--bare", bare], check=True)

import backend.publish as P


def patch():
    mod = sys.modules["backend.publish"]
    if not getattr(mod.publish, "_patched", False):
        orig = mod.publish
        f = lambda repo, msg="", token=None, remote=None: orig(repo, msg, token, remote=bare)
        f._patched = True
        mod.publish = f

nb = json.load(open("tw_dashboard.ipynb", encoding="utf-8"))
codes = [c for c in nb["cells"] if c["cell_type"] == "code"]
ns = {"__name__": "__main__", "sys": sys, "GITHUB_REPO": "demo/tw-dashboard", "display": print}
backup = open("config/universe.yaml", encoding="utf-8").read()
try:
    for i, c in enumerate(codes, 1):
        if i in (1, 5, 6):  # ① Colab 掛載、⑤ 即時模式（長駐）、工具格
            continue
        src = "".join(c["source"]).replace('MODE = "all"', f'MODE = "{mode}"').replace("USE_AI = True", "USE_AI = bool(os.environ.get('ANTHROPIC_API_KEY'))")
        src = "import os\n" + src.replace("from IPython.display import display", "")
        t = time.time()
        patch()
        exec(compile(src, f"cell{i}", "exec"), ns)
        print(f"--- cell {i} ok ({time.time() - t:.0f}s)")
    log = subprocess.run(["git", "--git-dir", bare, "log", "--oneline", "gh-pages"], capture_output=True, text=True).stdout
    files = subprocess.run(["git", "--git-dir", bare, "ls-tree", "-r", "--name-only", "gh-pages"], capture_output=True, text=True).stdout.split()
    print("gh-pages commits:", log.strip()); print("files:", len(files), [f for f in files if not f.startswith("data/stocks/")])
finally:
    open("config/universe.yaml", "w", encoding="utf-8").write(backup)
