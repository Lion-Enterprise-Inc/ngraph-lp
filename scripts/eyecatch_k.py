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
def record(path,slug,title,sub,fs,article):
    d=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {};h1=None
    if article and Path(article).exists():
        m=re.search(r"<h1\b[^>]*>(.*?)</h1>",Path(article).read_text(encoding="utf-8"),re.I|re.S)
        if m:h1=re.sub(r"<[^>]+>","",m.group(1)).strip()
    d[slug]={"title":title,"sub":sub,"pattern":"k-b-diagram","fs":fs,"article_h1":h1};path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(d,ensure_ascii=False,indent=1,sort_keys=True)+"\n",encoding="utf-8")
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
def main():
    p=argparse.ArgumentParser();p.add_argument("slug");p.add_argument("title");p.add_argument("sub");p.add_argument("--hub",required=True);p.add_argument("--nodes",required=True);p.add_argument("--label",default="N-KNOWLEDGE");p.add_argument("--foot",default="FIELD NOTE  /  COMPANY BRAIN");p.add_argument("--out",required=True);p.add_argument("--record");p.add_argument("--article");a=p.parse_args()
    try:
        nodes=[x.strip() for x in a.nodes.split(",")]
        if len(nodes)!=4 or any(not x for x in nodes):raise ValueError("--nodes は空語なしの4語を指定してください")
        fs,ls=fit(a.title);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
        svg=build(a.slug,a.title,a.sub,a.hub,nodes,a.label,a.foot,fs,ls)
        # 移植時の統合（2026-08-15）: --out が .jpg なら既存表紙と同じ経路でJPG化する。
        # SVG生成と自己検査までがCodexの納品契約で、レンダリングは受入側の持ち場
        if out.suffix.lower() in (".jpg",".jpeg"):svg_to_jpg(svg,str(out))
        else:out.write_text(svg+"\n",encoding="utf-8")
        if a.record:record(Path(a.record),a.slug,a.title,a.sub,fs,a.article)
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

def svg_to_jpg(svg_text, out_jpg):
    d = _tmp.mkdtemp(prefix="eyecatch_k_")
    hp = os.path.join(d, "cover.html")
    open(hp, "w", encoding="utf-8").write(
        '<!doctype html><meta charset="utf-8"><style>*{margin:0}'
        'body{width:1200px;height:630px;overflow:hidden}'
        'svg{display:block;width:1200px;height:630px}</style>' + svg_text)
    png = os.path.join(d, "cover.png")
    udd = _tmp.mkdtemp(prefix="eyecatch_k_udd_")
    _sp.run([_EDGE, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--window-size=1200,630", "--user-data-dir=" + udd,
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
    main()
