#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""企業のケーススタディ（NCG採点）を ngraph.jp/cases/ に書き出す。

なぜ作ったか（2026-10-17 髙橋さん「企業を分析した奴」をngraph.jpに載せる）:
  nicomachos.com/cases にあったケーススタディ（アルケー）を、NCG の実例として
  会社サイトに置く。診断機能（URLを入れて採点）は移さない（本人判断）。

元データ: scripts/cases/data.json
  = C:/dev/autowrite/src/lib/case-studies-data.ts を書き出したもの（v1.0 の採点・凍結）。
  中身を直すときは元の .ts を直してから書き出し直す。HTML を手で直さない。

使い方:
    python scripts/build_cases.py          # cases/ を作り直す
    python scripts/build_cases.py --check  # 生成物と data.json のズレを検査（exit 1）
その後 python scripts/sync_chrome.py でヘッダー・フッターを揃える。
"""
import html
import json
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(HERE, "cases", "data.json")
OUT = os.path.join(ROOT, "cases")
SITE = "https://ngraph.jp"

SURVIVAL = 47
EXCELLENT = 75

TIER = {
    "god": "W5", "earth": "アース20", "craft": "クラフト", "gold": "500年+ レジェンド",
    "silver": "300年+ レジェンド", "bronze": "100年+ レジェンド", "japan": "日本企業",
    "social": "ソーシャル", "startup": "スタートアップ", "fail": "失敗",
}
# 一覧の絞り込みの並び
FILTERS = [("all", "すべて"), ("god", "W5"), ("earth", "アース20"), ("japan", "日本企業"),
           ("longevity", "100年+ 老舗"), ("craft", "クラフト"), ("social", "ソーシャル"),
           ("startup", "スタートアップ"), ("fail", "失敗")]
TIER_RANK = {"god": 100, "earth": 90, "craft": 80, "gold": 70, "silver": 60, "bronze": 50,
             "japan": 40, "social": 35, "startup": 30, "fail": 10}
AGE_BADGE = {"bronze": "100年+", "silver": "300年+", "gold": "500年+"}
SCORE_LABEL = [
    ("market", "ターゲット市場"), ("problem", "課題の実在性"), ("solution", "ソリューション"),
    ("team", "チーム"), ("traction", "トラクション"), ("moat", "参入障壁"),
    ("revenue", "収益モデル"), ("financial", "財務計画"), ("efficiency", "資本効率"),
    ("exit", "出口戦略"), ("timing", "タイミング"), ("insight", "独自の洞察"),
]
# 国旗の絵文字はページに出さない（国名の文字にする）
COUNTRY = {"US": "米国", "JP": "日本", "CN": "中国", "IT": "イタリア", "FR": "フランス",
           "GB": "英国", "DE": "ドイツ", "SE": "スウェーデン", "KR": "韓国", "IN": "インド",
           "BD": "バングラデシュ", "AU": "オーストラリア", "NL": "オランダ", "CH": "スイス",
           "DK": "デンマーク", "CA": "カナダ", "IL": "イスラエル", "BR": "ブラジル",
           "TW": "台湾", "SG": "シンガポール", "KE": "ケニア", "FI": "フィンランド",
           "ES": "スペイン", "AT": "オーストリア", "BE": "ベルギー", "NO": "ノルウェー"}

e = html.escape


def country(flag):
    if not flag:
        return ""
    code = "".join(chr(ord(ch) - 0x1F1E6 + 65) for ch in flag if 0x1F1E6 <= ord(ch) <= 0x1F1FF)
    return COUNTRY.get(code, code)


def band(c):
    if c["tier"] == "fail":
        return ("fail", "逸脱")
    if c["score"] >= EXCELLENT:
        return ("ex", "卓越")
    if c["score"] >= SURVIVAL:
        return ("mean", "中庸")
    return ("weak", "脆弱")


def year_num(c):
    y = c["year"]
    if isinstance(y, int):
        return y
    digits = "".join(ch for ch in str(y) if ch.isdigit())[:4]
    return int(digits) if digits else 0


def load():
    with open(DATA, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    # 元データは同名・同年で tier 違いの2件（例: Microsoft 1975 の god と startup）が同じスラグになる。
    # 一覧に残る側（tier が上）に元のスラグを渡し、もう一方に -startup 等を足して一意にする。
    seen = {}
    for c in sorted(cases, key=lambda c: -TIER_RANK.get(c["tier"], 0)):
        s = c["slug"]
        if s in seen:
            c["slug"] = f"{s}-{c['tier']}"
        seen[c["slug"]] = True
    assert len({c["slug"] for c in cases}) == len(cases), "スラグが重複している"
    return cases


def canonical(cases):
    best = {}
    for c in cases:
        g = c["eraGroup"]
        if not g:
            continue
        cur = best.get(g)
        key = (TIER_RANK.get(c["tier"], 0), year_num(c))
        if cur is None or key > (TIER_RANK.get(cur["tier"], 0), year_num(cur)):
            best[g] = c
    return [c for c in cases if not c["eraGroup"] or best[c["eraGroup"]] is c]


def head(title, desc, path, extra_css):
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-L96HMXRK1D"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-L96HMXRK1D');
</script>
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{SITE}{path}">
<meta property="og:site_name" content="株式会社NGraph">
<link rel="canonical" href="{SITE}{path}">
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zen+Old+Mincho:wght@400;600;700;900&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/css/ngraph-zen.css?v=12">
<style>
{COMMON_CSS}{extra_css}</style>
<link rel="stylesheet" href="/css/sp.css?v=3">
</head>
<body>
<div class="bg-fx" aria-hidden="true"></div>
<header class="header scrolled"></header>
"""


