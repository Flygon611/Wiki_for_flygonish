#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把站点的 content/ 与 assets/ 同步回 Obsidian 库。

用法：
    python3 tools/sync_vault.py            # 同步
    python3 tools/sync_vault.py --dry-run  # 只看会动什么

为什么要这个脚本：
    库里的 .md 是站点内容的镜像，图片放在各自的素材目录里。以前同步是手工做的，
    结果出现过两次漏项——_作品.json 没带过去、以及所有图片都没带过去，
    在 Obsidian 里表现为「找不到 xxx.jpg」。

做三件事：
    1. content/<作品>/ 下的 .md 与 _作品.json → 库
    2. 正文里引用到的每张图 → 库的素材目录
    3. 报告「库里有、但仓库里已经没有」的页面（只报告，不删）

刻意不做的事：
    - 不删库里的任何文件。库里还有 _剧情大纲/、制作提醒/、_补全规范.md 这些
      只在 Obsidian 里存在的资料，删掉就没了。旧文件靠第 3 条报告出来手动处理。
"""

import os
import re
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.expanduser("~/Desktop/工具/Obsidian/NijiboshiStorage")

# 作品： (仓库内容目录, 库目录, 仓库素材目录, 库素材目录)
WORKS = [
    ("想要飞的始祖小鸟", "想要飞的始祖小鸟",
     "assets/想要飞的始祖小鸟", "使用贴图"),
    ("青梅竹马失踪后变成电飞鼠这档事", "幼驯染失踪后变成宝可梦这档事",
     "assets/青梅竹马失踪后变成电飞鼠这档事", "Assets"),
]

# ![[文件名]] 与 <img src="文件名"> 两种引用都算
REF_RE = re.compile(r'!\[\[([^\]|]+)|<img[^>]*src="([^"]+)"')
IMG_EXT = re.compile(r"\.(png|jpe?g|gif|webp)$", re.I)


def referenced_images(content_dir):
    """扫出正文里引用到的所有图片文件名。"""
    names = set()
    for root, _, files in os.walk(content_dir):
        for f in files:
            if not f.endswith(".md"):
                continue
            text = open(os.path.join(root, f), encoding="utf-8").read()
            for m in REF_RE.finditer(text):
                name = (m.group(1) or m.group(2)).strip()
                if IMG_EXT.search(name):
                    names.add(name)
    return names


def sync_work(repo_content, vault_dir, repo_assets, vault_asset_dir, dry):
    src = os.path.join(REPO, "content", repo_content)
    dst = os.path.join(VAULT, vault_dir)
    a_src = os.path.join(REPO, repo_assets)
    a_dst = os.path.join(dst, vault_asset_dir)
    if not os.path.isdir(src):
        print("  跳过（仓库里没有这个作品）:", repo_content)
        return 0, 0, []

    print("── %s → %s" % (repo_content, vault_dir))

    # ① 页面
    n_pages = 0
    want = set()
    for root, _, files in os.walk(src):
        for f in files:
            if not (f.endswith(".md") or f == "_作品.json"):
                continue
            rel = os.path.relpath(os.path.join(root, f), src)
            want.add(rel)
            target = os.path.join(dst, rel)
            data = open(os.path.join(root, f), "rb").read()
            if os.path.isfile(target) and open(target, "rb").read() == data:
                continue
            if not dry:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as fh:
                    fh.write(data)
            n_pages += 1
            if dry:
                print("     [写] %s" % rel)
    print("   页面：更新 %d 个" % n_pages)

    # ② 图片
    need = referenced_images(src)
    if not os.path.isdir(a_dst):
        if not dry:
            os.makedirs(a_dst, exist_ok=True)
        print("   图片：新建素材目录 %s" % a_dst)
    have = {f.lower() for f in os.listdir(a_dst)} if os.path.isdir(a_dst) else set()
    n_img, absent = 0, []
    for name in sorted(need):
        src_img = os.path.join(a_src, name)
        if name.lower() in have:
            continue
        if not os.path.isfile(src_img):
            absent.append(name)
            continue
        if not dry:
            shutil.copy2(src_img, os.path.join(a_dst, name))
        n_img += 1
        if dry:
            print("     [图] %s" % name)
    print("   图片：正文引用 %d 张，补入 %d 张" % (len(need), n_img))
    if absent:
        print("   ⚠ 仓库里也找不到这些图：%s" % "、".join(absent))

    # ③ 报告库里多出来的页面（不删）
    stale = []
    for root, _, files in os.walk(dst):
        for f in files:
            if not f.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(root, f), dst)
            # 只在仓库也有的目录里比对，免得把 _剧情大纲/ 之类误报
            top = rel.split(os.sep)[0]
            if os.path.isdir(os.path.join(src, top)) and rel not in want:
                stale.append(rel)
    if stale:
        print("   · 库里有、仓库里已无（未删，请自行确认）：%s" % "、".join(sorted(stale)))
    return n_pages, n_img, stale


def main():
    dry = "--dry-run" in sys.argv
    if not os.path.isdir(VAULT):
        print("找不到库：%s" % VAULT)
        return 1
    if dry:
        print("（dry-run：只看会动什么，不写盘）\n")
    tp = ti = 0
    for repo_content, vault_dir, repo_assets, vault_asset_dir in WORKS:
        p, i, _ = sync_work(repo_content, vault_dir, repo_assets, vault_asset_dir, dry)
        tp += p
        ti += i
        print()
    print("合计：页面 %d 个、图片 %d 张%s" % (tp, ti, "（dry-run）" if dry else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
