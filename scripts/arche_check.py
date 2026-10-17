#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""アルケー（ngraph.jp/cases/）の書き出しが、元ソースと揃っているかを見る。

なぜ作ったか（2026-10-17）:
  /cases/ は元のアルケー画面（C:/dev/autowrite）のソースを _arche/src/orig/ に複写し、
  _arche/build.mjs で静的HTMLに書き出している。複写だけ直して作り直さない、
  作り直したのに sitemap が古い、元（autowrite）が変わったのに複写が古い、を止める。

検査:
  NG  _arche/src/orig/ の中身と、cases/ を書き出したときの指紋（cases/_assets/build.json）が違う
  NG  cases/ のページが読む JS/CSS が cases/_assets/ に無い
  NG  sitemap.xml の /cases/ のURLと、cases/ のページの集合が違う
  WARN 元（autowrite）のソースと複写が違う（autowrite が手元にあるときだけ）

直し方: cd _arche && npm run sync && npm run build → python scripts/sync_chrome.py
"""
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, "_arche", "src", "orig")
CASES = os.path.join(ROOT, "cases")
STAMP = os.path.join(CASES, "_assets", "build.json")
SYNC = os.path.join(ROOT, "_arche", "sync.mjs")
AUTOWRITE_SRC = "C:/dev/autowrite/src"


def orig_hash():
    h = hashlib.sha256()
    for f in sorted(os.listdir(ORIG)):
        h.update(f.encode("utf-8"))
        # 改行は LF に揃える（build.mjs と同じ。git の autocrlf で CRLF になっても指紋は同じ）
        with open(os.path.join(ORIG, f), "rb") as fp:
            h.update(fp.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def main():
    if not os.path.isdir(CASES):
        print("OK: cases/ が無い（アルケー未公開）")
        return 0
    ng, warn = [], []

    with open(STAMP, encoding="utf-8") as f:
        stamp = json.load(f)
    if stamp.get("orig_sha256") != orig_hash():
        ng.append("_arche/src/orig/ を直した後に作り直していない（npm run build）")

    pages = []
    assets = set(os.listdir(os.path.join(CASES, "_assets")))
    for d, _, files in os.walk(CASES):
        if "index.html" not in files or "_assets" in d:
            continue
        rel = os.path.relpath(d, CASES).replace("\\", "/")
        pages.append("/cases/" if rel == "." else f"/cases/{rel}/")
        with open(os.path.join(d, "index.html"), encoding="utf-8") as fp:
            for ref in re.findall(r'/cases/_assets/([^"\s)]+)', fp.read()):
                if ref not in assets:
                    ng.append(f"{rel}/index.html が読む _assets/{ref} が無い")
    with open(os.path.join(ROOT, "sitemap.xml"), encoding="utf-8") as fp:
        sm = set(re.findall(r"<loc>https://ngraph\.jp(/cases/[^<]*)</loc>", fp.read()))
    if sm != set(pages):
        ng.append(f"sitemap.xml の /cases/ が書き出しと違う（sitemapだけ{len(sm - set(pages))}件・ページだけ{len(set(pages) - sm)}件）")

    if os.path.isdir(AUTOWRITE_SRC):
        with open(SYNC, encoding="utf-8") as fp:
            pairs = re.findall(r'"([^"]+\.tsx?)":\s*"([^"]+)"', fp.read())
        with open(os.path.join(ROOT, "_arche", "patches.json"), encoding="utf-8") as fp:
            patches = json.load(fp)
        for src, dst in pairs:
            a, b = os.path.join(AUTOWRITE_SRC, src), os.path.join(ORIG, dst)
            if not (os.path.exists(a) and os.path.exists(b)):
                continue
            with open(a, encoding="utf-8", newline="") as x:
                text = x.read().replace("\r\n", "\n")
            # sync.mjs と同じ手順で patches.json を当ててから比べる
            for p in (p for p in patches if p["file"] == dst):
                i = text.find(p["start"])
                j = -1 if i < 0 else text.find(p["end"], i)
                if i < 0 or j < 0:
                    warn.append(f"patches.json が元の {src} に当たらない（元が変わった）: {p['why']}")
                    break
                text = text[:i] + p["replace"] + text[j + len(p["end"]):]
            with open(b, encoding="utf-8", newline="") as y:
                if y.read().replace("\r\n", "\n") != text:
                    warn.append(f"元の {src} が複写と違う（取り込むなら npm run sync && npm run build）")

    for w in warn:
        print("WARN:", w)
    if ng:
        print(f"アルケー（cases/）のズレ {len(ng)}件")
        for n in ng[:15]:
            print("  -", n)
        return 1
    print(f"OK: アルケー（cases/）は元ソース・sitemap と一致（{len(pages)}ページ）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
