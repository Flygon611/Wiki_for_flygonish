#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编辑器路径安全自检（不需要启动服务）。

用法：
    python3 tools/check_editor.py

这里固化的是曾经真实存在过的漏洞：/api/upload 的 work 参数没校验，
可以借 `../../..` 把文件写到 assets/ 之外。改动 editor/serve.py 后请跑一遍。
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "editor"))

import serve  # noqa: E402

FAILS = []


def expect_reject(fn, value, label):
    try:
        got = fn(value)
    except ValueError:
        return
    except Exception as e:                                   # noqa: BLE001
        FAILS.append("%s：抛出了意外的 %s: %s（应抛 ValueError）" % (label, type(e).__name__, e))
        return
    FAILS.append("%s：本该拒绝，却接受了并返回 %r" % (label, got))


def expect_accept(fn, value, want, label):
    try:
        got = fn(value)
    except ValueError as e:
        FAILS.append("%s：本该接受，却被拒绝（%s）" % (label, e))
        return
    if got != want:
        FAILS.append("%s：返回 %r，期望 %r" % (label, got, want))


def main():
    print("=== 1. work_segment：作品目录名必须是单层普通目录 ===")
    for bad in ["../../../../tmp/pwn", "..", ".", "/etc", "a/b", "a\\b", ".hidden",
                "D:evil", "  ../../x  ", "/想要飞的始祖小鸟/", "C:/x"]:
        expect_reject(serve.work_segment, bad, "work_segment(%r)" % bad)
    expect_accept(serve.work_segment, "", "", "work_segment('')")
    expect_accept(serve.work_segment, "青梅竹马失踪后变成电飞鼠这档事",
                  "青梅竹马失踪后变成电飞鼠这档事", "work_segment(中文作品名)")
    expect_accept(serve.work_segment, "想要飞的始祖小鸟/", "想要飞的始祖小鸟",
                  "work_segment(只有尾部斜杠)")

    print("=== 2. content_path：只能落在 content/ 内的 .md ===")
    for bad in ["../x.md", "../../etc/passwd.md", "a/../../b.md", "/etc/passwd.md",
                "人物/../../../x.md", "C:/x.md", "", "a/b.txt", "./x.md"]:
        expect_reject(serve.content_path, bad, "content_path(%r)" % bad)
    ok = serve.content_path("青梅竹马失踪后变成电飞鼠这档事/人物/上鹈.md")
    if not serve._within(ok, serve.CONTENT):
        FAILS.append("content_path：正常中文路径没有落在 content/ 内")

    print("=== 3. _within：docs 与 docs_backup 不能混为一谈 ===")
    base = serve.DOCS
    if not serve._within(os.path.join(base, "index.html"), base):
        FAILS.append("_within：正常子文件被判为越界")
    if not serve._within(base, base):
        FAILS.append("_within：目录自身被判为越界")
    if serve._within(base + "_backup/secret.html", base):
        FAILS.append("_within：同前缀的旁路目录（docs_backup）被判为在 docs 内")
    if serve._within(os.path.dirname(base), base):
        FAILS.append("_within：父目录被判为在 docs 内")

    print("=== 4. 上传落点必须始终在 assets/ 内 ===")
    # 复现原始漏洞：合法校验后，任何 work 值都不能让落点跑出 assets/
    for work in ["", "想要飞的始祖小鸟", "青梅竹马失踪后变成电飞鼠这档事"]:
        w = serve.work_segment(work)
        dest_dir = os.path.join(serve.ASSETS, w) if w else serve.ASSETS
        if not serve._within(dest_dir, serve.ASSETS):
            FAILS.append("上传目录越界：work=%r → %s" % (work, dest_dir))

    print()
    if FAILS:
        print("❌ 有 %d 项未通过：" % len(FAILS))
        for f in FAILS:
            print("   - " + f)
        return 1
    print("✅ 路径安全校验全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
