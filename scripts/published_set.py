#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「本番に出ている記事」の集合を返す（配線・型の検査が見る対象）。

なぜ要るか（2026-08-14）:
  Cloudflare Pages は git から配信するので、**gitに入っていない blog/*.html は本番に存在しない**。
  ところが publish_check.py も format_lint.py も作業ディレクトリのファイルを列挙していたため、
  誰かが書きかけの記事をローカルに置いたまま別の作業へ移ると、その日から公開前ゲートが
  毎回NGを返し続ける状態になった（実際 20260813-torihikisaki-check.html で発生し、
  8/14の朝の記事はNGのまま push された）。

  常に赤いゲートは、緑にならないぶん「押し通す運用」を育てる。ずっと緑を疑うのと同じ理由で、
  ずっと赤も直す。見るのは「本番に出ているもの＝gitが持っているもの」に揃える。

  git add 済み（インデックス）の新記事は git ls-files に出るので、公開直前の記事は対象に入る。
  BLOG-OPS §6 の順番（git add → gate → commit → push）を守っていれば漏れない。

  除外したものは呼び出し側が必ず表示する。黙って落とすと検査の穴になる。
"""
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent


def tracked_blog_slugs():
    """gitが持っている blog/*.html の slug 集合。取れなければ None（＝従来どおり全部見る）。"""
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", "blog"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    slugs = set()
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.endswith(".html"):
            slugs.add(os.path.basename(line)[:-5])
    return slugs or None


def split_unpublished(slugs):
    """(本番に出ている slug のリスト, gitに無い slug のリスト) を返す。"""
    tracked = tracked_blog_slugs()
    if tracked is None:
        return list(slugs), []
    kept = [s for s in slugs if s in tracked]
    skipped = [s for s in slugs if s not in tracked]
    return kept, skipped


def note(skipped, indent="       "):
    """除外した記事を1行で説明する文字列（無ければ空）。呼び出し側は必ず出力する。"""
    if not skipped:
        return ""
    return "%s参考 未公開（gitに無いので本番に存在しない）ため対象外: %s" % (
        indent, "／".join(sorted(skipped)))
