# -*- coding: utf-8 -*-
"""未公开作品的「客户端密码门」。

思路：正文（传给 render_layout 的 body）在构建期用 AES-GCM 加密，密文写在页面里，
浏览器端用 WebCrypto 拿密码现解。站点外壳（页头、侧栏、页脚、导航）照旧是明文，
所以外观不变；但**任何产出文件里都不能出现正文**。

- salt：每次构建随机 16 字节（公开无害），整个站点共用一个，所以解锁一页之后，
  同一作品的其他页面靠 sessionStorage 里的密钥自动解锁。
- 密钥：PBKDF2-SHA256(密码, salt, iterations) -> 32 字节。
- 每页一个随机 12 字节 IV，AES-GCM 加密。
- 密码只从环境变量 WIKI_GATE_PASSWORD 读，绝不写进任何会被提交的文件。

这是「防君子」：挡得住翻源码、挡得住搜索引擎，挡不住拿到密码的人转发。
"""

import base64
import hashlib
import html as _html
import json
import os
import secrets
import sys

from . import aesgcm

PASSWORD_ENV = "WIKI_GATE_PASSWORD"
PASSWORD_FILE = ".gate-password"
DEFAULT_ITERATIONS = 250000
DEFAULT_HINT = "本内容尚未公开。输入密码后查看。"

BOX_TMPL = """<div class="gate-box" id="gate-box">
  <div class="gate-title">🔒 需要密码</div>
  <p class="gate-hint">%(hint)s</p>
  <form id="gate-form">
    <input type="password" id="gate-pass" autocomplete="current-password" placeholder="密码">
    <button type="submit">解锁</button>
  </form>
  <p class="gate-msg" id="gate-msg"></p>
  <noscript>本页内容已加密，需要启用 JavaScript 才能查看。</noscript>
</div>
<div class="gate-content" id="gate-content" hidden></div>
<script type="application/json" id="gate-data">%(data)s</script>"""


def b64(data):
    return base64.b64encode(data).decode("ascii")


class Gate:
    """一次构建的密码门：持有 salt 与派生密钥，负责把正文换成密文。"""

    def __init__(self, works, password, hint=None, iterations=DEFAULT_ITERATIONS):
        self.works = {str(w) for w in works}
        self.hint = str(hint).strip() if hint else DEFAULT_HINT
        try:
            self.iterations = int(iterations)
        except (TypeError, ValueError):
            sys.exit("gate.iterations 必须是整数，收到 %r" % (iterations,))
        if self.iterations < 1:
            sys.exit("gate.iterations 必须大于 0，收到 %r" % (iterations,))
        self.salt = secrets.token_bytes(16)
        self.key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), self.salt,
                                       self.iterations, 32)

    # -------------------------------------------------- 判断与加密
    def covers(self, work_dirname):
        """这个作品目录是否属于加密范围。"""
        return bool(work_dirname) and work_dirname in self.works

    def encrypt(self, plaintext, page_title="", doc_title=""):
        """加密一段正文，返回写进 #gate-data 的载荷。

        标题也一起塞进密文：外壳里不能出现条目名（否则对着 docs/ grep 一下
        就知道未公开作品里有哪些条目了），但解锁之后标签页和页头要还原成
        真正的标题，所以标题必须跟着密文走。
        """
        iv = secrets.token_bytes(12)
        envelope = json.dumps({"h": plaintext, "p": str(page_title or ""),
                               "d": str(doc_title or "")}, ensure_ascii=False)
        ct = aesgcm.seal(self.key, iv, envelope.encode("utf-8"))
        return {"v": 2, "iter": self.iterations, "salt": b64(self.salt),
                "iv": b64(iv), "ct": b64(ct)}

    # -------------------------------------------------- 输出片段
    def payload_json(self, payload):
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def box_html(self, payload):
        """密码门本体：这段 HTML 会替换掉原来的页面正文。"""
        return BOX_TMPL % {"hint": _html.escape(self.hint),
                           "data": self.payload_json(payload)}

    def script_tag(self, prefix, asset_ver=""):
        """gate.js 的引入标签，带上和其他脚本一样的缓存指纹。"""
        ver = "?v=%s" % _html.escape(str(asset_ver)) if asset_ver else ""
        return '<script src="%sassets/gate.js%s"></script>' % (prefix, ver)

    def body_fragment(self, plaintext, prefix, asset_ver=""):
        """加密页正文 + 脚本（渲染完整页面时用）。"""
        return (self.box_html(self.encrypt(plaintext)) +
                "\n" + self.script_tag(prefix, asset_ver))

    # -------------------------------------------------- 构建期自检
    def check_no_leak(self, out_path, html, plaintext):
        """构建期硬护栏：加密页的 HTML 里一旦出现明文正文，立刻中止构建。"""
        if plaintext and plaintext in html:
            sys.exit("构建中止：加密页 %s 的 HTML 里出现了明文正文。"
                     "这是密码门失效的严重问题，请检查 build.py 里替换正文的那一步。" % out_path)


def gate_from_config(cfg, works):
    """按配置和环境变量准备密码门；没配 gate.works 就返回 None。

    两条硬规则：
      1. 配了加密作品却没给 WIKI_GATE_PASSWORD -> 直接退出，绝不明文照发；
      2. gate.works 里写了 content/ 下不存在的目录名 -> 直接退出，
         否则拼错一个字就等于把该作品按明文发布出去。
    """
    conf = cfg.get("gate") or {}
    names = [str(x).strip() for x in (conf.get("works") or []) if str(x).strip()]
    if not names:
        return None

    missing = [n for n in names if n not in works]
    if missing:
        sys.exit("gate.works 里的作品在 content/ 下找不到：%s\n"
                 "（目录名必须和 content/ 下的作品目录完全一致，"
                 "否则这些页面会被当成普通页面按明文发布。）" % "、".join(missing))

    password = os.environ.get(PASSWORD_ENV, "")
    if not password:
        # 也支持放在仓库根目录的 .gate-password（已在 .gitignore 里，不会提交），
        # 这样本地编辑器和直接跑 build.py 都不用带环境变量。
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            PASSWORD_FILE)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    password = f.read().strip()
            except OSError:
                password = ""
    if not password:
        sys.exit("作品 %s 需要密码：请设置环境变量 %s，或在仓库根目录建一个 %s 文件。例如：\n"
                 "    %s=你的密码 python3 build.py\n"
                 "不设置就直接构建会把未公开的正文以明文写进 docs/，所以这里拒绝继续。"
                 % ("、".join(names), PASSWORD_ENV, PASSWORD_FILE, PASSWORD_ENV))

    return Gate(names, password, conf.get("hint"), conf.get("iterations", DEFAULT_ITERATIONS))
