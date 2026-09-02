#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""検査の自己テスト——「検査が緩められた/壊れた」を公開前ゲートの冒頭で検出する。

なぜ入れたか（2026-08-14の実事故）:
  リンク3本の検査に自分の出力が引っかかったAIが、出力ではなく検査の方を
  「行き先の数」に緩めて通した。検査自身を守る検査が無ければ、ゲートは
  黙って弱くなっていく。既知NGの断片が通ったら「検査が壊れている」として
  ゲート全体を止める（[[feedback_broken_gate_hides_violations]] の常設化）。

設計（2026-08-15・Codexレビュー反映）:
  - 既知NGだけでなく既知OKも回す（NGしか無いと「常に落ちる壊れ方」を見逃す）
  - 期待するNG理由の識別子まで照合する（exit code だけでは、引数エラーで落ちても
    「NGが出た」ことになってしまう）
  - fixtureで検査できないものは、黙って除外せず理由付きで NOT_COVERED に列挙する
  - ネットワークには出ない（gate.py の既存方針）

使い方:
    python scripts/selftest.py    # gate.py が最初に自動実行する
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
sys.path.insert(0, HERE)

# fixtureを当てられない検査は、黙って対象外にせず理由ごと明示する（検査の穴を見えるようにする）
NOT_COVERED = [
    ("url_canon / publish_check / crosslink_check / freshness_check / eyecatch_*",
     "blog/ と sitemap 等リポジトリ全体を突合する検査。fixture記事の注入が本番の blog/ を汚すため、"
     "負テストは変更時に手で行う（staged fixture方式・8/14実施記録がcommitにある）"),
    ("anecdote_lint / ai_tell_lint / title_lint",
     "同上（記事ファイル走査型）。中核の閾値・正規表現を変える改修時は staged fixture で負テストする"),
]


