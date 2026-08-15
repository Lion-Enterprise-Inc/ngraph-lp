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
