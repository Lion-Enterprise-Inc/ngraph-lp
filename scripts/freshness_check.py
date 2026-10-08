#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""記事の「再確認期限」が切れていないかの検査（gate.py から自動実行）。

なぜ入れたか（2026-08-11）: GA4実測で、ブログの検索流入は
`20260803-saitei-chingin-2026`（最低賃金）1本にほぼ全部集中していた
（3週間で Organic 481セッション／他の記事は1〜4）。**その1本の中身は毎日古くなる**
——都道府県の答申が8月中ずっと順次出るため。人の記憶に頼ると必ず落ちる（実際に
「答申確定後の差し替え未実施」というメモだけが残り、3日ぶんの答申が反映されていなかった）。

仕組み: 記事の中に次の1行を置くと、期限を過ぎた日から公開前ゲートが落ちる。

    <!-- recheck: 2026-08-12 | 何を確認するか | 確認に使うコマンド -->

期限が来たら、コマンドを実行して差分を反映し、**期限を先へ動かす**:

    python scripts/freshness_check.py --bump <slug> 2026-08-13

期限を動かすだけで中身を確認しないのは、検査を殺す行為なので禁止（`--bump` は
確認したうえで打つ。何を確認したかはcommitに書く）。

★2026-10-08 改修（髙橋さん判断「たかがブログの記事でサイトが止まる？」）:
期限切れで公開を止めるのは、**期限切れの記事そのものを今回公開するとき（pushに含まれるとき）だけ**。
それ以外の push（トップ・フォーム・他の記事）は警告を出して通す。対象の判定は環境変数
GATE_CHANGED（改行区切りのパス。pre-push フックと gate.py が設定する）。
期限の見張りは毎朝の司書ジョブ（shingo-brain/scripts/inbox-job.ps1）が `--alert` で行い、
期限切れ・3日以内の記事を shingo-brain/inbox/ に通知として置く。
テスト用に FRESHNESS_TODAY=YYYY-MM-DD で「今日」を差し替えられる。

使い方:
    python scripts/freshness_check.py
    python scripts/freshness_check.py --alert          # 朝ジョブ用：期限切れ・3日以内を inbox に通知
    python scripts/freshness_check.py --bump 20260803-saitei-chingin-2026 2026-08-13
"""
import datetime
import glob
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile(r"<!--\s*recheck:\s*(\d{4}-\d{2}-\d{2})\s*\|([^|]*)\|([^>]*?)-->")


def entries():
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "blog", "*.html"))):
        if os.path.basename(f) == "index.html":
            continue
        s = io.open(f, encoding="utf-8").read()
        for m in PAT.finditer(s):
            out.append({
                "file": f,
                "slug": os.path.basename(f)[:-5],
                "due": m.group(1),
                "what": m.group(2).strip(),
                "how": m.group(3).strip(),
            })
    return out


def bump(slug, new_date):
    try:
        datetime.date.fromisoformat(new_date)
    except ValueError:
        print("ERROR: 日付は YYYY-MM-DD で渡す")
        return 2
    f = os.path.join(ROOT, "blog", slug + ".html")
    if not os.path.exists(f):
        print("ERROR: 記事が無い:", f)
        return 2
    s = io.open(f, encoding="utf-8").read()
    n, cnt = PAT.subn(lambda m: m.group(0).replace(m.group(1), new_date, 1), s)
    if not cnt:
        print("ERROR: recheck の行が無い:", slug)
        return 2
    io.open(f, "w", encoding="utf-8").write(n)
    print("OK: %s の再確認期限を %s へ移した（%d件）" % (slug, new_date, cnt))
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--bump":
        if len(sys.argv) < 4:
            print("usage: --bump <slug> <YYYY-MM-DD>")
            return 2
        return bump(sys.argv[2], sys.argv[3])

    today = datetime.date.fromisoformat(os.environ["FRESHNESS_TODAY"]) if os.environ.get("FRESHNESS_TODAY") else datetime.date.today()
    if len(sys.argv) > 1 and sys.argv[1] == "--alert":
        return alert(today)
    rows = entries()
    if not rows:
        print("OK: 再確認期限を設定した記事なし")
        return 0
    over = [r for r in rows if datetime.date.fromisoformat(r["due"]) < today]
    for r in sorted(rows, key=lambda x: x["due"]):
        d = datetime.date.fromisoformat(r["due"])
        mark = "期限切れ" if d < today else ("本日" if d == today else "あと%d日" % (d - today).days)
        print("  %s %s（%s）" % (r["slug"], mark, r["due"]))
    changed = {os.path.basename(x.strip()).replace(".html", "") for x in os.environ.get("GATE_CHANGED", "").splitlines() if x.strip()}
    blocking = [r for r in over if r["slug"] in changed]
    if over and not blocking:
        print()
        print("WARN: 再確認期限が切れている記事 %d件（今回の公開には含まれないので止めない）" % len(over))
        for r in over:
            print("  - %s（期限 %s）確認すること: %s ／ %s" % (r["slug"], r["due"], r["what"], r["how"]))
        return 0
    if over:
        over = blocking
        print()
        print("NG: 今回公開する記事の再確認期限が切れている %d件" % len(over))
        for r in over:
            print("  - %s（期限 %s）" % (r["slug"], r["due"]))
            print("      確認すること: %s" % r["what"])
            print("      コマンド:     %s" % r["how"])
        print()
        print("  反映したら期限を動かす: python scripts/freshness_check.py --bump <slug> <YYYY-MM-DD>")
        print("  ※中身を確認せずに期限だけ動かすのは禁止（検査が死ぬ）")
        return 1
    print("OK: 再確認期限 %d件、切れているものなし" % len(rows))
    return 0



def alert(today):
    """朝ジョブ用：期限切れ・3日以内の記事を shingo-brain/inbox/ に1枚の通知として置く（同日は上書き）。"""
    rows = [r for r in entries() if (datetime.date.fromisoformat(r["due"]) - today).days <= 3]
    if not rows:
        print("freshness alert: 対象なし")
        return 0
    inbox = os.environ.get("FRESHNESS_ALERT_DIR", r"C:\dev\shingo-brain\inbox")
    path = os.path.join(inbox, "_ngraph-lp-recheck_%s.md" % today.isoformat())
    lines = ["# ngraph.jp ブログの再確認期限（%s 時点・freshness_check.py --alert）" % today.isoformat(), "",
             "期限を過ぎてもサイトの公開は止まらないが、その記事自体は更新するまで公開できない。", ""]
    for r in sorted(rows, key=lambda x: x["due"]):
        d = (datetime.date.fromisoformat(r["due"]) - today).days
        mark = "期限切れ" if d < 0 else ("本日" if d == 0 else "あと%d日" % d)
        lines += ["- **%s**（期限 %s・%s）" % (r["slug"], r["due"], mark), "  - 確認すること: " + r["what"], "  - コマンド: " + r["how"]]
    io.open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("freshness alert: %d件 -> %s" % (len(rows), path))
    return 0

if __name__ == "__main__":
    sys.exit(main())
