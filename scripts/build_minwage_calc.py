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
        out.append({"pref": c[0], "now": now, "new": int(m.group(1).replace(",", "")), "kind": m.group(2),
                    "effective": "2026-%02d-%02d" % (int(eff.group(1)), int(eff.group(2))) if eff else None})
    assert len(out) == 47, "47県でない: %d" % len(out)
    return {"as_of": dt.date.today().isoformat(), "source": "blog/20260803-saitei-chingin-2026.html の47県表（各労働局一次資料で突合済み）", "prefectures": out}


import datetime as dt
mw = extract_minwage(open(ART, encoding="utf-8", newline="").read())
json.dump(mw, open(os.path.join(ROOT, "tools", "minwage_2026.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("47県JSON再生成: 決定%d／答申%d／試算%d" % tuple(sum(p["kind"] == k for p in mw["prefectures"]) for k in ("決定", "答申", "試算")))
gk = json.load(open(os.path.join(ROOT, "tools", "gyomu_kaizen_2026.json"), encoding="utf-8"))
P = json.dumps([[p["pref"], p["now"], p["new"], p["kind"], p["effective"]] for p in mw["prefectures"]],
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
