# -*- coding: utf-8 -*-
"""記事の図解をグラフの型から作る（和禅テンプレ・1200x630）

データの形 → 型:
  順位・多項目の比較（1時点）      = bar
  2つの数字の対比                  = gap
  2時点の変化（複数項目）          = slope
  3時点以上の推移                  = line
  内訳（合計100%）                 = stack
  割合を1つだけ主役に              = ratio
  2軸の分類                        = matrix
  増減の内訳（始点→終点）          = waterfall
  多数の値＋基準線                 = dot

使い方:
  python scripts/fig_gen.py <type> --title "見出し" --data "ラベル=値,ラベル=値" [options]

型（--type）:
  bar        横棒ランキング。上位を朱で強調（--hot 3 で上位3本）
  gap        2値の対比。差がいくつかを真ん中に出す
  slope      2時点の変化。--data "項目=前値>後値" ／ --cols "前|後" ／ 前値なしは —
  line       折れ線。--mark "2:20万件で-13.6pt" で点に吹き出し
  stack      100%積み上げ1本。内訳の比率
  ratio      割合を1つだけ大きく。ドーナツ＋巨大数字
  matrix     2軸4象限。--axis "横軸ラベル|縦軸ラベル"
  waterfall  増減の内訳。--data "始点=100,増減=-58,増減=+12,終点=54"（途中は+/-必須）
             縦軸は0起点のまま。増減が始点に比べて小さいと帯が細くなる＝そういうデータ
  dot        多数の値を横軸1本に並べる。--ref "1176:全国平均" で朱の基準線

共通オプション:
  --title  見出し（結論を書く。「◯◯の割合」ではなく「◯◯は9つのうち6番目だけ」）
  --sub    小見出し1行（省略可）
  --concl  図の下の結論1行（省略可・これがあると図単体で意味が通る）
  --src    出所（「厚生労働省「令和7年度 能力開発基本調査」（2026年7月31日公表）」）
  --hot    朱で強調する本数（bar/stack。既定1）
  --unit   値の単位（既定 "%"）
  --out    出力パス。.png / .jpg / .svg で切り替わる
  --svg    記事に貼る <div class="a-fig-wrap"> ブロックを標準出力に出す
  --w --h  キャンバス（既定 1200x630）

出力:
  .png/.jpg = アイキャッチ・X添付用（Edgeヘッドレスで書き出し）
  .svg / --svg = 記事本文に貼るインラインSVG（SP幅では横スクロールする）

生成後は必ず画像を目視すること（単語中改行・見切れ・棒のはみ出し）。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")   # 書式エラーの日本語がcp932で化けるため

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

# 和禅パレット（ngraph-zen.css と揃える）
BG = "#f6f2e9"
INK = "#2b2620"
ACCENT = "#a63a24"
SUB = "#5c544a"
FAINT = "#8a8172"
DIM = "#cfc5b4"
DIM2 = "#ddd5c6"
LINE = "rgba(166,58,36,.24)"

SERIF = "'Zen Old Mincho',serif"
SANS = "'Zen Kaku Gothic New',sans-serif"


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_data(s):
    """"ラベル=値,ラベル=値" を [(ラベル, float, 元の表記)] にする。

    表記は書いたまま出す（10.0 を 10 に丸めない）。統計の桁は意味を持つので
    こちらで整形しない。
    """
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            sys.exit(f"--data の書式が違う（ラベル=値）: {part}")
        k, v = part.rsplit("=", 1)
        try:
            out.append((k.strip(), float(v), v.strip()))
        except ValueError:
            sys.exit(f"値が数値でない: {part}")
    if not out:
        sys.exit("--data が空")
    return out


def parse_slope(s):
    """"項目=前値>後値,項目=—>後値" を [(項目, 前値, 前表記, 後値, 後表記)] にする。

    前値なし（—）は None。値の表記は parse_data と同じく書いたまま出す。
    """
    dash = ("—", "―", "ー", "-", "–", "")
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            sys.exit(f"slope の --data の書式が違う（項目=前値>後値）: {part}")
        k, v = part.rsplit("=", 1)
        if ">" not in v:
            sys.exit(f"slope の --data は 項目=前値>後値 で書く: {part}")
        a, b = v.split(">", 1)
        a, b = a.strip(), b.strip()
        if b in dash:
            sys.exit(f"slope の後値は省略できない: {part}")
        try:
            va = None if a in dash else float(a)
            vb = float(b)
        except ValueError:
            sys.exit(f"値が数値でない: {part}")
        out.append((k.strip(), va, a, vb, b))
    if not out:
        sys.exit("--data が空")
    return out


def fmt(raw, unit):
    return str(raw) + unit


def tw(s, size):
    """テキストの概算幅。全角は size、半角は size*0.56 で見る（重なり回避の判定用）"""
    return sum(size if ord(c) > 0x2E7F else size * 0.56 for c in str(s))


def spread(ys, gap, lo, hi):
    """近すぎる y を最小 gap まで押し広げる（並び順は保つ）。はみ出したら全体を戻す"""
    if not ys:
        return []
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for k in range(1, len(order)):
        a, b = order[k - 1], order[k]
        if out[b] - out[a] < gap:
            out[b] = out[a] + gap
    over = out[order[-1]] - hi
    if over > 0:
        for i in order:
            out[i] -= over
        for k in range(len(order) - 2, -1, -1):
            a, b = order[k], order[k + 1]
            if out[b] - out[a] < gap:
                out[a] = out[b] - gap
    under = lo - out[order[0]]
    if under > 0:
        for i in order:
            out[i] += under
    return out


def text(x, y, s, size=20, fill=INK, weight=400, anchor="start", family=SANS):
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{esc(s)}</text>')


# ---------------------------------------------------------------- 型

BAR_STEP = 52          # 1行の高さ。barの自動高さ計算と描画で共有する


def label_col(rows, w):
    """barのラベル欄の右端x。最長ラベルに合わせ、全体の4割は超えない"""
    longest = max((len(str(lb)) for lb, _v, _r in rows), default=4)
    return int(min(w * 0.40, max(180, longest * 21 + 40)))


def fig_bar(d, o):
    """横棒ランキング。上位 --hot 本を朱、残りをグレー、最終行を墨で落とす"""
    rows = d
    top = max(v for _, v, _r in rows)
    # ラベル欄は最長ラベルから決める（固定幅だと短いラベルのとき左が大きく空く）
    x0 = label_col(rows, o["w"])
    barw = o["w"] - x0 - 200            # 右は値テキスト＋注の余白
    y = o["body_top"] + 6
    step = min(BAR_STEP, int((o["body_bottom"] - y) / max(len(rows), 1)))
    bh = min(34, step - 12)
    parts = []
    # 墨で落とす行・注を付ける行は 1始まりの行番号で指定する（既定は最終行）
    ink_i = (o["ink_row"] - 1) if o["ink_row"] else (len(rows) - 1 if o["ink_last"] else -1)
    tag_i = (o["tag_row"] - 1) if o["tag_row"] else len(rows) - 1
    for i, (label, v, raw) in enumerate(rows):
        w = max(6, int(barw * v / top))
        color = ACCENT if i < o["hot"] else DIM
        if i == ink_i:
            color = INK
        parts.append(text(x0 - 18, y + bh - 9, label, 21, INK, 700, "end"))
        parts.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{bh}" rx="2" fill="{color}"/>')
        vc = ACCENT if i < o["hot"] else (INK if i == ink_i else FAINT)
        parts.append(text(x0 + w + 12, y + bh - 8, fmt(raw, o["unit"]), 24, vc, 900))
        if o["tag"] and i == tag_i:
            tw = x0 + w + 12 + len(fmt(raw, o["unit"])) * 15
            parts.append(text(tw + 14, y + bh - 9, o["tag"], 16, ACCENT, 700))
        y += step
    return "".join(parts)


def fig_gap(d, o):
    """2値の対比。左右に太い棒、真ん中に差"""
    if len(d) < 2:
        sys.exit("gap は --data を2件にする")
    (la, va, ra), (lb, vb, rb) = d[0], d[1]
    top = max(va, vb)
    cy = (o["body_top"] + o["body_bottom"]) // 2
    maxh = min(210, o["body_bottom"] - o["body_top"] - 70)
    parts = []
    for i, (label, v, raw, color) in enumerate([(la, va, ra, ACCENT), (lb, vb, rb, DIM)]):
        h = max(20, int(maxh * v / top))
        cx = 330 + i * 480
        base = cy + maxh // 2
        parts.append(f'<rect x="{cx - 110}" y="{base - h}" width="220" height="{h}" rx="3" fill="{color}"/>')
        parts.append(text(cx, base - h - 18, fmt(raw, o["unit"]), 46, color if i == 0 else SUB, 900, "middle"))
        parts.append(text(cx, base + 34, label, 21, INK, 700, "middle"))
    mx = 330 + 240
    parts.append(f'<line x1="{mx}" y1="{o["body_top"] + 6}" x2="{mx}" y2="{o["body_bottom"] - 6}" '
                 f'stroke="{FAINT}" stroke-width="1" stroke-dasharray="4 4"/>')
    # 差は --diff を付けたときだけ出す。母集団や設問が違う数字を引き算すると嘘になる
    if o["diff"]:
        d2 = round(abs(va - vb), 10)
        d2 = int(d2) if d2 % 1 == 0 else d2
        parts.append(text(mx, cy - 88, f"差 {fmt(d2, o['unit'])}", 24, ACCENT, 900, "middle", SERIF))
    return "".join(parts)


def fig_slope(d, o):
    """2時点の変化。左右の基準線を線で結ぶ。--hot n は変化量の大きい上位n本を朱

    上昇・下落は色で区別しない（色に意味を持たせると凡例が要る）。
    """
    # 左右の基準線は「項目ラベル＋値＋引出し線の余白」が収まる位置まで内側に寄せる
    # （固定位置だと長い項目名が左端からはみ出す）
    gut = 46
    lw = max(tw(lb, 21) for lb, _va, _ra, _vb, _rb in d)
    vw = max([tw(fmt(ra, o["unit"]), 20) for _lb, va, ra, _vb, _rb in d if va is not None]
             + [tw("—", 20)])
    vwr = max(tw(fmt(rb, o["unit"]), 20) for _lb, _va, _ra, _vb, rb in d)
    # 左右30は表紙モードの飾り枠（x=22）を避ける分
    x0 = int(max(430, 30 + lw + 16 + vw + gut + 8))
    x1 = int(min(o["w"] - 30 - vwr - gut - 8, x0 + 460))
    x1 = max(x1, x0 + 200)
    ytop = o["body_top"] + 46          # 上に列見出しを置く分
    ybot = o["body_bottom"] - 18
    vals = []
    for _lb, va, _ra, vb, _rb in d:
        vals.append(vb)
        if va is not None:
            vals.append(va)
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.18 or 1
    lo, hi = lo - pad, hi + pad

    def py(v):
        return ybot - (ybot - ytop) * (v - lo) / (hi - lo)

    # 変化量の大きい順に --hot 本だけ朱。前値なしは変化量が出ないので対象外
    chg = [(abs(vb - va) if va is not None else -1.0) for _lb, va, _ra, vb, _rb in d]
    rank = sorted(range(len(d)), key=lambda i: -chg[i])
    hot = {i for i in rank[:max(o["hot"], 0)] if chg[i] >= 0}

    parts = []
    for x in (x0, x1):
        parts.append(f'<line x1="{x}" y1="{ytop - 26}" x2="{x}" y2="{ybot + 20}" '
                     f'stroke="{FAINT}" stroke-width="1.2"/>')
    if o["cols"]:
        ca, cb = (o["cols"] + "|").split("|")[:2]
        parts.append(text(x0, ytop - 40, ca, 20, SUB, 700, "middle"))
        if cb:
            parts.append(text(x1, ytop - 40, cb, 20, SUB, 700, "middle"))
    # 線と点は先に全部描いてからラベルを重ねる（線がラベルの上に乗らないように）
    for i, (_lb, va, _ra, vb, _rb) in enumerate(d):
        col = ACCENT if i in hot else DIM
        yb = py(vb)
        if va is not None:
            ya = py(va)
            parts.append(f'<line x1="{x0}" y1="{ya:.1f}" x2="{x1}" y2="{yb:.1f}" '
                         f'stroke="{col}" stroke-width="{3.6 if i in hot else 2.6}" stroke-linecap="round"/>')
            parts.append(f'<circle cx="{x0}" cy="{ya:.1f}" r="7" fill="{col}"/>')
        parts.append(f'<circle cx="{x1}" cy="{yb:.1f}" r="7" fill="{col}"/>')
    # ラベルは点の高さに置き、重なるときだけ上下にずらす。
    # ずらすと点との対応が切れるので、両脇に取った余白（gut）に引出し線を通す
    lvx, rvx = x0 - gut - 8, x1 + gut + 8
    lbx = lvx - vw - 16
    dy = [py(vb if va is None else va) for _lb, va, _ra, vb, _rb in d]
    ry0 = [py(vb) for _lb, _va, _ra, vb, _rb in d]
    ly = spread([y + 7 for y in dy], 32, o["body_top"] + 24, o["body_bottom"] - 4)
    ry = spread([y + 7 for y in ry0], 32, o["body_top"] + 24, o["body_bottom"] - 4)

    def lead(x_from, x_turn, x_to, ytxt, ypt):
        if abs(ytxt - ypt) < 3:
            return ""
        return (f'<polyline points="{x_from:.1f},{ytxt:.1f} {x_turn:.1f},{ytxt:.1f} '
                f'{x_to:.1f},{ypt:.1f}" fill="none" stroke="{DIM}" stroke-width="1"/>')

    for i, (lb, va, ra, vb, rb) in enumerate(d):
        col = ACCENT if i in hot else SUB
        parts.append(text(lbx, ly[i], lb, 21, INK if i in hot else SUB,
                          700 if i in hot else 500, "end"))
        if va is None:
            parts.append(text(lvx, ly[i], "—", 20, DIM, 700, "end"))
        else:
            parts.append(text(lvx, ly[i], fmt(ra, o["unit"]), 20, col, 900, "end"))
            parts.append(lead(lvx + 8, x0 - 22, x0 - 9, ly[i] - 6, dy[i]))
        parts.append(text(rvx, ry[i], fmt(rb, o["unit"]), 20, col, 900))
        parts.append(lead(rvx - 8, x1 + 22, x1 + 9, ry[i] - 6, ry0[i]))
    return "".join(parts)


def fig_line(d, o):
    """折れ線。--mark "index:文言" で点に吹き出し"""
    xs = d
    top = max(v for _, v, _r in xs) * 1.15
    x0, x1 = 220, 1000
    ytop, ybot = o["body_top"] + 26, o["body_bottom"] - 78
    n = len(xs)
    px = [x0 + (x1 - x0) * i / max(n - 1, 1) for i in range(n)]
    py = [ybot - (ybot - ytop) * (v / top) for _, v, _r in xs]
    parts = [f'<line x1="{x0 - 34}" y1="{ybot}" x2="{x1 + 34}" y2="{ybot}" stroke="{INK}" stroke-width="1.6"/>',
             f'<line x1="{x0 - 34}" y1="{ytop - 20}" x2="{x0 - 34}" y2="{ybot}" stroke="{INK}" stroke-width="1.6"/>']
    pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in zip(px, py))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="4" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (label, v, raw) in enumerate(xs):
        parts.append(f'<circle cx="{px[i]:.1f}" cy="{py[i]:.1f}" r="8" fill="{ACCENT}"/>')
        parts.append(text(px[i], ybot + 32, label, 20, INK, 700, "middle"))
    for m in o["marks"]:
        idx, body = m
        if idx >= n:
            continue
        bw = 26 + len(body) * 17
        flip = px[idx] + 40 + bw > o["w"] - 40
        bx = (px[idx] - 40 - bw) if flip else (px[idx] + 40)
        by = py[idx] - 46
        parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw}" height="46" rx="4" fill="{BG}" stroke="{ACCENT}"/>')
        parts.append(text(bx + bw / 2, by + 31, body, 21, INK, 700, "middle"))
        ex = (bx + bw) if flip else bx
        parts.append(f'<line x1="{px[idx] + (-9 if flip else 9):.1f}" y1="{py[idx]:.1f}" x2="{ex:.1f}" y2="{by + 46:.1f}" '
                     f'stroke="{ACCENT}" stroke-width="1.6"/>')
    if o["axis"]:
        ax, ay = (o["axis"] + "|").split("|")[:2]
        parts.append(text((x0 + x1) / 2, ybot + 66, ax, 19, SUB, 500, "middle"))
        if ay:
            parts.append(text(x0 - 56, (ytop + ybot) / 2, ay, 19, SUB, 500, "end"))
    return "".join(parts)


def fig_stack(d, o):
    """100%積み上げ1本。内訳の比率を1本で見せる"""
    total = sum(v for _, v, _r in d) or 1
    x0, w = 130, 940
    y = (o["body_top"] + o["body_bottom"]) // 2 - 60
    h = 92
    cols = [ACCENT, DIM, DIM2, "#e7e0d2"]
    parts = []
    x = x0
    for i, (label, v, raw) in enumerate(d):
        seg = w * v / total
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{seg:.1f}" height="{h}" '
                     f'fill="{cols[i % len(cols)]}"/>')
        if seg > 120:
            parts.append(text(x + seg / 2, y + h / 2 + 10, fmt(raw, o["unit"]), 30,
                              BG if i < o["hot"] else INK, 900, "middle"))
        else:
            parts.append(text(x + seg / 2, y - 16, fmt(raw, o["unit"]), 22, ACCENT, 900, "middle"))
        ly = y + h + 42 + (i % 2) * 34
        parts.append(text(x + seg / 2, ly, label, 20, INK if i < o["hot"] else SUB,
                          700 if i < o["hot"] else 500, "middle"))
        parts.append(f'<line x1="{x + seg / 2:.1f}" y1="{y + h + 6}" x2="{x + seg / 2:.1f}" '
                     f'y2="{ly - 18}" stroke="{FAINT}" stroke-width="1"/>')
        x += seg
    parts.append(f'<rect x="{x0}" y="{y}" width="{w}" height="{h}" fill="none" stroke="{INK}" stroke-width="1.2"/>')
    return "".join(parts)


def fig_ratio(d, o):
    """割合1つを巨大に。ドーナツ＋数字"""
    label, v, raw = d[0]
    cx, cy, r = 330, (o["body_top"] + o["body_bottom"]) // 2, 128
    circ = 2 * 3.14159265 * r
    on = circ * min(v, 100) / 100
    parts = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{DIM2}" stroke-width="40"/>',
             f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{ACCENT}" stroke-width="40" '
             f'stroke-dasharray="{on:.1f} {circ - on:.1f}" transform="rotate(-90 {cx} {cy})" stroke-linecap="butt"/>',
             text(cx, cy + 22, fmt(raw, o["unit"]), 66, ACCENT, 900, "middle", SANS)]
    parts.append(text(660, cy - 26, label, 30, INK, 700))
    if len(d) > 1:
        parts.append(text(660, cy + 26, d[1][0], 24, SUB, 500))
        parts.append(text(660, cy + 70, fmt(d[1][2], o["unit"]), 34, SUB, 900))
    return "".join(parts)


def fig_matrix(d, o):
    """2軸4象限。--data は 左上=,右上=,左下=,右下= の順"""
    if len(d) < 4:
        sys.exit("matrix は --data を4件にする（左上,右上,左下,右下）")
    x0, y0, w, h = 300, o["body_top"] + 6, 620, o["body_bottom"] - o["body_top"] - 66
    mx, my = x0 + w / 2, y0 + h / 2
    cells = [(x0, y0), (mx, y0), (x0, my), (mx, my)]
    parts = [f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="none" stroke="{FAINT}" stroke-width="1"/>']
    for i, (cx, cy) in enumerate(cells):
        fill = "rgba(166,58,36,.08)" if i == o["hot"] - 1 else "rgba(92,84,74,.05)"
        parts.append(f'<rect x="{cx}" y="{cy}" width="{w / 2}" height="{h / 2}" fill="{fill}"/>')
        col = ACCENT if i == o["hot"] - 1 else INK
        for j, ln in enumerate(d[i][0].split("／")):
            parts.append(text(cx + w / 4, cy + h / 4 - 6 + j * 30, ln, 21, col, 700, "middle"))
    parts.append(f'<line x1="{mx}" y1="{y0}" x2="{mx}" y2="{y0 + h}" stroke="{INK}" stroke-width="1.4"/>')
    parts.append(f'<line x1="{x0}" y1="{my}" x2="{x0 + w}" y2="{my}" stroke="{INK}" stroke-width="1.4"/>')
    if o["axis"]:
        ax, ay = (o["axis"] + "|").split("|")[:2]
        parts.append(text(x0 + w / 2, y0 + h + 38, ax, 20, SUB, 500, "middle"))
        if ay:
            parts.append(text(x0 - 22, y0 + h / 2, ay, 20, SUB, 500, "end"))
    return "".join(parts)


def fig_waterfall(d, o):
    """増減の内訳。最初＝始点・途中＝+/-の増減・最後＝終点

    増減は色に意味を持たせない（減=赤にしない）。--hot k で k番目の増減だけ朱。
    """
    n = len(d)
    if n < 3:
        sys.exit("waterfall は --data を3件以上にする（始点,増減…,終点）")
    for lb, _v, raw in d[1:-1]:
        if not raw.startswith(("+", "-")):
            sys.exit(f"waterfall の途中は増減なので +/- を付ける: {lb}={raw}")
    # 各バーの下端・上端を値で持つ（始点と終点は0から立てる柱）
    bars, cum = [], d[0][1]
    bars.append((0.0, d[0][1], INK))
    for i, (_lb, v, _raw) in enumerate(d[1:-1], start=1):
        bars.append((cum, cum + v, ACCENT if i == o["hot"] else DIM))
        cum += v
    bars.append((0.0, d[-1][1], INK))
    levels = [0.0] + [x for a, b, _c in bars for x in (a, b)]
    lo, hi = min(levels), max(levels)
    span = (hi - lo) * 1.02 or 1

    x0 = 110
    slot = (o["w"] - x0 * 2) / n
    barw = min(126, slot * 0.58)
    cx = [x0 + slot * (i + 0.5) for i in range(n)]
    # ラベルが隣とぶつかるときだけ2段にする
    stag = any(tw(lb, 20) > slot - 10 for lb, _v, _r in d)
    ybot = o["body_bottom"] - (78 if stag else 44)
    ytop = o["body_top"] + 44

    def py(v):
        return ybot - (ybot - ytop) * (v - lo) / span

    base = py(0)
    parts = [f'<line x1="{x0 - 30}" y1="{base:.1f}" x2="{o["w"] - x0 + 30}" y2="{base:.1f}" '
             f'stroke="{INK}" stroke-width="1.6"/>']
    for i, (a, b, col) in enumerate(bars):
        ya, yb = py(a), py(b)
        top, h = min(ya, yb), max(abs(ya - yb), 4)
        parts.append(f'<rect x="{cx[i] - barw / 2:.1f}" y="{top:.1f}" width="{barw:.1f}" '
                     f'height="{h:.1f}" rx="2" fill="{col}"/>')
        # 到達点から次のバーの立ち上がりへ細い破線をつなぐ（高さは到達点で水平）
        if i < n - 1:
            parts.append(f'<line x1="{cx[i] + barw / 2:.1f}" y1="{yb:.1f}" '
                         f'x2="{cx[i + 1] - barw / 2:.1f}" y2="{yb:.1f}" '
                         f'stroke="{FAINT}" stroke-width="1" stroke-dasharray="4 4"/>')
        lb, _v, raw = d[i]
        vc = INK if col == INK else (ACCENT if col == ACCENT else SUB)
        parts.append(text(cx[i], top - 14, fmt(raw, o["unit"]), 24, vc, 900, "middle"))
        # ラベルは0線ではなく描画域の下端に置く（マイナスに沈むとバーが0線より下に出る）
        ly = ybot + 34 + (i % 2) * 32 * (1 if stag else 0)
        parts.append(text(cx[i], ly, lb, 20, SUB if col == DIM else INK,
                          500 if col == DIM else 700, "middle"))
        if stag and i % 2:
            parts.append(f'<line x1="{cx[i]:.1f}" y1="{ybot + 8:.1f}" x2="{cx[i]:.1f}" '
                         f'y2="{ly - 18:.1f}" stroke="{FAINT}" stroke-width="1"/>')
    return "".join(parts)


DOT_DENSE = 12         # これを超え、かつ文字が3段以上に積むなら間引く
DOT_ROWS = 2           # 全部に文字を付けたまま許す段数


def dot_place(d, o):
    """dotの x座標と行を先に決める（高さ計算と描画で同じ結果を使う）

    行は軸からの段数。y = 軸 + 行 * pitch なので、負が上・正が下。
    文字が2段までに収まるなら全部に付けて下へ積む。それ以上に積むなら
    文字は --hot・最小・最大だけにして、点は軸を中心に上下交互へ散らす
    （47都道府県で下に伸ばすと1000px超の柱になり、右半分が空洞になる）。
    件数だけで切り替えると、13件が等間隔に並ぶだけでも間引かれてしまう。
    """
    n = len(d)
    lab = 20 if n <= DOT_DENSE else (17 if n <= 24 else 15)
    val = lab - 1
    vals = [v for _lb, v, _r in d]
    if o["ref"]:
        vals.append(o["ref"][0])
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * 0.06 or 1
    lo, hi = lo - pad, hi + pad
    x0, x1 = 96, o["w"] - 96
    xs = [x0 + (x1 - x0) * (v - lo) / (hi - lo) for _lb, v, _r in d]

    def stack_down(half):
        """左から順に、空いている一番上の段へ置く（下向きに積む）"""
        rows, right = [0] * n, []
        for i in sorted(range(n), key=lambda i: xs[i]):
            t = 0
            while t < len(right) and xs[i] - half[i] < right[t]:
                t += 1
            if t == len(right):
                right.append(0.0)
            right[t] = xs[i] + half[i]
            rows[i] = t
        return rows, len(right)

    full = [max(9.0, tw(lb, lab) / 2, tw(fmt(raw, o["unit"]), val) / 2) + 7
            for (lb, _v, raw) in d]
    rows, nrow = stack_down(full)
    dense = n > DOT_DENSE and nrow > DOT_ROWS

    # 文字を出す点。密なときは --hot 該当・最小・最大だけ（点は全部出す）
    if dense:
        keep = set(range(min(max(o["hot"], 0), n)))
        keep.add(min(range(n), key=lambda i: d[i][1]))
        keep.add(max(range(n), key=lambda i: d[i][1]))
        half = [full[i] if i in keep else 9.0 for i in range(n)]
    else:
        keep, half = set(range(n)), full

    if dense:
        pitch = 19
        up = -(-(lab + 18) // pitch)      # 文字が要る点が上下に食う行数
        dn = -(-(val + 20) // pitch)
        pref = [0] + [k for j in range(1, 10) for k in (j, -j)]
        rows, occ = [0] * n, {}

        def block(i, k):
            return range(k - up, k + dn + 1) if i in keep else range(k, k + 1)

        def fits(i, k):
            for r in block(i, k):
                for a, b in occ.get(r, ()):
                    if xs[i] - half[i] < b and a < xs[i] + half[i]:
                        return False
            return True

        # 文字を出す点を先に置く（軸上の0行を取らせる）
        for i in sorted(range(n), key=lambda i: (i not in keep, xs[i])):
            k = next((k for k in pref if fits(i, k)), pref[-1])
            for r in block(i, k):
                occ.setdefault(r, []).append((xs[i] - half[i], xs[i] + half[i]))
            rows[i] = k
    else:
        # 段の間隔は、上の段の値と下の段のラベルがくっつかない分を残す
        pitch = lab + val + (36 if nrow <= 6 else 34)

    # 中身の上下の張り出しから軸の位置と下端を決める
    ups = [rows[i] * pitch - 7 - (lab + 8 if i in keep else 0) for i in range(n)]
    dns = [rows[i] * pitch + 7 + (val + 8 if i in keep else 0) for i in range(n)]
    axis = o["body_top"] - min(ups) + (31 if o["ref"] else 1)
    return {"x": xs, "row": rows, "keep": keep, "lab": lab, "val": val, "dense": dense,
            "pitch": pitch, "axis": axis, "bottom": axis + max(dns),
            "drop": (not dense) and max(rows) <= 3,
            "x0": x0, "x1": x1, "lo": lo, "hi": hi, "half": half}


def fig_dot(d, o):
    """多数の値を横軸1本に並べる。--ref で朱の基準線。近い点は段をずらす"""
    p = o.get("dotp") or dot_place(d, o)
    xs, ax, keep = p["x"], p["axis"], p["keep"]
    parts = [f'<line x1="{p["x0"] - 34}" y1="{ax}" x2="{p["x1"] + 34}" y2="{ax}" '
             f'stroke="{INK}" stroke-width="1.6"/>']
    if o["ref"]:
        rv, rlab, rraw = o["ref"]
        rx = p["x0"] + (p["x1"] - p["x0"]) * (rv - p["lo"]) / (p["hi"] - p["lo"])
        parts.append(f'<line x1="{rx:.1f}" y1="{o["body_top"] + 22:.1f}" x2="{rx:.1f}" '
                     f'y2="{p["bottom"] + 10:.1f}" stroke="{ACCENT}" stroke-width="1.6" '
                     f'stroke-dasharray="7 5"/>')
        lt = f"{rlab} {fmt(rraw, o['unit'])}"
        lw = tw(lt, 19)
        parts.append(text(min(max(rx, lw / 2 + 10), o["w"] - lw / 2 - 10),
                          o["body_top"] + 12, lt, 19, ACCENT, 700, "middle"))
    for i, (lb, _v, raw) in enumerate(d):
        cy = ax + p["row"][i] * p["pitch"]
        if p["row"][i] and p["drop"]:
            # ラベルの手前で止める（点まで引くと自分のラベルを串刺しにする）
            parts.append(f'<line x1="{xs[i]:.1f}" y1="{ax + 4}" x2="{xs[i]:.1f}" '
                         f'y2="{cy - 19 - p["lab"]:.1f}" stroke="{DIM}" stroke-width="1"/>')
        hot = i < o["hot"]
        if hot:
            parts.append(f'<circle cx="{xs[i]:.1f}" cy="{cy:.1f}" r="7" fill="{ACCENT}"/>')
        else:
            parts.append(f'<circle cx="{xs[i]:.1f}" cy="{cy:.1f}" r="7" fill="{BG}" '
                         f'stroke="{INK}" stroke-width="1.6"/>')
        if i not in keep:
            continue
        # ラベルは点の上・値は点の下。端では画面外に出ないよう寄せる
        tx = min(max(xs[i], p["half"][i] + 4), o["w"] - p["half"][i] - 4)
        parts.append(text(tx, cy - 15, lb, p["lab"], ACCENT if hot else INK,
                          900 if hot else 700, "middle"))
        parts.append(text(tx, cy + 13 + p["val"], fmt(raw, o["unit"]), p["val"],
                          ACCENT if hot else SUB, 900 if hot else 500, "middle"))
    return "".join(parts)


def parse_timeline(s):
    """timeline用 "2026-08-25=デジタル化・AI導入補助金 1次締切,..." を (日付, ラベル) に。"""
    import datetime
    rows = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            sys.exit('timeline の --data は "YYYY-MM-DD=出来事" の形にする: ' + part)
        raw, label = part.split("=", 1)
        try:
            dt = datetime.date.fromisoformat(raw.strip())
        except ValueError:
            sys.exit(f"日付が YYYY-MM-DD になっていない: {raw}")
        rows.append((dt, label.strip(), raw.strip()))
    if len(rows) < 2:
        sys.exit("timeline は --data を2件以上にする")
    return sorted(rows, key=lambda r: r[0])


def fig_timeline(d, o):
    """日付の軸に出来事を置く。締切・公募・発効日など「いつ何が起きるか」用。

    ラベルは軸の上下へ交互に出す（横に密集しても重ならない）。
    """
    lo, hi = d[0][0], d[-1][0]
    span = max(1, (hi - lo).days)
    x0, x1 = 150, o["w"] - 150
    cy = (o["body_top"] + o["body_bottom"]) // 2
    parts = [f'<line x1="{x0 - 40}" y1="{cy}" x2="{x1 + 40}" y2="{cy}" '
             f'stroke="{FAINT}" stroke-width="1.5"/>']
    for i, (dt, label, _raw) in enumerate(d):
        x = x0 + (x1 - x0) * (dt - lo).days / span
        hot = i < o["hot"]
        col = ACCENT if hot else DIM
        up = i % 2 == 0                      # 上下交互
        ytxt = cy - 34 if up else cy + 34
        parts.append(f'<line x1="{x}" y1="{cy}" x2="{x}" y2="{ytxt + (12 if up else -12)}" '
                     f'stroke="{col}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{x}" cy="{cy}" r="{9 if hot else 7}" fill="{col}"/>')
        parts.append(text(x, ytxt - (14 if up else -14), f"{dt.month}/{dt.day}",
                          26, col if hot else SUB, 900, "middle", SERIF))
        # 端の点はラベルが画面外に出るので、寄せ方を切り替える（左端で見切れた 2026-08-08）
        half = tw(label, 19) / 2
        lx, anchor = x, "middle"
        if x - half < 24:
            lx, anchor = 24, "start"
        elif x + half > o["w"] - 24:
            lx, anchor = o["w"] - 24, "end"
        parts.append(text(lx, ytxt + (-44 if up else 44), label, 19,
                          INK if hot else SUB, 700 if hot else 500, anchor))
    parts.append(text(x0 - 40, cy + 78, f"{lo.year}年", 17, FAINT, 400, "middle"))
    return "".join(parts)


def fig_flow(d, o):
    """番号のついた手順。縦に積む（横組みだと長いラベルが入らずSP幅で潰れる）。

    --data "業務を選ぶ=1,現状を測る=2,..." の値は表示順のためだけに使う。
    """
    cx = 190
    step = min(112, max(76, (o["body_bottom"] - o["body_top"]) // max(1, len(d))))
    top = o["body_top"] + step // 2
    parts = []
    for i, (label, _v, _raw) in enumerate(d):
        cy = top + i * step
        hot = i < o["hot"]
        col = ACCENT if hot else DIM
        if i < len(d) - 1:
            parts.append(f'<line x1="{cx}" y1="{cy + 30}" x2="{cx}" y2="{cy + step - 30}" '
                         f'stroke="{FAINT}" stroke-width="1.5"/>')
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="27" fill="none" stroke="{col}" stroke-width="2.5"/>')
        parts.append(text(cx, cy + 12, str(i + 1), 30, col, 900, "middle", SERIF))
        parts.append(text(cx + 56, cy + 11, label, 27, INK, 700))
    return "".join(parts)


TYPES = {"bar": fig_bar, "gap": fig_gap, "slope": fig_slope, "line": fig_line,
         "stack": fig_stack, "ratio": fig_ratio, "matrix": fig_matrix,
         "waterfall": fig_waterfall, "dot": fig_dot,
         "timeline": fig_timeline, "flow": fig_flow}


# ---------------------------------------------------------------- 組み立て

def build_svg(kind, d, o):
    """bare=True は記事本文用。地色・枠・NGraph署名・見出しを出さない。

    本文では見出しを <p class="a-fig-title"> が持ち、地色は .a-fig-wrap が持つので、
    SVG側に重ねると二重になる。表紙・X添付用（bare=False）は1枚で完結させる。
    """
    w = o["w"]
    bare = o["bare"]
    head = []
    if bare:
        y = 18
        if o["sub"]:
            y += 26
            head.append(text(w / 2, y, o["sub"], 19, SUB, 500, "middle"))
        o["body_top"] = y + 26
        foot_space = 96 if o["concl"] else 54
    else:
        y = 92
        head.append(text(w / 2, y, o["title"], 46, INK, 900, "middle", SERIF))
        if o["sub"]:
            y += 40
            head.append(text(w / 2, y, o["sub"], 19, SUB, 500, "middle"))
        o["body_top"] = y + 34
        foot_space = 150 if o["concl"] else 110
    # --h 未指定（0）なら中身から高さを決める。barは行数に追従させる
    # （固定630だと3本のとき下半分が丸ごと空く）
    h = o["h"]
    if not h:
        if kind == "bar":
            h = o["body_top"] + 6 + len(d) * BAR_STEP + foot_space
            h = max(h, 300)
        elif kind == "gap":
            # 棒の最大高210＋上の数値と下のラベル分。630だと棒の下が大きく空く
            h = o["body_top"] + 320 + foot_space
        elif kind == "flow":
            h = o["body_top"] + len(d) * 112 + foot_space
            h = max(h, 300)
        elif kind == "timeline":
            h = o["body_top"] + 240 + foot_space
        elif kind == "dot":
            # 段の数は中身で決まる（点が近いほど増える）ので高さも追従させる
            p = dot_place(d, o)
            o["dotp"] = p
            h = int(p["bottom"] + 15 + foot_space)
            h = max(h, 300)
        else:
            h = 630
    o["h"] = h
    o["body_bottom"] = h - foot_space
    body = TYPES[kind](d, o)
    foot = []
    if o["concl"]:
        foot.append(text(w / 2, h - (58 if bare else 104), o["concl"], 24, INK, 900, "middle", SERIF))
    if o["src"]:
        foot.append(text(56 if not bare else 8, h - (16 if bare else 44),
                         "出所：" + o["src"], 13, FAINT, 400))
    if bare:
        return (f'<svg viewBox="0 0 {w} {h}" width="100%" style="min-width:640px" '
                f'role="img" aria-label="{esc(o["title"])}">'
                + "".join(head) + body + "".join(foot) + "</svg>")
    foot.append(text(w - 56, h - 42, "NGraph. ngraph.jp", 18, FAINT, 700, "end", SERIF))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{esc(o["title"])}">'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>'
            f'<rect x="22" y="22" width="{w - 44}" height="{h - 44}" fill="none" stroke="{LINE}"/>'
            + "".join(head) + body + "".join(foot) + "</svg>")


HTML = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>*{margin:0;padding:0}body{width:%(w)dpx;height:%(h)dpx;overflow:hidden}svg{display:block}</style>
</head><body>%(svg)s</body></html>"""


