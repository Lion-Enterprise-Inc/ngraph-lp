# -*- coding: utf-8 -*-
"""公開した記事が、本当にpushされた状態で終わっているかを最後に確かめる（2026-08-24新設）。

きっかけ: 8/24の朝の定時タスクの検収で、同日夕Bの記事
`20260824-gyomu-kaizen-joseikin.html` に未コミットの修正が14行残っていた。
中身は最終検収でのかっこ書きの開き直し13箇所と、**朝記事への相互リンク1行**。
夕のセッションは commit → push → HTTP 200 まで確認して完了報告しており、
そのあとに直した分がローカルに取り残されていた。本番は1日、古い本文と
相互リンクの無い状態で回っていた。

既存の検査で塞げなかった理由:
  - `gate.py` は push の**前**に走る。そこでは未コミットなのが正常なので判定できない
  - `unpushed_check.py` は名指しするが report-only（並行セッションや公開保留の記事で
    ゲートが「閉じられないまま赤」になるのを避けるため。この設計は変えない）
  - 本番実測は HTTP 200 しか見ておらず、**古い版でも200が返る**

よってこれは push の**後**に、**いま公開した記事1本だけ**を対象に閉じる検査にする。
対象を1本に絞るので、他セッションが別の記事を編集中でも止まらない。

  python scripts/published_clean.py blog/<記事>.html   # 汚れていたら exit 1
"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    r = subprocess.run(
        ["git"] + list(args), cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace"
    )
    return (r.stdout or "").strip(), r.returncode


def main(argv):
    if len(argv) != 1:
        print("使い方: python scripts/published_clean.py blog/<記事>.html")
        return 2
    path = argv[0].replace("\\", "/")
    if not os.path.exists(os.path.join(ROOT, path.replace("/", os.sep))):
        print("NG: ファイルが無い: %s" % path)
        return 1

    ng = []

    tracked, _ = git("ls-files", "--", path)
    if not tracked:
        ng.append("gitに追跡されていない（＝本番に存在しない）")

    dirty, _ = git("status", "--porcelain", "--", path)
    if dirty:
        ng.append(
            "未コミットの変更が残っている（最終検収の直しがローカルに取り残されている）: %s"
            % dirty.splitlines()[0][:2].strip()
        )

    if tracked and not dirty:
        # この記事を最後に触ったcommitが origin/main に載っているか
        sha, _ = git("log", "-1", "--format=%H", "--", path)
        if not sha:
            ng.append("この記事を含むcommitが見つからない")
        else:
            _, rc = git("merge-base", "--is-ancestor", sha, "origin/main")
            if rc != 0:
                ng.append("最後のcommit %s が origin/main に載っていない（未push）" % sha[:7])

    if ng:
        print("NG: 公開した記事がpush済みの状態で終わっていない: %s" % path)
        for m in ng:
            print("  - %s" % m)
        print("  → add → gate.py → commit → push まで通してから完了報告する")
        return 1

    print("OK: %s は push 済みで、ローカルに取り残しなし" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
