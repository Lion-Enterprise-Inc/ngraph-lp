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
ZEN_VERSION = "14"

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
    # 書きかけ（未追跡）の記事も揃える。publish_check の CSS版検査は未追跡も数えるため（2026-10-14）
    out += subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "*.html"], cwd=ROOT,
                          capture_output=True, encoding="utf-8").stdout.split()
    for p in out:
        if p.startswith(SKIP_PREFIX) or p in SKIP_FILES:
            continue
        yield p


# サービスページの末尾に置く「ほかのサービス」（自分のページは除く・2026-10-14）
RELATED = {"fde/index.html": "/fde/", "drill/index.html": "/drill/",
           "security/index.html": "/security/", "starter/index.html": "/starter/",
           "en/fde/index.html": "/en/fde/", "en/drill/index.html": "/en/drill/",
           "en/security/index.html": "/en/security/", "en/starter/index.html": "/en/starter/"}
REL_RE = re.compile(r'<section class="rel"[^>]*>.*?</section>\s*', re.S)
# 見出しの改行位置（2026-10-14）：「、」「。」の途中で折れないよう句ごとに nb で包む
TITLE_RE = re.compile(r'(<h2 class="section-title"[^>]*>)([^<]+)(</h2>)')
# 見出し下の説明文も同じ（2026-10-20「ローカルAI / Pack」と名前の途中で折れていた）。タグを含まない一文だけ対象
SUB_RE = re.compile(r'(<p class="section-sub"[^>]*>)([^<]+)(</p>)')
# トップのサービス一覧の説明文も同じ（2026-10-21「会社の脳に／整えて」「直／せる形で」と句の途中で折れていた）
DESC_RE = re.compile(r'(<span class="svc-desc"[^>]*>)([^<]+)(</span>)')
WRAP_RES = (TITLE_RE, SUB_RE, DESC_RE)
# 包んだ句が長すぎるとスマホ幅（約17字）で句の中が折れ「。」だけが次の行に落ちる（2026-10-21 実測）
DESC_NB_RE = re.compile(r'<span class="svc-desc">((?:<span class="nb">[^<]*</span>)+)</span>')
NB_MAX = 17.5


def nb_width(t):
    return sum(1 if ord(c) > 255 else 0.55 for c in t)


def long_phrases(html):
    return [t for blk in DESC_NB_RE.findall(html) for t in re.findall(r'<span class="nb">([^<]*)</span>', blk) if nb_width(t) > NB_MAX]
PHRASE_RE = re.compile(r"[^、。]+[、。]?")


# ---- ヘッダー（2026-10-14 全ページ共通。正本 scripts/chrome/header_*.html） ----
HEADER_RE = re.compile(r'<header class="(header[^"]*)">.*?</header>', re.S)
NAVJS_RE = re.compile(r'\s*<script data-chrome="navjs">.*?</script>', re.S)
NAVJS = ('<script data-chrome="navjs">(function(){var h=document.querySelector(".header"),t=document.getElementById("navToggle"),n=document.getElementById("nav");'
         'if(t&&n){t.addEventListener("click",function(){n.classList.toggle("open")});n.addEventListener("click",function(e){if(e.target.tagName==="A")n.classList.remove("open")})}'
         'if(h&&!h.classList.contains("scrolled")){var f=function(){h.classList.toggle("scrolled",window.scrollY>20)};window.addEventListener("scroll",f,{passive:true});f()}})();</script>')
# 申込フォームがページ内にあるLPは、ヘッダーのボタンをそのフォームへ
CTA = {
    "starter/index.html": ("#apply", "無料オンライン説明"),
    "security/index.html": ("#apply", "無料オンライン説明"),
    "drill/index.html": ("#apply", "無料で相談する"),
    "fde/index.html": ("#contact", "無料相談"),
    "en/fde/index.html": ("#contact", "Free Consultation"),
    "en/starter/index.html": ("#apply", "Free Online Briefing"),
    "en/security/index.html": ("#apply", "Free Online Briefing"),
    "en/drill/index.html": ("#apply", "Talk to us free"),
}
# 日英の対になるページ（2026-10-18 英語版を主要10ページに広げた）。en_check.py もこれを使う
EN_PAIRS = {"index.html": "en/index.html", "fde/index.html": "en/fde/index.html", "entry.html": "en/entry.html",
            "company.html": "en/company.html", "drill/index.html": "en/drill/index.html",
            "security/index.html": "en/security/index.html", "starter/index.html": "en/starter/index.html",
            "recruit.html": "en/recruit.html", "privacy.html": "en/privacy.html", "legal.html": "en/legal.html"}
ALT = {}  # 言語切替の行き先。page_url の定義後に EN_PAIRS から埋める



def page_url(path):
    p = path.replace("\\", "/")
    if p == "index.html":
        return "/"
    if p.endswith("/index.html"):
        return "/" + p[:-len("index.html")]
    return "/" + p[:-len(".html")]


