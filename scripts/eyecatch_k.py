# -*- coding: utf-8 -*-
import argparse,html,json,os,re,sys
from pathlib import Path
W,H=1200,630
TITLE_Y=252
KICKER_Y=178

for _stream in (sys.stdout,sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError,ValueError):
        pass
def esc(x): return html.escape(str(x),quote=True)
def width(s,fs,sp=0): return sum(fs*(1 if ord(c)>=0x2e80 else .56)+sp for c in s)
def bbox(s,x,y,fs,sp=0,anchor="l"):
    ww=width(s,fs,fs*sp)
    left=x-ww if anchor=="r" else x-ww/2 if anchor=="m" else x
    right=x if anchor=="r" else x+ww/2 if anchor=="m" else x+ww
    return left,y-fs,right,y
def intersects(a,b): return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
def wrap(s,fs,box=510):
    out=[];cur="";w=0;head="」）】』〉》、。，．・？！ゃゅょっァィゥェォッャュョーぁぃぅぇぉ%％";tail="「（【『〈《"
    for c in s:
        cw=fs*(1 if ord(c)>=0x2e80 else .56)+fs*.02
        if cur and w+cw>box:
            if (c in head or cur[-1] in tail) and len(cur)>1:
                moved=cur[-1];cur=cur[:-1];out.append(cur);cur=moved+c;w=width(cur,fs,fs*.02)
            else:out.append(cur);cur=c;w=cw
        else:cur+=c;w+=cw
    if cur:out.append(cur)
    return out
def fit(s):
    for fs in range(72,59,-1):
        ls=wrap(s,fs)
        if len(ls)<=2:return fs,ls
    keep=len(s)
    while keep and len(wrap(s[:keep],60))>2:keep-=1
    raise ValueError(f"主張が2行に収まりません（60ptでも超過）。あと{max(1,len(s)-keep)}文字ほど削ってください。")
def one(s,fs,mw,name):
    if "\n" in s or width(s,fs,fs*.02)>mw:raise ValueError(f"{name}が1行に収まりません。短くしてください。")
def record(path,slug,title,sub,fs,article,pattern="k-b-diagram"):
    d=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {};h1=None
    if article and Path(article).exists():
        m=re.search(r"<h1\b[^>]*>(.*?)</h1>",Path(article).read_text(encoding="utf-8"),re.I|re.S)
        if m:h1=re.sub(r"<[^>]+>","",m.group(1)).strip()
    d[slug]={"title":title,"sub":sub,"pattern":pattern,"fs":fs,"article_h1":h1};path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(d,ensure_ascii=False,indent=1,sort_keys=True)+"\n",encoding="utf-8")