FOOT = """
<footer class="footer"></footer>
"""

COMMON_CSS = """.k-wrap{max-width:860px;margin:0 auto;padding:130px 20px 80px}
.k-h1{font-family:var(--serif);font-size:1.75rem;font-weight:900;line-height:1.6;margin:8px 0 14px}
.k-lead{font-size:.92rem;color:var(--text-2);line-height:2}
.k-sec{margin-top:40px}
.k-sec h2{font-family:var(--serif);font-size:1.08rem;font-weight:700;border-left:3px solid var(--accent);padding-left:12px;margin-bottom:14px}
.k-note{font-size:.8rem;color:var(--text-3);line-height:2;border-top:1px solid var(--border);margin-top:48px;padding-top:18px}
.k-note a{text-decoration:underline}
.bd{display:inline-block;font-size:.78rem;font-weight:700;padding:1px 8px;border-radius:3px;white-space:nowrap}
.bd-ex{background:#e3efe6;color:#2e6e4e}
.bd-mean{background:#e4ebf3;color:#30557e}
.bd-weak{background:#f5ecd2;color:#7a5a0e}
.bd-fail{background:#f6e1db;color:#a63a24}
"""

LIST_CSS = """.k-method{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:22px}
.k-method div{border:1px solid var(--border);background:var(--bg-card);border-radius:4px;padding:12px 14px;font-size:.82rem;line-height:1.8;color:var(--text-2)}
.k-method strong{display:block;font-family:var(--serif);font-size:1.05rem;color:var(--text)}
.k-filter{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 16px}
.k-filter button{font:inherit;font-size:.8rem;padding:5px 12px;border:1px solid var(--border-strong);border-radius:3px;background:transparent;color:var(--text-2);cursor:pointer}
.k-filter button.on{background:var(--text);border-color:var(--text);color:#fdfaf4}
.k-count{font-size:.78rem;color:var(--text-3);margin-bottom:10px}
.k-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.k-card{display:block;border:1px solid var(--border);border-left:4px solid var(--c);background:var(--bg-card);border-radius:4px;padding:14px 16px;transition:border-color .2s,background .2s}
.k-card:hover{background:var(--bg-card-hover);border-color:var(--border-strong);border-left-color:var(--c)}
.k-card .t{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:2px 10px}
.k-card .n{font-family:var(--serif);font-size:1.05rem;font-weight:700;color:var(--text);min-width:0;word-break:keep-all}
.k-card .s{font-family:var(--serif);font-size:1.5rem;font-weight:900;color:var(--text);line-height:1;white-space:nowrap}
.k-card .s small{font-size:.78rem;font-weight:400;color:var(--text-3)}
.k-card .m{font-size:.78rem;color:var(--text-3);margin:4px 0 6px;display:flex;flex-wrap:wrap;gap:4px 10px;align-items:center}
.k-card .i{font-size:.84rem;color:var(--text-2);line-height:1.8}
.k-laws{font-size:.86rem;color:var(--text-2);line-height:2.1;padding-left:1.4em}
@media(max-width:640px){.k-method,.k-grid{grid-template-columns:1fr}.k-h1{font-size:1.45rem}}
"""

