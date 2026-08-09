# -*- coding: utf-8 -*-
"""朝A型ブログ記事を X Articles の下書きとして作成する（B型＝短信を落とした構成）

使い方:
  python scripts/x_article.py <slug> --teaser "<短信予告の1段落>"
  python scripts/x_article.py <slug> --teaser "..." --dry-run   # APIを叩かずJSONだけ出す

  <slug> は拡張子なし。例: 20260801-ai-agent-permission

作るもの（BLOG-OPS §7 のB型）:
  リード → H2×3（何が起きたか / なぜ重要か / 中小企業は何をすべきか）
  → NGraphの視点（/fde/ への一文は落とす）→ 参考（一次情報・メイン1本のみ）
  → 短信予告（--teaser）＋ 本家記事へのリンク

公開はしない。下書きまで作って article_id を返す。キャプションを入れて「公開」を
押すのは人の手（BLOG-OPS §7 の運用方針）。--publish を付けたときだけ公開する。

認証キーは x_post.py と同じ C:/Users/shing/.ngraph/x_keys.env から読む。
キーが無い場合は何も送らず exit 3。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from bs4 import BeautifulSoup, NavigableString

sys.stdout.reconfigure(encoding="utf-8")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xcount import X_TITLE_MAX, over_by, use_utf8_stdio, x_weighted_len
KEYS_PATH = os.path.expanduser("~/.ngraph/x_keys.env")
SITE = "https://ngraph.jp"
MEDIA_URL = "https://api.x.com/2/media/upload"
DRAFT_URL = "https://api.x.com/2/articles/draft"
PUBLISH_URL = "https://api.x.com/2/articles/{article_id}/publish"

EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

# 記事本文の図（.a-fig-wrap 内のインラインSVG）をX添付用のPNGにするときの台紙。
# 本文のSVGは --bare（地色・枠・見出し・署名なし）なので、ここで単体1枚に仕立て直す。
FIG_CARD = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#f6f2e9}
body{width:%(w)dpx;height:%(h)dpx;overflow:hidden;font-family:'Zen Kaku Gothic New',sans-serif}
.card{position:relative;height:100%%;padding:44px 52px 34px}
.card::before{content:"";position:absolute;inset:22px;border:1px solid rgba(166,58,36,.24);pointer-events:none}
h1{font-family:'Zen Old Mincho',serif;font-weight:900;font-size:40px;line-height:1.34;
   color:#2b2620;text-align:center;margin-bottom:26px}
svg{display:block;width:100%%;height:auto}
.sig{margin-top:22px;text-align:right;font-family:'Zen Old Mincho',serif;
     font-size:18px;font-weight:700;color:#8a8172}
</style></head><body><div class="card"><h1>%(title)s</h1>%(svg)s
<div class="sig">NGraph. ngraph.jp</div></div></body></html>"""


