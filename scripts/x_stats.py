"""Xアナリティクスのコンテンツ CSV を集計する。

使い方:
    python scripts/x_stats.py <account_analytics_content_*.csv>

出典: X アナリティクス → コンテンツ → エクスポート。
プロフィールの目視は使わない（経過時間が混ざる・全件見られない）。

⚠ 投稿から 24〜48 時間は測らない。インプレッションは数日かけて積み上がる。
⚠ 表示回数の比較は「同じ経過時間・同じ出し方」で揃える。揃えられないなら比べない。
⚠ CSV だけでは Articles とリンク投稿を区別できない（どちらも t.co が付く）。

※ このファイルは本番配信される（ngraph.jp/scripts/ は公開）。実測値・運用判断は
  書かないこと。それらはローカル正本 X-OPS.md 側に置く。
"""
import csv
import statistics as st
import sys


def load(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def imp(r):
    return int(r["インプレッション数"])


def classify(rows):
    """リプライ / ブログ告知 / 個人投稿 に分ける。"""
    reply, announce, personal = [], [], []
    for r in rows:
        body = r["ポスト本文"].strip()
        if body.startswith("@"):
            reply.append(r)
        elif "#" in body and "t.co" in body:
            announce.append(r)
        else:
            personal.append(r)
    return {"リプライ": reply, "ブログ告知": announce, "個人投稿": personal}


def summarize(name, group):
    if not group:
        print(f"{name}: 0件")
        return
    v = sorted((imp(r) for r in group), reverse=True)
    print(
        f"{name}: n={len(v)} 中央値={st.median(v):.0f} 平均={st.mean(v):.0f} "
        f"最大={v[0]} 最小={v[-1]} 100未満={sum(1 for x in v if x < 100)}/{len(v)}"
    )
    print("   上位:", v[:8])


def totals(name, group):
    def s(key):
        return sum(int(r[key]) for r in group)

    print(
        f"{name}: 総インプ{s('インプレッション数'):>6} "
        f"URLクリック{s('URLのクリック数'):>4} "
        f"プロフィール訪問{s('プロフィールへのアクセス数'):>4} "
        f"新フォロー{s('新しいフォロー'):>3}"
    )


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/x_stats.py <account_analytics_content_*.csv>")
    groups = classify(load(sys.argv[1]))

    print("=== 区分別（インプレッション） ===")
    for name, g in groups.items():
        summarize(name, g)

    print("\n=== 転換（ここが判断材料・X-OPS §3） ===")
    for name, g in groups.items():
        totals(name, g)

    print("\n=== ブログ告知の内訳（新しい順） ===")
    for r in groups["ブログ告知"]:
        print(
            f"  {r['日付'][5:]:>12} {imp(r):>5}  "
            f"URLクリック{r['URLのクリック数']:>2} "
            f"プロフ{r['プロフィールへのアクセス数']:>2}  "
            f"{r['ポスト本文'][:34]}"
        )


if __name__ == "__main__":
    main()
