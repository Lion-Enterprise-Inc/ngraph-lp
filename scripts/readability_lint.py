#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""読みにくさの検査——「長い文」と「同じ話の繰り返し」を機械で止める。

なぜ入れたか（2026-08-16・髙橋さん指摘）:
  20260815-tejun-wa-tool-ga-dasu について「内容はいいが、本文が何を言っているのか
  よく分からない」。既存の検査は AI生成の痕跡（ダーシ・AI文体）と かっこの多用 は
  見ていたが、**読みやすさそのもの**を誰も見ていなかった。文章術を毎回思い出す
  運用にしないため、数えられる2つをゲートに載せる。

  数えられないもの（主語が一人称か・抽象名詞が具体物に戻っているか・造語に定義が
  あるか）は、書き手が判断する。ここで検査するのは「機械が数えられる分」だけで、
  これを通ったから読みやすい、という意味ではない。

閾値の根拠（2026-08-16に既存61記事を実測。勘で置かない）:
  60字超の文の割合   最小3% / 中央31% / 平均28.5% / 最大54%
    → 40%。中央値に余裕があり、実測の最悪群（43〜54%）だけが落ちる。
  抽象語の密度       中央1.8 / 平均1.9 / 最大6.8（/1000字）
    → 5.5。分布に 5.4 → 6.6 の自然な切れ目があり、そこに線を引いた。
      基準点は2つ:「分かりにくい」と言われた 20260815-tejun… が6.8、
      髙橋さんが「めっちゃいい記事」と評した 20260806-seihon… が2.9。

⚠ この検査は問題の一部しか見ていない。2026-08-16の指摘の主因は
  「主語がAIで他人事」「造語に定義がない」で、どちらも文字列では判定できない。
  実際、指摘された記事は長い文11%・反復0件で、その2つでは素通りした。
  引っかかったのは抽象語の密度だけ。**通ったから読みやすい、ではない。**

使い方:
    python scripts/readability_lint.py          # gate.py が自動実行する
    python scripts/readability_lint.py --all    # 既存記事も含めて実測値を並べる（閾値の再検討用）
