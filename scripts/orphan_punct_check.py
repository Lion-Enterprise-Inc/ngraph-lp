#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""句読点やかっこだけが1行に落ちていないかを、ブラウザで実際に描いて調べる（パソコン・タブレット・スマホの3幅）。

2026-10-23「もし明日、パソコンが使えなくなった／。」と「。」だけが次の行に落ちていた。
句ごとに nb（折り返さない箱）で包んだ見出しは、句が1行に入らないとき箱の中で無理に折れ、
そのとき禁則（「。」を行頭に置かない）が効かない。見出しの級数を上げるたびに起きうるので、実測で止める。

対象: git が持っている .html のうち、ブログ記事・部品・試作を除くページ（ブログは一覧だけ）。
使い方: python scripts/orphan_punct_check.py   （NG があれば exit 1）
"""
import functools
import http.server
import os
import subprocess
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIDTHS = (1280, 768, 390)

# 各テキストを1文字ずつ測り、行ごとにまとめ、句読点・閉じかっこだけの行を探す
JS = r"""() => {
  const P = /^[、。，．,.・：；:;！？!?」』）)\]】〕〉》”’ー…\s]+$/;
  const out = [];
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const blocks = new Map();
  let n;
  while ((n = walker.nextNode())) {
    if (!n.nodeValue.trim()) continue;
    const el = n.parentElement;
    if (!el || el.closest('script,style,svg,noscript,[aria-hidden="true"],.sr-only,pre,code')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    let blk = el;
    while (blk && blk !== document.body) {
      const d = getComputedStyle(blk).display;
      if (d !== 'inline' && d !== 'inline-block' && d !== 'contents') break;
      blk = blk.parentElement;
    }
    if (!blocks.has(blk)) blocks.set(blk, []);
    blocks.get(blk).push(n);
  }
  for (const [blk, nodes] of blocks) {
    const lines = new Map();
    for (const t of nodes) {
      const s = t.nodeValue;
      for (let i = 0; i < s.length; i++) {
        const r = document.createRange(); r.setStart(t, i); r.setEnd(t, i + 1);
        const rect = r.getClientRects()[0];
        if (!rect || !rect.width) continue;
        const key = Math.round(rect.top / 4);
        if (!lines.has(key)) lines.set(key, '');
        lines.set(key, lines.get(key) + s[i]);
      }
    }
    if (lines.size < 2) continue;
    for (const txt of lines.values()) {
      if (txt.trim() && P.test(txt)) {
        const all = [...lines.values()].join('').replace(/\s+/g, '');
        if (!seen.has(all)) { seen.add(all); out.push(`「${txt.trim()}」だけの行 ← ${all.slice(0, 40)}`); }
      }
    }
  }
  return out;
}"""

NG_SAMPLE = '<div style="width:290px;font-size:24px;letter-spacing:0"><span style="display:inline-block;word-break:keep-all;overflow-wrap:anywhere">パソコンが使えなくなった。</span></div>'
OK_SAMPLE = '<div style="width:400px;font-size:24px">パソコンが使えなくなった。</div>'


def pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split()
    keep = []
    for p in out:
        if p.startswith(("_", ".", "scripts/", "figures/", "cases/")) or "/_" in p:
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
        pg.set_content("<html lang=ja><meta charset=utf-8><body>" + NG_SAMPLE)
        ng = pg.evaluate(JS)
        pg.set_content("<html lang=ja><meta charset=utf-8><body>" + OK_SAMPLE)
        ok = pg.evaluate(JS)
        if not ng or ok:
            print("orphan_punct_check の自己テストに失敗（検査が壊れている）", ng, ok)
            return 1
        for w in WIDTHS:
            pg.set_viewport_size({"width": w, "height": 900})
            for t in targets:
                pg.goto("http://127.0.0.1:%d/%s?noreveal" % (port, t), wait_until="networkidle")
                pg.evaluate("document.fonts && document.fonts.ready")
                for x in pg.evaluate(JS):
                    bad.append("%s（幅%d）: %s" % (t, w, x))
        b.close()
    srv.shutdown()
    if bad:
        print("句読点だけが1行に落ちている %d 件（句を分ける・言い換える・見出しの幅を広げる）" % len(bad))
        for x in bad:
            print("  - " + x)
        return 1
    print("OK: 句読点だけの行は無い（%d ページ × %d 幅）" % (len(targets), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
