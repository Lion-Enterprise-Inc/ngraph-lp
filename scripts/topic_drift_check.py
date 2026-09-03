#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""夕B型の題材がAI側から離れていないかを、書く前に見る検査。

2026-09-03新設。8/22〜9/2の夕B型7本が連続で「AIが主題でない制度解説」
（カスハラ／2割特例／年末調整／取適法／賃上げ促進税制／同一労働同一賃金）に
なっていたのを髙橋さんに指摘されて作った。

原因は夕タスクの手順2が「検索クエリが立つテーマ」「官公庁統計・調査データが
使えるテーマを優先」としか書いておらず、題材がAI側であるという条件が無かったこと。
公開前ゲートでは遅い（記事はもう書き上がっている）ので、テーマ選定の時点で回す。

使い方:
    python scripts/topic_drift_check.py            # 直近の夕B型を並べて連続数を出す
    python scripts/topic_drift_check.py --n 15     # 見る本数を変える
終了コード: AI側でない題材が3本以上つづいていたら exit 1（選び直させるため）
"""
import argparse
import glob
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# AI側の題材と判定する語。タイトル（＝読者が最初に見る場所）で見る。
# 本文にAIの語が1回出るだけの「後付けの接続」を通さないため、本文では見ない。
AI_WORDS = [
    "AI", "ＡＩ", "Claude", "クロード", "ChatGPT", "GPT", "OpenAI", "Anthropic",
    "Codex", "Copilot", "Gemini", "Grok", "KIMI", "DeepSeek", "Qwen", "Llama",
    "Perplexity", "Sora", "エージェント", "LLM", "MCP", "プロンプト",
    "自動化", "機械学習", "推論", "トークン", "モデル",
]
# 制度・税務・労務の語（AI語と同時に出ないなら、制度解説に寄っている合図）
SEIDO_WORDS = [
    "助成金", "補助金", "税制", "控除", "年末調整", "インボイス", "最低賃金",
    "労働", "雇用", "賃金", "社会保険", "扶養", "壁", "下請", "取適法",
    "カスハラ", "ハラスメント", "義務化", "施行", "改正", "過料", "納税",
]


def h1_of(path):
    s = open(path, encoding="utf-8").read()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", s, re.S)
    title = re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
    lab = re.search(r"2026\.\d\d\.\d\d\s*(朝|夕|ガイド|ナレッジ)", s)
    return title, (lab.group(1) if lab else "-")


def classify(title):
    """タイトルがAI側か。(is_ai, is_seido) を返す。"""
    is_ai = any(w in title for w in AI_WORDS)
    is_seido = any(w in title for w in SEIDO_WORDS)
    return is_ai, is_seido


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12, help="見る本数（既定12）")
    ap.add_argument("--limit", type=int, default=3,
                    help="この本数以上つづいたら exit 1（既定3）")
    a = ap.parse_args()

    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "blog", "2026*.html"))):
        title, lab = h1_of(f)
        if lab != "夕":
            continue
        rows.append((os.path.basename(f)[:-5], title))
    rows = rows[-a.n:]
    if not rows:
        print("夕B型の記事が見つかりません")
        return 0

    print("直近の夕B型 %d本（新しい順）:" % len(rows))
    streak = 0
    counting = True
    for slug, title in reversed(rows):
        is_ai, is_seido = classify(title)
        mark = "AI " if is_ai else ("制度" if is_seido else "他 ")
        print("  %s %s  %s" % (mark, slug, title[:52]))
        if counting:
            if is_ai:
                counting = False
            else:
                streak += 1

    print()
    n_ai = sum(1 for _, t in rows if classify(t)[0])
    print("AI側の題材: %d/%d本" % (n_ai, len(rows)))
    if streak == 0:
        print("OK: 直近はAI側の題材（連続ドリフトなし）")
        return 0
    print("AI側でない題材が %d本つづいています。" % streak)
    if streak < a.limit:
        print("OK: まだ %d本（%d本つづいたら選び直し）" % (streak, a.limit))
        return 0
    print()
    print("NG: 題材を選び直してください。うちの陣地はAI側です:")
    print("  ・AIツールとモデルの動き（Claude Code / Codex / Gemini / Grok / KIMI / OpenAI…）")
    print("  ・政府のAI政策・AI補助金・AIの規制")
    print("  ・AIのインフラと採算（電力・GPU・API単価）")
    print("  ・AI企業の経営者の発信（Anthropic・OpenAI・イーロン・マスク）")
    print("  ・他社／AIソロプレナーのAI活用事例")
    print("  ・うちのノウハウ（主語はAIの挙動。自社の実測は根拠として本文に置く）")
    print()
    print("  制度ものを書くなら「AIが対象になるか／AIで何が変わるか」が記事の背骨に")
    print("  あるときだけ（例: 業務改善助成金でAIの月額料金が対象になる条件＝可）。")
    print("  詳しくは BLOG-OPS.md §4 と memory feedback_topic_is_ai_behavior_not_our_blog_ops")
    return 1


if __name__ == "__main__":
    sys.exit(main())
