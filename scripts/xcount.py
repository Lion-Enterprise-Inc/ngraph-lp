#!/usr/bin/env python3
"""X（Twitter）の加重文字数。title_lint.py と x_article.py の共通実装。

2026-08-09新設。朝A型「ChatGPT無料版のテキストチャットが無制限になった——…」を
X Articles に貼ろうとしたら実機で 106/100 と赤字で弾かれた。
Python の len() は59を返していて、それを根拠に「100なら余裕」と報告してしまった。

Xは「全角2・半角1」で数える。len() とは一致しない。
下の範囲だけが1で、それ以外は2（em dash —— は 0x2014 なので1）。
実機の 106/100 表示と一致することを確認済み。

2箇所に同じ式を書くと片方だけ直る事故になるので、必ずここを import すること。
"""

# X Articles のタイトル上限（実機で確認）
X_TITLE_MAX = 100

_LIGHT = ((0x0000, 0x10FF), (0x2000, 0x200D), (0x2010, 0x201F), (0x2032, 0x2037))


def x_weighted_len(s):
    """Xの加重文字数を返す。CJKは2、ラテン・数字・約物（——を含む）は1"""
    return sum(1 if any(a <= ord(c) <= b for a, b in _LIGHT) else 2 for c in s)


def over_by(s, limit=X_TITLE_MAX):
    """上限をどれだけ超えているか（超えていなければ0）"""
    return max(0, x_weighted_len(s) - limit)


def use_utf8_stdio():
    """Windowsのcp932コンソールで日本語の警告が化けるのを防ぐ。

    検査は「NGを出す経路」で読めなければ意味がない
    （anecdote_lint.py が違反検出時にcp932で落ち、3週間気付かれなかった前例がある）。
    """
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
