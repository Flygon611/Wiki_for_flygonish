/* 见远观星集 · wiki 编辑器前端
   与后端 editor/serve.py 配套。所有渲染都走后台同一个 build.py 渲染器，保证所见即所得。 */
(function () {
  'use strict';

  var $ = function (s) { return document.querySelector(s); };
  var $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };

  var STATE = null;          // /api/state 的结果
  var current = null;        // { path, content, mtime }
  var mediaList = [];
  var dirty = false;
  var previewTimer = null;
  var buildTimer = null;
  var AC = { open: false, items: [], sel: 0, ctx: null };

  var LS = {
    get: function (k, d) { try { var v = localStorage.getItem('wikied:' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem('wikied:' + k, JSON.stringify(v)); } catch (e) {} }
  };

  /* ---------------------------------------------------------- 基础 */

  function api(path, opts) {
    opts = opts || {};
    return fetch(path, {
      method: opts.method || 'GET',
      headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      return r.json().catch(function () { return { error: 'HTTP ' + r.status }; })
        .then(function (j) {
          if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
          return j;
        });
    });
  }

  function toast(msg, kind) {
    var box = $('#toast');
    var el = document.createElement('div');
    el.className = 't' + (kind ? ' ' + kind : '');
    el.textContent = msg;
    box.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('on'); });
    setTimeout(function () {
      el.classList.remove('on');
      setTimeout(function () { el.remove(); }, 250);
    }, kind === 'err' ? 4200 : 2200);
  }

  function setDirty(v) {
    dirty = v;
    $('#dirty-dot').classList.toggle('on', v);
    document.title = (v ? '● ' : '') + '见远观星集 · 编辑器';
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function modal(html, opts) {
    opts = opts || {};
    var box = $('#modal');
    box.innerHTML = '<div class="box">' + html + '</div>';
    box.classList.add('on');
    return new Promise(function (resolve) {
      function close(v) { box.classList.remove('on'); box.innerHTML = ''; resolve(v); }
      box.addEventListener('click', function (e) { if (e.target === box) close(null); });
      $$('#modal [data-cancel]').forEach(function (b) { b.addEventListener('click', function () { close(null); }); });
      var ok = $('#modal [data-ok]');
      if (ok) ok.addEventListener('click', function () { close(opts.collect ? opts.collect() : true); });
      var first = $('#modal input, #modal textarea');
      if (first) { first.focus(); if (first.select) first.select(); }
      if (opts.onShown) opts.onShown();
      document.addEventListener('keydown', function esc(e) {
        if (!box.classList.contains('on')) { document.removeEventListener('keydown', esc); return; }
        if (e.key === 'Escape') { document.removeEventListener('keydown', esc); close(null); }
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && ok) ok.click();
      });
    });
  }

  /* ---------------------------------------------------------- 启动 */

  function init() {
    loadState().then(function () {
      wireTop(); wireToolbar(); wireTabs(); wireEditor(); wireMedia(); wireGit();
      // 支持 /#p=<页面路径> 直接打开某一页（方便收藏和排查）
      var hashPath = null;
      if (location.hash.indexOf('#p=') === 0) {
        try { hashPath = decodeURIComponent(location.hash.slice(3)); } catch (e) { hashPath = null; }
      }
      var last = hashPath || LS.get('lastPath', null);
      if (last && findPage(last)) openPage(last);
      else if (hashPath) { status('找不到页面：' + hashPath); renderTree(); }
      else status('从左边选一个页面开始');
    }).catch(function (e) { toast('加载失败：' + e.message, 'err'); });
  }

  function findPage(path) {
    if (!STATE) return null;
    return STATE.pages.filter(function (p) { return p.path === path; })[0] ||
           STATE.globals.filter(function (p) { return p.path === path; })[0] || null;
  }

  function loadState() {
    return api('/api/state').then(function (s) {
      STATE = s;
      renderTree();
      renderMediaWorkSelect();
      renderGit(s.git);
      renderBuildLog(s.lastBuild);
      $('#media-work').value = LS.get('mediaWork', STATE.works[0] ? STATE.works[0].dir : '');
      loadMedia();
    });
  }

  /* ---------------------------------------------------------- 页面树 */

  function renderTree() {
    var q = $('#page-filter').value.trim().toLowerCase();
    var tree = $('#page-tree');
    tree.innerHTML = '';
    var collapsed = LS.get('collapsed', {});
    var shown = 0;

    function item(p, indent) {
      var title = p.title || p.name;
      if (q && (title.toLowerCase().indexOf(q) < 0 && p.name.toLowerCase().indexOf(q) < 0)) return;
      shown++;
      var a = document.createElement('a');
      a.className = 'item' + (current && current.path === p.path ? ' on' : '');
      a.style.paddingLeft = (22 + indent * 12) + 'px';
      a.dataset.path = p.path;
      a.innerHTML = escapeHtml(title) + (p.stub ? '<span class="stub" title="还没有内容">待写</span>' : '');
      a.title = p.path;
      a.addEventListener('click', function (e) { e.preventDefault(); openPage(p.path); });
      a.href = '#';
      tree.appendChild(a);
    }

    function group(key, label, count, indent, render) {
      var g = document.createElement('div');
      g.className = 'grp';
      g.innerHTML = '<span class="caret">' + (collapsed[key] ? '▶' : '▼') + '</span>' +
                    escapeHtml(label) + ' <span style="color:#9aa8b4;font-weight:400">' + count + '</span>';
      g.addEventListener('click', function () {
        collapsed[key] = !collapsed[key];
        LS.set('collapsed', collapsed);
        renderTree();
      });
      tree.appendChild(g);
      if (!collapsed[key]) render(indent);
    }

    group('__global', '总览', STATE.globals.length, 0, function (indent) {
      STATE.globals.forEach(function (p) { item(p, indent); });
    });

    STATE.works.forEach(function (w) {
      var key = 'w:' + w.dir;
      group(key, w.title, STATE.pages.filter(function (p) { return p.work === w.dir; }).length, 0, function () {
        var cats = w.categories.slice().sort(function (a, b) {
          var oa = (w.meta.category_order || []).indexOf(a.path);
          var ob = (w.meta.category_order || []).indexOf(b.path);
          oa = oa < 0 ? 99 : oa; ob = ob < 0 ? 99 : ob;
          return oa - ob || a.path.localeCompare(b.path);
        });
        cats.forEach(function (c) {
          var pages = STATE.pages.filter(function (p) { return p.work === w.dir && p.category === c.path; });
          var ckey = 'c:' + w.dir + '/' + c.path;
          if (!pages.length) return;
          group(ckey, c.title, pages.length, 1, function (indent) {
            pages.forEach(function (p) { item(p, indent); });
          });
        });
        var direct = STATE.pages.filter(function (p) { return p.work === w.dir && !p.category; });
        direct.forEach(function (p) { item(p, 1); });
      });
    });

    if (q && !shown) tree.innerHTML = '<div class="empty">没有匹配「' + escapeHtml(q) + '」的页面</div>';
  }

  /* ---------------------------------------------------------- 打开 / 保存 */

  function openPage(path) {
    if (dirty && current && !confirm('「' + current.path + '」还有没保存的改动，确定要切换吗？')) return;
    api('/api/page?path=' + encodeURIComponent(path)).then(function (r) {
      current = { path: r.path, content: r.content, mtime: r.mtime };
      LS.set('lastPath', path);
      $('#editor').value = r.content;
      $('#cur-path').textContent = r.path;
      $('#meta-title').value = r.meta['标题'] || r.meta['title'] || '';
      setDirty(false);
      renderTree();
      parseInfoboxIntoForm();
      refreshPreview();
      updateStatus();
      $('#editor').focus();
    }).catch(function (e) { toast('打开失败：' + e.message, 'err'); });
  }

  function save(silent) {
    if (!current) { if (!silent) toast('还没有选择页面', 'err'); return Promise.resolve(); }
    var content = $('#editor').value;
    return api('/api/save', { method: 'POST', body: { path: current.path, content: content } })
      .then(function () {
        current.content = content;
        setDirty(false);
        if (!silent) toast('已保存', 'ok');
        status('已保存 ' + new Date().toLocaleTimeString());
        renderTree();
        if (LS.get('autoBuild', true)) {
          clearTimeout(buildTimer);
          buildTimer = setTimeout(function () { doBuild(true); }, 700);
        }
      })
      .catch(function (e) { toast('保存失败：' + e.message, 'err'); });
  }

  function status(msg) {
    $('#status-left').textContent = msg;
  }

  function updateStatus() {
    var ta = $('#editor');
    var v = ta.value;
    var chars = v.replace(/\s/g, '').length;
    var lines = v.split('\n').length;
    var t = '字数 ' + chars.toLocaleString() + ' · 行 ' + lines;
    if (current) {
      var p = findPage(current.path);
      if (p) t += ' · ' + p.workTitle + ' › ' + p.categoryTitle + ' · ' + p.path;
    }
    $('#status-right').textContent = t;
    $('#meta-title').placeholder = current ? ('页面标题（留空则用文件名「' + (current.path.split('/').pop().replace(/\.md$/, '')) + '」）') : '页面标题';
  }

  /* ---------------------------------------------------------- 预览 */

  function refreshPreview() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      if (!current) return;
      api('/api/preview', { method: 'POST', body: { path: current.path, content: $('#editor').value } })
        .then(function (r) {
          $('#preview').innerHTML = r.html;
          var notes = [];
          if (r.missing.length) notes.push(r.missing.length + ' 个红色链接');
          if (r.warnings.length) notes.push(r.warnings.length + ' 处缺图');
          if (r.stub) notes.push('内容还很少');
          $('#status-left').textContent = notes.length ? '预览提示：' + notes.join('、') : '预览已更新';
          if (r.warnings.length) toast('缺图：' + r.warnings.join('；'), 'err');
        })
        .catch(function (e) { $('#preview').innerHTML = '<p style="color:#b3261e">预览失败：' + escapeHtml(e.message) + '</p>'; });
    }, 320);
  }

  $('#preview');

  /* ---------------------------------------------------------- 工具栏 */

  function wrapSel(before, after, placeholder) {
    var ta = $('#editor');
    var s = ta.selectionStart, e = ta.selectionEnd;
    var sel = ta.value.slice(s, e) || placeholder || '';
    var text = before + sel + after;
    insertText(text);
    ta.selectionStart = s + before.length;
    ta.selectionEnd = s + before.length + sel.length;
  }

  function insertText(text) {
    var ta = $('#editor');
    var s = ta.selectionStart, e = ta.selectionEnd;
    ta.value = ta.value.slice(0, s) + text + ta.value.slice(e);
    ta.selectionStart = ta.selectionEnd = s + text.length;
    afterEdit();
  }

  function insertBlock(text) {
    var ta = $('#editor');
    var s = ta.selectionStart;
    var before = ta.value.slice(0, s);
    var pre = before.length && !/\n\s*\n$/.test(before) ? '\n\n' : '';
    var after = ta.value.slice(s);
    var post = /^\s*\n/.test(after) || !after ? (after ? '' : '\n') : '\n\n';
    var full = pre + text + post;
    ta.value = before + full + after;
    ta.selectionStart = ta.selectionEnd = s + pre.length + text.length;
    afterEdit();
  }

  function afterEdit() {
    setDirty(true);
    updateStatus();
    refreshPreview();
    parseInfoboxIntoForm();
  }

  function wireToolbar() {
    $('#toolbar').addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) return;
      var act = b.dataset.act;
      var today = new Date().toISOString().slice(0, 10);
      if (act === 'h2') insertText('\n## 标题\n');
      else if (act === 'h3') insertText('\n### 标题\n');
      else if (act === 'bold') wrapSel('**', '**', '粗体');
      else if (act === 'italic') wrapSel('*', '*', '斜体');
      else if (act === 'strike') wrapSel('~~', '~~', '删除线');
      else if (act === 'wikilink') wrapSel('[[', ']]', '页面名');
      else if (act === 'link') wrapSel('[', '](https://)', '链接文字');
      else if (act === 'image') {
        var name = mediaList.length ? mediaList[0].name : '图片.jpg';
        insertText('![[' + name + '|150]]');
        switchTab('media');
      }
      else if (act === 'infobox') insertBlock('> [!info] 角色名\n> ![[图片.jpg|150]]\n> - **真名**：\n> - **性别**：\n> - **年龄**：\n> - **归属**：');
      else if (act === 'callout') insertBlock('> [!tip] 小提示\n> 这里写提示内容。');
      else if (act === 'spoiler') insertBlock('### 第二季\n\n（这一段默认折叠，读者点开才看得到。）');
      else if (act === 'table') insertBlock('| 表头一 | 表头二 |\n| --- | --- |\n| 内容 | 内容 |');
      else if (act === 'hr') insertText('\n---\n');
      else if (act === 'frontmatter') insertFrontmatter();
      afterEdit();
    });
  }

  function insertFrontmatter() {
    var ta = $('#editor');
    if (/^---\s*\n/.test(ta.value)) { toast('已经有 frontmatter 了'); return; }
    var tpl = '---\n标题: \n标签: []\n别名: []\n剧透: false\n---\n\n';
    ta.value = tpl + ta.value;
    ta.selectionStart = ta.selectionEnd = tpl.indexOf('标题: ') + 4;
    ta.focus();
  }

  /* ---------------------------------------------------------- 编辑区 */

  function wireEditor() {
    var ta = $('#editor');
    ta.addEventListener('input', function () { afterEdit(); checkAutocomplete(); });
    ta.addEventListener('click', hideAC);
    ta.addEventListener('blur', function () { setTimeout(hideAC, 180); });
    ta.addEventListener('scroll', hideAC);
    ta.addEventListener('keydown', function (e) {
      if (AC.open && handleACKey(e)) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'b') { e.preventDefault(); wrapSel('**', '**', '粗体'); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'i') { e.preventDefault(); wrapSel('*', '*', '斜体'); }
      if (e.key === 'Tab') {
        e.preventDefault();
        insertText('  ');
      }
    });
    $('#meta-title').addEventListener('change', function () {
      setTitleFrontmatter(this.value.trim());
    });
  }

  function setTitleFrontmatter(title) {
    var ta = $('#editor');
    var v = ta.value;
    var fm = /^---\s*\n([\s\S]*?)\n---\s*\n?/.exec(v);
    var line = title ? ('标题: ' + title) : null;
    if (fm) {
      var body = fm[1].split('\n').filter(function (l) { return !/^\s*(标题|title)\s*:/.test(l); });
      if (line) body.unshift(line);
      ta.value = '---\n' + body.join('\n') + '\n---\n' + v.slice(fm[0].length);
    } else if (line) {
      ta.value = '---\n' + line + '\n---\n\n' + v;
    }
    afterEdit();
  }

  window.addEventListener('beforeunload', function (e) {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  /* ---------------------------------------------------------- 双链补全 */

  function acContext() {
    var ta = $('#editor');
    var pos = ta.selectionStart;
    if (pos !== ta.selectionEnd) return null;
    var before = ta.value.slice(0, pos);
    var m = /(!?)\[\[([^\[\]\n]*)$/.exec(before);
    if (!m) return null;
    return { embed: m[1] === '!', query: m[2], start: pos - m[2].length };
  }

  function checkAutocomplete() {
    var ctx = acContext();
    if (!ctx) { hideAC(); return; }
    var q = ctx.query.toLowerCase();
    var items;
    if (ctx.embed) {
      items = mediaList.map(function (m) { return { label: m.name, sub: '图片', value: m.name }; });
    } else {
      items = [];
      (STATE.pages || []).forEach(function (p) {
        items.push({ label: p.title, sub: p.workTitle, value: p.name });
      });
      (STATE.globals || []).forEach(function (p) { items.push({ label: p.title, sub: '总览', value: p.name }); });
      (mediaList || []).forEach(function (m) { items.push({ label: m.name, sub: '图片', value: m.name }); });
    }
    items = items.filter(function (i) { return !q || i.label.toLowerCase().indexOf(q) >= 0 || i.value.toLowerCase().indexOf(q) >= 0; });
    var seen = {};
    items = items.filter(function (i) { if (seen[i.value]) return false; seen[i.value] = 1; return true; });
    if (!items.length) { hideAC(); return; }
    AC.open = true; AC.items = items.slice(0, 40); AC.sel = 0; AC.ctx = ctx;
    var ac = $('#ac');
    ac.innerHTML = AC.items.map(function (i, n) {
      return '<div class="ac-item' + (n === 0 ? ' sel' : '') + '" data-n="' + n + '">' +
             '<span>' + escapeHtml(i.label) + '</span><span class="ac-sub">' + escapeHtml(i.sub) + '</span></div>';
    }).join('');
    ac.classList.add('on');
    positionAC();
    $$('#ac .ac-item').forEach(function (el) {
      el.addEventListener('mousedown', function (e) {
        e.preventDefault();
        acceptAC(parseInt(el.dataset.n, 10));
      });
    });
  }

  var charW = null;
  function measureChar(ta) {
    if (charW != null) return charW;
    var cs = getComputedStyle(ta);
    var span = document.createElement('span');
    span.style.cssText = 'position:absolute;visibility:hidden;white-space:pre;font:' + cs.font;
    span.textContent = '中文测试 abcdefghijklmnopqrstuvwxyz0123456789';
    document.body.appendChild(span);
    charW = span.getBoundingClientRect().width / span.textContent.length;
    span.remove();
    return charW;
  }

  function positionAC() {
    var ta = $('#editor'), ctx = AC.ctx;
    var cs = getComputedStyle(ta);
    var lh = parseFloat(cs.lineHeight) || 22;
    var before = ta.value.slice(0, ctx.start);
    var lines = before.split('\n');
    var line = lines.length - 1, col = lines[lines.length - 1].length;
    var r = ta.getBoundingClientRect();
    var ac = $('#ac');
    var x = r.left + 16 + col * measureChar(ta) - ta.scrollLeft;
    var y = r.top + 14 + (line + 1) * lh - ta.scrollTop;
    var h = Math.min(240, AC.items.length * 27 + 4);
    if (y + h > window.innerHeight) y = Math.max(r.top + 8, y - h - lh);
    ac.style.left = Math.max(8, Math.min(x, window.innerWidth - 320)) + 'px';
    ac.style.top = y + 'px';
  }

  function hideAC() { AC.open = false; $('#ac').classList.remove('on'); }

  function handleACKey(e) {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      AC.sel = (AC.sel + (e.key === 'ArrowDown' ? 1 : AC.items.length - 1)) % AC.items.length;
      $$('#ac .ac-item').forEach(function (el, n) { el.classList.toggle('sel', n === AC.sel); });
      var sel = $('#ac .ac-item.sel');
      if (sel) sel.scrollIntoView({ block: 'nearest' });
      return true;
    }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); acceptAC(AC.sel); return true; }
    if (e.key === 'Escape') { e.preventDefault(); hideAC(); return true; }
    return false;
  }

  function acceptAC(n) {
    var item = AC.items[n], ctx = AC.ctx;
    if (!item || !ctx) { hideAC(); return; }
    var ta = $('#editor');
    var v = ta.value;
    var pos = ta.selectionStart;
    var insert = item.value + ']]';
    ta.value = v.slice(0, ctx.start) + insert + v.slice(pos);
    var caret = ctx.start + insert.length;
    ta.selectionStart = ta.selectionEnd = caret;
    hideAC();
    afterEdit();
    ta.focus();
  }

  /* ---------------------------------------------------------- 信息框表单 */

  function parseBlocks(text) {
    var lines = text.split('\n');
    var i = 0;
    if (lines[0] === '---') { i = 1; while (i < lines.length && !/^---\s*$/.test(lines[i])) i++; i++; }
    var j = i;
    while (j < lines.length && !lines[j].trim()) j++;
    if (!/^>\s*\[!(\w+)\]/.test(lines[j] || '')) return null;
    var start = j;
    while (j < lines.length && /^>/.test(lines[j])) j++;
    return { start: start, end: j, lines: lines };
  }

  function readInfobox(text) {
    var b = parseBlocks(text);
    if (!b) return null;
    var m = /^>\s*\[!(\w+)\][+-]?\s*(.*)$/.exec(b.lines[b.start]);
    var data = { type: m[1], title: m[2].trim(), image: '', rows: [], extra: [] };
    for (var i = b.start + 1; i < b.end; i++) {
      var s = b.lines[i].replace(/^>\s?/, '').trim();
      if (!s) continue;
      var mi = /^!\[\[(.+?)\]\]$/.exec(s);
      if (mi) { data.image = mi[1]; continue; }
      var mr = /^[-*+]\s+(.*)$/.exec(s);
      if (mr) {
        var item = mr[1].replace(/^\*\*(.+?)\*\*/, '$1');
        var k = null, v = null;
        if (item.indexOf('：') >= 0) { k = item.slice(0, item.indexOf('：')); v = item.slice(item.indexOf('：') + 1); }
        else if (item.indexOf(':') >= 0) { k = item.slice(0, item.indexOf(':')); v = item.slice(item.indexOf(':') + 1); }
        if (k !== null) { data.rows.push({ k: k.trim(), v: v.trim() }); continue; }
      }
      data.extra.push(s);
    }
    data.block = b;
    return data;
  }

  function parseInfoboxIntoForm() {
    var data = readInfobox($('#editor').value);
    var box = $('#ib-rows');
    if (!data) {
      $('#ib-status').textContent = '这个页面开头没有 > [!info] 信息框。用工具栏的「信息框」按钮可以插一个。';
      $('#ib-title').value = ''; $('#ib-image').value = ''; box.innerHTML = '';
      return;
    }
    $('#ib-status').textContent = '读到 ' + data.rows.length + ' 个字段' + (data.extra.length ? '（另有 ' + data.extra.length + ' 行普通内容，会保留在末尾）' : '');
    $('#ib-title').value = data.title;
    $('#ib-image').value = data.image;
    box.innerHTML = '';
    data.rows.forEach(function (r, i) { addRow(r.k, r.v); });
  }

  function addRow(k, v) {
    k = k || ''; v = v || '';
    var div = document.createElement('div');
    div.className = 'row';
    div.innerHTML = '<input class="k" type="text" value="' + escapeHtml(k) + '" placeholder="字段名">' +
                    '<input class="v" type="text" value="' + escapeHtml(v) + '" placeholder="内容">' +
                    '<button title="删掉这一行">✕</button>';
    div.querySelector('button').addEventListener('click', function () { div.remove(); });
    $('#ib-rows').appendChild(div);
  }

  function wireInfobox() {
    $('#ib-addrow').addEventListener('click', function () { addRow('', ''); });
    $('#ib-write').addEventListener('click', function () {
      var ta = $('#editor');
      var data = readInfobox(ta.value);
      var block = buildInfoboxBlock({
        title: $('#ib-title').value.trim(),
        image: $('#ib-image').value.trim(),
        rows: $$('#ib-rows .row').map(function (d) {
          return { k: d.querySelector('.k').value.trim(), v: d.querySelector('.v').value.trim() };
        }).filter(function (r) { return r.k || r.v; }),
        extra: data ? data.extra : []
      });
      var lines = ta.value.split('\n');
      if (data) {
        lines.splice(data.block.start, data.block.end - data.block.start, block);
      } else {
        var b = parseBlocks(ta.value);
        var at = b ? b.start : 0;
        lines.splice(at, 0, block, '');
      }
      ta.value = lines.join('\n');
      afterEdit();
      toast('信息框已写回正文', 'ok');
    });
  }

  function buildInfoboxBlock(d) {
    var out = ['> [!info]' + (d.title ? ' ' + d.title : '')];
    if (d.image) out.push('> ![[%s]]'.replace('%s', d.image));
    d.rows.forEach(function (r) {
      out.push('> - **' + r.k + '**：' + r.v);
    });
    d.extra.forEach(function (s) { out.push('> ' + s); });
    return out.join('\n');
  }

  /* ---------------------------------------------------------- 图片 */

  function renderMediaWorkSelect() {
    var sel = $('#media-work');
    sel.innerHTML = '<option value="">（根目录）</option>' +
      STATE.works.map(function (w) { return '<option value="' + escapeHtml(w.dir) + '">' + escapeHtml(w.title) + '</option>'; }).join('');
  }

  function loadMedia() {
    var work = $('#media-work').value;
    LS.set('mediaWork', work);
    return api('/api/media?work=' + encodeURIComponent(work)).then(function (r) {
      mediaList = r.items;
      $('#media-grid').innerHTML = mediaList.map(function (m) {
        return '<div class="m" data-url="' + escapeHtml(m.url) + '" data-name="' + escapeHtml(m.name) + '">' +
               '<img src="' + escapeHtml(m.url) + '" loading="lazy" alt="">' +
               '<span>' + escapeHtml(m.name) + '</span></div>';
      }).join('') || '<p class="hint">这个位置还没有图片。</p>';
      $$('#media-grid .m').forEach(function (el) {
        el.addEventListener('click', function () {
          insertText('![[' + el.dataset.name + '|150]]');
          toast('已插入 ' + el.dataset.name, 'ok');
        });
      });
    }).catch(function (e) { toast('图片列表加载失败：' + e.message, 'err'); });
  }

  function uploadFiles(files) {
    var work = $('#media-work').value;
    Array.prototype.slice.call(files).forEach(function (f) {
      if (!/^image\//.test(f.type)) { toast(f.name + ' 不是图片', 'err'); return; }
      var fr = new FileReader();
      fr.onload = function () {
        api('/api/upload', { method: 'POST', body: { name: f.name, work: work, dataUrl: fr.result } })
          .then(function (r) { toast('已上传 ' + r.name, 'ok'); loadMedia(); })
          .catch(function (e) { toast('上传失败：' + e.message, 'err'); });
      };
      fr.readAsDataURL(f);
    });
  }

  function wireMedia() {
    var drop = $('#drop'), file = $('#file');
    drop.addEventListener('click', function () { file.click(); });
    file.addEventListener('change', function () { uploadFiles(file.files); file.value = ''; });
    ['dragenter', 'dragover'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('hot'); });
    });
    ['dragleave', 'drop'].forEach(function (ev) {
      drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('hot'); });
    });
    drop.addEventListener('drop', function (e) {
      if (e.dataTransfer && e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files);
    });
    document.addEventListener('paste', function (e) {
      if (document.activeElement !== $('#editor')) return;
      var items = (e.clipboardData || {}).items || [];
      var files = [];
      for (var i = 0; i < items.length; i++) {
        if (items[i].type && items[i].type.indexOf('image') === 0) {
          var f = items[i].getAsFile();
          if (f) { f.name = 'paste-' + Date.now() + '.png'; files.push(f); }
        }
      }
      if (files.length) { e.preventDefault(); uploadFiles(files); }
    });
    $('#media-work').addEventListener('change', loadMedia);
    $('#btn-media-reload').addEventListener('click', loadMedia);
  }

  /* ---------------------------------------------------------- 标签页 */

  function switchTab(name) {
    $$('#right-tabs button').forEach(function (b) { b.classList.toggle('on', b.dataset.tab === name); });
    $$('.tab-panel').forEach(function (p) { p.classList.toggle('on', p.id === 'panel-' + name); });
    LS.set('tab', name);
  }

  function wireTabs() {
    $$('#right-tabs button').forEach(function (b) {
      b.addEventListener('click', function () { switchTab(b.dataset.tab); });
    });
    // 支持 ?tab=infobox 直达某个标签页
    var want = (location.search.match(/[?&]tab=([^&]+)/) || [])[1];
    var t = want ? decodeURIComponent(want) : LS.get('tab', 'preview');
    if (t && document.getElementById('panel-' + t)) switchTab(t);
  }

  /* ---------------------------------------------------------- 顶部按钮 */

  function wireTop() {
    $('#btn-save').addEventListener('click', function () { save(); });
    $('#btn-build').addEventListener('click', function () { doBuild(false); });
    $('#btn-settings').addEventListener('click', openSettings);
    $('#btn-new').addEventListener('click', openNewPage);
    $('#page-filter').addEventListener('input', renderTree);
  }

  function doBuild(quiet) {
    if (!quiet) status('正在构建…');
    return api('/api/build', { method: 'POST', body: {} }).then(function (r) {
      renderBuildLog(r);
      if (!quiet) { switchTab('git'); toast(r.ok ? '构建完成' : '构建出错，看 Git 标签页的日志', r.ok ? 'ok' : 'err'); }
      else if (!r.ok) toast('构建出错', 'err');
      status('构建完成 ' + (r.secs || '') + 's');
      return r;
    }).catch(function (e) { toast('构建失败：' + e.message, 'err'); });
  }

  function renderBuildLog(r) {
    if (!r || !r.at) { $('#build-log').textContent = '（还没构建过）'; return; }
    $('#build-log').textContent = '[' + r.at + '] ' + (r.ok ? '成功' : '失败') + ' · ' + (r.secs || '?') + 's\n' + (r.out || '');
  }

  function openNewPage() {
    var works = STATE.works.map(function (w) { return '<option value="' + escapeHtml(w.dir) + '">' + escapeHtml(w.title) + '</option>'; }).join('');
    var cur = findPage(current && current.path);
    var curWork = cur ? cur.work : (STATE.works[0] || {}).dir;
    modal(
      '<h3>新建页面</h3>' +
      '<label style="display:block;font-size:11.5px;color:#66727d;margin:9px 0 3px">页面名称</label>' +
      '<input id="np-name" type="text" placeholder="例如：真夕" style="width:100%;padding:5px 8px;border:1px solid #c9d6e2;border-radius:3px">' +
      '<label style="display:block;font-size:11.5px;color:#66727d;margin:9px 0 3px">所属作品</label>' +
      '<select id="np-work" style="width:100%;padding:5px 8px;border:1px solid #c9d6e2;border-radius:3px">' + works +
      '<option value="__root">（根目录 · 总览类页面）</option></select>' +
      '<label id="np-cat-label" style="display:block;font-size:11.5px;color:#66727d;margin:9px 0 3px">分类（可填已有的，也可新写一个）</label>' +
      '<input id="np-cat" type="text" list="np-cats" placeholder="例如：人物" style="width:100%;padding:5px 8px;border:1px solid #c9d6e2;border-radius:3px">' +
      '<datalist id="np-cats">' + STATE.works.map(function (w) {
        return w.categories.map(function (c) { return '<option value="' + escapeHtml(c.path) + '">'; }).join('');
      }).join('') + '</datalist>' +
      '<label style="display:block;font-size:11.5px;color:#66727d;margin:9px 0 3px">模板</label>' +
      '<select id="np-tpl" style="width:100%;padding:5px 8px;border:1px solid #c9d6e2;border-radius:3px">' +
      ['人物', '组织', '地点', '事件', '名词', '空页面'].map(function (t) { return '<option>' + t + '</option>'; }).join('') +
      '</select>' +
      '<div class="actions"><button data-cancel>取消</button><button data-ok class="primary">创建</button></div>',
      {
        collect: function () {
          var work = $('#np-work').value;
          return {
            name: $('#np-name').value,
            work: work === '__root' ? '' : work,
            category: work === '__root' ? '' : $('#np-cat').value,
            atRoot: work === '__root',
            template: $('#np-tpl').value
          };
        },
        onShown: function () {
          var w = $('#np-work');
          w.value = curWork || '__root';
          var sync = function () {
            var root = w.value === '__root';
            $('#np-cat').style.display = root ? 'none' : '';
            var lbl = $('#np-cat-label');
            if (lbl) lbl.style.display = root ? 'none' : '';
          };
          w.addEventListener('change', sync);
          sync();
        }
      }
    ).then(function (form) {
      if (!form) return;
      if (!form.name) { toast('要填页面名称', 'err'); return; }
      api('/api/new', { method: 'POST', body: form }).then(function (r) {
        toast('已创建 ' + r.path, 'ok');
        return loadState().then(function () { openPage(r.path); });
      }).catch(function (e) { toast('创建失败：' + e.message, 'err'); });
    });
  }

  /* ---------------------------------------------------------- 设置 */

  function openSettings() {
    var opts = '<option value="__site">站点设置（wiki.config.json）</option>' +
      STATE.works.map(function (w) {
        return '<option value="' + escapeHtml(w.dir) + '">作品：' + escapeHtml(w.title) + '</option>';
      }).join('');
    api('/api/settings').then(function (site) {
      modal(
        '<h3>设置</h3>' +
        '<select id="st-which" style="width:100%;padding:5px 8px;border:1px solid #c9d6e2;border-radius:3px;margin-bottom:8px">' + opts + '</select>' +
        '<p style="font-size:11.5px;color:#66727d;margin:4px 0">改完点「保存」。JSON 格式错了会拒绝写入，不会弄坏文件。</p>' +
        '<textarea id="st-json" spellcheck="false" style="width:100%;height:340px;font:11.5px/1.6 Menlo,Consolas,monospace;padding:8px;border:1px solid #c9d6e2;border-radius:3px">' +
        escapeHtml(site.json) + '</textarea>' +
        '<div class="actions"><button data-cancel>取消</button><button data-ok class="primary">保存</button></div>',
        {
          collect: function () {
            return { which: $('#st-which').value, json: $('#st-json').value };
          }
        }
      ).then(function (res) {
        if (!res) return;
        var parsed;
        try { parsed = JSON.parse(res.json); }
        catch (e) { toast('JSON 有语法错误：' + e.message, 'err'); return; }
        void parsed;
        var url = res.which === '__site' ? '/api/settings' : '/api/work';
        var body = res.which === '__site' ? { json: res.json } : { dir: res.which, json: res.json };
        api(url, { method: 'POST', body: body }).then(function () {
          toast('已保存', 'ok');
          return loadState();
        }).catch(function (e) { toast('保存失败：' + e.message, 'err'); });
      }).then(function () {
        var sel = $('#st-which');
        if (sel) {
          sel.onchange = function () {
            var which = this.value;
            var pr = which === '__site' ? api('/api/settings')
              : api('/api/work?dir=' + encodeURIComponent(which));
            pr.then(function (r) { $('#st-json').value = r.json; });
          };
        }
      });
    });
  }

  /* ---------------------------------------------------------- Git */

  function renderGit(g) {
    if (!g || !g.ok) {
      $('#git-branch').textContent = '—';
      $('#git-remote').textContent = g && g.error ? g.error : '不可用';
      $('#git-changes').innerHTML = '';
      $('#remote-setup').style.display = '';
      return;
    }
    $('#git-branch').textContent = (g.branch || '(未命名)') + (g.ahead && g.ahead.indexOf('ahead') >= 0 ? ' · ' + g.ahead.split('...')[1] : '');
    $('#git-remote').textContent = g.remote || '（还没设置）';
    $('#git-count').textContent = g.changes.length;
    $('#git-changes').innerHTML = g.changes.map(function (c) {
      return '<li><span class="code">' + escapeHtml(c.code) + '</span><span>' + escapeHtml(c.file) + '</span></li>';
    }).join('') || '<li style="color:#66727d">工作区是干净的</li>';
    $('#remote-setup').style.display = g.remote ? 'none' : '';
  }

  function gitLog(msg) {
    var el = $('#git-log');
    el.textContent = msg;
    el.scrollTop = el.scrollHeight;
  }

  function gitRefresh() {
    api('/api/state').then(function (s) {
      STATE.git = s.git;
      renderGit(s.git);
      renderBuildLog(s.lastBuild);
    });
  }

  function wireGit() {
    $('#btn-git-refresh').addEventListener('click', function () { gitRefresh(); toast('已刷新'); });
    $('#btn-commit').addEventListener('click', function () { doCommit(false); });
    $('#btn-commit-push').addEventListener('click', function () { doCommit(true); });
    $('#btn-pull').addEventListener('click', function () {
      gitLog('正在拉取…');
      api('/api/git/pull', { method: 'POST', body: {} }).then(function (r) {
        gitLog((r.ok ? '拉取成功\n' : '拉取失败\n') + (r.output || '') + (r.error ? '\n' + r.error : ''));
        toast(r.ok ? '拉取完成' : '拉取失败', r.ok ? 'ok' : 'err');
        gitRefresh();
      });
    });
    $('#btn-remote-set').addEventListener('click', function () {
      var url = $('#remote-url').value.trim();
      api('/api/git/init-remote', { method: 'POST', body: { url: url } }).then(function (r) {
        gitLog((r.ok ? '已设置远程\n' : '设置失败\n') + (r.output || '') + (r.error ? '\n' + r.error : ''));
        toast(r.ok ? '远程已设置' : '设置失败', r.ok ? 'ok' : 'err');
        gitRefresh();
      }).catch(function (e) { toast(e.message, 'err'); });
    });
  }

  function doCommit(thenPush) {
    var msg = $('#git-msg').value.trim();
    if (!msg) {
      var stamp = new Date().toLocaleString('zh-CN');
      msg = '更新 wiki 内容（' + stamp + '）';
    }
    gitLog('正在提交…');
    api('/api/git/commit', { method: 'POST', body: { message: msg, addAll: true } }).then(function (r) {
      var out = (r.ok ? '提交成功\n' : '提交失败\n') + (r.output || '') + (r.error ? '\n' + r.error : '');
      gitLog(out);
      if (!r.ok) { toast('提交失败', 'err'); return; }
      toast('已提交', 'ok');
      $('#git-msg').value = '';
      if (!thenPush) { gitRefresh(); return; }
      gitLog(out + '\n\n正在推送…');
      return api('/api/git/push', { method: 'POST', body: {} }).then(function (p) {
        gitLog(out + '\n\n' + (p.ok ? '推送成功\n' : '推送失败\n') + (p.output || '') + (p.error ? '\n' + p.error : ''));
        toast(p.ok ? '已推送到 GitHub' : '推送失败，看日志', p.ok ? 'ok' : 'err');
        gitRefresh();
      });
    }).catch(function (e) { toast('提交出错：' + e.message, 'err'); });
  }

  /* ---------------------------------------------------------- 组装 */

  // 预览里的链接指向已构建的站点，点开用新标签页，别把预览面板顶掉
  $('#preview').addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href.charAt(0) === '#') return;
    e.preventDefault();
    if (href.indexOf('/site/') === 0) window.open(href, '_blank');
    else if (href === 'missing.html' || /\/missing\.html/.test(href)) window.open('/site/missing.html', '_blank');
  });

  wireInfobox();
  init();
})();