def render_png(svg, out, w, h):
    """Edgeヘッドレスで書き出す。作業ディレクトリに直接書けないことがあるので %TEMP% 経由"""
    tmpdir = tempfile.gettempdir()
    src = os.path.join(tmpdir, "ngfig_%d.html" % int(time.time() * 1000))
    png = os.path.join(tmpdir, "ngfig_%d.png" % int(time.time() * 1000))
    open(src, "w", encoding="utf-8").write(HTML % {"w": w, "h": h, "svg": svg})
    for attempt in range(3):
        udd = tempfile.mkdtemp(prefix="ngfig_udd_")
        subprocess.run([EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--disable-dev-shm-usage", "--hide-scrollbars",
                        "--user-data-dir=" + udd,
                        "--window-size=%d,%d" % (w, h), "--virtual-time-budget=10000",
                        "--screenshot=" + png, "file:///" + src.replace("\\", "/")],
                       check=False, capture_output=True)
        for _ in range(6):
            if os.path.exists(png) and os.path.getsize(png) > 5000:
                break
            time.sleep(1)
        if os.path.exists(png) and os.path.getsize(png) > 5000:
            break
    if not os.path.exists(png):
        sys.exit("生成に失敗した（Edgeのパスを確認）")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if out.lower().endswith((".jpg", ".jpeg")):
        from PIL import Image
        Image.open(png).convert("RGB").save(out, quality=92)
    else:
        shutil.copyfile(png, out)
    os.remove(src)
    os.remove(png)