for _ja, _en in EN_PAIRS.items():
    ALT[_ja], ALT[_en] = page_url(_en), page_url(_ja)


def header(path, cls):
    path = path.replace("\\", "/")
    lang = lang_of(path)
    with open(os.path.join(CHROME, f"header_{lang}.html"), encoding="utf-8") as f:
        h = f.read().strip()
    href, label = CTA.get(path, ("/en/entry", "Free Consultation") if lang == "en" else ("/entry", "無料相談"))
    alt = ALT.get(path, "/" if lang == "en" else "/en/")
    h = h.replace("{{CLASS}}", cls).replace("{{CTA_HREF}}", href).replace("{{CTA_LABEL}}", label).replace("{{ALT}}", alt)
    url = page_url(path)
    # 記事や各社ページの中でも、上の階層のメニュー（ブログ／企業分析）を今いる場所として示す
    key = "/blog/" if url.startswith("/blog/") else "/cases/" if url.startswith("/cases/") else url
    return h.replace('<a href="%s">' % key, '<a href="%s" aria-current="page">' % key, 1)


def own_nav_js(html):
    """ページ自身がメニューの開閉を持っているか（共通スクリプトと二重に付けると開かなくなる）"""
    body = NAVJS_RE.sub("", html)
    return bool(re.search(r"getElementById\(\s*['\"]navToggle", body))


def related(path):
    own = RELATED.get(path.replace("\\", "/"))
    if not own:
        return None
    with open(os.path.join(CHROME, f"related_{lang_of(path)}.html"), encoding="utf-8") as f:
        block = f.read().strip()
    return re.sub(r'\s*<li><a href="%s">.*?</li>' % re.escape(own), "", block, flags=re.S)


def wrap_title(text):
    parts = PHRASE_RE.findall(text)
    if len(parts) < 2:
        return text
    return "".join('<span class="nb">%s</span>' % x for x in parts)


def bad_titles(html):
    return [t for rx in WRAP_RES for _, t, _ in rx.findall(html) if len(PHRASE_RE.findall(t)) >= 2]


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
    hm = HEADER_RE.search(html)
    if hm and path:
        if norm(hm.group(0)) != norm(header(path, hm.group(1))):
            return False, "ヘッダーが共通部品と違う"
        if not own_nav_js(html) and not NAVJS_RE.search(html):
            return False, "メニューの開閉スクリプトが無い"
    rel = related(path)
    if rel is not None:
        m2 = REL_RE.search(html)
        if not m2 or norm(m2.group(0)) != norm(rel):
            return False, "「ほかのサービス」が無いか、正本と違う"
    bt = bad_titles(html)
    if bt:
        return False, "見出しが句の途中で折れる（nb で包んでいない）: " + bt[0]
    lp = long_phrases(html)
    if lp:
        return False, "サービスの説明文の句が長く、スマホで句の中が折れる（句を分けるか言い換える）: " + lp[0]
    return True, "OK"


def apply_html(html, lang, path=""):
    if not FOOTER_RE.search(html):
        return html
    nl = "\r\n" if "\r\n" in html else "\n"
    foot = partial(lang).replace("\n", nl)
    html = FOOTER_RE.sub(lambda m: foot, html, count=1)
    hm = HEADER_RE.search(html)
    if hm and path:
        html = HEADER_RE.sub(lambda m: header(path, m.group(1)).replace("\n", nl), html, count=1)
        html = NAVJS_RE.sub("", html)
        if not own_nav_js(html):
            html = html.replace("</header>", "</header>" + nl + NAVJS, 1)
    rel = related(path)
    if rel is not None:
        html = REL_RE.sub("", html)
        html = html.replace('<footer class="footer">', rel.replace("\n", nl) + nl + nl + '<footer class="footer">', 1)
    for rx in WRAP_RES:
        html = rx.sub(lambda m: m.group(1) + wrap_title(m.group(2)) + m.group(3), html)
    return ZEN_RE.sub(lambda m: m.group(1) + ZEN_VERSION, html)


def selftest():
    """検査そのものが緩められていないか（既知NGが落ち、既知OKが通るか）。gate.py は selftest.py
    を先に回すが、selftest.py は並行セッションの編集と衝突しやすいので、ここに同居させる。"""
    ng, _ = check_html('<footer class="footer"><a href="/#fde">FDEとは</a></footer>', "ja")
    ok, _ = check_html(partial("ja"), "ja")
    ng2, _ = check_html(partial("ja") + '<h2 class="section-title">AIは使いたい。でも、出せない。</h2>', "ja")
    ng3, _ = check_html(partial("ja") + '<span class="svc-desc">現場に入り、直せる形で渡します。</span>', "ja")
    ng4, _ = check_html(partial("ja") + '<span class="svc-desc"><span class="nb">最後は御社の中で直せる形で渡します。</span></span>', "ja")
    if ng is not False or ok is not True or ng2 is not False or ng3 is not False or ng4 is not False:
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
