#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI生成の痕跡（telltale signs）の検査。

きっかけ: Peter Steinberger（OpenClaw作者）が a16z speedrun のインタビューで
「em dashやAI speakの痕跡を見た瞬間、読み手は無意識にその文章の価値を切り下げる」
と述べた。本人のN=1なので主張自体は根拠にしない。**うちの記事を実測したら
2倍ダーシ「——」だけが54/54記事にあり、中央値1.38回/1000字だった**ので、
外れ値と反復だけを機械で見張る。

見るもの:
  1. ダーシの密度（1000字あたり）— 単発は日本語として正当。外れ値だけ落とす
  2. ダーシを含む文の連続 — 痕跡は文字ではなく「同じ修辞の反復」
  3. 日本語のAI文体マーカー — 現状ほぼ0件なので、増えたら落とす回帰ガード

使い方:
    python scripts/ai_tell_lint.py                    # 全記事の分布レポート（exit 0）
    python scripts/ai_tell_lint.py blog/<記事>.html   # その記事を検査（NGならexit 1）
"""
import glob
import os
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 2026-08-12実測（54記事）: 密度 中央値1.38 / 最大3.09。外れ値だけを落とす
MAX_DASH_PER_1000 = 2.0
# 「短い断定——その解説」が並ぶと、内容ではなく型が見える。
# 実測（54記事）: 連鎖0が9本・1が25本・2が11本・3が6本・4が1本・5が2本
MAX_DASH_RUN = 4

# 現状ほぼ0件（ではないでしょうか0 / 本記事では0 / いかがでしたか0 / まさに2）。
# BLOG-OPS §0が効いている状態を固定するための回帰ガード
AI_SPEAK = [
    (r"ではないでしょうか", "問いかけで締める定型"),
    (r"本記事では", "自己言及の前置き"),
    (r"いかがでした", "締めの定型"),
    (r"注目が集ま", "主語のない盛り"),
    (r"求められて(いま|い)", "主語のない受動"),
    (r"まさに", "強調の埋め草"),
    (r"と言えるでしょう", "断定回避の埋め草"),
]


def _strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html)).strip()


def text_of(path):
    s = open(path, encoding="utf-8").read()
    return _strip(re.sub(r"(?s)<(script|style|head).*?</\1>", "", s))


def blocks_of(path):
    """li / p / h2 / h3 / td の中身。連鎖は文ではなくブロック単位で見る
    （箇条書きの各項目が全部『断定——解説』で揃う形が実際の痕跡だった）。"""
    s = re.sub(r"(?s)<(script|style|head).*?</\1>", "",
               open(path, encoding="utf-8").read())
    out = []
    for m in re.finditer(r"(?s)<(li|p|h2|h3|td)\b[^>]*>(.*?)</\1>", s):
        t = _strip(m.group(2))
        if t:
            out.append(t)
    return out


def measure(path):
    b = text_of(path)
    n = len(re.findall(r"——", b))
    density = n / max(len(b), 1) * 1000
    run = cur = 0
    for t in blocks_of(path):
        if "——" in t:
            cur += 1
            run = max(run, cur)
        else:
            cur = 0
    speak = [(pat, why, len(re.findall(pat, b))) for pat, why in AI_SPEAK]
    return {"n": n, "len": len(b), "density": density, "run": run,
            "speak": [(p, w, c) for p, w, c in speak if c]}


def check(path):
    m = measure(path)
    ng = []
    if m["density"] > MAX_DASH_PER_1000:
        ng.append("ダーシ「——」が %d回/%d字（%.2f回/1000字・上限%.1f）。"
                  "単発は問題ないが、この密度は文字ではなく型が見える"
                  % (m["n"], m["len"], m["density"], MAX_DASH_PER_1000))
    if m["run"] >= MAX_DASH_RUN:
        ng.append("ダーシを含む文が%d連続（上限%d）。同じ修辞の反復が痕跡になる"
                  % (m["run"], MAX_DASH_RUN))
    for pat, why, c in m["speak"]:
        ng.append("AI文体マーカー『%s』が%d件（%s）。現状の記事はほぼ0件で揃っている"
                  % (pat, c, why))

    name = os.path.basename(path)
    if ng:
        print("NG: %s" % name)
        for x in ng:
            print("  - %s" % x)
        return 1
    print("OK: %s（——%d回・%.2f回/1000字・最大連鎖%d）"
          % (name, m["n"], m["density"], m["run"]))
    return 0


def report():
    files = [f for f in sorted(glob.glob(os.path.join(ROOT, "blog", "*.html")))
             if "index" not in os.path.basename(f)]
    rows = [(measure(f), os.path.basename(f)) for f in files]
    ds = [m["density"] for m, _ in rows]
    print("記事%d本 / ダーシ密度 中央値%.2f 最大%.2f（上限%.1f）"
          % (len(rows), statistics.median(ds), max(ds), MAX_DASH_PER_1000))
    over = [(m, f) for m, f in rows
            if m["density"] > MAX_DASH_PER_1000 or m["run"] >= MAX_DASH_RUN or m["speak"]]
    print("上限超え: %d本（既存記事なので落とさない。新記事だけ検査する）" % len(over))
    for m, f in sorted(over, key=lambda x: -x[0]["density"])[:10]:
        print("  %.2f回/1000字  連鎖%d  %s" % (m["density"], m["run"], f))
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(check(sys.argv[1]))
    sys.exit(report())
