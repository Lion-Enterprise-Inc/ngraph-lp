# -*- coding: utf-8 -*-
"""記事の図解をグラフの型から作る（和禅テンプレ・1200x630）

使い方:
  python scripts/fig_gen.py <type> --title "見出し" --data "ラベル=値,ラベル=値" [options]

型（--type）:
  bar     横棒ランキング。上位を朱で強調（--hot 3 で上位3本）
  gap     2値の対比。差がいくつかを真ん中に出す
  line    折れ線。--mark "2:20万件で-13.6pt" で点に吹き出し
  stack   100%積み上げ1本。内訳の比率
  ratio   割合を1つだけ大きく。ドーナツ＋巨大数字
  matrix  2軸4象限。--axis "横軸ラベル|縦軸ラベル"

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


def fmt(raw, unit):
    return str(raw) + unit


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


TYPES = {"bar": fig_bar, "gap": fig_gap, "line": fig_line,
         "stack": fig_stack, "ratio": fig_ratio, "matrix": fig_matrix}


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
    ap = argparse.ArgumentParser()
    ap.add_argument("type", choices=sorted(TYPES))
    ap.add_argument("--title", required=True, help="見出し（結論を書く）")
    ap.add_argument("--data", required=True, help="ラベル=値,ラベル=値")
    ap.add_argument("--sub", default="")
    ap.add_argument("--concl", default="", help="図の下の結論1行")
    ap.add_argument("--src", default="", help="出所")
    ap.add_argument("--tag", default="", help="最終行に付ける注（barのみ）")
    ap.add_argument("--axis", default="", help="横軸|縦軸（line/matrix）")
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

    o = {"title": a.title, "sub": a.sub, "concl": a.concl, "src": a.src, "tag": a.tag,
         "axis": a.axis, "marks": marks, "hot": a.hot, "ink_last": a.ink_last,
         "unit": a.unit, "w": a.w, "h": a.h, "diff": a.diff, "bare": a.bare,
         "ink_row": a.ink_row, "tag_row": a.tag_row}
    svg = build_svg(a.type, parse_data(a.data), o)

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
