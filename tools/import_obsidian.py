#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 Obsidian 库一次性导入小说笔记到 wiki 的 content/ 与 assets/。

用法：
    python3 tools/import_obsidian.py                 # 预览，不写文件
    python3 tools/import_obsidian.py --write         # 实际导入
    python3 tools/import_obsidian.py --write --force # 覆盖 content/ 里已有页面

说明：
    这是**一次性引导工具**，不是持续同步。导入后 wiki 的内容就以仓库里的
    content/ 为准，之后用编辑器改。重新跑一次会看到差异，但不会自动合并。
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import time

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".avif"}
SKIP_DIR = {".obsidian", ".trash", ".git", ".DS_Store", "assets"}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(base):
    """产出 (相对路径, 绝对路径)，跳过隐藏目录与临时文件。"""
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR and not d.startswith(".")]
        for name in sorted(filenames):
            if name.startswith(".") or name == ".DS_Store":
                continue
            full = os.path.join(dirpath, name)
            yield os.path.relpath(full, base), full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="/Users/nijiboshi06/Desktop/工具/Obsidian/NijiboshiStorage",
                    help="Obsidian 库根目录（其下每个子目录视为一部作品）")
    ap.add_argument("--write", action="store_true", help="真正写入；不加则只预览")
    ap.add_argument("--force", action="store_true", help="覆盖 content/ 中已存在的页面")
    args = ap.parse_args()

    vault = os.path.abspath(os.path.expanduser(args.vault))
    if not os.path.isdir(vault):
        sys.exit("找不到库目录：%s" % vault)

    works = sorted(d for d in os.listdir(vault)
                   if os.path.isdir(os.path.join(vault, d)) and not d.startswith("."))
    if not works:
        sys.exit("库目录下没有作品子目录：%s" % vault)

    print("库目录：%s" % vault)
    print("作品：%s\n" % "、".join(works))

    manifest = {}
    stats = {"pages_new": 0, "pages_skip": 0, "pages_overwrite": 0,
             "images_new": 0, "images_dupe": 0, "stubs": []}
    collisions = []

    for work in works:
        work_src = os.path.join(vault, work)
        seen_images = {}

        for rel, full in walk_files(work_src):
            ext = os.path.splitext(rel)[1].lower()
            base = os.path.basename(rel)

            if ext == ".md":
                dest = os.path.join(ROOT, "content", work, rel)
                exists = os.path.isfile(dest)
                if exists and not args.force:
                    stats["pages_skip"] += 1
                    state = "skip"
                else:
                    stats["pages_new" if not exists else "pages_overwrite"] += 1
                    state = "new" if not exists else "overwrite"
                    if args.write:
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        shutil.copy2(full, dest)
                size = os.path.getsize(full)
                if size == 0:
                    stats["stubs"].append("%s/%s" % (work, rel))
                manifest["content/%s/%s" % (work, rel.replace(os.sep, "/"))] = {
                    "source": full, "sha1": sha1(full), "bytes": size,
                }
                print("  [%s] %s/%s%s" % (state, work, rel, "  (空笔记 → 小作品页)" if size == 0 else ""))

            elif ext in IMAGE_EXT:
                dest_dir = os.path.join(ROOT, "assets", work)
                dest = os.path.join(dest_dir, base)
                if base in seen_images and seen_images[base] != rel:
                    collisions.append("%s：%s 与 %s 同名" % (work, seen_images[base], rel))
                seen_images[base] = rel
                if os.path.isfile(dest) and sha1(dest) == sha1(full):
                    stats["images_dupe"] += 1
                else:
                    stats["images_new"] += 1
                    if args.write:
                        os.makedirs(dest_dir, exist_ok=True)
                        shutil.copy2(full, dest)

                if args.write:
                    key = "assets/%s/%s" % (work, base)
                    manifest[key] = {"source": full, "sha1": sha1(full)}

    print("\n页面：新增 %d / 覆盖 %d / 已存在跳过 %d" %
          (stats["pages_new"], stats["pages_overwrite"], stats["pages_skip"]))
    print("图片：新增 %d / 内容相同跳过 %d" % (stats["images_new"], stats["images_dupe"]))
    if stats["stubs"]:
        print("空笔记（会生成小作品占位页）：%d 篇" % len(stats["stubs"]))
        for s in stats["stubs"]:
            print("    %s" % s)
    if collisions:
        print("\n⚠️  同一作品内图片重名，后面的会覆盖前面的：")
        for c in collisions:
            print("    %s" % c)

    if not args.write:
        print("\n（预览模式，未写入任何文件。加 --write 执行导入。）")
        return

    os.makedirs(os.path.join(ROOT, "content"), exist_ok=True)
    with open(os.path.join(ROOT, "content", ".import-manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"_note": "由 tools/import_obsidian.py 生成，记录页面的 Obsidian 来源与导入时哈希",
                   "_imported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "_vault": vault, "files": manifest}, f, ensure_ascii=False, indent=2)
    print("已写入 content/.import-manifest.json")


if __name__ == "__main__":
    main()
