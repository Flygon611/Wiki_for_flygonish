/* assets/gate.js —— 未公开作品的客户端密码门。
 *
 * 纯浏览器端：PBKDF2-SHA256 派生密钥 + AES-GCM 解密，只用 WebCrypto，没有依赖。
 * 密文写在页面的 <script type="application/json" id="gate-data"> 里。
 *
 * 解锁一页后，密钥（base64）会存进 sessionStorage['wiki-gate-key']；
 * 因为整个站点每次构建只用一个 salt，同一作品的其他页面会直接自动解锁，不再问密码。
 */
(function () {
  "use strict";

  var dataEl = document.getElementById("gate-data");
  if (!dataEl) return;

  var box = document.getElementById("gate-box");
  var content = document.getElementById("gate-content");
  var msg = document.getElementById("gate-msg");
  var form = document.getElementById("gate-form");
  var input = document.getElementById("gate-pass");
  var KEY_STORE = "wiki-gate-key";

  var data = null;
  try { data = JSON.parse(dataEl.textContent || "{}"); } catch (e) { data = null; }
  if (!data || !data.ct || !data.iv || !data.salt || !content) return;

  function say(text) { if (msg) msg.textContent = text; }

  // ---------------------------------------------------------- base64 <-> ArrayBuffer
  function b64ToBytes(s) {
    var bin = atob(s), out = new Uint8Array(bin.length), i;
    for (i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  function bytesToB64(buf) {
    var bytes = new Uint8Array(buf), s = "", i;
    for (i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s);
  }

  // ---------------------------------------------------------- 环境检查
  // 非安全上下文（file://、http 的局域网地址）下 Chrome / Firefox 不提供 crypto.subtle，
  // 这时密码门根本没法解，必须说清楚，不能装作没事。
  if (!(window.crypto && window.crypto.subtle)) {
    say("这个页面需要 WebCrypto 才能解密，而浏览器只在安全上下文里提供它：" +
        "请用 https 访问，或在本地用 http://127.0.0.1 预览（直接双击打开的 file:// 页面不行）。");
    if (form) form.hidden = true;
    if (input) input.disabled = true;
    return;
  }

  // ---------------------------------------------------------- 密钥与解密
  function deriveKey(password) {
    var enc = new TextEncoder();
    return crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"])
      .then(function (base) {
        return crypto.subtle.deriveKey(
          { name: "PBKDF2", salt: b64ToBytes(data.salt),
            iterations: data.iter || 250000, hash: "SHA-256" },
          base, { name: "AES-GCM", length: 256 }, true, ["decrypt"]);
      });
  }

  function importKey(b64) {
    try {
      return crypto.subtle.importKey("raw", b64ToBytes(b64), { name: "AES-GCM" },
                                     false, ["decrypt"]);
    } catch (e) {
      return Promise.reject(e);
    }
  }

  function decryptWith(key) {
    return crypto.subtle.decrypt(
      { name: "AES-GCM", iv: b64ToBytes(data.iv), tagLength: 128 },
      key, b64ToBytes(data.ct)
    ).then(function (buf) {
      return new TextDecoder("utf-8").decode(buf);
    });
  }

  // ---------------------------------------------------------- 显示
  function jumpToHash() {
    var raw = location.hash.replace(/^#/, "");
    if (!raw) return;
    var id = raw;
    try { id = decodeURIComponent(raw); } catch (e) { /* 保持原样 */ }
    var el = document.getElementById(id) || document.getElementsByName(id)[0];
    if (el && el.scrollIntoView) el.scrollIntoView(true);
  }

  // 密文解出来是一个信封：h=正文，p=条目名，d=完整 <title>。
  // 标题也走了密文，所以外壳里不会留下条目名（grep 不到），
  // 但解锁之后标签页与页头要还原成真正的标题。
  function unwrap(text) {
    try {
      var o = JSON.parse(text);
      if (o && typeof o === "object" && typeof o.h === "string") return o;
    } catch (e) { /* 不是信封，按旧格式当整段正文处理 */ }
    return { h: text, p: "", d: "" };
  }

  function show(text) {
    var o = unwrap(text);
    content.innerHTML = o.h;
    content.hidden = false;
    if (box) box.style.display = "none";
    say("");      // 把「正在解密…」清掉，免得下次失败时还留着上一轮的字
    if (o.d) { try { document.title = o.d; } catch (e) { /* 忽略 */ } }
    if (o.p) {
      var h1 = document.querySelector("h1.page-title");
      if (h1) h1.textContent = o.p;
      var sub = document.querySelector(".page-subtitle");
      if (sub) sub.textContent = "";
    }
    jumpToHash();
  }

  function askPassword(text) {
    if (text) say(text);
    if (form) {
      form.addEventListener("submit", function (e) {
        e.preventDefault();
        submit();
      });
    }
    if (input) {
      try { input.focus(); } catch (e) { /* 忽略 */ }
    }
  }

  function submit() {
    var pass = input ? input.value : "";
    if (!pass) { say("请输入密码。"); return; }
    say("正在解密…");
    var key = null;
    deriveKey(pass).then(function (k) {
      key = k;
      return decryptWith(k);
    }).then(function (html) {
      // 记住密钥：同一作品的其他页面就不用再问一次了。
      return crypto.subtle.exportKey("raw", key).then(function (raw) {
        try { sessionStorage.setItem(KEY_STORE, bytesToB64(raw)); } catch (e) { /* 隐私模式下可能不给写 */ }
      }).catch(function () { /* 导出失败就算了，不影响本次解密 */ }).then(function () {
        show(html);
      });
    }).catch(function () {
      say("密码错误。");
      if (input) { try { input.select(); } catch (e) { /* 忽略 */ } }
    });
  }

  // ---------------------------------------------------------- 入口
  var cached = null;
  try { cached = sessionStorage.getItem(KEY_STORE); } catch (e) { cached = null; }

  if (cached) {
    importKey(cached).then(decryptWith).then(show).catch(function () {
      // 站点重新构建过（salt 变了）或者密钥坏了：清掉，老老实实重新输密码。
      try { sessionStorage.removeItem(KEY_STORE); } catch (e) { /* 忽略 */ }
      askPassword("上一个会话的密钥已失效，请重新输入密码。");
    });
  } else {
    askPassword("");
  }
})();
