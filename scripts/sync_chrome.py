#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全ページのフッターを共通部品（scripts/chrome/footer_*.html）に揃える。

なぜ作ったか（2026-10-14）:
  フッターが各ページへの手書きコピーで、5〜6種類に分裂していた。旧トップ時代の
  「FDEとは(/#fde)」等、飛び先の無いリンクも古い記事に残り続けていた。
  正本を1か所にし、gate.py でズレを止める。

使い方:
    python scripts/sync_chrome.py           # 全ページへ書き込む
    python scripts/sync_chrome.py --check   # ズレているページを列挙して exit 1（gate.py が呼ぶ）

フッターを変えるときは scripts/chrome/footer_ja.html（英語は footer_en.html）を直して
このスクリプトを実行する。ページ側のフッターを手で直さない（次の検査で落ちる）。
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CHROME = os.path.join(HERE, "chrome")

# ngraph-zen.css を変えたら上げる（ブラウザ・CDNの古いCSSと新しいHTMLの組み合わせを防ぐ）
ZEN_VERSION = "11"

FOOTER_RE = re.compile(r'<footer class="footer">.*?</footer>', re.S)
ZEN_RE = re.compile(r'(/css/ngraph-zen\.css\?v=)(\d+)')
# 公開しない・別系統のページ
SKIP_PREFIX = ("scripts/", "_", "figures/")
SKIP_FILES = {"index-old.html", "ngraph-lp-v3.html"}


def partial(lang):
    with open(os.path.join(CHROME, f"footer_{lang}.html"), encoding="utf-8") as f:
        return f.read().strip()


def lang_of(path):
    return "en" if path.replace("\\", "/").startswith("en/") else "ja"


def norm(s):
    return re.sub(r"\s+", " ", s.replace("\r\n", "\n")).strip()


def pages():
    out = subprocess.run(["git", "ls-files", "*.html"], cwd=ROOT, capture_output=True,
                         encoding="utf-8").stdout.split()
    for p in out:
        if p.startswith(SKIP_PREFIX) or p in SKIP_FILES:
            continue
        yield p


# サービスページの末尾に置く「ほかのサービス」（自分のページは除く・2026-10-14）
RELATED = {"fde/index.html": "/fde/", "drill/index.html": "/drill/",
           "security/index.html": "/security/", "starter/index.html": "/starter/"}
REL_RE = re.compile(r'<section class="rel"[^>]*>.*?</section>\s*', re.S)
# 見出しの改行位置（2026-10-14）：「、」「。」の途中で折れないよう句ごとに nb で包む
TITLE_RE = re.compile(r'(<h2 class="section-title"[^>]*>)([^<]+)(</h2>)')
PHRASE_RE = re.compile(r"[^、。]+[、。]?")


def related(path):
    own = RELATED.get(path.replace("\\", "/"))
    if not own:
        return None
    with open(os.path.join(CHROME, "related_ja.html"), encoding="utf-8") as f:
        block = f.read().strip()
    return re.sub(r'\s*<li><a href="%s">.*?</li>' % re.escape(own), "", block, flags=re.S)


def wrap_title(text):
    parts = PHRASE_RE.findall(text)
    if len(parts) < 2:
        return text
    return "".join('<span class="nb">%s</span>' % x for x in parts)


def bad_titles(html):
    return [t for _, t, _ in TITLE_RE.findall(html) if len(PHRASE_RE.findall(t)) >= 2]


def check_html(html, lang, path=""):
    """(ok, 理由)。selftest からも呼ぶ。"""
    m = FOOTER_RE.search(html)
    if not m:
        return True, "フッター無し（対象外）"
    if norm(m.group(0)) != norm(partial(lang)):
        return False, "共通フッターと違う"
    for v in ZEN_RE.findall(html):
        if v[1] != ZEN_VERSION:
            return False, f"ngraph-zen.css の版が古い（v={v[1]}・正は v={ZEN_VERSION}）"
    rel = related(path)
    if rel is not None:
        m2 = REL_RE.search(html)
        if not m2 or norm(m2.group(0)) != norm(rel):
            return False, "「ほかのサービス」が無いか、正本と違う"
    bt = bad_titles(html)
    if bt:
        return False, "見出しが句の途中で折れる（nb で包んでいない）: " + bt[0]
    return True, "OK"


def apply_html(html, lang, path=""):
    if not FOOTER_RE.search(html):
        return html
    nl = "\r\n" if "\r\n" in html else "\n"
    foot = partial(lang).replace("\n", nl)
    html = FOOTER_RE.sub(lambda m: foot, html, count=1)
    rel = related(path)
    if rel is not None:
        html = REL_RE.sub("", html)
        html = html.replace('<footer class="footer">', rel.replace("\n", nl) + nl + nl + '<footer class="footer">', 1)
    html = TITLE_RE.sub(lambda m: m.group(1) + wrap_title(m.group(2)) + m.group(3), html)
    return ZEN_RE.sub(lambda m: m.group(1) + ZEN_VERSION, html)


def selftest():
    """検査そのものが緩められていないか（既知NGが落ち、既知OKが通るか）。gate.py は selftest.py
    を先に回すが、selftest.py は並行セッションの編集と衝突しやすいので、ここに同居させる。"""
    ng, _ = check_html('<footer class="footer"><a href="/#fde">FDEとは</a></footer>', "ja")
    ok, _ = check_html(partial("ja"), "ja")
    ng2, _ = check_html(partial("ja") + '<h2 class="section-title">AIは使いたい。でも、出せない。</h2>', "ja")
    if ng is not False or ok is not True or ng2 is not False:
        print("sync_chrome の自己テストに失敗（検査が壊れている）")
        sys.exit(1)


def main():
    check = "--check" in sys.argv
    if check:
        selftest()
    bad, changed = [], []
    for p in pages():
        fp = os.path.join(ROOT, p)
        with open(fp, encoding="utf-8", newline="") as f:
            html = f.read()
        if check:
            ok, why = check_html(html, lang_of(p), p)
            if not ok:
                bad.append(f"{p}: {why}")
            continue
        new = apply_html(html, lang_of(p), p)
        if new != html:
            with open(fp, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            changed.append(p)
    if check:
        if bad:
            print(f"共通フッターとズレているページ {len(bad)}件 → python scripts/sync_chrome.py で揃える")
            for b in bad[:30]:
                print("  - " + b)
            sys.exit(1)
        print("全ページのフッターが共通部品と一致")
        return
    print(f"揃えたページ {len(changed)}件")
    for c in changed:
        print("  " + c)


if __name__ == "__main__":
    main()
