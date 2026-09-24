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
    python scripts/saitei_chingin_watch.py            # まだ確定していない県を巡回（既定）
    python scripts/saitei_chingin_watch.py --all      # 47局すべて巡回
    python scripts/saitei_chingin_watch.py --pref 福井

⚠**既定の巡回対象を「試算のままの県」から「まだ確定していない県」に変えた（2026-09-24）**。
2026-09-16に47県すべてが答申以上になった結果、**巡回対象が0県になり、それでも
「記事は最新（差分なし）」と緑を返していた**。検査が死んでいても同じ出力になる状態＝
このファイルが2026-08-11に一度直した「ずっと緑」の型の再発。実際、宮崎は9月24日に
決定（官報公示・発効日10月24日）が出ていたのに、記事は「答申・発効日なし」のままで、
watch は1県も見に行かなかった。

最低賃金は **試算 → 答申 → 決定（官報公示）→ 発効** と進むので、段階で数える。
既定の巡回対象は「決定まで進んでいて、かつ発効日が記事に入っている県」以外の全部。
全県がそこまで到達したときだけ対象が0になり、そのときは緑ではなく「巡回対象なし」と出す。

exit code:
    0 … 差分なし・対象県をすべて確認できた
    1 … 記事の更新が必要（金額のズレ・段階の進行・発効日の判明）
    2 … 確認できなかった県がある（取得経路が壊れている可能性。緑にしない）
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
# ⚠**「公示」を一律で弾くと、決定（官報公示）の記者発表まで落ちる**（2026-09-24に実測）。
# 北海道「北海道最低賃金の改正決定の官報公示に係る記者発表」(9/1) は決定済みの発表なのに
# DENY の「公示」で捨てられていた。かといって「公示」を外すと、東京「東京地方最低賃金審議会の
# 意見に関する公示について」や鹿児島「…意見に関する公示」を答申として拾う。
# **47局の見出しを実際に採って確かめたところ、「公示」という語は一度も仕事をしていなかった**
# （2026-09-24・全局を巡回して「最低賃金」と「公示」を含む見出しを集めた結果は7件で、
# そのうち弾くべきものは全部「諮問」「意見聴取」で先に落ちる）。一方で「公示」を弾くと、
# 京都「京都府最低賃金は令和8年11月16日から時間額1,180円に ー改正決定（官報公示）とー」(9/18)
# のような**金額も発効日も入った決定の告知**を殺す。守っていないものを守るふりをして、
# 本当に要る発表を落としていたので、語そのものを外した。
# 代わりに、集めた実物7件を下の SELFTEST_LABELS に入れて挙動を固定した
# （検査を消したのではなく、当て先を「言葉の勘」から「実物の標本」に移した）。
DENY_HARD = ("諮問", "意見聴取", "推薦", "候補者", "専門部会委員")
DENY = DENY_HARD  # 旧名（外から参照されている場合に備えて残す）
# 特定（産業別）最低賃金は地域別とは別の制度で、金額も別。地域別の表に混ぜたら記事が壊れる。
# 実物: 愛媛「愛媛県特定最低賃金改正決定に係る意見聴取等に関する公示」・
# 三重「…意見聴取に関する公示（特定（産業別）最低賃金）」（2026-09-24に採取）。
# いまは偶然「意見聴取」で落ちているだけなので、制度名そのもので弾く。
TOKUTEI = re.compile(r"(?:特定[（(]?(?:産業別)?[）)]?最低賃金|産業別最低賃金|特定最低賃金)")
# ⚠**見出しに「答申」と書かない局がある**（2026-09-16に実測）。秋田「秋田県最低賃金を時間額
# 1,090円に」（8/18・本文は答申）・佐賀「佐賀県最低賃金が令和8年11月15日から1,095円に」（9/1・
# PDF本文は答申）はどちらも答申済みなのに、NEED を**見出しだけ**に当てていたため落ちていた。
# 落ちた県は「答申の見出しは無い（未答申の可能性）」に混ざる＝また未答申と区別が付かない。
# よって、金額が書かれた見出しは「かもしれない」として拾い、**本文に答申/改正決定があるときだけ**
# 採用する（諮問の安全弁は本文側にも掛ける＝本文が諮問なら採らない）。
# 金額そのものは従来どおり extract/checksum で拾い、現行額以下は plausible() が弾く。
AMOUNT_HINT = re.compile(r"(?:時間額)?[0-9０-９][,，]?[0-9０-９]{3}\s*円")


