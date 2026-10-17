#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日本語ページと英語ページ（en/）がズレていないかを見る。

なぜ作ったか（2026-10-18）:
  英語のトップに、日本語版で 10/14 に消した節が残ったままだった。英語版のリンクも
  nicomachos.com/cases（もう Teles に飛ぶ）のままだった。日本語だけ直して英語を
  直し忘れても、どの検査も止めなかったため。

検査（対は scripts/sync_chrome.py の EN_PAIRS が正本）:
  NG  英語ページが無い
  NG  日英で h2 の数・section の id の並びが違う（節を足した／消したのに片方だけ）
  NG  英語ページの本文に日本語が残っている（ヘッダー・フッター・フォームの name/hidden 値は除く）
  NG  hreflang（ja / en / x-default）が日英の両方に無い
  NG  日本語ページの本文が、英語版を最後に合わせたとき（en/_sync.json の指紋）から変わっている

直し方:
  英語ページを日本語の今の版に合わせて直す → python scripts/en_check.py --stamp で指紋を更新
  （日本語の誤字直しなど英語に関係ない変更でも、英語側を確かめたうえで --stamp する）
"""
import hashlib
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from sync_chrome import EN_PAIRS, page_url  # noqa: E402

STAMP = os.path.join(ROOT, "en", "_sync.json")
CHROME_RE = re.compile(r'<header class="header.*?</header>|<footer class="footer">.*?</footer>|'
                       r'<section class="rel".*?</section>|<script.*?</script>|<style.*?</style>|'
                       r'<head>.*?</head>|<!--.*?-->', re.S)
JP = re.compile(r"[぀-ヿ一-鿿]")
SITE = "https://ngraph.jp"


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def body(html):
    return CHROME_RE.sub("", html.replace("\r\n", "\n"))


def fingerprint(html):
    """日本語ページの本文（ヘッダー・フッター・CSS版を除く）の指紋"""
    text = re.sub(r"\s+", " ", body(html))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def shape(html):
    b = body(html)
    return len(re.findall(r"<h2[\s>]", b)), re.findall(r'<section[^>]*\bid="([^"]+)"', b)


def jp_left(html):
    b = body(html)
    # フォームの受け側は日本語のフィールド名で受けている（name・hidden の value は訳さない）
    b = re.sub(r'\bname="[^"]*"|<input type="hidden"[^>]*>|<option value="[^"]*"', "", b)
    # 人名の原表記など、意図して日本語で出す所は lang="ja" を付ける
    b = re.sub(r'<(\w+)[^>]*\blang="ja"[^>]*>.*?</\1>', "", b, flags=re.S)
    b = re.sub(r"<[^>]+>", " ", b)
    return sorted({m.group(0) for m in re.finditer(r"[^\s<>]*[぀-ヿ一-鿿][^\s<>]*", b)
                   if m.group(0) not in ("日本語",)})


def has_hreflang(html, ja, en):
    want = [(f'hreflang="ja" href="{SITE}{page_url(ja)}"'), (f'hreflang="en" href="{SITE}{page_url(en)}"'),
            'hreflang="x-default"']
    return all(w in html for w in want)


def check():
    bad = []
    stamps = {}
    if os.path.exists(STAMP):
        with open(STAMP, encoding="utf-8") as f:
            stamps = json.load(f)
    for ja, en in EN_PAIRS.items():
        if not os.path.exists(os.path.join(ROOT, en)):
            bad.append(f"{en}: 英語ページが無い（{ja} の対）")
            continue
        hj, he = read(ja), read(en)
        sj, se = shape(hj), shape(he)
        if sj != se:
            bad.append(f"{en}: 節の数・並びが日本語版と違う（h2 {sj[0]}/{se[0]}・section id {sj[1]} / {se[1]}）")
        left = jp_left(he)
        if left:
            bad.append(f"{en}: 本文に日本語が残っている: {' / '.join(left[:6])}")
        for p, h in ((ja, hj), (en, he)):
            if not has_hreflang(h, ja, en):
                bad.append(f"{p}: hreflang（ja/en/x-default）が無いか、相手のURLと違う")
        if stamps.get(ja) != fingerprint(hj):
            bad.append(f"{ja}: 英語版を合わせた後に日本語の本文が変わった → {en} を直して --stamp")
    return bad


def selftest():
    a = '<h2>a</h2><section id="x"></section>'
    if shape(a) == shape('<h2>a</h2>') or not jp_left("<p>残り</p>") or jp_left('<input type="hidden" name="種別" value="値">') \
            or jp_left('<p lang="ja">髙橋</p>'):
        print("en_check の自己テストに失敗（検査が壊れている）")
        sys.exit(1)


def main():
    selftest()
    if "--stamp" in sys.argv:
        data = {ja: fingerprint(read(ja)) for ja in EN_PAIRS}
        with open(STAMP, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"指紋を更新しました（{len(data)}ページ）。先に英語版を直したかを確かめてから実行すること")
    bad = check()
    if bad:
        print(f"日英のズレ {len(bad)}件")
        for b in bad:
            print("  - " + b)
        sys.exit(1)
    print(f"OK: 日英 {len(EN_PAIRS)} 組が揃っている")


if __name__ == "__main__":
    main()
