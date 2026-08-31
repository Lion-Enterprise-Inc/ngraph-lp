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
import io
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
        age = -1
        if os.path.exists(full):
            age = int((time.time() - os.path.getmtime(full)) / 86400)
        rows.append((path, kind, days, age))

    if not rows:
        print("OK: 未pushのブログ資産なし")
        return 0

    # 2026-09-01: 8/30夕Bの記事がステージ済みのまま commit されず、本番404で約29時間放置された。
    # 8/21にも同じことが起きており（上のコメント）、名指しを変えるだけでは止まらなかった。
    # 原因は「今日の作業中のもの」と「前のセッションの取り残し」が同じ塊で並ぶこと。
    # 作業中は正常なので読み飛ばすのが正しく、その読み飛ばしが取り残しにも及ぶ。
    # よって**1日以上動いていないものを別枠にして先に出す**（止めはしない＝設計は変えない）。
    # 公開保留と決まっているものは `.assetsignore` に明示で入っている（§6-5.5）。
    # これを取り残しとして毎回鳴らすと、**その塊ごと読み飛ばす習慣がつく**＝
    # 本物の取り残しも一緒に見落とす。決着済みのものは警告から外し、静かに並べる。
    held = set()
    ai = os.path.join(ROOT, ".assetsignore")
    if os.path.exists(ai):
        for ln in io.open(ai, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                held.add(ln.lstrip("/").rstrip("/"))

    stale = [r for r in rows if r[3] >= 1 and r[0] not in held]
    decided = [r for r in rows if r[3] >= 1 and r[0] in held]
    fresh = [r for r in rows if r[3] < 1]

    if stale:
        print("⚠ 前のセッションの取り残しの可能性 %d件"
              "（1日以上動いていない・**本番には出ていない**）:" % len(stale))
        for path, kind, days, _ in sorted(stale):
            print("  - %s: %s%s" % (path, kind, "・" + days if days else ""))
        print("  → 今日の作業を始める前に、公開するのか捨てるのかを決めて閉じること。")
        print("    公開するなら gate.py を通して commit + push、公開しないなら消すか、")
        print("    理由をBLOG-OPSに1行残す（放置すると次のセッションも同じ塊を読み飛ばす）")

    if decided:
        print("公開保留と決まっているもの %d件（.assetsignore 済み・触らない）:" % len(decided))
        for path, kind, days, _ in sorted(decided):
            print("  - %s%s" % (path, "・" + days if days else ""))

    if fresh:
        print("参考 未pushのブログ資産 %d件（作業中とみられる・止めはしない）:" % len(fresh))
        for path, kind, days, _ in sorted(fresh):
            print("  - %s: %s%s" % (path, kind, "・" + days if days else ""))
        print("  → 公開するなら add してゲートを通す。公開しないなら消すか、理由をBLOG-OPSに1行残す")
    return 0


if __name__ == "__main__":
    sys.exit(main())