DETAIL_CSS = """.k-back{font-size:.8rem;color:var(--text-3)}
.k-back:hover{color:var(--accent)}
.k-hero{border:1px solid var(--border);border-top:5px solid var(--c);background:var(--bg-card);border-radius:4px;padding:22px 24px;margin-top:14px;display:grid;grid-template-columns:1fr auto;gap:6px 20px;align-items:start}
.k-hero .meta{font-size:.78rem;color:var(--text-3);display:flex;flex-wrap:wrap;gap:4px 12px}
.k-hero h1{font-family:var(--serif);font-size:1.8rem;font-weight:900;line-height:1.4;margin:4px 0 2px}
.k-hero .en{font-size:.8rem;color:var(--text-3);letter-spacing:.04em}
.k-hero .sc{text-align:right;grid-row:1 / span 2;grid-column:2}
.k-hero .sc .l{font-size:.78rem;letter-spacing:.2em;color:var(--text-3)}
.k-hero .sc .v{font-family:var(--serif);font-size:3rem;font-weight:900;line-height:1}
.k-hero .sc .u{font-size:.78rem;color:var(--text-3);margin-bottom:4px}
.k-hero .ins{grid-column:1 / -1;margin-top:12px;padding:12px 14px;background:rgba(43,38,32,.04);border-radius:3px;font-size:.92rem;line-height:1.9}
.k-p{font-size:.9rem;color:var(--text-2);line-height:2.05;white-space:pre-wrap}
.k-score{width:100%;border-collapse:collapse;font-size:.85rem}
.k-score td{border-bottom:1px solid var(--border);padding:9px 6px;vertical-align:top;line-height:1.8}
.k-score td.k{width:9.5em;font-weight:700;color:var(--text);white-space:nowrap}
.k-score td.v{width:6.5em;white-space:nowrap}
.k-score td.r{color:var(--text-2)}
.k-bar{display:inline-block;width:46px;height:6px;background:rgba(60,52,42,.1);border-radius:3px;vertical-align:middle;margin-right:6px;position:relative;overflow:hidden}
.k-bar i{position:absolute;left:0;top:0;bottom:0;background:var(--text-2)}
.k-axes{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.k-axes div{border:1px solid var(--border);background:var(--bg-card);border-radius:4px;padding:12px;text-align:center;font-size:.8rem;color:var(--text-3)}
.k-axes strong{display:block;font-family:var(--serif);font-size:1.6rem;color:var(--text);line-height:1.3}
.k-axes strong small{font-size:.78rem;color:var(--text-3);font-weight:400}
.k-box{border:1px solid var(--border);background:var(--bg-card);border-radius:4px;padding:16px 18px}
.k-virtue{margin-top:12px;border-left:3px solid var(--accent);padding-left:12px;font-family:var(--serif);font-weight:700;font-size:.92rem}
.k-bonus{display:flex;gap:14px;align-items:baseline}
.k-bonus b{font-family:var(--serif);font-size:1.8rem;color:var(--accent);line-height:1}
.k-key{border-left:3px solid #2e6e4e;padding:12px 16px;background:rgba(46,110,78,.05);font-size:.88rem;line-height:2;color:var(--text-2)}
.k-key.f{border-left-color:var(--accent);background:rgba(166,58,36,.05)}
.k-era a{display:block;padding:10px 0;border-bottom:1px solid var(--border);font-size:.88rem;color:var(--text-2)}
.k-era a:hover{color:var(--accent)}
.k-era span{color:var(--text-3);font-size:.78rem;margin-left:8px}
@media(max-width:640px){.k-hero{grid-template-columns:1fr;padding:18px}.k-hero .sc{grid-row:auto;grid-column:auto;text-align:left;display:flex;gap:10px;align-items:baseline}.k-hero h1{font-size:1.45rem}.k-hero .sc .v{font-size:2.3rem}.k-score tr{display:grid;grid-template-columns:1fr auto;border-bottom:1px solid var(--border)}.k-score td{border-bottom:0;padding:8px 4px 0}.k-score td.k{width:auto}.k-score td.v{width:auto}.k-score td.r{grid-column:1 / -1;padding:2px 4px 10px}}
"""

