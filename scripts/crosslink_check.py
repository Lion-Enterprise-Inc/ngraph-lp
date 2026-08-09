#!/usr/bin/env python3
"""同日の朝A型↔夕B型が相互リンクしているかの機械検査（push前ゲート）

2026-08-09新設。BLOG-OPS §3 の最終行「朝記事から夕記事へ内部リンクを張り
（朝記事も更新）、相互接続する」と、朝夕の定時タスクの手順5が要求している配線。
手順書には書いてあるが誰も検査していなかったので、監査したら
2026-07-26 / 08-01（両方向）/ 08-06 / 08-07 / 08-09（両方向）で落ちていた。
＝手で守っていたものは3割落ちる。publish_check.py が「載せ忘れ」を見るのと同じ理由でここに置く。

夕記事の公開直後に朝記事へ追記する運用なので、**落ちるのは決まって朝記事側**
（夕を書いた勢いで朝に戻る工程が飛ぶ）。エラーには追記する場所を出す。

自動修正は付けない。アンカーテキスト（どの見出しで釣るか）は書き手の判断で、
機械が入れると「関連記事」だらけの死んだリンクになるため。

対象: blog/YYYYMMDD-*.html のうち同じ日に2本以上ある日。
      slug が CUTOFF 以降の日は落とす。それ以前は 参考 表示のみ（公開済みの改稿は髙橋さんの判断）。
      恒久ページ（what-is-fde 等・日付なしslug）は対象外。
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xcount import use_utf8_stdio

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 2026-08-09の夕タスクでこの検査を入れ、同時に08-09の両記事を直した。
# それ以前の落ち（7/26・8/1・8/6・8/7）は公開済み記事の改稿になるので落とさず、
# 黙って除外すると居座って検査が死ぬので毎回 参考 として表示する。
CUTOFF = "20260809"


def slug_of(name):
    return name[:-5] if name.endswith(".html") else name


def main():
    use_utf8_stdio()
    by_day = collections.defaultdict(list)
    for path in sorted(glob.glob(os.path.join(BASE, "blog", "2026*.html"))):
        name = os.path.basename(path)
        if not re.match(r"^\d{8}-", name):
            continue
        by_day[name[:8]].append(name)

    fails, legacy, checked = [], [], 0
    for day in sorted(by_day):
        names = by_day[day]
        if len(names) < 2:
            continue  # 1本しか無い日は相互リンクの相手がいない
        for name in names:
            checked += 1
            html = open(os.path.join(BASE, "blog", name), encoding="utf-8").read()
            others = [o for o in names if o != name]
            # 内部リンクは拡張子なし（BLOG-OPS §8）。href の形で見る
            linked = [o for o in others
                      if re.search(r'href="/blog/%s"' % re.escape(slug_of(o)), html)]
            if linked:
                continue
            msg = ("同じ日の記事へのリンクが無い（相手: %s）。"
                   "記事末の <div class=\"a-src\"> の最後に "
                   "「・あわせて読む：<a href=\"/blog/%s\">…</a>」を足す"
                   % ("／".join(slug_of(o) for o in others), slug_of(others[0])))
            (fails if day >= CUTOFF else legacy).append((name, msg))

    for name, msg in legacy:
        print("参考 %s: %s（公開済みのため落とさない）" % (name, msg))
    if fails:
        for name, msg in fails:
            print("NG %s: %s" % (name, msg))
        sys.exit(1)
    print("OK: 同日記事の相互リンク 全通過（対象 %d 記事・slug %s 以降で落とす）"
          % (checked, CUTOFF))


if __name__ == "__main__":
    main()
