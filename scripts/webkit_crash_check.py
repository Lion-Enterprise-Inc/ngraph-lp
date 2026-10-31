#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""変えたページが WebKit（iPhone の Safari と同じ描画エンジン）のスマホ幅で落ちないかを、実際に開いて調べる。

2026-10-26 /drill/ に「IPA の自社診断」の案内を足したら、WebKit の 390・414 幅でだけ
ページごと落ちた（Page crashed）。Chromium・PC 幅では普通に表示され、目でも他の検査でも見つからない。
原因は中央寄せの段落で、折り返さない箱（.nb）の並びの間に <br> を置いたこと。
同じ書き方は他の段落にもあって、そちらは落ちない。書き方から機械で当てるのは無理なので、開いて確かめる。

対象（上から順に使う）:
  1. 引数で渡したページ（ROOT からの相対パス・絶対パスどちらでも）
  2. 環境変数 GATE_CHANGED（pre-push フックが設定する今回 push するファイル・改行区切り）
  3. 上流（@{upstream}・無ければ origin/main）との差分＋ステージ済み＋作業中の変更
  ブログ記事・部品・試作は除く。基準のブランチが見つからないときは、対象不明として失敗にする。
1回ごとに子プロセスで WebKit を起動し、時間の上限（LOAD_LIMIT 秒）で打ち切る
（落ちたページを閉じようとすると WebKit ごと固まることがあるため）。
落ちた／開けない（404 など）／時間切れ は分けて出す。検査できない環境（WebKit が無い）も失敗にする。