NOTE = (
    '<p class="k-note">各社の点数は、NGraph が NCG（Nicomachos Company Graph）の採点基準 v1.0 で、'
    '公開されている沿革・報道をもとに採点したものです（2026年4月時点・以後は更新していません）。'
    '各社の公式見解ではなく、投資や取引の判断材料として作ったものでもありません。'
    '記載に誤りがあれば<a href="/entry">お問い合わせ</a>からお知らせください。'
    'NCG の考え方は<a href="/company#tech">会社概要の構造化技術</a>にあります。</p>'
)


def card(c):
    k, label = band(c)
    meta = [f"{e(str(c['year']))}年"]
    if c["flag"]:
        meta.append(e(country(c["flag"])))
    meta.append(e(TIER[c["tier"]]))
    if c["ageBadge"]:
        meta.append(AGE_BADGE[c["ageBadge"]])
    filt = [c["tier"]] + (["longevity"] if (c["age"] or 0) >= 100 else [])
    return (
        f'<a class="k-card" href="/cases/{c["slug"]}/" style="--c:{e(c["color"])}" data-f="{" ".join(filt)}">'
        f'<div class="t"><span class="n">{e(c["name"])}</span><span class="s">{c["score"]}<small>/100</small></span></div>'
        f'<div class="m">{"<span>・</span>".join(f"<span>{m}</span>" for m in meta)}<span class="bd bd-{k}">{label}</span></div>'
        f'<p class="i">{e(c["insight"])}</p></a>'
    )


def build_list(cases):
    shown = sorted(canonical(cases), key=lambda c: (-c["score"], c["name"]))
    n_company = len(shown)
    desc = (f"Apple・トヨタ・任天堂から失敗した企業まで、{n_company}社の事業を同じ12項目と三軸で採点した構造分析。"
            "NGraph の企業構造化（NCG）の実例です。")
    out = [head(f"企業の構造分析 — {n_company}社をNCGで採点 | 株式会社NGraph", desc, "/cases/", LIST_CSS)]
    out.append('<main class="k-wrap">')
    out.append('<div class="section-label">Company Cases</div>')
    out.append(f'<h1 class="k-h1">企業の構造分析<span class="nb">（{n_company}社）</span></h1>')
    out.append('<p class="k-lead">世界の企業を、同じ物差しで並べました。市場・課題・チーム・参入障壁など12項目と、'
               '世間・相手・自己の三軸で採点し、100点満点で表しています。'
               '長く続いた会社と、消えた会社の差がどこに出るかを見るための一覧です。</p>')
    out.append('<div class="k-method">'
               '<div><strong>12項目 × 5点</strong>市場・課題・解決策・チーム・実績・参入障壁・収益・財務・資本効率・出口・タイミング・洞察（60点）</div>'
               '<div><strong>三軸 × 10点</strong>世間（社会への影響）・相手（顧客）・自己（会社自身）を各10点（30点）</div>'
               f'<div><strong>存続ライン {SURVIVAL}点</strong>{EXCELLENT}点以上を卓越、{SURVIVAL}点以上を中庸、未満を脆弱とします。加点は最大10点</div>'
               '</div>')
    out.append('<section class="k-sec"><h2>一覧</h2>')
    out.append('<div class="k-filter" role="group" aria-label="絞り込み">' + "".join(
        f'<button type="button" data-f="{k}"{" class=\"on\"" if k == "all" else ""}>{v}</button>' for k, v in FILTERS) + '</div>')
    out.append(f'<p class="k-count" id="kCount">{n_company}社</p>')
    out.append('<div class="k-grid" id="kGrid">' + "".join(card(c) for c in shown) + '</div></section>')
    out.append('<section class="k-sec"><h2>並べて見えた5つのこと</h2><ol class="k-laws">'
               f'<li>存続ラインは{SURVIVAL}点。ただし「タイミング」と「独自の洞察」が満点なら、下回っても生き残る例がある</li>'
               '<li>参入障壁は育てるもの。スタートアップの平均2.4点に対し、長寿レジェンドの平均は4.6点</li>'
               '<li>失敗した会社に共通するのは「独自の洞察」1点。調達額が大きくても消える</li>'
               '<li>長く続く会社は「成長しない勇気」を持っている</li>'
               '<li>「何で稼いでいるか」と「何で生き残っているか」は別物</li></ol></section>')
    out.append(NOTE)
    out.append('</main>')
    out.append(FOOT)
    out.append("""<script>
(function(){var bs=document.querySelectorAll('.k-filter button'),cs=document.querySelectorAll('#kGrid .k-card'),ct=document.getElementById('kCount');
bs.forEach(function(b){b.addEventListener('click',function(){var f=b.dataset.f,n=0;bs.forEach(function(x){x.classList.toggle('on',x===b)});
cs.forEach(function(c){var ok=f==='all'||c.dataset.f.split(' ').indexOf(f)>=0;c.style.display=ok?'':'none';if(ok)n++});ct.textContent=n+'社';});});})();
</script>
</body>
</html>
""")
    return "\n".join(out)


