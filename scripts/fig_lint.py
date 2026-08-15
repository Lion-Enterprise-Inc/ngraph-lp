#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""記事に貼った図のブロックが二重に包まれていないかの検査。

なぜ入れたか（2026-08-16の実事故）:
  `fig_gen.py --svg --bare` の出力は **`.a-fig-wrap` の div と `.a-fig-title` の見出しを
  すでに含んでいる**（BLOG-OPS §3）。それを知らずにもう一度 div で包んだ結果、
  同じ見出しが2つ並んだ記事が本番へ出かけた。公開前ゲートは14本とも緑だった——
  どの検査も「図が何個あるか」しか見ておらず、**中身の入れ子は誰も見ていなかった**。

  貼る側が毎回この仕様を覚えている前提の運用は、いつか必ず破れる。機械で見る。

検査するもの:
  - `.a-fig-wrap` の入れ子（bare出力を二重に包んだ状態）
  - 1つの `.a-fig-wrap` に `.a-fig-title` が2つ以上
  - `.a-fig-wrap` の中に svg が無い（見出しだけ残って図が消えている）

使い方:
    python scripts/fig_lint.py    # gate.py が自動実行する
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_files  # noqa: E402
import published_set  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPEN = re.compile(r'<div class="a-fig-wrap"')
CLOSE = re.compile(r"</div>")
TITLE = re.compile(r'class="a-fig-title"')


def blocks(html):
    """(開始位置, 終了位置) を返す。div の入れ子を数えながら閉じ位置を決める。"""
    out = []
    for m in OPEN.finditer(html):
        depth, i = 0, m.start()
        for tag in re.finditer(r"<div\b|</div>", html[m.start():]):
            depth += 1 if tag.group(0) != "</div>" else -1
            if depth == 0:
                i = m.start() + tag.end()
                break
        out.append((m.start(), i))
    return out


def main():
    fails = []
    checked = 0
    slugs, unpublished = published_set.split_unpublished(blog_files.article_slugs())

    for slug in slugs:
        html = open(os.path.join(ROOT, "blog", slug + ".html"), encoding="utf-8").read()
        for start, end in blocks(html):
            checked += 1
            inner = html[start:end]
            n_wrap = len(OPEN.findall(inner))
            n_title = len(TITLE.findall(inner))
            if n_wrap > 1:
                fails.append("%s: 図のブロックが%d重に包まれている。`--svg --bare` の出力は"
                             "すでに .a-fig-wrap を含むので、そのまま貼る（包み直さない）"
                             % (slug, n_wrap))
            elif n_title > 1:
                fails.append("%s: 1つの図に見出しが%d個ある" % (slug, n_title))
            # 図の実体は svg とは限らない（画像で貼った既存記事がある）
            if "<svg" not in inner and "<img" not in inner:
                fails.append("%s: 図のブロックに図が無い（見出しだけ残っている）" % slug)

    memo = published_set.note(unpublished, indent="")
    if memo:
        print(memo)
    for f in fails:
        print("NG " + f)
    if fails:
        print("図のブロック: NG %d件 / %d個" % (len(fails), checked))
        return 1
    print("OK: 図のブロック 全通過（%d個）" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
