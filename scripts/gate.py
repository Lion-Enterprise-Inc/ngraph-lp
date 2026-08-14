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

# (表示名, スクリプト, 追加引数, 記事ファイルを引数に取るか)
CHECKS = [
    ("URL形式（拡張子なしに揃っているか）", "url_canon.py", ["--check"], False),
    ("配線漏れ（sitemap / llms.txt / alt）", "publish_check.py", ["--check"], False),
    ("タイトルの弱い定型", "title_lint.py", [], False),
    ("同日記事の相互リンク（朝↔夕）", "crosslink_check.py", [], False),
    ("一次体験の使い回し", "anecdote_lint.py", [], True),
    ("AI生成の痕跡（ダーシの密度・反復・AI文体）", "ai_tell_lint.py", [], True),
    ("かっこ書きの多用（読みにくさ）", "paren_lint.py", [], False),
    ("アイキャッチの本文と図案の重なり", "eyecatch_check.py", [], False),
    ("表紙の文言と記事タイトルのズレ", "eyecatch_text_check.py", [], False),
    ("記事の再確認期限（鮮度）", "freshness_check.py", [], False),
    ("型（朝A/夕B/ガイドG・字数・H2・ラベル・枠の重複）", "format_lint.py", [], False),
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
    failed = []

    for label, script, args, needs_article in CHECKS:
        if needs_article:
            if not article:
                print("- %s: SKIP（記事ファイルを引数で渡すと検査する）" % label)
                continue
            args = args + [article]
        code, out = run(script, args)
        head = out.strip().splitlines()
        print(("OK   " if code == 0 else "NG   ") + label)
        for line in head:
            print("       " + line)
        if code != 0:
            failed.append(label)

    print()
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