def label_kind(label):
    """局トップの見出し1本を、答申・決定ページの候補として見るかどうか判定する。

    'sure'  … 見出しに答申/改正決定がある（従来どおり）
    'maybe' … 答申とは書いていないが金額がある（本文に答申・決定があるときだけ採る）
    None    … 候補にしない
    """
    if any(d in label for d in DENY_HARD):
        return None
    if TOKUTEI.search(label) and "地域別" not in label:
        return None
    if any(k in label for k in NEED):
        return "sure"          # 答申、および決定（官報公示）の記者発表
    if AMOUNT_HINT.search(label):
        return "maybe"
    return None


# 発効日の言い回しは局ごとに違う。実物（2026-09-24に採取）:
#   北海道PDF「発効日は令和８年10月１日です」「効力発生日は令和８年10月１日です」
#   宮崎PDF「最低賃金が10月24日から時間額1,085円（62円の引上げ）に改正されます」
#            「これにより10月24日から宮崎県最低賃金は1,085円となり、…適用されます」
# 「発効予定日」しか見ていなかったので、決定まで進んだ県の発効日を1つも拾えていなかった。
# 「発効日」と名乗っている型。⚠**年を書いてある場合は今年度のものだけ採る**
# （2026-09-24・群馬の答申文の別紙に「発効日 令和6年10月4日」という**前年度**の記載があり、
# それを今年の発効日として拾っていた。年を無視すると、古い資料が新しい事実として入ってくる）。
START_STRICT = (
    r"発効日[はを]?[^0-9]{0,10}(?:令和([0-9]{1,2})年)?([0-9]{1,2})月([0-9]{1,2})日",
    r"効力発生日[はを]?[^0-9]{0,10}(?:令和([0-9]{1,2})年)?([0-9]{1,2})月([0-9]{1,2})日",
    r"発効予定日[^0-9]{0,6}(?:令和([0-9]{1,2})年)?([0-9]{1,2})月([0-9]{1,2})日",
)
YEAR_WAREKI = "8"  # 令和8年度。年度が変わったらここも直す
# 「◯月◯日から…適用/改正」型。**同じ文にその県の金額があるときだけ**採る（find_start 参照）
START_LOOSE = r"([0-9]{1,2})月([0-9]{1,2})日から[^。]{0,60}?(?:適用|改正)"


def find_start(n, amount=None):
    """正規化済みテキストから発効日を拾う。見つからなければ None。

    ⚠**緩い型（「◯月◯日から…適用/改正」）は、同じ文にその県の金額が無ければ採らない**
    （2026-09-24・初回の巡回で嘘の発効日を大量に作った）。金額の裏取りを付ける前は、
    茨城「6月1日」・千葉「12月25日」のような**最低賃金の発効ではあり得ない日付**を拾って
    「発効日が判明」と報告していた。ページには特定（産業別）最低賃金や助成金の日付も載るので、
    日付の形だけを手がかりにすると、もっともらしい嘘が作れてしまう。
    """
    if not amount:
        return None
    bare = amount.replace(",", "")
    # ⚠**その県の額が同じ資料に書かれていないなら、そこに載っている日付は別の話の日付**
    # （2026-09-24・神奈川の記者発表に同封された業務改善助成金の案内に「発効日の前日
    # 令和8年9月1日」という**例示**があり、それを神奈川の発効日として拾っていた）。
    if bare not in n.replace(",", ""):
        return None
    for pat in START_STRICT:
        for m in re.finditer(pat, n):
            era, mm, dd = m.group(1), m.group(2), m.group(3)
            if era and era != YEAR_WAREKI:
                continue          # 前年度以前の資料の発効日
            return "%s月%s日" % (int(mm), int(dd))
    for m in re.finditer(START_LOOSE, n):
        if bare in m.group(0).replace(",", ""):
            return "%s月%s日" % (int(m.group(1)), int(m.group(2)))
    return None


