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

⚠ PDF出典を足した理由（2026-09-02・夕タスクの検収で発見）:
賃上げ促進税制の記事は出典3本のうち2本が中小企業庁のPDFで、その2本とも「未確認
（取得できず）」で素通りしていた。原因は取得の失敗ではなく、**PDFに <title> タグが
無い**こと——`page_title()` が None を返し、捏造でも実在でも同じ「未確認」に落ちる。
うちは補助金・税制の記事を書くので官公庁の一次情報はPDFが主で、つまりこの検査は
**一番捏造されやすい出典の型をまるごと見ていなかった**。ずっと緑なら検査を疑う
（[[feedback_broken_gate_hides_violations]]）。PDFの題名の出所は次の順に当たる:
  ① PDFのメタデータ /Title  ② PDF本文（先頭3ページ）  ③ そのPDFを載せている
  同一ホストのHTMLページのリンク表記（参考枠に一緒に挙げた索引ページ、または
  URLを1つ上に辿ったページ）
③まで要るのは、PDFの題名が本文に書かれていない場合があるため。実例＝中小企業庁の
「「賃上げ促進税制」パンフレット（令和8年6月時点版）」は、その文字列がPDFの中に
一度も出てこない（掲載ページ側のリンク表記が正）。ここを本文一致だけで判定すると
正しい出典をNGにするので、③を根拠として認める。
どれにも当たらなければ NG にせず「要目視」で件数を出す（誤検出で運用を止めない）。
ただし**PDFが取得できない・PDFではない**は NG にする（リンク切れと捏造URLはここで出る）。

使い方:
    python scripts/source_title_check.py blog/<記事>.html
    python scripts/source_title_check.py            # blog/ の最新1本
