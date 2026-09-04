# -*- coding: utf-8 -*-
"""表紙v3・画像生成（2026-09-04 髙橋さん「いいねこの表紙スタイルでいこうぜこれからも。まぁ一辺倒はつまらないけど」）

Gemini（nano-banana-2・C:/dev/nano-banana-2-skill）で表紙の絵を生成し、ブログ用 1200x630 と note用 1280x670 に
切り出して、`assets/blog/_eyecatch.json` に pattern=visual-gen で記録する（eyecatch_check.py はこの型を
「全面イラスト＝テキスト枠と図案の分離が無い」として扱う）。

使い方:
  python scripts/eyecatch_ai.py <slug> --prompt "<英語プロンプト>" [--ref 参照画像 ...] [--model flash|pro]
        [--title "<表紙に描かせた主張・記録用>"] [--h1 "<記事h1>"] [--note] [--sub "<記録用メモ>"]
  python scripts/eyecatch_ai.py <slug> --from 既存.jpeg [--note] ...   # 生成せず切り出し＋記録だけ（無料）

型（毎回同じにしない・混ぜる）:
  - 地は和紙（#f6f2e9）×墨（#2b2620）×朱（#a63a24）を基調にしつつ、モチーフは記事ごとに変える
  - 製品名が主役なら公式ロゴを --ref で渡す（simple-icons の形状を PNG にしたもの。例: kit11/mark_anthropic.png, mark_openai.png）
  - 文字は製品名・数字だけ（長文はAIが崩す）。文言の検査は目視（gate.py が表紙の文言と記事h1を並べて出す）
  - 生成後は必ず Read で目視。ロゴの崩れ・余計な文字・人物が出たら作り直す（1枚 ~$0.12〜0.17）
"""
import argparse, io, json, os, subprocess, sys, tempfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUN = r"C:\Users\shing\AppData\Roaming\npm\bun.cmd"
CLI = r"C:\dev\nano-banana-2-skill\src\cli.ts"
RECORD = os.path.join(ROOT, "assets", "blog", "_eyecatch.json")
NOTE_COVERS = r"C:\dev\lion-enterprise\note\covers"

STYLE = ("Flat vector editorial illustration, clean and minimal. Background: warm off-white Japanese washi paper (#f6f2e9) "
         "with a thin vermilion (#a63a24) double frame near the edges and subtle ink-wash gradients. Ink (#2b2620) and vermilion accents. "
         "No glow, no neon, no anime, no people unless asked. Wide 16:9 composition with generous margins. ")


def crop_to(src, w, h, out, q=88):
    im = Image.open(src).convert("RGB")
    sw, sh = im.size
    nh = int(sh * w / sw)
    im = im.resize((w, nh), Image.LANCZOS)
    if nh < h:
        raise SystemExit("生成画像の縦が足りない: %dx%d → %dx%d" % (sw, sh, w, nh))
    top = (nh - h) // 2
    im.crop((0, top, w, top + h)).save(out, quality=q)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--prompt")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--model", default="flash", choices=["flash", "pro"])
    ap.add_argument("--from", dest="src")
    ap.add_argument("--title", default="", help="表紙に描かせた主張（記録用。gate が記事h1と並べて出す）")
    ap.add_argument("--sub", default="", help="記録用メモ（何で生成したか等）")
    ap.add_argument("--h1", default="", help="記事h1（省略時は記事HTMLから拾う）")
    ap.add_argument("--note", action="store_true", help="note用 1280x670 も covers/ に出す")
    ap.add_argument("--no-style", action="store_true", help="STYLE 前置きを付けない")
    a = ap.parse_args()

    src = a.src
    if not src:
        if not a.prompt:
            raise SystemExit("--prompt か --from が要る")
        prompt = ("" if a.no_style else STYLE) + a.prompt
        outdir = tempfile.mkdtemp(prefix="eyecatch_ai_")
        cmd = [BUN, CLI, prompt] + sum([["--ref", os.path.abspath(r)] for r in a.ref], []) + \
              ["-s", "2K", "-a", "16:9", "--model", a.model, "-o", "gen", "-d", outdir]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
        cands = [os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("gen.")]
        if not cands:
            print(r.stdout[-600:], r.stderr[-600:])
            raise SystemExit("生成失敗")
        src = cands[0]
        print("generated:", src, "|", [l for l in r.stdout.splitlines() if "Cost" in l])

    blog_out = os.path.join(ROOT, "assets", "blog", a.slug + ".jpg")
    crop_to(src, 1200, 630, blog_out)
    print("blog eyecatch:", blog_out)
    if a.note:
        os.makedirs(NOTE_COVERS, exist_ok=True)
        note_out = os.path.join(NOTE_COVERS, a.slug + "_note.jpg")
        crop_to(src, 1280, 670, note_out, q=90)
        print("note cover:", note_out)

    h1 = a.h1
    if not h1:
        html = os.path.join(ROOT, "blog", a.slug + ".html")
        if os.path.exists(html):
            import re
            m = re.search(r"<h1>(.*?)</h1>", io.open(html, encoding="utf-8").read(), flags=re.S)
            h1 = m.group(1).strip() if m else ""
    rec = json.load(io.open(RECORD, encoding="utf-8")) if os.path.exists(RECORD) else {}
    rec[a.slug] = {"article_h1": h1, "title": a.title, "sub": a.sub or ("visual-gen: nano-banana-2 %s" % a.model),
                   "pattern": "visual-gen", "fs": 0}
    io.open(RECORD, "w", encoding="utf-8", newline="\n").write(json.dumps(rec, ensure_ascii=False, indent=1) + "\n")
    print("record: pattern=visual-gen |", a.slug)
    print("次: Read で目視 → gate.py → 表紙の文言（--title）と記事h1を並べて読む")


if __name__ == "__main__":
    main()
