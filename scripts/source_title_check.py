#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""参考（一次情報）枠の出典タイトルが、実在するページのタイトルと一致するかを見る。

なぜ入れたか（2026-08-18）: 朝A型の記事で、Wizの調査記事の題名が
「Red Agent: Snowflake, Copilot, and a CI/CD bug」と書かれて公開された。
実際の題名は「Red Agent Exploits Snowflake Vuln Created by Copilot Autofix」で、
URLのスラッグ（red-agent-snowflake-copilot-cicd-bug）から**それらしい題名が合成**
されていた。同じ理由で Gemini の2本も実在しない邦題になっていた。
出典の題名は、書き手が一番「もっともらしく作れてしまう」場所なので、目視で守れない。

⚠ この検査はネットワークに出るので `gate.py` には入れない
（BLOG-OPS §4 と同じ理由＝公開前ゲートを外部依存にしない）。
朝夕の定時タスクが push 前に単体で回す。取得できなかったURLは NG にせず「未確認」で残す。

使い方:
    python scripts/source_title_check.py blog/<記事>.html
    python scripts/source_title_check.py            # blog/ の最新1本
"""
import glob
import html as htmllib
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "Mozilla/5.0 (compatible; ngraph-source-check/1.0)"
TIMEOUT = 25


def page_title(url):
    """ページの <title> を返す。取れなければ None。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read(400_000)
    except Exception:
        return None
    text = None
    for enc in ("utf-8", "cp932", "euc-jp", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        return None
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    if not m:
        return None
    return re.sub(r"\s+", " ", htmllib.unescape(m.group(1))).strip()


def norm(s):
    """比較用に正規化する。記号・空白・大小文字の差は無視する。"""
    s = htmllib.unescape(s or "")
    s = re.sub(r"[\s　]+", "", s)
    s = re.sub(r"[|｜\-–—―‐・:：,，.。、「」『』（）()\[\]【】\"'’”]", "", s)
    return s.lower()


def matches(link_text, title):
    """リンク文字列がページタイトルと一致していると見なせるか。

    サイト名が「題名 | サービス名 | 会社名」の形で付くので部分一致で見る。
    区切りで割ったどの断片とも突き合わせる（うちの表記は題名だけを書くため）。
    """
    lt, tt = norm(link_text), norm(title)
    if not lt or not tt:
        return False
    if lt in tt or tt in lt:
        return True
    for part in re.split(r"[|｜]", title):
        p = norm(part)
        if p and (lt in p or p in lt):
            return True
    return False


def src_links(path):
    """記事の参考枠（.a-src）の中の外部リンクを [(text, url)] で返す。"""
    with open(path, encoding="utf-8") as f:
        doc = f.read()
    blocks = re.findall(r'<div class="a-src".*?</div>', doc, re.S)
    out = []
    for b in blocks:
        for url, text in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', b, re.S):
            out.append((re.sub(r"<[^>]+>", "", text).strip(), url))
    return out


def check(path):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    links = src_links(path)
    if not links:
        print(f"  {rel}: 参考枠に外部リンクが無い")
        return 0, 0
    ng = unknown = 0
    for text, url in links:
        title = page_title(url)
        if title is None:
            print(f"  ? 未確認（取得できず） {text} -> {url}")
            unknown += 1
        elif matches(text, title):
            print(f"  OK {text}")
        else:
            print(f"  NG {rel}")
            print(f"     書いてある題名: {text}")
            print(f"     実際のページ  : {title}")
            print(f"     {url}")
            ng += 1
    return ng, unknown


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        targets = [a if os.path.isabs(a) else os.path.join(ROOT, a) for a in args]
    else:
        found = sorted(glob.glob(os.path.join(ROOT, "blog", "2*.html")))
        targets = found[-1:]
    if not targets:
        print("対象の記事が無い")
        return 0

    total_ng = total_unknown = 0
    for t in targets:
        if not os.path.exists(t):
            print(f"NG: ファイルが無い {t}")
            total_ng += 1
            continue
        ng, unknown = check(t)
        total_ng += ng
        total_unknown += unknown

    if total_ng:
        print(f"\nNG: 出典の題名が実際のページと違う {total_ng}件。"
              "実際の題名をそのまま貼ること（URLから題名を作らない）")
        return 1
    print(f"\nOK: 出典の題名は実在のページと一致（未確認 {total_unknown}件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
