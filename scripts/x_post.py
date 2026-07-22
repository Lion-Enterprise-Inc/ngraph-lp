# -*- coding: utf-8 -*-
"""ブログ記事のX(旧Twitter)自動投稿
使い方: python scripts/x_post.py "<投稿本文（URL込み・280字相当以内）>"

認証キーはリポジトリ外の C:/Users/shing/.ngraph/x_keys.env から読む（絶対にリポジトリに置かない。
このリポジトリはCloudflare Pagesで全ファイル公開されるため）。ファイル形式:
  X_API_KEY=...
  X_API_SECRET=...
  X_ACCESS_TOKEN=...
  X_ACCESS_TOKEN_SECRET=...
（X Developer Portalのアプリで App permissions を Read and write にしてから
 投稿するアカウントで Access Token を発行すること）

キーファイルが無い場合は何も投稿せず exit 3（呼び出し側は下書き運用にフォールバック）。
"""
import sys, os

sys.stdout.reconfigure(encoding="utf-8")

KEYS_PATH = os.path.expanduser("~/.ngraph/x_keys.env")
POST_URL = "https://api.x.com/2/tweets"


def load_keys():
    if not os.path.exists(KEYS_PATH):
        return None
    keys = {}
    for line in open(KEYS_PATH, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            keys[k.strip()] = v.strip()
    need = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"]
    return keys if all(keys.get(k) for k in need) else None


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(__doc__)
        sys.exit(1)
    text = sys.argv[1]
    keys = load_keys()
    if keys is None:
        print(f"NO_KEYS: {KEYS_PATH} が無いか不完全。投稿せず終了（下書き運用へ）")
        sys.exit(3)
    from requests_oauthlib import OAuth1Session
    s = OAuth1Session(
        keys["X_API_KEY"],
        client_secret=keys["X_API_SECRET"],
        resource_owner_key=keys["X_ACCESS_TOKEN"],
        resource_owner_secret=keys["X_ACCESS_TOKEN_SECRET"],
    )
    r = s.post(POST_URL, json={"text": text}, timeout=30)
    if r.status_code == 201:
        tid = r.json().get("data", {}).get("id", "?")
        print(f"OK tweet id={tid} https://x.com/i/web/status/{tid}")
    else:
        print(f"ERROR {r.status_code}: {r.text[:300]}")
        sys.exit(2)


if __name__ == "__main__":
    main()
