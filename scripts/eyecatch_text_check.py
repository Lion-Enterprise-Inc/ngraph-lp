#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""表紙（アイキャッチ）の文言が、記事の現在のタイトルとズレていないかの検査。

なぜ入れたか（2026-08-11・髙橋さん指摘「面白いテーマなのに表紙の文字がそれを表現出来てない」）:
`20260806-seihon-yomarenai` は8/8に改題（旧「正本をつくったのに、AIが読まなかった」→
新「AIは指示を一定確率で無視する」）したのに、**表紙だけが旧タイトルのまま3日間出ていた**。
原因は仕組みの側にある——**表紙の文言は焼かれたJPEGの中にしか存在せず、どこにも記録が無かった。**
だから改題しても「表紙が古い」ことを誰も（人もスクリプトも）見られなかった。
8/9に同じ画像を重なり修正で作り直したときも、旧文言のまま再生成している（＝日付の比較では捕まらない）。

仕組み: `eyecatch_gen.py` が生成時に `assets/blog/_eyecatch.json` へ
  {slug: {title, sub, pattern, fs, article_h1}}
を記録する。`article_h1` は「その表紙を作った時点の記事タイトル」。
この検査は `article_h1` と現在の `<h1>` を比べるだけ。**改題すれば必ず不一致になる。**

判定:
  - 記録あり／`article_h1` が現在のh1と不一致 → NG（改題後に表紙を作り直していない）
  - 記録あり／`article_h1` が null → 現在のh1で初回紐付けして記録（表紙を記事より先に作る運用を許容）
  - 記録なし／slug が CUTOFF 以降 → NG（生成器を通していない＝手で作った表紙）
  - 記録なし／それ以前 → 参考表示のみ（既存資産。改題履歴のある記事は8/11に遡って記録済み）

使い方:
    python scripts/eyecatch_text_check.py
"""
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "assets", "blog", "_eyecatch.json")
# この日付以降のslugは、記録が無ければ落とす（title_lint.py と同じ考え方）
CUTOFF = "20260811"


def load():
    try:
        return json.load(open(STORE, encoding="utf-8"))
    except Exception:
        return {}


def h1_of(path):
    m = re.search(r"<h1[^>]*>(.*?)</h1>", open(path, encoding="utf-8").read(), re.S)
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else None


def main():
    data = load()
    files = sorted(glob.glob(os.path.join(ROOT, "blog", "*.html")))
    files = [f for f in files if os.path.basename(f) != "index.html"]

    bad, linked, unrecorded = [], [], []
    for f in files:
        slug = os.path.basename(f)[:-5]
        h1 = h1_of(f)
        rec = data.get(slug)
        if rec is None:
            if slug[:8].isdigit() and slug[:8] >= CUTOFF:
                bad.append((slug, "表紙の文言が記録されていない（eyecatch_gen.py で作り直す）"))
            else:
                unrecorded.append(slug)
            continue
        if rec.get("article_h1") is None:
            rec["article_h1"] = h1
            linked.append(slug)
            continue
        if h1 and rec["article_h1"] != h1:
            bad.append((slug, "改題後に表紙を作り直していない\n"
                              "         表紙を作った時のタイトル: %s\n"
                              "         現在のタイトル:           %s\n"
                              "         いまの表紙の文言: 「%s」／「%s」"
                              % (rec["article_h1"][:60], h1[:60],
                                 rec.get("title", "").replace("{nb}", "").replace("{/nb}", ""),
                                 rec.get("sub", ""))))

    if linked:
        with open(STORE, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=1, sort_keys=True)
            fp.write("\n")
        print("初回紐付け: %d件（%s）" % (len(linked), " / ".join(linked)))

    if bad:
        print("NG: 表紙の文言が記事とズレている %d件" % len(bad))
        for slug, why in bad:
            print("  - %s: %s" % (slug, why))
        print("  直し方: python scripts/eyecatch_gen.py <slug> \"<主張だけを短く>\" \"<サブ>\" <pattern>")
        print("         （表紙は記事タイトルの流用ではなく、主張だけを言い切る。BLOG-OPS §3）")
        return 1

    print("OK: 表紙の文言 %d件を記事タイトルと照合（未記録の既存記事 %d件は対象外）"
          % (len(files) - len(unrecorded), len(unrecorded)))
    show_wording(data)
    return 0


def show_wording(data):
    """公開する記事の表紙の文言を、画像ではなくテキストで出す（report-only・2026-08-17新設）。

    なぜ入れたか〔髙橋さん 2026-08-17「この表紙の文言どうなってるの。これ意味不明だし
    何にも魅力的じゃないな」〕: `20260817-qwen-27b-local` の表紙が「最強より、手元で動く」＝
    主語が無く、表紙だけ見ても何の話か分からない状態で公開されていた。BLOG-OPS §3 の
    「表紙の主張には主語を入れる」は前日（8/16）に本人指摘で入れたばかりのルールで、
    防波堤は「生成前にこの行を読むことと、目視」だけだった。**画像を目視すると、絵と級数は
    見るが文言は読み飛ばす。** だから文言そのものをテキストで、記事タイトルと並べて出す。

    主語の有無を機械で判定しようとしたが、記録26件で実測したところ助詞（は/が/も）を
    持たない表紙が7件あり、うち「最低賃金2026、いつから・いくら」「取引先を3分で裏取りする」
    「いいね40個 ＝ リンクコピー1個」は表紙として成立していた（誤検知が3割近い）。
    よって**判定はしない。読む機会を強制するだけ**にしてある（BLOG-OPS §3 の
    「雑な検査は誤検知で運用を止める」に従う）。
    """
    if len(sys.argv) < 2:
        return
    slug = os.path.basename(sys.argv[1])
    slug = slug[:-5] if slug.endswith(".html") else slug
    rec = data.get(slug)
    if not rec:
        return
    title = (rec.get("title") or "").replace("{nb}", "").replace("{/nb}", "")
    print("表紙の文言（目で読んで判断する。機械は判定しない）:")
    print("  主張: 「%s」" % title)
    print("  サブ: 「%s」" % (rec.get("sub") or ""))
    print("  記事: %s" % (rec.get("article_h1") or ""))
    print("  問い: ①主語があるか（「AIは」「Qwenは」…体言止めの標語にしない）")
    print("        ②表紙だけ見て何の話か分かるか ③記事の一番強い数字が載っているか")


if __name__ == "__main__":
    sys.exit(main())
