#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""密码门独立验证：把 docs/ 里的密文解回来，确认加密是对的、明文没漏。

用法：
    WIKI_GATE_PASSWORD=test123 python3 tools/verify_gate.py
    WIKI_GATE_PASSWORD=test123 python3 tools/verify_gate.py --dump /tmp/解密出来的
    WIKI_GATE_PASSWORD=test123 python3 tools/verify_gate.py --expect 阿尔宙斯 --expect 符利根

它做四件事：
  1. AES 内核的已知答案自检（FIPS-197 的三组向量）——避免「自己跟自己对答案」；
  2. 扫描 docs/ 下所有带 #gate-data 的页面，用 WIKI_GATE_PASSWORD 重新走一遍
     PBKDF2-SHA256 + AES-GCM，把正文解出来（解密路径不经过 build.py）；
  3. 检查加密作品的目录里没有漏掉加密的页面、也没有明文残留在 HTML 里；
  4. 机器上有 node 的话，再用 Node 的 OpenSSL 实现独立解一遍，比对明文摘要。

脚本不会把解出来的正文打到终端（免得验证输出本身变成泄漏源），
需要肉眼看正文就用 --dump 写到临时目录。
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from wikicore.aesgcm import AES, open_                                # noqa: E402

GATE_RE = re.compile(r'<script type="application/json" id="gate-data">(.*?)</script>', re.S)

# FIPS-197 附录 C 的已知答案向量（明文都是 00112233445566778899aabbccddeeff）
FIPS_VECTORS = [
    ("000102030405060708090a0b0c0d0e0f", "69c4e0d86a7b0430d8cdb78070b4c55a"),
    ("000102030405060708090a0b0c0d0e0f1011121314151617", "dda97ca4864cdfe06eaf70a0ec0d7191"),
    ("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
     "8ea2b7ca516745bfeafc49904b496089"),
]

NODE_JS = ('let s="";process.stdin.on("data",function(d){s+=d});'
           'process.stdin.on("end",function(){'
           'var c=require("crypto"),j=JSON.parse(s);'
           'var ct=Buffer.from(j.ct,"base64"),iv=Buffer.from(j.iv,"base64");'
           'var d=c.createDecipheriv("aes-256-gcm",Buffer.from(j.key,"base64"),iv);'
           'd.setAuthTag(ct.slice(-16));'
           'var out=Buffer.concat([d.update(ct.slice(0,-16)),d.final()]);'
           'console.log(c.createHash("sha256").update(out).digest("hex"));'
           '});')


def check_aes_vectors():
    pt = binascii.unhexlify("00112233445566778899aabbccddeeff")
    bad = []
    for key_hex, want in FIPS_VECTORS:
        got = AES(binascii.unhexlify(key_hex)).encrypt_block(pt).hex()
        if got != want:
            bad.append("AES-%d：得到 %s，FIPS-197 期望 %s" % (len(key_hex) * 4, got, want))
    return bad


