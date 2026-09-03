#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""対外ページの禁止語を機械で止める（2026-09-03）。

背景: 9/2 の決定「比喩（司書・扉・窓口・検問）は使わない。部品は 記録・検査・自動整理・
AI接続口・LINEボット」と 9/3 の決定「『動いている』と書かない。受入テストを通るまで
『正本』『安全機構』と対外に言わない」に対し、トップに『正本』7回・/fde/ に18回が残っていた。
言葉の決定はサイト側に自動では届かないので、公開前ゲートで名指しして止める。

対象: ルート直下・fde/・en/ の HTML（ブログは記事の性質上、語の説明で使うので対象外）。
検査するのは表示テキストのみ（script/style/コメント/JSON-LD は除く）。

使い方:
    python scripts/vocab_check.py            # 違反を列挙して exit 1
    python scripts/vocab_check.py --list     # 対象ファイルを表示
"""
import html
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 語 → 置き換えの目安（メッセージに出す）
BANNED = {
    "正本": "会社の記録／一つの記録",
    "検問": "検査",
    "司書": "自動整理",
    "読み口": "AI接続口",
    "窓口": "AI接続口（比喩は使わない）",
    "稼働中": "本番運用中 など、部品の状態は5段階で書く",
    "安全機構": "検査（受入テストを通るまで使わない）",
}
# 「扉」は「扉絵」等の一般語と衝突するため、比喩用法だけを拾う
BANNED_RE = {
    # 「動いている」は状態の過大表現として禁止。ただし状態整理の軸「決まっていること／動いていること」は製品の定義語なので除く
    r"動いている(?!こと)": "実装済み／配布済み／本番接続済み／実測済み／未実測 のどれか",
    r"AI(への|の)扉|同じ扉|一つの扉": "AI接続口（比喩は使わない）",
}

TARGETS = ["index.html", "company.html", "recruit.html", "entry.html", "page.html",
           "fde/index.html", "en/index.html", "en/fde/index.html"]


def visible_text(src: str) -> str:
    src = re.sub(r"<!--[\s\S]*?-->", " ", src)
    src = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", src, flags=re.I)
    src = re.sub(r"<[^>]+>", " ", src)
    return html.unescape(src)


def check(path: pathlib.Path):
    text = visible_text(path.read_text(encoding="utf-8"))
    hits = []
    for w, alt in BANNED.items():
        n = len(re.findall(re.escape(w), text))
        if n:
            hits.append((w, n, alt))
    for pat, alt in BANNED_RE.items():
        n = len(re.findall(pat, text))
        if n:
            hits.append((pat, n, alt))
    return hits


def main():
    if "--list" in sys.argv:
        for t in TARGETS:
            print(t, "(missing)" if not (ROOT / t).exists() else "")
        return 0
    bad = 0
    for t in TARGETS:
        p = ROOT / t
        if not p.exists():
            continue
        hits = check(p)
        for w, n, alt in hits:
            bad += 1
            print("NG %s: 「%s」×%d → %s" % (t, w, n, alt))
    if bad:
        print("\n対外ページに社内語・比喩・状態の過大表現が %d 件。決定は ngraph-brain company/CURRENT-DECISIONS.md の 2026-09-02 / 09-03 行。" % bad)
        return 1
    print("OK: 対外ページの禁止語なし（%d ファイル）" % len([t for t in TARGETS if (ROOT / t).exists()]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