def build(slug,title,sub,hub,nodes,label,foot,fs,ls):
    if len(nodes)!=4:raise ValueError("--nodes は4語を指定してください")
    one(sub,22,510,"サブ")
    for n in nodes:one(n,19,106,"箱ラベル")
    one(hub,21,150,"中心語");one(label,17,240,"シリーズ名");one(foot,14,480,"下部キャプション")
    checks=[(label,72,54,17,.18,"l"),(f"NGRAPH / {slug}",1128,54,13,.08,"r"),("社内ナレッジ発信シリーズ",72,178,14,.08,"l"),(sub,72,425,22,.05,"l"),(foot,72,548,14,.08,"l"),(hub,882,306,21,.02,"m"),("共有できる正本",882,331,13,.08,"m"),("知識 → 判断 → 業務",882,546,13,.08,"m")]
    checks += [(x,72,TITLE_Y+i*fs*1.28,fs,.02,"l") for i,x in enumerate(ls)]
    checks += [(n,x,y,19,.02,"m") for n,x,y in [(nodes[0],737,195),(nodes[1],1027,195),(nodes[2],742,439),(nodes[3],1022,439)]]
    for v,x,y,z,sp,a in checks:
        ww=width(v,z,z*sp);left=x-ww if a=="r" else x-ww/2 if a=="m" else x;right=x if a=="r" else x+ww/2 if a=="m" else x+ww
        if left<0 or right>W or y-z<0 or y>H:raise ValueError(f"テキストがキャンバス外です: {v!r}")
    kicker_box=bbox("社内ナレッジ発信シリーズ",72,KICKER_Y,14,.08)
    first_title_box=bbox(ls[0],72,TITLE_Y,fs,.02)
    if intersects(kicker_box,first_title_box):
        raise ValueError("サブ見出しと主張1行目のバウンディングボックスが交差しています")
    titles="".join(f'<text class="title" x="72" y="{TITLE_Y+i*fs*1.28:.1f}">{esc(v)}</text>' for i,v in enumerate(ls))
    boxes=[(682,168,nodes[0]),(972,168,nodes[1]),(682,412,nodes[2]),(962,412,nodes[3])]
    ns="".join(f'<rect x="{x}" y="{y}" width="122" height="54" rx="2" class="node"/><text class="nodeText" x="{x+61}" y="{y+34}" text-anchor="middle">{esc(v)}</text>' for x,y,v in boxes)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630" role="img" aria-labelledby="title desc"><title id="title">{esc(title)} — N-KNOWLEDGE</title><desc id="desc">{esc(hub)}を中心に知識と業務がつながる構造を示す図解。</desc><defs><style>.label{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:17px;letter-spacing:.18em;fill:#8a8172}}.kicker{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:14px;letter-spacing:.08em;fill:#b05a45}}.title{{font-family:'Zen Old Mincho',serif;font-weight:700;font-size:{fs}px;letter-spacing:.02em;fill:#1a1a1a}}.sub{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:22px;letter-spacing:.05em;fill:#b05a45}}.tiny{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:13px;letter-spacing:.08em;fill:#8a8172}}.line{{fill:none;stroke:#b9b2aa;stroke-width:1.5}}.accent{{fill:none;stroke:#c8553a;stroke-width:2}}.node{{fill:#fffdf9;stroke:#d8d0c6;stroke-width:1.5}}.nodeText{{font-family:'Zen Old Mincho',serif;font-size:19px;fill:#454545}}.center{{fill:#fdf6f4;stroke:#c8553a;stroke-width:2}}</style></defs><rect width="1200" height="630" fill="#f6f2e9"/><path d="M72 74H1128" stroke="#d8d0c6"/><text class="label" x="72" y="54">{esc(label)}</text><text class="tiny" x="1128" y="54" text-anchor="end">NGRAPH / {esc(slug)}</text><text class="kicker" x="72" y="{KICKER_Y}">社内ナレッジ発信シリーズ</text>{titles}<text class="sub" x="72" y="425">{esc(sub)}</text><path d="M72 450H400" class="accent"/><text class="tiny" x="72" y="548">{esc(foot)}</text><g><path d="M882 306L737 195M882 306L1027 195M882 306L742 439M882 306L1022 439" class="line"/><circle cx="882" cy="306" r="88" class="center"/><text class="nodeText" x="882" y="306" text-anchor="middle">{esc(hub)}</text><text class="tiny" x="882" y="331" text-anchor="middle">共有できる正本</text>{ns}<circle cx="882" cy="170" r="5" fill="#c8553a"/><circle cx="882" cy="442" r="5" fill="#c8553a"/><path d="M716 500H1048" stroke="#d8d0c6"/><text class="tiny" x="882" y="546" text-anchor="middle">知識 → 判断 → 業務</text></g></svg>'''

# ---- タイトル全文型（2026-08-19新設）------------------------------------------
# 起点: 髙橋さん「表紙タイトル改行もおかしいし。なんのフックにもならない。弱すぎる」（8/19）。
# 8/18・8/19と2回続けて「抽象標語で何の記事か分からない」で差し戻された。
# 原因はレイアウトにある——図解ハブが右半分を占めるため主張が左半分に押し込まれ、
# 16字に収める過程で必ず抽象標語になる。書き手の心がけでは止まらない。
# はてなブックマークの保存上位を実測（2026-08-19・blog-specimens.jsonl）したところ、
# 1707users・1226usersとも表紙は「タイトル全文を巨大に焼いただけ・図解なし」だった。
# よってこの型では **記事タイトルの主題部をそのまま焼く**。書き手が別の文言を考える
# 余地を無くすことで、抽象標語もタイトルとのズレも構造的に起こらなくなる。
TITLE_BOX = 1056          # 左右マージン72ずつ
TITLE_MAXLINES = 3

def fit_title(s, box=TITLE_BOX, maxlines=TITLE_MAXLINES, fs_max=96, fs_min=52):
    """タイトルを最大3行に収める級数と行を返す。'|' があれば手動改行を優先する。"""
    if "|" in s:
        lines = [x.strip() for x in s.split("|") if x.strip()]
        if len(lines) > maxlines:
            raise ValueError(f"手動改行が{len(lines)}行です。{maxlines}行までにしてください")
        for fs in range(fs_max, fs_min - 1, -1):
            if all(width(l, fs, fs * .02) <= box for l in lines):
                return fs, lines
        raise ValueError("手動改行しても収まりません。1行あたりを短くしてください")
    for fs in range(fs_max, fs_min - 1, -1):
        ls = wrap(s, fs, box)
        if len(ls) <= maxlines:
            return fs, ls
    raise ValueError(f"タイトルが{maxlines}行に収まりません（{fs_min}ptでも超過）。短くするか '|' で改行位置を指定してください")

