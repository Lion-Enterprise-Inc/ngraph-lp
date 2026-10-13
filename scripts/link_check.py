#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""サイト内リンクの飛び先（ファイルとページ内の #アンカー）が実在するかの検査。

なぜ作ったか（2026-10-14）:
  トップのフッター「進め方」(/#process) や、古い記事のフッター「FDEとは」(/#fde) が、
  トップの作り直しで飛び先を失ったまま何か月も残っていた。押すとトップの先頭に
  戻るだけなので、見た目では気づけない。

使い方:
    python scripts/link_check.py    # 飛び先の無いリンクを列挙して exit 1
"""
import os
import re
import subprocess
import sys
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKIP_PREFIX = ("scripts/", "_", "figures/")
SKIP_FILES = {"index-old.html", "ngraph-lp-v3.html"}

HREF_RE = re.compile(r'<a\b[^>]*?\bhref="([^"]+)"', re.I)
ID_RE = re.compile(r'\b(?:id|name)="([^"]+)"')


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, encoding="utf-8").stdout
    return set(out.split())


def resolve(path, files):
    """URLのパス部分 → リポジトリ内のファイル（無ければ None）。worker の拡張子なしURLに合わせる。"""
    p = unquote(path).lstrip("/")
    cands = [p] if p else ["index.html"]
    if p.endswith("/"):
        cands = [p + "index.html"]
    elif p:
        cands += [p + ".html", p + "/index.html"]
    for c in cands:
        if c in files:
            return c
    return None


def ids_of(html):
    return set(ID_RE.findall(html))


def check_links(page, html, files, read):
    """(page, href, 理由) のリスト。read(path)->html。selftest からも呼ぶ。"""
    bad = []
    for href in HREF_RE.findall(html):
        if href.startswith(("http:", "https:", "mailto:", "tel:", "javascript:", "//", "data:")):
            continue
        if "{" in href or "'+" in href or href.startswith("$"):  # JSで組み立てるURL
            continue
        path, _, frag = href.partition("#")
        path = path.split("?")[0]
        if path:
            if not path.startswith("/"):
                base = os.path.dirname(page).replace("\\", "/")
                path = "/" + (base + "/" if base else "") + path
            target = resolve(path, files)
            if target is None:
                if re.search(r"\.(png|jpe?g|webp|svg|pdf|gif|xml|txt|json|ico|css|js)$", path, re.I):
                    if path.lstrip("/") in files:
                        continue
                bad.append((page, href, "飛び先のページが無い"))
                continue
        else:
            target = page
        if frag and frag not in ("top", ""):
            if not target.endswith(".html"):
                continue
            if frag not in ids_of(read(target)):
                bad.append((page, href, f"#{frag} がページに無い"))
    return bad


def selftest():
    """既知NG（無いアンカー・無いページ）が落ち、既知OKが通るか。"""
    pages = {"index.html": '<section id="start"></section>', "company.html": '<div id="tech"></div>'}
    rd = lambda p: pages[p]
    ng1 = check_links("index.html", '<a href="/#process">x</a>', set(pages), rd)
    ng2 = check_links("index.html", '<a href="/nowhere/">x</a>', set(pages), rd)
    ok = check_links("index.html", '<a href="/company#tech">x</a><a href="#start">y</a>', set(pages), rd)
    if not ng1 or not ng2 or ok:
        print("link_check の自己テストに失敗（検査が壊れている）")
        sys.exit(1)


def main():
    selftest()
    files = tracked()
    cache = {}

    def read(p):
        if p not in cache:
            with open(os.path.join(ROOT, p), encoding="utf-8", errors="replace") as f:
                cache[p] = f.read()
        return cache[p]

    bad = []
    for p in sorted(f for f in files if f.endswith(".html")):
        if p.startswith(SKIP_PREFIX) or p in SKIP_FILES:
            continue
        bad += check_links(p, read(p), files, read)
    if bad:
        print(f"飛び先の無いサイト内リンク {len(bad)}件")
        for page, href, why in bad[:60]:
            print(f"  - {page}: {href}（{why}）")
        sys.exit(1)
    print("サイト内リンクの飛び先はすべて実在")


if __name__ == "__main__":
    main()
