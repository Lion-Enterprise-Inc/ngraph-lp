#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""公開前ゲートの単一入口（BLOG-OPS §6・§9）。

検査を足すたびに BLOG-OPS.md・ngraph-blog-post スキル・朝夕の定時タスクの
4ドキュメントを編集する構造だったので、入口を1つにした。
**新しい検査を足すときは、このファイルの CHECKS に1行足すだけでよい。**
運用ドキュメント側は `python scripts/gate.py` としか書かない。

使い方:
    python scripts/gate.py                      # サイト全体の検査
    python scripts/gate.py blog/<新記事>.html   # 上記＋その記事の一次体験の検査

どれか1つでも落ちたら exit 1。**1つ落ちても残りは最後まで実行する**
（最初の1件で止まると、直して再実行するたびに次の1件が出て往復が増えるため）。
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# report-only（NG でも push を止めない・出力は WARN として残す）。
# 2026-10-19 髙橋さん「全部再点検して直して」＝AI が自分の判断で入れた「文体・型・同期」の検査で
# サイト全体の公開を止めない（棚卸し: shingo-brain/inbox/2026-10-19_ai-invented-rules-audit.md）。
# 本番を壊す検査（URL・配線・リンク切れ・JS 構文・表紙の重なり）は fail-closed のまま。
REPORT_ONLY = {
    "arche_check.py",        # アルケー側の未ビルドでブログの push まで止めていた
    "en_check.py",           # 日本語1ページの修正で全 push を止めていた（最低賃金ゲートと同型）
    "title_lint.py",         # タイトルの定型＝文体の好み
    "crosslink_check.py",    # 朝夕の相互リンク＝運用の慣習
    "style_lint.py",         # AI 感＝出どころは社外の X 投稿
    "format_lint.py",        # 字数・H2 本数＝閾値は AI が決めた
    "cta_service_check.py",  # CTA の型
    "unpushed_check.py",
    "title_sync_check.py",
}

# (表示名, スクリプト, 追加引数, 記事ファイルを引数に取るか)
CHECKS = [
    # selftest は必ず先頭（他の検査が緩められた/壊れた状態で走るのを防ぐ・2026-08-15）
    ("検査の自己テスト（既知NGが通ったら検査が壊れている）", "selftest.py", [], False),
    ("URL形式（拡張子なしに揃っているか）", "url_canon.py", ["--check"], False),
    ("対外ページの禁止語（正本・検問・司書・読み口・稼働中 等）", "vocab_check.py", [], False),
    ("インラインJSの構文（壊れたscriptは無言で止まる）", "js_check.py", [], False),
    ("CSSの名札とHTML/JSの食い違い（規則が一度も当たらない）", "class_check.py", [], False),
    ("配線漏れ（sitemap / llms.txt / alt）", "publish_check.py", ["--check"], False),
    ("共通フッターのズレ（正本 scripts/chrome/・直すのは sync_chrome.py）", "sync_chrome.py", ["--check"], False),
    ("サイト内リンクの飛び先（ページと #アンカーが実在するか）", "link_check.py", [], False),
    ("アルケー（cases/）と元ソース・sitemap のズレ（直すのは _arche で npm run build・report-only）", "arche_check.py", [], False),
    ("日本語と英語（en/）のズレ（日本語を直したら英語も直して en_check.py --stamp・report-only）", "en_check.py", [], False),
    ("タイトルの弱い定型（report-only）", "title_lint.py", [], False),
    ("同日記事の相互リンク（朝↔夕・report-only）", "crosslink_check.py", [], False),
    ("一次体験の使い回し", "anecdote_lint.py", [], True),
    ("AI生成の痕跡（ダーシの密度・反復・AI文体）", "ai_tell_lint.py", [], True),
    ("かっこ書きの多用（読みにくさ）", "paren_lint.py", [], False),
    ("AI感（NG表現・語尾3連続・文体混在・report-only）", "style_lint.py", [], True),
    ("読みにくさ（長い文・言い回しの反復・抽象語）", "readability_lint.py", [], False),
    ("アイキャッチの本文と図案の重なり", "eyecatch_check.py", [], False),
    ("表紙の文言と記事タイトルのズレ", "eyecatch_text_check.py", [], True),
    ("表紙の文言記録の追随漏れ（記事だけpushしていないか）", "eyecatch_record_push_check.py", [], False),
    ("型（朝A/夕B/ガイドG・字数・H2・ラベル・枠の重複・report-only）", "format_lint.py", [], False),
    ("図のブロックの二重包み", "fig_lint.py", [], False),
    ("一覧カードのカテゴリ（タブ）", "blog_categories.py", [], False),
    ("ナレッジ正本の出所と台帳（誰が決めた行か・公開済みが台帳に載っているか）", "knowledge_ops_lint.py", [], False),
    ("ナレッジ型のCTA3要素とサービス呼称（report-only）", "cta_service_check.py", [], True),
    ("書いたのにpushされていない記事・表紙（report-only）", "unpushed_check.py", [], False),
    ("一覧/llms.txt と記事h1のタイトル不一致（report-only）", "title_sync_check.py", [], False),
]


def run(script, args):
    # 子はパイプ出力時に既定でcp932を使うため、明示しないと日本語が化ける
    # （自前で stdout.reconfigure している検査としていない検査が混在している）
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(
        [PY, os.path.join(HERE, script)] + args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    article = sys.argv[1] if len(sys.argv) > 1 else None
    # pre-push フックが GATE_CHANGED（今回 push するファイル）を設定する。手で記事を渡したときはその記事を対象に含める。
    if article:
        os.environ["GATE_CHANGED"] = os.environ.get("GATE_CHANGED", "") + "\n" + article
    failed = []
    warned = []

    for label, script, args, needs_article in CHECKS:
        if needs_article:
            if not article:
                print("- %s: SKIP（記事ファイルを引数で渡すと検査する）" % label)
                continue
            args = args + [article]
        code, out = run(script, args)
        head = out.strip().splitlines()
        report_only = script in REPORT_ONLY
        mark = "OK   " if code == 0 else ("WARN " if report_only else "NG   ")
        print(mark + label)
        for line in head:
            print("       " + line)
        if code != 0 and not report_only:
            failed.append(label)
        elif code != 0:
            warned.append(label)

    print()
    if warned:
        print("WARN（止めない）: %d件 — %s" % (len(warned), " / ".join(warned)))
    if failed:
        print("公開前ゲート: NG（%d件）— %s" % (len(failed), " / ".join(failed)))
        print("直してから push すること。`--fix` を持つ検査は自動修正できる:")
        print("  python scripts/url_canon.py --fix")
        print("  python scripts/publish_check.py --fix")
        return 1
    print("公開前ゲート: 全通過")
    return 0


if __name__ == "__main__":
    sys.exit(main())
