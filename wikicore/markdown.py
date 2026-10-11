# -*- coding: utf-8 -*-
"""Obsidian 兼容的 Markdown → HTML 渲染器。

刻意不依赖任何第三方库：只用标准库，双击就能跑。

支持：
    * 标题 # ~ ######（自动生成目录锚点）
    * 段落、软换行（可配置）、粗体、斜体、删除线、==高亮==、`行内代码`
    * [[双链]] / [[目标|显示名]]  → 站内链接，目标不存在时渲染成红色链接
    * ![[图片.jpg|150]]          → 按文件名在全站 assets 里找图
    * 原生 <img src="X.jpg">     → 同样按文件名找图并改写成正确的相对路径
    * > [!info] 标题 callout      → 信息框（infobox）或彩色提示框
    * GFM 管道表格、无序/有序列表、引用块、水平线
    * %%Obsidian 注释%%           → 丢弃
    * 块级原生 HTML（<table> <div> <figure> <center> …）原样保留
"""

import html as _html
import posixpath
import re
from urllib.parse import quote

# ---------------------------------------------------------------- 正则

CALLOUT_RE = re.compile(r"^\[!([A-Za-z]+)\]([+-]?)\s*(.*)$")
WIKILINK_RE = re.compile(r"(!?)\[\[([^\[\]]+?)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
HR_RE = re.compile(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$")
UL_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
OL_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"'][^>]*>", re.I)
INFO_ROW_RE = re.compile(r"^\s*[-*+]\s+(.*)$")

VOID_TAGS = {"hr", "img", "br", "input", "meta", "link", "source", "wbr", "col"}
BLOCK_TAGS = ("table", "div", "figure", "center", "section", "details", "summary",
              "ul", "ol", "blockquote", "dl", "pre", "p", "hr", "img", "iframe",
              "style", "script", "svg", "video", "audio", "aside", "nav", "article")

# 图片找不到时的占位图（内联 SVG，避免多一个二进制资源）
MISSING_IMG = ("data:image/svg+xml;utf8,"
               "%3Csvg xmlns='http://www.w3.org/2000/svg' width='160' height='110'%3E"
               "%3Crect width='160' height='110' fill='%23f4f6f8' stroke='%23c0392b' stroke-dasharray='5 4'/%3E"
               "%3Ctext x='80' y='58' font-size='13' fill='%23c0392b' text-anchor='middle'%3E图片缺失%3C/text%3E"
               "%3C/svg%3E")

CALLOUT_STYLES = {
    "info": ("信息", "c-info"), "note": ("笔记", "c-note"), "abstract": ("摘要", "c-note"),
    "summary": ("摘要", "c-note"), "todo": ("待办", "c-note"), "tip": ("提示", "c-tip"),
    "hint": ("提示", "c-tip"), "important": ("重要", "c-tip"), "success": ("完成", "c-success"),
    "check": ("完成", "c-success"), "done": ("完成", "c-success"), "question": ("疑问", "c-question"),
    "help": ("疑问", "c-question"), "faq": ("疑问", "c-question"), "warning": ("警告", "c-warning"),
    "caution": ("警告", "c-warning"), "attention": ("警告", "c-warning"), "failure": ("失败", "c-fail"),
    "fail": ("失败", "c-fail"), "missing": ("缺失", "c-fail"), "danger": ("危险", "c-danger"),
    "error": ("错误", "c-danger"), "bug": ("缺陷", "c-danger"), "example": ("示例", "c-example"),
    "quote": ("引用", "c-quote"), "cite": ("引用", "c-quote"),
}


def slugify_anchor(text, index):
    """标题锚点：中文没有可靠的 ascii slug，统一用顺序号，稳定且不会撞车。"""
    return "sec-%d" % index


class Resolver:
    """负责把页面名 / 图片名解析成站内相对 URL。"""

    def __init__(self, pages_by_name, images_by_name, work_of=None):
        self.pages_by_name = pages_by_name          # name -> [Page, ...]
        self.images_by_name = images_by_name        # basename -> root 相对路径（未编码）
        self.work_of = work_of or {}                # Page -> work 目录名
        # 大小写不敏感的回退表：macOS 不区分大小写，但 GitHub Pages(Linux) 区分，
        # 正文里写 denji_cute.jpg、实际文件叫 Denji_Cute.jpg 时必须兜住。
        self.images_lower = {}
        for name, paths in images_by_name.items():
            self.images_lower.setdefault(name.lower(), []).extend(paths)

    def find_page(self, name, current=None):
        cands = self.pages_by_name.get(name)
        if not cands:
            return None
        if current is not None and len(cands) > 1:
            for p in cands:
                if p.work == current.work:
                    return p
        return cands[0]

    def find_image(self, name, current=None):
        base = posixpath.basename(name.strip())
        cands = self.images_by_name.get(base) or self.images_lower.get(base.lower())
        if not cands:
            return None
        work = getattr(current, "work", None)
        if work:
            pref = "assets/%s/%s" % (work, base)
            for c in cands:
                if c.lower() == pref.lower():
                    return c
        return cands[0]


class Renderer:
    def __init__(self, resolver, config, current=None, url_prefix=None):
        self.r = resolver
        self.cfg = config
        self.current = current                  # 当前 Page（用于算相对路径），首页为 None
        self.url_prefix = url_prefix            # 编辑器预览用：所有链接改成 /site/... 绝对路径
        self.headings = []                      # [(level, anchor, text, in_spoiler)]
        self.warnings = []
        self.links_out = set()                  # 本页指向的其他页面名
        self.missing_links = set()
        self.spoiler_used = False
        self._anchor = 0

    # ------------------------------------------------------------ 路径

    def rel(self, root_path):
        """把 docs/ 下的根相对路径转成当前页面的相对 URL（并做百分号编码）。"""
        if not root_path:
            return ""
        if self.url_prefix is not None:
            return self.url_prefix + quote(root_path, safe="/-_.~!$&'()*+,;=:@")
        if self.current is not None:
            base = posixpath.dirname(self.current.out_path)
            rp = posixpath.relpath(root_path, base) if base else root_path
        else:
            rp = root_path
        return quote(rp, safe="/-_.~!$&'()*+,;=:@")

    def asset_url(self, root_path):
        return self.rel(root_path)

    # ------------------------------------------------------------ 内联

    def inline(self, text):
        codes = []

        def stash(m):
            codes.append(m.group(1))
            return "\x00C%d\x00" % (len(codes) - 1)

        text = re.sub(r"`([^`]+)`", stash, text)
        text = re.sub(r"%%.*?%%", "", text, flags=re.S)
        text = WIKILINK_RE.sub(self._wikilink, text)
        text = re.sub(r"==([^=\n]+)==", r"<mark>\1</mark>", text)
        text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"(?<![A-Za-z0-9_*])\*([^*\n]+?)\*(?![A-Za-z0-9_*])", r"<em>\1</em>", text)
        text = re.sub(r"~~(.+?)~~", r"<del>\1</del>", text)
        text = re.sub(r"\[([^\]\n]+)\]\(([^)\s]+)\)", self._mdlink, text)
        text = re.sub(r"(?<![\"'>=/])(https?://[^\s<>\"'）】]+)",
                      r'<a class="ext" href="\1" target="_blank" rel="noopener noreferrer">\1</a>', text)
        text = text.replace("<!--more-->", "")
        for i, c in enumerate(codes):
            text = text.replace("\x00C%d\x00" % i, "<code>%s</code>" % _html.escape(c))
        return text

    def _mdlink(self, m):
        label, url = m.group(1), m.group(2)
        if url.startswith(("http://", "https://")):
            return '<a class="ext" href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (url, label)
        return '<a href="%s">%s</a>' % (quote(url, safe="/-_.~!$&'()*+,;=:@?#"), label)

    def _wikilink(self, m):
        is_embed, inner = m.group(1) == "!", m.group(2)
        inner = inner.replace("\\|", "\x00PIPE\x00")
        parts = [p.strip() for p in inner.split("|")]
        target = parts[0].replace("\x00PIPE\x00", "|")
        arg = parts[1].replace("\x00PIPE\x00", "|") if len(parts) > 1 else None
        target = target.split("#")[0].strip()

        img_path = self.r.find_image(target, self.current)
        if img_path:
            return self._img_tag(img_path, target, arg)
        if is_embed:
            page = self.r.find_page(target, self.current)
            if page:
                return ('<a class="wikilink embed" href="%s">→ %s</a>'
                        % (self.rel(page.out_path), page.title))
        page = self.r.find_page(target, self.current)
        if page:
            self.links_out.add(page.name)
            label = arg or (page.title if page.title != page.name else target)
            return '<a class="wikilink" href="%s" title="%s">%s</a>' % (
                self.rel(page.out_path), _html.escape(page.title, quote=True), label)
        self.missing_links.add(target)
        label = arg or target
        return ('<a class="new" href="%s" title="页面「%s」还不存在">%s</a>'
                % (self.rel("missing.html") + "?page=" + quote(target), _html.escape(target), label))

    def _img_tag(self, root_path, name, arg):
        width = ""
        if arg:
            w = re.split(r"[x×]", arg.strip())[0].strip()
            if re.fullmatch(r"\d+", w):
                width = ' width="%s"' % w
        return '<img class="wikimg" src="%s"%s alt="%s" loading="lazy">' % (
            self.asset_url(root_path), width, _html.escape(name, quote=True))

    # ------------------------------------------------------------ 块级

    def render(self, text):
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return self._blocks(lines)

    def _blocks(self, lines):
        out = []
        i, n = 0, len(lines)
        soft = self.cfg.get("soft_breaks", "br")
        while i < n:
            raw = lines[i]
            line = raw.rstrip()
            if not line.strip():
                i += 1
                continue

            # 围栏代码块 ``` ... ```（内部原样保留，不做行内处理）
            fence = re.match(r"^\s*(```+|~~~+)\s*([\w+-]*)\s*$", line)
            if fence:
                marker, lang = fence.group(1)[0], fence.group(2)
                j = i + 1
                while j < n and not re.match(r"^\s*%s{3,}\s*$" % marker, lines[j]):
                    j += 1
                if j < n:                                # 有收尾围栏才算代码块
                    body = lines[i + 1:j]
                    i = j + 1
                    cls = ' class="lang-%s"' % _html.escape(lang) if lang else ""
                    out.append('<pre class="codeblock"><code%s>%s</code></pre>'
                               % (cls, _html.escape("\n".join(body))))
                    continue
                # 没有收尾围栏：当普通段落处理，绝不吞掉后面的整篇文档

            html_block = self._try_html_block(lines, i)
            if html_block is not None:
                frag, i = html_block
                out.append(frag)
                continue

            m = HEADING_RE.match(line)
            if m:
                level = len(m.group(1))
                text_h = m.group(2).strip()
                self._anchor += 1
                anchor = slugify_anchor(text_h, self._anchor)
                plain = re.sub(r"[*`\[\]]|!\[\[|\]\]", "", text_h)
                self.headings.append({"level": level, "anchor": anchor, "text": plain,
                                      "spoiler": self._is_spoiler(text_h), "nested": False})
                out.append('<h%d id="%s">%s<span class="anchor">'
                           '<a href="#%s" title="锚点">¶</a></span></h%d>'
                           % (level, anchor, self.inline(text_h), anchor, level))
                i += 1
                continue

            if HR_RE.match(line) and not HEADING_RE.match(line):
                out.append("<hr>")
                i += 1
                continue

            if QUOTE_RE.match(raw) or QUOTE_RE.match(line):
                block, i = self._consume(lines, i, lambda s: QUOTE_RE.match(s) is not None)
                out.append(self._blockquote(block))
                continue

            if line.lstrip().startswith("|") and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1]):
                block, i = self._consume(lines, i, lambda s: "|" in s and s.strip() != "")
                out.append(self._table(block))
                continue

            if UL_RE.match(line) or OL_RE.match(line):
                block, i = self._consume(lines, i, lambda s: UL_RE.match(s) or OL_RE.match(s)
                                         or (s.strip() and (s.startswith("  ") or s.startswith("\t"))))
                out.append(self._list(block))
                continue

            # 段落
            buf = [line]
            i += 1
            while i < n:
                nxt = lines[i]
                if not nxt.strip():
                    break
                if self._starts_block(nxt):
                    break
                buf.append(nxt.rstrip())
                i += 1
            sep = {"br": "<br>\n", "space": "\n", "paragraph": "</p>\n<p>"}.get(soft, "<br>\n")
            out.append("<p>" + sep.join(self.inline(b) for b in buf) + "</p>")
        return "\n".join(out)

    def _nested_blocks(self, lines):
        """渲染嵌套块（callout / 信息框 / 引用块内部），并把这些块里的标题标记为 nested。

        嵌套标题不参与目录，也不参与剧透折叠。否则 wrap_spoilers 会按字符偏移
        从 <div class="callout-body"> 中间切一刀，产出结构错乱的 HTML。
        """
        start = len(self.headings)
        html = self._blocks(lines)
        for h in self.headings[start:]:
            h["nested"] = True
        return html

    def _starts_block(self, line):
        if HEADING_RE.match(line) or HR_RE.match(line):
            return True
        if QUOTE_RE.match(line) or UL_RE.match(line) or OL_RE.match(line):
            return True
        if line.lstrip().startswith("|"):
            return True
        return self._html_block_start(line) is not None

    def _consume(self, lines, i, pred):
        block = []
        n = len(lines)
        while i < n:
            if not pred(lines[i]):
                break
            block.append(lines[i])
            i += 1
        return block, i

    # ------------------------------------------------------- 原生 HTML

    def _html_block_start(self, line):
        s = line.lstrip()
        if not s.startswith("<"):
            return None
        m = re.match(r"</?([a-zA-Z][a-zA-Z0-9]*)", s)
        if not m:
            return None
        tag = m.group(1).lower()
        return tag if tag in BLOCK_TAGS else None

    def _try_html_block(self, lines, i):
        """如果是块级 HTML，返回 (html, 新下标)；否则 None。"""
        tag = self._html_block_start(lines[i])
        if not tag:
            return None
        if tag in VOID_TAGS or re.search(r"/>\s*$", lines[i].strip()):
            frag = lines[i].strip()
            if tag == "img":
                frag = self._rewrite_img_src(frag)
            return frag, i + 1

        open_re = re.compile(r"<%s\b" % tag, re.I)
        close_re = re.compile(r"</%s\s*>" % tag, re.I)
        depth = 0
        buf = []
        j = i
        n = len(lines)
        while j < n:
            cur = lines[j]
            if j > i and not cur.strip() and depth <= 0:
                break
            buf.append(cur.strip())
            depth += len(open_re.findall(cur)) - len(close_re.findall(cur))
            if re.search(r"/>\s*$", cur.strip()) and not close_re.search(cur):
                depth -= 1
            j += 1
            if depth <= 0:
                break
        if depth > 0:                      # 没闭合：当普通段落处理，别吞掉半篇文档
            return None
        frag = "\n".join(buf)
        if tag == "img":
            frag = self._rewrite_img_src(frag)
        frag = IMG_SRC_RE.sub(lambda m: self._rewrite_one_img(m), frag)
        return frag, j

    def _rewrite_img_src(self, frag):
        return IMG_SRC_RE.sub(lambda m: self._rewrite_one_img(m), frag)

    def _rewrite_one_img(self, m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        root = self.r.find_image(src, self.current)
        if root:
            return m.group(0).replace('src="%s"' % src, 'src="%s"' % self.asset_url(root)) \
                             .replace("src='%s'" % src, 'src="%s"' % self.asset_url(root))
        self.warnings.append("找不到图片：%s" % src)
        return m.group(0).replace('src="%s"' % src, 'src="%s"' % MISSING_IMG) \
                         .replace("src='%s'" % src, 'src="%s"' % MISSING_IMG)

    # ---------------------------------------------------------- 各块渲染

    def _blockquote(self, block):
        inner = []
        for b in block:
            m = QUOTE_RE.match(b)
            inner.append(m.group(1) if m else b.lstrip(">").strip())
        m = CALLOUT_RE.match(inner[0].strip())
        if m:
            kind = m.group(1).lower()
            collapsed = m.group(2) == "-"
            title = m.group(3).strip()
            body = inner[1:]
            infobox_types = self.cfg.get("infobox_callouts",
                                         ["info", "note", "abstract", "summary", "example"])
            if kind in infobox_types and self._looks_like_infobox(body):
                return self._infobox(title, body)
            return self._callout(kind, title, body, collapsed)
        body = "\n".join(inner)
        return '<blockquote>%s</blockquote>' % self._nested_blocks(body.split("\n"))

    @staticmethod
    def _looks_like_infobox(body):
        """只有出现「- 键：值」行或图片的行，才算信息框；否则当普通提示框。

        这样 `> [!info] 欢迎来到…` 这种纯文字 callout 不会被挤成右侧信息框。
        """
        for line in body:
            s = line.strip()
            if not s:
                continue
            if re.match(r"^\s*!\[\[", s) or s.startswith("<img"):
                return True
            m = INFO_ROW_RE.match(s)
            if m and ("：" in m.group(1) or ":" in m.group(1)):
                return True
        return False

    def _callout(self, kind, title, body, collapsed):
        label, cls = CALLOUT_STYLES.get(kind, (kind, "c-note"))
        head = title or label
        inner_html = self._nested_blocks(body)
        if collapsed:
            return ('<details class="callout %s"><summary><span class="callout-label">%s</span> %s'
                    '</summary><div class="callout-body">%s</div></details>'
                    % (cls, label, self.inline(head), inner_html))
        return ('<div class="callout %s"><div class="callout-title"><span class="callout-label">%s</span>'
                ' %s</div><div class="callout-body">%s</div></div>'
                % (cls, label, self.inline(head), inner_html))

    def _infobox(self, title, body):
        """把 callout 里的键值行抽成信息框。"""
        images, rows, extra = [], [], []
        for line in body:
            s = line.strip()
            if not s:
                continue
            m = WIKILINK_RE.search(s)
            if m and m.group(1) == "!" and len(re.sub(r"!\[\[.*?\]\]", "", s).strip()) == 0:
                images.append(self._wikilink(m))
                continue
            if s.startswith("<img"):
                images.append(self._rewrite_img_src(s))
                continue
            m = INFO_ROW_RE.match(s)
            if m:
                item = m.group(1).strip()
                item = re.sub(r"^\*\*(.+?)\*\*", r"\1", item)
                if "：" in item:
                    k, v = item.split("：", 1)
                elif ":" in item:
                    k, v = item.split(":", 1)
                else:
                    extra.append(item)
                    continue
                rows.append((k.strip(), self.inline(v.strip())))
                continue
            extra.append(s)

        parts = ['<aside class="infobox">']
        if title:
            parts.append('<div class="infobox-title">%s</div>' % self.inline(title))
        for img in images:
            parts.append('<div class="infobox-image">%s</div>' % img)
        if rows:
            parts.append('<table class="infobox-table">')
            for k, v in rows:
                parts.append("<tr><th>%s</th><td>%s</td></tr>" % (_html.escape(k), v))
            parts.append("</table>")
        if extra:
            parts.append('<div class="infobox-extra">%s</div>' % self._nested_blocks(extra))
        parts.append("</aside>")
        return "\n".join(parts)

    def _table(self, block):
        def cells(line):
            s = line.strip()
            if s.startswith("|"):
                s = s[1:]
            if s.endswith("|"):
                s = s[:-1]
            return [c.strip() for c in s.split("|")]

        head = cells(block[0])
        rows = [cells(b) for b in block[2:]]
        out = ['<table class="wikitable">', "<thead><tr>"]
        out += ["<th>%s</th>" % self.inline(c) for c in head]
        out.append("</tr></thead><tbody>")
        for r in rows:
            out.append("<tr>")
            out += ["<td>%s</td>" % self.inline(c) for c in r]
            out.append("</tr>")
        out.append("</tbody></table>")
        return "".join(out)

    def _list(self, block):
        """列表渲染：按缩进建树，缩进续行并入上一个列表项。

        注意：旧实现用 `out[-1].endswith("</li>")` 判断续行，而循环末尾总会 append
        `<li>…`，那个条件永远不成立 —— 结果是缩进续行被静默丢掉。
        """
        items = []                       # [[缩进, 是否有序, [文本行…]], …]
        for line in block:
            mu, mo = UL_RE.match(line), OL_RE.match(line)
            if mu or mo:
                indent = len((mu or mo).group(1).replace("\t", "    "))
                ordered = mo is not None
                items.append([indent, ordered, [mo.group(3) if ordered else mu.group(2)]])
            elif items:
                items[-1][2].append(line.strip())      # 续行接到上一个列表项
        if not items:
            return ""

        root = {"indent": -1, "ordered": None, "lines": [], "children": []}
        stack = [root]
        for indent, ordered, lines in items:
            # 缩进不大于栈顶时回退到合适的父节点：2 空格和 4 空格都能作为一级子列表
            while len(stack) > 1 and indent <= stack[-1]["indent"]:
                stack.pop()
            node = {"indent": indent, "ordered": ordered, "lines": lines, "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        return self._render_list(root["children"])

    def _render_list(self, nodes):
        out, i = [], 0
        while i < len(nodes):
            ordered = nodes[i]["ordered"]
            group = []
            while i < len(nodes) and nodes[i]["ordered"] == ordered:
                group.append(nodes[i])
                i += 1
            tag = "ol" if ordered else "ul"
            out.append("<%s>" % tag)
            for n in group:
                text = "<br>\n".join(self.inline(x) for x in n["lines"] if x.strip())
                out.append("<li>%s%s</li>" % (text, self._render_list(n["children"])))
            out.append("</%s>" % tag)
        return "".join(out)

    # ---------------------------------------------------------- 剧透折叠

    def _is_spoiler(self, heading_text):
        pats = self.cfg.get("spoiler", {}).get("fold_headings", [])
        return any(p in heading_text for p in pats)


def wrap_spoilers(body_html, headings, summary_fmt="\U0001F512 %s —— 含剧透，点击展开"):
    """把含有剧透关键词的章节整段包进 <details> 折叠块。

    需要 body_html、headings 同源（由同一个 Renderer 产出）。
    返回 (新 html, 是否产生了折叠)。
    """
    marked = [(i, h) for i, h in enumerate(headings)
              if h.get("spoiler") and h["level"] in (2, 3) and not h.get("nested")]
    if not marked:
        return body_html, False

    pos = {}
    for i, h in enumerate(headings):
        pos[i] = body_html.find('<h%d id="%s">' % (h["level"], h["anchor"]))

    regions = []
    for i, h in marked:
        start = pos.get(i, -1)
        if start < 0:
            continue
        end = len(body_html)
        for j in range(i + 1, len(headings)):
            # 嵌套在 callout / 信息框 / 引用块里的标题不能用来「结束」外层折叠区：
            # 它位于容器内部，拿它的位置当终点会让 <details> 在容器里闭合，产出错乱 HTML。
            if headings[j].get("nested"):
                continue
            if headings[j]["level"] <= h["level"] and pos.get(j, -1) > start:
                end = pos[j]
                break
        regions.append((start, end, h["text"]))

    regions.sort()
    kept = []
    for r in regions:
        if kept and r[0] < kept[-1][1]:      # 已被外层折叠包住，跳过
            continue
        kept.append(r)
    if not kept:
        return body_html, False

    out, prev = [], 0
    for start, end, text in kept:
        safe = _html.escape(text, quote=True)
        out.append(body_html[prev:start])
        out.append('<details class="spoiler-fold" data-fold="%s"><summary>%s</summary>'
                   '<div class="spoiler-body">' % (safe, summary_fmt % safe))
        out.append(body_html[start:end])
        out.append("</div></details>")
        prev = end
    out.append(body_html[prev:])
    return "".join(out), True