def needs_checksum(text):
    """この資料から金額を採るとき、検算（現行＋引上げ＝答申）を必須にするか。

    ⚠**特定（産業別）最低賃金が併記された資料は、額が2つ並ぶ**（2026-09-24）。千葉の周知
    リーフレットは「◆千葉県最低賃金 ◆特定最低賃金／時間額1,210円 時間額1,195円」で、
    素直に先頭の額を採ると**特定側の1,210円**を千葉県の地域別最低賃金として拾う（正しくは1,195円）。
    ただし、**特定最低賃金という語が出てくるだけで資料ごと捨てると行き過ぎる**——同じ日に試して、
    確認できない県が10→17に増えた（北海道・岩手・群馬・三重・滋賀・愛媛などの正規の記者発表にも、
    注記としてこの語が出てくる）。そこで、捨てるのではなく**検算を必須にする**。
    現行額＋引上げ額＝答申額 が成立する組しか採らないので、隣に並んだ別制度の額は通らない。
    """
    return bool(TOKUTEI.search(norm(text)))


def stage_of_text(text):
    """発表本文が答申の段階か、決定（官報公示）まで進んだかを返す。

    2=決定 / 1=答申 / 0=どちらとも読めない。
    決定の目印は「官報に公示」＋「決定」。諮問・答申の段階の発表には官報公示は出てこない
    （官報公示は労働局長が異議申出などの手続きを経てから行うもの）。実物で確認した文:
      北海道「…改正することを決定し、令和８年９月１日、官報公示を行いました」
      宮崎「…改正することを決定し、本日（９月24日）、官報に公示されました」
    """
    n = norm(text)
    if re.search(r"官報.{0,8}公示", n) and "決定" in n:
        return 2
    if any(k in n for k in NEED):
        return 1
    return 0


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
    got["start"] = find_start(n)
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
    got["start"] = find_start(n)
    return got


STAGE_NAMES = {0: "試算", 1: "答申", 2: "決定"}


