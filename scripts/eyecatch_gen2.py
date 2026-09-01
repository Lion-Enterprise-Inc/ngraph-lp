# -*- coding: utf-8 -*-
"""ブログ記事アイキャッチ生成 v2（2型システム・1200x630）

2026-09-01制定。和禅テンプレ（eyecatch_gen.py）の後継ではなく併存。
記事の種類で使い分ける（BLOG-OPS §3 が正本）:
  doodle = 顛末記・失敗解剖（現場の話を3コマの落書きで見せる。手の温度）
  cards  = 判断材料記事（制度・数字・期日。表紙1枚で結論が持ち帰れる）

使い方:
  python scripts/eyecatch_gen2.py doodle <slug> <title> \
      --chip="現場の顛末記 #01" \
      --beats="excel_x:止まったExcel,person:現場に入る,plant:毎朝、勝手に出る" [--out=...]
    title内 {m1}..{/m1}=橙マーカー {m2}..{/m2}=緑マーカー {nb}..{/nb}=改行禁止

  python scripts/eyecatch_gen2.py cards <slug> <title> \
      --card="確定|green|答申が出た県 {b}40{/b} 県|10月〜11月に順次発効" \
      --card="未定|yellow|まだ答申前 {b}7{/b} 県|秋田・山梨・徳島 ほか" \
      --card="最低|blue|全国で最も低いのは|沖縄 {b}1,079{/b} 円" \
      --card="実務|red|10月給与の前に|雇用契約と求人票の時給確認" \
      --asof="2026-09-01時点・47労働局の発表と突合" [--out=...]
    card=タグ|色|1行目|2行目。色: green/yellow/blue/red。{b}..{/b}=朱の強調数字

出力: 既定 assets/blog/<slug>.jpg。記録は eyecatch_gen.py と同じ _eyecatch.json
（pattern に "doodle"/"cards" が入る。eyecatch_text_check.py の改題ズレ検査はそのまま効く）。
文字あふれは生成前に機械で落とす（このゲートを外した表紙を公開しない）。
生成後は必ず画像を目視確認すること。
"""
import os
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "blog")
os.makedirs(OUT, exist_ok=True)
EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

# 共通パレット（生成り地・4色チップ）
INK, PAPER, RED, GREEN, YELLOW, BLUE, GRAY = (
    "#33302b", "#faf5e9", "#b8503c", "#4f8a5b", "#c9a227", "#5b7fa6", "#8a8378")

