#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""記事の配線漏れを機械で止める（push前ゲート・BLOG-OPS §6）。

url_canon.py が「URLの形」を見るのに対し、こちらは「載せ忘れ」を見る。
新記事を書いたあと、blog/index.html・sitemap.xml・llms.txt へ手で追記する運用なので、
どれか1つを忘れても誰も気付かない。実際 2026-08-08 の監査で llms.txt が5記事漏れていた。

検査項目:
  1. blog/*.html と sitemap.xml の <loc> が1:1（漏れ・余剰・重複なし）
  2. blog/*.html が llms.txt のブログ一覧に全部載っている
  3. sitemap の /blog/ (一覧ページ) の lastmod が最新記事の日付と一致
     ——一覧は記事を足すたびに中身が変わるのに、lastmod が置き去りになりやすい
  4. アイキャッチ画像 (.a-eyecatch) の alt が空でない
     ——空altは「装飾画像」の意味になる。アイキャッチは内容を持つ画像なので誤り
     （ロゴの alt="" は隣に文字があるので正しい。ここでは対象にしない）

使い方:
    python scripts/publish_check.py --check   # 違反を列挙して exit 1
    python scripts/publish_check.py --fix     # 直せるものを直す
"""
import argparse
import datetime
import html
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://ngraph.jp"
BLOG = ROOT / "blog"
SITEMAP = ROOT / "sitemap.xml"
LLMS = ROOT / "llms.txt"

LLMS_SECTION = "## ブログ（AI導入の実践知）"
DATED = re.compile(r"^(\d{4})(\d{2})(\d{2})-")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import published_set  # noqa: E402

UNPUBLISHED = []


def articles():
    """記事slugの一覧（index.html は一覧ページなので除く）。

    gitに入っていない記事は本番に存在しないので対象外（published_set.py 参照）。
    除外したものは main() が「参考」として必ず表示する。
    """
    found = sorted(p.stem for p in BLOG.glob("*.html") if p.stem != "index")
    kept, skipped = published_set.split_unpublished(found)
    UNPUBLISHED[:] = skipped
    return kept


def slug_date(slug):
    """20260803-foo -> 2026-08-03。日付を持たない恒久記事は None。"""
    m = DATED.match(slug)
    return "%s-%s-%s" % m.groups() if m else None


def h1_of(slug):
    src = (BLOG / (slug + ".html")).read_text(encoding="utf-8")
    m = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
    if not m:
        return None
    text = re.sub(r"<[^>]+>", "", m.group(1))
    return html.unescape(" ".join(text.split()))


def sitemap_locs():
    xml = SITEMAP.read_text(encoding="utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def latest_article_date():
    """最新記事の日付。sitemap の /blog/ の lastmod はこれと一致すべき。"""
    dates = [d for d in (slug_date(s) for s in articles()) if d]
    return max(dates) if dates else None


# ---------------------------------------------------------------- 検査


def check_sitemap():
    locs = sitemap_locs()
    dup = sorted({u for u in locs if locs.count(u) > 1})
    blog_locs = [u for u in locs if u.startswith(SITE + "/blog/") and u != SITE + "/blog/"]
    have = {u.rsplit("/", 1)[-1] for u in blog_locs}
    want = set(articles())

    out = []
    for s in sorted(want - have):
        out.append("sitemap.xml に無い記事: %s/blog/%s" % (SITE, s))
    for s in sorted(have - want):
        out.append("sitemap.xml にあるが記事ファイルが無い: %s/blog/%s" % (SITE, s))
    for u in dup:
        out.append("sitemap.xml に重複: %s" % u)
    if SITE + "/blog/" not in locs:
        out.append("sitemap.xml に一覧ページ %s/blog/ が無い" % SITE)
    return out


def check_llms():
    text = LLMS.read_text(encoding="utf-8")
    return [
        "llms.txt に無い記事: %s/blog/%s" % (SITE, s)
        for s in articles()
        if ("%s/blog/%s)" % (SITE, s)) not in text
    ]


def check_blog_lastmod():
    latest = latest_article_date()
    if not latest:
        return []
    xml = SITEMAP.read_text(encoding="utf-8")
    m = re.search(r"<loc>%s/blog/</loc>\s*<lastmod>([\d-]+)</lastmod>" % re.escape(SITE), xml)
    if not m:
        return ["sitemap.xml の %s/blog/ に lastmod が無い" % SITE]
    if m.group(1) != latest:
        return [
            "sitemap.xml の一覧ページ lastmod が古い: %s → 最新記事は %s"
            % (m.group(1), latest)
        ]
    return []


def check_alt():
    out = []
    for slug in articles():
        src = (BLOG / (slug + ".html")).read_text(encoding="utf-8")
        for m in re.finditer(r'<img[^>]*class="a-eyecatch"[^>]*>', src):
            tag = m.group(0)
            alt = re.search(r'\balt="([^"]*)"', tag)
            if alt is None or not alt.group(1).strip():
                out.append("アイキャッチの alt が空: blog/%s.html" % slug)
    return out


CSS = ROOT / "css" / "ngraph-zen.css"
CSS_REF = re.compile(r"ngraph-zen\.css\?v=(\d+)")


def check_css_version():
    """共有CSSのキャッシュバスター `?v=N` が全ページで揃っているかを見る。

    2026-08-08: 共有CSSを直したのに全ページが `?v=6` のままで、本番のCSSは新しいのに
    既存訪問者のブラウザは古いCSSを使い続ける状態になった（CDNではなくブラウザキャッシュ）。
    「本番に出た＝直った」ではないので、ここで揃っていることだけは機械で保証する。
    **CSSを変えたら v を上げる**のは人の判断（見た目に影響しない変更まで上げると無駄なので）。
    """
    if not CSS.exists():
        return []
    versions = {}
    for p in sorted(ROOT.rglob("*.html")):
        if p.name in {"index-old.html", "ngraph-lp-v3.html"} or "__pycache__" in p.parts:
            continue
        for m in CSS_REF.finditer(p.read_text(encoding="utf-8")):
            versions.setdefault(m.group(1), []).append(p.relative_to(ROOT).as_posix())
    if len(versions) <= 1:
        return []
    detail = " / ".join(
        "v=%s %d件(例 %s)" % (v, len(f), f[0]) for v, f in sorted(versions.items())
    )
    return [
        "共有CSSの ?v= が揃っていません（古い方のページだけ旧CSSで表示される）: " + detail
    ]


CHECKS = [check_sitemap, check_llms, check_blog_lastmod, check_alt, check_css_version]


# ---------------------------------------------------------------- 修正


def fix_alt():
    changed = []
    for slug in articles():
        path = BLOG / (slug + ".html")
        src = path.read_text(encoding="utf-8")
        title = h1_of(slug)
        if not title:
            continue

        def sub(m):
            tag = m.group(0)
            a = re.search(r'\balt="([^"]*)"', tag)
            if a and a.group(1).strip():
                return tag
            esc = html.escape(title, quote=True)
            if a:
                return tag[: a.start(1)] + esc + tag[a.end(1) :]
            return tag[:-1] + ' alt="%s">' % esc

        dst = re.sub(r'<img[^>]*class="a-eyecatch"[^>]*>', sub, src)
        if dst != src:
            path.write_text(dst, encoding="utf-8")
            changed.append("blog/%s.html" % slug)
    return changed


def fix_blog_lastmod():
    latest = latest_article_date()
    if not latest:
        return []
    xml = SITEMAP.read_text(encoding="utf-8")
    pat = re.compile(r"(<loc>%s/blog/</loc>\s*<lastmod>)[\d-]+(</lastmod>)" % re.escape(SITE))
    dst, n = pat.subn(r"\g<1>%s\g<2>" % latest, xml)
    if n and dst != xml:
        SITEMAP.write_text(dst, encoding="utf-8")
        return ["sitemap.xml: /blog/ の lastmod を %s に更新" % latest]
    return []


def fix_sitemap_missing():
    locs = sitemap_locs()
    have = {u.rsplit("/", 1)[-1] for u in locs if u.startswith(SITE + "/blog/")}
    missing = [s for s in articles() if s not in have]
    if not missing:
        return []
    xml = SITEMAP.read_text(encoding="utf-8")
    today = datetime.date.today().isoformat()
    rows = "".join(
        "  <url><loc>%s/blog/%s</loc><lastmod>%s</lastmod></url>\n"
        % (SITE, s, slug_date(s) or today)
        for s in missing
    )
    SITEMAP.write_text(xml.replace("</urlset>", rows + "</urlset>"), encoding="utf-8")
    return ["sitemap.xml に%d件追記: %s" % (len(missing), ", ".join(missing))]


def fix_llms_missing():
    text = LLMS.read_text(encoding="utf-8")
    lines = text.splitlines()
    try:
        start = lines.index(LLMS_SECTION) + 1
    except ValueError:
        return ["llms.txt にブログ節（%s）が見つからない" % LLMS_SECTION]
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines)
    )
    # 節末の空行は次の見出しとの区切り。ここへ挿し込むと見出しに行がくっついて
    # 節の境界が壊れるので、空行の手前を「節の終わり」とする
    while end > start and not lines[end - 1].strip():
        end -= 1

    def slug_of(line):
        m = re.search(r"%s/blog/([A-Za-z0-9._-]+)\)" % re.escape(SITE), line)
        return m.group(1) if m else None

    present = {slug_of(l) for l in lines[start:end]}
    missing = [s for s in articles() if s not in present]
    if not missing:
        return []

    added = []
    for slug in missing:
        title = h1_of(slug) or slug
        line = "- [%s](%s/blog/%s)" % (title, SITE, slug)
        date = slug_date(slug)
        pos = end  # 恒久記事（日付なしslug）は節の末尾へ
        if date:
            # 日付付きは新しい順に並べる。自分より古い最初の記事の直前へ。
            # 見つからない＝既存のどれより古い場合は、恒久記事の後ろに落ちないよう
            # 「最後の日付付き記事の直後」に入れる（日付ブロックと恒久ブロックを混ぜない）
            last_dated = None
            pos = None
            for i in range(start, end):
                s = slug_of(lines[i])
                d = slug_date(s) if s else None
                if not d:
                    continue
                last_dated = i
                if d < date and pos is None:
                    pos = i
            if pos is None:
                pos = last_dated + 1 if last_dated is not None else end
        lines.insert(pos, line)
        end += 1
        added.append(slug)

    LLMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ["llms.txt に%d件追記: %s" % (len(added), ", ".join(added))]


FIXES = [fix_sitemap_missing, fix_llms_missing, fix_blog_lastmod, fix_alt]


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="違反を列挙して exit 1")
    g.add_argument("--fix", action="store_true", help="直せるものを直す")
    args = ap.parse_args()

    if args.fix:
        done = [msg for fn in FIXES for msg in fn()]
        memo = published_set.note(UNPUBLISHED, indent="  ")
        if memo:
            print(memo)
        if not done:
            print("修正するものはありません")
        for d in done:
            print("  " + d)
        return 0

    violations = [v for fn in CHECKS for v in fn()]
    memo = published_set.note(UNPUBLISHED, indent="  ")
    if memo:
        print(memo)
    if violations:
        print("記事の配線に漏れがあります:")
        for v in violations:
            print("  " + v)
        print(
            "\n%d件。多くは `python scripts/publish_check.py --fix` で直せます"
            "（CSSの ?v= だけは人が判断して上げる）。" % len(violations)
        )
        return 1
    print("OK: sitemap / llms.txt / alt はすべて揃っています")
    return 0


if __name__ == "__main__":
    sys.exit(main())
