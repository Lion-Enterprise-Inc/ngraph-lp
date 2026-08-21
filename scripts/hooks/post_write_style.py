#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""PostToolUse フック: ngraph-lp/blog/*.html を書いた直後に AI感の検査を走らせ、
引っかかったら**書いた本人（Claude Code）に**警告を返す（2026-08-22新設）。

設計（@ai_ai_ailover 2026-08-22 の投稿から取り入れた部分）:
  - 書く前の指示（CLAUDE.md / BLOG-OPS）は会話が長くなると薄まる。書いた直後に機械が読む
  - 人に通知するのではなく Claude Code に返す（exit 2 + stderr）。作業は止めない＝直させる
  - 語の置換ではなく文ごと書き直させる（警告文に明記）
  - 判定は文字列照合（style_lint / ai_tell_lint）。AIに判定させない＝毎回同じ結果・無料・速い

対象: C:/dev/ngraph-lp/blog/ 配下で slug が 20260823 以降の日付付き記事のみ
（既存記事の小修正で毎回鳴らさない。gate.py の CUTOFF と同じ線）。
index.html・恒久記事（what-is-fde 等）は対象外。
"""
import json
import os
import re
import subprocess
import sys

ROOT = "C:/dev/ngraph-lp"
CUTOFF = "20260823"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    path = (data.get("tool_input") or {}).get("file_path") or ""
    path = path.replace("\\", "/")
    if "/ngraph-lp/blog/" not in path or not path.endswith(".html"):
        return 0
    slug = os.path.basename(path)[:-5]
    if not re.match(r"\d{8}", slug) or slug[:8] < CUTOFF:
        return 0
    out = []
    for script in ("style_lint.py", "ai_tell_lint.py"):
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "scripts", script), path],
                           capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=60)
        if r.returncode != 0:
            out.append(r.stdout.strip())
    if not out:
        return 0
    sys.stderr.write(
        "【AI感の検査（書いた直後の自動検査）】以下が引っかかった。語を置き換えるのではなく、"
        "検出箇所を含む文を丸ごと書き直すこと。直したら同じ検査がもう一度走る。\n"
        + "\n".join(out) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
