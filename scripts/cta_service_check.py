#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""N-KNOWLEDGE（k-*.html）のCTAの検査。

(1) CTAの3要素が揃っているか（fail-closed）
(2) CTAで名乗ったサービス名がLPの呼称と一致しているか（report-only）

なぜ入れたか（2026-08-26・5本目 k-multilingual-density の計画中に発見）:
  KNOWLEDGE-OPS §0-2 は「承っております、と書けるのは実在のサービスだけ／呼称は営業資料と
  一字レベルで揃える」と定めている。記事→問い合わせ→商談資料が地続きになる設計なので、
  呼称がブレるとそこで切れる。
  ところが §4 のネタ台帳の右列（紐づくサービス）は 2026-08-15 にClaudeが自分で書いたラベルの
  ままで、**LPと突合されたことが一度も無かった**。今回消化した行の「多言語HP制作」はLPに存在せず、
  正しくは「飲食店HPの多言語対応制作」だった。残る行の「書類作成支援」もLPには無い。
  §0-2 は書き手の心がけとしてしか書かれておらず、機械が見ていなかった。心がけは会話が長くなると
  薄まる（BLOG-OPS §0-12 と同じ理由）ので、機械が見る。

なぜ (2) を fail-closed にしないか:
  §0-4 の確定文型（2026-08-16・髙橋さん）は「①何を構築するのかを1文で言う」であって、
  カタログ名を名乗る形に限っていない。実際 k-company-brain-abc のCTAは
  「企業の『会社の脳』を構築し…伴走する支援」という説明文で、これは承認された形。
  ここでNGを出すと、**正しい記事が公開できなくなる**（[[feedback_fail_closed_scope_and_invented_requirements]]）。
  意味を推測して「これは名前か説明か」を機械に判定させることもしない
  （KNOWLEDGE-OPS §2 の「意味を推測する検査は作らない」と同じ轍を踏まない）。
  よって呼称の突合は目に見せるところまでにして、判断は書き手に残す。

なぜ (1) は fail-closed でよいか:
  §0-4 は3要素を確定事項として列挙していて、揃っているかどうかは文字列の有無だけで決まる。
  推測が要らないので誤検知が出ない。

照合先: 公開中のLP（index.html / fde/index.html）の本文と、そのJSON-LDの name / alternateName。
  比較のときだけ空白を落とす——LP自身が見出し「FDE型 AI導入伴走支援」とJSON-LDの
  「FDE型AI導入伴走支援」で半角スペース1つ食い違っており、そこでNGを出しても得るものが無い。

使い方:
    python scripts/cta_service_check.py blog/k-<topic>.html   # gate.py が自動実行する
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# サービスの呼称の正本＝公開中のLP。営業資料（PPTX）は別リポジトリなのでここでは見ない
LP_FILES = ["index.html", os.path.join("fde", "index.html")]
DOC = os.path.join(ROOT, "KNOWLEDGE-OPS.md")

CTA = re.compile(r"NGraphでは、?(.+?)を承っております")
SPACE = re.compile(r"[\s　]+")
NAME_FIELD = re.compile(r'"(?:name|alternateName)"\s*:\s*(".*?"|\[.*?\])', re.S)
DM_HANDLE = "@japan19840824"


def norm(s):
    return SPACE.sub("", s)


def read(rel):
    p = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return ""
    return open(p, encoding="utf-8", errors="ignore").read()


def visible(s):
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    return re.sub(r"<[^>]+>", "", s)


def lp_names():
    """LPの本文（可視テキスト）と、JSON-LD の name / alternateName を合わせた照合材料。"""
    buf = []
    for rel in LP_FILES:
        raw = read(rel)
        if not raw:
            continue
        buf.append(visible(raw))
        for m in NAME_FIELD.finditer(raw):
            buf.append(m.group(1))
    return norm("\n".join(buf))


def ledger_services():
    """§4 の台帳の表の右列（紐づくサービス）。〔起案 ...〕等の注記は落とす。"""
    if not os.path.exists(DOC):
        return []
    out = []
    for line in read(DOC).splitlines():
        if not line.startswith("|") or line.startswith("|---") or "| 題材 |" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        name = re.sub(r"〔.*?〕", "", cells[-1]).strip()
        if name:
            out.append(name)
    return out


def main():
    if len(sys.argv) < 2:
        print("参考 記事ファイルを引数で渡すと検査する")
        return 0
    article = sys.argv[1]
    if not os.path.basename(article).startswith("k-"):
        print("参考 %s はナレッジ型ではない（対象外）" % os.path.basename(article))
        return 0
    raw = read(article)
    if not raw:
        print("NG %s が無い" % article)
        return 1

    body = visible(raw)
    lp = lp_names()
    fails = []

    # (1) CTAの3要素（KNOWLEDGE-OPS §0-4・確定 2026-08-16）
    if "承っております" not in body:
        fails.append("CTAの「NGraphでは◯◯を承っております。」が無い（§0-4①：何を構築するのかを1文で言う）")
    if "ご依頼は随時募集" not in body:
        fails.append("CTAに「ご依頼は随時募集しています」が無い（§0-4②：受注可能だと明示する）")
    if 'href="/entry"' not in raw:
        fails.append("CTAに /entry への導線が無い（§0-4③：問い合わせ口）")
    if DM_HANDLE not in raw:
        fails.append("CTAにXのDM導線（%s）が無い（§0-4③：問い合わせ口）" % DM_HANDLE)

    # (2) 名乗ったサービス名とLPの呼称の突合（report-only）
    for hit in CTA.findall(body):
        name = hit.strip().strip("　")
        if norm(name) in lp:
            print("OK CTAのサービス名「%s」はLPの呼称と一致" % name)
        else:
            print("参考 CTAの「%s」はLPの呼称と一致しない。カタログ名を名乗るならLPの見出しから写す"
                  % (name if len(name) <= 40 else name[:40] + "…"))
            print("     （説明文で構築物を1文で言う形なら、これは正常＝§0-4①）")

    # 台帳の右列も見せる。公開物ではないので落とさない
    for name in ledger_services():
        if norm(name) not in lp:
            print("参考 台帳の呼称「%s」はLPに無い。その題材を書くときはLPの呼称へ直す" % name)

    for f in fails:
        print("NG " + f)
    if fails:
        print("CTA: NG %d件" % len(fails))
        return 1
    print("CTA: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