def build_detail(c, cases):
    k, label = band(c)
    axes_total = (c["axes"]["society"] + c["axes"]["customer"] + c["axes"]["self"]) * 2
    sub = c["nameEn"] if c["nameEn"] and c["nameEn"] != c["name"] else ""
    title = f"{c['name']}（{c['year']}年）の構造分析 — NCG {c['score']}点 | 株式会社NGraph"
    desc = f"{c['name']}（{TIER[c['tier']]}・NCG {c['score']}/100点）{c['insight']}"
    if len(desc) > 120:
        desc = desc[:119] + "…"
    out = [head(title, desc, f"/cases/{c['slug']}/", DETAIL_CSS)]
    out.append('<main class="k-wrap">')
    out.append('<a class="k-back" href="/cases/">← 企業の構造分析の一覧へ</a>')
    meta = [f"{e(str(c['year']))}年"]
    if c["flag"]:
        meta.append(e(country(c["flag"])))
    meta.append(e(TIER[c["tier"]]))
    if c["ageBadge"]:
        meta.append(AGE_BADGE[c["ageBadge"]] + " 続く会社")
    if c["tierLabel"]:
        meta.append(e(c["tierLabel"]))
    out.append(f'<div class="k-hero" style="--c:{e(c["color"])}">'
               f'<div><div class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</div>'
               f'<h1>{e(c["name"])}</h1>' + (f'<div class="en">{e(sub)}</div>' if sub else "") + '</div>'
               f'<div class="sc"><div class="l">NCG</div><div class="v">{c["score"]}</div><div class="u">/100点</div><span class="bd bd-{k}">{label}</span></div>'
               f'<p class="ins">{e(c["insight"])}</p></div>')
    if c["situation"]:
        out.append(f'<section class="k-sec"><h2>当時の状況</h2><p class="k-p">{e(c["situation"])}</p></section>')
    rows = []
    for key, lab in SCORE_LABEL:
        v = c["scores"][key]
        reason = (c["reasons"] or {}).get(key, "")
        rows.append(f'<tr><td class="k">{lab}</td><td class="v"><span class="k-bar"><i style="width:{v * 20}%"></i></span>{v}/5</td>'
                    f'<td class="r">{e(reason)}</td></tr>')
    out.append(f'<section class="k-sec"><h2>12項目の採点（{c["total12"]}/60）</h2><table class="k-score">{"".join(rows)}</table></section>')
    ax = c["axes"]
    out.append(f'<section class="k-sec"><h2>三軸の評価（{axes_total}/30）</h2><div class="k-axes">'
               f'<div>世間<strong>{ax["society"] * 2}<small>/10</small></strong></div>'
               f'<div>相手<strong>{ax["customer"] * 2}<small>/10</small></strong></div>'
               f'<div>自己<strong>{ax["self"] * 2}<small>/10</small></strong></div></div></section>')
    b = c["bonus"]
    if b["value"] > 0 and b["reason"]:
        out.append(f'<section class="k-sec"><h2>加点</h2><div class="k-box k-bonus"><b>+{b["value"]}</b>'
                   f'<p class="k-p">{e(b["reason"])}</p></div></section>')
    if c["comment"]:
        virtue = f'<p class="k-virtue">{e(c["virtue"])}</p>' if c["virtue"] else ""
        out.append(f'<section class="k-sec"><h2>テレスの所感</h2><div class="k-box"><p class="k-p">{e(c["comment"])}</p>{virtue}</div></section>')
    is_fail = c["tier"] == "fail"
    key_text = c["failReason"] if is_fail else c["survivalKey"]
    if key_text and "上記スコア参照" not in key_text:
        out.append(f'<section class="k-sec"><h2>{"失敗の核心" if is_fail else "存続の鍵"}</h2>'
                   f'<div class="k-key{" f" if is_fail else ""}">{e(key_text)}</div></section>')
    if c["eraGroup"]:
        sibs = sorted((x for x in cases if x["eraGroup"] == c["eraGroup"] and x is not c), key=year_num)
        if sibs:
            out.append('<section class="k-sec"><h2>同じ会社の別の時点</h2><div class="k-era">' + "".join(
                f'<a href="/cases/{x["slug"]}/">{e(x["name"])}（{e(str(x["year"]))}年・{TIER[x["tier"]]}）'
                f'<span>NCG {x["score"]}点</span> →</a>' for x in sibs) + '</div></section>')
    out.append(NOTE)
    out.append('</main>')
    out.append(FOOT)
    out.append("</body>\n</html>\n")
    return "\n".join(out)


