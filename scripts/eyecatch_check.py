#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""アイキャッチの「本文が図案に重なる」検査（BLOG-OPS §6・gate.py から自動実行）。

なぜ入れたか（2026-08-08）: `eyecatch_gen.py` のテキスト枠は
left:112 + padding30 + width730 = 右端872px、図案は right:64 + 400px = 左端736px。
**枠が最初から136px重なっていた。** タイトルが短い回はテキストが図案まで届かないので
表に出ず、長い回だけ本文が図案を突き抜ける。47枚中12枚で発生していた
（what-is-fde・20260802-seisei-ai-gijiroku-domari など）。

検査の理屈: 図案の線は opacity .5 で地色と混ざり RGB ≒ 153 になる。
タイトルの墨は #2b2620（≒ 43）。**図案域に「最大値80未満の画素」があれば本文が入り込んでいる**。
サブテキストのグレー #5c544a（≒92）は拾わない。朱 #a63a24 は R=166 なので拾わない。
目視でなく画素で判定できる。

締め直し（2026-08-09・クロスレビューで発覚）: 旧設定（x742起点・1画素飛ばし・閾値400）は
走査が粗く、実際に本文が重なっていた `20260806-seihon-yomarenai.jpg`（重なり376px）を
閾値400未満として見逃していた。図案の左端x736から全画素を走査し、閾値を50に締める。

使い方:
    python scripts/eyecatch_check.py                 # assets/blog/*.jpg を全数検査
    python scripts/eyecatch_check.py <path.jpg> ...  # 指定ファイルだけ
"""
import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANVAS = (1200, 630)
# 図案の占有域（テキストが入ってきてはいけない範囲）
X0, X1 = 736, 1140
Y0, Y1 = 90, 520
INK_MAX = 80       # これ未満を「墨のテキスト」とみなす
LIMIT = 50         # この画素数を超えたら重なりとする（JPEGノイズの数画素は許容）


def scan(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.size != CANVAS:
        return None, "サイズが %s（想定 %s）" % (im.size, CANVAS)
    px = im.load()
    n = 0
    for y in range(Y0, Y1):
        for x in range(X0, X1):
            r, g, b = px[x, y]
            if max(r, g, b) < INK_MAX:
                n += 1
    return n, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = args or sorted(glob.glob(os.path.join(ROOT, "assets", "blog", "*.jpg")))
    if not files:
        print("検査対象なし")
        return 0
    bad = []
    for p in files:
        n, err = scan(p)
        if err:
            bad.append((os.path.basename(p), err))
            continue
        if n > LIMIT:
            bad.append((os.path.basename(p), "本文が図案に重なっている（墨 %d px）" % n))
    if bad:
        print("NG: アイキャッチ %d 枚で本文が図案に重なっている" % len(bad))
        for name, why in bad:
            print("  - %s: %s" % (name, why))
        print("  直し方: python scripts/eyecatch_gen.py <slug> \"<短いタイトル>\" \"<サブ>\" <pattern> で作り直す")
        print("         （生成側は文字数に応じて自動で級数を落とすので、作り直せば解消する）")
        return 1
    print("OK: アイキャッチ %d 枚、本文と図案の重なりなし" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
