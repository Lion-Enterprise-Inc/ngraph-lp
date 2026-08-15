#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""検査対象の記事ファイルの集合（各リントが共有する1つの定義）。

なぜ切り出したか（2026-08-16）:
  format_lint / paren_lint / title_lint がそれぞれ `blog/2026*.html` を glob していた。
  「記事のslugは日付で始まる」が対象集合の暗黙の前提として3か所にコピーされていたため、
  日付を持たない恒久slug のナレッジ型（`k-<topic>.html`・KNOWLEDGE-OPS.md §1）が
  **3つの検査から丸ごと外れたまま、ゲートは「全通過」と表示する**状態だった。
  1本目のナレッジ記事を公開する直前に発見（[[feedback_broken_gate_hides_violations]]）。

  対象集合の定義を1か所に寄せ、新しいslugの型を足すときはここだけを直す。

  日付を持たない既存の恒久記事（what-is-fde・ai-cost 等）は、規律が出そろう前に
  書かれたものなので従来どおり対象外。ナレッジ型は規律が全部そろった後に生まれた
  シリーズなので、常に対象にする。
"""
import glob
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ナレッジ型の恒久slug（KNOWLEDGE-OPS.md §1）
KNOWLEDGE_PREFIX = "k-"


def is_knowledge(slug):
    return slug.startswith(KNOWLEDGE_PREFIX)


def article_paths():
    """検査対象の記事ファイルのパス（日付slug＋ナレッジ型の恒久slug）。"""
    base = os.path.join(str(ROOT), "blog")
    return sorted(glob.glob(os.path.join(base, "2026*.html"))
                  + glob.glob(os.path.join(base, KNOWLEDGE_PREFIX + "*.html")))


def article_slugs():
    return sorted(os.path.basename(p)[:-5] for p in article_paths())


def in_scope(slug, cutoff):
    """その記事に新しい規律を適用するか（False＝既存記事なので落とさない）。

    ナレッジ型は日付を持たないが、規律が全部そろった後に始まったシリーズなので常に対象。
    日付で始まらない既存の恒久記事は、文字列比較すると 'a' > '2' で新記事扱いになるため
    （2026-08-16に paren_lint で踏んだ穴）、明示的に日付の形を確かめてから比較する。
    """
    if is_knowledge(slug):
        return True
    return bool(re.match(r"^\d{8}$", slug[:8])) and slug[:8] >= cutoff
