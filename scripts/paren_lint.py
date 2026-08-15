#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""かっこ書きの多用を止める（push前ゲート・BLOG-OPS §0-9）。

なぜ入れたか〔髙橋さん 2026-08-14「なにか単語をだしたあと解説や注釈でかっこ書きがおおい」
「これすごく読みにくいからできるだけ読みやすくして」〕:

  §0-5 が「専門用語には毎回1行の説明」を求めているので、書き手は用語のうしろに
  かっこで注釈を足しにいく。1つなら親切だが、続けると本筋の文が途切れ続けて読めなくなる。
  2026-08-14 の朝記事は本文3,284字にかっこ24箇所（7.3回/1000字）で、
  1文の中で「透かし（imperceptible watermark）」「規格「C2PA（Coalition for ...）」」
  のように二重に入っていた。

  実測（2026-08-14・59記事）: 中央値 5.31 回/1000字・平均 4.81・最大 10.21。
  つまり癖はサイト全体のもので、1記事を直しても再発する。

  直し方は削ることではなく**地の文に開くこと**。
    × 適用範囲はClaude Platform（API）・…に及びます
    ○ API経由の利用、Claudeのアプリ、…まで、Anthropicは「あらゆる場所」と書いています
    × …と書いています（完了時期は明記されていません）
    ○ …と書かれていて、完了時期は示されていません
  リンクも「（一次情報）」で外に出さず、見出し語そのものに載せる。

対象外にするもの:
  - 記事末の「参考（一次情報）」枠（.a-src）。出典表記の（公開日）は正しい用法
  - 図（SVG）の中の文字、code / pre

使い方:
    python scripts/paren_lint.py            # gate.py から自動実行される
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blog_files  # noqa: E402
import published_set  # noqa: E402

CUTOFF = "20260815"        # これ以降のslugは落とす。既存記事は「参考」で出すだけ
MAX_PER_1000 = 3.0         # 本文1000字あたりのかっこの数（実測中央値5.31の6割）
MAX_PER_BLOCK = 2          # 同じ段落・箇条書き1項目の中に入れてよい数

PAREN = re.compile(r"（[^（）]*）|\([^()]*\)")
BLOCK = re.compile(r"<(p|li)\b[^>]*>(.*?)</\1>", re.S)


def body_of(html):
    """本文（参考枠・図・コードを除いたところ）のHTMLを返す。"""
    m = re.search(r"<article.*?</article>", html, re.S)
    if not m:
        return None
    art = m.group(0)
    art = re.sub(r'<div class="a-src".*?</div>', "", art, flags=re.S)
    art = re.sub(r"<svg.*?</svg>", "", art, flags=re.S)
    art = re.sub(r"<(code|pre)\b.*?</\1>", "", art, flags=re.S)
    return art


def measure(html):
    art = body_of(html)
    if art is None:
        return None
    text = re.sub(r"<[^>]+>", "", art)
    chars = len(re.sub(r"\s", "", text))
    if chars < 500:
        return None
    hits = PAREN.findall(text)
    crowded = []
    for m in BLOCK.finditer(art):
        inner = re.sub(r"<[^>]+>", "", m.group(2))
        n = len(PAREN.findall(inner))
        if n > MAX_PER_BLOCK:
            crowded.append((n, " ".join(inner.split())[:38]))
    return chars, hits, crowded


def main():
    found = blog_files.article_slugs()
    live, unpublished = published_set.split_unpublished(found)

    fails, legacy, checked = [], [], 0
    for slug in live:
        html = open(os.path.join(BASE, "blog", slug + ".html"), encoding="utf-8").read()
        got = measure(html)
        if not got:
            continue
        chars, hits, crowded = got
        per1000 = len(hits) / chars * 1000

        # 日付で始まらないslug（what-is-fde・ai-cost 等の恒久記事）は日付比較が
        # 成立しない。文字列比較だと 'a' > '2' で新記事扱いになり、定時運用と
        # 無関係な恒久記事でゲートが落ちる（2026-08-16に readability_lint を
        # 作る過程で同じ穴を踏んで発見。こちらは閾値未満で表面化していなかった）。
        # 判定は blog_files に寄せた（ナレッジ型 k- は日付を持たないが常に対象）
        if not blog_files.in_scope(slug, CUTOFF):
            if per1000 > MAX_PER_1000:
                legacy.append("%s: かっこ %d箇所・%.1f回/1000字" % (slug, len(hits), per1000))
            continue

        checked += 1
        if per1000 > MAX_PER_1000:
            fails.append(
                "%s: かっこが %d箇所・%.1f回/1000字（上限 %.1f）。"
                "注釈をかっこに押し込まず地の文に開く。リンクは「（一次情報）」ではなく見出し語に載せる"
                % (slug, len(hits), per1000, MAX_PER_1000))
        for n, head in crowded:
            fails.append("%s: 1つの段落にかっこが %d個（上限 %d）: 「%s…」"
                         % (slug, n, MAX_PER_BLOCK, head))

    memo = published_set.note(unpublished, indent="")
    if memo:
        print(memo)

    if legacy:
        legacy.sort(key=lambda s: -float(re.search(r"・([\d.]+)回", s).group(1)))
        print("参考 上限を超えている既存記事 %d本（公開済みのため落とさない・多い順に3本）:" % len(legacy))
        for line in legacy[:3]:
            print("  " + line)

    if fails:
        print("かっこ書きが多すぎます:")
        for f in fails:
            print("  " + f)
        print("%d件（対象 %d記事・slug %s 以降で落とす）" % (len(fails), checked, CUTOFF))
        return 1

    print("OK: かっこ書きの密度 全通過（対象 %d記事・slug %s 以降で落とす）" % (checked, CUTOFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
