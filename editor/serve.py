#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nijiboshi-wiki 本地编辑器。

启动：
    python3 editor/serve.py            # 打开 http://127.0.0.1:8765
    python3 editor/serve.py --port 9000 --no-open

能做这些事：
    * 左侧页面树浏览 / 搜索 / 新建（带模板）/ 重命名 / 删除（进回收站）
    * 中间写 Markdown，右侧实时预览（用的就是 build.py 同一套渲染器，所见即所得）
    * [[双链]] 自动补全、图片拖拽上传、信息框表单化编辑
    * 一键「构建站点」，一键 Git 提交 / 推送 / 拉取
    * 站点设置与每部作品的元信息编辑

只监听 127.0.0.1，只依赖 Python 3.8+ 标准库。
"""

import argparse
import base64
import functools
import json
import mimetypes
import os
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

EDITOR_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(EDITOR_DIR)
sys.path.insert(0, ROOT)

import build as B                                              # noqa: E402
from wikicore import pages as P                                # noqa: E402
from wikicore.markdown import Renderer, Resolver               # noqa: E402

CONTENT = os.path.join(ROOT, "content")
ASSETS = os.path.join(ROOT, "assets")
DOCS = os.path.join(ROOT, "docs")
TRASH = os.path.join(CONTENT, ".trash")
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".avif"}

_build_lock = threading.Lock()
_last_build = {"at": None, "out": "", "ok": None}


# ------------------------------------------------------------------ 辅助

def cfg():
    return B.load_config(ROOT)


def json_response(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler, text, status=200, ctype="text/plain; charset=utf-8"):
    body = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def content_path(rel):
    """把 content/ 下的相对路径转成绝对路径，并挡住目录穿越。"""
    rel = (rel or "").replace("\\", "/").strip()
    if not rel:
        raise ValueError("缺少路径")
    # 绝对路径与盘符直接拒绝，不靠 normpath 把 /etc/x.md 悄悄变成 content/etc/x.md
    if rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise ValueError("只接受 content/ 下的相对路径：%s" % rel)
    parts = [p for p in rel.split("/") if p]
    if any(p in (".", "..") for p in parts):
        raise ValueError("路径不合法：%s" % rel)
    full = os.path.normpath(os.path.join(CONTENT, *parts))
    if not _within(full, CONTENT):
        raise ValueError("路径越界：%s" % rel)
    if not full.endswith(".md"):
        raise ValueError("只允许编辑 .md 文件")
    return full


def work_segment(work, label="作品目录名"):
    """校验「作品目录」参数：只允许单层普通目录名，不能有分隔符或 .. 段。

    这个参数来自浏览器，之前没校验，upload 接口能借它把文件写到 assets/ 之外。
    """
    w = (work or "").strip()
    if not w:
        return ""
    # 去掉一个尾部斜杠后仍有斜杠、以 / 开头、含反斜杠或盘符 —— 一律拒绝
    if "/" in w.rstrip("/") or "\\" in w or w.startswith("/") or re.match(r"^[A-Za-z]:", w):
        raise ValueError("%s不合法：%s" % (label, work))
    w = w.rstrip("/")
    if w in (".", "..") or w.startswith("."):
        raise ValueError("%s不合法：%s" % (label, work))
    return w


def _within(path, base):
    """path 是否在 base 之内（用 os.sep 收尾，避免 docs 与 docs_backup 被当成同一个）。"""
    path = os.path.normpath(path)
    base = os.path.normpath(base)
    return path == base or path.startswith(base + os.sep)


def safe_name(name):
    name = (name or "").strip()
    name = name.replace("/", "").replace("\\", "")
    if not name or name in (".", ".."):
        raise ValueError("名字不合法")
    if name.startswith("."):
        raise ValueError("名字不能以点开头")
    return name


def fresh_indexes():
    cfg_ = cfg()
    works, pages, home = B.load_pages(ROOT, cfg_)
    for p in pages:
        B.load_page_source(p)
    if home is not None:
        B.load_page_source(home)
    by_name, images = B.build_indexes(ROOT, cfg_, pages + ([home] if home else []))
    return cfg_, works, pages, home, by_name, images


def state_payload():
    c, works, pages, home, by_name, images = fresh_indexes()
    page_list = []
    for w in sorted(works.values(), key=lambda x: x.get("order", 0)):
        for p in sorted(w.pages, key=lambda x: (x.category, x.name)):
            page_list.append({
                "path": p.rel, "name": p.name, "title": p.title,
                "work": w.dirname, "workTitle": w.title, "category": p.category,
                "categoryTitle": p.category_title, "stub": p.is_stub,
                "mtime": p.mtime, "bytes": os.path.getsize(p.abs),
                "outPath": p.out_path,
            })
    globals_ = []
    if home is not None:
        globals_.append({"path": home.rel, "name": home.name, "title": home.title,
                         "category": "", "categoryTitle": "总览"})
    work_meta = [{"dir": w.dirname, "title": w.title, "tagline": w.tagline,
                  "accent": w.accent, "order": w.get("order", 0),
                  "categories": [{"path": ct.path, "title": ct.title,
                                  "count": len(ct.pages)} for ct in w.sorted_categories()],
                  "meta": w.meta}
                 for w in sorted(works.values(), key=lambda x: x.get("order", 0))]
    return {
        "config": {k: v for k, v in c.items() if not k.startswith("_")},
        "pages": page_list, "globals": globals_, "works": work_meta,
        "media": sorted(images.keys()),
        "git": git_status(),
        "lastBuild": _last_build,
    }


# ------------------------------------------------------------------ git

def git(*args, timeout=60):
    try:
        r = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "找不到 git 命令"
    except subprocess.TimeoutExpired:
        return 124, "", "git 超时"


def git_status():
    code, out, err = git("status", "--porcelain=v1", "-b")
    if code != 0:
        return {"ok": False, "error": err or out, "branch": "", "changes": [], "remote": ""}
    lines = out.split("\n") if out else []
    branch, ahead = "", ""
    if lines and lines[0].startswith("##"):
        head = lines[0][2:].strip()
        branch = head.split("...")[0].strip()
        ahead = head
        lines = lines[1:]
    _, remote, _ = git("remote", "get-url", "origin")
    changes = []
    for line in lines:
        if len(line) > 3:
            changes.append({"code": line[:2].strip(), "file": line[3:].strip()})
    return {"ok": True, "branch": branch, "remote": remote, "ahead": ahead,
            "changes": changes, "dirty": bool(changes)}


# ------------------------------------------------------------------ 预览

def render_preview(rel, content):
    c, works, pages, home, by_name, images = fresh_indexes()
    resolver = Resolver(by_name, images)
    meta, body = B.parse_frontmatter(content)
    virtual = B.Page(os.path.join(CONTENT, rel), rel)
    virtual.meta = meta
    virtual.title = str(meta.get("标题") or meta.get("title") or virtual.name)
    tags = meta.get("标签", meta.get("tags", []))
    virtual.tags = [str(x) for x in ([tags] if isinstance(tags, str) else tags)]
    aliases = meta.get("别名", meta.get("aliases", []))
    virtual.aliases = [str(x) for x in ([aliases] if isinstance(aliases, str) else aliases)]
    r = Renderer(resolver, c, current=virtual, url_prefix="/site/")
    html = r.render(body)
    from wikicore.markdown import wrap_spoilers
    html, folded = wrap_spoilers(html, r.headings)
    return {
        "html": html,
        "headings": r.headings,
        "missing": sorted(r.missing_links),
        "warnings": r.warnings,
        "spoiler": folded or bool(meta.get("剧透") or meta.get("spoiler")),
        "stub": len(body.strip()) < 30,
    }


# ------------------------------------------------------------------ 构建

def run_build():
    with _build_lock:
        cfg_ = cfg()
        t0 = time.time()
        buf = []
        import io
        import contextlib
        f = io.StringIO()
        ok = True
        try:
            with contextlib.redirect_stdout(f):
                B.build(ROOT, cfg_, False)
        except SystemExit as e:
            ok = False
            buf.append(str(e))
        except Exception as e:                                  # noqa: BLE001
            ok = False
            buf.append("%s: %s" % (type(e).__name__, e))
        out = f.getvalue() + "\n".join(buf)
        _last_build.update({"at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "out": out, "ok": ok, "secs": round(time.time() - t0, 2)})
        return _last_build


# ------------------------------------------------------------------ 请求处理

class Handler(BaseHTTPRequestHandler):
    server_version = "nijiboshi-wiki-editor/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("WIKI_EDITOR_VERBOSE"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -------------------------------------------------- GET

    def do_GET(self):
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        try:
            if path.startswith("/api/"):
                return self.api_get(path[5:], parse_qs(parts.query))
            if path in ("/", "/index.html"):
                return self.serve_file(os.path.join(EDITOR_DIR, "ui", "index.html"))
            if path.startswith("/ui/"):
                return self.serve_file(os.path.join(EDITOR_DIR, "ui", path[4:]))
            if path == "/preview.css":
                c = cfg()
                return text_response(self, P.theme_css(c.get("theme", {})),
                                     ctype="text/css; charset=utf-8")
            if path.startswith("/site/"):
                return self.serve_file(os.path.join(DOCS, path[6:]))
            if path.startswith("/media/"):
                return self.serve_file(os.path.join(ASSETS, path[7:]))
            if path == "/favicon.ico":
                return self.serve_file(os.path.join(DOCS, "assets", "favicon.svg"))
            text_response(self, "404 not found", 404)
        except ValueError as e:
            json_response(self, {"error": str(e)}, 400)
        except Exception as e:                                  # noqa: BLE001
            json_response(self, {"error": "%s: %s" % (type(e).__name__, e)}, 500)

    def api_get(self, route, q):
        if route == "state":
            return json_response(self, state_payload())
        if route == "page":
            rel = (q.get("path") or [""])[0]
            full = content_path(rel)
            if not os.path.isfile(full):
                return json_response(self, {"error": "页面不存在"}, 404)
            with open(full, encoding="utf-8") as f:
                content = f.read()
            meta, _ = B.parse_frontmatter(content)
            return json_response(self, {"path": rel, "content": content, "meta": meta,
                                        "mtime": os.path.getmtime(full)})
        if route == "media":
            work = work_segment((q.get("work") or [""])[0])
            items = []
            base = os.path.join(ASSETS, work) if work else ASSETS
            if not _within(base, ASSETS):
                raise ValueError("作品目录不合法")
            if os.path.isdir(base):
                for dirpath, dirnames, filenames in os.walk(base):
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                    for name in sorted(filenames):
                        if os.path.splitext(name)[1].lower() in IMAGE_EXT:
                            items.append({
                                "name": name,
                                "url": "/media/" + os.path.relpath(
                                    os.path.join(dirpath, name), ASSETS).replace(os.sep, "/"),
                                "bytes": os.path.getsize(os.path.join(dirpath, name)),
                            })
            return json_response(self, {"items": items})
        if route == "settings":
            path = os.path.join(ROOT, "wiki.config.json")
            with open(path, encoding="utf-8") as f:
                return json_response(self, {"json": f.read(), "data": json.load(f)})
        if route == "work":
            d = (q.get("dir") or [""])[0]
            path = os.path.join(CONTENT, d, "_作品.json")
            if not os.path.isfile(path):
                return json_response(self, {"error": "找不到作品配置"}, 404)
            with open(path, encoding="utf-8") as f:
                return json_response(self, {"json": f.read(), "data": json.load(f)})
        if route == "build-log":
            return json_response(self, _last_build)
        if route == "diff":
            rel = (q.get("path") or [""])[0]
            code, out, err = git("diff", "--no-color", "--", "content/" + rel)
            code2, out2, _ = git("diff", "--no-color", "--cached", "--", "content/" + rel)
            return json_response(self, {"diff": (out + "\n" + out2).strip(), "error": err})
        return json_response(self, {"error": "未知接口 %s" % route}, 404)

    # -------------------------------------------------- POST

    def do_POST(self):
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception as e:                                  # noqa: BLE001
            return json_response(self, {"error": "请求体不是合法 JSON：%s" % e}, 400)
        try:
            if path == "/api/save":
                return self.api_save(data)
            if path == "/api/new":
                return self.api_new(data)
            if path == "/api/rename":
                return self.api_rename(data)
            if path == "/api/delete":
                return self.api_delete(data)
            if path == "/api/preview":
                return json_response(self, render_preview(data.get("path", ""),
                                                          data.get("content", "")))
            if path == "/api/upload":
                return self.api_upload(data)
            if path == "/api/build":
                return json_response(self, run_build())
            if path == "/api/settings":
                return self.api_settings(data)
            if path == "/api/work":
                return self.api_work(data)
            if path == "/api/git/commit":
                return self.api_commit(data)
            if path == "/api/git/push":
                code, out, err = git("push", timeout=180)
                return json_response(self, {"ok": code == 0, "output": out, "error": err})
            if path == "/api/git/pull":
                code, out, err = git("pull", "--ff-only", timeout=180)
                return json_response(self, {"ok": code == 0, "output": out, "error": err})
            if path == "/api/git/init-remote":
                return self.api_init_remote(data)
        except ValueError as e:
            return json_response(self, {"error": str(e)}, 400)
        except Exception as e:                                  # noqa: BLE001
            return json_response(self, {"error": "%s: %s" % (type(e).__name__, e)}, 500)
        return json_response(self, {"error": "未知接口 %s" % path}, 404)

    # -------------------------------------------------- 具体动作

    def api_save(self, data):
        rel = data.get("path", "")
        full = content_path(rel)
        content = data.get("content", "")
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return json_response(self, {"ok": True, "path": rel, "bytes": len(content.encode("utf-8")),
                                    "mtime": os.path.getmtime(full)})

    def api_new(self, data):
        name = safe_name(data.get("name", ""))
        work = work_segment(data.get("work"))
        category = (data.get("category") or "").strip().strip("/")
        if category and any(seg in (".", "..") for seg in category.split("/")):
            raise ValueError("分类名不合法：%s" % data.get("category"))
        if data.get("atRoot"):
            rel = "%s.md" % name
        else:
            if not work:
                raise ValueError("请选择所属作品")
            if not os.path.isdir(os.path.join(CONTENT, work)):
                raise ValueError("作品目录不存在：%s" % work)
            rel = posixpath.join(work, category, name + ".md") if category else \
                posixpath.join(work, name + ".md")
        full = content_path(rel)
        if os.path.exists(full):
            raise ValueError("「%s」已经存在了" % rel)
        content = data.get("content")
        if not content:
            tpl = (data.get("template") or "人物")
            content = TEMPLATES.get(tpl, TEMPLATES["空页面"]).replace("{{NAME}}", name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        return json_response(self, {"ok": True, "path": rel})

    def api_rename(self, data):
        rel = data.get("path", "")
        new_name = safe_name(data.get("name", ""))
        full = content_path(rel)
        if not os.path.isfile(full):
            raise ValueError("页面不存在")
        target_rel = posixpath.join(posixpath.dirname(rel), new_name + ".md")
        target = content_path(target_rel)
        if os.path.exists(target):
            raise ValueError("「%s」已经存在了" % new_name)
        os.rename(full, target)
        return json_response(self, {"ok": True, "path": target_rel.replace(os.sep, "/")})

    def api_delete(self, data):
        rel = data.get("path", "")
        full = content_path(rel)
        if not os.path.isfile(full):
            raise ValueError("页面不存在")
        dest_dir = os.path.join(TRASH, time.strftime("%Y%m%d-%H%M%S"))
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(full, os.path.join(dest_dir, os.path.basename(full)))
        return json_response(self, {"ok": True, "trash": os.path.relpath(
            os.path.join(dest_dir, os.path.basename(full)), ROOT).replace(os.sep, "/")})

    def api_upload(self, data):
        name = safe_name(os.path.basename(data.get("name", "")))
        work = work_segment(data.get("work"))
        data_url = data.get("dataUrl", "")
        m = re.match(r"^data:([^;]+);base64,(.*)$", data_url, re.S)
        if not m:
            raise ValueError("图片数据格式不对")
        ext = os.path.splitext(name)[1].lower()
        if ext not in IMAGE_EXT:
            raise ValueError("不支持的文件类型：%s" % ext)
        blob = base64.b64decode(m.group(2))
        if len(blob) > 25 * 1024 * 1024:
            raise ValueError("图片超过 25MB")
        dest_dir = os.path.join(ASSETS, work) if work else ASSETS
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, name)
        n = 1
        while os.path.exists(dest):
            stem, ext2 = os.path.splitext(name)
            dest = os.path.join(dest_dir, "%s_%d%s" % (stem, n, ext2))
            n += 1
        with open(dest, "wb") as f:
            f.write(blob)
        return json_response(self, {
            "ok": True, "name": os.path.basename(dest),
            "url": "/media/" + os.path.relpath(dest, ASSETS).replace(os.sep, "/"),
            "bytes": len(blob)})

    def api_settings(self, data):
        raw = data.get("json")
        if raw is None:
            raise ValueError("缺少 json 字段")
        parsed = json.loads(raw)                                 # 校验
        path = os.path.join(ROOT, "wiki.config.json")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return json_response(self, {"ok": True})

    def api_work(self, data):
        d = work_segment(data.get("dir"))
        if not d:
            raise ValueError("作品目录不合法")
        raw = data.get("json")
        parsed = json.loads(raw)
        path = os.path.join(CONTENT, d, "_作品.json")
        if not os.path.isfile(path):
            raise ValueError("找不到 %s/_作品.json" % d)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return json_response(self, {"ok": True})

    def api_commit(self, data):
        msg = (data.get("message") or "").strip() or "更新 wiki 内容"
        if data.get("addAll", True):
            code, out, err = git("add", "-A")
            if code != 0:
                return json_response(self, {"ok": False, "output": out, "error": err})
        code, out, err = git("commit", "-m", msg, timeout=120)
        return json_response(self, {"ok": code == 0, "output": out, "error": err})

    def api_init_remote(self, data):
        url = (data.get("url") or "").strip()
        if not url.startswith("http"):
            raise ValueError("请填 https://github.com/用户名/仓库名.git")
        code, out, err = git("remote", "get-url", "origin")
        if code == 0:
            code, out, err = git("remote", "set-url", "origin", url)
        else:
            code, out, err = git("remote", "add", "origin", url)
        if code != 0:
            return json_response(self, {"ok": False, "error": err or out})
        code2, out2, err2 = git("branch", "-M", "main")
        return json_response(self, {"ok": code2 == 0, "output": "已设置 origin = %s\n%s" % (url, out2),
                                    "error": err2})

    # -------------------------------------------------- 静态文件

    def serve_file(self, full):
        full = os.path.normpath(full)
        allowed = any(_within(full, base) for base in (EDITOR_DIR, DOCS, ASSETS))
        if not allowed or not os.path.isfile(full):
            return text_response(self, "404 not found", 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "image/svg+xml"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


# ------------------------------------------------------------------ 模板

TEMPLATES = {
    "人物": """---