def build_title(slug, title, lines, fs, label):
    """タイトル全文型のSVG。図解・キャッチ・固定キャプションは置かない。"""
    for l in lines:
        if l and l[0] in "をがはにでとへもの、。":
            raise ValueError(f"行が助詞・句読点で始まっています: {l!r}。'|' で改行位置を指定してください")
    total = len(lines) * fs * 1.32
    top = (H - total) / 2 + fs * 0.86 + 8
    checks = [(label, 72, 54, 17, .18, "l"), (f"NGRAPH / {slug}", 1128, 54, 13, .08, "r")]
    checks += [(x, 72, top + i * fs * 1.32, fs, .02, "l") for i, x in enumerate(lines)]
    for v, x, y, z, sp, a in checks:
        ww = width(v, z, z * sp)
        left = x - ww if a == "r" else x - ww / 2 if a == "m" else x
        right = x if a == "r" else x + ww / 2 if a == "m" else x + ww
        if left < 0 or right > W or y - z < 0 or y > H:
            raise ValueError(f"テキストがキャンバス外です: {v!r}")
    ts = "".join(f'<text class="title" x="72" y="{top + i * fs * 1.32:.1f}">{esc(v)}</text>' for i, v in enumerate(lines))
    rule_y = top + (len(lines) - 1) * fs * 1.32 + fs * 0.52
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'role="img" aria-labelledby="title"><title id="title">{esc(title)} — N-KNOWLEDGE</title>'
            f'<defs><style>'
            f".label{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:17px;letter-spacing:.18em;fill:#8a8172}}"
            f".title{{font-family:'Zen Old Mincho',serif;font-weight:700;font-size:{fs}px;letter-spacing:.02em;fill:#1a1a1a}}"
            f".tiny{{font-family:'Zen Kaku Gothic New',sans-serif;font-size:13px;letter-spacing:.08em;fill:#8a8172}}"
            f'</style></defs>'
            f'<rect width="{W}" height="{H}" fill="#f6f2e9"/>'
            f'<path d="M72 74H1128" stroke="#d8d0c6"/>'
            f'<text class="label" x="72" y="54">{esc(label)}</text>'
            f'<text class="tiny" x="1128" y="54" text-anchor="end">NGRAPH / {esc(slug)}</text>'
            f'{ts}'
            f'<path d="M72 {rule_y:.1f}H300" stroke="#c8553a" stroke-width="3"/>'
            f'</svg>')

def main():
    p=argparse.ArgumentParser()
    p.add_argument("slug");p.add_argument("title");p.add_argument("sub",nargs="?",default="")
    p.add_argument("--layout",choices=("title","hub"),default="title",
                   help="title=タイトル全文型（既定・2026-08-19）／hub=旧B案の図解ハブ型")
    p.add_argument("--hub");p.add_argument("--nodes")
    p.add_argument("--label",default="N-KNOWLEDGE")
    p.add_argument("--foot",default="FIELD NOTE  /  COMPANY BRAIN")
    p.add_argument("--out",required=True);p.add_argument("--record");p.add_argument("--article")
    p.add_argument("--wide",action="store_true",
                   help="X Articles用の横長版(1500x600)。ブログの表紙は1200x630のままが正なので --record と併用不可")
    a=p.parse_args()
    if a.wide and a.record:
        print("NG: --wide は --record と併用しない（ブログ用の表紙の記録を横長版で上書きしないため）",file=sys.stderr);return 3
    try:
        out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
        if a.layout=="title":
            # 表紙に焼くのは記事タイトルの主題部そのもの。書き手が別の文言を考えない
            # ＝抽象標語とタイトルとのズレが構造的に起きない（2026-08-19・標本実測）
            fs,ls=fit_title(a.title)
            svg=build_title(a.slug,a.title.replace("|",""),ls,fs,a.label)
        else:
            if not a.hub or not a.nodes:raise ValueError("hub型には --hub と --nodes が必要です")
            nodes=[x.strip() for x in a.nodes.split(",")]
            if len(nodes)!=4 or any(not x for x in nodes):raise ValueError("--nodes は空語なしの4語を指定してください")
            fs,ls=fit(a.title)
            svg=build(a.slug,a.title,a.sub,a.hub,nodes,a.label,a.foot,fs,ls)
        # 移植時の統合（2026-08-15）: --out が .jpg なら既存表紙と同じ経路でJPG化する。
        # SVG生成と自己検査までがCodexの納品契約で、レンダリングは受入側の持ち場
        if out.suffix.lower() in (".jpg",".jpeg"):svg_to_jpg(svg,str(out),wide=a.wide)
        else:out.write_text(svg+"\n",encoding="utf-8")
        if a.record:record(Path(a.record),a.slug,a.title.replace("|",""),a.sub,fs,a.article,
                           "k-title" if a.layout=="title" else "k-b-diagram")
        print(f"OK {out} fs={fs} lines={len(ls)}");return 0
    except (ValueError,OSError,json.JSONDecodeError) as e:print(f"ERROR: {e}",file=sys.stderr);return 3

