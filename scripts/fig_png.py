# -*- coding: utf-8 -*-
"""記事内の概念図（.a-fig-wrap）を単体PNGで書き出す（X添付・note再掲用）
使い方:
  python scripts/fig_png.py <slug> [図の番号(0始まり・既定0)] [--w=1200] [--h=675] [--out=絶対パス.png]
出力: 既定 assets/blog/fig/<slug>-fig<N>.png
用途: Xに図だけを貼る／noteに図を差し込む。本文テキストごとスクショすると
      スマホで潰れて読めないので、図だけを切り出す。
生成後は必ず画像を目視確認すること（見切れ・改行）。
"""
import sys, os, re, subprocess, tempfile, time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

TPL = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{width:%(w)dpx;height:%(h)dpx;overflow:hidden;display:flex;align-items:center;justify-content:center;
 background:#f6f2e9;font-family:'Zen Kaku Gothic New',sans-serif;color:#2b2620}
.frame{position:absolute;inset:22px;border:1px solid rgba(166,58,36,.24);pointer-events:none}
.box{width:%(inner)dpx;padding:0 10px}
.a-fig-title{font-family:'Zen Old Mincho',serif;font-size:30px;font-weight:800;color:#2b2620;
 margin-bottom:24px;padding-left:16px;border-left:5px solid #a63a24;line-height:1.4}
svg{width:100%%;height:auto;display:block}
.a-fig-cap{margin-top:20px;font-size:15px;line-height:1.7;color:#5c544a}
.brand{position:absolute;right:44px;bottom:34px;font-family:'Zen Old Mincho',serif;
 font-size:19px;font-weight:700;letter-spacing:.1em;color:#8a8172}
.brand i{font-style:normal;color:#a63a24}
</style></head><body>
<div class="frame"></div>
<div class="box">%(fig)s</div>
<div class="brand">NGraph<i>.</i> ngraph.jp</div>
</body></html>"""


def extract(slug, idx):
    path = os.path.join(ROOT, "blog", slug if slug.endswith(".html") else slug + ".html")
    if not os.path.exists(path):
        sys.exit("記事が見つからない: " + path)
    html = open(path, encoding="utf-8").read()
    figs = re.findall(r'<div class="a-fig-wrap">(.*?)</div>\s*(?=<p|<h2|<h3|<div|</section)', html, re.S)
    if not figs:
        sys.exit("この記事に .a-fig-wrap が無い")
    if idx >= len(figs):
        sys.exit("図は %d 個しかない（指定: %d）" % (len(figs), idx))
    print("図の数: %d / 使う番号: %d" % (len(figs), idx))
    return figs[idx]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    if not args:
        sys.exit(__doc__)
    slug = args[0].replace(".html", "")
    idx = int(args[1]) if len(args) > 1 else 0
    w, h = int(opts.get("w", 1200)), int(opts.get("h", 675))

    fig = extract(slug, idx)
    out = opts.get("out") or os.path.join(ROOT, "assets", "blog", "fig", "%s-fig%d.png" % (slug, idx))
    os.makedirs(os.path.dirname(out), exist_ok=True)

    html = TPL % {"w": w, "h": h, "inner": int(w * 0.82), "fig": fig}
    tmp = os.path.join(tempfile.gettempdir(), "ngfig_%d.html" % int(time.time()))
    open(tmp, "w", encoding="utf-8").write(html)

    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--window-size=%d,%d" % (w, h),
                    "--hide-scrollbars", "--virtual-time-budget=6000",
                    "--screenshot=" + out, "file:///" + tmp.replace("\\", "/")], check=False)
    if os.path.exists(out):
        print("OK:", out, os.path.getsize(out), "bytes")
    else:
        sys.exit("生成に失敗した（Edgeのパスを確認）")


if __name__ == "__main__":
    main()