使い方: python scripts/webkit_crash_check.py [ページ...]   （NG があれば exit 1）
"""
import concurrent.futures
import functools
import http.server
import json
import os
import subprocess
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = (320, 375, 390, 393, 402, 414, 430)  # 2026-10-31 393・402 は実機に多い幅。ここを測らず本番の全ページが落ちていた
WORKERS = 4
LOAD_LIMIT = 60


def git_paths(*a):
    """git の出力をファイル名の一覧に。失敗したら None（変更ゼロとは区別する）。"""
    r = subprocess.run(["git", *a, "-z"], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        return None
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def is_page(p):
    if not p.endswith(".html"):
        return False
    if p.startswith(("_", ".", "scripts/", "figures/")) or "/_" in p:
        return False
    # 2026-10-31 本人「企業分析ページはデザイン不要」。cases/ は対象外
    if p.startswith(("cases/", "en/cases/")):
        return False
    if p.startswith(("blog/", "en/blog/")) and not p.endswith("index.html"):
        return False
    return True


def rel(p):
    p = os.path.abspath(os.path.join(ROOT, p)) if not os.path.isabs(p) else os.path.abspath(p)
    return os.path.relpath(p, ROOT).replace("\\", "/")


def changed_pages():
    env = os.environ.get("GATE_CHANGED", "")
    if env.strip():
        files = [rel(x.strip()) for x in env.splitlines() if x.strip()]
    else:
        base = None
        for b in ("@{upstream}", "origin/main"):
            if subprocess.run(["git", "rev-parse", "--verify", "-q", b], cwd=ROOT, capture_output=True).returncode == 0:
                base = b
                break
        if base is None:
            return None
        parts = [git_paths("diff", "--name-only", base), git_paths("diff", "--name-only", "--cached"), git_paths("diff", "--name-only")]
        if any(x is None for x in parts):
            return None
        files = sorted(set(sum(parts, [])))
    return [p for p in files if is_page(p) and os.path.exists(os.path.join(ROOT, p))]


def one(url, width):
    """子プロセス側: 1ページを1幅で開いて結果を JSON で返す。"""
    from playwright.sync_api import sync_playwright
    out = {"state": "ok"}
    with sync_playwright() as p:
        b = p.webkit.launch()
        pg = b.new_page(viewport={"width": width, "height": 900})
        crashed = []
        pg.on("crash", lambda *_: crashed.append(1))
        try:
            resp = pg.goto(url, wait_until="load", timeout=40000)
            if not url.startswith("about:") and (resp is None or resp.status >= 400):
                out = {"state": "notfound", "msg": "HTTP %s" % (resp.status if resp else "応答なし")}
            else:
                pg.evaluate("document.fonts ? document.fonts.ready.then(() => document.body.scrollHeight) : 0")
                pg.wait_for_timeout(300)
                pg.evaluate("document.body.scrollHeight")
        except Exception as e:
            msg = str(e).splitlines()[0][:80]
            out = {"state": "crash" if (crashed or "crash" in msg.lower()) else "error", "msg": msg}
        print(json.dumps(out, ensure_ascii=False))
        sys.stdout.flush()
        os._exit(0)  # 落ちたページの後始末で固まらないよう、閉じずに抜ける


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main(argv):
    if argv[:1] == ["--one"]:
        return one(argv[1], int(argv[2]))
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("NG: playwright が無いので WebKit で開けない（pip install playwright && python -m playwright install webkit）")
        return 1
    targets = [rel(a) for a in argv] if argv else changed_pages()
    if targets is None:
        print("NG: 基準のブランチ（@{upstream} / origin/main）が見つからず、変えたページが分からない。ページを引数で渡す")
        return 1
    missing = [t for t in targets if not os.path.exists(os.path.join(ROOT, t))]
    if missing:
        print("NG: ページが無い: " + ", ".join(missing))
        return 1
    if not targets:
        print("OK: 変えたページが無い（WebKit の検査は省略）")
        return 0
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    # 自己テスト: WebKit が起動できなければ検査できていない＝失敗
    probe = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", "about:blank", "390"],
                           capture_output=True, text=True, encoding="utf-8", timeout=LOAD_LIMIT)
    if '"state": "ok"' not in probe.stdout:
        print("NG: WebKit を起動できない（python -m playwright install webkit）:", (probe.stdout + probe.stderr).strip()[-200:])
        srv.shutdown()
        return 1
    bad = []
    label = {"crash": "落ちた", "notfound": "開けない", "error": "読み込みに失敗", "timeout": "時間切れ"}
    def probe_one(job):
        t, w = job
        url = "http://127.0.0.1:%d/%s" % (port, t[:-len("index.html")] if t.endswith("index.html") else t)
        try:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), "--one", url, str(w)],
                               capture_output=True, text=True, encoding="utf-8", timeout=LOAD_LIMIT)
            lines = [x for x in r.stdout.splitlines() if x.startswith("{")]
            res = json.loads(lines[-1]) if lines else {"state": "crash", "msg": (r.stderr.strip().splitlines() or ["WebKit が結果を返さない"])[-1][:120]}
        except subprocess.TimeoutExpired:
            res = {"state": "timeout", "msg": "%d 秒で終わらない" % LOAD_LIMIT}
        return t, w, res

    # 2026-10-31 全ページに効く変更で1時間を超えたので並列にする（検査の中身は同じ）
    jobs = [(t, w) for t in targets for w in WIDTHS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for t, w, res in ex.map(probe_one, jobs):
            if res["state"] == "ok":
                continue
            # 並列の負荷で読み込みが切れることがあるので、落ちた以外は1つずつ開き直して確かめる
            if res["state"] != "crash":
                t, w, res = probe_one((t, w))
            if res["state"] != "ok":
                bad.append("%s（幅%d）%s: %s" % (t, w, label[res["state"]], res.get("msg", "")))
    srv.shutdown()
    if bad:
        print("WebKit（iPhone と同じエンジン）で問題 %d 件。落ちたなら、直前に足した部品を1つずつ外して原因を探す" % len(bad))
        for x in bad:
            print("  - " + x)
        return 1
    print("OK: WebKit のスマホ幅で落ちない（%d ページ × %d 幅）" % (len(targets), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