"""
import os
import re
import sys
import html as htmllib
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CUTOFF = "20260815"      # これ以降のslugは落とす。既存記事は「参考」で出すだけ
LONG_CHARS = 60          # 1文がこれを超えたら「長い文」
MAX_LONG_RATIO = 40      # 長い文の割合の上限（%）
PHRASE_CHARS = 16        # 反復とみなす最短の長さ
PHRASE_TIMES = 3         # 同じ言い回しがこの回数以上で反復
MAX_PHRASES = 3          # 反復とみなした言い回しの種類の上限
MAX_ABSTRACT_PER_1000 = 5.5   # 抽象語の密度の上限（/1000字）

# 具体物の代わりに置かれがちな言葉。これが増えるほど「絵が浮かばない文章」になる
ABSTRACT = r"(?:仕組み|経路|形で|形に|方式|工程|構造|定型|運用|処理)"


def body_of(html):
    """記事本文の地の文だけを返す（図・表・見出し・参考枠は文の数え方が違うので除く）。"""
    m = re.search(r"<article.*?</article>", html, re.S)
    if not m:
        return ""
    a = m.group(0)
    for pat in (r"<svg.*?</svg>", r"<table[^>]*>.*?</table>", r"<figure[^>]*>.*?</figure>",
                r"<h[1-6][^>]*>.*?</h[1-6]>", r"<div class=\"a-src\".*?</div>",
                r"<div class=\"a-cta\".*?</div>"):
        a = re.sub(pat, " ", a, flags=re.S)
    a = re.sub(r"<[^>]+>", " ", a)
    return re.sub(r"\s+", " ", htmllib.unescape(a)).strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[。？！])", text) if len(s.strip()) > 4]


def repeated_phrases(text):
    """3回以上そのまま出てくる言い回しを、重なりをまとめた最長の形で返す。

    窓を1字ずつずらして数えるだけだと、1つの繰り返しが十数件に化けて数が意味を失う。
    連続する窓は1つの言い回しに畳んでから数える。
    """
    n = len(text)
    if n <= PHRASE_CHARS:
        return []
    c = Counter(text[i:i + PHRASE_CHARS] for i in range(n - PHRASE_CHARS))
    hot = {k for k, v in c.items() if v >= PHRASE_TIMES}
    if not hot:
        return []
    # 出現位置を拾い、隣り合う位置は1つの言い回しに畳む
    starts = sorted(i for i in range(n - PHRASE_CHARS) if text[i:i + PHRASE_CHARS] in hot)
    merged, cur_s, cur_e = [], starts[0], starts[0] + PHRASE_CHARS
    for i in starts[1:]:
        if i <= cur_e:
            cur_e = max(cur_e, i + PHRASE_CHARS)
        else:
            merged.append(text[cur_s:cur_e])
            cur_s, cur_e = i, i + PHRASE_CHARS
    merged.append(text[cur_s:cur_e])
    # 畳んだ結果、同じ言い回しが複数の場所から出てくる＝それが反復の実体
    seen, out = set(), []
    for p in merged:
        key = p[:PHRASE_CHARS]
        if key in seen:
            continue
        seen.add(key)
        if not is_claim(p):
            continue    # 用語・固有名詞の反復は正当（下の is_claim を参照）
        out.append(p)
    return out


def is_claim(phrase):
    """その言い回しが「主張」か「ただの用語」かを分ける。

    用語や固有名詞は繰り返されて当たり前で（FDE記事の「Forward Deployed Engineer」、
    補助金記事の制度名）、これを落とす検査は押し通す運用を育てる。落としたいのは
    「同じ結論を3回言う」ほうなので、述語を含むものだけを反復とみなす。
    """
    return bool(re.search(r"(です|ます|ました|でした|ません|である|になる|という)", phrase))


def abstract_density(text):
    """抽象語の密度（/1000字）。具体物に戻せていない文章ほど高くなる。"""
    if not text:
        return 0.0
    return round(1000 * len(re.findall(ABSTRACT, text)) / len(text), 1)


def measure(html):
    """(長い文の割合%, 長い文のリスト, 反復した言い回しのリスト, 抽象語の密度) を返す。"""
    text = body_of(html)
    sents = sentences(text)
    if not sents:
        return 0, [], [], 0.0
    longs = [s for s in sents if len(s) > LONG_CHARS]
    ratio = round(100 * len(longs) / len(sents))
    return ratio, longs, repeated_phrases(text), abstract_density(text)


def live_slugs():
    """本番に出ている記事だけを見る（未公開の下書きでゲートが恒常NGになるのを防ぐ）。"""
    try:
        from published_set import published_slugs
        return sorted(published_slugs())
    except Exception:
        out = []
        for f in sorted(os.listdir(os.path.join(BASE, "blog"))):
            if f.endswith(".html") and f != "index.html":
                out.append(f[:-5])
        return out


def main():
    show_all = "--all" in sys.argv
    fails, legacy, checked = [], [], 0
    for slug in live_slugs():
        p = os.path.join(BASE, "blog", slug + ".html")
        if not os.path.exists(p):
            continue
        ratio, longs, phrases, abst = measure(open(p, encoding="utf-8").read())
        # 日付で始まらないslug（what-is-fde・ai-cost 等の恒久記事）は日付比較が
        # 成立しないので、必ず「参考」側に置く。文字列比較だと 'a' > '2' で
        # 新記事扱いになり、定時運用と無関係な記事でゲートが落ちる
        if not re.match(r"^\d{8}$", slug[:8]) or slug[:8] < CUTOFF:
            if (show_all or ratio > MAX_LONG_RATIO or len(phrases) > MAX_PHRASES
                    or abst > MAX_ABSTRACT_PER_1000):
                legacy.append("%s: 長い文 %d%%・反復 %d件・抽象語 %.1f/1000字"
                              % (slug, ratio, len(phrases), abst))
            continue
        checked += 1
        if ratio > MAX_LONG_RATIO:
            fails.append("%s: 60字を超える文が %d%%（上限 %d%%・%d文中%d文）\n     例: %s"
                         % (slug, ratio, MAX_LONG_RATIO, len(sentences(body_of(
                             open(p, encoding='utf-8').read()))), len(longs),
                            longs[0][:70] + "…"))
        if len(phrases) > MAX_PHRASES:
            fails.append("%s: 同じ言い回しが%d回以上出てくる箇所が %d種（上限 %d種）\n     例: %s"
                         % (slug, PHRASE_TIMES, len(phrases), MAX_PHRASES, phrases[0][:50] + "…"))
        if abst > MAX_ABSTRACT_PER_1000:
            fails.append("%s: 抽象語が %.1f/1000字（上限 %.1f・全61記事の中央は1.8）\n"
                         "     「%s」あたりを具体物の名前に戻す"
                         % (slug, abst, MAX_ABSTRACT_PER_1000, "／".join(
                             sorted(set(re.findall(ABSTRACT, body_of(
                                 open(p, encoding='utf-8').read()))))[:6])))

    for line in legacy:
        print("       参考 " + line)
    if fails:
        print("NG: 読みにくさ")
        for f in fails:
            print("  - " + f)
        print("%d件（対象 %d記事・slug %s 以降で落とす）" % (len(fails), checked, CUTOFF))
        print("  直し方: 長い文は1文1情報に切る／同じ結論の繰り返しは1回に減らす")
        return 1
    print("OK: 読みにくさ 全通過（対象 %d記事・slug %s 以降で落とす）" % (checked, CUTOFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
