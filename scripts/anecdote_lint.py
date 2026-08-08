# -*- coding: utf-8 -*-
"""一次体験の定型例の使い回し検査。

使い方:
    python scripts/anecdote_lint.py blog/<新記事>.html

「福井の飲食グループ本部（12店舗）／原価計算のExcelが約2年停止／
新人ガイダンス年間約100人」は公表可能な実話だが、同じ3点セットを
毎記事に貼ると読者には同じ話の繰り返しになる（2026-08-07 髙橋さん指摘・
当時44本中20本が使用、3点セット同時使用が11本）。

ルール（BLOG-OPS §0）:
- 3点セットを1記事に2つ以上入れない
- 直近7日の記事で同じ定型句を使っていたら、その記事では使わない
  （一次体験は「その記事のテーマでしか語れない具体」を書く）
"""
import glob
import os
import re
import sys

# NGを出す行に「—」が入っており、Windowsの既定(cp932)だと
# 違反を見つけた瞬間にUnicodeEncodeErrorで落ちていた（2026-08-08）。
# 検査が「見つけると落ちる」のは検査になっていないので、出力をUTF-8に固定する。
sys.stdout.reconfigure(encoding="utf-8")

TOKENS = {
    "12店舗": r"12\s*店舗",
    "原価Excel": r"原価[^。]{0,12}(Excel|エクセル)",
    # 「51〜100人は5,000万円」のような補助金の従業員規模区分を誤検知していたので、
    # 「年間」か「約」が直前に付く形だけを見る（2026-08-08）
    "年100人": r"(年間\s*約?|約)\s*100\s*人",
}
RECENT_DAYS = 7


def hits(path):
    text = open(path, encoding="utf-8").read()
    return [name for name, pat in TOKENS.items() if re.search(pat, text)]


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/anecdote_lint.py blog/<article>.html")
    target = sys.argv[1]

    # what-is-fde は伴走現場そのものを説明する正典ページなので、3点セットの
    # 「使い回し」ではなく「初出」にあたる。ここだけは全部書いてよい（2026-08-08）。
    # 他の記事はこのページへ内部リンクを張って、事例の反復は1つまでにする。
    if os.path.basename(target) == "what-is-fde.html":
        print("OK: 正典ページ（what-is-fde）は事例の初出として対象外")
        return

    mine = hits(target)
    ok = True

    if len(mine) >= 2:
        print(f"NG: 定型例を{len(mine)}個使用 {mine} — 1記事1つまで。言い換えるか削る")
        ok = False

    if mine:
        base = os.path.basename(target)
        m = re.match(r"(\d{8})-", base)
        # 日付付きslugなら直近7日、恒久記事なら日付付き全記事の直近7本と比較
        dated = sorted(glob.glob("blog/2*.html"), reverse=True)
        recent = []
        if m:
            d = int(m.group(1))
            recent = [f for f in dated
                      if os.path.basename(f) != base
                      and d - int(os.path.basename(f)[:8]) < RECENT_DAYS]
        else:
            recent = dated[:RECENT_DAYS]
        for f in recent:
            dup = set(mine) & set(hits(f))
            if dup:
                print(f"NG: {sorted(dup)} は直近記事 {f} でも使用済み — この記事では別の具体を書く")
                ok = False

    if ok:
        print("OK: 定型例の使い回しなし" + (f"（使用: {mine}）" if mine else ""))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