SITEMAP = os.path.join(ROOT, "sitemap.xml")
SM_START, SM_END = "<!-- cases:start -->", "<!-- cases:end -->"
# 社数を本文に書いているページ（データの社数が変わったら --check で止める）
COUNT_PAGES = ["index.html", "company.html", "llms.txt"]


def sitemap_block(cases):
    urls = ["/cases/"] + [f"/cases/{c['slug']}/" for c in cases]
    lines = [f"  <url><loc>{SITE}{u}</loc><lastmod>2026-10-17</lastmod></url>" for u in urls]
    return SM_START + "\n" + "\n".join(lines) + "\n  " + SM_END


def sync_sitemap(cases, check):
    with open(SITEMAP, encoding="utf-8") as f:
        s = f.read()
    block = sitemap_block(cases)
    if SM_START in s:
        new = s[:s.index(SM_START)] + block + s[s.index(SM_END) + len(SM_END):]
    else:
        new = s.replace("</urlset>", "  " + block + "\n</urlset>")
    if check:
        # lastmod の日付は比べない（URL の集合だけ見る）
        import re
        urls = lambda t: sorted(re.findall(r"<loc>(https://ngraph\.jp/cases/[^<]*)</loc>", t))
        return urls(s) == urls(new)
    with open(SITEMAP, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    return True


def count_ok(cases):
    n = len(canonical(cases))
    bad = []
    for rel in COUNT_PAGES:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            if f"{n}社" not in f.read():
                bad.append(rel)
    return n, bad


def render_all():
    cases = load()
    files = {"index.html": build_list(cases)}
    for c in cases:
        files[f"{c['slug']}/index.html"] = build_detail(c, cases)
    return files


def main():
    check = "--check" in sys.argv
    files = render_all()
    if check:
        # ヘッダー・フッターは sync_chrome.py が中身を入れるので、その部分を除いて比べる
        import re
        strip = lambda s: re.sub(r'<(header|footer) class="[^"]*">.*?</\1>|\s*<script data-chrome="navjs">.*?</script>', "", s, flags=re.S)
        bad = []
        for rel, body in files.items():
            p = os.path.join(OUT, rel)
            if not os.path.exists(p):
                bad.append(rel + "（無い）")
                continue
            with open(p, encoding="utf-8") as f:
                if strip(f.read()) != strip(body):
                    bad.append(rel)
        if not sync_sitemap(load(), True):
            bad.append("sitemap.xml の /cases/ のURL")
        n, cbad = count_ok(load())
        bad += [f"{r} に「{n}社」が無い（社数を書き直す）" for r in cbad]
        if bad:
            print("cases/ が data.json とずれています（python scripts/build_cases.py を実行）:")
            for b in bad[:20]:
                print("  ", b)
            sys.exit(1)
        print(f"cases/ は data.json と一致（{len(files)}ページ）")
        return
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    for rel, body in files.items():
        p = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
    sync_sitemap(load(), False)
    print(f"cases/ に {len(files)} ページを書き出しました（sitemap.xml も更新）")
    n, cbad = count_ok(load())
    if cbad:
        print(f"注意: {', '.join(cbad)} に「{n}社」が無い。社数を書き直すこと")


if __name__ == "__main__":
    main()
