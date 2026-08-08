# -*- coding: utf-8 -*-
"""ブログ記事アイキャッチ生成（和禅テンプレ・1200x630）
使い方:
  python scripts/eyecatch_gen.py <slug> <title> <sub> <pattern> [--label=NGRAPH BLOG] [--out=絶対パス.jpg]
  pattern: tree_down/tree_up/radial/seq/pyramid/venn/ring/cycle/balance/shield/layers/steps/fork/gauge
           /split/deadline/blocked
  型の選び方（BLOG-OPS §10 が正本）:
    分解・要因=tree_down / 集約=tree_up / ハブ・接続=radial / 手順・フロー=seq
    階層・優先順位=pyramid / 重なり・共通点=venn / 構成要素の一覧=ring / 循環=cycle
    対比・vs・乗り換え判断=balance / セキュリティ・権限・リスク=shield
    データ基盤・記憶・蓄積=layers / 補助金申請・段階導入=steps
    対象/対象外の線引き=fork / 価格・単価・倍率・実測検証=gauge
    集計がズレる・数字が2つに割れる=split / 締切・公募・期限=deadline
    止まる・使われない・定着しない=blocked
  title内で改行禁止にしたい語は {nb}...{/nb} で囲む（例: "AIが現場で止まる、{nb}3つの理由{/nb}"）
出力: 既定 assets/blog/<slug>.jpg（--outで任意パスに変更可）
生成後は必ず画像を目視確認すること（単語中改行・見切れ）。
"""
import sys, os, subprocess, tempfile, time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "blog")
os.makedirs(OUT, exist_ok=True)

PATS = {
 "tree_down": '<path d="M24 15v7M24 22H9v6M24 22h15v6M24 22v6"/><circle cx="24" cy="10" r="5"/><circle cx="9" cy="32" r="4.5"/><circle cx="24" cy="32" r="4.5"/><circle cx="39" cy="32" r="4.5"/>',
 "tree_up": '<path d="M24 33v-7M24 26H9v-6M24 26h15v-6M24 26v-6"/><circle cx="24" cy="38" r="5"/><circle cx="9" cy="16" r="4.5"/><circle cx="24" cy="16" r="4.5"/><circle cx="39" cy="16" r="4.5"/>',
 "radial": '<path d="M24 18.5V9M28.7 21l8.5-5M28.7 27l8.5 5M24 29.5V39M19.3 27l-8.5 5M19.3 21l-8.5-5"/><circle cx="24" cy="24" r="5.5"/><circle cx="24" cy="7" r="2.8"/><circle cx="39" cy="14.5" r="2.8"/><circle cx="39" cy="33.5" r="2.8"/><circle cx="24" cy="41" r="2.8"/><circle cx="9" cy="33.5" r="2.8"/><circle cx="9" cy="14.5" r="2.8"/>',
 "seq": '<circle cx="7" cy="24" r="4.5"/><path d="M13 24h4.5M15 21.5l2.5 2.5-2.5 2.5M25 17.5l6.5 6.5-6.5 6.5-6.5-6.5zM33 24h4.5M35 21.5l2.5 2.5-2.5 2.5M40 20h8v8h-8z"/>',
 "pyramid": '<path d="M24 7l6 8.5H18zM15.5 20h17l5 8.5h-27zM8 33h32l5 8.5H3z"/>',
 "venn": '<circle cx="18" cy="19" r="10.5"/><circle cx="30" cy="19" r="10.5"/><circle cx="24" cy="29.5" r="10.5"/>',
 "ring": '<circle cx="24" cy="8" r="3.6"/><circle cx="37.9" cy="16" r="3.6"/><circle cx="37.9" cy="32" r="3.6"/><circle cx="24" cy="40" r="3.6"/><circle cx="10.1" cy="32" r="3.6"/><circle cx="10.1" cy="16" r="3.6"/>',
 "cycle": '<path d="M37.5 18a15 15 0 00-25-4.5M12.5 13.5V7M12.5 13.5H19M10.5 30a15 15 0 0025 4.5M35.5 34.5V41M35.5 34.5H29"/>',
 "balance": '<path d="M24 8v30M10 14h28M10 14l-4 8M10 14l4 8M38 14l-4 8M38 14l4 8M6 22a4 4 0 008 0M34 22a4 4 0 008 0M14 38h20"/>',
 "shield": '<path d="M24 6l14 5v12c0 10-6 16-14 19-8-3-14-9-14-19V11z"/><path d="M24 13v25"/>',
 "layers": '<path d="M24 26l14 7-14 7-14-7zM24 17l14 7-14 7-14-7zM24 8l14 7-14 7-14-7z"/>',
 "steps": '<path d="M6 38h10v-8h10v-8h10v-8h6"/><circle cx="42" cy="10" r="2.5"/>',
 "fork": '<path d="M4 24h12M24 21l12-8M24 27l12 8"/><circle cx="20" cy="24" r="4.5"/><circle cx="36" cy="13" r="3.2"/><circle cx="36" cy="35" r="3.2" stroke-dasharray="1.1 1.3"/>',
 "gauge": '<path d="M8 34a16 16 0 0 1 32 0M11 27l-3 2M24 18v-4M37 27l3 2M24 34L34 24"/><circle cx="24" cy="34" r="2.5"/>',
 # 同じ対象なのに数字が2つ出る（集計のズレ）。fork（対象/対象外の線引き）と違い、両方とも実在する
 "split": '<path d="M9 9v30M9 19h29M9 31h17"/><circle cx="38" cy="19" r="3.4"/><circle cx="26" cy="31" r="3.4"/>',
 # 締切・公募・期限。丸を付けた1日が主役
 "deadline": '<path d="M8 12h32v28H8zM8 20h32M16 7v8M32 7v8"/><circle cx="31" cy="30" r="5"/>',
 # 流れが途中で止まる（使われない・定着しない・詰まる）。破線＝起きるはずだったのに起きていない側
 "blocked": '<path d="M5 24h13M14.5 20.5l3.5 3.5-3.5 3.5M24 10v28"/><path d="M30 24h12M38.5 20.5l3.5 3.5-3.5 3.5" stroke-dasharray="1.1 1.3"/>',
}

