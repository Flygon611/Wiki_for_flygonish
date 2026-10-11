#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nijiboshi-wiki 静态站点生成器。

把 content/ 下的 Obsidian 风格 Markdown 编译成 docs/ 下的静态 wiki，
可直接用 GitHub Pages 发布（Pages 源选 main 分支 /docs 目录即可）。

用法：
    python3 build.py              # 生成到 docs/
    python3 build.py --open       # 生成后启动本地预览并打开浏览器
    python3 build.py --port 8123  # 指定预览端口
    python3 build.py --quiet      # 只输出摘要

只依赖 Python 3.8+ 标准库，无需安装任何东西。
"""

import argparse
import datetime
import hashlib
import html as _html
import json
import os
import posixpath
import re
import shutil
import sys
import time
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from wikicore import pages as P                                    # noqa: E402
from wikicore.markdown import Renderer, Resolver, wrap_spoilers     # noqa: E402

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


# ------------------------------------------------------------------ 工具

def log(msg, quiet=False):
    if not quiet:
        print(msg)


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path, text):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def url_of(out_path):
    return quote(out_path, safe="/-_.~!$&'()*+,;=:@") if out_path else ""


def rel_to(base_dir, out_path):
    """从 base_dir（相对 docs/）指向 out_path 的相对 URL。"""
    rp = posixpath.relpath(out_path, base_dir) if base_dir else out_path
    return quote(rp, safe="/-_.~!$&'()*+,;=:@")


def tag_filename(tag):
    """标签 → 文件名片段（落盘与 href 解码后的名字必须是同一份字符串）。"""
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(tag)).strip().strip(".")
    return s or "_"


def build_tag_map(all_tags):
    """标签 → 文件名。返回 (mapping, collisions)。

    归一化会把不同标签映射到同一个名字（`a/b`、`a_b`、`a:b` 都是 `a_b`），
    而 `index` 是标签总览页的保留名，超长名字还会撞文件名长度上限。
    这些都会让标签页互相覆盖且不自检报错，所以在这里统一加上短哈希让开。
    """
    mapping, taken, collisions = {}, {}, []
    for tag in sorted({str(t) for t in all_tags}):
        base = tag_filename(tag)
        if len(base) > 60:                      # 文件系统单段上限 255 字节，中文一个字 3 字节
            base = base[:60].rstrip(".")
        cand = base
        need = cand.lower() == "index" or cand.lower() in taken
        if need:
            h = hashlib.sha1(tag.encode("utf-8")).hexdigest()[:6]
            cand = "%s-%s" % (base[:50], h)
            while cand.lower() in taken:
                cand += "x"
            collisions.append((tag, base, cand))
        taken[cand.lower()] = tag
        mapping[tag] = cand
    return mapping, collisions


# 站点自带页面的输出名，顶层页面不能和它们抢
RESERVED_ROOT = {"index.html", "all.html", "recent.html", "missing.html",
                 "special.html", "search.html", "random.html", "404.html"}
RESERVED_DIRS = {"tags", "assets"}


def prefix_for(out_path):
    """从 docs/ 下某个输出文件回到 docs/ 根的相对前缀（'' / '../' / '../../'）。"""
    d = posixpath.dirname(out_path)
    return "../" * len([x for x in d.split("/") if x]) if d else ""


def shade(hex_color, factor):
    """把十六进制颜色调亮/调暗，factor<1 变暗。用于每个作品的配色调。"""
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return hex_color
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hex_color
    if factor < 1:
        r, g, b = (int(c * factor) for c in (r, g, b))
    else:
        r, g, b = (int(c + (255 - c) * (factor - 1)) for c in (r, g, b))
    return "#%02x%02x%02x" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def parse_frontmatter(text):
    """极简 YAML：只认 key: value 与 key: [a, b]。返回 (meta, 正文)。"""
    m = FM_RE.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            meta[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        elif v in ("true", "yes", "on"):
            meta[k] = True
        elif v in ("false", "no", "off"):
            meta[k] = False
        else:
            meta[k] = v.strip("'\"")
    return meta, text[m.end():]


def plain_excerpt(body_html, limit=220):
    h = re.sub(r'<aside class="infobox">.*?</aside>', " ", body_html, flags=re.S)
    h = re.sub(r"<details.*?</details>", " ", h, flags=re.S)
    h = re.sub(r'<span class="anchor">.*?</span>', "", h, flags=re.S)
    h = re.sub(r'<span class="callout-label">.*?</span>', "", h, flags=re.S)   # 别把「信息」这类标签混进摘要
    h = re.sub(r"<[^>]+>", " ", h)
    h = _html.unescape(h)
    h = re.sub(r"\s+", " ", h).strip()
    if not h:
        # 正文为空（内容全在信息框里）时退回用信息框的文字，字段之间补个分隔符
        h = re.sub(r'<aside class="infobox">(.*?)</aside>', _infobox_text, body_html, flags=re.S)
        h = re.sub(r"<[^>]+>", " ", h)
        h = re.sub(r"\s+", " ", _html.unescape(h)).strip()
    return h[:limit]


def _infobox_text(m):
    """把信息框表格的每一行拼成「字段：值」形式，便于当摘要用。"""
    inner = m.group(1)
    inner = re.sub(r"</tr>", " · ", inner)
    inner = re.sub(r"</th>", "：", inner)
    inner = re.sub(r"</td>", "", inner)
    inner = re.sub(r"</(table|div)>", " ", inner)
    return inner


# ------------------------------------------------------------------ 数据模型

class Category:
    def __init__(self, work, path):
        self.work = work
        self.path = path
        self.name = path.split("/")[-1]
        self.parent = path.rsplit("/", 1)[0] if "/" in path else None
        self.pages = []
        self.children = []
        self.out_path = "%s/%s/index.html" % (work.dirname, path)

    @property
    def title(self):
        cn = self.work.category_names
        return cn.get(self.path) or cn.get(self.name) or self.name

    @property
    def url(self):
        return url_of(self.out_path)


class Work:
    def __init__(self, dirname, meta):
        self.dirname = dirname
        self.meta = meta or {}
        self.pages = []
        self.categories = {}

    def get(self, key, default=""):
        v = self.meta.get(key, default)
        return v if v not in (None, "") else default

    @property
    def title(self):
        return self.get("title", self.dirname)

    @property
    def nav_label(self):
        return self.get("nav_label", self.get("short", self.title))

    @property
    def tagline(self):
        return self.get("tagline", "")

    @property
    def description(self):
        return self.get("description", "")

    @property
    def accent(self):
        return self.get("accent", "")

    @property
    def category_names(self):
        return self.meta.get("category_names", {}) or {}

    @property
    def order_map(self):
        return {name: i for i, name in enumerate(self.meta.get("category_order", []) or [])}

    @property
    def out_path(self):
        return "%s/index.html" % self.dirname

    @property
    def url(self):
        return url_of(self.out_path)

    def sorted_categories(self):
        om = self.order_map
        return sorted(self.categories.values(),
                      key=lambda c: (om.get(c.path, om.get(c.name, 99)), c.path))


class Page:
    def __init__(self, abs_path, rel):
        self.abs = abs_path
        self.rel = rel
        self.name = posixpath.basename(rel)[:-3]
        parts = rel.split("/")
        if len(parts) == 1:
            self.work = None
            self.category = ""
        else:
            self.work = parts[0]
            self.category = "/".join(parts[1:-1])
        self.meta = {}
        self.title = self.name
        self.is_home = False          # 只有 content/首页.md 会被置为 True
        self.tags = []
        self.aliases = []
        self.spoiler_flag = None
        self.is_stub = False
        self.body_html = ""
        self.headings = []
        self.has_spoiler = False
        self.links_out = set()
        self.missing_links = set()
        self.warnings = []
        self.mtime = 0

    @property
    def is_global(self):
        """顶层页面（不在任何作品目录里），例如首页。"""
        return self.work is None

    @property
    def out_path(self):
        if self.is_home:
            return "index.html"
        if self.work is None:
            # 其他顶层页面：生成到 docs/<名字>.html，别让它们消失
            return "%s.html" % self.name
        cat = (self.category + "/") if self.category else ""
        return "%s/%s%s.html" % (self.work, cat, self.name)

    @property
    def url(self):
        return url_of(self.out_path)

    @property
    def category_title(self):
        return self.category.split("/")[-1] if self.category else ""


# ------------------------------------------------------------------ 载入

DEFAULT_CONFIG = {
    "site_name": "我的维基",
    "site_tagline": "",
    "about": "",
    "language": "zh-CN",
    "content_dir": "content",
    "assets_dir": "assets",
    "output_dir": "docs",
    "soft_breaks": "br",
    "theme": {},
    "footer": "",
    "repo": {},
    "extra_nav": [],
    "infobox_callouts": ["info", "note", "abstract", "summary", "example"],
    "spoiler": {"fold_headings": [], "banner_text": "本页内容包含剧情透露。"},
}


def load_config(root):
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = os.path.join(root, "wiki.config.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def load_pages(root, cfg, verbose=False):
    content_dir = os.path.join(root, cfg["content_dir"])
    if not os.path.isdir(content_dir):
        sys.exit("找不到内容目录：%s" % content_dir)

    works, pages, home = {}, [], None
    HOME_NAMES = ("首页.md", "index.md")
    root_pages = []
    for dirpath, dirnames, filenames in os.walk(content_dir):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.endswith(".md") or name.startswith("."):
                continue
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, content_dir).replace(os.sep, "/")
            page = Page(abs_path, rel)
            page.mtime = os.path.getmtime(abs_path)
            if page.work is None and name in HOME_NAMES:
                if home is not None:
                    sys.exit("content/ 下同时存在 %s 和 %s，请只留一个作为首页"
                             % (home.rel, rel))
                page.is_home = True
                home = page
            else:
                if page.work is None:
                    root_pages.append(page)
                pages.append(page)

    for dirpath, dirnames, filenames in os.walk(content_dir):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        if "_作品.json" in filenames:
            wd = os.path.relpath(dirpath, content_dir).replace(os.sep, "/")
            with open(os.path.join(dirpath, "_作品.json"), encoding="utf-8") as f:
                works[wd] = Work(wd, json.load(f))

    for p in pages:
        if p.work is None:
            continue                      # 顶层页面不属于任何作品
        w = works.setdefault(p.work, Work(p.work, {}))
        w.pages.append(p)
        if p.category:
            w.categories.setdefault(p.category, Category(w, p.category)).pages.append(p)

    for w in works.values():
        for path in list(w.categories):
            if "/" in path:
                w.categories.setdefault(path.rsplit("/", 1)[0], Category(w, path.rsplit("/", 1)[0]))
        for cat in w.categories.values():
            if cat.parent and cat.parent in w.categories:
                w.categories[cat.parent].children.append(cat)

    if home is None:
        sys.exit("content/ 下缺少首页文件（content/首页.md）")
    # 顶层页面会生成到站点根目录，撞上站点自带页面就会被静默覆盖
    for p in root_pages:
        name = os.path.basename(p.out_path)
        if name.lower() in RESERVED_ROOT:
            sys.exit("content/%s 会生成成 %s，和站点自带的页面撞名（会被覆盖），请改个名字。"
                     % (p.rel, p.out_path))
    for wd in works:
        if wd.lower() in RESERVED_DIRS:
            sys.exit("作品目录名 %r 与站点自带目录（%s）冲突，请改名。"
                     % (wd, "、".join(sorted(RESERVED_DIRS))))
    if root_pages and verbose:
        print("提示：content/ 顶层另有 %d 个页面，会生成到站点根目录：%s"
              % (len(root_pages), "、".join(p.name for p in root_pages)))
    return works, pages, home


def build_indexes(root, cfg, pages):
    by_name = {}
    for p in pages:
        by_name.setdefault(p.name, []).append(p)
        for a in p.aliases:
            by_name.setdefault(a, []).append(p)
    images = {}
    assets_dir = os.path.join(root, cfg["assets_dir"])
    for dirpath, dirnames, filenames in os.walk(assets_dir):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            images.setdefault(name, []).append(rel)
    return by_name, images


# ------------------------------------------------------------------ 渲染

def load_page_source(p):
    """解析 frontmatter，填充标题 / 标签 / 别名。"""
    meta, body = parse_frontmatter(read_text(p.abs))
    p.meta = meta
    p.title = str(meta.get("标题") or meta.get("title") or p.name)
    tags = meta.get("标签", meta.get("tags", []))
    p.tags = [str(x) for x in ([tags] if isinstance(tags, str) else tags)]
    aliases = meta.get("别名", meta.get("aliases", []))
    p.aliases = [str(x) for x in ([aliases] if isinstance(aliases, str) else aliases)]
    p.spoiler_flag = meta.get("剧透", meta.get("spoiler"))
    p.is_stub = len(body.strip()) < 30
    return body


def render_body(p, body, resolver, cfg):
    r = Renderer(resolver, cfg, current=p)
    html = r.render(body)
    if not body.strip():
        html = ('<div class="stub-notice">这个页面还没有内容。在编辑器的「新建 / 编辑页面」里打开 '
                '<b>%s</b> 就能开始写设定了。</div>' % _html.escape(p.rel))
    html, folded = wrap_spoilers(html, r.headings)
    p.body_html = html
    p.headings = r.headings
    p.has_spoiler = folded or bool(p.spoiler_flag)
    p.links_out = r.links_out
    p.missing_links = r.missing_links
    p.warnings = r.warnings


# ------------------------------------------------------------------ 站点外壳

def build_nav(cfg, works):
    nav = [("首页", "index.html", "home")]
    for w in sorted(works.values(), key=lambda x: x.get("order", 0)):
        nav.append((w.nav_label, w.out_path, w.dirname))
    nav += [("所有页面", "all.html", "all"),
            ("最近更新", "recent.html", "recent"),
            ("随机页面", "random.html", "random"),
            ("特殊页面", "special.html", "special")]
    for extra in cfg.get("extra_nav", []):
        nav.append((extra.get("label", "链接"), extra.get("url", "#"), extra.get("key", extra.get("url", ""))))
    return nav


def make_sidebar(cfg, works, nav_active, current_page, backlinks, total_pages):
    boxes = [{"title": "导航", "items": [
        ("首页", "index.html", "", nav_active == "home"),
        ("所有页面", "all.html", str(total_pages), nav_active == "all"),
        ("最近更新", "recent.html", "", nav_active == "recent"),
        ("随机页面", "random.html", "", nav_active == "random"),
        ("特殊页面", "special.html", "", nav_active == "special"),
        ("未完成的页面", "missing.html", "", nav_active == "missing"),
    ]}]
    for w in sorted(works.values(), key=lambda x: x.get("order", 0)):
        items = []
        for cat in w.sorted_categories():
            if cat.parent:
                continue
            total = len(cat.pages) + sum(len(c.pages) for c in cat.children)
            items.append((cat.title, cat.out_path, str(total),
                          bool(current_page) and current_page.work == w.dirname))
            for child in sorted(cat.children, key=lambda c: c.name):
                items.append(("　└ " + child.title, child.out_path, str(len(child.pages)), False))
        boxes.append({"title": w.title, "href": w.out_path, "items": items, "key": w.dirname})
    tools = []
    if current_page is not None:
        tools.append(("链入本页", "#backlinks", str(len(backlinks.get(current_page.rel, []))), False))
    tools += [("搜索", "search.html", "", False),
              ("全部图片", "special.html#media", "", False)]
    boxes.append({"title": "工具", "items": tools})
    about = _html.escape(cfg.get("about", "")).replace("\n", "<br>")
    if cfg.get("repo", {}).get("url"):
        about += '<br><a href="%s" target="_blank" rel="noopener">GitHub 仓库</a>' % cfg["repo"]["url"]
    boxes.append({"title": "关于", "html": '<div class="box-body">%s</div>' % about})
    return boxes


def page_banner(page, cfg, works):
    if not page.has_spoiler:
        return ""
    w = works.get(page.work)
    text = (w.meta.get("spoiler_banner_text") if w else None) or \
        cfg.get("spoiler", {}).get("banner_text", "本页包含剧情透露。")
    return P.spoiler_banner(_html.escape(str(text)))


def work_accent_css(w):
    """按作品配色调生成 <style> 覆盖片段（信息框、页头渐变都会跟着变）。"""
    if not w or not w.accent:
        return ""
    return ("<style>:root{--accent:%s;--accent-2:%s;--accent-3:%s}</style>"
            % (w.accent, shade(w.accent, 0.68), shade(w.accent, 1.45)))


def catlinks_for(page, cfg, works, prefix="", tag_map=None):
    links = []
    w = works.get(page.work)
    if page.work is None and not page.is_home:
        links.append(("总览", prefix + "index.html"))
    if w:
        links.append((w.title, prefix + w.url))
        cat = w.categories.get(page.category)
        if cat:
            links.append((cat.title, prefix + cat.url))
    tag_map = tag_map or {}
    for tag in page.tags:
        name = tag_map.get(tag) or tag_filename(tag)
        links.append((tag, prefix + "tags/%s.html" % quote(name, safe="")))
    return P.catlinks_html(links)


def backlinks_box(page, backlinks, base_dir):
    items = []
    seen = set()
    for b in backlinks.get(page.rel, []):
        if b.rel in seen:
            continue
        seen.add(b.rel)
        items.append((b.title, rel_to(base_dir, b.out_path)))
    return P.backlinks_html(items)


# ------------------------------------------------------------------ 主流程

def build(root, cfg, quiet=False):
    out_dir = os.path.join(root, cfg["output_dir"])
    works, pages, home = load_pages(root, cfg, verbose=not quiet)

    home_body = load_page_source(home)
    all_pages = pages + [home]

    # 先解析全部 frontmatter，再建索引（别名要参与链接解析）
    bodies = {}
    for p in pages:
        bodies[p.rel] = load_page_source(p)

    by_name, images = build_indexes(root, cfg, all_pages)
    resolver = Resolver(by_name, images)

    warn = 0
    for p in pages:
        render_body(p, bodies[p.rel], resolver, cfg)
        warn += len(p.warnings)
    render_body(home, home_body, resolver, cfg)

    # 反向链接
    backlinks = {p.rel: [] for p in all_pages}
    by_rel_name = {}
    for p in all_pages:
        by_rel_name.setdefault(p.name, []).append(p)
    for p in all_pages:
        for target in p.links_out:
            cands = by_rel_name.get(target, [])
            if not cands:
                continue
            pick = next((c for c in cands if c.work == p.work), cands[0])
            if pick.rel != p.rel:
                backlinks[pick.rel].append(p)

    # 标签 → 文件名，在这里定一次，供分类条和标签页共用（避免两边算出不同的名字）
    tag_map, tag_collisions = build_tag_map([t for x in all_pages for t in x.tags])
    if tag_collisions:
        log("提示：以下标签归一化后重名，已自动加后缀区分：", quiet)
        for tag, base, fixed in tag_collisions:
            log("    %s（%s）→ %s" % (tag, base, fixed), quiet)

    nav = build_nav(cfg, works)
    total_images = sum(len(v) for v in images.values())
    stats = "共 %d 个页面 · %d 张图片 · 生成于 %s" % (
        len(all_pages), total_images, time.strftime("%Y-%m-%d %H:%M"))

    site = P.Site(cfg, nav, [])

    if os.path.isdir(out_dir):
        for name in os.listdir(out_dir):
            if name == ".git":
                continue
            path = os.path.join(out_dir, name)
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
    os.makedirs(out_dir, exist_ok=True)

    def emit(out_path, html):
        write_text(os.path.join(out_dir, out_path.replace("/", os.sep)), html)

    def render_shell(page, nav_active, *, titleblock=None, body=None, description="",
                     top_extra="", with_tabs=True, catlinks=None, blinks=None):
        base_dir = posixpath.dirname(page.out_path) if page is not None else ""
        site.sidebar_boxes = make_sidebar(cfg, works, nav_active, page, backlinks, len(all_pages))
        head_extra = work_accent_css(works.get(page.work)) if page is not None else ""
        return P.render_layout(
            site,
            title="%s - %s" % (page.title if page else nav_active, site.name),
            body=body if body is not None else (P.toc_html(page.headings, page.has_spoiler) + "\n" + page.body_html),
            rel=prefix_for(page.out_path) if page is not None else "",
            current_page=page,
            head_extra=head_extra,
            titleblock=titleblock if titleblock is not None else P.page_title_block(
                _html.escape(page.title),
                [w.title for w in works.values() if w.dirname == page.work] if page and page.work else None),
            catlinks=catlinks if catlinks is not None else (
                catlinks_for(page, cfg, works, prefix_for(page.out_path), tag_map)
                if page else ""),
            backlinks=blinks if blinks is not None else (backlinks_box(page, backlinks, base_dir) if page else ""),
            nav_active=nav_active,
            sidebar_active=(page.work or "") if page else "",
            banner=page_banner(page, cfg, works) if page else "",
            stats_line=stats,
            description=description or (plain_excerpt(page.body_html, 150) if page else ""),
            top_extra=top_extra,
            page_tabs=None if with_tabs else '<span class="tab active">页面</span>',
        )

    # ---- 普通条目 ----
    for page in pages:
        emit(page.out_path, render_shell(page, page.work or ""))

    # ---- 首页 ----
    home_tb = ('<h1 class="page-title">%s</h1><div class="page-subtitle">%s</div>'
               % (_html.escape(site.name), _html.escape(site.tagline)))
    site.sidebar_boxes = make_sidebar(cfg, works, "home", home, backlinks, len(all_pages))
    emit("index.html", P.render_layout(
        site, title=site.name,        # 首页标题直接用站名，不必写成「首页 - 站名」
        body=(P.toc_html(home.headings, home.has_spoiler) + "\n" + home.body_html),
        rel="", current_page=home, titleblock=home_tb, nav_active="home",
        catlinks="", backlinks="", banner=page_banner(home, cfg, works),
        stats_line=stats,
        description="%s —— %s" % (site.tagline, cfg.get("about", ""))))

    # ---- 作品门户 ----
    for w in works.values():
        emit(w.out_path, portal_html(cfg, works, w, site, make_sidebar, backlinks,
                                     len(all_pages), stats))

    # ---- 分类页 ----
    for w in works.values():
        for cat in w.categories.values():
            base_dir = posixpath.dirname(cat.out_path)
            blocks = []
            if cat.children:
                blocks.append("<h2>子分类</h2>")
                blocks.append("".join(
                    '<a class="chip" href="%s">%s <span style="color:#7b8794">%d</span></a>'
                    % (rel_to(base_dir, c.out_path), _html.escape(c.title), len(c.pages))
                    for c in sorted(cat.children, key=lambda c: c.name)))
            if cat.pages:
                blocks.append("<h2>条目</h2><div class=\"list-grid\">")
                blocks.append("".join(
                    '<div class="card"><h4><a href="%s">%s</a></h4><p>%s</p></div>'
                    % (rel_to(base_dir, p.out_path), _html.escape(p.title),
                       _html.escape(plain_excerpt(p.body_html, 120) or "（小作品，待补充）"))
                    for p in sorted(cat.pages, key=lambda p: -p.mtime)))
                blocks.append("</div>")
            if not blocks:
                blocks.append('<p class="hit-count">这个分类下还没有条目。</p>')
            site.sidebar_boxes = make_sidebar(cfg, works, w.dirname, None, backlinks, len(all_pages))
            emit(cat.out_path, P.render_layout(
                site, title="分类：%s - %s" % (cat.title, site.name),
                body="".join(blocks), rel=prefix_for(cat.out_path), current_page=None,
                nav_active=w.dirname, head_extra=work_accent_css(w),
                titleblock=P.page_title_block("分类：%s" % _html.escape(cat.title),
                                              ["%s › %s" % (w.title, cat.path),
                                               "%d 个条目" % len(cat.pages)]),
                stats_line=stats))

    write_list_pages(root, cfg, works, pages, home, all_pages, site, make_sidebar,
                     backlinks, stats, out_dir)
    write_tag_pages(cfg, works, all_pages, site, make_sidebar, backlinks, stats,
                    out_dir, tag_map)
    write_assets(root, cfg, out_dir)
    write_search_index(cfg, works, all_pages, out_dir)
    report(root, cfg, works, pages, all_pages, by_name, images, backlinks, warn, quiet)
    return len(all_pages)


def write_tag_pages(cfg, works, all_pages, site, make_sidebar, backlinks, stats,
                    out_dir, tag_map=None):
    """frontmatter 里写了「标签: [a, b]」的页面，会生成 tags/<标签>.html 供分类条链接。"""
    tags = {}
    for p in all_pages:
        for tag in p.tags:
            tags.setdefault(tag, []).append(p)
    if not tags:
        return
    tag_map = tag_map or build_tag_map(list(tags))[0]
    # 构建期断言：每个标签必须有自己的、不占用保留名的页面。
    # 归一化碰撞曾让多个标签共用一个文件，而 check_site.py 只查文件是否存在，测不出来。
    seen = {}
    for tag in tags:
        name = tag_map.get(tag) or tag_filename(tag)
        if name.lower() == "index":
            sys.exit("标签 %r 的文件名占用了 tags/index.html（标签总览页）" % tag)
        if name.lower() in seen:
            sys.exit("标签 %r 与 %r 的文件名撞车（都是 %s）" % (tag, seen[name.lower()], name))
        seen[name.lower()] = tag
    total = len(all_pages)

    def emit(out_path, html):
        write_text(os.path.join(out_dir, out_path.replace("/", os.sep)), html)

    for tag, items in tags.items():
        site.sidebar_boxes = make_sidebar(cfg, works, "", None, backlinks, total)
        # 磁盘上用未编码的名字（和普通页面一样），href 里才做百分号编码。
        # 之前这里把 quote() 之后的结果直接当文件名写盘，链接被 HTTP 层解码成中文名后必然 404。
        out_path = "tags/%s.html" % (tag_map.get(tag) or tag_filename(tag))
        rows = "".join(
            '<div class="recent-row"><span class="who">%s</span><span style="flex:1 1 auto">'
            '<a href="%s">%s</a></span></div>'
            % (_html.escape(works[p.work].title if p.work in works else ""),
               rel_to("tags", p.out_path), _html.escape(p.title))
            for p in sorted(items, key=lambda p: p.name))
        emit(out_path, P.render_layout(
            site, title="标签：%s - %s" % (tag, site.name), body=rows,
            rel=prefix_for(out_path), current_page=None, nav_active="",
            titleblock=P.page_title_block("标签：%s" % _html.escape(tag), ["%d 个条目" % len(items)]),
            stats_line=stats))

    site.sidebar_boxes = make_sidebar(cfg, works, "", None, backlinks, total)
    body = "".join('<a class="chip" href="%s.html">%s <span style="color:#7b8794">%d</span></a>'
                   % (quote(tag_map.get(t) or tag_filename(t), safe=""), _html.escape(t), len(v))
                   for t, v in sorted(tags.items()))
    emit("tags/index.html", P.render_layout(
        site, title="标签总览 - %s" % site.name, body='<p>%s</p>' % body,
        rel=prefix_for("tags/index.html"), current_page=None, nav_active="",
        titleblock=P.page_title_block("标签总览", ["%d 个标签" % len(tags)]), stats_line=stats))


def portal_html(cfg, works, w, site, make_sidebar, backlinks, total_pages, stats):
    site.sidebar_boxes = make_sidebar(cfg, works, w.dirname, None, backlinks, total_pages)
    blocks = []
    aka = w.meta.get("aka")
    if aka:
        blocks.append('<p class="aka">又名《%s》</p>' % _html.escape(str(aka)))
    if w.description:
        blocks.append("<p>%s</p>" % _html.escape(w.description).replace("\n", "<br>"))
    featured = w.meta.get("featured", []) or []
    cards = []
    for name in featured:
        match = next((p for p in w.pages if p.name == name), None)
        if not match:
            continue
        cards.append('<div class="card"><h4><a href="%s">%s</a></h4><p>%s</p></div>'
                     % (rel_to(w.dirname, match.out_path), _html.escape(match.title),
                        _html.escape(plain_excerpt(match.body_html, 110) or "（尚无内容）")))
    if cards:
        blocks.append('<h2>代表条目</h2><div class="list-grid">%s</div>' % "".join(cards))
    for cat in w.sorted_categories():
        if cat.parent:
            continue
        chips = ['<a class="chip" href="%s">%s <span style="color:#7b8794">%d</span></a>'
                 % (rel_to(w.dirname, c.out_path), _html.escape(c.title), len(c.pages))
                 for c in sorted(cat.children, key=lambda c: c.name)]
        chips += ['<a class="chip" href="%s">%s</a>'
                  % (rel_to(w.dirname, p.out_path), _html.escape(p.title))
                  for p in sorted(cat.pages, key=lambda p: p.name)]
        blocks.append('<div class="cat-block"><h3>%s</h3>%s</div>'
                      % (_html.escape(cat.title), "".join(chips) or
                         '<span class="hit-count">（暂无条目）</span>'))
    body = ('<div class="portal-hero"><div class="ph-top"><h2>%s</h2><p>%s</p></div>'
            '<div class="ph-body">%s</div></div>'
            % (_html.escape(w.title), _html.escape(w.tagline), "".join(blocks)))
    return P.render_layout(
        site, title="%s - %s" % (w.title, site.name), body=body, rel=prefix_for(w.out_path),
        current_page=None, nav_active=w.dirname, head_extra=work_accent_css(w),
        titleblock=P.page_title_block(_html.escape(w.title),
                                      ["%d 个条目" % len(w.pages), "作品门户"]),
        stats_line=stats, description=w.description)


def write_list_pages(root, cfg, works, pages, home, all_pages, site, make_sidebar,
                     backlinks, stats, out_dir):
    def emit(out_path, html):
        write_text(os.path.join(out_dir, out_path.replace("/", os.sep)), html)

    # ---- 所有页面 ----
    site.sidebar_boxes = make_sidebar(cfg, works, "all", None, backlinks, len(all_pages))
    groups = []
    for w in sorted(works.values(), key=lambda x: x.get("order", 0)):
        items = "".join('<a href="%s">%s</a>' % (rel_to("", p.out_path), _html.escape(p.title))
                        for p in sorted(w.pages, key=lambda p: p.name))
        groups.append('<div class="cat-block"><h3><a href="%s">%s</a>（%d）</h3>'
                      '<div class="pagelist">%s</div></div>'
                      % (rel_to("", w.out_path), _html.escape(w.title), len(w.pages), items))
    root_items = ['<a href="index.html">%s</a>' % _html.escape(home.title)]
    root_items += ['<a href="%s">%s</a>' % (rel_to("", p.out_path), _html.escape(p.title))
                   for p in sorted((x for x in all_pages if x.is_global and not x.is_home),
                                   key=lambda x: x.name)]
    head = ('<div class="cat-block"><h3>总览</h3><div class="pagelist">%s</div></div>'
            % "".join(root_items))
    emit("all.html", P.render_layout(
        site, title="所有页面 - %s" % site.name, body=head + "".join(groups), rel="",
        current_page=None, nav_active="all",
        titleblock=P.page_title_block("所有页面", ["共 %d 个" % len(all_pages)]),
        stats_line=stats))

    # ---- 最近更新 ----
    recent = sorted(all_pages, key=lambda p: -p.mtime)[:150]
    rows = "".join(
        '<div class="recent-row"><span class="when">%s</span><span class="who">%s</span>'
        '<span style="flex:1 1 auto"><a href="%s">%s</a></span></div>'
        % (datetime.datetime.fromtimestamp(p.mtime).strftime("%Y-%m-%d %H:%M"),
           _html.escape(works[p.work].title if p.work in works else "总览"),
           rel_to("", p.out_path), _html.escape(p.title)) for p in recent)
    site.sidebar_boxes = make_sidebar(cfg, works, "recent", None, backlinks, len(all_pages))
    emit("recent.html", P.render_layout(
        site, title="最近更新 - %s" % site.name,
        body='<p class="hit-count">按源文件最后修改时间排列，共 %d 条。</p>%s' % (len(recent), rows),
        rel="", current_page=None, nav_active="recent",
        titleblock=P.page_title_block("最近更新"), stats_line=stats))

    # ---- 未完成的页面（红色链接汇总） ----
    missing = {}
    for p in all_pages:
        for t in getattr(p, "missing_links", set()) or set():
            missing.setdefault(t, []).append(p)
    rows = []
    for t, srcs in sorted(missing.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        inner = "".join('<div class="recent-row"><span style="flex:1 1 auto">'
                        '<a href="%s">%s</a></span></div>'
                        % (rel_to("", s.out_path), _html.escape(s.title)) for s in srcs[:10])
        rows.append('<details class="spoiler-fold" style="border-color:#cfd9e3;background:#fbfcfd">'
                    '<summary style="color:#22456e">%s <span class="hit-count">（%d 处引用）</span></summary>'
                    '<div class="spoiler-body">%s</div></details>' % (_html.escape(t), len(srcs), inner))
    site.sidebar_boxes = make_sidebar(cfg, works, "missing", None, backlinks, len(all_pages))
    extra = ('<script>(function(){var q=new URLSearchParams(location.search).get("page");'
             'if(q){document.getElementById("missing-note").innerHTML="<div class=\\"spoiler-banner\\">'
             '<b>「"+q.replace(/[<>&]/g,"")+"」这个页面还不存在。</b> 在编辑器的「新建页面」里'
             '填入这个名字就能创建它。</div>";}})();</script>')
    emit("missing.html", P.render_layout(
        site, title="未完成的页面 - %s" % site.name,
        body=('<p class="hit-count">下面这些页面被别的条目引用了，但还没有内容，正文里显示为'
              '<span style="color:#ba0000">红色链接</span>。</p><div id="missing-note"></div>%s'
              % ("".join(rows) or "<p>很好，没有悬空的链接。</p>")),
        rel="", current_page=None, nav_active="missing",
        titleblock=P.page_title_block("未完成的页面", ["%d 个待建条目" % len(missing)]),
        stats_line=stats, top_extra=extra))

    # ---- 特殊页面 ----
    by_name, images = build_indexes(root, cfg, all_pages)
    cats = "".join('<a class="chip" href="%s">%s › %s <span style="color:#7b8794">%d</span></a>'
                   % (rel_to("", c.out_path), _html.escape(w.title), _html.escape(c.title), len(c.pages))
                   for w in sorted(works.values(), key=lambda x: x.get("order", 0))
                   for c in w.sorted_categories())
    media = "".join('<a class="chip" href="%s">%s</a>' % (rel_to("", v[0]), _html.escape(k))
                    for k, v in sorted(images.items()))
    n_media = sum(len(v) for v in images.values())
    body = ('<h2>统计</h2><p>页面 %d 个（其中小作品 %d 个）· 图片 %d 张 · 分类 %d 个</p>'
            '<h2>分类</h2><p>%s</p><h2 id="media">全部图片</h2>'
            '<p class="hit-count">共 %d 张</p><p>%s</p>'
            '<h2>工具</h2><p><a href="all.html">所有页面</a> · <a href="recent.html">最近更新</a> · '
            '<a href="random.html">随机页面</a> · <a href="search.html">搜索</a> · '
            '<a href="missing.html">未完成的页面</a></p>'
            % (len(all_pages), sum(1 for p in all_pages if p.is_stub), n_media,
               sum(len(w.categories) for w in works.values()), cats or "（无）", n_media, media))
    site.sidebar_boxes = make_sidebar(cfg, works, "special", None, backlinks, len(all_pages))
    emit("special.html", P.render_layout(
        site, title="特殊页面 - %s" % site.name, body=body, rel="",
        current_page=None, nav_active="special",
        titleblock=P.page_title_block("特殊页面"), stats_line=stats))

    # ---- 搜索 ----
    site.sidebar_boxes = make_sidebar(cfg, works, "", None, backlinks, len(all_pages))
    emit("search.html", P.render_layout(
        site, title="搜索 - %s" % site.name,
        body=('<form id="sform" class="search-form" style="max-width:520px;margin:10px 0 16px">'
              '<input id="q" type="search" placeholder="输入关键字，例如：复原团、飞云市、超能力">'
              '<button type="submit">搜索</button></form>'
              '<div id="sresults"><p class="hit-count">正在加载索引…</p></div>'),
        rel="", current_page=None, nav_active="",
        titleblock=P.page_title_block("搜索"), stats_line=stats,
        top_extra='<script src="assets/search.js"></script>'))

    # ---- 随机 ----
    emit("random.html", P.render_layout(
        site, title="随机页面 - %s" % site.name,
        body=('<p>要从全部 <b id="cnt">…</b> 个页面里随机抽一个吗？</p>'
              '<p><button id="go" style="padding:6px 16px;cursor:pointer">带我去一个随机页面</button></p>'),
        rel="", current_page=None, nav_active="random",
        titleblock=P.page_title_block("随机页面"), stats_line=stats,
        top_extra='<script src="assets/random.js"></script>'))

    # ---- 404 ----
    emit("404.html", P.render_layout(
        site, title="页面不存在 - %s" % site.name,
        body=('<p>这个地址没有对应的条目。可以试试 <a href="search.html">搜索</a>，'
              '或者从 <a href="index.html">首页</a> 出发。</p>'),
        rel="", current_page=None, nav_active="",
        titleblock=P.page_title_block("页面不存在"), stats_line=stats))


def write_assets(root, cfg, out_dir):
    src = os.path.join(root, cfg["assets_dir"])
    dst = os.path.join(out_dir, "assets")
    os.makedirs(dst, exist_ok=True)
    if os.path.isdir(src):
        for dirpath, dirnames, filenames in os.walk(src):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                target = os.path.join(dst, os.path.relpath(os.path.join(dirpath, name), src))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(os.path.join(dirpath, name), target)
    write_text(os.path.join(dst, "theme.css"), P.theme_css(cfg.get("theme", {})))
    write_text(os.path.join(dst, "theme.js"), P.THEME_JS)
    write_text(os.path.join(dst, "search.js"), P.SEARCH_JS)
    write_text(os.path.join(dst, "random.js"), P.RANDOM_JS)
    write_text(os.path.join(dst, "favicon.svg"), P.FAVICON)
    write_text(os.path.join(out_dir, ".nojekyll"), "")


def write_search_index(cfg, works, all_pages, out_dir):
    items = []
    for p in all_pages:
        w = works.get(p.work)
        keys = [p.name] + list(p.tags) + list(p.aliases)
        if w:
            keys += [w.title, w.nav_label, str(w.meta.get("aka", ""))]
        items.append({
            "t": p.title, "u": p.url,
            "w": w.title if w else "", "c": p.category_title,
            "k": " ".join(x for x in keys if x),
            "x": plain_excerpt(p.body_html, 200),
            "n": len(p.body_html),
        })
    items.sort(key=lambda i: i["t"])
    write_text(os.path.join(out_dir, "search.json"), json.dumps(items, ensure_ascii=False))


def report(root, cfg, works, pages, all_pages, by_name, images, backlinks, warn, quiet):
    dup_names = {k: v for k, v in by_name.items() if len({p.rel for p in v}) > 1}
    dup_imgs = {k: v for k, v in images.items() if len(v) > 1}
    orphans = [p for p in pages if not backlinks.get(p.rel) and not p.links_out]
    red = {}
    for p in all_pages:
        for t in getattr(p, "missing_links", set()) or set():
            red[t] = red.get(t, 0) + 1
    log("\n生成完成 → %s" % os.path.join(root, cfg["output_dir"]), quiet)
    log("  页面 %d · 作品 %d · 图片 %d · 待建条目 %d"
        % (len(all_pages), len(works), sum(len(v) for v in images.values()), len(red)), quiet)
    if warn:
        log("  ⚠ 缺失图片 %d 处" % warn, quiet)
    if red:
        log("  ⚠ 悬空链接（正文里显示为红色）：%s"
            % "、".join("%s×%d" % (k, v) for k, v in sorted(red.items(), key=lambda kv: -kv[1])[:12]), quiet)
    if dup_names:
        log("  ⚠ 同名页面：%s" % "、".join(dup_names), quiet)
    if dup_imgs:
        log("  ⚠ 同名图片：%s" % "、".join(dup_imgs), quiet)
    if orphans:
        log("  · 孤立页面（无链入也无链出）%d 个：%s"
            % (len(orphans), "、".join(p.name for p in orphans[:12])), quiet)


def serve(out_dir, port):
    import http.server
    import socketserver
    import threading
    import webbrowser

    handler = lambda *a, **kw: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=out_dir, **kw)

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with Server(("127.0.0.1", port), handler) as httpd:
        url = "http://127.0.0.1:%d/index.html" % port
        print("本地预览：%s   （Ctrl+C 停止）" % url)
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止预览。")


def main():
    ap = argparse.ArgumentParser(description="生成 nijiboshi-wiki 静态站点")
    ap.add_argument("--root", default=HERE, help="项目根目录")
    ap.add_argument("--open", action="store_true", help="生成后启动本地预览并打开浏览器")
    ap.add_argument("--port", type=int, default=8123, help="预览端口，默认 8123")
    ap.add_argument("--quiet", action="store_true", help="只输出摘要")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    cfg = load_config(root)
    t0 = time.time()
    build(root, cfg, args.quiet)
    log("  用时 %.2f 秒" % (time.time() - t0), args.quiet)
    if args.open:
        serve(os.path.join(root, cfg["output_dir"]), args.port)


if __name__ == "__main__":
    main()
