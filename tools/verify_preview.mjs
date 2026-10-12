#!/usr/bin/env node
// 词条悬停预览的行为验证：用最小 DOM 桩加载真实的 docs/assets/theme.js，
// 喂真实的 docs/previews.json，模拟鼠标进入 / 移开 / Esc，检查卡片。
//
// 用法：node tools/verify_preview.mjs
//
// 桩里没有真排版，只实现 theme.js 真正用到的那几个接口：
// getElementById / addEventListener / closest / contains / appendChild /
// removeChild / getBoundingClientRect / innerHTML / matchMedia / fetch。
// 时间用手动时钟推进，所以「等 400ms」是确定性的，不靠 sleep。

import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const THEME_JS = fs.readFileSync(path.join(ROOT, "docs/assets/theme.js"), "utf8");
const PREVIEWS = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/previews.json"), "utf8"));

const tick = () => new Promise((resolve) => setImmediate(resolve));
const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok, detail });
  console.log(`${ok ? "  ✅" : "  ❌"} ${name}${detail ? "  — " + detail : ""}`);
}

// --------------------------------------------------------------- DOM 桩
class ClassList {
  constructor(el) { this.el = el; this.set = new Set(); }
  _sync() { this.el._className = [...this.set].join(" "); }
  add(...c) { c.forEach((x) => this.set.add(x)); this._sync(); }
  remove(...c) { c.forEach((x) => this.set.delete(x)); this._sync(); }
  contains(c) { return this.set.has(c); }
  toggle(c, force) {
    const on = force === undefined ? !this.set.has(c) : !!force;
    if (on) this.set.add(c); else this.set.delete(c);
    this._sync();
    return on;
  }
}

class El {
  constructor(tag, doc) {
    this.tagName = String(tag).toUpperCase();
    this.doc = doc;
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.style = {};
    this.innerHTML = "";
    this.textContent = "";
    this._className = "";
    this._id = "";
    this._listeners = {};
    this.classList = new ClassList(this);
    this.offsetWidth = 340;
    this.offsetHeight = 120;
  }
  get className() { return this._className; }
  set className(v) {
    this._className = String(v);
    this.classList.set = new Set(this._className.split(/\s+/).filter(Boolean));
  }
  get id() { return this._id; }
  set id(v) { this._id = String(v); if (this._id) this.doc._ids.set(this._id, this); }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
    if (k === "id") this.id = v;
    if (k === "class") this.className = v;
  }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; }
  appendChild(node) { node.parentNode = this; this.children.push(node); return node; }
  removeChild(node) {
    const i = this.children.indexOf(node);
    if (i >= 0) this.children.splice(i, 1);
    node.parentNode = null;
    return node;
  }
  remove() { if (this.parentNode) this.parentNode.removeChild(this); }
  contains(node) { for (let n = node; n; n = n.parentNode) if (n === this) return true; return false; }
  closest(sel) { for (let n = this; n; n = n.parentNode) if (n.matches(sel)) return n; return null; }
  matches(sel) {
    const m = /^([a-zA-Z]+)?(?:\.([\w-]+))?$/.exec(sel.trim());
    if (!m) return false;
    const [, tag, cls] = m;
    if (tag && this.tagName !== tag.toUpperCase()) return false;
    if (cls && !this.classList.contains(cls)) return false;
    return true;
  }
  addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); }
  dispatch(type, ev = {}) { (this._listeners[type] || []).forEach((fn) => fn({ type, target: this, ...ev })); }
  setRect(r) { this._rect = r; }
  getBoundingClientRect() {
    return this._rect || { left: 100, top: 300, right: 220, bottom: 318, width: 120, height: 18 };
  }
}

class Doc {
  constructor() {
    this._ids = new Map();
    this._listeners = {};
    this.body = new El("body", this);
    this.documentElement = new El("html", this);
    this.documentElement.clientWidth = 1280;
    this.documentElement.clientHeight = 800;
  }
  createElement(tag) { return new El(tag, this); }
  // 从 body 往下找：卡片被 remove() 之后就不该再被找到（getElementById 认的是文档树）
  getElementById(id) {
    const walk = (n) => {
      if (n.id === id) return n;
      for (const c of n.children) { const hit = walk(c); if (hit) return hit; }
      return null;
    };
    return walk(this.body);
  }
  querySelectorAll() { return []; }
  addEventListener(type, fn) { (this._listeners[type] ||= []).push(fn); }
  dispatch(type, ev) { (this._listeners[type] || []).forEach((fn) => fn(ev)); }
}

