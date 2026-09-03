"""対外ページのインラインJSを node --check で構文検査する（2026-09-03）。

背景: トップの「会社の脳に聞く」で h.split(/\n+/) の改行エスケープが実改行として書き込まれ、
SyntaxError でスクリプト全体が止まったまま本番に出ていた。見た目では気づけないので機械で止める。
使い方: python scripts/js_check.py [ファイル...]   引数なし=対外ページ一式。exit 1 で失敗。
"""
import io, os, re, subprocess, sys, tempfile

TARGETS = ["index.html", "fde/index.html", "en/index.html", "en/fde/index.html",
           "company.html", "recruit.html", "entry.html", "page.html"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r'<script(?![^>]*\ssrc=)(?![^>]*type="application/ld\+json")[^>]*>([\s\S]*?)</script>', re.I)

def check(path):
    src = io.open(path, encoding="utf-8").read()
    bad = []
    for i, m in enumerate(PAT.finditer(src)):
        line = src[:m.start()].count("\n") + 1
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(m.group(1)); tmp = f.name
        try:
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
        finally:
            os.unlink(tmp)
        if r.returncode != 0:
            msg = [l for l in r.stderr.splitlines() if l.strip()][-1:]
            bad.append((i, line, msg[0] if msg else "syntax error"))
    return bad

def main(argv):
    files = argv or [t for t in TARGETS if os.path.exists(os.path.join(ROOT, t))]
    fail = 0
    for f in files:
        p = f if os.path.isabs(f) else os.path.join(ROOT, f)
        for i, line, msg in check(p):
            fail += 1
            print(f"NG {f}: script#{i} (html行{line}) {msg}")
    if fail:
        print(f"NG: インラインJSの構文エラー {fail} 件"); return 1
    print(f"OK: インラインJS構文エラーなし（{len(files)} ファイル）"); return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
