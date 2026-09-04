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

HTML = r'''
<div class="a-note" id="calc" style="border-left:3px solid var(--accent)">
<p><strong>御社の数字で計算する——賃上げでいくら増えて、業務改善助成金でいくら戻るか</strong></p>
<p style="margin-bottom:10px">上の表の自分の県を選び、いまの事業場内の最低時給と人数を入れると、<strong>2026年度の引上げで増える人件費</strong>と、<strong>業務改善助成金を使って設備投資をした場合の助成額・実質負担</strong>が出ます。県の額は上の表と同じ時点のもの（決定・答申・試算の別も表のとおり）、助成金の率と上限は厚生労働省の令和8年度交付要綱にもとづきます。</p>
<div class="calc-grid">
<label>都道府県<select id="c-pref"></select></label>
<label>いまの事業場内の最低時給（円）<input type="number" id="c-now" min="800" max="2000" step="1"></label>
<label>時給を上げる人数<input type="number" id="c-n" min="1" max="500" value="5"></label>
<label>1人あたり月の労働時間<input type="number" id="c-h" min="1" max="250" value="132"><small>例: 6時間×22日＝132</small></label>
<label>事業場の労働者数<select id="c-size"><option value="s">30人未満</option><option value="l">30人以上</option></select></label>
<label>検討中の設備投資額（税抜・円）<input type="number" id="c-inv" min="0" step="10000" value="1500000"></label>
</div>
<div id="c-out" class="calc-out" aria-live="polite"></div>
<p class="a-src" style="margin-top:12px">⚠ 目安の計算です。助成の可否・コース・上限は労働局の審査で決まります。<strong>交付決定前に発注・導入したものは対象外</strong>／事務用の汎用パソコン・タブレットは対象外／クラウド・月額利用料は契約時から3年分が上限／申請期限は<strong>あなたの県の最低賃金の発効日の前日</strong>か11月30日の早い方。</p>
<p style="margin:16px 0 0"><a class="btn" id="c-cta" href="/entry?type=%E6%A5%AD%E5%8B%99%E6%94%B9%E5%96%84%E5%8A%A9%E6%88%90%E9%87%91">この結果を持って、対象経費になるか30分で確認する（無料）→</a></p>
<p class="a-src" style="margin-top:8px">計算結果が相談フォームに入った状態で開きます。受発注・請求の転記、シフト作成、社内の問い合わせ対応のような「人の時間を食っている業務」を、助成の対象になる形で設備投資に落とすところまで一緒に見ます。</p>
</div>
<style>
.article-wrap .calc-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px 18px;margin:14px 0}
.article-wrap .calc-grid label{display:flex;flex-direction:column;font-size:.86rem;color:var(--text-3);gap:4px}
.article-wrap .calc-grid input,.article-wrap .calc-grid select{font-size:1rem;padding:9px 10px;border:1px solid var(--border-strong);border-radius:4px;background:#fff;color:var(--text)}
.article-wrap .calc-grid small{font-size:.75rem}
.article-wrap .calc-out{background:#fff;border:1px solid var(--border);border-radius:4px;padding:16px 18px;margin-top:6px}
.article-wrap .calc-out table{width:100%;border-collapse:collapse;font-size:.95rem}
.article-wrap .calc-out td{padding:7px 4px;border-bottom:1px solid var(--border);vertical-align:top}
.article-wrap .calc-out td:last-child{text-align:right;white-space:nowrap;font-weight:600}
.article-wrap .calc-out td small{font-weight:400;white-space:normal}
.article-wrap .calc-out .c-big{font-size:1.25rem;color:var(--accent)}
.article-wrap .calc-out .c-ng{color:#8a3b2c;white-space:normal;font-weight:500}
@media(max-width:640px){.article-wrap .calc-grid{grid-template-columns:1fr}.article-wrap .calc-out td:last-child{white-space:normal}}
</style>
<script>
(function(){
var P=__P__;
var C=__C__;
var $=function(id){return document.getElementById(id)};
var sel=$('c-pref');P.forEach(function(p,i){var o=document.createElement('option');o.value=i;o.textContent=p[0];sel.appendChild(o)});
sel.value=__FUKUI__;
function yen(n){return n.toLocaleString('ja-JP')+'円'}
function eff(s){if(!s)return '';var m=s.split('-');return '・'+(+m[1])+'月'+(+m[2])+'日発効'}
function course(d){return d>=90?'90円':d>=70?'70円':d>=50?'50円':null}
/* 「10人以上」の区分は特例事業者（事業場内最低賃金1,050円未満、または物価高騰等要件）だけ。
   通常の事業者は8人以上が最上位（厚労省 業務改善助成金ページ・2026-09-04確認）。
   ここで機械的に判定できるのは賃金要件（now<1050）だけなので、それ以外は8人以上に置く */
function bracket(n,tokurei){return n<=1?'1人':n<=3?'2〜3人':n<=5?'4〜5人':n<=7?'6〜7人':(n>=10&&tokurei)?'10人以上':'8人以上'}
function cap(co,n,size,tokurei){
  var b=bracket(n,tokurei);var rows=C.filter(function(r){return r[0]===co});
  var hit=rows.filter(function(r){return r[1]===b})[0];
  return hit?(size==='s'?hit[2]:hit[3]):null;
}
function calc(){
  var p=P[+sel.value];var now=+$('c-now').value||p[1];var n=+$('c-n').value||0;var h=+$('c-h').value||0;var size=$('c-size').value;var inv=+$('c-inv').value||0;
  var target=p[2];var diff=Math.max(0,target-now);var month=diff*n*h;var year=month*12;
  var html='<table>';
  html+='<tr><td>'+p[0]+'の2026年度の最低賃金</td><td>'+yen(target)+'<small>（'+p[3]+eff(p[4])+'）</small></td></tr>';
  html+='<tr><td>いまの事業場内最低時給との差</td><td>'+(diff>0?'+'+diff+'円':'差なし（すでに上回っています）')+'</td></tr>';
  html+='<tr><td>増える人件費（'+n+'人×'+h+'時間）</td><td>月 '+yen(month)+' ／ <span class="c-big">年 '+yen(year)+'</span></td></tr>';
  var eligible=now<target;var raise=target-now;var co=course(raise);var sub=null;
  if(!eligible){html+='<tr><td>業務改善助成金</td><td class="c-ng">対象外の見込み——事業場内最低賃金が2026年度の地域別最低賃金以上のため</td></tr>';}
  else if(!co){html+='<tr><td>業務改善助成金</td><td class="c-ng">この差（'+raise+'円）だけでは50円コースに届きません<br><small>50円以上に上げれば対象。例: '+yen(now+50)+'に上げる（最低賃金より+'+(now+50-target)+'円上乗せ）</small></td></tr>';}
  else{
    var rate=now<1050?0.8:0.75;var tokurei=now<1050;var cp=cap(co,n,size,tokurei);
    /* 交付要綱: 助成対象経費の下限10万円／助成額は1,000円未満切り捨て（2026-09-04 一次資料で確認） */
    if(inv<100000){html+='<tr><td>業務改善助成金</td><td class="c-ng">助成対象経費の下限は10万円です（交付要綱）。10万円以上の設備投資で計算してください</td></tr>';html+='</table>';$('c-out').innerHTML=html;$('c-cta').href='/entry?type='+encodeURIComponent('業務改善助成金')+'&memo='+encodeURIComponent('【賃上げ・助成金の試算】'+p[0]+'／2026年度 '+yen(target)+'（'+p[3]+'）／現在 '+yen(now)+'／'+n+'人×'+h+'h／人件費 年'+yen(year)+'／投資額10万円未満');return;}
    sub=Math.floor(Math.min(inv*rate,cp||0)/1000)*1000;var own=inv-sub;
    html+='<tr><td>コース／助成率／上限</td><td>'+co+'コース／'+(rate===0.8?'4/5':'3/4')+'／'+yen(cp)+'<small>（'+bracket(n,tokurei)+'・'+(size==='s'?'30人未満':'30人以上')+'）</small></td></tr>';
    html+='<tr><td>設備投資 '+yen(inv)+' に対する助成額（目安）</td><td><span class="c-big">'+yen(sub)+'</span></td></tr>';
    html+='<tr><td>実質負担（目安）</td><td>'+yen(own)+'</td></tr>';
    if(inv*rate>cp)html+='<tr><td colspan="2"><small>上限に当たっています。'+yen(Math.floor(cp/rate))+'までの投資なら助成率どおりです。</small></td></tr>';
    if(n>=10&&!tokurei)html+='<tr><td colspan="2"><small>「10人以上」の上限区分（'+yen(cap(co,n,size,true))+'）は特例事業者だけ＝事業場内最低賃金が1,050円未満か、物価高騰等で利益率が前年度比3ポイント以上下がっている場合。後者に当たるなら相談時に確認します。</small></td></tr>';
  }
  html+='</table>';
  $('c-out').innerHTML=html;
  var memo='【賃上げ・助成金の試算】'+p[0]+'／2026年度 '+yen(target)+'（'+p[3]+'）／現在 '+yen(now)+'／'+n+'人×'+h+'h／人件費 年'+yen(year)+(sub!==null?'／'+co+'コース 助成目安 '+yen(sub)+'（投資'+yen(inv)+'・'+bracket(n,now<1050)+'区分）':'／助成: 要確認');
  $('c-cta').href='/entry?type='+encodeURIComponent('業務改善助成金')+'&memo='+encodeURIComponent(memo);
}
['c-pref','c-now','c-n','c-h','c-size','c-inv'].forEach(function(id){$(id).addEventListener('input',calc);$(id).addEventListener('change',calc)});
sel.addEventListener('change',function(){$('c-now').value=P[+sel.value][1];calc()});
$('c-now').value=P[__FUKUI__][1];calc();
var seen=false;$('c-inv').addEventListener('change',function(){if(!seen&&window.gtag){seen=true;gtag('event','calc_use');}});
})();
</script>
'''
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