# ---- doodle型のコマ絵（手描き風SVG・stroke統一） ------------------------------
ICONS = {
 "excel_x": ('<svg width="110" height="96" viewBox="0 0 110 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M14 12 C 40 8, 78 10, 96 13 L 98 82 C 70 86, 36 85, 12 82 Z"/>'
   '<path d="M13 36 C 42 33, 74 34, 97 36"/><path d="M13 59 C 42 57, 74 58, 97 59"/>'
   '<path d="M42 13 C 41 38, 42 62, 42 83"/><path d="M70 13 C 71 38, 70 62, 71 83"/>'
   '<path d="M20 45 L 92 74" stroke="%r" stroke-width="6"/><path d="M92 45 L 20 74" stroke="%r" stroke-width="6"/></svg>'),
 "sheet": ('<svg width="110" height="96" viewBox="0 0 110 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M14 12 C 40 8, 78 10, 96 13 L 98 82 C 70 86, 36 85, 12 82 Z"/>'
   '<path d="M13 36 C 42 33, 74 34, 97 36"/><path d="M13 59 C 42 57, 74 58, 97 59"/>'
   '<path d="M42 13 C 41 38, 42 62, 42 83"/><path d="M70 13 C 71 38, 70 62, 71 83"/></svg>'),
 "person": ('<svg width="96" height="96" viewBox="0 0 96 96" fill="none" stroke="%g" stroke-width="4" stroke-linecap="round">'
   '<circle cx="48" cy="26" r="13"/><path d="M48 40 C 47 58, 48 66, 48 70"/>'
   '<path d="M48 48 C 36 54, 30 60, 24 68"/><path d="M48 48 C 60 54, 66 60, 74 66"/>'
   '<path d="M48 70 C 42 78, 38 84, 34 90"/><path d="M48 70 C 54 78, 58 84, 62 90"/>'
   '<path d="M74 62 C 80 58, 84 52, 86 46" stroke="%y"/></svg>'),
 "plant": ('<svg width="100" height="96" viewBox="0 0 100 96" fill="none" stroke="%g" stroke-width="4" stroke-linecap="round">'
   '<path d="M50 90 C 49 70, 50 58, 50 48"/>'
   '<path d="M50 56 C 38 50, 30 40, 30 28 C 42 30, 50 38, 50 50"/>'
   '<path d="M50 48 C 62 42, 70 32, 70 20 C 58 22, 50 32, 50 44"/>'
   '<path d="M28 90 C 42 86, 60 86, 74 90" stroke="#b8865a"/><path d="M32 90 L 36 74 M70 90 L 66 74" stroke="#b8865a"/></svg>'),
 "clock": ('<svg width="96" height="96" viewBox="0 0 96 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M48 10 C 70 9, 86 26, 87 46 C 88 68, 70 86, 48 86 C 26 87, 9 68, 10 47 C 11 27, 27 11, 48 10 Z"/>'
   '<path d="M48 26 C 48 36, 48 42, 48 48 L 64 58" stroke="%r" stroke-width="5"/></svg>'),
 "gear": ('<svg width="96" height="96" viewBox="0 0 96 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<circle cx="48" cy="48" r="16"/><circle cx="48" cy="48" r="6"/>'
   '<path d="M48 22 L 48 12 M48 74 L 48 84 M22 48 L 12 48 M74 48 L 84 48 M30 30 L 23 23 M66 66 L 73 73 M66 30 L 73 23 M30 66 L 23 73"/></svg>'),
 "mail": ('<svg width="104" height="96" viewBox="0 0 104 84" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M12 16 C 40 13, 68 13, 92 16 L 93 68 C 66 71, 38 70, 11 68 Z"/>'
   '<path d="M13 18 C 27 32, 40 42, 52 48 C 64 42, 78 31, 91 18"/></svg>'),
 "paper": ('<svg width="88" height="96" viewBox="0 0 88 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M16 8 C 36 6, 54 7, 72 8 L 73 88 C 54 90, 34 90, 15 88 Z"/>'
   '<path d="M26 28 L 62 28 M26 44 L 62 45 M26 60 L 50 61" stroke="%g"/></svg>'),
 "bot": ('<svg width="96" height="96" viewBox="0 0 96 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M20 34 C 38 30, 60 30, 76 34 L 78 74 C 58 78, 38 78, 18 74 Z"/>'
   '<circle cx="36" cy="52" r="4" fill="%b"/><circle cx="62" cy="52" r="4" fill="%b"/>'
   '<path d="M38 64 C 44 68, 54 68, 60 64" stroke="%g"/><path d="M48 32 L 48 20 M48 18 C 51 15, 55 17, 53 21"/></svg>'),
 "question": ('<svg width="80" height="96" viewBox="0 0 80 96" fill="none" stroke="%y" stroke-width="5" stroke-linecap="round">'
   '<path d="M20 30 C 20 16, 34 10, 44 14 C 56 18, 58 32, 48 40 C 42 45, 40 50, 40 58"/>'
   '<circle cx="40" cy="76" r="4" fill="%y"/></svg>'),
 "yen": ('<svg width="96" height="96" viewBox="0 0 96 96" fill="none" stroke="%y" stroke-width="4" stroke-linecap="round">'
   '<path d="M48 10 C 70 9, 86 26, 87 46 C 88 68, 70 86, 48 86 C 26 87, 9 68, 10 47 C 11 27, 27 11, 48 10 Z"/>'
   '<path d="M34 30 L 48 50 L 62 30 M48 50 L 48 72 M36 56 L 60 56 M36 64 L 60 64"/></svg>'),
 "graph_up": ('<svg width="104" height="96" viewBox="0 0 104 96" fill="none" stroke="%g" stroke-width="4" stroke-linecap="round">'
   '<path d="M14 12 C 14 40, 14 62, 14 82 C 42 84, 70 84, 92 82"/>'
   '<path d="M22 68 C 34 58, 42 62, 52 50 C 62 38, 72 36, 84 24" stroke="%r" stroke-width="5"/>'
   '<path d="M72 22 L 86 22 L 86 36" stroke="%r" stroke-width="5"/></svg>'),
 "shield_x": ('<svg width="88" height="96" viewBox="0 0 88 96" fill="none" stroke="%b" stroke-width="4" stroke-linecap="round">'
   '<path d="M44 8 C 56 12, 68 15, 78 17 C 79 44, 72 70, 44 88 C 16 70, 9 44, 10 17 C 20 15, 32 12, 44 8 Z"/>'
   '<path d="M32 34 L 56 58 M56 34 L 32 58" stroke="%r" stroke-width="6"/></svg>'),
}

