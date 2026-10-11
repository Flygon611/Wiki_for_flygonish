#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 88×31 小按钮（2010 年代那种站标）。

用法：
    python3 tools/make_buttons.py            # 生成到 assets/buttons/
    python3 tools/make_buttons.py --list     # 只看清单，不生成

想改文字、配色或加按钮，直接改下面 BUTTONS 那张表，然后重跑一次即可。
生成的是 PNG，浏览器标签页/网页里都能直接用。

风格说明：88×31 是那个年代通用的站标尺寸（"小按钮"），
一般带 1px 立体边框 + 渐变底 + 11px 小字。
"""

import argparse
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("需要 Pillow：pip install Pillow")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "assets", "buttons")

W, H = 88, 31

# 字体候选（macOS 上一般都有；找不到会自动退到 PIL 自带位图字体）
CJK_FONTS = ["/System/Library/Fonts/Hiragino Sans GB.ttc",
             "/System/Library/Fonts/STHeiti Light.ttc",
             "/System/Library/Fonts/Supplemental/Songti.ttc",
             "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"]
LATIN_FONTS = ["/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
               "/System/Library/Fonts/Supplemental/Verdana.ttf",
               "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]

INK = (255, 255, 255)
SHADOW = (0, 0, 0)
HILIGHT = (255, 255, 255, 110)
DARKEN = (0, 0, 0, 110)

# ------------------------------------------------------------------ 按钮清单
# name   : 输出文件名
# lines  : 文字（列表 = 多行）
# cjk    : 用中文字体
# top/bot: 渐变底色
# size   : 字号（不填按语言取默认）
BUTTONS = [
    dict(name="见远观星集", lines=["见远观星集"], cjk=True,
         top=(122, 96, 168), bot=(72, 52, 108), size=13, ink=(255, 232, 120)),
    dict(name="SINCE-2010", lines=["SINCE 2010", "手写 HTML"], cjk=True,
         top=(92, 132, 186), bot=(46, 78, 122), size=10),
    dict(name="BEST-VIEWED-1024x768", lines=["BEST VIEWED", "1024 x 768"], cjk=False,
         top=(126, 126, 126), bot=(64, 64, 64), size=9),
    dict(name="NO-FRAME-NO-ADS", lines=["NO FRAME", "NO ADS"], cjk=False,
         top=(176, 108, 64), bot=(112, 60, 28), size=10),
    dict(name="MADE-BY-HAND", lines=["此站由", "人手绘"], cjk=True,
         top=(150, 92, 128), bot=(96, 48, 82), size=11),
    dict(name="POWERED-BY-PYTHON", lines=["POWERED BY", "PYTHON 3"], cjk=False,
         top=(72, 128, 148), bot=(32, 76, 96), size=9),
    dict(name="EST-2010", lines=["EST. 2010"], cjk=False,
         top=(104, 152, 96), bot=(52, 96, 52), size=11),
    dict(name="任何浏览器", lines=["任何浏览器", "都可以看"], cjk=True,
         top=(196, 196, 196), bot=(132, 132, 132), size=11, ink=(24, 24, 24),
         shadow=(255, 255, 255)),
]


def load_font(paths, size):
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:                                  # noqa: BLE001
                continue
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def make(spec):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 渐变底
    for y in range(H):
        d.line([(0, y), (W - 1, y)], fill=lerp(spec["top"], spec["bot"], y / (H - 1)))

    # 1px 立体边框：外圈深色，左上高光，右下暗影
    d.rectangle([0, 0, W - 1, H - 1], outline=(0, 0, 0, 255))
    d.line([(1, 1), (W - 2, 1)], fill=HILIGHT)
    d.line([(1, 1), (1, H - 2)], fill=HILIGHT)
    d.line([(1, H - 2), (W - 2, H - 2)], fill=DARKEN)
    d.line([(W - 2, 1), (W - 2, H - 2)], fill=DARKEN)

    # 居中文字，带 1px 投影
    size = spec.get("size") or (11 if spec.get("cjk") else 10)
    font = load_font(CJK_FONTS if spec.get("cjk") else LATIN_FONTS, size)
    lines = spec["lines"]
    lh = size + 3
    total = lh * len(lines)
    y = (H - total) // 2 + 1
    ink = spec.get("ink", INK)
    shadow = spec.get("shadow", SHADOW)
    for i, text in enumerate(lines):
        bb = d.textbbox((0, 0), text, font=font)
        x = (W - (bb[2] - bb[0])) // 2 - bb[0]
        d.text((x + 1, y + 1), text, font=font, fill=shadow + (255,) if len(shadow) == 3 else shadow)
        d.text((x, y), text, font=font, fill=ink + (255,) if len(ink) == 3 else ink)
        y += lh
    return img


def main():
    ap = argparse.ArgumentParser(description="生成 88x31 小按钮")
    ap.add_argument("--list", action="store_true", help="只列出清单")
    ap.add_argument("--out", default=OUT_DIR)
    args = ap.parse_args()

    if args.list:
        for s in BUTTONS:
            print("  %-26s %s" % (s["name"] + ".png", " / ".join(s["lines"])))
        return
    os.makedirs(args.out, exist_ok=True)
    for spec in BUTTONS:
        img = make(spec)
        path = os.path.join(args.out, spec["name"] + ".png")
        img.save(path, optimize=True)
        print("  %-30s %s" % (os.path.relpath(path, ROOT), "%dx%d" % img.size))
    print("\n共 %d 个按钮 → %s" % (len(BUTTONS), os.path.relpath(args.out, ROOT)))


if __name__ == "__main__":
    main()
