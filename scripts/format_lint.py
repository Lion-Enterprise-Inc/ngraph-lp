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

2026-08-14追加・ガイド型（G型）と「同じ枠が2本」の検査:
  `20260813-torihikisaki-check`（自社ツールの使い方・4,531字・H2 8本）が「夕」を
  名乗って夕Bの下限6,000字で落ちた。だが8/13は既に朝(3,570字)・夕(9,005字)が
  揃っており、**これは3本目＝定時枠の記事ではない**。ラベルの方が間違っている。
  6,000字に伸ばす手段は言い換え段落の追加しかなく、それは BLOG-OPS §3 の
  水増し禁止条項そのものなので、字数を下げるのでも slug を除外するのでもなく
  **型を1つ増やす**（BLOG-OPS §3.5）。slug の除外リストは「型を持たない記事」を
  作り続ける許可になり、この検査が塞いだ穴を制度化するので採らない。

  同時に、本当の穴だった「同じ日に同じ枠が2本ある」を検査する。字数がたまたま
  下限を超えていれば、型違いの記事が「夕」を名乗って一覧に混ざるのを字数だけでは
  止められない（今回それが起きた）。ガイド型が枠を消費していないかも見る。

使い方:
    python scripts/format_lint.py
"""
import collections
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF = "20260812"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import published_set  # noqa: E402

# (型, 字数の下限, 字数の上限, H2の下限, H2の上限)
RULES = {
    "朝": (2300, 4000, 4, 4),
    "夕": (6000, None, 7, None),
    "ガイド": (3000, 6000, 5, 10),
}
TARGET = {"朝": "2,500〜3,500字・H2 4本（BLOG-OPS §2）",
          "夕": "6,000〜8,000字・H2 7〜9本（BLOG-OPS §3）",
          "ガイド": "3,000〜6,000字・H2 5〜10本（BLOG-OPS §3.5）"}
# 上限を超えたときに何が壊れるかは型ごとに違う。使い回すと理由が嘘になる
OVER = {"朝": "速報性が死ぬ",
        "ガイド": "使い方の材料が尽きて水増しになる。深掘りなら夕B型で書く"}
# 定時の枠。1日1本ずつしか無い。ガイド型は枠を消費しない3本目
SLOTS = ("朝", "夕")
LABEL_RE = r"(20\d\d)\.(\d\d)\.(\d\d)\s*(朝|夕|ガイド)"


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
    lab = re.search(LABEL_RE, article)
    return len(text), h2, lab


def main():
    fails = []
    legacy = []
    notes = []
    by_day = collections.defaultdict(list)  # 日付 -> [(型, slug), ...]
    checked = 0

    found = sorted(os.path.basename(p)[:-5]
                   for p in glob.glob(os.path.join(BASE, "blog", "2026*.html")))
    live, unpublished = published_set.split_unpublished(found)

    for slug in live:
        path = os.path.join(BASE, "blog", slug + ".html")
        name = slug + ".html"
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
        by_day[slug[:8]].append((kind, slug))
        if "".join(lab.group(1, 2, 3)) != slug[:8]:
            fails.append("%s: 日付ラベル %s.%s.%s が slug の日付と違う"
                         % (slug, lab.group(1), lab.group(2), lab.group(3)))

        lo, hi, h2lo, h2hi = RULES[kind]
        if chars < lo:
            fails.append("%s（%s型）: %d字は薄い（下限%d字）。目安は%s"
                         % (slug, kind, chars, lo, TARGET[kind]))
        if hi and chars > hi:
            fails.append("%s（%s型）: %d字は長すぎる（上限%d字・%s）。目安は%s"
                         % (slug, kind, chars, hi, OVER.get(kind, "型から外れる"),
                            TARGET[kind]))
        if h2 < h2lo:
            fails.append("%s（%s型）: H2が%d本。%d本以上必要。目安は%s"
                         % (slug, kind, h2, h2lo, TARGET[kind]))
        if h2hi and h2 > h2hi:
            limit = ("%d本ちょうど" % h2hi) if h2lo == h2hi else ("%d本まで" % h2hi)
            fails.append("%s（%s型）: H2が%d本。%s型は%s。目安は%s"
                         % (slug, kind, h2, kind, limit, TARGET[kind]))

    # 枠の重複（2026-08-14新設）。字数だけでは型違いの記事が「夕」を名乗って
    # 混ざるのを止められない。定時の枠は1日1本ずつなので、2本目は必ず別の型
    for day in sorted(by_day):
        kinds = [k for k, _ in by_day[day]]
        for slot in SLOTS:
            dup = [s for k, s in by_day[day] if k == slot]
            if len(dup) > 1:
                fails.append("%s: 「%s」のラベルが%d本ある（%s）。定時の枠は1日1本ずつ。"
                             "枠の記事でないものは §3.5 のガイド型にする"
                             % (day, slot, len(dup), "／".join(sorted(dup))))
        # ガイド型は枠を消費しない3本目。落とさないのは、朝を書いた時点では
        # その日の夕がまだ無いのが正常だから（常に赤いゲートは押し通す運用を育てる）
        if "ガイド" in kinds:
            missing = [s for s in SLOTS if s not in kinds]
            if missing:
                notes.append("%s: ガイド型があるがその日の%sが無い。ガイド型は朝A/夕Bの枠を"
                             "消費しない3本目（BLOG-OPS §3.5）。枠の記事を落としていないか確認"
                             % (day, "・".join(missing)))

    memo = published_set.note(unpublished, indent="")
    if memo:
        print(memo)

    for line in notes:
        print("参考 " + line)
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