ARROW = ('<svg class="arrow" width="90" height="40" viewBox="0 0 90 40" fill="none" stroke="#a58bc9"'
         ' stroke-width="5" stroke-linecap="round" stroke-linejoin="round">'
         '<path d="M6 26 C 30 14, 55 15, 76 21"/><path d="M62 10 L 78 21 L 60 29"/></svg>')

DOODLE_TPL = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Yusei+Magic&family=Zen+Maru+Gothic:wght@500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;overflow:hidden;position:relative;background:%(paper)s;
 font-family:'Yusei Magic',sans-serif;color:#3a3530}
.chip{position:absolute;top:44px;left:60px;font-family:'Zen Maru Gothic';font-weight:700;font-size:26px;
 color:%(red)s;border:3px solid %(red)s;border-radius:999px;padding:6px 26px;transform:rotate(-2deg);background:#fff}
h1{position:absolute;top:%(t_top)dpx;left:0;width:100%%;text-align:center;
 font-size:%(fs)dpx;font-weight:400;line-height:1.35;letter-spacing:.02em}
h1 .m1{background:linear-gradient(transparent 68%%, #f5c9a8 68%%, #f5c9a8 92%%, transparent 92%%)}
h1 .m2{background:linear-gradient(transparent 68%%, #bcd9b0 68%%, #bcd9b0 92%%, transparent 92%%)}
h1 .nb{white-space:nowrap}
.story{position:absolute;bottom:78px;width:100%%;display:flex;justify-content:center;gap:90px}
.beat{text-align:center;font-size:30px}
.beat svg{display:block;margin:0 auto 10px}
.arrow{align-self:center;margin-top:-40px}
.brand{position:absolute;bottom:36px;right:56px;font-family:'Zen Maru Gothic';font-weight:700;
 font-size:26px;color:%(gray)s;letter-spacing:.08em}
</style></head><body>
<div class="chip">%(chip)s</div>
<h1>%(title)s</h1>
<div class="story">%(story)s</div>
<div class="brand">NGraph ｜ AI導入の実践知</div>
</body></html>"""

CARDS_TPL = """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@500;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;overflow:hidden;position:relative;background:%(paper)s;
 font-family:'Zen Maru Gothic',sans-serif;color:%(ink)s}
h1{padding:46px 0 0;text-align:center;font-size:54px;font-weight:900;letter-spacing:.02em;white-space:nowrap}
h1 em{font-style:normal;color:%(red)s}
.grid{position:absolute;top:148px;left:70px;right:70px;display:grid;grid-template-columns:1fr 1fr;gap:24px 32px}
.card{background:#fff;border-radius:22px;padding:20px 34px;box-shadow:0 4px 14px rgba(90,70,40,.10)}
.tag{display:inline-block;font-size:22px;font-weight:700;color:#fff;border-radius:8px;padding:3px 16px;margin-bottom:10px}
.green{background:%(green)s}.yellow{background:%(yellow)s}.blue{background:%(blue)s}.red{background:%(red)s}
.card p{font-size:32px;font-weight:700;line-height:1.45}
.card p b{font-size:40px;color:%(red)s}
.asof{position:absolute;bottom:30px;left:70px;font-weight:500;font-size:24px;color:%(gray)s}
.brand{position:absolute;bottom:30px;right:56px;font-weight:700;font-size:26px;color:%(gray)s;letter-spacing:.08em}
</style></head><body>
<h1>%(title)s</h1>
<div class="grid">%(cards)s</div>
<div class="asof">%(asof)s</div>
<div class="brand">NGraph ｜ AI導入の実践知</div>
</body></html>"""

KINSOKU_HEAD = "」）】』〉》、。，．・？！ゃゅょっァィゥェォッャュョーぁぃぅぇぉ%％"
KINSOKU_TAIL = "「（【『〈《"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _advance(ch, fs, half=0.57, full=1.06):
    return fs * (half if ord(ch) < 0x2E80 else full)


def _count_lines(body, fs, box_w):
    lines, cur = 1, 0.0
    for i, ch in enumerate(body):
        w = _advance(ch, fs)
        if cur + w > box_w:
            lines += 1
            cur = w
            if ch in KINSOKU_HEAD or (i and body[i - 1] in KINSOKU_TAIL):
                cur += _advance(ch, fs)
        else:
            cur += w
    return lines


def strip_marks(s):
    for t in ("{m1}", "{/m1}", "{m2}", "{/m2}", "{nb}", "{/nb}", "{b}", "{/b}", "{br}"):
        s = s.replace(t, "")
    return s


def marks_to_html(s):
    s = esc(s)
    for t, o in (("{m1}", '<span class="m1">'), ("{/m1}", "</span>"),
                 ("{m2}", '<span class="m2">'), ("{/m2}", "</span>"),
                 ("{nb}", '<span class="nb">'), ("{/nb}", "</span>"), ("{br}", "<br>"),
                 ("{b}", "<b>"), ("{/b}", "</b>")):
        s = s.replace(t, o)
    return s


# ---- doodle ------------------------------------------------------------------
# タイトルは中央寄せ・実効幅1080px・最大2行。一覧の縮小表示で読める下限は56pt。
D_BOX_W, D_FS_MAX, D_FS_MIN, D_LEGIBLE = 1080, 76, 44, 56
# 2行時はコマ絵と近づくのでタイトルを上に寄せる
D_TOP_1LINE, D_TOP_2LINE = 170, 120


def _width(s, fs):
    return sum(_advance(c, fs) for c in s)


def _split_at_nth_toten(marked, n):
    """マーク付きタイトルを、n個目の読点・句点の直後で2行に割る（マーク内に読点は無い前提）。"""
    seen = -1
    for i, ch in enumerate(marked):
        if ch in "、。":
            seen += 1
            if seen == n:
                return marked[:i + 1] + "{br}" + marked[i + 1:]
    return marked


def fit_doodle(title):
    """級数と改行位置を決める。単語の途中で折らない（2026-09-01初回生成の実事故）。

    優先順位: ①1行で入る最大級数 ②読点・句点で割った2行 ③明示{br} ④どれも無理ならエラー。
    貪欲折り返し任せの2行は「止まってい／た理由」のような途中折れになるので採用しない。
    戻り値: (fs, 行数, {br}を埋めたタイトル)
    """
    body = strip_marks(title.replace("{br}", ""))
    # ①1行
    for fs in range(D_FS_MAX, D_LEGIBLE - 1, -1):
        if _width(body, fs) <= D_BOX_W:
            return fs, 1, title.replace("{br}", "")
    # ③明示{br}（書いた位置を尊重して検査だけする）
    if "{br}" in title:
        parts = [strip_marks(p) for p in title.split("{br}")]
        if len(parts) != 2:
            print("ERROR: {br} は1個だけ。")
            sys.exit(3)
        for fs in range(D_FS_MAX, D_LEGIBLE - 1, -1):
            if all(_width(p, fs) <= D_BOX_W for p in parts):
                return fs, 2, title
        print("ERROR: {br} で割っても収まりません。文言を短くしてください。")
        sys.exit(3)
    # ②読点・句点で割る（両行が収まる中で級数最大→行バランス最良）
    puncts = [i for i, ch in enumerate(body) if ch in "、。"]
    for fs in range(D_FS_MAX, D_LEGIBLE - 1, -1):
        best = None
        for n, i in enumerate(puncts):
            w1, w2 = _width(body[:i + 1], fs), _width(body[i + 1:], fs)
            if w1 <= D_BOX_W and w2 <= D_BOX_W:
                score = max(w1, w2)
                if best is None or score < best[0]:
                    best = (score, n)
        if best:
            return fs, 2, _split_at_nth_toten(title, best[1])
    print("ERROR: タイトルが収まりません。短くするか、折り位置に読点を入れるか、"
          "{br} で折り位置を指定してください（いま%d文字）。" % len(body))
    sys.exit(3)


def gen_doodle(slug, title, chip, beats_arg):
    beats = [b.strip() for b in beats_arg.split(",") if b.strip()]
    if len(beats) != 3:
        print("ERROR: --beats はちょうど3コマ（icon:caption をカンマ区切り）。いま%d個。" % len(beats))
        sys.exit(3)
    story = []
    for i, b in enumerate(beats):
        icon, _, cap = b.partition(":")
        if icon not in ICONS:
            print("ERROR: 不明なコマ絵 '%s'。使えるもの: %s" % (icon, "/".join(sorted(ICONS))))
            sys.exit(3)
        if len(cap) > 10:
            print("ERROR: コマ%dのキャプション「%s」が%d文字（上限10）。" % (i + 1, cap, len(cap)))
            sys.exit(3)
        svg = (ICONS[icon].replace("%b", BLUE).replace("%r", RED)
               .replace("%g", GREEN).replace("%y", YELLOW))
        if i:
            story.append(ARROW)
        story.append('<div class="beat">%s%s</div>' % (svg, esc(cap)))
    if len(chip) > 14:
        print("ERROR: チップ「%s」が%d文字（上限14）。" % (chip, len(chip)))
        sys.exit(3)
    fs, nlines, title = fit_doodle(title)
    html = DOODLE_TPL % {
        "paper": PAPER, "red": RED, "gray": GRAY, "fs": fs,
        "t_top": D_TOP_2LINE if nlines > 1 else D_TOP_1LINE,
        "chip": esc(chip), "title": marks_to_html(title), "story": "".join(story)}
    return html, fs


# ---- cards -------------------------------------------------------------------
# タイトルは1行固定（幅1080px）。カード本文は実効幅446px・2行固定。
C_TITLE_W, C_TITLE_FS = 1080, 54
C_CARD_W, C_CARD_FS, C_CARD_BFS = 446, 32, 40
CARD_COLORS = ("green", "yellow", "blue", "red")


def _card_line_w(line):
    w, i, bold = 0.0, 0, False
    while i < len(line):
        if line.startswith("{b}", i):
            bold, i = True, i + 3
            continue
        if line.startswith("{/b}", i):
            bold, i = False, i + 4
            continue
        fs = C_CARD_BFS if bold else C_CARD_FS
        w += _advance(line[i], fs, half=0.55, full=1.02)
        i += 1
    return w


def gen_cards(slug, title, cards_arg, asof):
    body = strip_marks(title.replace("{em}", "").replace("{/em}", ""))
    tw = sum(_advance(c, C_TITLE_FS, half=0.55, full=1.04) for c in body)
    if tw > C_TITLE_W:
        over = int((tw - C_TITLE_W) / (C_TITLE_FS * 1.04)) + 1
        print("ERROR: タイトルが1行に収まりません（あと%d文字ほど削る）。" % over)
        sys.exit(3)
    if len(cards_arg) != 4:
        print("ERROR: --card はちょうど4枚。いま%d枚。" % len(cards_arg))
        sys.exit(3)
    cards = []
    for i, c in enumerate(cards_arg):
        parts = c.split("|")
        if len(parts) != 4:
            print("ERROR: カード%d「%s」の形式はタグ|色|1行目|2行目。" % (i + 1, c))
            sys.exit(3)
        tag, color, l1, l2 = parts
        if color not in CARD_COLORS:
            print("ERROR: カード%dの色 '%s'。使えるもの: %s" % (i + 1, color, "/".join(CARD_COLORS)))
            sys.exit(3)
        for ln in (l1, l2):
            if _card_line_w(ln) > C_CARD_W:
                print("ERROR: カード%dの行「%s」が幅に収まりません。短くしてください。" % (i + 1, strip_marks(ln)))
                sys.exit(3)
        cards.append('<div class="card"><span class="tag %s">%s</span><p>%s<br>%s</p></div>'
                     % (color, esc(tag), marks_to_html(l1), marks_to_html(l2)))
    title_html = esc(title).replace("{em}", "<em>").replace("{/em}", "</em>")
    html = CARDS_TPL % {
        "paper": PAPER, "ink": INK, "red": RED, "green": GREEN, "yellow": YELLOW,
        "blue": BLUE, "gray": GRAY,
        "title": title_html, "cards": "".join(cards), "asof": esc(asof)}
    return html, C_TITLE_FS


# ---- 共通: 描画と記録（eyecatch_gen.py と同じ仕組み・同じ記録先） ----------------
def render(slug, html, out_override):
    tmp = tempfile.mkdtemp(prefix="eyecatch2_")
    hp = os.path.join(tmp, slug + ".html")
    open(hp, "w", encoding="utf-8").write(html)
    png = os.path.join(tmp, slug + ".png")
    udd = tempfile.mkdtemp(prefix="eyecatch2_udd_")
    subprocess.run([EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--window-size=1200,630", "--user-data-dir=" + udd,
                    "--hide-scrollbars", "--virtual-time-budget=8000",
                    "--screenshot=" + png, "file:///" + hp.replace("\\", "/")],
                   capture_output=True)
    for _ in range(10):
        if os.path.exists(png) and os.path.getsize(png) > 10000:
            break
        time.sleep(1)
    if not os.path.exists(png) or os.path.getsize(png) <= 10000:
        print("ERROR: Edge screenshot failed:", png)
        sys.exit(2)
    from PIL import Image
    im = Image.open(png).convert("RGB")
    out = out_override or os.path.join(OUT, slug + ".jpg")
    im.save(out, "JPEG", quality=86)
    return out, im.size


def record(slug, title, sub, pattern, fs):
    import json
    import re
    path = os.path.join(OUT, "_eyecatch.json")
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:
        data = {}
    h1 = None
    art = os.path.join(ROOT, "blog", slug + ".html")
    if os.path.exists(art):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", open(art, encoding="utf-8").read(), re.S)
        if m:
            h1 = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    data[slug] = {"title": title, "sub": sub, "pattern": pattern, "fs": fs, "article_h1": h1}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ("doodle", "cards"):
        print(__doc__)
        sys.exit(1)
    mode, slug, title = sys.argv[1], sys.argv[2], sys.argv[3]
    chip, beats, asof, out_override = "現場の顛末記", None, "", None
    cards = []
    for a in sys.argv[4:]:
        if a.startswith("--chip="):
            chip = a[7:]
        elif a.startswith("--beats="):
            beats = a[8:]
        elif a.startswith("--card="):
            cards.append(a[7:])
        elif a.startswith("--asof="):
            asof = a[7:]
        elif a.startswith("--out="):
            out_override = a[6:]
    if mode == "doodle":
        if not beats:
            print("ERROR: doodle には --beats= が必須。")
            sys.exit(1)
        html, fs = gen_doodle(slug, title, chip, beats)
        sub = chip
    else:
        if not asof:
            print("ERROR: cards には --asof=（時点の明記）が必須。実測主義の一部。")
            sys.exit(1)
        html, fs = gen_cards(slug, title, cards, asof)
        sub = asof
    out, size = render(slug, html, out_override)
    if not out_override:
        record(slug, strip_marks(title), sub, mode, fs)
    print("OK", out, size)


if __name__ == "__main__":
    main()