"""
import glob
import html as htmllib
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UA = "Mozilla/5.0 (compatible; ngraph-source-check/1.0)"
TIMEOUT = 25


def fetch(url, limit=8_000_000, tries=3):
    """(本文バイト列, Content-Type, 失敗の種別) を返す。成功なら種別は None。

    PDFは数MBあるので上限を大きく取る（HTMLの <title> だけが目的だった頃の
    400KB制限のままだと、PDFは途中で切れて中身を読めない）。

    ⚠ 中小企業庁は同じURLでも中身ゼロの text/html を返すことがある（連続で叩いた
    ときに出る）。**取得できないこと自体は出典の誤りではない**ので、
    「見つからない(404/410)」だけを missing、それ以外の失敗は blocked として返し、
    呼び出し側で NG と 未確認 に振り分ける。
    """
    last = "neterr"
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read(limit)
            if len(raw) < 64:
                last = "empty"
            else:
                return raw, (r.headers.get("Content-Type") or "").lower(), None
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return None, None, "missing"
            last = f"http{e.code}"
        except Exception:
            last = "neterr"
        if i < tries - 1:
            time.sleep(2 + i * 3)
    return None, None, last


def is_pdf(url, raw, ctype):
    return (ctype or "").startswith("application/pdf") or \
        (raw or b"")[:5] == b"%PDF-" or url.lower().split("?")[0].endswith(".pdf")


def pdf_titles(raw):
    """PDFから題名の候補を返す（メタデータの /Title と先頭3ページの本文）。

    pypdf が無い環境では空リストを返し、呼び出し側は「要目視」に落とす。
    """
    try:
        from pypdf import PdfReader
    except Exception:
        return []
    try:
        r = PdfReader(io.BytesIO(raw))
    except Exception:
        return []
    out = []
    try:
        if r.metadata and r.metadata.title:
            out.append(str(r.metadata.title))
    except Exception:
        pass
    for pg in r.pages[:3]:
        try:
            out.append(pg.extract_text() or "")
        except Exception:
            continue
    return [t for t in out if t]


def linked_label(index_url, pdf_url):
    """索引ページ側で、そのPDFに張られているリンクの表記を返す。取れなければ None。

    PDFの題名が本文に書かれていない場合の、正しい出所がここ。
    """
    raw, _, _ = fetch(index_url, limit=800_000)
    if raw is None:
        return None
    text = decode(raw)
    if text is None:
        return None
    tail = urllib.parse.urlparse(pdf_url).path.rsplit("/", 1)[-1]
    if not tail:
        return None
    for href, label in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.S | re.I):
        if href.split("?")[0].endswith(tail):
            return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", "", label))).strip()
    return None


def index_candidates(pdf_url, siblings):
    """そのPDFを載せていそうな同一ホストのHTMLページのURLを候補で返す。

    ①同じ記事の参考枠に一緒に挙がっている同一ホストのHTML ②PDFのURLを1つ上に辿った形。
    """
    host = urllib.parse.urlparse(pdf_url).netloc
    out = [u for u in siblings
           if urllib.parse.urlparse(u).netloc == host and not u.lower().split("?")[0].endswith(".pdf")]
    base = pdf_url.rsplit("/", 1)[0]
    out += [base + ".html", base + "/", base + "/index.html"]
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def decode(raw):
    for enc in ("utf-8", "cp932", "euc-jp", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return None


def page_title(url):
    """ページの <title> を返す。取れなければ None。"""
    raw, _, _ = fetch(url, limit=400_000)
    if raw is None:
        return None
    text = decode(raw)
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


def check_pdf(rel, text, url, siblings):
    """PDF出典を見る。戻り値は 'ok' / 'ng' / 'eye'（要目視）/ 'unknown'。"""
    raw, ctype, err = fetch(url)
    if err == "missing":
        print(f"  NG {rel}")
        print(f"     PDFが存在しない（404）: {text}")
        print(f"     {url}")
        return "ng"
    if raw is None:
        print(f"  ? 未確認（取得できず・{err}） {text} -> {url}")
        return "unknown"
    if not is_pdf(url, raw, ctype):
        print(f"  NG {rel}")
        print(f"     PDFとして出典に挙げているが、返ってきたのはPDFではない: {text}")
        print(f"     {url}")
        return "ng"

    cands = pdf_titles(raw)
    for c in cands:
        if matches(text, c):
            print(f"  OK {text}（PDFの中身と一致）")
            return "ok"

    for idx in index_candidates(url, siblings):
        label = linked_label(idx, url)
        if label and matches(text, label):
            print(f"  OK {text}（掲載ページのリンク表記と一致: {idx}）")
            return "ok"
        if label:
            print(f"  NG {rel}")
            print(f"     書いてある題名  : {text}")
            print(f"     掲載ページの表記: {label}")
            print(f"     {idx}")
            return "ng"

    print(f"  △ 要目視（PDF本文にも掲載ページにも題名が見つからない） {text}")
    print(f"     {url}")
    if not cands:
        print("     ※PDFの文字を取り出せていない可能性（画像PDF、または pypdf が無い）")
    return "eye"


def check(path):
    rel = os.path.relpath(path, ROOT).replace("\\", "/")
    links = src_links(path)
    if not links:
        print(f"  {rel}: 参考枠に外部リンクが無い")
        return 0, 0, 0
    ng = unknown = eye = 0
    urls = [u for _, u in links]
    for i, (text, url) in enumerate(links):
        if i:
            time.sleep(1.5)  # 官公庁サイトは連続で叩くと中身ゼロを返す。間を空ける
        if url.lower().split("?")[0].endswith(".pdf"):
            r = check_pdf(rel, text, url, urls)
            ng += r == "ng"
            eye += r == "eye"
            unknown += r == "unknown"
            continue
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
    return ng, unknown, eye


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

    total_ng = total_unknown = total_eye = 0
    for t in targets:
        if not os.path.exists(t):
            print(f"NG: ファイルが無い {t}")
            total_ng += 1
            continue
        ng, unknown, eye = check(t)
        total_ng += ng
        total_unknown += unknown
        total_eye += eye

    if total_ng:
        print(f"\nNG: 出典の題名が実際のページと違う {total_ng}件。"
              "実際の題名をそのまま貼ること（URLから題名を作らない）")
        return 1
    print(f"\nOK: 出典の題名は実在のページと一致"
          f"（未確認 {total_unknown}件・要目視 {total_eye}件）")
    if total_eye:
        print("   要目視は、PDFを開いて表紙の題名を自分の目で突き合わせること")
    return 0


if __name__ == "__main__":
    sys.exit(main())
