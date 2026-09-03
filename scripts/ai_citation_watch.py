#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Google検索の「AI による概要」に ngraph.jp が引用されているかの定点観測（BLOG-OPS §10）。

2026-08-22新設。起点＝ライオンレンタカーのサイトが「バングラデシュ レンタカー」のAI概要に
引用された実測と、「NGraph FDE」で ngraph.jp/fde が同じく引用されていた実測（同日）。
AI概要に出るかどうかは目で見て一喜一憂するものではなく、同じ問いを同じ方法で週次に投げて
記録するもの。記録だけが「いつから出た／消えた」を言える。

方法: ヘッドレスEdgeでGoogleの検索結果ページをDOMごと取得し、
  - 「AI による概要」の文字列があるか（AI概要の有無）
  - その位置から次の「ウェブ検索結果」までの区間に ngraph.jp が出るか（概要内の引用）
  - 自然検索の結果リンクの中で ngraph.jp が何番目か（順位・無ければ null）
を1クエリ1行のJSONで ops-watch/ai-citation.jsonl に追記する。

⚠ 判定は文字列の位置関係による近似。Googleの画面構造が変わると区間の切り方が外れる。
   取得そのものが失敗した行は status="fetch_failed" で残す（失敗と「出ていない」を混ぜない＝
   memory feedback_broken_gate_hides_violations の型）。
⚠ ネットワークに出るので gate.py には入れない。blog-weekly-review（毎週木曜）が単体で回す。
⚠ ヘッドレスブラウザは --user-data-dir を毎回一時ディレクトリにする（ブラウザペインと衝突すると無言死）。
⚠ 2026-09-03: ブラウザは固定しない（起動前に自己検査して --dump-dom が動く方を採る）。
   さらに同日、Googleが headless に対してボット検出ページを返すようになった＝この経路では計測できない。
   回避（CAPTCHA突破・IP変更）はしない。当面は週次レビューが実ブラウザで主要3クエリを目視し、
   blog-metrics.jsonl の manual_serp に記録する（BLOG-OPS §10）。

使い方:
    python scripts/ai_citation_watch.py            # 全クエリを回して追記・要約を表示
    python scripts/ai_citation_watch.py --dry      # 追記せず表示だけ
    python scripts/ai_citation_watch.py --q "NGraph FDE"   # 1クエリだけ
クエリ表: scripts/ai_citation_queries.json（狙い＝検索語・どの記事/ページで取りに行っているか）
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERIES = os.path.join(BASE, "scripts", "ai_citation_queries.json")
LOG = r"C:\dev\ngraph-workspace\projects\ops-watch\ai-citation.jsonl"
# ⚠ ブラウザは固定しない（2026-09-03）。Edge 151/152 で --dump-dom が壊れ（ローカルHTMLでも0バイト）、
#   「Edgeで動く」という前提のまま2週間 fetch_failed を出し続けた。起動前に自己検査して動く方を採る。
BROWSERS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
OVERVIEW_MARK = "AI による概要"
WEB_MARK = "ウェブ検索結果"
OURS = "ngraph.jp"
# Googleのボット検出ページ（/sorry/ 相当）の目印。小さいHTMLなので、サイズ判定だけだと
# 「取得失敗」に化けて原因を取り違える（2026-09-03に実際に取り違えた）。
BLOCK_MARKS = ("通常と異なるトラフィック", "unusual traffic", "recaptcha")

_BROWSER = "unset"


def _run_dump_dom(exe, url, budget, out, timeout=90):
    tmp = tempfile.mkdtemp(prefix="aicw_")
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
           f"--user-data-dir={tmp}", f"--virtual-time-budget={budget}", "--lang=ja",
           "--dump-dom", url]
    with open(out, "wb") as f:
        subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, timeout=timeout)
    return os.path.getsize(out)


