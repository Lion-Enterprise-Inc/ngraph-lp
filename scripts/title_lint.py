#!/usr/bin/env python3
"""ブログ記事タイトルの機械検査（push前ゲート・url_canon.py と並置）

2026-08-08新設。8/6夕記事「正本をつくったのに、AIが読まなかった——…」を
8/8に「AIは指示を一定確率で無視する——…」へ改題した事例が起点。
シャープさ自体は機械で測れないので、ここで落とすのは「弱いタイトルの定型」だけ。
言い切りの検査（タイトルだけで主張が復元できるか）は BLOG-OPS §9 のチェックリストで行う。

対象: slug が 20260808 以降の日付付き記事と、ナレッジ型の恒久slug（k-*）。
既存記事は対象外。恒久ページ（what-is-fde 等・日付なしslug）はキーワード狙いのため対象外。
対象集合の定義は blog_files.py が持つ（各検査が自前で glob すると新しいslugの型が漏れる）。
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_files  # noqa: E402
from xcount import X_TITLE_MAX, over_by, use_utf8_stdio, x_weighted_len

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF = "20260808"
# X加重100の検査を入れたのは2026-08-09。入れた時点で既存4記事が全部超過していた
# （8/8以降ずっと超過していて、貼るたびに手で直していた＝誰も検査していなかった）。
# 公開済みタイトルの改題は髙橋さんの判断なので既存記事では落とさない。ただし
# 黙って除外すると「対象外」が居座って検査が死ぬので、毎回 参考 として必ず表示する。
X_CUTOFF = "20260810"

NG_PATTERNS = [
    (r"(という話|した話|になった話|してみた話|する話)$", "「〜話」で終わる＝主張のぼかし。言い切る"),
    (r"(のか|でしょうか|だろうか|どうなる)$", "疑問で終わっている＝答えを先に言う"),
    (r"？$", "疑問符で終わっている＝答えを先に言う（「〜とは？」を途中に置くのは可）"),
    (r"(について|のまとめ|の考察|のメモ|のお知らせ)$", "内容の予告がない定型"),
    (r"(H2|slug|JSON-LD|OGP|canonical)", "実装語がタイトルに露出（BLOG-OPS §0-7）"),
]

def main():
    use_utf8_stdio()
    fails = []
    legacy = []
    checked = 0
    for path in blog_files.article_paths():
        name = os.path.basename(path)
        slug = name[:-5]
        if not blog_files.in_scope(slug, CUTOFF):
            continue
        checked += 1
        html = open(path, encoding="utf-8").read()
        m = re.search(r"<title>(.*?)(?:\s*\|\s*NGraph[^<]*)?</title>", html, re.S)
        if not m:
            fails.append((name, "<title>が無い"))
            continue
        title = m.group(1).strip()
        # 2026-08-19: k-writing-standard が「| NGraphブログ」無しで本番へ出た。
        # 対象25記事のうち欠けていたのは1本だけ＝サイトの慣行として確立している。
        # 検索結果とタブに出るのは <title> なので、ここが欠けると1本だけ名乗りが消える。
        if not re.search(r"<title>[^<]*\|\s*NGraphブログ\s*</title>", html):
            fails.append((name, f"<title>に「 | NGraphブログ」が無い: 「{title}」"))
        # og:title も同じ形で揃える（SNSカードに出る名前）
        og = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        if og and "| NGraphブログ" not in og.group(1):
            fails.append((name, f"og:titleに「 | NGraphブログ」が無い: 「{og.group(1)}」"))
        for pat, msg in NG_PATTERNS:
            if re.search(pat, title):
                fails.append((name, f"{msg}: 「{title}」"))
        if not re.search(r"[0-9０-９]", title) and "「" not in title:
            fails.append((name, f"数字も「」強調も無い＝引きが弱い定型の疑い: 「{title}」"))
        # 記事はX Articlesに貼る運用（BLOG-OPS §7）。貼る段で気付くと書き直しになるので
        # 執筆時点で100以内に収める。Xは全角2・半角1で数える＝len()とは一致しない
        if over_by(title):
            msg = (f"X加重 {x_weighted_len(title)}/{X_TITLE_MAX}文字＝超過。"
                   f"全角{(over_by(title) + 1) // 2}文字ほど削る: 「{title}」")
            (fails if blog_files.in_scope(slug, X_CUTOFF) else legacy).append((name, msg))
    for name, msg in legacy:
        print(f"参考 {name}: {msg}（公開済みのため落とさない。Xに貼るなら要短縮）")
    if fails:
        for name, msg in fails:
            print(f"NG {name}: {msg}")
        sys.exit(1)
    print(f"OK: タイトル検査 全通過（対象 {checked} 記事・slug {CUTOFF} 以降）")

if __name__ == "__main__":
    main()