def run():
    fails, oks = [], 0

    def case(name, fn, expect_ok, expect_sub=""):
        nonlocal oks
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 - 検査の実装が例外で死ぬのも「壊れている」
            ok, detail = None, f"例外: {e!r}"
        if expect_ok:
            if ok is True:
                oks += 1
            else:
                fails.append(f"{name}: 既知OKが通らない（{detail}）")
        else:
            if ok is False and (expect_sub in detail):
                oks += 1
            elif ok is False:
                fails.append(f"{name}: NGは出たが理由が期待と違う（期待「{expect_sub}」/実際「{detail[:80]}」）")
            else:
                fails.append(f"{name}: 既知NGが通ってしまった＝検査が緩められたか壊れている（{detail}）")

    # ---- x_article: 正本の定型ブロック抽出と版照合 --------------------------------
    import x_article

    def t_tpl_real():
        norm, h = x_article.template_block()
        if h != x_article.TEMPLATE_HASH:
            return False, f"正本 {h} / ツール {x_article.TEMPLATE_HASH}"
        return True, ""
    case("正本↔ツールの版照合（現物）", t_tpl_real, expect_ok=True)

    def t_tpl_double():
        try:
            x_article.template_block(os.path.join(FIX, "blogops_template_double.md"))
            return True, "抽出できてしまった"
        except ValueError as e:
            return False, str(e)
    case("定型マーカー2組は抽出失敗", t_tpl_double, expect_ok=False, expect_sub="一意でない")

    def t_tpl_missing():
        try:
            x_article.template_block(os.path.join(FIX, "blogops_template_missing.md"))
            return True, "抽出できてしまった"
        except ValueError as e:
            return False, str(e)
    case("定型マーカー無しは抽出失敗", t_tpl_missing, expect_ok=False, expect_sub="一意でない")

    # ---- x_article: リンク検査 ---------------------------------------------------
    def t_links_4():
        err = x_article.check_links(["https://a/1", "https://a/2", "https://a/3", "https://a/4"])
        return (err is None), (err or "")
    case("リンク4本はNG", t_links_4, expect_ok=False, expect_sub="上限3本")

    def t_links_fde():
        err = x_article.check_links(["https://ngraph.jp/fde/"])
        return (err is None), (err or "")
    case("/fde/ 混入はNG", t_links_fde, expect_ok=False, expect_sub="/fde/")

    def t_links_3():
        err = x_article.check_links(["https://a/1", "https://a/2", "https://a/3"])
        return (err is None), (err or "")
    case("リンク3本はOK", t_links_3, expect_ok=True)

    # ---- x_article: キャプション検査 ---------------------------------------------
    def t_cap_url():
        err, _ = x_article.check_caption("記事はこちら https://ngraph.jp/blog/x #AI導入")
        return (err is None), (err or "")
    case("キャプションのngraph.jp URLはNG", t_cap_url, expect_ok=False, expect_sub="カードが2枚")

    def t_cap_tags():
        err, _ = x_article.check_caption("本文です #a #b #c")
        return (err is None), (err or "")
    case("ハッシュタグ3個はNG", t_cap_tags, expect_ok=False, expect_sub="2個まで")

    def t_cap_ok():
        err, _ = x_article.check_caption("これは110字前後のまともなキャプションという想定の本文です。" * 3 + " #AI導入 #中小企業")
        return (err is None), (err or "")
    case("普通のキャプションはOK", t_cap_ok, expect_ok=True)

    # ---- x_article: ナレッジ型の末尾一文と図の取り込み（2026-08-16新設）-------------
    from bs4 import BeautifulSoup

    def soup_of(html):
        return BeautifulSoup(html, "html.parser")

    def t_offer():
        art = soup_of('<div class="a-cta"><p>見出し。</p>'
                      '<p>NGraphでは、企業の「会社の脳」を構築し、'
                      'そこまで伴走する支援を承っております。ご依頼は随時募集しています。</p></div>')
        got = x_article.offer_sentence(art)
        return (got == "NGraphでは、企業の「会社の脳」を構築し、そこまで伴走する支援を承っております。"), f"got={got!r}"
    case("ナレッジ型の末尾一文をCTAから取り出す", t_offer, expect_ok=True)

    def t_offer_missing():
        # 「承っております。」が無いCTAで一文を組み立ててしまうと、記事とXで呼称がズレる
        art = soup_of('<div class="a-cta"><p>お気軽にご相談ください。</p></div>')
        got = x_article.offer_sentence(art)
        return (got is None), f"got={got!r}"
    case("承っておりますが無ければ一文を作らない", t_offer_missing, expect_ok=True)

    def t_fig_img():
        # 図はSVGとは限らない。img決め打ちで落とすと図が黙って全部消える
        _t, _cs, _f = None, None, None
        wrap = soup_of('<div class="a-fig-wrap"><p class="a-fig-title">全体構図</p>'
                       '<img src="/assets/blog/x.jpg" alt=""></div>')
        found = wrap.find("div").find("img")
        return (found is not None and found["src"].startswith("/assets/")), "imgを拾えない"
    case("画像の図を図として認識する", t_fig_img, expect_ok=True)

    def t_internal_link_dropped():
        # 自ブログへの関連リンクはXでは文字に落とす（末尾の本家1本に導線を集約）
        text, styles, ranges, ents = [], [], [], []
        node = soup_of('<p>詳しくは<a href="/blog/foo">別の記事</a>で書きました。</p>').find("p")
        x_article.inline(node, text, styles, ranges, ents)
        return (len(ents) == 0 and "別の記事" in "".join(text)), f"entities={len(ents)}"
    case("自ブログへの内部リンクはXで文字に落とす", t_internal_link_dropped, expect_ok=True)

    def t_external_link_kept():
        text, styles, ranges, ents = [], [], [], []
        node = soup_of('<p>出典は<a href="https://example.com/a">ここ</a>です。</p>').find("p")
        x_article.inline(node, text, styles, ranges, ents)
        return (len(ents) == 1), f"entities={len(ents)}"
    case("外部リンクは落とさない", t_external_link_kept, expect_ok=True)

    # ---- deck_fig: スライドの切り出し（2026-08-16新設）------------------------------
    def t_deck_crop():
        # 本文の下に空白を挟んで置かれた細い帯＝資料のフッター。Xでは落とす
        from PIL import Image, ImageDraw
        import deck_fig
        im = Image.new("RGB", (400, 300), (250, 249, 247))
        d = ImageDraw.Draw(im)
        d.rectangle([40, 30, 360, 200], fill=(30, 30, 30))     # 本文
        d.rectangle([40, 270, 360, 278], fill=(30, 30, 30))    # フッター帯
        box = deck_fig.crop_box(im)
        # フッターは含まれず、本文は欠けない
        return (box[3] < 265 and box[3] > 200), f"box={box}"
    case("スライドのフッター帯を落とし、本文は欠けない", t_deck_crop, expect_ok=True)

    # ---- paren_lint: かっこ密度の中核 ---------------------------------------------
    import paren_lint

    def t_paren_crowded():
        art = ('<article><p>透かし（英語）が入る（見えない）（要点）。</p>'
               '<p>' + "あ" * 600 + '</p></article>')
        got = paren_lint.measure(art)
        if got is None:
            return None, "measureがNoneを返した"
        _, _, crowded = got
        return (not crowded), f"crowded={crowded}"
    case("1段落かっこ3個は検出される", t_paren_crowded, expect_ok=False, expect_sub="crowded=[(3")

    def t_paren_ok():
        art = ('<article><p>透かし（英語）が入る（見えない）。</p><p>' + "あ" * 600 + "</p></article>")
        got = paren_lint.measure(art)
        _, _, crowded = got
        return (not crowded), f"crowded={crowded}"
    case("1段落かっこ2個は通る", t_paren_ok, expect_ok=True)

    # ---- style_lint: AI感（NG表現・語尾3連続・文体混在）2026-08-22 ------------------
    import style_lint as st

    def t_style_tail_run():
        m = st.measure("<p>設定を開きます。値を変えます。保存します。</p>")
        return (not m["runs"]), f"runs={m['runs']}"
    case("同じ語尾3連続は検出される", t_style_tail_run, expect_ok=False, expect_sub="runs=[('ます'")

    def t_style_tail_two_ok():
        m = st.measure("<p>設定を開きます。値を変えます。保存して終わりです。</p>")
        return (not m["runs"]), f"runs={m['runs']}"
    case("同じ語尾2連続は通る", t_style_tail_two_ok, expect_ok=True)

    def t_style_ng_word():
        m = st.measure("<p>この設定が効きます。単なる自動化ではなく仕組み化です。</p>")
        ids = sorted(k for k, *_ in m["hits"])
        return (not ids), f"hits={ids}"
    case("「効きます。」「単なるAではなく」は検出される", t_style_ng_word, expect_ok=False, expect_sub="hits=['ng:kiku', 'ng:tanaru']")

    def t_style_ng_word_narrowed():
        m = st.measure("<p>この薬が効くのは服用後30分からで、痛みが半分になります。</p>")
        return (not m["hits"]), f"hits={m['hits']}"
    case("効く先を書いた「効く」は通る（狭めた条件）", t_style_ng_word_narrowed, expect_ok=True)

    def t_style_fix_present():
        missing = [r["id"] for r in st.NG_WORDS if not r.get("fix")]
        return (not missing), f"代替なし={missing}"
    case("ng_words.json は全行に代替がある", t_style_fix_present, expect_ok=True)

    # ---- readability_lint: 読みにくさの中核 ---------------------------------------
    import readability_lint as rd

    def t_read_abstract():
        # 抽象語だけを並べた本文は、密度の上限を超えるので落ちなければならない
        art = "<article><p>" + "この仕組みは処理の経路を運用の形に定めた方式です。" * 12 + "</p></article>"
        d = rd.abstract_density(rd.body_of(art))
        return (d <= rd.MAX_ABSTRACT_PER_1000), f"density={d}"
    case("抽象語だらけの本文は検出される", t_read_abstract, expect_ok=False, expect_sub="density=")

    def t_read_ok():
        art = "<article><p>" + "きのう店で味噌汁を出した。客は残さず飲んだ。" * 12 + "</p></article>"
        d = rd.abstract_density(rd.body_of(art))
        return (d <= rd.MAX_ABSTRACT_PER_1000), f"density={d}"
    case("具体的な本文は通る", t_read_ok, expect_ok=True)

    def t_read_long():
        art = "<article><p>" + ("あ" * 80 + "。") * 10 + "</p></article>"
        ratio, longs, _, _ = rd.measure(art)
        return (ratio <= rd.MAX_LONG_RATIO), f"ratio={ratio}"
    case("長い文だらけの本文は検出される", t_read_long, expect_ok=False, expect_sub="ratio=100")

    def t_read_term_not_claim():
        # 用語の反復は正当（FDE記事の Forward Deployed Engineer 等）＝落としてはいけない
        return (not rd.is_claim("Forward Deployed Engineer")), "用語を主張と誤判定"
    case("用語の反復は反復とみなさない", t_read_term_not_claim, expect_ok=True)

    def t_read_endrun():
        art = "<article><p>" + "きのう店で味噌汁を出しました。客がそれを飲みました。私は器を洗いました。" * 8 + "</p></article>"
        run, mashita = rd.ending_monotony(rd.body_of(art))
        return (run <= rd.MAX_END_RUN), f"run={run} mashita={mashita}"
    case("同じ語尾3連続は検出される", t_read_endrun, expect_ok=False, expect_sub="run=")

    def t_read_endrun_ok():
        art = "<article><p>" + "きのう店で味噌汁を出しました。客は残さず飲む。器はもう洗ってある。次は朝の仕込みです。" * 8 + "</p></article>"
        run, mashita = rd.ending_monotony(rd.body_of(art))
        return (run <= rd.MAX_END_RUN and mashita <= rd.MAX_MASHITA_PCT), f"run={run} mashita={mashita}"
    case("語尾を混ぜた本文は通る", t_read_endrun_ok, expect_ok=True)

    def t_read_thresholds():
        if rd.MAX_ABSTRACT_PER_1000 > 6.0 or rd.MAX_LONG_RATIO > 45:
            return False, "読みにくさの閾値が緩められている"
        if rd.MAX_END_RUN > 2 or rd.MAX_MASHITA_PCT > 35:
            return False, "語尾単調の閾値が緩められている"
        return True, ""
    case("読みにくさの閾値（抽象5.5・長文40%）", t_read_thresholds, expect_ok=True)

    # ---- format_lint: 型の閾値が守られているか -------------------------------------
    import format_lint

    def t_fmt_thresholds():
        lo = format_lint.RULES["朝"][0]
        if lo < 2000:
            return False, f"朝の下限が {lo} に緩められている"
        if format_lint.RULES["朝"][2] < 4 or format_lint.RULES["夕"][0] < 5000:
            return False, "H2/夕の閾値が緩められている"
        return True, ""
    case("型の閾値（朝2300字・H2 4本・夕6000字）", t_fmt_thresholds, expect_ok=True)

    # ---- blog_files: 検査対象の集合に穴が開いていないか ------------------------------
    # 2026-08-16の実事故: format_lint / paren_lint / title_lint が `blog/2026*.html` を
    # 個別に glob していたため、日付を持たないナレッジ型 `k-*.html` が3つの検査から
    # 丸ごと外れたまま、ゲートは「全通過」と表示していた。対象集合は検査の前提なので、
    # 集合が縮んだら検査そのものが壊れたとみなす。
    import blog_files

    def t_scope_knowledge():
        if not blog_files.in_scope("k-blog-gate", "20260812"):
            return False, "ナレッジ型が対象外になっている"
        if blog_files.in_scope("what-is-fde", "20260812"):
            return False, "日付なしの既存恒久記事まで対象に入っている"
        if not blog_files.in_scope("20260815-x", "20260812"):
            return False, "日付slugの新記事が対象外になっている"
        if blog_files.in_scope("20260101-x", "20260812"):
            return False, "cutoff より前の記事が対象に入っている"
        return True, ""
    case("検査対象の判定（ナレッジ型は対象・既存恒久記事は対象外）",
         t_scope_knowledge, expect_ok=True)

    def t_scope_lints_share():
        # 3つのリントが blog_files を使わずに独自 glob へ戻ったら、この検査で気付く
        bad = []
        for mod in ("format_lint", "paren_lint", "title_lint"):
            src = open(os.path.join(HERE, mod + ".py"), encoding="utf-8").read()
            if "2026*.html" in src:
                bad.append(mod)
        return (not bad), f"独自globに戻っている: {bad}"
    case("リントが対象集合を自前で持っていない", t_scope_lints_share, expect_ok=True)

    # ---- source_title_check: PDF出典の判定（2026-09-02新設）------------------------
    # なぜ: 出典がPDFのとき <title> が無く、捏造でも実在でも「未確認」で素通りしていた。
    # 補助金・税制の記事の一次情報はPDFが主なので、一番捏造されやすい型が無検査だった。
    # ネットワークにも実PDFにも依存させないため fetch と pdf_titles を差し替えて
    # 判定の分岐だけを見る（PDFからの文字取り出しは pypdf の仕事）。
    import source_title_check as stc

    G = "https://x.example/doc/guide.pdf"
    IDX = "https://x.example/doc.html"
    IDX_HTML = ('<a href="/doc/guide.pdf">中小企業向け賃上げ促進税制ご利用ガイドブック</a>'
                '<a href="/doc/pamph.pdf">「賃上げ促進税制」パンフレット（令和8年6月時点版）</a>')
    P = "https://x.example/doc/pamph.pdf"

    def with_stub(body_titles, fetch_map, fn):
        """fetch / pdf_titles を差し替えて fn を走らせ、必ず元に戻す。"""
        of, op = stc.fetch, stc.pdf_titles
        stc.fetch = lambda url, limit=8_000_000, tries=3: fetch_map.get(
            url, (None, None, "neterr"))
        stc.pdf_titles = lambda raw: body_titles
        try:
            return fn()
        finally:
            stc.fetch, stc.pdf_titles = of, op

    PDF = (b"%PDF-" + b"x" * 200, "application/pdf", None)
    FMAP = {G: PDF, P: PDF, IDX: (IDX_HTML.encode("utf-8"), "text/html", None)}

    def t_pdf_body_ok():
        got = with_stub(["中小企業向け賃上げ促進税制ご利用ガイドブック"], FMAP,
                        lambda: stc.check_pdf("fix", "中小企業向け賃上げ促進税制ご利用ガイドブック",
                                              G, [IDX]))
        return (got == "ok"), f"got={got}"
    case("PDF本文に題名があればOK", t_pdf_body_ok, expect_ok=True)

    def t_pdf_index_ok():
        # 題名がPDFの中に一度も出てこない実例（中小企業庁のパンフレット）。
        # 掲載ページのリンク表記を根拠に認めないと、正しい出典をNGにしてしまう
        got = with_stub(["賃上げに取り組む経営者の皆様へ"], FMAP,
                        lambda: stc.check_pdf("fix", "「賃上げ促進税制」パンフレット（令和8年6月時点版）",
                                              P, [IDX]))
        return (got == "ok"), f"got={got}"
    case("PDF本文に無くても掲載ページの表記と一致すればOK", t_pdf_index_ok, expect_ok=True)

    def t_pdf_fabricated():
        # 2026-08-18の事故と同じ型（URLのスラッグから題名を合成した）
        got = with_stub(["中小企業向け賃上げ促進税制ご利用ガイドブック"], FMAP,
                        lambda: stc.check_pdf("fix", "賃上げ促進税制ガイドブック 令和8年度改正のポイント",
                                              G, [IDX]))
        return (got != "ng"), f"got={got}"
    case("PDFの題名を捏造したらNG", t_pdf_fabricated, expect_ok=False, expect_sub="got=ng")

    def t_pdf_404():
        got = with_stub([], {G: (None, None, "missing")},
                        lambda: stc.check_pdf("fix", "存在しない資料", G, []))
        return (got != "ng"), f"got={got}"
    case("PDFが404ならNG", t_pdf_404, expect_ok=False, expect_sub="got=ng")

    def t_pdf_blocked():
        # 中小企業庁は連続で叩くと中身ゼロを返す。取得できないことは出典の誤りではないので
        # NGにしない（ここをNGにすると、正しい記事が公開できなくなる）
        got = with_stub([], {G: (None, None, "empty")},
                        lambda: stc.check_pdf("fix", "中小企業向け賃上げ促進税制ご利用ガイドブック",
                                              G, []))
        return (got == "unknown"), f"got={got}"
    case("サイトが空応答を返しても止めない（未確認）", t_pdf_blocked, expect_ok=True)

    # ---- 報告 --------------------------------------------------------------------
    for name, why in NOT_COVERED:
        print(f"  対象外 {name}: {why}")
    if fails:
        print("検査の自己テストに失敗（検査が緩められたか壊れています）:")
        for f in fails:
            print("  NG " + f)
        return 1
    print(f"OK: 検査の自己テスト {oks}件 全通過")
    return 0


if __name__ == "__main__":
    sys.exit(run())