# ---- 移植時の統合（2026-08-15・受入後にClaude側で追加）--------------------------
# Codexの納品契約はSVG生成まで。ブログの表紙は assets/blog/<slug>.jpg なので、
# --out が .jpg のときは eyecatch_gen.py と同じ経路（headlessスクリーンショット→PIL）で
# 変換する。レンダラは共有せず薄く持つ（既存ジェネレータを触らないため）。
import subprocess as _sp
import tempfile as _tmp
import time as _time

_EDGE = r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"

def svg_to_jpg(svg_text, out_jpg, wide=False):
    """SVGをJPGにする。wide=True で X Articles 用の横長版（1500x600）。

    なぜ横長版が要るか〔実測 2026-08-17・eyecatch_gen.py と同じ根拠〕: Xのカバー枠は
    約2.5〜2.7:1で、1200x630（1.90:1）を上げると**上下が切れて見出しとラベルが飛ぶ**。

    k系の表紙は座標が焼かれたSVGなので、eyecatch_gen.py の --wide（同じHTMLを広い
    ビューポートで描き直す）と同じ手は使えない。代わりに**1500x600の地色の上に、
    SVG全体を高さ600に合わせて（1143x600）中央へ置く**。切り抜きではないので文字は
    1つも欠けない（縦横とも95.2%の等倍縮小）。左右の余白は表紙と同じ地色 #f6f2e9 で埋める。
    """
    cw, ch = (1500, 600) if wide else (1200, 630)
    if wide:
        sw, sh = 1143, 600          # 1200x630 を高さ600に合わせた等倍（左右に178.5pxずつ余白）
        box = ('body{width:1500px;height:600px;overflow:hidden;background:#f6f2e9;'
               'display:flex;align-items:center;justify-content:center}'
               'svg{display:block;width:%dpx;height:%dpx}' % (sw, sh))
    else:
        box = ('body{width:1200px;height:630px;overflow:hidden}'
               'svg{display:block;width:1200px;height:630px}')
    d = _tmp.mkdtemp(prefix="eyecatch_k_")
    hp = os.path.join(d, "cover.html")
    open(hp, "w", encoding="utf-8").write(
        '<!doctype html><meta charset="utf-8"><style>*{margin:0}' + box + '</style>' + svg_text)
    png = os.path.join(d, "cover.png")
    udd = _tmp.mkdtemp(prefix="eyecatch_k_udd_")
    _sp.run([_EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--window-size=%d,%d" % (cw, ch), "--user-data-dir=" + udd,
             "--hide-scrollbars", "--virtual-time-budget=8000",
             "--screenshot=" + png, "file:///" + hp.replace("\\", "/")],
            capture_output=True)
    for _ in range(10):
        if os.path.exists(png) and os.path.getsize(png) > 10000:
            break
        _time.sleep(1)
    if not os.path.exists(png) or os.path.getsize(png) <= 10000:
        print("ERROR: headlessスクリーンショットに失敗。ブラウザペイン起動中はEdgeが無言死する既知事象"
              "（memory: technique_headless_edge_user_data_dir）。Chromeで再試行:")
        print(r'  "C:/Program Files/Google/Chrome/Application/chrome.exe" で同じ引数')
        sys.exit(2)
    from PIL import Image
    Image.open(png).convert("RGB").save(out_jpg, "JPEG", quality=86)


if __name__ == "__main__":
    # main() の戻り値を捨てていたため、ERROR でも exit 0 で返っていた（2026-08-20実測）。
    # 呼び出し側（x_article.py の横長カバー生成）は returncode で成否を見るので、
    # 失敗が成功として通っていた
    sys.exit(main())
