# -*- coding: utf-8 -*-
"""ブログ記事アイキャッチ生成（和禅テンプレ・1200x630）
使い方:
  python scripts/eyecatch_gen.py <slug> <title> <sub> <pattern> [--label=NGRAPH BLOG] [--out=絶対パス.jpg]
  pattern: tree_down/tree_up/radial/seq/pyramid/venn/ring/cycle
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
.txt{position:absolute;left:112px;top:50%%;transform:translateY(-56%%);width:730px;border-left:5px solid #a63a24;padding-left:30px}
.label{font-size:19px;letter-spacing:.42em;color:#a63a24;font-weight:700;margin-bottom:24px}
.title{font-family:'Zen Old Mincho',serif;font-weight:900;font-size:68px;line-height:1.34;letter-spacing:.02em;color:#2b2620;margin-bottom:26px}
.sub{width:640px;font-size:24px;line-height:1.75;color:#5c544a}
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
    html = TPL % {"title": title_html, "sub": esc(sub), "pat": PATS[pat]}
    html = html.replace(">NGRAPH BLOG<", ">" + esc(label) + "<")
    tmp = tempfile.mkdtemp(prefix="eyecatch_")
    hp = os.path.join(tmp, slug + ".html")
    open(hp, "w", encoding="utf-8").write(html)
    png = os.path.join(tmp, slug + ".png")
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--window-size=1200,630",
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
