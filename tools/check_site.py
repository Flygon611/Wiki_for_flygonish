#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站内链接自检：扫描 docs/ 下所有 HTML，验证每个 href/src 是否真的存在。

用法：
    python3 tools/check_site.py            # 检查
    python3 tools/check_site.py --list     # 顺便列出所有页面

会检查：
    * 站内相对链接（页面 / 图片 / css / js）是否指向存在的文件
    * 百分号编码的中文路径能否还原
    * 页面里是否有空标题、未替换的占位符
外部链接（http/https）只统计数量，不发请求。
"""

import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTR_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]*)"', re.I)
DATA_INDEX_RE = re.compile(r'data-index\s*=\s*"([^"]*)"', re.I)

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}
KNOWN_TAGS = ({"html", "head", "body", "title", "style", "script", "div", "span", "p",
               "a", "ul", "ol", "li", "table", "thead", "tbody", "tr", "th", "td",
               "h1", "h2", "h3", "h4", "h5", "h6", "aside", "nav", "article", "footer",
               "header", "main", "section", "figure", "figcaption", "center", "details",
               "summary", "blockquote", "code", "mark", "b", "i", "s", "em", "strong",
               "del", "dl", "dt", "dd", "pre", "form", "button", "label", "select",
               "option", "datalist", "textarea", "small", "sub", "sup", "hr", "br"}) | VOID_TAGS


class BalanceChecker(HTMLParser):
    """检查标签是否配平。只看已知标签，避免把正文里的 `->`、`<3` 当成标签。"""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag in KNOWN_TAGS and tag not in VOID_TAGS:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag not in KNOWN_TAGS or tag in VOID_TAGS:
            return
        line = self.getpos()[0]
        names = [t for t, _ in self.stack]
        if not self.stack:
            self.problems.append("第 %d 行：多余的 </%s>" % (line, tag))
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        if tag in names:
            idx = len(names) - 1 - names[::-1].index(tag)
            unclosed = [t for t, _ in self.stack[idx + 1:]]
            self.problems.append("第 %d 行：</%s> 错位，未闭合 %s" % (line, tag, unclosed))
            del self.stack[idx:]
        else:
            self.problems.append("第 %d 行：多余的 </%s>" % (line, tag))


def check_tag_balance(docs):
    bad, n = [], 0
    for dirpath, dirnames, filenames in os.walk(docs):
        for name in filenames:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            n += 1
            with open(full, encoding="utf-8") as f:
                html = f.read()
            p = BalanceChecker()
            try:
                p.feed(html)
                p.close()
            except Exception as e:                              # noqa: BLE001
                bad.append((os.path.relpath(full, docs), "解析失败：%s" % e))
                continue
            rel = os.path.relpath(full, docs).replace(os.sep, "/")
            for msg in p.problems:
                bad.append((rel, msg))
            if p.stack:
                bad.append((rel, "文末仍未闭合：" + str([t for t, _ in p.stack])))
    print("标签配平：扫描 %d 个 HTML%s" % (n, "" if not bad else "，发现不配平"))
    return bad


def check_search_links(docs):
    """检查顶部即时搜索的候选链接。

    这些 href 是 theme.js 在运行时用 search.json 里的「相对站点根」路径拼出来的，
    静态扫 HTML 看不到。深层页面必须补上回到根目录的前缀，否则点结果会 404。
    """
    index_path = os.path.join(docs, "search.json")
    if not os.path.isfile(index_path):
        return []
    with open(index_path, encoding="utf-8") as f:
        try:
            items = json.load(f)
        except ValueError as e:
            return [("<search.json>", "不是合法 JSON：%s" % e)]
    bad, checked, n_pages = [], 0, 0
    for dirpath, dirnames, filenames in os.walk(docs):
        for name in filenames:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8") as f:
                html = f.read()
            m = DATA_INDEX_RE.search(html)
            if not m:
                continue
            n_pages += 1
            prefix = re.sub(r"search\.json.*$", "", m.group(1))
            rel_page = os.path.relpath(full, docs).replace(os.sep, "/")
            for it in items:
                checked += 1
                target = os.path.normpath(os.path.join(dirpath, unquote(prefix + it.get("u", ""))))
                if not os.path.exists(target):
                    bad.append((rel_page, "搜索候选 %s → %s" % (it.get("t"), prefix + it.get("u", ""))))
                    break
    print("搜索候选链接：在 %d 个带搜索框的页面上校验了 %d 条引用%s"
          % (n_pages, checked, "" if not bad else "，其中有问题"))
    return bad


def check_theme_js(docs):
    """源码级防线：顶部搜索必须给候选链接补「回到站点根」的前缀。

    这一条静态扫 HTML 抓不到——href 是 theme.js 运行时拼的，
    一旦有人把前缀去掉，深层页面点搜索结果就会 404。"""
    path = os.path.join(docs, "assets", "theme.js")
    if not os.path.isfile(path):
        return [("<assets/theme.js>", "找不到 theme.js")]
    with open(path, encoding="utf-8") as f:
        js = f.read()
    if "basePrefix" not in js:
        return [("<assets/theme.js>",
                 "顶部搜索未给候选链接补『回到站点根』的前缀（basePrefix），"
                 "深层页面点搜索结果会跳到不存在的地址")]
    # 光有变量名不够，必须确实是从 data-index 推导出来的，而不是赋成了别的值
    if not re.search(r"basePrefix\s*=\s*indexUrl\b[^;]{0,200}replace\(", js):
        return [("<assets/theme.js>",
                 "顶部搜索的 basePrefix 不是从 data-index 推导出来的，"
                 "深层页面的搜索结果链接会是错的")]
    return []


def check(docs, list_pages=False):
    broken, external, checked = [], set(), 0
    pages = []
    for dirpath, dirnames, filenames in os.walk(docs):
        for name in filenames:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            rel_page = os.path.relpath(full, docs).replace(os.sep, "/")
            pages.append(rel_page)
            with open(full, encoding="utf-8") as f:
                html = f.read()
            if "{{" in html or "%(" in html:
                broken.append((rel_page, "<未替换的模板占位符>"))
            if "<h1 class=\"page-title\"></h1>" in html:
                broken.append((rel_page, "<空的一级标题>"))
            for raw in ATTR_RE.findall(html):
                if not raw or raw.startswith(("#", "mailto:", "javascript:", "data:")):
                    continue
                split = urlsplit(raw)
                if split.scheme in ("http", "https"):
                    external.add(split.scheme + "://" + split.netloc)
                    continue
                if split.scheme:
                    continue
                path = unquote(split.path)
                if not path:
                    continue
                base = os.path.dirname(full)
                target = os.path.normpath(os.path.join(base, path))
                checked += 1
                if path.endswith("/"):
                    target = os.path.join(target, "index.html")
                if not os.path.exists(target):
                    broken.append((rel_page, raw))
    print("检查页面 %d 个，静态站内引用 %d 处，外部站点 %d 个"
          % (len(pages), checked, len(external)))
    if external:
        print("外部链接域名：%s" % "、".join(sorted(external)))
    broken += check_search_links(docs)
    broken += check_theme_js(docs)
    broken += check_tag_balance(docs)
    if broken:
        print("\n❌ 有 %d 处引用指向不存在的文件：" % len(broken))
        for page, ref in broken[:60]:
            print("   %s  ->  %s" % (page, ref))
        if len(broken) > 60:
            print("   …还有 %d 处" % (len(broken) - 60))
    else:
        print("\n✅ 所有站内链接、图片、样式与脚本都存在。")
    if list_pages:
        print("\n页面清单：")
        for p in sorted(pages):
            print("   " + p)
    return 1 if broken else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--list", action="store_true", help="列出所有页面")
    args = ap.parse_args()
    if not os.path.isdir(args.docs):
        sys.exit("找不到输出目录：%s（先跑 python3 build.py）" % args.docs)
    sys.exit(check(args.docs, args.list))


if __name__ == "__main__":
    main()
