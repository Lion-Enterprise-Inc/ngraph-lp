#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""X公開アルゴリズムの監視——重み・係数が変わったら差分で知らせる（2026-08-17新設）。

なぜ入れたか: 8/17のXアルゴ検証記事とX-OPSの運用仕様は、xai-org/x-algorithm の
パラメータ実測値に依存している。READMEは実験で重みが変わり得ると明言しており、
放置すると「唯一の根拠が古い数字で回る」（最低賃金記事と同じ構造）。
saitei_chingin_watch.py と同じ役割の装置。

使い方:
    python scripts/x_algo_watch.py            # GitHubの現物と snapshot を突合（差分あれば exit 1）
    python scripts/x_algo_watch.py --update   # 現物を新しい正として snapshot を更新

ネットワークに出るので gate.py には入れない（公開前ゲートを外部依存にしない）。
記事の recheck 期限（freshness_check）から手動で回すのが導線。
"""
import json
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "scripts", "x_algo_snapshot.json")
RAW = "https://raw.githubusercontent.com/xai-org/x-algorithm/main/"

# 監視対象（記事とX-OPSが根拠にしている値だけ。全パラメータは追わない＝ノイズで死ぬ）
WATCH = [
    "FavoriteWeight", "ReplyWeight", "RetweetWeight", "QuoteWeight", "ShareWeight",
    "ShareViaDmWeight", "ShareViaCopyLinkWeight", "FollowAuthorWeight", "ProfileClickWeight",
    "NotInterestedWeight", "BlockAuthorWeight", "MuteAuthorWeight", "ReportWeight",
    "NotDwelledWeight", "AuthorDiversityDecay", "AuthorDiversityFloor", "OonWeightFactor",
    "BidirectionalFollowReplyWeightBoost",
    "ColdStartImpressionThreshold", "ColdStartSlotMin", "ColdStartSlotMax",
    "ColdStartFollowerCap", "ColdStartMaxPostAgeSecs", "LowImpressionsMaxPositionRatio",
]

PARAM_RE = re.compile(r"param!\(\s*(\w+)\s*,\s*\w+\s*,\s*\"[^\"]+\"\s*,\s*(-?[\d.]+)\s*\)", re.S)


def fetch(path):
    req = urllib.request.Request(RAW + path, headers={"User-Agent": "ngraph-x-algo-watch"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def current():
    src = fetch("home-mixer/params/param.rs")
    vals = {m.group(1): float(m.group(2)) for m in PARAM_RE.finditer(src) if m.group(1) in WATCH}
    cfg = fetch("home-mixer/params/config.rs")
    m = re.search(r"MAX_POST_AGE:\s*u64\s*=\s*([\d\s*+]+);", cfg)
    if m:
        vals["MAX_POST_AGE_HOURS"] = eval(m.group(1)) / 3600  # noqa: S307 - 数式リテラルのみ
    missing = [w for w in WATCH if w not in vals]
    return vals, missing


def main():
    try:
        vals, missing = current()
    except Exception as e:  # noqa: BLE001
        print(f"取得失敗（ネットワークかリポジトリ構造の変化）: {e!r}")
        print("パラメータのファイル配置が変わった可能性もある。手でリポジトリを確認すること")
        return 2

    if "--update" in sys.argv or not os.path.exists(SNAP):
        json.dump(vals, open(SNAP, "w", encoding="utf-8"), indent=1, sort_keys=True)
        print(f"snapshot更新: {len(vals)}項目 -> {SNAP}")
        if missing:
            print("⚠ 取得できなかった監視対象:", "／".join(missing))
        return 0

    snap = json.load(open(SNAP, encoding="utf-8"))
    diffs = []
    for k in sorted(set(snap) | set(vals)):
        a, b = snap.get(k), vals.get(k)
        if a != b:
            diffs.append(f"  {k}: {a} -> {b}")
    if missing:
        diffs.append("  取得不能（構造変化の疑い）: " + "／".join(missing))
    if diffs:
        print("X算法パラメータに差分あり。記事とX-OPS §11の数値を更新し、--update でsnapshotを進めること:")
        print("\n".join(diffs))
        print("対象: blog/20260817-x-algorithm-code.html ／ X-OPS.md §11 ほか当該数値を引く記事")
        return 1
    print(f"OK: 監視対象{len(vals)}項目、snapshotと一致（重みの変更なし）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
