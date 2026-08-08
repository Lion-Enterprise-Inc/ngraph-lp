# -*- coding: utf-8 -*-
"""IndexNow ping: sitemap.xmlの全URLをBing系検索エンジンに即時通知する。

使い方: デプロイ(git push→CF Pages反映確認)の後に `python scripts/indexnow.py` を実行。
特定URLだけ通知: `python scripts/indexnow.py https://ngraph.jp/blog/xxx ...`（拡張子なし・BLOG-OPS §8）

**成否は exit code で返す（0=成功 / 1=失敗）**。定時実行エージェントはこれで送信漏れを検知する。
以前は HTTPError を print するだけで exit 0 を返していたため、403（キー不正）でも
ネットワーク断でも「送信した」ように見えて、無言で送信ゼロになり得た（2026-08-08 是正）。
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

HOST = "ngraph.jp"
KEY = "1f9479eea285777318a2cc51aab60168"
KEY_URL = "https://%s/%s.txt" % (HOST, KEY)
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "Mozilla/5.0"}
# IndexNow の成功応答。200=受理 / 202=受理（キー検証は非同期）
OK_STATUS = (200, 202)
# 失敗コードの意味（そのまま出しても何が悪いか分からないので訳を添える）
ERR_HINT = {
    400: "リクエストの形式が不正（JSONかURLの形を確認）",
    403: "キーが無効。%s が配信されていないか中身が違う" % KEY_URL,
    422: "URLがhostと一致しない、またはキーがURLと対応していない",
    429: "送信しすぎ（レート制限）。時間を空けて再送する",
}


def _get(url, timeout=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def check_key():
    """keyファイルの状態を送信前に見る。戻り値は (中止すべきか, メッセージ)。

    **「取得できない」と「中身が違う」を区別する**:
      - 中身が違う → 403が確定するので中止する（送るだけ無駄で、失敗の原因も紛れる）
      - 取得できない → こちら側の一時的な不調でも起きる。キー自体はBingが直接取りに行く
        ので、送信は続行して警告だけ出す（ここで止めると、ngraph.jpの瞬断で
        公開フローが止まる。それは検査として過剰）
    """
    try:
        body = _get(KEY_URL).read().decode("utf-8", "replace").strip()
    except Exception as e:
        return False, "警告: keyファイルを確認できませんでした（%s）: %s — 送信は続行する" % (KEY_URL, e)
    if body != KEY:
        return True, "keyファイルの中身が一致しません: 期待=%s 実際=%r" % (KEY, body)
    return False, None


def sitemap_urls():
    xml = _get("https://%s/sitemap.xml" % HOST).read().decode("utf-8")
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def validate(urls):
    """host不一致のURLが1本でも混ざると全体が422で落ちるので、送る前に弾く。"""
    prefix = "https://%s/" % HOST
    bad = [u for u in urls if not u.startswith(prefix)]
    if bad:
        return "host(%s)と一致しないURLが%d件あります: %s" % (HOST, len(bad), bad[:3])
    if not urls:
        return "送信するURLが0件です"
    return None


def log(line):
    """ログはリポジトリ内に置かない（Cloudflare Pagesが全ファイルを配信するため）。"""
    path = os.path.join(os.environ.get("TEMP") or "/tmp", "ngraph-indexnow.log")
    stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("%s\t%s\n" % (stamp, line))
    except OSError:
        pass


def ping(urls):
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": KEY_URL,
        "urlList": urls[:10000],
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        r = urllib.request.urlopen(req, timeout=30)
        status = r.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace").strip()
        hint = ERR_HINT.get(e.code, "")
        msg = "NG HTTP %d %s %s" % (e.code, hint, body)
        print("IndexNow:", msg)
        log(msg)
        return False
    except urllib.error.URLError as e:
        msg = "NG 接続失敗: %s" % e.reason
        print("IndexNow:", msg)
        log(msg)
        return False

    if status not in OK_STATUS:
        msg = "NG 想定外のステータス %s" % status
        print("IndexNow:", msg)
        log(msg)
        return False

    msg = "OK %d -> %d URLs submitted" % (status, len(urls))
    print("IndexNow:", msg)
    log("%s | %s" % (msg, " ".join(urls[:5])))
    return True


def main():
    abort, msg = check_key()
    if msg:
        print("IndexNow:", ("送信中止 — " if abort else "") + msg)
        log(("ABORT " if abort else "WARN ") + msg)
    if abort:
        return 1

    urls = sys.argv[1:] or sitemap_urls()
    err = validate(urls)
    if err:
        print("IndexNow: 送信中止 —", err)
        log("ABORT %s" % err)
        return 1

    print("submitting %d urls..." % len(urls))
    return 0 if ping(urls) else 1


if __name__ == "__main__":
    sys.exit(main())
