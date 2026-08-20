#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""一覧（blog/index.html）と llms.txt のタイトルが、記事のh1と一致しているか（report-only）。

なぜ要るか〔2026-08-20実測〕: `k-writing-standard` は記事本体だけ改題され、一覧と
llms.txt が**旧タイトルのまま公開されていた**（一覧の説明文に至っては没にした旧構想の
まま）。改題は記事HTMLの5箇所を直すので「直した」感覚になるが、配線側は別ファイルなので
黙って取り残される。既存の配線検査（publish_check）は **URLがあるか**しか見ていない。

なぜ落とさないか: 導入時点で既存14件が不一致で、しかも性質が3つに分かれる——
  ①改題が配線に反映されていない事故（最低賃金・k-x-loop 等。直すべき）
  ②llms.txt が恒久記事の題を意図的に短縮している（「営業のAI活用」等。正しいかもしれない）
  ③引用符だけの差
②を機械が書き換えると意図した索引名を壊すので、正解は機械では決められない。
よって**落とさず毎回全件出す**（黙って対象外にすると検査が死ぬ＝
memory feedback_broken_gate_hides_violations）。全件が①③に片付いたら
publish_check.py の CHECKS へ移して fail-closed に上げる。
"""
import importlib.util
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    spec = importlib.util.spec_from_file_location(
        "publish_check", os.path.join(HERE, "publish_check.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    bad = m.check_title_sync()
    if not bad:
        print("OK: 一覧・llms.txt のタイトルは記事h1と一致（不一致なし）")
        return 0
    print("参考 一覧/llms.txt と記事h1のタイトル不一致 %d件（本番には出ている・止めはしない）:" % len(bad))
    for b in bad:
        print("  - " + b.replace("\n", "\n  "))
    print("  → 改題を配線に反映し忘れたものは直す。llms.txt で意図的に短くしている恒久記事は"
          "そのままでよい（どちらか決めたらこの検査を publish_check.py の CHECKS へ移す）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