def main():
    # docstring 冒頭（データの形→型の対応表と型一覧）を --help にそのまま出す
    ap = argparse.ArgumentParser(
        description=__doc__.split("共通オプション:")[0].rstrip(),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("type", choices=sorted(TYPES))
    ap.add_argument("--title", required=True, help="見出し（結論を書く）")
    ap.add_argument("--data", required=True, help="ラベル=値,ラベル=値")
    ap.add_argument("--sub", default="")
    ap.add_argument("--concl", default="", help="図の下の結論1行")
    ap.add_argument("--src", default="", help="出所")
    ap.add_argument("--tag", default="", help="最終行に付ける注（barのみ）")
    ap.add_argument("--axis", default="", help="横軸|縦軸（line/matrix）")
    ap.add_argument("--cols", default="", help='slope用 2時点の見出し "2023年度|2025年度"')
    ap.add_argument("--ref", default="", help='dot用 基準線 "1176:全国平均"')
    ap.add_argument("--mark", action="append", default=[], help='line用 "点の番号:文言"（0始まり）')
    ap.add_argument("--hot", type=int, default=1, help="朱で強調する本数（既定1）")
    ap.add_argument("--ink-last", action="store_true", help="最終行を墨で塗る（barの落とし）")
    ap.add_argument("--ink-row", type=int, default=0, help="墨で塗る行（1始まり・barのみ）")
    ap.add_argument("--tag-row", type=int, default=0, help="--tag を付ける行（1始まり・既定は最終行）")
    ap.add_argument("--diff", action="store_true",
                    help="gapで2値の差を出す。母集団・設問が同じときだけ付ける")
    ap.add_argument("--unit", default="%")
    ap.add_argument("--w", type=int, default=1200)
    ap.add_argument("--h", type=int, default=0,
                    help="キャンバス高さ。既定0=中身から自動（barは行数に追従）")
    ap.add_argument("--out", default="")
    ap.add_argument("--svg", action="store_true", help="記事に貼るブロックを標準出力へ")
    ap.add_argument("--bare", action="store_true",
                    help="本文用。地色・枠・署名・見出しを出さない（--svg と併用）")
    a = ap.parse_args()

    marks = []
    for m in a.mark:
        if ":" not in m:
            sys.exit('--mark は "番号:文言"')
        i, body = m.split(":", 1)
        marks.append((int(i), body))

    ref = None
    if a.ref:
        if ":" not in a.ref:
            sys.exit('--ref は "値:ラベル"')
        rv, rlab = a.ref.split(":", 1)
        try:
            ref = (float(rv), rlab.strip(), rv.strip())
        except ValueError:
            sys.exit(f"--ref の値が数値でない: {a.ref}")

    o = {"title": a.title, "sub": a.sub, "concl": a.concl, "src": a.src, "tag": a.tag,
         "axis": a.axis, "marks": marks, "hot": a.hot, "ink_last": a.ink_last,
         "unit": a.unit, "w": a.w, "h": a.h, "diff": a.diff, "bare": a.bare,
         "ink_row": a.ink_row, "tag_row": a.tag_row, "cols": a.cols, "ref": ref}
    if a.type == "slope":
        d = parse_slope(a.data)
    elif a.type == "timeline":
        d = parse_timeline(a.data)
    else:
        d = parse_data(a.data)
    svg = build_svg(a.type, d, o)

    if a.svg or (a.out and a.out.lower().endswith(".svg")):
        block = ('<div class="a-fig-wrap">\n'
                 f'<p class="a-fig-title">{esc(a.title)}</p>\n{svg}\n</div>')
        if a.out and a.out.lower().endswith(".svg"):
            open(a.out, "w", encoding="utf-8").write(svg)
            print("OK:", a.out)
        else:
            print(block)
        if not a.out or a.out.lower().endswith(".svg"):
            return

    out = a.out or os.path.join(ROOT, "assets", "blog", "fig", "fig-%s.png" % a.type)
    render_png(svg, out, a.w, o["h"])   # 自動高さのとき a.h は 0 なので確定値を使う
    print("OK:", out, os.path.getsize(out), "bytes")
    print("※ 必ず目視すること（単語中改行・見切れ・棒のはみ出し）")


if __name__ == "__main__":
    main()
