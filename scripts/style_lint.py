#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI感の検査＝「語を探す」と「数える」の2本立て（2026-08-22新設・BLOG-OPS §0-12）。

起点: @ai_ai_ailover の投稿「AI感消して…」（2026-08-22 髙橋さん共有）。うちの既存検査
（ai_tell_lint＝ダーシ密度・AI文体マーカー／paren_lint／readability_lint／natural-japanese）
に無かったのは次の4つ。言葉の側に寄せて作る＝モデルが替わっても持ち越せる。

  1. NG表現（scripts/ng_words.json・**必ず代替つき**）: 「効きます。」「単なるAではなくB」等。
     語の置換ではなく**文ごと書き直す**。リストは指摘が出るたびに1行足す（育てる）。
     誤検出は**消さずに狭める**（pattern の条件を足す）
  2. 文末3連続: 「〜します。〜します。〜します。」同じ語尾が3文続くとリズムでAIと分かる。
     2連続は普通。3から警告
  3. 文体の混在: です・ます（敬体）と だ・である（常体）の混在。少数派を多数派に寄せる
  4. たとえ話の重なり: 「例えると」「みたいなもの」が近距離で2回＝描きかけの絵を消して別の絵

NGにするのは 1〜3（slug 20260823 以降）。4 は report-only（創作・引用で正当な場合がある）。
既存記事は「参考」で多い順に3本出すだけ（黙って対象外にしない＝paren_lint と同じ流儀）。

使い方:
    python scripts/style_lint.py                      # 全記事（gate.py 経由）
    python scripts/style_lint.py blog/<slug>.html     # 1本
    python scripts/style_lint.py --tally [--days 7]   # 直近N日の記事でどの規則が何回鳴ったか（週次棚卸し用）
