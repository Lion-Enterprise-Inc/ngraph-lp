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
    return 0


if __name__ == "__main__":
    sys.exit(main())
