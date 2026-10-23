#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""文字が小さすぎないかを、ブラウザで実際に描いて調べる（パソコン 1280px・スマホ 390px）。

2026-10-23 実測で、図の中の文字がスマホで 8px、フッターの見出しや小さな札が 10〜11px になっていた。
本文の文字は 12px 以上、図（SVG）の中の文字は描かれた大きさで 11px 以上を下限にする。
下限を変えたいときはここの数字を直す（検査を外さない）。

対象: git が持っている .html のうち、ブログ記事・部品・試作・アルケーを除くページ（ブログは一覧だけ）。
使い方: python scripts/type_floor_check.py   （NG があれば exit 1）
"""
import functools
import http.server
import os
import subprocess
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = (1280, 390)
MIN_HTML = 12.0
MIN_SVG = 11.0

JS = r"""([minH, minS]) => {
  const out = []; const seen = new Set();
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
  while ((n = w.nextNode())) {
    const t = n.nodeValue.trim(); if (!t) continue;
    const el = n.parentElement;
    if (!el || el.closest('script,style,noscript,[aria-hidden="true"],.sr-only')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    let px, kind;
    if (el.closest('svg')) {
      const svg = el.closest('svg'); const m = svg.getScreenCTM && svg.getScreenCTM();
      px = parseFloat(cs.fontSize) * (m ? Math.hypot(m.a, m.b) : 1); kind = 'svg';
      if (px >= minS) continue;
    } else { px = parseFloat(cs.fontSize); kind = 'html'; if (px >= minH) continue; }
    const key = kind + t.slice(0, 20);
    if (seen.has(key)) continue; seen.add(key);
    out.push(`${px.toFixed(1)}px（${kind === 'svg' ? '図の中' : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '')}）「${t.slice(0, 24)}」`);
  }
  return out;
}"""


def pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split()
    keep = []
    for p in out:
        if p.startswith(("_", ".", "scripts/", "figures/", "cases/", "tools/")) or "/_" in p:
            continue
        if p.startswith(("blog/", "en/blog/")) and not p.endswith("index.html"):
            continue
        keep.append(p)
    return keep


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP: playwright が無いので実測できない（pip install playwright）")
        return 0
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    bad = []
    targets = pages()
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1280, "height": 900})
        pg.set_content('<html lang=ja><meta charset=utf-8><body><p style="font-size:9px">小さい</p><svg viewBox="0 0 1000 100" width="200"><text x="0" y="50" font-size="40">図</text></svg>')
        ng = pg.evaluate(JS, [MIN_HTML, MIN_SVG])
        pg.set_content('<html lang=ja><meta charset=utf-8><body><p style="font-size:16px">本文</p>')
        ok = pg.evaluate(JS, [MIN_HTML, MIN_SVG])
        if len(ng) != 2 or ok:
            print("type_floor_check の自己テストに失敗（検査が壊れている）", ng, ok)
            return 1
        for w in WIDTHS:
            pg.set_viewport_size({"width": w, "height": 900})
            for t in targets:
                pg.goto("http://127.0.0.1:%d/%s?noreveal" % (port, t), wait_until="networkidle")
                for x in pg.evaluate(JS, [MIN_HTML, MIN_SVG]):
                    bad.append("%s（幅%d）: %s" % (t, w, x))
        b.close()
    srv.shutdown()
    if bad:
        print("文字が小さすぎる %d 件（本文 %gpx・図の中 %gpx が下限）" % (len(bad), MIN_HTML, MIN_SVG))
        for x in bad:
            print("  - " + x)
        return 1
    print("OK: 文字の大きさは下限以上（%d ページ × %d 幅）" % (len(targets), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
