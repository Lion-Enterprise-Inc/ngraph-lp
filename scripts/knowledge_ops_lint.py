#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""KNOWLEDGE-OPS.md の規則行に出所（確定／起案）が付いているかの検査。

なぜ入れたか〔髙橋さん 2026-08-16「このシリーズの記事名は日付を持たない決まり？？なんで？そんな決まりないぞ」〕:
  §1のslug規則は、Claudeが2026-08-15に自分で決めて、出所を書かずに置いたものだった。
  翌日のセッションはそれを「決まり」として読み、記事本文と報告に
  「決まりを守ったから検査から漏れた」とまで書いた。**帰属の無い行は、次のセッションで
  承認済みの決定に化ける。** 正本にとってこれは、内容の誤りより質が悪い——
  誰も決めていないものが、決定として運用に効いてしまう。

  起案＝間違い、ではない。立ち上げ指示の細部をAIが埋めるのは正常な仕事の形で、
  まずいのは埋めたことを隠すこと。この検査は内容の是非を判定しない。
  **出所が書いてあるかどうかだけ**を見る。

対象: KNOWLEDGE-OPS.md の「## 0.」以降にある箇条書き・表の行のうち、規則を述べているもの。
  見出し・空行・コードブロック・補足のインデント行・「消化済み」等の記録行は対象外。

使い方:
    python scripts/knowledge_ops_lint.py    # gate.py が自動実行する
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = os.path.join(ROOT, "KNOWLEDGE-OPS.md")

MARK = re.compile(r"〔(確定|起案|実測)\b")
# 規則を述べる行＝トップレベルの箇条書き（"- " / "1. "）と、台帳の表の行
RULE = re.compile(r"^(?:[-*] |\d+\. )")
TABLE = re.compile(r"^\|")
# 記録であって規則ではない行（出所を求めない）
SKIP_WORDS = ("消化済み", "書いたら行を消して", "| 題材 |", "|---")


def committed_k_slugs():
    """**commit 済み**の blog/k-*.html の slug。取れなければ None（＝この検査は黙って見送る）。

    published_set.py は git ls-files（インデックス込み）を見るが、ここでは HEAD だけを見る。
    公開の手順は「git add → gate → commit → push」なので、インデックスを見ると
    **いま公開しようとしている記事**が対象に入り、台帳へ書く前にゲートが落ちて公開できなくなる。
    台帳は commit の後（同じ作業の中）で動かすので、見るのは commit 済みのものだけでよい。
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", "blog"],
            cwd=ROOT, capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    slugs = []
    for line in out.stdout.splitlines():
        line = line.strip()
        name = os.path.basename(line)
        if name.startswith("k-") and name.endswith(".html"):
            slugs.append(name[:-5])
    return slugs


def check_ledger(text):
    """公開済みのナレッジ記事が、台帳の「消化済み」に載っているか。

    なぜ入れたか（2026-09-10）:
      「補助金書類のAI下書き運用」の行は 2026-09-02 に k-subsidy-draft として公開されたのに、
      台帳の行が残ったままだった。BLOG-OPS §4 の台帳が 2026-08-09 に踏んだのと同じ穴で、
      **次のセッションが消化済みの題材を先頭として拾う**状態になる（実際 8/9 はそうなった）。
      「書いたらその日のうちに動かす」という書き置きは2回とも守られなかったので、機械で見る。

      判定は slug の文字列が**消化済みの行に**あるかだけ＝誤検知ゼロ。中身の是非は見ない。

      ⚠ 最初の実装はファイル全体を検索していて、負テストが通らなかった（2026-09-10）。
      経緯を書いた注意書きの中に slug が出てくるので、台帳から消しても検査が緑のままだった。
      **見る範囲は「消化済み」の行だけ**に絞る。ずっと緑の検査は、無い検査より悪い。
    """
    slugs = committed_k_slugs()
    if slugs is None:
        return [], "参考 gitが読めないので台帳の消化済み検査は見送り"
    done = "\n".join(l for l in text.splitlines() if l.lstrip().startswith("消化済み"))
    missing = [s for s in slugs if s not in done]
    if missing:
        return ([
            "台帳の「消化済み」に無い公開済みのナレッジ記事: %s\n"
            "        公開したら同じ作業の中で §4 の台帳を動かす"
            "（行を消して、消化済みへ公開URLと日付を移す）" % "／".join(missing)
        ], "")
    return [], "OK: 公開済みのナレッジ記事 %d本すべてが台帳の消化済みにある" % len(slugs)


def main():
    if not os.path.exists(DOC):
        print("参考 KNOWLEDGE-OPS.md が無い（このリポジトリでは対象外）")
        return 0

    lines = open(DOC, encoding="utf-8").read().splitlines()
    fails = []
    started = False
    in_code = False
    checked = 0

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # 「出所の記法」の節そのものは、記法の説明なので対象外
        if line.startswith("## "):
            started = line.startswith("## 0.") or started
            if "出所の記法" in line:
                started = False
            continue
        if not started:
            continue
        if any(w in line for w in SKIP_WORDS):
            continue
        if not (RULE.match(line) or TABLE.match(line)):
            continue
        # 未着手のタスク行（"- [ ] "）はこれから決めることなので出所を求めない
        if line.startswith("- [ ]"):
            continue

        checked += 1
        if not MARK.search(line):
            fails.append("%d行目: 出所の印が無い（〔確定 YYYY-MM-DD〕か〔起案 YYYY-MM-DD〕を付ける）\n"
                         "        %s" % (i, line[:76]))

    ledger_fails, ledger_note = check_ledger("\n".join(lines))

    for f in fails:
        print("NG " + f)
    for f in ledger_fails:
        print("NG " + f)
    if fails or ledger_fails:
        if fails:
            print("KNOWLEDGE-OPS の出所: NG %d件 / %d行。"
                  "**印の無い行は、次のセッションが「決まり」として読む**" % (len(fails), checked))
        if ledger_fails:
            print("KNOWLEDGE-OPS の台帳: NG %d件。"
                  "**動かし忘れた台帳は、次のセッションが消化済みの題材を先頭として拾う**"
                  % len(ledger_fails))
        return 1
    print("OK: KNOWLEDGE-OPS の出所 全通過（規則 %d行すべてに 確定／起案 の印あり）" % checked)
    if ledger_note:
        print("       " + ledger_note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
