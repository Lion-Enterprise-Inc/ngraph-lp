#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""記事が朝A型・夕B型のどちらの型に乗っているかの機械検査（push前ゲート・BLOG-OPS §2/§3）。

2026-08-12新設。起点は `20260806-ai-cross-review`——3,326字・H2 6本・日付に朝夕の
ラベルが無い記事が、6日間だれにも気づかれずに一覧に混ざっていた。見つかったのは
髙橋さんがXに出そうとして「なんでこれ書き方違うんだ」と言った瞬間で、**目で見つける
しかない状態だった**。

なぜ混ざったか（git log で確認）: 2026-08-06はその日の夕枠（13:17）のあとに、会話の
流れで 17:24 / 21:23 / 22:00 と3本を追加している。**定時タスクはBLOG-OPSの型を手順として
必ず通るが、会話で「これ記事にして」と言われて書くときは型を通らない**。経路によって
型が抜ける穴があり、gate.py は URL・配線・タイトル・一次体験・鮮度は見ていたが、
型そのもの（字数・H2の本数・朝夕ラベル）は1つも見ていなかった。

対象: slug が 20260812 以降の日付付き記事のみ（既存記事は落とさない）。
恒久ページ（what-is-fde 等・日付なしslug）は型を持たないので対象外。

閾値は実測で決めた（2026-08-12・既存42本を計測）:
  朝A型  実測 2,296〜3,605字・H2は22本すべて4本ちょうど
  夕B型  実測 6,045〜13,061字・H2 8〜13本
BLOG-OPS の目安は朝2,500〜3,500字だが、**直近2本が3,60x字**でありそこで落とすと
正常な運用が毎回赤くなる。ここで落とすのは「明らかな型外れ」だけにして、目安への
寄せ方は人が判断する（検査は運用を止めるためのものではない）。

使い方:
    python scripts/format_lint.py
"""
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF = "20260812"

# (型, 字数の下限, 字数の上限, H2の下限, H2の上限)
RULES = {
    "朝": (2300, 4000, 4, 4),
    "夕": (6000, None, 7, None),
}
TARGET = {"朝": "2,500〜3,500字・H2 4本（BLOG-OPS §2）",
          "夕": "6,000〜8,000字・H2 7〜9本（BLOG-OPS §3）"}


def measure(html):
    """記事の本文字数とH2の本数、日付ラベルを返す。

    字数は図（SVG）の中の文字を除いて数える。図のラベルは本文ではないので、
    図を増やすほど字数が伸びる数え方にすると、材料でなく飾りで基準を満たせてしまう。
    """
    m = re.search(r"<article.*?</article>", html, re.S)
    if not m:
        return None, None, None
    article = m.group(0)
    prose = re.sub(r"<svg.*?</svg>", "", article, flags=re.S)
    text = re.sub(r"\s", "", re.sub(r"<[^>]+>", "", prose))
    h2 = len(re.findall(r"<h2", article))
    lab = re.search(r"(20\d\d)\.(\d\d)\.(\d\d)\s*(朝|夕)", article)
    return len(text), h2, lab


def main():
    fails = []
    legacy = []
    checked = 0

    for path in sorted(glob.glob(os.path.join(BASE, "blog", "2026*.html"))):
        name = os.path.basename(path)
        slug = name[:-5]
        html = open(path, encoding="utf-8").read()
        chars, h2, lab = measure(html)
        if chars is None:
            continue

        # 対象外の既存記事でも、ラベルが無いものは毎回「参考」で出す。
        # 黙って除外すると、混ざったまま誰も見ない状態が続く（それが今回の事故そのもの）
        if name[:8] < CUTOFF:
            if not lab:
                legacy.append("%s: 朝/夕のラベルが無い（%d字・H2 %d本）。定時の型を通っていない記事"
                              % (slug, chars, h2))
            continue

        checked += 1
        if not lab:
            fails.append("%s: 日付に朝/夕のラベルが無い＝どちらの型で書いたのかが分からない。"
                         "記事冒頭の日付を「2026.08.12 夕」の形にする（%d字・H2 %d本）"
                         % (slug, chars, h2))
            continue

        kind = lab.group(4)
        if "".join(lab.group(1, 2, 3)) != slug[:8]:
            fails.append("%s: 日付ラベル %s.%s.%s が slug の日付と違う"
                         % (slug, lab.group(1), lab.group(2), lab.group(3)))

        lo, hi, h2lo, h2hi = RULES[kind]
        if chars < lo:
            fails.append("%s（%s型）: %d字は薄い（下限%d字）。目安は%s"
                         % (slug, kind, chars, lo, TARGET[kind]))
        if hi and chars > hi:
            fails.append("%s（%s型）: %d字は長すぎる（上限%d字・速報性が死ぬ）。目安は%s"
                         % (slug, kind, chars, hi, TARGET[kind]))
        if h2 < h2lo:
            fails.append("%s（%s型）: H2が%d本。%d本以上必要。目安は%s"
                         % (slug, kind, h2, h2lo, TARGET[kind]))
        if h2hi and h2 > h2hi:
            fails.append("%s（%s型）: H2が%d本。%s型は%d本ちょうど（BLOG-OPS §2）"
                         % (slug, kind, h2, kind, h2hi))

    for line in legacy:
        print("参考 " + line + "（公開済みのため落とさない）")
    for line in fails:
        print("NG " + line)

    if fails:
        print("型の検査: NG %d件（対象 %d記事・slug %s 以降）" % (len(fails), checked, CUTOFF))
        return 1
    print("OK: 型の検査 全通過（対象 %d記事・slug %s 以降）" % (checked, CUTOFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
