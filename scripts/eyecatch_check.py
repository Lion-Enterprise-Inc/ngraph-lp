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

パターン分岐（2026-08-16・k-blog-gate 初回実測）: `eyecatch_k.py`（KNOWLEDGE-OPS §2・
k-b-diagram パターン）は、図案そのものが右半分に墨色の見出し語（中心語・4つの箱ラベル）
を持つデザインで、上の判定域（x736-1140）を丸ごとスキャンすると図案自身の文字を
「本文の侵入」として誤検知する。k-blog-gate.jpg で実測: 墨88px でNG。

誤検知だからといって判定そのものをやめるのではなく、パターンごとに見る範囲を変える。
`eyecatch_k.py` は見出し・サブ見出しを x=72 起点・幅510で組むため（build() 内の
one()/wrap() が数値で保証）、右端は最大でも x=582 に収まる。図案の箱の左端は x=682。
このあいだの x582-682（幅100px）は、正しく生成できていれば地色のままのはずの
緩衝帯で、ここに墨が出たら「見出しが図案側へはみ出した」という本物の重なりになる。
`assets/blog/_eyecatch.json` の記録（生成時にeyecatch_k.pyが書く）でパターンを
判定し、k-b-diagram系だけこの緩衝帯を見る。記録が無い・旧パターンの画像は
従来どおり x736-1140 の全域を見る（既存の47枚の検査を弱めない）。

使い方:
    python scripts/eyecatch_check.py                 # assets/blog/*.jpg を全数検査
    python scripts/eyecatch_check.py <path.jpg> ...  # 指定ファイルだけ
"""
import glob
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(ROOT, "assets", "blog", "_eyecatch.json")

CANVAS = (1200, 630)
# 図案の占有域（テキストが入ってきてはいけない範囲）——旧パターン（eyecatch_gen.py）用
X0, X1 = 736, 1140
Y0, Y1 = 90, 520
# k-b-diagram（eyecatch_k.py）用の緩衝帯——見出し右端(x582)と図案の箱の左端(x682)の間
KX0, KX1 = 582, 682
KY0, KY1 = 90, 520
INK_MAX = 80       # これ未満を「墨のテキスト」とみなす
LIMIT = 50         # この画素数を超えたら重なりとする（JPEGノイズの数画素は許容）


def pattern_of(path):
    """記録された生成パターンを返す（無ければ None＝旧パターン扱い）。"""
    if not os.path.exists(RECORD):
        return None
    try:
        d = json.loads(open(RECORD, encoding="utf-8").read())
    except (OSError, ValueError):
        return None
    slug = os.path.splitext(os.path.basename(path))[0]
    return d.get(slug, {}).get("pattern")


def scan(path):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.size != CANVAS:
        return None, "サイズが %s（想定 %s）" % (im.size, CANVAS)
    px = im.load()
    pat = pattern_of(path)
    # visual-gen（2026-08-17・画像生成表紙の試験運用）: 全面イラストで「テキスト枠と図案の重なり」
    # という前提自体が無い。検査対象外にする（対象外は呼び出し側の出力で見えるようにする）
    if pat == "visual-gen":
        return 0, None
    x0, x1, y0, y1 = (KX0, KX1, KY0, KY1) if pat == "k-b-diagram" else (X0, X1, Y0, Y1)
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y]
            if max(r, g, b) < INK_MAX:
                n += 1
    return n, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = args or sorted(glob.glob(os.path.join(ROOT, "assets", "blog", "*.jpg")))
    if not args:
        # gitに無いjpgは本番に存在しない＝ゲート対象外（published_set.py・2026-08-16）。
        # 書きかけ記事の表紙1枚でゲートが恒常NGになる穴が、この検査にだけ残っていた。
        # パスを明示して呼んだときは従来どおり見る（作業中の表紙を単体検査する用途）
        import published_set
        slugs = [os.path.splitext(os.path.basename(p))[0] for p in files]
        kept, skipped = published_set.split_unpublished(slugs)
        keep = set(kept)
        files = [p for p in files
                 if os.path.splitext(os.path.basename(p))[0] in keep]
        memo = published_set.note(skipped, indent="")
        if memo:
            print(memo)
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
