#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""commit に入る記事が、そのcommitで意図した記事かを見る（commit-msg フック）。

なぜ要るか（2026-08-26の事故）:
  このリポジトリは複数のセッションが同じ作業ツリーを共有する。
  `git add -- a b` で2ファイルだけ足しても、続く `git commit` に pathspec が無ければ
  **index 全体**が commit される。この日、並行セッションがステージ済みだった
  `blog/k-multilingual-density.html` と配線3ファイル（index/sitemap/llms）が
  そのまま commit され、本人の判断を経ずに本番へ出た。
  memory `feedback_parallel_sessions_shared_worktree` に「commitはpathspec指定」と
  書いてあったが、書いてあるだけでは止まらなかったので機械にした。

やること:
  commit に含まれる blog/<slug>.html（index.html は除く）の slug を集め、
  commit メッセージに現れない slug があれば止める。
  ブログのcommitは BLOG-OPS の慣習で本文に slug を書くので、単独記事なら素通りする。

抜け道を用意してある:
  - 複数記事をまとめて出すときは、メッセージに slug を並べれば通る
  - どうしても通したいときは `git commit --no-verify`
"""
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def sh(*args):
    return subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          text=True, encoding="utf-8", errors="replace").stdout


def staged_article_slugs():
    """commit に入る blog/<slug>.html の slug（index.html は配線なので除く）"""
    out = sh("git", "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    slugs = []
    for path in out.splitlines():
        m = re.fullmatch(r"blog/([A-Za-z0-9._-]+)\.html", path.strip())
        if m and m.group(1) != "index":
            slugs.append(m.group(1))
    return slugs


def commit_message():
    """commit-msg フックは第1引数にメッセージファイルのパスを受け取る。

    pre-commit ではダメだった: そこで .git/COMMIT_EDITMSG を読むと
    **前回の** メッセージが入っており、常に素通り（または誤検出）する。
    """
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return open(sys.argv[1], encoding="utf-8", errors="replace").read()
    return ""


def main():
    slugs = staged_article_slugs()
    if not slugs:
        return 0
    msg = commit_message()
    missing = [s for s in slugs if s not in msg]
    if not missing:
        return 0
    print("NG: commit に、メッセージで名指ししていない記事が入っています")
    for s in missing:
        print("  - blog/%s.html" % s)
    print("")
    print("同じ作業ツリーを別のセッションが使っています。心当たりが無いなら、")
    print("それは他のセッションがステージ済みだった記事です（本番へ出ます）。")
    print("")
    print("  自分の分だけ出す:  git commit -- <自分のファイル> ...")
    print("  まとめて出す    :  commit メッセージに上の slug を書く")
    print("  検査を飛ばす    :  git commit --no-verify")
    return 1


if __name__ == "__main__":
    sys.exit(main())
