#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CSSが見ている名札（クラス）と、HTML・JSが実際に付ける名札を突き合わせる。

なぜ入れたか（2026-10-03の実事故）:
  トップのスマホメニューを開くと項目の文字が消えていた。黒いヒーローの上では
  ヘッダーの文字を白にしており、それを打ち消すCSSは書いてあったのに、
  CSS側が `.nav.active` を見ていて JS が付けるのは `.nav.open` だった。
  **名札の名前が食い違っても、ブラウザは何のエラーも出さず黙って無視する。**
  だから目でも、他の検査でも見つからず、本番で白地に白のまま残っていた。

何を見るか（この2つだけ。古い未使用CSSは対象にしない＝騒がしくして誰も見なくなるため）:
  A. 名札の取り違え … 同じ要素に掛かる塊（`.nav.open` のような密着した指定）で、
     片方はHTMLに在るのに、もう片方はそのページのHTMLにもJSにも無い。
     誰も付けない名札なので、その規則は一度も当たらない。
  B. 効かない付け外し … JSが付け外ししている名札を見ているCSSが無い。
     付けても見た目が変わらない（JS自身が読み返している場合は除く）。

照合はページ単位で行う:
  ページ内の<style>  → そのページのHTML・JSだけと照合
  /css/*.css        → そのCSSを読み込んでいる全ページのHTML・JSと照合
  （全ページをひとまとめにすると、別ページで使われている同名の名札に
    隠れて取り違えを見逃す。実際この取り違えは `active` が別ページに在ったため
    最初の実装では検出できなかった）

使い方:
    python scripts/class_check.py            # gate.py が自動実行する
    python scripts/class_check.py --list     # 判定の内訳を出す（調整用）
    python scripts/class_check.py <file...>  # 対象を指定（selftest用）

意図して残す名札は scripts/class_allow.json に理由付きで書く。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ALLOW_PATH = os.path.join(HERE, "class_allow.json")

# 検査するページ（対外ページ＝js_check.py と同じ並び＋一覧）
PAGES = ["index.html", "fde/index.html", "en/index.html", "en/fde/index.html",
         "company.html", "check/index.html", "entry.html", "page.html", "legal.html",
         "blog/index.html"]

SKIP_DIRS = {".claude", "node_modules", ".git", "__pycache__"}

JS_SET = re.compile(r"""classList\s*\.\s*(?:add|remove|toggle|replace)\s*\(([^)]*)\)""")
JS_READ = re.compile(r"""(?:classList\s*\.\s*contains|closest|matches|querySelector(?:All)?|getElementsByClassName)\s*\(([^)]*)\)""")
STR_LIT = re.compile(r"""['"]([^'"]*)['"]""")
CLASS_ATTR = re.compile(r"""\bclass\s*=\s*['"]([^'"]*)['"]""", re.I)
CLASS_IN_SEL = re.compile(r"\.(-?[_A-Za-z][\w-]*)")
STYLE_BLOCK = re.compile(r"<style[^>]*>([\s\S]*?)</style>", re.I)
SCRIPT_BLOCK = re.compile(r"<script[^>]*>([\s\S]*?)</script>", re.I)
LINKED_CSS = re.compile(r"""<link[^>]+href\s*=\s*['"]([^'"]+\.css)[^'"]*['"]""", re.I)
CSS_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
CSS_BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
UNIT_SPLIT = re.compile(r"\s*[,>+~]\s*|\s+")
PSEUDO = re.compile(r"::?[\w-]+(\([^)]*\))?")


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


def all_html():
    out = []
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".html"):
                out.append(os.path.join(base, f))
    return out


def classes_from_markup(src):
    """class="a b c" に書かれている名札（JSの文字列の中のmarkupも拾う）。"""
    out = set()
    for m in CLASS_ATTR.finditer(src):
        for tok in m.group(1).split():
            if not tok.startswith("{") and not tok.startswith("$"):
                out.add(tok)
    return out


def classes_from_js(src, pattern):
    """JS が付け外し・参照している名札。querySelector('.a .b') の形も割る。"""
    out = set()
    for block in SCRIPT_BLOCK.findall(src):
        for m in pattern.finditer(block):
            for lit in STR_LIT.findall(m.group(1)):
                if "." in lit or " " in lit or "#" in lit or "[" in lit:
                    out.update(CLASS_IN_SEL.findall(lit))
                elif re.fullmatch(r"-?[_A-Za-z][\w-]*", lit or ""):
                    out.add(lit)
    return out


def selectors_of(css):
    css = CSS_COMMENT.sub(" ", css)
    out = []
    for m in CSS_BLOCK.finditer(css):
        sel = m.group(1).strip()
        if not sel or sel.startswith("@") or sel.endswith("%"):
            continue
        if CLASS_IN_SEL.search(sel):
            out.append(" ".join(sel.split()))
    return out


def units_of(selector):
    """`.header:not(.scrolled) .nav.open a` → [['nav','open']]（同じ要素に掛かる塊だけ）

    :not(.x) は「付いていない」条件なので実在を要求しない＝先に落とす。
    """
    sel = PSEUDO.sub(" ", selector)
    out = []
    for part in UNIT_SPLIT.split(sel):
        names = CLASS_IN_SEL.findall(part)
        if len(names) >= 2:
            out.append(names)
    return out


def css_names_of(css):
    out = set()
    for sel in selectors_of(css):
        out |= set(CLASS_IN_SEL.findall(sel))
    return out


def main(argv):
    show = "--list" in argv
    args = [a for a in argv if not a.startswith("--")]
    pages = args or PAGES

    allow = json.load(io.open(ALLOW_PATH, encoding="utf-8")) if os.path.exists(ALLOW_PATH) else {}
    allowed = set(allow.keys())

    # 全HTMLの使用状況（共有CSSの照合に使う）
    usage, links = {}, {}
    for p in all_html():
        src = read(p)
        usage[p] = (classes_from_markup(src),
                    classes_from_js(src, JS_SET),
                    classes_from_js(src, JS_READ))
        links[p] = set()
        for href in LINKED_CSS.findall(src):
            if not href.startswith("http"):
                links[p].add(os.path.normpath(os.path.join(ROOT, href.split("?")[0].lstrip("/"))))

    def used_of(paths):
        u = set()
        for p in paths:
            m, s, r = usage.get(p, (set(), set(), set()))
            u |= m | s | r
        return u

    # 照合するCSS: (表示名, 中身, そのCSSが効くページ群)
    sources, seen = [], {}
    for rel in pages:
        p = os.path.normpath(os.path.join(ROOT, rel))
        if not os.path.exists(p):
            continue
        src = read(p)
        inline = "\n".join(STYLE_BLOCK.findall(src))
        if inline.strip():
            sources.append((rel + " の<style>", inline, [p]))
        for fp in sorted(links[p]):
            if os.path.exists(fp) and fp not in seen:
                linkers = [q for q in usage if fp in links.get(q, ())]
                seen[fp] = True
                sources.append((os.path.relpath(fp, ROOT).replace("\\", "/"), read(fp), linkers))

    # A: 名札の取り違え
    dead = {}
    for label, css, scope in sources:
        used = used_of(scope)
        markup = set()
        for q in scope:
            markup |= usage.get(q, (set(),))[0]
        for sel in selectors_of(css):
            for names in units_of(sel):
                if not any(n in markup for n in names):
                    continue   # 塊ごと古い規則＝取り違えではないので触らない
                for n in names:
                    if n not in used and n not in allowed:
                        dead.setdefault((n, label), sel)

    # B: 効かない付け外し
    inert = {}
    for rel in pages:
        p = os.path.normpath(os.path.join(ROOT, rel))
        if p not in usage:
            continue
        _, jsset, jsread = usage[p]
        css = "\n".join(STYLE_BLOCK.findall(read(p)))
        names = css_names_of(css)
        for fp in links[p]:
            if os.path.exists(fp):
                names |= css_names_of(read(fp))
        for n in sorted(jsset - names - jsread - allowed):
            inert.setdefault(n, rel)

    if show:
        print("照合したCSS %d 本 / 検査ページ %d" % (len(sources), len(pages)))

    fail = 0
    for (name, label), sel in sorted(dead.items()):
        fail += 1
        print("NG [名札の取り違え] %s: `.%s` をHTMLもJSも付けていない（%s）" % (label, name, sel))
    for name, rel in sorted(inert.items()):
        fail += 1
        print("NG [効かない付け外し] %s: JSが付ける `%s` を見ているCSSが無い" % (rel, name))

    if fail:
        print("NG: CSSとHTML/JSで名札が食い違っている %d 件。"
              "規則を直すか、意図して残すなら scripts/class_allow.json に理由を書く。" % fail)
        return 1
    print("OK: CSSの名札はHTML/JSと一致（検査ページ %d）" % len(pages))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