def fig_height(title, svg, w=1200):
    """台紙の高さを中身から決める（固定だと図の下に死んだ余白が残る）。"""
    inner = w - 52 * 2                      # .card の左右padding
    m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
    svg_h = float(m.group(2)) * inner / float(m.group(1)) if m else 560.0
    lines = max(1, -(-len(title) // max(1, int(inner / 40))))   # 40px和文＝1文字40px相当
    return int(44 + lines * 54 + 26 + svg_h + 22 + 27 + 34)


def render_fig(title, svg, out, w=1200):
    """図1点をPNGで書き出す。ブラウザペイン起動中でも落ちないよう毎回使い捨てプロファイルを使う。"""
    tmpdir = tempfile.gettempdir()
    stamp = int(time.time() * 1000)
    src = os.path.join(tmpdir, "ngxfig_%d.html" % stamp)
    png = os.path.join(tmpdir, "ngxfig_%d.png" % stamp)
    h = fig_height(title, svg, w)
    open(src, "w", encoding="utf-8").write(
        FIG_CARD % {"w": w, "h": h, "title": esc(title), "svg": svg})
    for _ in range(3):
        udd = tempfile.mkdtemp(prefix="ngxfig_udd_")
        subprocess.run([EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--disable-dev-shm-usage", "--hide-scrollbars",
                        "--user-data-dir=" + udd, "--window-size=%d,%d" % (w, h),
                        "--virtual-time-budget=10000", "--screenshot=" + png,
                        "file:///" + src.replace("\\", "/")],
                       check=False, capture_output=True)
        for _ in range(6):
            if os.path.exists(png) and os.path.getsize(png) > 5000:
                break
            time.sleep(1)
        if os.path.exists(png) and os.path.getsize(png) > 5000:
            break
    # returncode ではなく出力ファイルの実サイズで判定する（Edgeは無言で失敗する）
    if not (os.path.exists(png) and os.path.getsize(png) > 5000):
        sys.exit(f"図の書き出しに失敗した: {out}（Edgeのパスを確認）")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    shutil.copyfile(png, out)
    os.remove(src)
    os.remove(png)


# B型に載せるH2（この3つだけ。「その他の注目ニュース」は本家記事に残す）
KEEP_HEADINGS = ("何が起きたか", "なぜ重要か", "中小企業は何をすべきか")
# NGraphの視点から落とす一文（Xでは末尾の記事リンクに導線を一本化する）
CTA_SENTENCE = re.compile(r"この分野の導入相談は.*$")


# ---------------------------------------------------------------- HTML 解析

def abs_url(href):
    if href.startswith("/"):
        return SITE + href
    return href


def inline(node, text, styles, ranges, entities):
    """1ブロック分のインライン要素を歩いて text/太字/リンク を積む。

    DraftJS のオフセットは UTF-16 コードユニット。日本語(BMP)は1文字=1ユニットで
    Python の len() と一致する。絵文字(サロゲートペア)を本文に入れるとズレるので入れない。
    """
    for child in node.children:
        if isinstance(child, NavigableString):
            # 連続空白の圧縮はここでやる。オフセットを積んだ後に本文を縮めるとリンク位置がズレる
            text.append(re.sub(r"\s+", " ", str(child)))
            continue
        name = child.name
        start = sum(len(t) for t in text)
        inline(child, text, styles, ranges, entities)
        length = sum(len(t) for t in text) - start
        if length == 0:
            continue
        if name in ("strong", "b"):
            styles.append({"offset": start, "length": length, "style": "bold"})
        elif name in ("em", "i"):
            styles.append({"offset": start, "length": length, "style": "italic"})
        elif name == "a" and child.get("href"):
            key = str(len(entities))
            entities.append({
                "key": key,
                "value": {
                    "type": "link",
                    "mutability": "mutable",
                    "data": {"url": abs_url(child["href"])},
                },
            })
            ranges.append({"offset": start, "length": length, "key": key})


def drop(body, ranges, i, n=1):
    """本文の i から n 文字を削り、リンク・太字の範囲を追従させる。"""
    body = body[:i] + body[i + n:]
    for r in ranges:
        end = r["offset"] + r["length"]
        if r["offset"] >= i + n:
            r["offset"] -= n
        elif r["offset"] > i:
            r["length"] -= r["offset"] - i
            r["offset"] = i
        if end > i:
            r["length"] = max(0, min(r["length"], len(body) - r["offset"]))
    return body


def tidy(body, ranges):
    """圧縮しきれなかった連続空白と前後の空白を、オフセットを追従させながら落とす。"""
    while True:
        m = re.search(r"  +", body)
        if not m:
            break
        body = drop(body, ranges, m.start(), m.end() - m.start() - 1)
    while body.startswith(" "):
        body = drop(body, ranges, 0)
    while body.endswith(" "):
        body = drop(body, ranges, len(body) - 1)
    return body


def block(el, block_type, entities):
    text, styles, ranges = [], [], []
    inline(el, text, styles, ranges, entities)
    body = tidy("".join(text), styles + ranges)
    return {
        "key": f"b{abs(hash(body)) % 10**8:08d}",
        "type": block_type,
        "text": body,
        "inline_style_ranges": [r for r in styles if r["length"] > 0],
        "entity_ranges": [r for r in ranges if r["length"] > 0],
        "data": {},
    }


# Xの記事は1段落が長いと読まれない（2026-08-08 髙橋さん「本文が続きまくって読みにくい」）。
# 句点で区切って、目安この文字数を超えたら段落を割る。
SPLIT_TARGET = 120


def split_long(b, target=SPLIT_TARGET):
    """長い段落を句点の直後で複数ブロックに割る。太字・リンクのオフセットは割った位置ぶん詰め直す。"""
    if b["type"] != "unstyled":
        return [b]
    text = b["text"]
    if len(text) <= target * 1.5:
        return [b]
    ranges = b["inline_style_ranges"] + b["entity_ranges"]
    # 太字・リンクの途中では割らない（DraftJSのオフセットが壊れるため）
    cuts = [m.end() for m in re.finditer("。", text)]
    cuts = [c for c in cuts if c < len(text)
            and all(not (r["offset"] < c < r["offset"] + r["length"]) for r in ranges)]
    if not cuts:
        return [b]

    bounds, start = [], 0
    for c in cuts:
        if c - start >= target:
            bounds.append((start, c))
            start = c
    if start < len(text):
        if bounds and len(text) - start < 20:
            bounds[-1] = (bounds[-1][0], len(text))   # 数文字の尻尾だけ前の段落へ吸収
        else:
            bounds.append((start, len(text)))

    # 一文が長すぎて句点で割れなかった段落は、読点で真ん中あたりを割る
    hard = target * 1.5
    commas = [m.end() for m in re.finditer("、", text)
              if all(not (r["offset"] < m.end() < r["offset"] + r["length"]) for r in ranges)]
    grown = []
    for s, e in bounds:
        while e - s > hard:
            mid = (s + e) // 2
            c = min((x for x in commas if s + 40 < x < e - 40),
                    key=lambda x: abs(x - mid), default=None)
            if c is None:
                break
            grown.append((s, c))
            s = c
        grown.append((s, e))
    bounds = grown
    if len(bounds) < 2:
        return [b]

    out = []
    for i, (s, e) in enumerate(bounds):
        seg = text[s:e]
        shift = lambda rs: [dict(r, offset=r["offset"] - s) for r in rs
                            if s <= r["offset"] < e]
        out.append({
            "key": f"b{abs(hash(seg)) % 10**8:08d}{i}",
            "type": "unstyled",
            "text": seg,
            "inline_style_ranges": shift(b["inline_style_ranges"]),
            "entity_ranges": shift(b["entity_ranges"]),
            "data": {},
        })
    return out


def text_block(body, block_type="unstyled", bold_prefix=None, link=None, entities=None):
    """プレーンな文字列から1ブロック作る（先頭太字・全体リンクだけ対応）。"""
    styles, ranges = [], []
    if bold_prefix and body.startswith(bold_prefix):
        styles.append({"offset": 0, "length": len(bold_prefix), "style": "bold"})
    if link:
        key = str(len(entities))
        entities.append({
            "key": key,
            "value": {"type": "link", "mutability": "mutable", "data": {"url": link}},
        })
        ranges.append({"offset": 0, "length": len(body), "key": key})
    return {
        "key": f"b{abs(hash(body)) % 10**8:08d}",
        "type": block_type,
        "text": body,
        "inline_style_ranges": styles,
        "entity_ranges": ranges,
        "data": {},
    }


def table_blocks(wrap, entities):
    """表を箇条書きに開く。X記事エディタは表を持てないので、行を1項目にたたむ。

    1行目を見出し行として扱い、「1列目 — 見出し2 値2／見出し3 値3」の形にする。
    1列目は太字。見出し行が無い表（th無し）は先頭行も本文として扱う。
    """
    table = wrap if getattr(wrap, "name", None) == "table" else wrap.find("table")
    if table is None:
        return []
    rows = [[c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            for tr in table.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    heads = rows[0] if table.find("th") else []
    body = rows[1:] if heads else rows
    out = []
    for row in body:
        label = row[0]
        rest = []
        for i, cell in enumerate(row[1:], start=1):
            if not cell:
                continue
            head = heads[i] if i < len(heads) else ""
            rest.append(f"{head} {cell}".strip())
        text = label + ("　" + "／".join(rest) if rest else "")
        out.append(text_block(text, "unordered-list-item",
                              bold_prefix=label, entities=entities))
    return out


def first_reference(art):
    """.a-src は <br> 区切りの行の集まり。外部リンクを含む最初の行のノード列を返す。"""
    src = art.find("div", class_="a-src")
    if src is None:
        return None
    line = []
    for node in src.children:
        if getattr(node, "name", None) == "br":
            if any(getattr(n, "name", None) == "a" and not n.get("href", "/").startswith("/")
                   for n in line):
                return line
            line = []
            continue
        line.append(node)
    return None


def ref_block(nodes, entities):
    """参考行を1ブロックに。行頭の「・」は落とし、タイトル部分だけリンクにする。"""
    holder = BeautifulSoup("<div></div>", "html.parser").div
    for n in nodes:
        holder.append(n.__copy__() if hasattr(n, "__copy__") else NavigableString(str(n)))
    b = block(holder, "unstyled", entities)
    if b["text"].startswith("・"):
        b["text"] = drop(b["text"], b["inline_style_ranges"] + b["entity_ranges"], 0)
    return b


def build(slug, teaser, heads=None, mark_figs=False):
    path = os.path.join(REPO, "blog", f"{slug}.html")
    if not os.path.exists(path):
        sys.exit(f"記事が見つかりません: {path}")
    soup = BeautifulSoup(open(path, encoding="utf-8").read(), "html.parser")
    art = soup.find("article", class_="article-wrap")
    if art is None:
        sys.exit("article.article-wrap が見つかりません（記事の雛形か確認）")
    keep = tuple(heads) if heads else KEEP_HEADINGS

    title = art.find("h1").get_text(strip=True)
    blocks, entities, figs = [], [], []

    def take_fig(wrap):
        """本文の図を1点拾う。

        既定（mark_figs=False）は図を載せず、本家記事に残す〔髙橋さん 2026-08-08「一旦図は無しで行くか」〕。
        Xは貼り付けで画像が入らず、1点ごとに挿入操作が要るため手間に見合わないという判断。
        --figs を付けたときだけ、本文に位置の目印［図N］を置いてPNGを書き出す。
        """
        svg = wrap.find("svg")
        if svg is None:
            return
        cap = wrap.find("p", class_="a-fig-title")
        figs.append({
            "n": len(figs) + 1,
            "title": cap.get_text(strip=True) if cap else f"図{len(figs) + 1}",
            "svg": str(svg),
        })
        if mark_figs:
            blocks.append(text_block(f"［図{figs[-1]['n']}］{figs[-1]['title']}",
                                     bold_prefix=f"［図{figs[-1]['n']}］", entities=entities))

    # リード（h1直後の最初の<p>）
    lead = art.find("p")
    if lead is None:
        sys.exit("リード段落が見つかりません")
    blocks.extend(split_long(block(lead, "unstyled", entities)))

    # H2×3 とその中身
    kept = 0
    for h2 in art.find_all("h2"):
        head = h2.get_text(strip=True)
        if not head.startswith(keep):
            continue
        kept += 1
        blocks.append(block(h2, "header-two", entities))
        for sib in h2.find_next_siblings():
            if sib.name == "h2":
                break
            if sib.name == "p":
                blocks.extend(split_long(block(sib, "unstyled", entities)))
            elif sib.name == "ul":
                for li in sib.find_all("li", recursive=False):
                    blocks.append(block(li, "unordered-list-item", entities))
            elif "a-fig-wrap" in (sib.get("class") or []):
                take_fig(sib)
            elif sib.name == "table" or "a-table-wrap" in (sib.get("class") or []):
                blocks.extend(table_blocks(sib, entities))
    if kept != len(keep):
        sys.exit(f"H2が想定と違います（拾えたのは{kept}個 / 期待{len(keep)}個）\n"
                 f"  指定した見出し: {' / '.join(keep)}\n"
                 f"  記事のH2: {' / '.join(h.get_text(strip=True) for h in art.find_all('h2'))}")

    # 一次体験ブロック（朝A型は「NGraphの視点」、夕B型は「現場の話」など）。
    # ラベルは .a-note 冒頭の <strong> から取る。/fde/ への一文は落とす
    note = art.find("div", class_="a-note")
    if note is not None:
        strong = note.find("strong")
        label = strong.get_text(strip=True) if strong else "NGraphの視点："
        if not label.endswith("："):
            label += "："
        body = CTA_SENTENCE.sub("", note.get_text(" ", strip=True)).strip()
        body = re.sub(r"：\s+", "：", body)
        if not body.startswith(label):
            body = label + body
        blocks.extend(split_long(text_block(body, bold_prefix=label, entities=entities)))

    # 参考（一次情報）— メインの1本だけ。「発表元「タイトル」（公開日）」の行ごと載せる
    ref = first_reference(art)
    if ref is not None:
        blocks.append(text_block("参考（一次情報）", bold_prefix="参考（一次情報）",
                                 entities=entities))
        blocks.append(ref_block(ref, entities))

    # 短信予告 ＋ 本家記事へのリンク
    blocks.append(text_block(teaser, entities=entities))
    # URLは拡張子なし（Cloudflare Pagesが /blog/x.html を /blog/x へ307する）。BLOG-OPS §8
    article_url = f"{SITE}/blog/{slug}"
    blocks.append(text_block(article_url, link=article_url, entities=entities))

    return title, {"blocks": blocks, "entities": entities}, figs


# ---------------------------------------------------------------- クリップボード

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def blocks_to_html(cs):
    """DraftJSブロックからHTMLを起こす。X記事エディタに Ctrl+V で書式ごと入る。

    DraftJS側と同じデータから起こすので、API版と手貼り版で中身がズレない。
    """
    urls = {e["key"]: e["value"]["data"]["url"] for e in cs["entities"]}
    out, in_list = [], False
    for b in cs["blocks"]:
        text = b["text"]
        # 1文字ごとに (太字か, リンク先) を持たせて、同じ装飾が続く区間でまとめる
        marks = [[False, None] for _ in text]
        for r in b["inline_style_ranges"]:
            if r["style"] == "bold":
                for i in range(r["offset"], min(r["offset"] + r["length"], len(text))):
                    marks[i][0] = True
        for r in b["entity_ranges"]:
            for i in range(r["offset"], min(r["offset"] + r["length"], len(text))):
                marks[i][1] = urls.get(r["key"])

        parts, i = [], 0
        while i < len(text):
            j = i
            while j < len(text) and marks[j] == marks[i]:
                j += 1
            chunk, (bold, url) = esc(text[i:j]), marks[i]
            if bold:
                chunk = f"<strong>{chunk}</strong>"
            if url:
                chunk = f'<a href="{esc(url)}">{chunk}</a>'
            parts.append(chunk)
            i = j
        inner = "".join(parts)

        if b["type"] == "unordered-list-item":
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inner}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        tag = {"header-two": "h2", "header-three": "h3"}.get(b["type"], "p")
        out.append(f"<{tag}>{inner}</{tag}>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def to_clipboard(html, plain):
    """CF_HTML形式でクリップボードに載せる（オフセットはUTF-8のバイト数で書く）。"""
    import subprocess
    import tempfile

    head = ("Version:0.9\r\nStartHTML:{:010d}\r\nEndHTML:{:010d}\r\n"
            "StartFragment:{:010d}\r\nEndFragment:{:010d}\r\n")
    # charset宣言が無いと受け取り側がUTF-8と解釈せず日本語が化ける
    pre = ('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
           "</head><body>\r\n<!--StartFragment-->")
    post = "<!--EndFragment-->\r\n</body></html>"
    dummy = head.format(0, 0, 0, 0)
    n = len(dummy.encode("utf-8"))
    start_html = n
    start_frag = n + len(pre.encode("utf-8"))
    end_frag = start_frag + len(html.encode("utf-8"))
    end_html = end_frag + len(post.encode("utf-8"))
    payload = head.format(start_html, end_html, start_frag, end_frag) + pre + html + post

    d = tempfile.mkdtemp()
    hp, tp = os.path.join(d, "cf.html"), os.path.join(d, "cf.txt")
    open(hp, "w", encoding="utf-8", newline="").write(payload)
    open(tp, "w", encoding="utf-8", newline="").write(plain)
    # CF_HTML は「UTF-8のバイト列」と決まっている。文字列で SetData すると .NET 側で
    # もう一度エンコードされて日本語が化けるので、MemoryStream に生バイトを入れて渡す。
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$b = [System.IO.File]::ReadAllBytes('{hp}')
$ms = New-Object System.IO.MemoryStream
$ms.Write($b, 0, $b.Length)
$t = [System.IO.File]::ReadAllText('{tp}', [System.Text.Encoding]::UTF8)
$o = New-Object System.Windows.Forms.DataObject
$o.SetData([System.Windows.Forms.DataFormats]::Html, $false, $ms)
$o.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $t)
[System.Windows.Forms.Clipboard]::SetDataObject($o, $true)
Write-Output 'CLIPBOARD_OK'
"""
    r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                       capture_output=True, text=True)
    if "CLIPBOARD_OK" not in r.stdout:
        return False, (r.stderr or "").strip()
    return verify_clipboard(html)


def verify_clipboard(html):
    """クリップボードの生バイトをWin32 APIで直接読んで検証する。

    .NET の Clipboard.GetData は CF_HTML のバイト列をシステムのANSIコードページ(cp932)で
    文字列化して返すため、読み戻しが化けて見える。生バイトを見ないと真偽が判定できない。
    """
    import ctypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    k32.GlobalLock.argtypes = [ctypes.c_void_p]
    k32.GlobalLock.restype = ctypes.c_void_p
    k32.GlobalSize.argtypes = [ctypes.c_void_p]
    k32.GlobalSize.restype = ctypes.c_size_t
    k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    u32.GetClipboardData.argtypes = [ctypes.c_uint]
    u32.GetClipboardData.restype = ctypes.c_void_p

    fmt = u32.RegisterClipboardFormatW("HTML Format")
    if not u32.OpenClipboard(None):
        return False, "クリップボードを開けませんでした"
    try:
        h = u32.GetClipboardData(fmt)
        if not h:
            return False, "CF_HTML が載っていません"
        raw = ctypes.string_at(k32.GlobalLock(h), k32.GlobalSize(h))
        k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()

    try:
        text = raw.rstrip(b"\x00").decode("utf-8")
    except UnicodeDecodeError as e:
        return False, f"UTF-8として読めません（文字化け）: {e}"
    if html[:200] not in text or html[-120:] not in text:
        return False, "内容が一致しません"
    return True, ""


# ---------------------------------------------------------------- X API

def load_keys():
    if not os.path.exists(KEYS_PATH):
        return None
    keys = {}
    for line in open(KEYS_PATH, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    need = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    return keys if all(keys.get(k) for k in need) else None


def session(keys):
    from requests_oauthlib import OAuth1Session
    return OAuth1Session(
        keys["X_API_KEY"],
        client_secret=keys["X_API_SECRET"],
        resource_owner_key=keys["X_ACCESS_TOKEN"],
        resource_owner_secret=keys["X_ACCESS_TOKEN_SECRET"],
    )


def die(label, r):
    sys.exit(f"ERROR {label} {r.status_code}: {r.text[:500]}")


def upload_cover(s, path):
    """INIT → APPEND → FINALIZE。アイキャッチは200KB前後なので1チャンクで足りる。"""
    total = os.path.getsize(path)
    r = s.post(MEDIA_URL, data={
        "command": "INIT", "media_type": "image/jpeg",
        "total_bytes": total, "media_category": "tweet_image",
    }, timeout=60)
    if r.status_code not in (200, 201, 202):
        die("media INIT", r)
    media_id = r.json()["data"]["id"]

    with open(path, "rb") as f:
        r = s.post(MEDIA_URL, data={"command": "APPEND", "media_id": media_id,
                                    "segment_index": 0}, files={"media": f}, timeout=120)
    if r.status_code not in (200, 201, 202, 204):
        die("media APPEND", r)

    r = s.post(MEDIA_URL, data={"command": "FINALIZE", "media_id": media_id}, timeout=60)
    if r.status_code not in (200, 201):
        die("media FINALIZE", r)
    return media_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--teaser", required=True, help="予告の1段落（本家に残した中身を名指しする）")
    ap.add_argument("--x-title", dest="x_title",
                    help="X Articles用のタイトル。記事のh1がX上限(全角2・半角1で100)を"
                         "超えるとき、記事本体を書き換えずにXの場だけ短縮する")
    ap.add_argument("--heads", help="載せるH2の見出し（前方一致・カンマ区切り）。"
                                    "省略時は朝A型の3本。夕B型はここで3本ほど選ぶ")
    ap.add_argument("--clipboard", action="store_true",
                    help="APIを使わず、書式付きHTMLをクリップボードに載せる（手貼り運用・課金ゼロ）")
    ap.add_argument("--dry-run", action="store_true", help="APIを叩かずJSONを書き出すだけ")
    ap.add_argument("--publish", action="store_true", help="下書きを作ってそのまま公開する（既定は下書きまで）")
    ap.add_argument("--figs", nargs="?", const="", metavar="DIR",
                    help="本文の図をX添付用のPNGで書き出す（既定は %%TEMP%%/x_figs_<slug>/）。"
                         "貼った本文の［図N］の位置に、挿入ボタンで入れる")
    use_utf8_stdio()
    a = ap.parse_args()

    heads = [h.strip() for h in a.heads.split(",") if h.strip()] if a.heads else None
    title, content_state, figs = build(a.slug, a.teaser, heads, mark_figs=a.figs is not None)
    # 記事のh1がX上限を超えるとき用。記事本体（公開済みのcanonical/JSON-LD）を
    # 触らずにXの場だけ短縮できるようにする。指定が無ければh1をそのまま使う
    if a.x_title:
        title = a.x_title
    n = len(content_state["blocks"])
    chars = sum(len(b["text"]) for b in content_state["blocks"])
    tw = x_weighted_len(title)
    print(f"title: {title}")
    print(f"タイトル: X加重 {tw}/{X_TITLE_MAX}文字")
    if over_by(title):
        # クリップボードに入れてから弾かれると貼り直しになるので、ここで止める
        sys.exit(f"NG タイトルがX上限を{over_by(title)}超過（{tw}/{X_TITLE_MAX}）。"
                 f"全角{(over_by(title) + 1) // 2}文字ほど削ること。\n"
                 f"   記事本体を直すか、公開済みで触りたくなければ --x-title \"<短縮版>\" を渡す。\n"
                 f"   Xは全角2・半角1で数える＝Pythonのlen()（{len(title)}）を根拠にしない")
    print(f"blocks: {n} / entities: {len(content_state['entities'])} / 本文 約{chars}字")

    # 黙って消えるのが一番まずいので、載せなかった図は必ず1行で報告する
    if figs and a.figs is None:
        print(f"図{len(figs)}点は載せず本家記事に残した（Xにも載せるなら --figs）")
    if a.figs is not None:
        figdir = a.figs or os.path.join(os.environ.get("TEMP", "."), f"x_figs_{a.slug}")
        if os.path.isdir(figdir):
            for old in os.listdir(figdir):      # 隣の記事の図を掴む事故を防ぐため毎回空にする
                if old.lower().endswith(".png"):
                    os.remove(os.path.join(figdir, old))
        os.makedirs(figdir, exist_ok=True)
        for f in figs:
            out_png = os.path.join(figdir, f"fig{f['n']}.png")
            render_fig(f["title"], f["svg"], out_png)
            print(f"  ［図{f['n']}］{f['title']}\n      {out_png}")
        if not figs:
            print("  （載せるH2の中に図はありません）")

    # リポジトリ内には書かない（このリポジトリはCloudflare Pagesで全ファイル公開される）
    out = os.path.join(os.environ.get("TEMP", "."), f"x_article_{a.slug}.json")
    payload = {"title": title, "content_state": content_state}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"payload: {out}")

    if a.clipboard:
        html = blocks_to_html(content_state)
        plain = "\n".join(b["text"] for b in content_state["blocks"])
        ok, err = to_clipboard(html, plain)
        if not ok:
            sys.exit(f"クリップボードに載せられませんでした: {err[:300]}")
        cover = os.path.join(REPO, "assets", "blog", f"{a.slug}.jpg")
        print("クリップボードに載せました（書式つき）")
        print("  1. https://x.com/compose/articles →「記事を作成」")
        print(f"  2. タイトル欄に貼る: {title}")
        print("  3. 本文欄で Ctrl+V（見出し・太字・リンクごと入る）")
        print(f"  4. カバー画像をアップ: {cover}")
        print("  5. キャプションを入れて公開")
        return

    if a.dry_run:
        print("--- 本文プレビュー ---")
        for b in content_state["blocks"]:
            mark = {"header-two": "## ", "unordered-list-item": "- "}.get(b["type"], "")
            print(mark + b["text"])
        return

    keys = load_keys()
    if keys is None:
        print(f"NO_KEYS: {KEYS_PATH} が無いか不完全。何も送らず終了")
        sys.exit(3)
    s = session(keys)

    cover = os.path.join(REPO, "assets", "blog", f"{a.slug}.jpg")
    if os.path.exists(cover):
        media_id = upload_cover(s, cover)
        payload["cover_media"] = {"media_category": "tweet_image", "media_id": media_id}
        print(f"cover uploaded: media_id={media_id}")
    else:
        print(f"WARN: アイキャッチが無いのでカバー無しで作ります ({cover})")

    r = s.post(DRAFT_URL, json=payload, timeout=60)
    if r.status_code != 201:
        die("draft", r)
    article_id = r.json()["data"]["id"]
    print(f"OK draft article_id={article_id}")
    print("次: https://x.com/compose/articles を開いて下書きを確認 → キャプションを入れて公開")

    if a.publish:
        r = s.post(PUBLISH_URL.format(article_id=article_id), timeout=60)
        if r.status_code != 200:
            die("publish", r)
        pid = r.json()["data"]["post_id"]
        print(f"PUBLISHED post_id={pid} https://x.com/i/web/status/{pid}")


if __name__ == "__main__":
    main()