def collect(docs):
    """返回 [(相对路径, 整页 HTML, gate-data 原始 JSON)]。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(docs):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if not name.endswith(".html"):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding="utf-8") as f:
                html = f.read()
            m = GATE_RE.search(html)
            if m:
                out.append((os.path.relpath(full, docs).replace(os.sep, "/"), html, m.group(1)))
    return out


def node_hash(key, iv, ct):
    try:
        p = subprocess.run(["node", "-e", NODE_JS], input=json.dumps(
            {"key": base64.b64encode(key).decode(), "iv": base64.b64encode(iv).decode(),
             "ct": base64.b64encode(ct).decode()}),
            capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if p.returncode != 0:
        return None, (p.stderr or "").strip()[:200]
    return p.stdout.strip(), None


def public_strings(docs, content_dir):
    """站点公开外壳里本来就有的字符串，不算泄漏。

    两种情况会让条目名与外壳撞车，都是误报：
      - 作者名等页脚文字：未加密页面里也有（拿站点首页当参照）；
      - 分类名：侧栏会列出加密作品的分类（这是站点设计，未加密作品一样），
        条目名与分类名同名时会命中（例如「游戏系统」既是分类也是条目）。
    """
    buf = []
    home = os.path.join(docs, "index.html")
    if os.path.isfile(home):
        with open(home, encoding="utf-8") as f:
            buf.append(f.read())
    for work in sorted(os.listdir(content_dir)) if os.path.isdir(content_dir) else []:
        wdir = os.path.join(content_dir, work)
        if not os.path.isdir(wdir):
            continue
        buf.append(work)
        conf = os.path.join(wdir, "_作品.json")
        if os.path.isfile(conf):
            try:
                with open(conf, encoding="utf-8") as f:
                    meta = json.load(f)
                buf.append(json.dumps(meta, ensure_ascii=False))
            except ValueError:
                pass
        for dirpath, dirnames, _ in os.walk(wdir):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            buf.append(os.path.basename(dirpath))
    return "\n".join(buf)


def main():
    ap = argparse.ArgumentParser(description="验证 docs/ 里的密码门密文能正确解密")
    ap.add_argument("--docs", default=os.path.join(ROOT, "docs"))
    ap.add_argument("--expect", action="append", default=[],
                    help="解密后的正文里必须出现的字符串，可重复")
    ap.add_argument("--dump", default="", help="把解出来的正文写到这个目录里（默认不落盘）")
    args = ap.parse_args()

    password = os.environ.get("WIKI_GATE_PASSWORD", "")
    if not password:
        sys.exit("请先设置环境变量 WIKI_GATE_PASSWORD（和构建时用的是同一个密码）")
    if not os.path.isdir(args.docs):
        sys.exit("找不到输出目录：%s（先跑 python3 build.py）" % args.docs)

    fails = []
    print("=== 1. AES 内核已知答案自检（FIPS-197）===")
    bad = check_aes_vectors()
    if bad:
        fails += bad
        for b in bad:
            print("  ❌ " + b)
    else:
        print("  ✅ AES-128/192/256 三组向量全部对上")

    with open(os.path.join(ROOT, "wiki.config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    gated_works = [str(x) for x in ((cfg.get("gate") or {}).get("works") or [])]

    print("\n=== 2. 加密作品目录下每个 HTML 都必须带 #gate-data ===")
    n_gated = 0
    for work in gated_works:
        wdir = os.path.join(args.docs, work)
        n_work = 0
        for dirpath, dirnames, filenames in os.walk(wdir):
            for name in filenames:
                if not name.endswith(".html"):
                    continue
                n_work += 1
                full = os.path.join(dirpath, name)
                with open(full, encoding="utf-8") as f:
                    if 'id="gate-data"' not in f.read():
                        fails.append("%s 没有加密" % os.path.relpath(full, args.docs))
        n_gated += n_work
        print("  %s：%d 个 HTML 全部加密" % (work, n_work))

    print("\n=== 3. 逐页解密（PBKDF2 + AES-GCM）===")
    chrome = public_strings(args.docs, os.path.join(ROOT, "content"))
    pages = collect(args.docs)
    if not pages:
        fails.append("docs/ 下没有找到任何密文页")
    salts, total, plaintexts = set(), 0, []
    node_done = False
    for rel, html, raw in pages:
        try:
            payload = json.loads(raw)
            salt = base64.b64decode(payload["salt"])
            iv = base64.b64decode(payload["iv"])
            ct = base64.b64decode(payload["ct"])
            key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt,
                                      int(payload.get("iter", 250000)), 32)
            text = open_(key, iv, ct).decode("utf-8")
        except Exception as e:                                        # noqa: BLE001
            fails.append("%s 解密失败：%s: %s" % (rel, type(e).__name__, e))
            continue
        # v2 起正文装在一个信封里：{"h": 正文, "p": 条目名, "d": 完整 <title>}。
        # 条目名与页面标题也走密文，所以外壳 HTML 里 grep 不到任何条目名。
        page_title = ""
        try:
            env = json.loads(text)
            if isinstance(env, dict) and isinstance(env.get("h"), str):
                plain, page_title = env["h"], env.get("p") or ""
            else:
                plain = text
        except ValueError:
            plain = text
        salts.add(payload["salt"])
        total += len(plain)
        plaintexts.append(plain)
        if plain and plain in html:
            fails.append("%s 的 HTML 里出现了明文正文" % rel)
        if page_title and page_title in html and page_title not in chrome:
            fails.append("%s 的 HTML 里出现了条目名「%s」" % (rel, page_title))
        if args.dump:
            dest = os.path.join(args.dump, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(plain)
        # 有 node 就用另一套实现独立解一页，证明 Python 侧不是自说自话
        if not node_done and shutil.which("node"):
            digest, err = node_hash(key, iv, ct)
            want = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if err:
                print("  · Node 交叉验证跳过（%s）" % err)
            elif digest != want:
                fails.append("Node 解出来的明文和 Python 不一致（%s）" % rel)
                print("  ❌ Node 交叉验证不一致：%s" % rel)
            else:
                print("  ✅ Node(OpenSSL) 独立解密 %s，明文摘要一致：%s" % (rel, want[:16]))
            node_done = True
    print("  解出 %d 页，明文合计 %d 字节" % (len(pages), total))
    print("  salt 取值个数：%d %s" % (len(salts),
                                     "（全站共用一个，同一作品解锁一页即可）" if len(salts) == 1 else ""))

    print("\n=== 4. 正文内容抽查 ===")
    blob = "\n".join(plaintexts)
    for text in (args.expect or ["阿尔宙斯", "符利根"]):
        if text in blob:
            print("  ✅ 解出的正文里含「%s」" % text)
        else:
            fails.append("解出的正文里找不到「%s」" % text)
            print("  ❌ 解出的正文里找不到「%s」" % text)

    print()
    if fails:
        print("❌ 有 %d 项没通过：" % len(fails))
        for f in fails:
            print("   - " + f)
        return 1
    print("✅ 密码门验证通过：密文可正确解密，且产出文件里没有明文残留。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