TPL = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:1200px;height:630px;overflow:hidden;position:relative;
 background:#f6f2e9;
 background-image:radial-gradient(ellipse 900px 500px at 88%% 12%%, rgba(166,58,36,.05), transparent 60%%),radial-gradient(ellipse 700px 480px at 8%% 95%%, rgba(60,52,42,.05), transparent 60%%);
 font-family:'Zen Kaku Gothic New',sans-serif;color:#2b2620}
.frame{position:absolute;inset:26px;border:1px solid rgba(166,58,36,.28)}
.frame::after{content:"";position:absolute;inset:6px;border:1px solid rgba(60,52,42,.10)}
.txt{position:absolute;left:112px;top:50%%;transform:translateY(-56%%);width:566px;border-left:5px solid #a63a24;padding-left:30px}
.label{font-size:19px;letter-spacing:.42em;color:#a63a24;font-weight:700;margin-bottom:24px}
.title{font-family:'Zen Old Mincho',serif;font-weight:900;font-size:%(fs)dpx;line-height:1.34;letter-spacing:.02em;color:#2b2620;margin-bottom:26px}
.sub{width:566px;font-size:24px;line-height:1.75;color:#5c544a}
.title .nb{white-space:nowrap}
.brand{position:absolute;left:112px;bottom:78px;display:flex;align-items:baseline;gap:18px}
.brand .n{font-family:'Zen Old Mincho',serif;font-size:30px;font-weight:700;letter-spacing:.12em}
.brand .n i{font-style:normal;color:#a63a24}
.brand .u{font-size:19px;color:#8a8172;letter-spacing:.06em}
.pat{position:absolute;right:64px;top:50%%;transform:translateY(-50%%)}
.pat svg{width:400px;height:400px;fill:none;stroke:#3c342a;stroke-width:1.5;stroke-linecap:round;stroke-linejoin:round;opacity:.5}
.pat .hl{position:absolute;inset:0;display:flex}
.pat .hl svg{stroke:#a63a24;opacity:.55;clip-path:inset(0 0 62%% 0)}
.hanko{position:absolute;right:88px;bottom:74px;width:58px;height:58px;border:2px solid #a63a24;border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:'Zen Old Mincho',serif;font-size:30px;font-weight:900;color:#a63a24;opacity:.85}
</style></head><body>
<div class="frame"></div>
<div class="pat"><svg viewBox="0 0 48 48">%(pat)s</svg><div class="hl"><svg viewBox="0 0 48 48">%(pat)s</svg></div></div>
<div class="txt"><div class="label">NGRAPH BLOG</div>
<div class="title">%(title)s</div>
<div class="sub">%(sub)s</div></div>
<div class="brand"><span class="n">NGraph<i>.</i></span><span class="u">ngraph.jp — AI導入伴走支援</span></div>
<div class="hanko">構</div>
</body></html>"""

EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# テキスト枠は右端708px、図案は左端736px。枠が重ならないよう幅を566pxに絞ったので、
# 長いタイトルは級数を落とさないと行数が増えて縦にはみ出す。文字数から級数を決める。
# （2026-08-08: 旧設定は枠が136px重なっており、47枚中12枚で本文が図案を突き抜けていた）
# .txt は width:566px だが box-sizing:border-box なので、
# 実際に文字が流れる幅は 566 − padding-left 30 − border-left 5 = 531px。
# ここを566のまま計算していて、1文字あふれて3行になる回が出た（2026-08-08）。
BOX_W = 531
FS_MAX, FS_MIN = 68, 40


MAX_LINES = 2
# 行頭に置けない文字（禁則）。ここに当たると1文字前の行へ送られるので、
# 掛け算で級数を決めると必ず読み違える。実際に折り返しを回して数える。
KINSOKU_HEAD = "」）】』〉》、。，．・？！ゃゅょっァィゥェォッャュョーぁぃぅぇぉ%％"
KINSOKU_TAIL = "「（【『〈《"


def _advance(ch, fs):
    return fs * 0.57 if ord(ch) < 0x2E80 else fs * 1.04  # 1.02em + letter-spacing .02em


def _count_lines(body, fs):
    """禁則を考慮した貪欲な折り返しで行数を数える。"""
    lines, cur = 1, 0.0
    for i, ch in enumerate(body):
        w = _advance(ch, fs)
        if cur + w > BOX_W:
            # 次の文字が行頭禁則、または今の文字が行末禁則なら1文字ぶん余計に送る
            lines += 1
            cur = w
            if ch in KINSOKU_HEAD or (i and body[i - 1] in KINSOKU_TAIL):
                cur += _advance(ch, fs)
        else:
            cur += w
    return lines


def fit_font_size(title):
    """MAX_LINES 行に収まる最大の級数を返す（1文字だけ残る行を作らない）。"""
    body = title.replace("{nb}", "").replace("{/nb}", "")
    if not body:
        return FS_MAX
    for fs in range(FS_MAX, FS_MIN - 1, -1):
        if _count_lines(body, fs) <= MAX_LINES:
            return fs
    n = _count_lines(body, FS_MIN)
    if n > MAX_LINES:
        print("ERROR: タイトルが長すぎて%d行に収まりません（最小級数%dptでも%d行）。"
              "タイトルを短くしてください。" % (MAX_LINES, FS_MIN, n))
        sys.exit(3)
    return FS_MIN


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)
    slug, title, sub, pat = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    label, out_override = "NGRAPH BLOG", None
    for a in sys.argv[5:]:
        if a.startswith("--label="):
            label = a[8:]
        elif a.startswith("--out="):
            out_override = a[6:]
    if pat not in PATS:
        print("unknown pattern:", pat, "->", "/".join(PATS))
        sys.exit(1)
    title_html = esc(title).replace("{nb}", '<span class="nb">').replace("{/nb}", "</span>")
    html = TPL % {"title": title_html, "sub": esc(sub), "pat": PATS[pat], "fs": fit_font_size(title)}
    html = html.replace(">NGRAPH BLOG<", ">" + esc(label) + "<")
    tmp = tempfile.mkdtemp(prefix="eyecatch_")
    hp = os.path.join(tmp, slug + ".html")
    open(hp, "w", encoding="utf-8").write(html)
    png = os.path.join(tmp, slug + ".png")
    udd = tempfile.mkdtemp(prefix="eyecatch_udd_")
    subprocess.run([EDGE, "--headless=new", "--no-sandbox", "--disable-gpu", "--window-size=1200,630",
                    "--user-data-dir=" + udd,
                    "--hide-scrollbars", "--virtual-time-budget=8000",
                    "--screenshot=" + png, "file:///" + hp.replace("\\", "/")],
                   capture_output=True)
    for _ in range(10):
        if os.path.exists(png) and os.path.getsize(png) > 10000:
            break
        time.sleep(1)
    if not os.path.exists(png) or os.path.getsize(png) <= 10000:
        print("ERROR: Edge screenshot failed. Run the Edge command manually from bash:")
        print(f'"{EDGE}" --headless=new --disable-gpu --window-size=1200,630 --hide-scrollbars --virtual-time-budget=8000 --screenshot={png} file:///{hp}')
        sys.exit(2)
    from PIL import Image
    im = Image.open(png).convert("RGB")
    out = out_override or os.path.join(OUT, slug + ".jpg")
    im.save(out, "JPEG", quality=86)
    print("OK", out, im.size)


if __name__ == "__main__":
    main()
