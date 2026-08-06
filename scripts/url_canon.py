#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""内部URLの形を正規化する（ngraph.jp = Cloudflare Pages）。

Cloudflare Pages は /foo.html を /foo へ 307 リダイレクトする。この挙動は
リポジトリ側から止められないので、サイトが名乗るURLの方を実際に配信される形
（拡張子なし）へ揃える。揃っていないと:
  - canonical が自分自身を指さない（307先が本体になる）
  - sitemap の全URLが1ホップ余計に踏まれる
  - 内部リンクのクリックが毎回リダイレクトを1回挟む
  - _redirects が .html を指していると 301 -> 307 -> 200 の2ホップになる

使い方:
    python scripts/url_canon.py --check    # 違反を列挙して exit 1（CI・公開前QA用）
    python scripts/url_canon.py --fix      # 書き換える

対象: *.html / blog/*.html / sitemap.xml / _redirects
外部ホストのURLには一切触らない（mhlw.go.jp/....html 等を壊さないため）。
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ngraph.jp"

# 除外: 公開対象でない作業ファイル
SKIP_NAMES = {"index-old.html", "ngraph-lp-v3.html"}


def targets():
    files = [p for p in ROOT.glob("*.html") if p.name not in SKIP_NAMES]
    files += sorted(ROOT.glob("blog/*.html"))
    for extra in ("sitemap.xml", "_redirects"):
        p = ROOT / extra
        if p.exists():
            files.append(p)
    return files


# 内部URLだけを捕まえる。外部URL（mhlw.go.jp/....html 等）を絶対に巻き込まないため、
# 「ngraph.jp から始まる」か「区切り文字の直後の絶対パス」のどちらかに限定する。
# ホスト名の途中にある /path.html （例: https://example.com/a.html）は前が英数字なので
# どちらにも当たらない。直後に来てよいのは 引用符 / # / ? / 空白 / < / 行末 のみ。
TAIL = r"(?=[\"'#?\s<]|$)"
PATTERNS = [
    # https://ngraph.jp/foo/bar.html
    re.compile(r"(?P<keep>" + re.escape(SITE) + r")(?P<path>/[A-Za-z0-9._\-/]*?)\.html" + TAIL),
    # href="/foo/bar.html" / _redirects の "  /entry.html" / 行頭の /foo.html
    re.compile(r"(?P<keep>[\"'(\s]|^)(?P<path>/[A-Za-z0-9._\-/]*?)\.html" + TAIL, re.M),
]


def canon(m):
    path = m.group("path")
    # /index.html と /blog/index.html はディレクトリのルートに畳む
    if path.endswith("/index"):
        path = path[: -len("index")]
    return m.group("keep") + path


def convert(text):
    for pat in PATTERNS:
        text = pat.sub(canon, text)
    return text


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="違反を列挙して exit 1")
    g.add_argument("--fix", action="store_true", help="書き換える")
    args = ap.parse_args()

    violations = []
    changed = []
    for path in targets():
        src = path.read_text(encoding="utf-8")
        dst = convert(src)
        if src == dst:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if args.fix:
            path.write_text(dst, encoding="utf-8")
            changed.append(rel)
        else:
            for i, (a, b) in enumerate(zip(src.splitlines(), dst.splitlines()), 1):
                if a != b:
                    for pat in PATTERNS:
                        for m in pat.finditer(a):
                            violations.append("%s:%d  %s.html" % (rel, i, m.group("path")))

    if args.fix:
        print("fixed %d files" % len(changed))
        for c in changed:
            print("  " + c)
        return 0

    if violations:
        print("内部URLに .html が残っています（Cloudflare Pages が307で剥がすため、"
              "名乗るURLも拡張子なしに揃える）:")
        for v in violations:
            print("  " + v)
        print("\n%d件。`python scripts/url_canon.py --fix` で直せます。" % len(violations))
        return 1

    print("OK: 内部URLはすべて拡張子なしに揃っています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
