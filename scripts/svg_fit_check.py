#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""図の吹き出し・ラベル（SVG の g の中の rect と text）で、文字が枠からはみ出していないかを実測する。

SVG の枠は幅が固定なので、文字の書体や太さ・英訳を変えると、静的な検査では気づけずに
はみ出す（2026-10-23「知識の置き場所＝会話の中」が日本語版で4px、英語版の3か所が最大36px
はみ出していた）。実際にブラウザで描いて、文字の箱と枠の箱を比べる。

対象: git が持っている .html のうち、<svg> の中に <text> を持つページ（ブログ記事は除く）。
使い方: python scripts/svg_fit_check.py   （NG があれば exit 1）
"""
import functools
import http.server
import os
import re
import subprocess
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAD = 6  # 枠の内側にこれだけの余白が無ければ「はみ出し」とみなす（角丸・線の太さの分）

JS = """(pad) => {
  const out = [];
  document.querySelectorAll('svg g').forEach(g => {
    const r = g.querySelector(':scope > rect'); if (!r) return;
    if (getComputedStyle(g).display === 'none') return;
    const rb = r.getBBox(); if (rb.width < 40 || rb.height < 20) return;
    g.querySelectorAll(':scope > text').forEach(t => {
      const tb = t.getBBox(); if (!tb.width) return;
      if (tb.x < rb.x + pad || tb.x + tb.width > rb.x + rb.width - pad)
        out.push(`「${t.textContent.trim()}」文字 ${tb.x.toFixed(0)}〜${(tb.x + tb.width).toFixed(0)} ／ 枠 ${rb.x.toFixed(0)}〜${(rb.x + rb.width).toFixed(0)}`);
    });
  });
  return out;
}"""

NG_SAMPLE = '<svg viewBox="0 0 400 100"><g><rect width="80" height="40"/><text x="10" y="28">はみ出す長い文字列です</text></g></svg>'
OK_SAMPLE = '<svg viewBox="0 0 400 100"><g><rect width="300" height="40"/><text x="10" y="28">収まる</text></g></svg>'


def pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split()
    res = []
    for p in out:
        # ブログ記事・表紙の型（scripts/）・図の部品（figures/、文字コード宣言の無い断片）は対象外
        if p.startswith(("blog/", "en/blog/", "scripts/", "figures/", "_", ".")) or "/_" in p:
            continue
        s = open(os.path.join(ROOT, p), encoding="utf-8", errors="replace").read()
        if re.search(r"<svg[^>]*>.*?<g[^>]*>\s*<rect[^>]*/>\s*.*?<text", s, re.S):
            res.append(p)
    return res


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    h = functools.partial(Quiet, directory=ROOT)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright が無いので実測できない（pip install playwright）")
        return 0
    targets = pages()
    srv = serve()
    port = srv.server_address[1]
    bad = []
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        # 自己テスト：既知NGが落ち、既知OKが通るか（検査そのものが壊れていないか）
        pg.set_content(NG_SAMPLE)
        ng = pg.evaluate(JS, PAD)
        pg.set_content(OK_SAMPLE)
        ok = pg.evaluate(JS, PAD)
        if not ng or ok:
            print("svg_fit_check の自己テストに失敗（検査が壊れている）")
            return 1
        for t in targets:
            url = "http://127.0.0.1:%d/%s" % (port, t)
            pg.goto(url, wait_until="networkidle")
            pg.evaluate("document.fonts && document.fonts.ready")
            pg.wait_for_timeout(300)
            for x in pg.evaluate(JS, PAD):
                bad.append("%s: %s" % (t, x))
        b.close()
    srv.shutdown()
    if bad:
        print("図の文字が枠からはみ出している %d 件（枠を広げるか、文字を短く・小さく）" % len(bad))
        for x in bad:
            print("  - " + x)
        return 1
    print("OK: 図の文字は枠に収まっている（%d ページ）" % len(targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
