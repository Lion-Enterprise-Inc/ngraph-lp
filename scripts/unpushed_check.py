# -*- coding: utf-8 -*-
"""書いたのにpushされていないブログ資産を毎回名指しする（2026-08-17新設）。

きっかけ: 8/17夕の検収で2件見つかった。
  1. 最低賃金記事の再確認期限を 8/18→8/20 にバンプした編集が未コミットのまま残っていた
     （＝突合の実測は済んでいるのに、その事実がリポジトリに無い）
  2. 8/13に書いたガイド記事 20260813-torihikisaki-check.html が4日間、
     未コミット・未配線のまま blog/ に置かれていた（表紙jpgも同様）

どちらも「ローカルにはある／本番には無い」状態で、誰も気づかないまま日が経つ。
既存の検査は本番に出た記事の中身しか見ないので、この穴は塞げない。

**report-only（必ず exit 0）**。理由: 並行セッションが作業中のファイルや、
公開判断が本人待ちの記事（torihikisaki）でpushを止めると、ゲートが
「閉じられないまま赤」になり、毎日の公開が止まる。名指しはするが止めない。
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET_DIRS = ("blog/", "assets/blog/")


def git(*args):
    r = subprocess.run(
        ["git"] + list(args), cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace"
    )
    return r.stdout or ""


def main():
    out = git("status", "--porcelain", "--", *TARGET_DIRS)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip().strip('"')
        if not path.startswith(TARGET_DIRS):
            continue
        full = os.path.join(ROOT, path.replace("/", os.sep))
        days = ""
        if os.path.exists(full):
            days = "%d日前に更新" % int((time.time() - os.path.getmtime(full)) / 86400)
        if code.strip() == "??":
            kind = "未追跡（gitに無い＝本番に存在しない）"
        elif code[0] == "A":
            # 2026-08-22: 8/21夕Bの記事が add 済みのまま commit されず、本番404で1日放置された。
            # 「未コミットの変更」では既存記事の小修正と区別がつかず読み飛ばされる。名指しを変える
            kind = "ステージ済みで未コミット（新記事がcommitから取りこぼされている＝本番に無い）"
        else:
            kind = "未コミットの変更"
        rows.append((path, kind, days))

    if not rows:
        print("OK: 未pushのブログ資産なし")
        return 0

    print("参考 未pushのブログ資産 %d件（本番には出ていない・止めはしない）:" % len(rows))
    for path, kind, days in sorted(rows):
        print("  - %s: %s%s" % (path, kind, "・" + days if days else ""))
    print("  → 公開するなら add してゲートを通す。公開しないなら消すか、理由をBLOG-OPSに1行残す")
    return 0


if __name__ == "__main__":
    sys.exit(main())
