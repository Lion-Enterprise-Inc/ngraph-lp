#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""scripts/git_hooks/ のフックを .git/hooks/ へ入れる（gitはフックを配布しないため）。

使い方: python scripts/install_hooks.py
"""
import os, shutil, stat, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(ROOT, "scripts", "git_hooks")
dst_dir = os.path.join(ROOT, ".git", "hooks")
for name in os.listdir(src_dir):
    src, dst = os.path.join(src_dir, name), os.path.join(dst_dir, name)
    shutil.copyfile(src, dst)
    os.chmod(dst, os.stat(dst).st_mode | stat.S_IEXEC)
    print("installed:", dst)