def browser():
    """--dump-dom が実際に文字列を返すブラウザを1つ選ぶ（ローカルHTMLで自己検査）。
    どれも返さなければ None。returncode では判定しない（0で戻って空を吐くのが今回の故障）。"""
    global _BROWSER
    if _BROWSER != "unset":
        return _BROWSER
    tmp = tempfile.mkdtemp(prefix="aicw_probe_")
    hp = os.path.join(tmp, "p.html")
    with open(hp, "w", encoding="utf-8") as f:
        f.write("<html><body><h1>aicw-probe-ok</h1></body></html>")
    _BROWSER = None
    for i, exe in enumerate(BROWSERS):
        if not os.path.exists(exe):
            continue
        out = os.path.join(tmp, "local%d.html" % i)
        # 合否はサイズではなく中身で見る。probeのDOMは60バイト程度しかなく、
        # サイズ閾値で見ると動いているブラウザを落とす（2026-09-03に実際に落とした）。
        try:
            _run_dump_dom(exe, "file:///" + hp.replace("\\", "/"), 3000, out, timeout=60)
            ok = "aicw-probe-ok" in open(out, encoding="utf-8", errors="ignore").read()
        except Exception:
            ok = False
        if ok:
            _BROWSER = exe
            break
    return _BROWSER


def fetch(query, budget=8000):
    """検索結果ページのDOMを (本文, 理由) で返す。取れたときは 理由=None。
    理由は "no_browser"（--dump-dom が動くブラウザが無い）/ "blocked"（Googleのボット検出）/
    "empty"（返ってこない）。"""
    exe = browser()
    if not exe:
        return None, "no_browser"
    url = "https://www.google.com/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ja", "gl": "jp"})
    out = os.path.join(tempfile.mkdtemp(prefix="aicw_"), "out.html")
    last = "empty"
    for _ in range(2):
        try:
            n = _run_dump_dom(exe, url, budget, out)
        except Exception:
            n = 0
        if n > 0:
            html = open(out, encoding="utf-8", errors="ignore").read()
            if any(m in html for m in BLOCK_MARKS):
                return None, "blocked"
            if n > 100_000:
                return html, None
        time.sleep(3)
    return None, last


def organic_rank(html):
    """自然検索のリンク（h3を持つ結果）の順に並べ、ngraph.jp の順位を返す。"""
    urls = []
    for m in re.finditer(r'<a [^>]*href="(https?://[^"]+)"[^>]*>(?:(?!</a>).)*?<h3', html, re.S):
        u = m.group(1)
        if "google." in urllib.parse.urlparse(u).netloc:
            continue
        d = urllib.parse.urlparse(u).netloc
        if d not in urls:
            urls.append(d)
    rank = next((i + 1 for i, d in enumerate(urls) if OURS in d), None)
    return rank, urls[:10]


HEADING_RE = re.compile(r'role="heading"[^>]*>' + OVERVIEW_MARK)