// --------------------------------------------------------------- 沙箱
function makeWorld({ hover = true, page = "青梅竹马失踪后变成电飞鼠这档事/人物/暗镜.html" } = {}) {
  const doc = new Doc();
  const input = doc.createElement("input");
  input.setAttribute("id", "wiki-search-input");
  input.setAttribute("data-index", "../../search.json");
  doc.body.appendChild(input);

  const timers = new Map();
  let now = 0;
  let seq = 1;
  const fetched = [];

  const sandbox = {
    document: doc,
    console,
    location: { href: "http://127.0.0.1:8000/" + encodeURI(page), pathname: "/" + encodeURI(page), search: "" },
    URL,
    Promise,
    Math,
    JSON,
    decodeURIComponent,
    encodeURIComponent,
    setTimeout(fn, ms) { const id = seq++; timers.set(id, { at: now + (ms || 0), fn }); return id; },
    clearTimeout(id) { timers.delete(id); },
    fetch(url) {
      fetched.push(url);
      return Promise.resolve({ json: () => Promise.resolve(PREVIEWS) });
    },
    localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: hover, media: "(hover: hover) and (pointer: fine)" }),
    innerWidth: 1280,
    innerHeight: 800,
    addEventListener(type, fn) {
      this._win = this._win || {};
      this._win[type] = this._win[type] || [];
      this._win[type].push(fn);
    },
    dispatchWindow(type, ev) { ((this._win || {})[type] || []).forEach((fn) => fn(ev)); },
  };
  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;

  const ctx = vm.createContext(sandbox);
  vm.runInContext(THEME_JS, ctx, { filename: "docs/assets/theme.js" });

  return {
    doc, sandbox, fetched,
    advance(ms) {
      const target = now + ms;
      for (;;) {
        const due = [...timers.entries()].filter(([, t]) => t.at <= target)
          .sort((a, b) => a[1].at - b[1].at)[0];
        if (!due) break;
        timers.delete(due[0]);
        now = due[1].at;
        due[1].fn();
      }
      now = target;
    },
  };
}

function cards(doc) {
  return doc.body.children.filter((c) => c.classList.contains("pv-card"));
}
function link(doc, href, cls = "wikilink") {
  const a = doc.createElement("a");
  a.className = cls;
  a.setAttribute("href", href);
  doc.body.appendChild(a);
  return a;
}
function findItem(pred) { return PREVIEWS.find(pred); }
const dec = (s) => decodeURIComponent(s);

