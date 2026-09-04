# -*- coding: utf-8 -*-
"""最低賃金記事に「賃上げ×業務改善助成金」計算機を埋め込む（2026-09-04）。

狙い: 記事に来ている9,837人/90日（労務・経営者）に、その人の今日の課題＝賃上げの成果物を
ページ上で出し、助成金を使った設備投資（うちの導入）へ財布の見え方で接続する。
データは tools/minwage_2026.json（47県・答申/試算・発効日）と tools/gyomu_kaizen_2026.json
（助成率・上限表・但し書き）。どちらも記事本文から抽出したもの＝記事を直したら両方作り直す。

使い方: python scripts/build_minwage_calc.py   （冪等: 既存の計算機ブロックを差し替える）
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "blog", "20260803-saitei-chingin-2026.html")
ENTRY = os.path.join(ROOT, "entry.html")
MARK_S, MARK_E = "<!-- calc:start -->", "<!-- calc:end -->"

def extract_minwage(html):
    """記事の47県表から JSON を作り直す（記事を直したら計算機も追随する＝二重管理をなくす）。
    kind は 決定／答申／試算 の3値（労働局の3段階＝諮問→答申→決定。saitei_chingin_watch.py と同じ語）"""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S)
    t47 = next(tb for tb in tables if "<td>沖縄</td>" in tb)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", t47, re.S)
    out = []
    for r in rows:
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S)]
        if len(c) < 5 or c[0] in ("都道府県", "全国加重平均"):
            continue
        now = int(c[1].replace("円", "").replace(",", ""))
        m = re.search(r"([\d,]+)円\s*(決定|答申|試算)", c[4])
        assert m, "2026年度の時給の欄に 決定/答申/試算 が無い: " + c[0] + " / " + c[4]
        eff = re.search(r"(\d{1,2})月(\d{1,2})日発効", c[4])
        prev = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", c[2])  # 「この時給になった日」＝前年度の発効日
        out.append({"pref": c[0], "now": now, "new": int(m.group(1).replace(",", "")), "kind": m.group(2),
                    "effective": "2026-%02d-%02d" % (int(eff.group(1)), int(eff.group(2))) if eff else None,
                    "prev_effective": "%s-%02d-%02d" % (prev.group(1), int(prev.group(2)), int(prev.group(3))) if prev else None})
    assert len(out) == 47, "47県でない: %d" % len(out)
    return {"as_of": dt.date.today().isoformat(), "source": "blog/20260803-saitei-chingin-2026.html の47県表（各労働局一次資料で突合済み）", "prefectures": out}


import datetime as dt
mw = extract_minwage(open(ART, encoding="utf-8", newline="").read())
json.dump(mw, open(os.path.join(ROOT, "tools", "minwage_2026.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("47県JSON再生成: 決定%d／答申%d／試算%d" % tuple(sum(p["kind"] == k for p in mw["prefectures"]) for k in ("決定", "答申", "試算")))
gk = json.load(open(os.path.join(ROOT, "tools", "gyomu_kaizen_2026.json"), encoding="utf-8"))
P = json.dumps([[p["pref"], p["now"], p["new"], p["kind"], p["effective"], p["prev_effective"]] for p in mw["prefectures"]],
               ensure_ascii=False, separators=(",", ":"))
C = json.dumps([[c["course"], c["headcount"], c["small_lt30"], c["other"]] for c in gk["caps"]],
               ensure_ascii=False, separators=(",", ":"))
FUKUI = next(i for i, p in enumerate(mw["prefectures"]) if p["pref"] == "福井")

# 計算機の本体（HTML/CSS/JS）はテンプレート。__P__/__C__/__FUKUI__ を差し込む
HTML = open(os.path.join(ROOT, "scripts", "minwage_calc_block.html"), encoding="utf-8", newline="").read().replace("\r\n", "\n")
HTML = HTML.replace("__P__", P).replace("__C__", C).replace("__FUKUI__", str(FUKUI))
block = MARK_S + HTML + MARK_E

# 改行は LF に固定する。Windows の text モードで書くと記事全体が CRLF に化ける
# （2026-09-04 に実際に化けた＝348行の記事が丸ごと差分になった）。読み書きとも newline='' で通す
def read_lf(p):
    return open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")


def write_lf(p, s):
    open(p, "w", encoding="utf-8", newline="").write(s)


h = read_lf(ART)
# 既存ブロックは一度外してから、正しい位置に入れ直す（冪等）
h, n_removed = re.subn(r"\n?" + re.escape(MARK_S) + r".*?" + re.escape(MARK_E), "", h, flags=re.S)
# 挿入位置＝47県表（5列・1列目が県名）の末尾。「沖縄」の文字列検索だと先に出るランク表
# （Cランク…鹿児島・沖縄）に当たって、表の手前に入ってしまった（2026-09-04に実際にやった）
m = re.search(r"<tr>\s*<td>沖縄</td>", h)
assert m, "47県表の沖縄行が見つからない"
e = h.find("</table></div>", m.start()) + len("</table></div>")
assert e > len("</table></div>")
h = h[:e] + "\n" + block + h[e:]
how = ("差し替え" if n_removed else "新規挿入") + "（47県表の直後）"
h = re.sub(r'("dateModified"\s*:\s*")2026-09-01(")', r"\g<1>2026-09-04\2", h)

# --- 冒頭の導線（髙橋さん 2026-09-04「冒頭にアンカーリンクなど導線追入れたりしたら？」）---
# ①リード直後に計算機への入口 ②「この記事でわかること」に1行 ③追従CTAをこの記事だけ計算機へ
LEAD_S, LEAD_E = "<!-- calc-lead:start -->", "<!-- calc-lead:end -->"
lead = LEAD_S + '''<p class="calc-lead"><a href="#calc">▶ 自分の県を選ぶだけ——賃上げで増える人件費と、業務改善助成金でいくら戻るかを計算する（記事内・30秒）</a></p>
<style>.article-wrap .calc-lead{margin:-8px 0 28px}.article-wrap .calc-lead a{display:block;border:1px solid var(--accent);border-radius:4px;padding:12px 16px;font-size:.95rem;font-weight:600;color:var(--accent);text-decoration:none;background:#fff}.article-wrap .calc-lead a:hover{background:var(--bg-card)}</style>''' + LEAD_E
h = re.sub(r"\n?" + re.escape(LEAD_S) + r".*?" + re.escape(LEAD_E), "", h, flags=re.S)
toc = h.find('<div class="a-toc">')
assert toc > 0
h = h[:toc] + lead + "\n" + h[toc:]
toc_line = '・<strong>御社の数字で計算</strong>——県と時給を入れると、増える人件費と業務改善助成金の戻りが出る（<a href="#calc">計算機へ</a>）<br>\n'
if "計算機へ</a>" not in h:
    h = h.replace('<div class="a-toc"><strong>この記事でわかること</strong><br>\n',
                  '<div class="a-toc"><strong>この記事でわかること</strong><br>\n' + toc_line, 1)
assert "計算機へ</a>" in h
h = h.replace('<div class="float-cta" id="floatCta"><a href="/entry">無料で相談する →</a>',
              '<div class="float-cta" id="floatCta"><a href="#calc">御社の数字で計算する →</a>', 1)
write_lf(ART, h)
print("冒頭導線: リード直後 / わかること1行 / 追従CTA→#calc")
print("記事:", how, "/ dateModified:", re.findall(r'dateModified"\s*:\s*"([^"]+)', h))

# /entry: 種別の追加＋URLパラメータで事前入力（冪等）
e = read_lf(ENTRY)
opt = '<option value="その他">採用・取材・その他</option>'
newopt = '<option value="業務改善助成金">賃上げ・業務改善助成金を使った設備投資の相談</option>'
if newopt not in e:
    assert opt in e
    e = e.replace(opt, newopt + "\n            " + opt, 1)
PRE = """<script>
(function(){var q=new URLSearchParams(location.search);var f=document.getElementById('contact-form');if(!f)return;
var t=q.get('type'),m=q.get('memo');
if(t){var s=f.querySelector('[name="お問い合わせ種別"]');for(var i=0;i<s.options.length;i++){if(s.options[i].value===t){s.selectedIndex=i;break;}}}
if(m){var ta=f.querySelector('[name="お問い合わせ内容"]');if(ta&&!ta.value)ta.value=m+'\\n\\n（上の試算を見ながら、対象になる設備投資の形を相談したい）';}
})();
</script>
"""
if "q.get('memo')" not in e:
    assert e.count("</body>") == 1
    e = e.replace("</body>", PRE + "</body>", 1)
write_lf(ENTRY, e)
print("/entry: 種別「業務改善助成金」＋URL事前入力 OK")

# ---------------------------------------------------------------------------
# 独自URL版 /tools/gyomu-kaizen/（2026-09-04 髙橋さんGO「いいね」）
# 狙い＝「業務改善助成金 計算／シミュレーション／いくら戻る」を検索する人（＝設備投資を考えている人）を
# 取りに行く。記事内の計算機と同じテンプレを、ページとして独立させる。
# ---------------------------------------------------------------------------
TOOL_DIR = os.path.join(ROOT, "tools", "gyomu-kaizen")
TOOL = os.path.join(TOOL_DIR, "index.html")
TOOL_URL = "https://ngraph.jp/tools/gyomu-kaizen/"
os.makedirs(TOOL_DIR, exist_ok=True)
chk = read_lf(os.path.join(ROOT, "check", "index.html"))
head_common = chk[chk.find("<script async src=\"https://www.googletagmanager.com"):chk.find("<title>")]
fonts = chk[chk.find("<link rel=\"icon\""):chk.find("<style>")]
header = chk[chk.find("<header class=\"header scrolled\">"):chk.find("</header>") + len("</header>")]
footer = chk[chk.find("<footer class=\"footer\">"):chk.find("</footer>") + len("</footer>")]
faq = [
    ("業務改善助成金の対象になる会社の条件は？",
     "中小企業・小規模事業者で、事業場内の最低賃金が令和8年度の地域別最低賃金を下回っていること、解雇や賃金引下げなどの不交付事由がないことが要件です。事業場内最低賃金を50円以上、1回で引き上げ、生産性向上に資する設備投資などを行うと、その費用の一部が助成されます。"),
    ("申請の締切はいつですか？",
     "令和8年9月1日から、申請する事業場の都道府県で適用される地域別最低賃金の発効日の前日、または11月30日のいずれか早い日までです。発効日は都道府県ごとに違い、早い県は10月1日です。上の計算機で県を選ぶと締切の目安が出ます。"),
    ("AIやクラウドの月額料金は対象になりますか？",
     "クラウドサービスの利用料はライセンス契約等として対象で、契約時から3年分が上限です。事務用の汎用パソコン・タブレット・スマートフォンは対象外です。経営コンサルティングの費用は国家資格者等によるものに限られます。交付決定の前に発注・導入したものは対象外になります。"),
]
faq_html = "".join("<details><summary>%s</summary><p>%s</p></details>" % q for q in faq)
faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}, ensure_ascii=False)
page_ld = json.dumps({"@context": "https://schema.org", "@type": "WebPage", "name": "業務改善助成金はいくら戻るか——都道府県別の計算機",
                      "url": TOOL_URL, "dateModified": dt.date.today().isoformat(), "inLanguage": "ja",
                      "publisher": {"@type": "Organization", "name": "株式会社NGraph", "url": "https://ngraph.jp/"}}, ensure_ascii=False)
page = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
{head_common}<title>業務改善助成金はいくら戻る？都道府県別の計算機——賃上げで増える人件費・助成額・実質負担・申請締切 | 株式会社NGraph</title>
<meta name="description" content="県と、事業場内の最低時給・人数・設備投資額を入れると、2026年度の賃上げで増える人件費と、業務改善助成金の助成額・実質負担・申請締切の目安が出ます。厚生労働省の令和8年度交付要綱と各労働局の答申にもとづく計算です。">
<meta property="og:title" content="業務改善助成金はいくら戻る？都道府県別の計算機 | 株式会社NGraph">
<meta property="og:description" content="賃上げで増える人件費と、業務改善助成金の助成額・実質負担・申請締切を、県と会社の数字から30秒で。">
<meta property="og:type" content="website">
<meta property="og:url" content="{TOOL_URL}">
<meta property="og:site_name" content="株式会社NGraph">
<link rel="canonical" href="{TOOL_URL}">
{fonts}<style>
.c-wrap{{max-width:760px;margin:0 auto;padding:140px 20px 80px}}
.t-h1{{font-family:var(--serif);font-size:1.6rem;font-weight:900;line-height:1.6;margin:10px 0 14px}}
.t-lead{{font-size:.95rem;color:var(--text-2);line-height:2;margin-bottom:8px}}
.article-wrap .a-faq details{{border-bottom:1px solid var(--border);padding:12px 0}}
.article-wrap .a-faq summary{{cursor:pointer;font-weight:700}}
.t-links a{{display:block;padding:10px 0;border-bottom:1px solid var(--border);font-size:.9rem}}
</style>
<script type="application/ld+json">{page_ld}</script>
<script type="application/ld+json">{faq_ld}</script>
</head>
<body>
<div class="bg-fx" aria-hidden="true"></div>
{header}

<div class="c-wrap"><div class="article-wrap">
  <div class="section-label">Tool</div>
  <h1 class="t-h1">業務改善助成金はいくら戻るか——都道府県別の計算機</h1>
  <p class="t-lead">2026年度の最低賃金の引上げで御社の人件費がいくら増えるか。その賃上げに合わせて設備投資をしたとき、業務改善助成金でいくら戻り、実質負担がいくらになるか。申請の締切はいつか。県と会社の数字を入れると、30秒で目安が出ます。</p>
  <p class="t-lead">県ごとの額は各都道府県労働局の答申・決定、未答申の県は目安からの試算です。助成率と上限額は厚生労働省の令和8年度交付要綱にもとづきます。数字の時点と出典は<a href="/blog/20260803-saitei-chingin-2026">47都道府県別の一覧記事</a>と同じです。</p>

{block}

  <h2>よくある質問</h2>
  <div class="a-faq">{faq_html}</div>

  <h2>あわせて読む</h2>
  <div class="t-links">
    <a href="/blog/20260824-gyomu-kaizen-joseikin">業務改善助成金は9月1日開始——締切は県ごとに最短30日、AIの月額料金が対象になる条件</a>
    <a href="/blog/20260803-saitei-chingin-2026">最低賃金2026年度はいつから・いくら？47都道府県別の時給と発効日</a>
    <a href="/blog/ai-hojokin">AI導入に使える補助金はどれか——8制度の対象経費を読み解く実務判定表</a>
  </div>

  <div class="a-src" style="margin-top:28px">参考（一次情報）：厚生労働省「<a href="https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/zigyonushi/shienjigyou/03.html" target="_blank" rel="noopener">業務改善助成金</a>」／同「<a href="https://www.mhlw.go.jp/content/11200000/001693416.pdf" target="_blank" rel="noopener">業務改善助成金のご案内</a>」／同「<a href="https://www.mhlw.go.jp/content/11200000/001693388.pdf" target="_blank" rel="noopener">交付要綱</a>」（いずれも令和8年度）</div>
</div></div>

{footer}
</body>
</html>
'''
write_lf(TOOL, page)
print("tools/gyomu-kaizen/index.html を生成")

# sitemap（冪等）
SM = os.path.join(ROOT, "sitemap.xml")
sm = read_lf(SM)
entry = "  <url><loc>%s</loc><lastmod>%s</lastmod></url>\n" % (TOOL_URL, dt.date.today().isoformat())
if TOOL_URL not in sm:
    k = sm.find("</url>\n") + len("</url>\n")
    sm = sm[:k] + entry + sm[k:]
else:
    sm = re.sub(r"  <url><loc>%s</loc><lastmod>[^<]+</lastmod></url>\n" % re.escape(TOOL_URL), entry, sm)
write_lf(SM, sm)
print("sitemap.xml:", TOOL_URL)

# 既に(a)の読者がいる2記事から計算機へ（冪等・リード直後）
LINK_S, LINK_E = "<!-- calc-link:start -->", "<!-- calc-link:end -->"
link = LINK_S + '''<p class="calc-lead"><a href="/tools/gyomu-kaizen/">▶ 御社の県と人数で、業務改善助成金がいくら戻るか・申請締切はいつかを30秒で計算する</a></p>
<style>.article-wrap .calc-lead{margin:-8px 0 28px}.article-wrap .calc-lead a{display:block;border:1px solid var(--accent);border-radius:4px;padding:12px 16px;font-size:.95rem;font-weight:600;color:var(--accent);text-decoration:none;background:#fff}.article-wrap .calc-lead a:hover{background:var(--bg-card)}</style>''' + LINK_E
for slug in ("20260824-gyomu-kaizen-joseikin", "ai-hojokin"):
    fp = os.path.join(ROOT, "blog", slug + ".html")
    a = read_lf(fp)
    a = re.sub(r"\n?" + re.escape(LINK_S) + r".*?" + re.escape(LINK_E), "", a, flags=re.S)
    t = a.find('<div class="a-toc">')
    assert t > 0, slug + ": a-toc が無い"
    a = a[:t] + link + "\n" + a[t:]
    write_lf(fp, a)
    print("導線:", slug, "→ /tools/gyomu-kaizen/")