"""
import datetime as dt
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import blog_files  # noqa: E402

CUTOFF = "20260823"
NG_WORDS = json.load(open(os.path.join(HERE, "ng_words.json"), encoding="utf-8"))
MAX_TAIL_RUN = 3          # 同じ語尾が3文連続で警告
MIX_MIN = 4               # 少数派の文体が4文以上あれば混在とみなす（引用内の「〜だ」1〜3文は拾わない）
MIX_RATIO = 0.30          # 少数派が3割未満＝「混ざった」状態（3割以上なら意図した文体）
METAPHOR_GAP = 220        # たとえ話の合図がこの字数以内に2回
METAPHOR = r"例える|たとえる|に例えれば|みたいなもの|イメージとしては|に似てい"
POLITE = r"(です|ます|ません|でした|ました|ましょう|ください)$"


def paragraphs(html):
    """<p> の中身だけ（表・FAQ・箇条書きは並列が設計なので語尾の検査から外す）。"""
    s = re.sub(r"(?s)<(script|style|head).*?</\1>", "", html)
    out = []
    for m in re.finditer(r"(?s)<p\b[^>]*>(.*?)</p>", s):
        t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        if t and "a-src" not in m.group(0):
            out.append(t)
    return out


def sentences(paras):
    for p in paras:
        for s in re.split(r"(?<=[。！？])", p):
            s = s.strip()
            if len(s) >= 6:
                yield s


def tail_of(s):
    s = re.sub(r"[。！？」）)]+$", "", s)
    m = re.search(r"(ました|でした|ません|ましょう|ください|です|ます|である|だった|った|た|だ|ない|る)$", s)
    return m.group(1) if m else s[-2:]


def body_text(html):
    s = re.sub(r"(?s)<(script|style|head).*?</\1>", "", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))


def measure(html):
    paras = paragraphs(html)
    sents = list(sentences(paras))
    body = body_text(html)
    hits = []
    # 1. NG表現
    for rule in NG_WORDS:
        found = [m.group(0) for m in re.finditer(rule["pattern"], body)]
        limit = rule.get("max", 0)
        if len(found) > limit:
            hits.append(("ng:" + rule["id"], len(found), found[:3], rule))
    # 2. 文末3連続（段落をまたがない）
    runs = []
    for p in paras:
        ss = [s for s in sentences([p])]
        cur, prev = 1, None
        for s in ss:
            t = tail_of(s)
            if t == prev:
                cur += 1
                if cur == MAX_TAIL_RUN:
                    runs.append((t, p[:40]))
            else:
                cur = 1
            prev = t
    # 3. 文体の混在
    polite = sum(1 for s in sents if re.search(POLITE, re.sub(r"[。！？」）)]+$", "", s)))
    plain = sum(1 for s in sents if re.search(r"(である|だ|だった)$", re.sub(r"[。！？」）)]+$", "", s)))
    mix = None
    total = polite + plain
    if total and min(polite, plain) >= MIX_MIN and min(polite, plain) / total < MIX_RATIO:
        mix = (polite, plain)
    # 4. たとえ話の重なり（report-only）
    pos = [m.start() for m in re.finditer(METAPHOR, body)]
    near = [(a, b) for a, b in zip(pos, pos[1:]) if b - a <= METAPHOR_GAP]
    return {"hits": hits, "runs": runs, "mix": mix, "near": near, "len": len(body)}


def check_one(path, strict=True):
    html = open(path, encoding="utf-8").read()
    m = measure(html)
    ng, info = [], []
    for key, n, ex, rule in m["hits"]:
        ng.append("NG表現 %d件『%s』: %s\n      → 直し方: %s（語の置換ではなく、その文を丸ごと書き直す）"
                  % (n, "／".join(ex), rule["why"], rule["fix"]))
    for t, head in m["runs"]:
        ng.append("同じ語尾「%s」が%d文連続（段落「%s…」）\n      → 直し方: 出来事は過去形・仕組みは現在形に混ぜる／2文を1文に統合／主語を物や仕組みに替える"
                  % (t, MAX_TAIL_RUN, head))
    if m["mix"]:
        po, pl = m["mix"]
        ng.append("文体の混在: 敬体%d文・常体%d文\n      → 直し方: 少数派を多数派に寄せる（どちらが正しいかは決めなくてよい）" % (po, pl))
    for a, b in m["near"]:
        info.append("たとえ話の合図が%d字以内に2回（位置%d→%d）。描きかけの絵を消して別の絵を描かせていないか" % (b - a, a, b))
    name = os.path.basename(path)
    if ng:
        print(("NG: " if strict else "参考 ") + name)
        for x in ng:
            print("  - " + x)
    for x in info:
        print("  参考 " + x)
    if not ng and strict:
        print("OK: %s（NG表現0・語尾3連続0・文体混在なし）" % name)
    return 1 if (ng and strict) else 0


def main_all():
    slugs = blog_files.article_slugs()
    live, skipped = (blog_files.split_unpublished(slugs) if hasattr(blog_files, "split_unpublished") else (slugs, []))
    fails, legacy, checked = [], [], 0
    for slug in live:
        path = os.path.join(ROOT, "blog", slug + ".html")
        if not os.path.exists(path):
            continue
        if re.match(r"\d{8}", slug) and blog_files.in_scope(slug, CUTOFF):
            checked += 1
            if check_one(path, strict=True):
                fails.append(slug)
        else:
            m = measure(open(path, encoding="utf-8").read())
            score = len(m["hits"]) + len(m["runs"]) + (1 if m["mix"] else 0)
            if score:
                legacy.append((score, slug))
    if legacy:
        print("       参考 既存記事で鳴るもの %d本（公開済みのため落とさない・多い順に3本）:" % len(legacy))
        for score, slug in sorted(legacy, reverse=True)[:3]:
            print("         %s: %d件" % (slug, score))
    if fails:
        print("NG: AI感の検査 %d件（対象 %d記事・slug %s 以降で落とす）" % (len(fails), checked, CUTOFF))
        return 1
    print("OK: AI感の検査 全通過（対象 %d記事・slug %s 以降で落とす）" % (checked, CUTOFF))
    return 0


def tally(days):
    since = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y%m%d")
    count = {}
    files = 0
    for path in glob.glob(os.path.join(ROOT, "blog", "*.html")):
        slug = os.path.basename(path)[:-5]
        if not re.match(r"\d{8}", slug) or slug[:8] < since:
            continue
        files += 1
        m = measure(open(path, encoding="utf-8").read())
        for key, n, _, _ in m["hits"]:
            count[key] = count.get(key, 0) + n
        if m["runs"]:
            count["語尾3連続"] = count.get("語尾3連続", 0) + len(m["runs"])
        if m["mix"]:
            count["文体混在"] = count.get("文体混在", 0) + 1
        if m["near"]:
            count["たとえ話の重なり"] = count.get("たとえ話の重なり", 0) + len(m["near"])
    print("直近%d日の記事 %d本で鳴った規則（多い順）:" % (days, files))
    for k, v in sorted(count.items(), key=lambda x: -x[1]):
        print("  %3d  %s" % (v, k))
    if not count:
        print("  0件")
    print("→ 上位は『狭める（誤検出なら条件を足す）』か『育てる（本当の癖なら代替を見直す）』の判断材料。消さない")
    return 0


if __name__ == "__main__":
    if "--tally" in sys.argv:
        d = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 7
        sys.exit(tally(d))
    if len(sys.argv) > 1:
        # gate.py 経由で記事1本を渡されたとき。CUTOFF より前の slug は落とさず「参考」で出す
        slug = os.path.basename(sys.argv[1])[:-5]
        strict = "--strict" in sys.argv or (bool(re.match(r"\d{8}", slug)) and slug[:8] >= CUTOFF)
        sys.exit(check_one(sys.argv[1], strict=strict))
    sys.exit(main_all())
