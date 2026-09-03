#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""営業資料（PPTXビルドモジュール）から書き出したSVG図解を、ページに差し込む（2026-09-03）。

図の正本は Documents\\Codex\\2026-08-13\\new-chat\\tmp\\faithful_pptx\\slides\\*.mjs。
SVG は同フォルダの svg_export/run.mjs で書き出す（対外語彙の置換・和禅の色はそこで行う）。
このスクリプトは、書き出し済みの out/<name>.fig.svg を、HTML内の
  <!-- deckfig:<name> --> … <!-- /deckfig -->
の間に差し込むだけ。見出し（kicker/H1/lede）は meta.json から取り、HTMLのテキストとして書く。

使い方:
    python scripts/deck_figs.py index.html fde/index.html
"""
import html
import io
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
OUT = pathlib.Path(r"C:\Users\shing\Documents\Codex\2026-08-13\new-chat\tmp\faithful_pptx\svg_export\out")
VOCAB = [("唯一の正本", "一つの記録"), ("会社の正本", "会社の記録"), ("正本", "記録"), ("検問", "検査"), ("読み口", "AI接続口"), ("会社のBrain", "会社の脳"), ("Brain", "会社の脳")]


def tr(s):
    for a, b in VOCAB:
        s = s.replace(a, b)
    return s


def runs_html(rs):
    return "".join(('<span class="hl">%s</span>' % html.escape(tr(r["t"]))) if r.get("color") else html.escape(tr(r["t"])) for r in rs)


def block(name, label=None):
    svg = io.open(OUT / (name + ".fig.svg"), encoding="utf-8").read()
    meta = json.load(io.open(OUT / (name + ".meta.json"), encoding="utf-8"))
    h = meta["header"]
    svg = svg.replace("<svg ", '<svg aria-labelledby="%s-t" ' % name, 1)
    head = '<div class="section-head reveal">\n      <div class="section-label">%s</div>\n      <h2 class="section-title" id="%s-t">%s</h2>\n' % (
        html.escape(label or h["kicker"]), name, runs_html(h["h1"]))
    if h.get("lede"):
        head += '      <p class="section-sub">%s</p>\n' % runs_html(h["lede"])
    head += "    </div>\n"
    return head + '    <figure class="dkfig">\n      %s\n    </figure>' % svg


def main(paths):
    for p in paths:
        s = io.open(p, encoding="utf-8").read()
        n = 0

        def rep(m):
            nonlocal n
            n += 1
            name = m.group(1)
            label = m.group(2)
            return "<!-- deckfig:%s%s -->\n    %s\n    <!-- /deckfig -->" % (name, (" label=" + label) if label else "", block(name, label))

        s2 = re.sub(r"<!-- deckfig:(\S+?)(?: label=([^\n]+?))? -->[\s\S]*?<!-- /deckfig -->", rep, s)
        io.open(p, "w", encoding="utf-8", newline="\n").write(s2)
        print(p, "図を差し込み:", n)


if __name__ == "__main__":
    main(sys.argv[1:] or ["index.html"])