标签: []
---

> [!info] {{NAME}}
> ![[占位图.jpg|150]]
> - **日文姓名**：
> - **真名**：{{NAME}}
> - **性别**：
> - **年龄**：
> - **出身地区**：
> - **变成的宝可梦**：
> - **归属**：

---

## 角色形象

## 第一季

## 名字来源

""",
    "组织": """---
标签: [组织]
---

> [!info] {{NAME}}
> ![[占位图.jpg|150]]
> - **类型**：
> - **目标**：
> - **活动地区**：
> - **主要成员**：

---

## 概述

## 经历

""",
    "地点": """---
标签: [地点]
---

> [!info] {{NAME}}
> ![[占位图.jpg|150]]
> - **类型**：
> - **所在地区**：
> - **登场作品**：

---

## 概述

## 名字来由

""",
    "事件": """---
标签: [事件]
---

## 概述

## 经过

## 影响

""",
    "名词": """---
标签: [设定]
---

## 定义

## 说明

""",
    "空页面": """---
标签: []
---

## {{NAME}}

""",
}


def main():
    ap = argparse.ArgumentParser(description="nijiboshi-wiki 本地编辑器")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(CONTENT):
        sys.exit("找不到 content/ 目录：%s" % CONTENT)
    os.makedirs(TRASH, exist_ok=True)

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("wiki 编辑器已启动：%s" % url)
    print("  · 内容目录：%s" % CONTENT)
    print("  · 预览站点：%s" % DOCS)
    print("  · 按 Ctrl+C 停止")
    if not args.no_open:
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n编辑器已停止。")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
