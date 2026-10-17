#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""アルケー（ngraph.jp/cases/）の書き出しが、ソースと揃っているかを見る。

なぜ作ったか（2026-10-17）:
  /cases/ は _arche/src/ のソース（元は nicomachos.com のアルケー画面。2026-10-17 に
  ngraph.jp 用に分岐し、以後はこちらが正本）を _arche/build.mjs で静的HTMLに書き出している。
  ソースだけ直して作り直さない、作り直したのに sitemap が古い、を止める。

検査:
  NG  _arche/src/cases/ の中身と、cases/ を書き出したときの指紋（cases/_assets/build.json）が違う
  NG  cases/ のページが読む JS/CSS が cases/_assets/ に無い
  NG  sitemap.xml の /cases/ のURLと、cases/ のページの集合が違う

直し方: cd _arche && npm run build → python scripts/sync_chrome.py
"""
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "_arche", "src", "cases")
CASES = os.path.join(ROOT, "cases")
STAMP = os.path.join(CASES, "_assets", "build.json")


def src_hash():
    h = hashlib.sha256()
    for f in sorted(os.listdir(SRC)):
        h.update(f.encode("utf-8"))
        # 改行は LF に揃える（build.mjs と同じ。git の autocrlf で CRLF になっても指紋は同じ）
        with open(os.path.join(SRC, f), "rb") as fp:
            h.update(fp.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def main():
    if not os.path.isdir(CASES):
        print("OK: cases/ が無い（アルケー未公開）")
        return 0
    ng = []

    with open(STAMP, encoding="utf-8") as f:
        stamp = json.load(f)
    if stamp.get("orig_sha256") != src_hash():
        ng.append("_arche/src/cases/ を直した後に作り直していない（cd _arche && npm run build）")

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

    if ng:
        print(f"アルケー（cases/）のズレ {len(ng)}件")
        for n in ng[:15]:
            print("  -", n)
        return 1
    print(f"OK: アルケー（cases/）はソース・sitemap と一致（{len(pages)}ページ）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
