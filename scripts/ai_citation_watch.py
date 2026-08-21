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
⚠ ヘッドレスEdgeは --user-data-dir を毎回一時ディレクトリにする（ブラウザペインと衝突すると無言死）。

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
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OVERVIEW_MARK = "AI による概要"
WEB_MARK = "ウェブ検索結果"
OURS = "ngraph.jp"


def fetch(query, budget=8000):
    """検索結果ページのDOMを文字列で返す。取れなければ None。"""
    url = "https://www.google.com/search?" + urllib.parse.urlencode(
        {"q": query, "hl": "ja", "gl": "jp"})
    tmp = tempfile.mkdtemp(prefix="aicw_")
    out = os.path.join(tmp, "out.html")
    cmd = [EDGE, "--headless=new", "--disable-gpu", "--no-sandbox",
           f"--user-data-dir={tmp}", f"--virtual-time-budget={budget}", "--lang=ja",
           f"--dump-dom", url]
    for _ in range(2):
        with open(out, "wb") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.DEVNULL, timeout=90)
        if os.path.getsize(out) > 100_000:
            return open(out, encoding="utf-8", errors="ignore").read()
        time.sleep(3)
    return None


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
        html = fetch(q["q"])
        row = {"date": today, "q": q["q"], "target": q.get("target", "")}
        res = analyze(html) if html else None
        if res and res.get("pending"):
            html = fetch(q["q"], budget=16000)
            res = analyze(html) if html else None
        if html is None:
            row["status"] = "fetch_failed"
        elif res.get("pending"):
            row["status"] = "overview_pending"
            row.update({"ai_overview": None, "ours_in_overview": False})
        else:
            row["status"] = "ok"
            row.update(res)
            row["organic_rank"], row["top_domains"] = organic_rank(html)
        rows.append(row)
        mark = ("✗取得失敗" if row["status"] == "fetch_failed" else
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
        print(f"⚠ 取得失敗・生成待ち {len(failed)}件（未引用と混ぜない）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