async function main() {
  console.log("theme.js:", path.relative(ROOT, path.join(ROOT, "docs/assets/theme.js")),
              "· previews.json 条目 " + PREVIEWS.length);

  const target = findItem((i) => dec(i.u) === "青梅竹马失踪后变成电飞鼠这档事/人物/上鹈.html");
  if (!target) throw new Error("previews.json 里找不到「上鹈」，测试无法进行");

  // ------------------------------------------------ 1. 悬停 → 卡片
  const w = makeWorld();
  const a = link(w.doc, "%E4%B8%8A%E9%B9%88.html");     // 与当前页同目录的兄弟链接

  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  check("延迟未到时没有卡片", cards(w.doc).length === 0);

  w.advance(450);
  await tick(); await tick();

  let card = w.doc.getElementById("pv-card");
  check("悬停 400ms 后创建卡片", !!card);
  check("同一时间只有一张卡片", cards(w.doc).length === 1);
  check("标题正确", !!card && card.innerHTML.includes(target.t), `t=${target.t}`);
  check("摘要正确", !!card && card.innerHTML.includes(target.x.slice(0, 24)),
        `x=${target.x.slice(0, 24)}…`);
  check("摘要不是 [ 编辑 ] 那种脏文本", !!card && !card.innerHTML.includes("[ 编辑 ]"));
  check("缩略图用信息框里的图", !!card && card.innerHTML.includes("../../assets/" + encodeURIComponent("青梅竹马失踪后变成电飞鼠这档事") + "/Kamiu_Front.jpg"));
  check("有「查看条目」链接", !!card && card.innerHTML.includes("查看条目"));
  check("卡片落在视口内",
        !!card && parseFloat(card.style.left) >= 8 && parseFloat(card.style.top) >= 8 &&
        parseFloat(card.style.left) + 340 <= 1280 && parseFloat(card.style.top) + 120 <= 800,
        `left=${card.style.left} top=${card.style.top}`);
  check("previews.json 带了缓存指纹",
        w.fetched.length === 1 && /^\.\.\/\.\.\/previews\.json\?v=.+/.test(w.fetched[0]),
        w.fetched[0]);

  // ------------------------------------------------ 2. 同一链接不重复建 DOM
  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  check("再次进入同一链接不会多出卡片", cards(w.doc).length === 1);
  check("卡片还是同一张 DOM", w.doc.getElementById("pv-card") === card);

  // ------------------------------------------------ 3. 鼠标移开 → 收起
  w.doc.dispatch("mouseout", { target: a, relatedTarget: null });
  w.advance(300);
  check("鼠标移开（宽限期后）卡片被移除", w.doc.getElementById("pv-card") === null && cards(w.doc).length === 0);

  // ------------------------------------------------ 4. Esc 关闭
  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  check("Esc 之前卡片在", !!w.doc.getElementById("pv-card"));
  w.doc.dispatch("keydown", { key: "Escape" });
  check("Esc 能关掉卡片", w.doc.getElementById("pv-card") === null);

  // ------------------------------------------------ 5. 滚动 / 点击别处
  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  w.sandbox.dispatchWindow("scroll", {});
  check("页面滚动收起卡片", w.doc.getElementById("pv-card") === null);

  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  w.doc.dispatch("click", { target: w.doc.body });
  check("点击别处收起卡片", w.doc.getElementById("pv-card") === null);

  // ------------------------------------------------ 6. 加密作品不弹卡片
  const gated = link(w.doc, "../../%E6%83%B3%E8%A6%81%E9%A3%9E%E7%9A%84%E5%A7%8B%E7%A5%96%E5%B0%8F%E9%B8%9F/%E4%BA%BA%E7%89%A9/fa9cb0d6b560.html");
  w.doc.dispatch("mouseover", { target: gated, relatedTarget: null });
  w.advance(600);
  await tick(); await tick();
  check("指向加密作品的链接不弹卡片", w.doc.getElementById("pv-card") === null);
  check("previews.json 里没有加密作品的条目",
        !PREVIEWS.some((i) => dec(i.u).startsWith("想要飞的始祖小鸟/")));

  // 不存在的条目（红色链接是 a.new，本来就不在 a.wikilink 里）
  const redLink = link(w.doc, "missing.html?page=%E8%AF%AD%E6%B5%B7", "new");
  w.doc.dispatch("mouseover", { target: redLink, relatedTarget: null });
  w.advance(600);
  await tick(); await tick();
  check("红色（不存在）链接不弹卡片", w.doc.getElementById("pv-card") === null);

  // ------------------------------------------------ 7. href 还原：../ 与 # 锚点、?query
  const chaos = findItem((i) => dec(i.u) === "青梅竹马失踪后变成电飞鼠这档事/特殊名词/超能力.html");
  const up = link(w.doc, "../%E7%89%B9%E6%AE%8A%E5%90%8D%E8%AF%8D/%E8%B6%85%E8%83%BD%E5%8A%9B.html?x=1#sec-1");
  w.doc.dispatch("mouseover", { target: up, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  card = w.doc.getElementById("pv-card");
  check("href 带 ../ 与 # 锚点也能对上条目",
        !!card && !!chaos && card.innerHTML.includes(chaos.t), `t=${chaos && chaos.t}`);

  // 外链（同样挂着 wikilink 类）不弹
  w.doc.dispatch("mouseout", { target: up, relatedTarget: null });
  w.advance(300);
  const ext = link(w.doc, "https://wiki.52poke.com/wiki/%E4%B8%8A%E9%B9%88");
  w.doc.dispatch("mouseover", { target: ext, relatedTarget: null });
  w.advance(600);
  await tick(); await tick();
  check("站外 http 链接不弹卡片", w.doc.getElementById("pv-card") === null);

  // 链到当前页自己不弹（Wikipedia 也不弹）
  const self = link(w.doc, encodeURI("青梅竹马失踪后变成电飞鼠这档事/人物/暗镜.html"));
  w.doc.dispatch("mouseover", { target: self, relatedTarget: null });
  w.advance(600);
  await tick(); await tick();
  check("指向当前页自身的链接不弹卡片", w.doc.getElementById("pv-card") === null);

  // ------------------------------------------------ 8. 贴边定位
  a.setRect({ left: 1200, top: 300, right: 1320, bottom: 318, width: 120, height: 18 });   // 贴右
  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  card = w.doc.getElementById("pv-card");
  check("链接贴右边时卡片左移、不溢出",
        !!card && parseFloat(card.style.left) + 340 <= 1280 && parseFloat(card.style.left) >= 8,
        `left=${card && card.style.left}`);
  w.doc.dispatch("mouseout", { target: a, relatedTarget: null });
  w.advance(300);

  a.setRect({ left: 100, top: 780, right: 220, bottom: 798, width: 120, height: 18 });     // 贴底
  w.doc.dispatch("mouseover", { target: a, relatedTarget: null });
  w.advance(450);
  await tick(); await tick();
  card = w.doc.getElementById("pv-card");
  check("链接贴视口底部时卡片显示在链接上方",
        !!card && parseFloat(card.style.top) + 120 <= 800 && parseFloat(card.style.top) < 780,
        `top=${card && card.style.top}`);
  check("索引只取了一次", w.fetched.length === 1, `fetch ${w.fetched.length} 次`);

  // ------------------------------------------------ 9. 触屏设备整套不启用
  const touch = makeWorld({ hover: false });
  const ta = link(touch.doc, "%E4%B8%8A%E9%B9%88.html");
  touch.doc.dispatch("mouseover", { target: ta, relatedTarget: null });
  touch.advance(1000);
  await tick(); await tick();
  check("没有 hover 的设备不弹卡片", cards(touch.doc).length === 0);
  check("没有 hover 的设备也不去取索引", touch.fetched.length === 0);

  // ------------------------------------------------ 汇总
  const failed = results.filter((r) => !r.ok);
  console.log();
  if (failed.length) {
    console.log(`❌ ${failed.length}/${results.length} 项未通过`);
    process.exit(1);
  }
  console.log(`✅ ${results.length} 项全部通过`);
}

main().catch((e) => { console.error(e); process.exit(1); });
