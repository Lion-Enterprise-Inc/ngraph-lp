# -*- coding: utf-8 -*-
"""記事をコミットしたのに、表紙の文言記録（_eyecatch.json）を置いてきていないかを見る（2026-08-19新設）。

きっかけ: 2日で2回起きた。
  1. 8/18 — commit 7eaedae「表紙の文言記録（_eyecatch.json）の追随漏れを解消」
  2. 8/19 — 夕B型 20260819-106man-kabe を公開したcommitに _eyecatch.json が入っていなかった

_eyecatch.json は eyecatch_gen.py が生成時に書く「その表紙を作った時点の文言と記事タイトル」で、
`eyecatch_text_check.py`（改題したのに表紙が旧文言のまま、を捕まえる検査）の唯一の記録場所。
記事だけpushして記録を置いていくと、**本番の表紙には文言があるのにリポジトリには無い**状態になり、
次に改題したときズレを検知できない＝検査が静かに死ぬ。

unpushed_check.py は同じ状態を名指ししているが report-only（並行セッションのファイルでpushを
止めないため）。こちらは **slugで結び付いた1組だけ**を見るので、他人の作業中ファイルには当たらない。
そのぶん止める。

NG条件: _eyecatch.json の未コミットの差分に slug が現れ、かつ blog/<slug>.html が HEAD にある
        （＝記事はもう入っているのに、表紙の記録だけ置いてきている）
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REC = "assets/blog/_eyecatch.json"


def git(*args):
    r = subprocess.run(
        ["git"] + list(args), cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "")


def main():
    code, diff = git("diff", "HEAD", "--", REC)
    if code != 0:
        print("参考 gitが読めないため対象外")
        return 0
    if not diff.strip():
        print("OK: 表紙の文言記録に未コミットの変更なし")
        return 0

    slugs = sorted(set(re.findall(r'^\+\s*"([^"]+)"\s*:\s*\{', diff, re.M)))
    fails = []
    for slug in slugs:
        rc, _ = git("cat-file", "-e", "HEAD:blog/%s.html" % slug)
        if rc == 0:
            fails.append(slug)

    if fails:
        print("NG 記事はコミット済みなのに、表紙の文言記録が未コミット:")
        for slug in fails:
            print("  - %s（blog/%s.html はHEADにある）" % (slug, slug))
        print("  → git add %s して同じcommitに入れる" % REC)
        print("  記録が本番に無いと、改題したとき表紙とのズレを誰も検知できない")
        return 1

    if slugs:
        print("OK: 表紙の記録に未コミットのslugはあるが、記事もまだ未コミット（%s）" % "、".join(slugs))
    else:
        print("OK: 表紙の文言記録の追随漏れなし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