def analyze(html):
    """AI概要の見出し要素から次の「ウェブ検索結果」までを概要の区間とみなす。
    display:none の定型文（「現在、AI による概要を生成できません」）は見出し要素ではないので拾わない。
    見出しがあっても本文テキストが短ければ生成待ちの取りこぼし＝ pending を返す（呼び出し側で再取得）。"""
    m = HEADING_RE.search(html)
    if not m:
        return {"ai_overview": False, "ours_in_overview": False}
    i = m.end()
    j = html.find(WEB_MARK, i)
    seg = html[i: j if j > 0 else i + 300_000]
    text = re.sub(r"<(script|style)[^>]*>.*?</(script|style)>", " ", seg, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 60:
        return {"ai_overview": None, "ours_in_overview": False, "pending": True}
    return {"ai_overview": True,
            "ours_in_overview": OURS in seg,
            "overview_excerpt": text[:240]}



def env_probe():
    """全件取得失敗のとき、原因が「Edgeがネットワークに出られない」のか
    「Googleが返さない」のかを切り分けて1行で名指しする。

    2026-08-27追加。この日、9クエリ全部が fetch_failed になり、切り分けに時間を使った。
    実測で確定した原因は「Edgeが壊れた」でも「ネットワークが死んだ」でもなく、
    **--dump-dom だけが出力を返さない**こと（Edge 151.0.4129.101）:
      - --dump-dom は file:// のローカルHTMLでも 0 バイト（git-bash でも PowerShell でも同じ）
      - --screenshot は同じEdgeで正常（eyecatch_gen.py は動いている＝表紙生成は無事）
      - curl は同じURLで 200 を返す＝ネットワークは生きている
    つまり切り分けの軸は「ローカル/リモート」ではなく「--dump-dom/--screenshot」だった。
    次に同じ状態を踏む人が同じ回り道をしないよう、失敗時にこのプローブが自分で名指しする
    （環境要因で原因を潰せないときでも、診断は装置に持たせる）。
    """
    exe = browser()
    if not exe:
        tried = " / ".join(b for b in BROWSERS if os.path.exists(b)) or "（候補が1つも見つからない）"
        return ("--dump-dom が動くブラウザが1つも無い。試したのは " + tried + "。"
                "--screenshot は別経路なので表紙生成(eyecatch_gen.py)は動いている可能性が高い"
                "（切り分けの軸はローカル/リモートではなく --dump-dom/--screenshot）。"
                "⚠curlで代替しないこと＝JS描画のAI概要が取れず『概要なし』の偽の緑になる")
    _, why = fetch("example.com とは")
    if why == "blocked":
        return (os.path.basename(exe) + " の --dump-dom は動くが、Googleがボット検出ページを返している"
                "（headlessからの検索を遮断）。**この経路ではAI概要は計測できない**。"
                "回避（CAPTCHA突破・IP変更）はしない。実ブラウザでの目視観測に切り替えるか、"
                "計測方法そのものを設計し直す。⚠『概要なし』と書かないこと")
    if why:
        return (os.path.basename(exe) + " の --dump-dom はローカルでは動くがGoogleで空＝"
                "ネットワーク経路の遮断を疑う（プロキシ/ポリシー）。"
                "⚠curlで代替しないこと＝JS描画のAI概要が取れず『概要なし』の偽の緑になる")
    return (os.path.basename(exe) + " は動いておりGoogleにも出られる。"
            "Google側が結果を返さなかった可能性（レート制限・画面構造の変更）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--q", help="1クエリだけ")
    a = ap.parse_args()
    qs = json.load(open(QUERIES, encoding="utf-8"))
    if a.q:
        qs = [q for q in qs if q["q"] == a.q] or [{"q": a.q, "target": ""}]
    today = dt.date.today().isoformat()
    rows = []
    for q in qs:
        html, why = fetch(q["q"])
        row = {"date": today, "q": q["q"], "target": q.get("target", "")}
        res = analyze(html) if html else None
        if res and res.get("pending"):
            html2, why2 = fetch(q["q"], budget=16000)
            if html2 or why2 != "empty":
                html, why = html2, why2
            res = analyze(html) if html else None
        if html is None:
            row["status"] = "blocked_by_google" if why == "blocked" else "fetch_failed"
            row["reason"] = why
        elif res.get("pending"):
            row["status"] = "overview_pending"
            row.update({"ai_overview": None, "ours_in_overview": False})
        else:
            row["status"] = "ok"
            row.update(res)
            row["organic_rank"], row["top_domains"] = organic_rank(html)
        rows.append(row)
        mark = ("✗Google遮断" if row["status"] == "blocked_by_google" else
                "✗取得失敗" if row["status"] == "fetch_failed" else
                "?概要生成待ち" if row["status"] == "overview_pending" else
                ("★概要内に引用" if row.get("ours_in_overview") else
                 ("概要あり・未引用" if row.get("ai_overview") else "概要なし")))
        print(f"{mark:10} 自然検索{str(row.get('organic_rank')):>5}位  {q['q']}")
        time.sleep(2)
    if not a.dry:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"→ {len(rows)}行を追記: {LOG}")
    failed = [r for r in rows if r["status"] != "ok"]
    if failed:
        print(f"⚠ 取得失敗・遮断・生成待ち {len(failed)}件（未引用と混ぜない）")
        if len(failed) == len(rows) and all(
                r["status"] in ("fetch_failed", "blocked_by_google") for r in rows):
            print("→ 全件取れず。切り分け中…")
            print("→ 診断: " + env_probe())
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