def start_passed(start, today=None):
    """記事に書いてある発効日（「10月1日」形式）が、もう過ぎているか。

    最低賃金は10〜12月に順次発効するので、発効日を過ぎた県は記事の「◯月◯日発効」という
    書き方そのものが古くなる（読者は未来の予定として読む）。機械で名指しできるのはここまでで、
    本文をどう書き直すかは人が決める。
    """
    if not start:
        return False
    m = re.match(r"([0-9]{1,2})月([0-9]{1,2})日", start)
    if not m:
        return False
    import datetime
    t = today or datetime.date.today()
    # 発効はその年度内（10〜12月）なので、年は記事の年度に合わせて今年で見る
    try:
        d = datetime.date(t.year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return False
    return d <= t


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
        kind = label_kind(label)
        if not kind:
            continue
        cands.append((urllib.parse.urljoin(top, href), label, kind))
    if not cands:
        # ⚠**「見つからない」を1つの文言にまとめない**（2026-08-25）。取得経路が壊れていても
        # 本当に未答申でも同じ「未答申の可能性」が出ていたため、22県が同じ理由で並んでも
        # 異常に見えなかった。どこまで辿れたかを出して、壊れた経路が緑に紛れないようにする。
        if seen_mw == 0:
            return None, "局トップに最低賃金の見出しが1件も無い（**取得経路が壊れている可能性**・要確認）"
        if seen_year == 0:
            return None, ("最低賃金の見出しは%d件あるが今年度の表記が無い"
                          "（**年の判定が効いていない可能性**・要確認）" % seen_mw)
        return None, "最低賃金の見出し%d件のうち答申・金額の見出しは無い（未答申の可能性）" % seen_year

    def plausible(got):
        """抽出した額が現行額以下なら、答申額ではなく現行額を拾っている。"""
        if not got["amount"]:
            return False
        a = yen(got["amount"])
        return not (now_yen and a and a <= now_yen)

    def read(text):
        """型で拾う→ダメなら金額の検算で拾う。どちらも現行額以下は採らない。

        採れたときは、**その金額を採ったのと同じテキスト**から段階と発効日も拾う。
        別のページから段階や日付を持ってくると、県の発表と支援策の案内が混ざる。
        """
        if needs_checksum(text):
            got = extract_by_checksum(text)
            if not (got and plausible(got)):
                return None
        else:
            got = extract(text)
            if not plausible(got):
                got = extract_by_checksum(text)
                if not (got and plausible(got)):
                    return None
        got["stage"] = stage_of_text(text)
        got["start"] = find_start(norm(text), got["amount"])
        return got

    def enrich(got, text):
        """段階・発効日だけを後から補う。**金額と引上げ額は絶対に上書きしない**。

        見出しだけで金額が採れた県（奈良型）は、段階と発効日が見出しに無い。そこで本文を
        読みに行くが、そのとき本文の金額で上書きすると別の制度の額を掴む
        （2026-09-24の初回巡回で、千葉・群馬・長崎の金額と引上げ額が実際に壊れた）。
        """
        if got.get("stage", 0) < 2:
            st = stage_of_text(text)
            if st > got.get("stage", 0):
                got["stage"] = st
        if not got.get("start"):
            got["start"] = find_start(norm(text), got["amount"])
        return got

    saw_pdf = False
    # 「答申」と書いた見出しを先に見る（従来の経路を変えない）。金額だけの見出しはその後。
    cands.sort(key=lambda c: 0 if c[2] == "sure" else 1)

    def body_says_toshin(text):
        """本文が答申/改正決定を名乗っているか。諮問の本文は採らない。"""
        head = text[:4000]
        if "諮問" in head and not any(k in head for k in NEED):
            return False
        return any(k in text for k in NEED)

    for url, label, kind in cands[:3]:
        head_got = None
        # 見出し自体に金額が書かれている型（例: 奈良「時間額56円引上げ1,107円へ」）。
        # ただし「答申」と書いていない見出しは、本文を読むまで採らない。
        if kind == "sure":
            head_got = read(label)
        try:
            page = fetch(url)
        except Exception:
            if head_got:
                return head_got, label
            continue
        if head_got:
            # 金額は見出しのものを使い、段階と発効日だけ本文・PDFで補う
            enrich(head_got, page)
            if not (head_got["stage"] and head_got["start"]):
                for pm in list(re.finditer(r'href="([^"]+\.pdf)"', page, re.I))[:2]:
                    try:
                        data = fetch(urllib.parse.urljoin(url, pm.group(1)), binary=True)
                    except Exception:
                        continue
                    t = pdf_text(data, os.path.join(tmpdir, "%s.pdf" % pref))
                    if t:
                        enrich(head_got, t)
                    if head_got["stage"] and head_got["start"]:
                        break
            return head_got, label
        if kind == "maybe" and not body_says_toshin(norm(page)):
            # PDFに本文がある型（佐賀）もあるので、ここでは捨てずにPDFへ進む
            page_ok = False
        else:
            page_ok = True
        if page_ok:
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
            if kind == "maybe" and not body_says_toshin(t):
                continue
            got = read(t)
            if got:
                return got, label
    if saw_pdf:
        return None, ("答申ページのPDFから文字が取れなかった（**PDFの読み取りが効いていない可能性**"
                      "・要確認）: %s" % cands[0][1])
    return None, "答申ページはあるが答申額を抽出できなかった（現行額しか拾えない等）: %s" % cands[0][1]


def stage_of_cell(cell):
    """記事の表のセルが、その県をどの段階として書いているか。2=決定 / 1=答申 / 0=試算。"""
    if "決定" in cell:
        return 2
    if "答申" in cell:
        return 1
    return 0


def start_of_cell(cell):
    """記事の表のセルに書いてある発効日。無ければ None。"""
    m = re.search(r"([0-9]{1,2})月([0-9]{1,2})日発効", norm(cell))
    return "%s月%s日" % (int(m.group(1)), int(m.group(2))) if m else None


def article_state():
    """記事の47県表から {県: {cell, stage, start, now}} を作る。"""
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
        # 段階は 試算(0) → 答申(1) → 決定(2)。2026-09-16まで「答申以上かどうか」の真偽値で
        # 持っていたが、それだと**答申から決定への進行が記事にもこの検査にも現れない**。
        cell = cells[-1]
        out[cells[0]] = {
            "cell": cell,
            "stage": stage_of_cell(cell),
            "start": start_of_cell(cell),
            "now": cells[1] if len(cells) > 2 else "",
        }
    return out


SELFTEST_LABELS = [
    # 実物の見出し（2026-09-16に局トップから採取）。検査を緩めたら、ここが落ちる。
    ("2026年08月18日 秋田県最低賃金を時間額1,090円に【報道発表】", "maybe"),
    ("2026年09月01日 佐賀県最低賃金が令和8年11月15日から1,095円に", "maybe"),
    ("2026年08月24日 京都府最低賃金時間額1,180円へ ～58円引上げの答申～", "sure"),
    ("2026年08月20日 広島県最低賃金56円引き上げて「時間額1,141円」へ ―答申―", "sure"),
    # 諮問は答申の前段階。拾ったら記事に現行額を書く事故になる（2026-08-11に実際に起きかけた）
    ("2026年07月06日 福井県最低賃金の改正を審議会へ諮問しました", None),
    ("2026年06月30日 静岡県最低賃金の改正決定に係る諮問について", None),
    ("2026年08月26日 鹿児島地方最低賃金審議会の意見に関する公示", None),
    ("2026年05月01日 最低賃金の履行確保に向けた取組について", None),
    # 決定（官報公示）の記者発表。「公示」で一律に弾いていたため落ちていた（2026-09-24に実測）
    ("2026年09月01日 北海道最低賃金の改正決定の官報公示に係る記者発表", "sure"),
    ("2026年09月24日 最低賃金が10月24日から時間額1,085円（62円の引上げ）に改正されます", "maybe"),
    ("2026年09月01日 東京都最低賃金を1,280円に引上げます", "maybe"),
    # 決定の「前」の手続きの公示。決定と同じ語を含むので、ここを通したら事故になる
    ("2026年09月16日 最低賃金の改正決定に係る関係労働者及び関係使用者の意見聴取に関する公示", None),
    ("2026年08月05日 東京地方最低賃金審議会の意見に関する公示について", None),
    ("2026年09月16日 令和8年度 北海道地方最低賃金審議会に関する公示について", None),
    # 47局を巡回して集めた「最低賃金」＋「公示」の実物（2026-09-24）。
    # 「公示」という語を弾きに使うのをやめた判断は、この7件が根拠。
    ("2026年09月18日 京都府最低賃金は令和8年11月16日から時間額1,180円に "
     "ー京都府最低賃金の改正決定（官報公示）と各種支援についてー", "sure"),
    ("2026年08月05日 香川県最低賃金の改正決定に係る香川地方最低賃金審議会の意見に関する公示", "sure"),
    ("2026年08月21日 最低賃金の改正決定に係る関係労働者及び関係使用者の意見聴取に関する公示"
     "（特定（産業別）最低賃金）", None),
    ("2026年07月28日 愛媛県特定最低賃金改正決定に係る意見聴取等に関する公示を掲載しました。", None),
    ("2026年08月28日 地域別最低賃金の決定（改正決定）に係る関係労働者及び関係使用者の"
     "意見聴取に関する公示", None),
    # ⚠この1件だけは**合成**（実物ではない）。特定（産業別）最低賃金は答申が11〜12月に出るため、
    # 2026-09-24の巡回では「金額入りの特定最低賃金の見出し」を1件も採れなかった。
    # 実物が採れたら差し替える。合成と実物を混ぜて「実測」と呼ばないための注記。
    ("（合成）愛媛県特定最低賃金を時間額1,090円に改正する答申", None),
]

# 発表本文の段階判定と発効日の抽出を、実物の文（2026-09-24に労働局のPDFから採取）で検査する。
# 見出しだけの検査では、段階（答申か決定か）と発効日を取り違えても気づけない。
# (名前, 期待する段階, 期待する発効日, その県の答申額, 本文)
SELFTEST_BODIES = [
    ("北海道・決定", 2, "10月1日", "1,131",
     "北海道労働局長は、北海道最低賃金を56円引上げ、時間額1,131円に改正することを決定し、"
     "令和８年９月１日、官報公示を行いました。効力発生日は令和８年10月１日です。"),
    ("宮崎・決定", 2, "10月24日", "1,085",
     "同審議会は、８月25日、現行の時間額1,023円を62円引き上げて、1,085円に改正することが"
     "適当である旨の答申を行いました。これを受けて宮崎労働局長は、異議申出などの諸手続を経て、"
     "宮崎県最低賃金を時間額1,085円に改正することを決定し、本日（９月24日）、官報に公示されました。"
     "これにより10月24日から宮崎県最低賃金は1,085円となり、すべての労働者に適用されます。"),
    ("答申のみ（決定にしない）", 1, None, "1,090",
     "同審議会は、現行の時間額1,031円を59円引き上げて時間額1,090円に改正することが"
     "適当である旨の答申を行いました。"),
    ("諮問（段階0のまま）", 0, None, "1,090",
     "岩手県最低賃金の改正について、岩手地方最低賃金審議会に諮問しました。"),
    # ⚠2026-09-24の初回巡回で実際に嘘の発効日を作った型。金額の裏取りが無いと「6月1日」を拾う。
    # 最低賃金の発効は10〜12月なので、6月1日は一目で嘘と分かるが、機械は日付の形しか見ない。
    ("金額の裏取りが無い日付は採らない", 1, None, "1,136",
     "茨城県最低賃金の改正について答申がありました。なお、産業別の最低賃金は"
     "6月1日から適用されます。"),
    # ⚠ 前年度の資料に書かれた発効日（群馬の答申文の別紙・2026-09-24に実測）
    ("前年度の発効日は採らない", 1, None, "1,120",
     "この最低賃金額は1時間1,120円とする旨の答申を受けました。"
     "参考: 前回の改正の発効日令和6年10月4日"),
    # ⚠ 同封の助成金案内に出てくる例示の日付（神奈川・2026-09-24に実測）
    ("その県の額が無い資料の日付は採らない", 0, None, "1,279",
     "例: 10月1日に新しい地域別最低賃金（1,040円→1,090円）が発効される場合、"
     "発効日の前日令和8年9月1日までに引上げを完了してください。"),
]


# 検算を必須にする資料かの判定（実物・2026-09-24に労働局のPDFから採取）。
# あわせて「検算を必須にすると千葉のリーフレットから額が採れなくなる」ことも確かめる
# ＝ここが通ってしまうと、特定最低賃金の額を記事に書く事故に戻る。
SELFTEST_USABLE = [
    ("千葉の周知リーフレット（特定と地域別が並ぶ）", True,
     "◆千葉県最低賃金 ◆特定最低賃金 千葉県の最低賃金 時間額 時間額1,210円 時間額1,195円"),
    ("神奈川の記者発表（地域別だけ）", False,
     "「神奈川県最低賃金」について時間額1,279円（引上げ額54円）とする旨の答申がありました。"),
]


def selftest():
    """見出し判定・段階判定・発効日の抽出を、実物の文字列で検査する（ネットワークに出ない）。"""
    bad = 0
    for label, exp in SELFTEST_LABELS:
        got = label_kind(label)
        if got != exp:
            bad += 1
            print("  NG 見出し %-6s（期待 %s）: %s" % (got, exp, label))
    for name, exp_stage, exp_start, amount, body in SELFTEST_BODIES:
        st = stage_of_text(body)
        sd = find_start(norm(body), amount)
        if st != exp_stage:
            bad += 1
            print("  NG 段階 %s（期待 %s）: %s" % (st, exp_stage, name))
        if sd != exp_start:
            bad += 1
            print("  NG 発効日 %s（期待 %s）: %s" % (sd, exp_start, name))
    for name, exp, body in SELFTEST_USABLE:
        if needs_checksum(body) != exp:
            bad += 1
            print("  NG 検算の要否 %s（期待 %s）: %s" % (not exp, exp, name))
        if exp and extract_by_checksum(body):
            bad += 1
            print("  NG 検算が通ってしまう（別制度の額を拾う）: %s" % name)
    n = len(SELFTEST_LABELS) + len(SELFTEST_BODIES) * 2 + len(SELFTEST_USABLE)
    print("自己テスト: %s（%d件）" % ("全通過" if not bad else "NG %d件" % bad, n))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="確定済みの県も含めて47局すべて巡回する")
    ap.add_argument("--pref", help="1県だけ")
    ap.add_argument("--selftest", action="store_true",
                    help="見出し・段階・発効日・金額の判定を実物の文字列で検査する"
                         "（ネットワークに出ない）")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest())

    state = article_state()

    def unsettled(v):
        """まだ確定していない＝決定まで進んでいない、または発効日が記事に入っていない。"""
        return v["stage"] < 2 or not v["start"]

    if a.pref:
        targets = [a.pref]
    elif a.all:
        targets = [p for p in BUREAU if p in state]
    else:
        targets = [p for p, v in state.items() if p in BUREAU and unsettled(v)]

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="saichin_")
    n_stage = {0: 0, 1: 0, 2: 0}
    for v in state.values():
        n_stage[v["stage"]] += 1
    n_nostart = sum(1 for v in state.values() if not v["start"])
    print("巡回 %d県（記事の段階 試算 %d / 答申 %d / 決定 %d・うち発効日なし %d）"
          % (len(targets), n_stage[0], n_stage[1], n_stage[2], n_nostart))
    if not targets and not a.pref:
        # ⚠ここで「記事は最新」と出していたのが 2026-09-24 に見つかった穴。
        # 対象0件は「全部確かめた」ではなく「1つも確かめていない」なので、緑の文言を使わない。
        print()
        print("巡回対象なし＝47県すべてが決定済みで、発効日も記事に入っている。")
        print("この先で変わるのは発効そのものなので、発効日を過ぎた県の書き方を人が見る。")
        return 0

    diffs, notes = [], []
    for pref in targets:
        v = state.get(pref, {"cell": "", "stage": 0, "start": None, "now": ""})
        cur, stage_a, start_a = v["cell"], v["stage"], v["start"]
        got, why = probe(pref, tmpdir, yen(re.sub(r"[^0-9,]", "", v["now"])))
        if not got:
            notes.append((pref, why))
            continue
        stage_b = got.get("stage") or 0
        line = "%s +%s円%s" % (STAGE_NAMES.get(stage_b, "答申"), got["up"] or "?",
                              "・%s発効" % got["start"] if got["start"] else "")
        why_diff = []
        if got["amount"] not in cur:
            why_diff.append("金額が違う（記事「%s」／ 発表 %s円）" % (cur, got["amount"]))
        if stage_b > stage_a:
            why_diff.append("段階が進んだ（記事 %s → 発表 %s）"
                            % (STAGE_NAMES[stage_a], STAGE_NAMES[stage_b]))
        if got["start"] and not start_a:
            why_diff.append("発効日が判明（%s）" % got["start"])
        elif got["start"] and start_a and got["start"] != start_a:
            why_diff.append("発効日が違う（記事 %s ／ 発表 %s）" % (start_a, got["start"]))
        if why_diff:
            diffs.append((pref, got, line, why_diff))
            print("  差分 %s: %s" % (pref, " ／ ".join(why_diff)))
        else:
            print("  検算 %s: %s円 一致（記事: %s）" % (pref, got["amount"], cur))

    print()
    passed = [p for p, v in state.items() if v["start"] and start_passed(v["start"])]
    if passed:
        print("発効日が過ぎている県 %d（記事の「発効」の書き方を人が見る）: %s"
              % (len(passed), "・".join(passed)))
        print()
    if notes:
        print("確認できなかった県 %d:" % len(notes))
        for pref, why in notes:
            print("  - %s: %s" % (pref, why))
        print()
    if diffs:
        print("記事の更新が必要 %d件:" % len(diffs))
        for pref, got, line, why_diff in diffs:
            print("  %s\t%s円\t%s\t%s"
                  % (pref, got["amount"], line, " ／ ".join(why_diff)))
        print()
        print("表の該当行を書き換えたら dateModified・sitemapのlastmod・IndexNow も更新する")
        return 1
    if notes:
        # ⚠確認できなかった県を残したまま「記事は最新」と言わない（2026-09-24）。
        # 取得経路が壊れていても差分0にはなるので、緑の文言はこの穴を隠す。
        print("差分は無いが、上の %d県は確認できていない。人が局のページを開く。" % len(notes))
        return 2
    print("記事は最新（巡回した %d県すべて確認・差分なし）" % len(targets))
    return 0


if __name__ == "__main__":
    sys.exit(main())
