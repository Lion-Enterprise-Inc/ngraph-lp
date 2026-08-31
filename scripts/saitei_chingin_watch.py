#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最低賃金の答申状況を各都道府県労働局から巡回して、記事の表との差分を出す。

なぜ入れたか（2026-08-11）: `blog/20260803-saitei-chingin-2026.html` は
**ブログの検索流入のほぼ全部を1本で背負っている**（GA4実測 3週間で Organic 481セッション・
他の記事は1〜4）。この記事の中身は「都道府県ごとの答申額」で、8月中は毎日どこかの県で
答申が出る＝**放っておくと毎日古くなる**。手で47局を見る運用は続かないので機械で巡回する。

厚労省の全国一覧は全都道府県の答申が揃ってからしか出ない。それまでの一次情報は
各労働局の報道発表（HTMLかPDF）に分散していて、URLの形も局ごとに違う。
なので「局トップから最低賃金の答申らしいリンクを辿り、金額を拾う」方式にした。

使い方:
    python scripts/saitei_chingin_watch.py            # 記事で「試算」のままの県だけ巡回
    python scripts/saitei_chingin_watch.py --all      # 47局すべて巡回（答申済みの検算）
    python scripts/saitei_chingin_watch.py --pref 福井

差分（記事が試算のままなのに答申が出ている県）が1件以上あれば exit 1。
ネットワークに出るので `gate.py` には入れない（公開前ゲートを外部依存にしない）。
記事側の鮮度は `freshness_check.py` の data-recheck が見張る。
"""
import argparse
import io
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTICLE = os.path.join(ROOT, "blog", "20260803-saitei-chingin-2026.html")
UA = {"User-Agent": "Mozilla/5.0 (compatible; ngraph-blog-freshness/1.0)"}
TIMEOUT = 45

BUREAU = {
    "北海道": "hokkaido", "青森": "aomori", "岩手": "iwate", "宮城": "miyagi",
    "秋田": "akita", "山形": "yamagata", "福島": "fukushima", "茨城": "ibaraki",
    "栃木": "tochigi", "群馬": "gunma", "埼玉": "saitama", "千葉": "chiba",
    "東京": "tokyo", "神奈川": "kanagawa", "新潟": "niigata", "富山": "toyama",
    "石川": "ishikawa", "福井": "fukui", "山梨": "yamanashi", "長野": "nagano",
    "岐阜": "gifu", "静岡": "shizuoka", "愛知": "aichi", "三重": "mie",
    "滋賀": "shiga", "京都": "kyoto", "大阪": "osaka", "兵庫": "hyogo",
    "奈良": "nara", "和歌山": "wakayama", "鳥取": "tottori", "島根": "shimane",
    "岡山": "okayama", "広島": "hiroshima", "山口": "yamaguchi", "徳島": "tokushima",
    "香川": "kagawa", "愛媛": "ehime", "高知": "kochi", "福岡": "fukuoka",
    "佐賀": "saga", "長崎": "nagasaki", "熊本": "kumamoto", "大分": "oita",
    "宮崎": "miyazaki", "鹿児島": "kagoshima", "沖縄": "okinawa",
}
# 令和8年度の答申ページだけを拾う（前年度のページを掴まないため）
YEAR_HINT = ("令和8年度", "令和８年度", "令和8年", "令和８年")
# ⚠**元号だけを年の目印にすると、西暦で見出しを書く局を丸ごと取りこぼす**（2026-08-25に実測）。
# 京都「2026年08月24日 京都府最低賃金時間額1,180円へ ～…58円引上げの答申～」・
# 広島「2026年08月20日 広島県最低賃金56円（5.2％）引き上げて「時間額1,141円」へ ―…答申―」は
# どちらも答申済みなのに、ラベルに「令和8年」が1文字も無いため YEAR_HINT で落ちていた。
# 落ちた県は「答申ページが見つからない（未答申の可能性）」に混ざる＝**未答申と区別が付かない**ので、
# 22県が同じ文言で並んでも異常に見えない（2026-08-11の「ずっと緑」と同じ型の再発）。
# 局トップの見出しは先頭に配信日が付くので、西暦の年度表記も年の目印として認める。
# NEED/DENY と「現行額以下は採用しない」安全弁は従来どおり効くので、前年度を掴む risk は上がらない。
# 年度が変わったら YEAR_HINT と一緒にここも直す（令和8年度＝2026年度）。
YEAR_WEST = ("2026年", "2026/")
# 「答申」か「改正決定」を要求する。**「改正」だけでは諮問（答申の前段階）を拾う**
# ——2026-08-11、福井「改正を審議会へ諮問しました」(7/6)・静岡「改正決定に係る諮問」(6/30)を
# 答申として拾い、しかも抽出した金額は**現行額**だった（福井1,053円・静岡1,097円）。
# 答申が出ていない県を「出ている」と報告するのは、記事に嘘の数字を書かせる事故そのもの。
NEED = ("答申", "改正決定")
DENY = ("諮問", "公示", "意見聴取", "推薦", "候補者", "専門部会委員")


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    return raw if binary else raw.decode("utf-8", "replace")


def norm(t):
    return unicodedata.normalize("NFKC", t).replace("\n", "").replace(" ", "")


def pdf_text(data, tmp):
    open(tmp, "wb").write(data)
    try:
        import fitz
    except ImportError:
        return ""
    try:
        doc = fitz.open(tmp)
        t = "\n".join(p.get_text() for p in doc)
        doc.close()
        return t
    except Exception:
        return ""


def extract(text):
    """答申額・引上げ額・発効予定日を抜く。取れなかった項目は None。"""
    n = norm(text)
    got = {"amount": None, "up": None, "start": None, "rate": None}
    # 「現行時間額1,053円を59円引き上げ、時間額1,112円へ答申」型（福井 2026-08-10）を最優先。
    # 後続の汎用パターンは先頭の金額を答申額と見なすため、この型では現行額を掴んで静かに誤る。
    # 現行+引上げ=答申額 が成立したときだけ採る（成立しなければ採らず、後続の型に渡す）。
    m = re.search(r"現行[^。]{0,12}?([0-9],[0-9]{3})円を([0-9]{2})円引き?上げ[^。]{0,12}?([0-9],[0-9]{3})円", n)
    if m:
        cur, up, amt = m.group(1), m.group(2), m.group(3)
        if yen(cur) + int(up) == yen(amt):
            got["amount"] = amt
            got["up"] = up
    if not got["amount"]:
        m = re.search(r"時間額([0-9],[0-9]{3})円\(?(?:時間額)?(?:([0-9]{2})円引上げ)?", n)
        if m:
            got["amount"] = m.group(1)
            got["up"] = got["up"] or m.group(2)
    if not got["up"]:
        m = re.search(r"([0-9]{2})円引上げ", n)
        if m:
            got["up"] = m.group(1)
    if not got["amount"]:
        # 「時間額56円引上げ1,107円へ」型（引上げ額が先に来る。奈良 2026-08-10）
        m = re.search(r"([0-9]{2})円引上げ([0-9],[0-9]{3})円", n)
        if m:
            got["up"] = m.group(1)
            got["amount"] = m.group(2)
    if not got["amount"]:
        # 「現行の…1,050円から58円…引き上げ」型
        m = re.search(r"現行の[^。]{0,40}?([0-9],[0-9]{3})円から([0-9]{2})円", n)
        if m:
            got["up"] = got["up"] or m.group(2)
            got["amount"] = "{:,}".format(int(m.group(1).replace(",", "")) + int(m.group(2)))
    m = re.search(r"([0-9]{1,2}\.[0-9]{1,2})%\)?~?", n)
    if m:
        got["rate"] = m.group(1)
    m = re.search(r"発効予定日[^0-9]{0,6}([0-9]{1,2})月([0-9]{1,2})日", n)
    if m:
        got["start"] = "%s月%s日" % (m.group(1), m.group(2))
    return got


def extract_by_checksum(text):
    """語順に依存せず「現行額＋引上げ額＝答申額」が成立する組だけを採る。

    なぜ入れたか（2026-09-01）: 宮崎の答申（8/25）を取りこぼしていた。発表本文が
    「現在の宮崎県最低賃金時間額1,023円から『62円引上げ』となる『時間額1,085円』」型で、
    extract() のどの型にも当たらず、汎用型が先頭の**現行額**1,023円を掴んで
    plausible() に弾かれ、「答申額を抽出できなかった」に落ちていた。
    ⚠**弾かれた県は「未答申の可能性」の県と同じ塊で表示される**ので、
    取りこぼしと未答申が区別できない（2026-08-11・08-25と同じ型の再発）。

    局ごとに言い回しが違うので、型を足し続けても次の言い回しでまた落ちる。
    金額そのものの検算（現行＋引上げ＝答申）が通る組だけを採れば語順に依存しない。
    検算の通る組が複数あって答申額が割れる場合は、**採らない**（黙って選ばない）。
    """
    n = norm(text)
    amounts = set()
    for m in re.finditer(r"([0-9],[0-9]{3})円", n):
        v = yen(m.group(1))
        if v:
            amounts.add(v)
    ups = set()
    for m in re.finditer(r"([0-9]{2})円[」』]?引き?上げ", n):
        ups.add(int(m.group(1)))
    for m in re.finditer(r"引き?上げ[額]?[^0-9]{0,6}([0-9]{2})円", n):
        ups.add(int(m.group(1)))
    hits = set()
    for cur in amounts:
        for up in ups:
            if cur + up in amounts:
                hits.add((cur, up, cur + up))
    if not hits:
        return None
    if len({h[2] for h in hits}) != 1:
        return None  # 答申額の候補が割れた。推測しない
    cur, up, amt = sorted(hits)[-1]
    got = {"amount": "{:,}".format(amt), "up": str(up), "start": None, "rate": None}
    m = re.search(r"([0-9]{1,2}\.[0-9]{1,2})%", n)
    if m:
        got["rate"] = m.group(1)
    m = re.search(r"発効予定日[^0-9]{0,6}([0-9]{1,2})月([0-9]{1,2})日", n)
    if m:
        got["start"] = "%s月%s日" % (m.group(1), m.group(2))
    return got


def yen(s):
    try:
        return int(str(s).replace(",", ""))
    except Exception:
        return None


def probe(pref, tmpdir, now_yen=None):
    """局トップ→答申ページ→（必要なら）PDF の順に辿って金額を探す。"""
    top = "https://jsite.mhlw.go.jp/%s-roudoukyoku/" % BUREAU[pref]
    try:
        html = fetch(top)
    except Exception as e:
        return None, "局トップ取得失敗: %s" % e
    cands = []
    # 局トップのリンクラベルは「2026年08月05日\r\n\r\n\r\n令和8年度…答申されました【報道発表】\r\nNEW」
    # のように日付とNEWバッジが同じaタグに入り、改行も入る。
    # 素朴な `>([^<]{4,80})</a>` では長さと入れ子で落ちる（2026-08-11に26県すべて
    # 「未答申」と誤判定していた＝ずっと緑になる壊れた検査だった）。タグを剥がして判定する。
    seen_mw = 0      # 最低賃金を含む「日付付きの新着見出し」が局トップに何件あったか
    seen_year = 0    # うち今年度のもの
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        href = m.group(1)
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(2))).strip()
        if "最低賃金" not in label:
            continue
        # 「最低賃金の詳細」「◯◯県の最低賃金（地域別）」のような**常設のナビゲーション**は
        # 新着ではないので数に入れない（数に入れると、新着が1件も無い局が
        # 「見出しはあるが答申が無い＝未答申」に見える。青森・佐賀・宮崎で実際にそう出た）。
        # 局トップの新着は必ず配信日が頭に付く。
        if not re.match(r"(20[0-9]{2}年[0-9]{1,2}月|令和[0-9０-９]{1,2}年[0-9０-９]{1,2}月)", label):
            continue
        seen_mw += 1
        if not any(y in label for y in YEAR_HINT + YEAR_WEST):
            continue
        seen_year += 1
        if any(d in label for d in DENY):
            continue
        if not any(k in label for k in NEED):
            continue
        cands.append((urllib.parse.urljoin(top, href), label))
    if not cands:
        # ⚠**「見つからない」を1つの文言にまとめない**（2026-08-25）。取得経路が壊れていても
        # 本当に未答申でも同じ「未答申の可能性」が出ていたため、22県が同じ理由で並んでも
        # 異常に見えなかった。どこまで辿れたかを出して、壊れた経路が緑に紛れないようにする。
        if seen_mw == 0:
            return None, "局トップに最低賃金の見出しが1件も無い（**取得経路が壊れている可能性**・要確認）"
        if seen_year == 0:
            return None, ("最低賃金の見出しは%d件あるが今年度の表記が無い"
                          "（**年の判定が効いていない可能性**・要確認）" % seen_mw)
        return None, "最低賃金の見出し%d件のうち答申の見出しは無い（未答申の可能性）" % seen_year

    def plausible(got):
        """抽出した額が現行額以下なら、答申額ではなく現行額を拾っている。"""
        if not got["amount"]:
            return False
        a = yen(got["amount"])
        return not (now_yen and a and a <= now_yen)

    def read(text):
        """型で拾う→ダメなら金額の検算で拾う。どちらも現行額以下は採らない。"""
        got = extract(text)
        if plausible(got):
            return got
        got = extract_by_checksum(text)
        if got and plausible(got):
            return got
        return None

    saw_pdf = False
    for url, label in cands[:2]:
        # 見出し自体に金額が書かれている型（例: 奈良「時間額56円引上げ1,107円へ」）
        got = read(label)
        if got:
            return got, label
        try:
            page = fetch(url)
        except Exception:
            continue
        got = read(page)
        if got:
            return got, label
        for pm in list(re.finditer(r'href="([^"]+\.pdf)"', page, re.I))[:3]:
            purl = urllib.parse.urljoin(url, pm.group(1))
            try:
                data = fetch(purl, binary=True)
            except Exception:
                continue
            t = pdf_text(data, os.path.join(tmpdir, "%s.pdf" % pref))
            if not t:
                # PDFを開けたのに文字が取れていない＝読めない経路。緑に紛れさせない
                saw_pdf = True
                continue
            got = read(t)
            if got:
                return got, label
    if saw_pdf:
        return None, ("答申ページのPDFから文字が取れなかった（**PDFの読み取りが効いていない可能性**"
                      "・要確認）: %s" % cands[0][1])
    return None, "答申ページはあるが答申額を抽出できなかった（現行額しか拾えない等）: %s" % cands[0][1]


def article_state():
    """記事の47県表から {県: (現在の表記, 答申済みか)} を作る。"""
    s = io.open(ARTICLE, encoding="utf-8").read()
    tbl = [t for t in re.findall(r"<table.*?</table>", s, re.S)
           if "鳥取" in t and "1,0" in t]
    if not tbl:
        print("ERROR: 47都道府県の表が見つからない（記事の構造が変わった）")
        sys.exit(2)
    out = {}
    for row in re.findall(r"<tr>(.*?)</tr>", tbl[0], re.S)[1:]:
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td.*?</td>", row, re.S)]
        if len(cells) < 2:
            continue
        # 表には「全国加重平均」の行も入っている。県として数えると
        # 巡回対象でもないのに「試算のまま」が1件多く出続ける（2026-09-01に実測）
        if cells[0] not in BUREAU:
            continue
        out[cells[0]] = (cells[-1], "答申" in cells[-1], cells[1] if len(cells) > 2 else "")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="答申済みの県も巡回して検算する")
    ap.add_argument("--pref", help="1県だけ")
    a = ap.parse_args()

    state = article_state()
    if a.pref:
        targets = [a.pref]
    elif a.all:
        targets = [p for p in BUREAU if p in state]
    else:
        targets = [p for p, v in state.items() if not v[1] and p in BUREAU]

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="saichin_")
    print("巡回 %d県（記事の反映済み %d県 / 試算のまま %d県）"
          % (len(targets),
             sum(1 for v in state.values() if v[1]),
             sum(1 for v in state.values() if not v[1])))

    diffs, notes = [], []
    for pref in targets:
        cur, done, now = state.get(pref, ("", False, ""))
        got, why = probe(pref, tmpdir, yen(re.sub(r"[^0-9,]", "", now)))
        if not got:
            notes.append((pref, why))
            continue
        line = "答申 +%s円%s" % (got["up"] or "?",
                              "・%s発効" % got["start"] if got["start"] else "")
        if not done:
            diffs.append((pref, got, line))
            print("  差分 %s: 答申が出ている → %s円（%s）記事はいま「%s」"
                  % (pref, got["amount"], line, cur))
        else:
            ok = got["amount"] in cur
            print("  検算 %s: %s円 %s（記事: %s）"
                  % (pref, got["amount"], "一致" if ok else "★不一致", cur))
            if not ok:
                diffs.append((pref, got, line))

    print()
    if notes:
        print("答申を確認できなかった県 %d:" % len(notes))
        for pref, why in notes:
            print("  - %s: %s" % (pref, why))
    if diffs:
        print()
        print("記事の更新が必要 %d件:" % len(diffs))
        for pref, got, line in diffs:
            print("  %s\t%s円\t%s" % (pref, got["amount"], line))
        print()
        print("表の該当行を書き換えたら dateModified・sitemapのlastmod・IndexNow も更新する")
        return 1
    print("記事は最新（差分なし）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
