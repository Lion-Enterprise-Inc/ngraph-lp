#!/usr/bin/env python3
"""ブログ記事タイトルの機械検査（push前ゲート・url_canon.py と並置）

2026-08-08新設。8/6夕記事「正本をつくったのに、AIが読まなかった——…」を
8/8に「AIは指示を一定確率で無視する——…」へ改題した事例が起点。
シャープさ自体は機械で測れないので、ここで落とすのは「弱いタイトルの定型」だけ。
言い切りの検査（タイトルだけで主張が復元できるか）は BLOG-OPS §9 のチェックリストで行う。

対象: blog/2026*.html のうち slug が 20260808 以降の記事のみ（既存記事は対象外）。
恒久ページ（what-is-fde 等・日付なしslug）はキーワード狙いのため対象外。
"""
import glob
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF = "20260808"

NG_PATTERNS = [
    (r"(という話|した話|になった話|してみた話|する話)$", "「〜話」で終わる＝主張のぼかし。言い切る"),
    (r"(のか|でしょうか|だろうか|どうなる)$", "疑問で終わっている＝答えを先に言う"),
    (r"？$", "疑問符で終わっている＝答えを先に言う（「〜とは？」を途中に置くのは可）"),
    (r"(について|のまとめ|の考察|のメモ|のお知らせ)$", "内容の予告がない定型"),
    (r"(H2|slug|JSON-LD|OGP|canonical)", "実装語がタイトルに露出（BLOG-OPS §0-7）"),
]

def main():
    fails = []
    checked = 0
    for path in sorted(glob.glob(os.path.join(BASE, "blog", "2026*.html"))):
        name = os.path.basename(path)
        if name[:8] < CUTOFF:
            continue
        checked += 1
        html = open(path, encoding="utf-8").read()
        m = re.search(r"<title>(.*?)(?:\s*\|\s*NGraph[^<]*)?</title>", html, re.S)
        if not m:
            fails.append((name, "<title>が無い"))
            continue
        title = m.group(1).strip()
        for pat, msg in NG_PATTERNS:
            if re.search(pat, title):
                fails.append((name, f"{msg}: 「{title}」"))
        if not re.search(r"[0-9０-９]", title) and "「" not in title:
            fails.append((name, f"数字も「」強調も無い＝引きが弱い定型の疑い: 「{title}」"))
    if fails:
        for name, msg in fails:
            print(f"NG {name}: {msg}")
        sys.exit(1)
    print(f"OK: タイトル検査 全通過（対象 {checked} 記事・slug {CUTOFF} 以降）")

if __name__ == "__main__":
    main()
