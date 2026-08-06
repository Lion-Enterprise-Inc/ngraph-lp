# -*- coding: utf-8 -*-
"""IndexNow ping: sitemap.xmlの全URLをBing系検索エンジンに即時通知する。
使い方: デプロイ(git push→CF Pages反映確認)の後に `python scripts/indexnow.py` を実行。
特定URLだけ通知: `python scripts/indexnow.py https://ngraph.jp/blog/xxx ...`（拡張子なし・BLOG-OPS §8）
"""
import sys, json, re, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HOST = "ngraph.jp"
KEY = "1f9479eea285777318a2cc51aab60168"

def sitemap_urls():
    req = urllib.request.Request(f"https://{HOST}/sitemap.xml", headers={"User-Agent": "Mozilla/5.0"})
    xml = urllib.request.urlopen(req).read().decode("utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)

def ping(urls):
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls[:10000],
    }
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req)
        print("IndexNow:", r.status, "->", len(urls), "URLs submitted")
    except urllib.error.HTTPError as e:
        print("IndexNow HTTPError:", e.code, e.read().decode("utf-8", "replace"))

if __name__ == "__main__":
    urls = sys.argv[1:] or sitemap_urls()
    print(f"submitting {len(urls)} urls...")
    ping(urls)
