#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""営業資料のスライドから、用途別に図の画像を作る。

なぜ要るか〔髙橋さん 2026-08-16「X用の記事の画像は別で生成して」〕:
  記事本文に貼った画像をそのままXへ回していた。ブログ用は本文カラム幅に合わせて
  縮めた上でJPEGにしたもので、Xへ回すと**二重圧縮**になる。さらにスライドの下端には
  資料のページ番号（07/15）と連絡先が入っていて、資料の中では正しいが、
  1枚で流れるXでは意味の無い帯として残る。用途が違えば作り直す。

やること:
  - 元PNG（1920x1080）から、台紙の外側の余白と下端のフッター帯を落とす
  - 用途ごとの幅で書き出す（web=1600 / x=1920）

出所の対応表は `assets/blog/_fig_sources.json`。ブログの画像名 → 元スライドのパス。
元が見つからないときは黙って諦めず、呼び出し側が既存の画像で代替したと分かるようにする。

使い方:
    python scripts/deck_fig.py --list
    python scripts/deck_fig.py brain-deck-abc --use x --out C:/tmp/fig.jpg
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES = os.path.join(REPO, "assets", "blog", "_fig_sources.json")
WIDTH = {"web": 1600, "x": 1920}
QUALITY = {"web": 92, "x": 92}


def load_sources():
    try:
        return json.load(open(SOURCES, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def source_of(name):
    """ブログ画像名（拡張子あり/なし）に対応する元スライドのパス。無ければ None。"""
    src = load_sources()
    key = name if name in src else name + ".jpg"
    entry = src.get(key)
    if not entry:
        return None
    path = entry["src"] if isinstance(entry, dict) else entry
    return path if os.path.exists(path) else None


def crop_box(im, gap=24, footer_max=90):
    """台紙の外周余白と、下端のフッター帯を除いた切り出し範囲を返す。

    フッターは「本文の下に、地色の空白を挟んで離れて置かれた最後の行」。
    行の位置を決め打ちにすると、スライドの版が変わった日に黙ってズレるので、
    地色との差から毎回測る。
    """
    px = im.load()
    w, h = im.size
    bg = px[2, 2]

    def differs(c):
        return sum(abs(a - b) for a, b in zip(c, bg)) > 24

    rows = [y for y in range(h) if any(differs(px[x, y]) for x in range(0, w, 4))]
    cols = [x for x in range(w) if any(differs(px[x, y]) for y in range(0, h, 4))]
    if not rows or not cols:
        return (0, 0, w, h)
    top, bottom = rows[0], rows[-1]
    left, right = cols[0], cols[-1]

    # 下から順に、空白で切れている最後のかたまりを探す。細くて離れていればフッター
    band_end = bottom
    band_start = bottom
    for y in range(bottom, top, -1):
        if y in rows:
            band_start = y
        elif band_start - y > gap:
            break
    if (band_end - band_start) <= footer_max and (band_start - gap) > top:
        # フッターと本文のあいだの空白の中間で切る（切り口が詰まって見えないように）
        prev = max([y for y in rows if y < band_start - gap] or [top])
        bottom = (prev + band_start) // 2
    pad = 18
    return (max(0, left - pad), max(0, top - pad),
            min(w, right + pad + 1), min(h, bottom + pad))


def render(name, use, out):
    from PIL import Image
    src = source_of(name)
    if src is None:
        return None
    im = Image.open(src).convert("RGB")
    im = im.crop(crop_box(im))
    target = WIDTH[use]
    if im.width != target:
        im = im.resize((target, round(im.height * target / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    im.save(out, "JPEG", quality=QUALITY[use], optimize=True, progressive=True)
    return im.size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?", help="ブログ画像名（例 brain-deck-abc）")
    ap.add_argument("--use", choices=sorted(WIDTH), default="x")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true", help="対応表を表示する")
    a = ap.parse_args()

    if a.list or not a.name:
        src = load_sources()
        if not src:
            print("対応表がありません: %s" % SOURCES)
            return 1
        for k, v in sorted(src.items()):
            if k.startswith("_"):
                continue
            p = v["src"] if isinstance(v, dict) else v
            print("%-28s %s %s" % (k, "OK  " if os.path.exists(p) else "見つからない", p))
        return 0

    if not a.out:
        return ap.error("--out が必要です")
    size = render(a.name, a.use, a.out)
    if size is None:
        print("元スライドが見つかりません: %s（対応表 %s）" % (a.name, SOURCES))
        return 1
    print("OK %s %dx%d %dKB" % (a.out, size[0], size[1], os.path.getsize(a.out) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
