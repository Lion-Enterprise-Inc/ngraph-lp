#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Webネイティブ図解（figures/*.html）をページに差し込む（2026-09-03）。

図の正本は ngraph-lp/figures/<name>.html（HTML断片）と figures/<name>.css。
ページ側には
    <!-- fig:<name> -->
    …（ここが差し替わる）…
    <!-- /fig -->
と書いておく。見出し（section-head）はページ側に置いたまま。

CSS は figures/*.css を css/figures.css の末尾（マーカー以降）に連結する。

使い方:
    python scripts/web_figs.py index.html fde/index.html
"""
import io
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
CSS = ROOT / "css" / "figures.css"
MARK = "/* ===== 以下 figures/*.css から自動連結（web_figs.py）。ここより下は手で編集しない ===== */"


def inject(path):
    s = io.open(path, encoding="utf-8").read()
    n = 0

    def rep(m):
        nonlocal n
        name = m.group(1)
        f = FIG / (name + ".html")
        if not f.exists():
            print("  警告 figures/%s.html が無い（据え置き）" % name)
            return m.group(0)
        n += 1
        frag = io.open(f, encoding="utf-8").read().strip("\n")
        return "<!-- fig:%s -->\n%s\n    <!-- /fig -->" % (name, frag)

    s2 = re.sub(r"<!-- fig:([a-z0-9_-]+) -->[\s\S]*?<!-- /fig -->", rep, s)
    io.open(path, "w", encoding="utf-8", newline="\n").write(s2)
    print(path, "図を差し込み:", n)


def build_css():
    base = io.open(CSS, encoding="utf-8").read()
    if MARK in base:
        base = base[: base.index(MARK)].rstrip("\n") + "\n"
    parts = [base, MARK, ""]
    for f in sorted(FIG.glob("*.css")):
        parts.append("/* ── figures/%s ── */" % f.name)
        parts.append(io.open(f, encoding="utf-8").read().strip("\n"))
        parts.append("")
    io.open(CSS, "w", encoding="utf-8", newline="\n").write("\n".join(parts))
    print("css/figures.css を再生成:", len(list(FIG.glob("*.css"))), "ファイル")


if __name__ == "__main__":
    FIG.mkdir(exist_ok=True)
    build_css()
    for p in (sys.argv[1:] or ["index.html"]):
        inject(p)
