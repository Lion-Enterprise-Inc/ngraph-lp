#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ブログ一覧のカテゴリ（タブ）の正本と検査（2026-08-22新設・髙橋さん「体系別に分けて見れるのがいい」）。

タブは読者が探す軸（BLOG-OPS §4「発注者が相談直前に検索する問い」）で切る。社内の7系統ではない。
FDEの記事は独立タブにせず「AI導入の判断」に入れる（読者は「FDE」では探さない）。

  news      AIニュース        朝A型
  adoption  AI導入の判断      使われない理由・費用・研修との違い・PoC止まり・FDE
  subsidy   補助金・制度      補助金・最低賃金・106/130万の壁・インボイス
  security  セキュリティ・権限 AIに何を読ませるか・権限・漏えい
  tech      技術の地図        非エンジニア向けの技術解説・自社でやってみた・ナレッジ

使い方:
    python scripts/blog_categories.py --suggest   # カテゴリ未設定のカードに対する推定を表示（付ける判断は人）
    python scripts/blog_categories.py             # 検査: 一覧の全カードに data-cat があり、許可された値か（gate.py 経由）
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "blog", "index.html")

CATS = {
    "news": "AIニュース",
    "adoption": "AI導入の判断",
    "subsidy": "補助金・制度",
    "security": "セキュリティ・権限",
    "tech": "技術の地図",
}


def cards(html):
    for m in re.finditer(r'<div class="card blog-card"([^>]*)>(.*?)</div>', html, re.S):
        attrs, body = m.group(1), m.group(2)
        cat = re.search(r'data-cat="([^"]*)"', attrs)
        lab = re.search(r'b-date">([^<]*)', body)
        slug = re.search(r'href="/blog/([^"]+)"', body)
        title = re.search(r"<h3>(.*?)</h3>", body, re.S)
        yield {
            "cat": cat.group(1) if cat else None,
            "label": lab.group(1) if lab else "",
            "slug": slug.group(1) if slug else "",
            "title": re.sub("<[^>]+>", "", title.group(1)) if title else "",
        }


def suggest(card):
    t, lab, slug = card["title"], card["label"], card["slug"]
    if "朝" in lab:
        return "news"
    if re.search(r"補助金|最低賃金|助成金|の壁|インボイス|制度|申請", t):
        return "subsidy"
    if re.search(r"セキュリティ|権限|漏えい|漏洩|認証|パスワード", t):
        return "security"
    if slug.startswith("k-") or re.search(
            r"MCP|Cloudflare|GitHub|API|LLM|モデル|アルゴリズム|トークン|Qwen|DeepSeek|ローカル|透かし|正本|Brain|ブレイン|記憶|営業資料|取引先|コード", t):
        return "tech"
    return "adoption"


def main():
    html = open(INDEX, encoding="utf-8").read()
    rows = list(cards(html))
    if "--suggest" in sys.argv:
        for c in rows:
            print("%-9s %-42s %s" % (c["cat"] or "(" + suggest(c) + ")", c["slug"][:42], c["title"][:40]))
        return 0
    bad = [c for c in rows if c["cat"] not in CATS]
    if bad:
        print("NG: カテゴリ未設定または不正なカード %d件（data-cat は %s のどれか）" % (len(bad), "/".join(CATS)))
        for c in bad:
            print("  - %s: data-cat=%r（推定: %s）" % (c["slug"], c["cat"], suggest(c)))
        return 1
    counts = {}
    for c in rows:
        counts[c["cat"]] = counts.get(c["cat"], 0) + 1
    print("OK: 一覧 %d枚すべてにカテゴリあり（%s）" % (
        len(rows), "・".join("%s %d" % (CATS[k], v) for k, v in counts.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
