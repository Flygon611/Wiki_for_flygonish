
(function(){
  // ---------- 目录折叠 ----------
  document.querySelectorAll('.toc-head .toggle').forEach(function(t){
    t.addEventListener('click', function(){
      var box = t.closest('.toc');
      var list = box.querySelector('ol');
      var hidden = list.style.display === 'none';
      list.style.display = hidden ? '' : 'none';
      t.textContent = hidden ? '[隐藏]' : '[显示]';
    });
  });

  // ---------- 剧透折叠：记忆展开状态 ----------
  var KEY = 'wiki-spoiler-open';
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e){}
  document.querySelectorAll('details.spoiler-fold').forEach(function(d){
    var id = (d.dataset.fold || '') + '@' + location.pathname;
    if (saved[id]) d.open = true;
    d.addEventListener('toggle', function(){
      saved[id] = d.open;
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch(e){}
    });
  });

  // ---------- 顶部即时搜索 ----------
  var input = document.getElementById('wiki-search-input');
  var panel = document.getElementById('wiki-search-results');
  var indexUrl = input && input.getAttribute('data-index');
  // search.json 里的 u 是「相对站点根」的路径，而本下拉框会出现在任意深度的页面上，
  // 所以要补上「从当前页回到站点根」的前缀（例如 '../../'），否则在深层页点结果会 404。
  var basePrefix = indexUrl ? indexUrl.replace(/search\.json.*$/, '') : '';
  var data = null, loading = null, loadFailed = false;
  var FILE_HINT = '搜索需要本地服务器：双击打开 HTML 文件时浏览器不允许读取索引。' +
                  '请用 python3 build.py --open 预览，或直接访问发布在 GitHub Pages 上的站点。';

  function load(){
    if (data) return Promise.resolve(data);
    if (!loading) loading = fetch(indexUrl).then(function(r){ return r.json(); }).then(function(j){ data = j; return j; })
      .catch(function(){ loadFailed = true; data = []; return data; });
    return loading;
  }
  function render(list, q){
    if (loadFailed){ panel.innerHTML = '<div class="sr-none">' + FILE_HINT + '</div>'; return; }
    if (!list.length){ panel.innerHTML = '<div class="sr-none">没有找到「' + q + '」</div>'; return; }
    panel.innerHTML = list.slice(0, 12).map(function(p){
      var s = p.x ? p.x.slice(0, 60) + (p.x.length > 60 ? '…' : '') : '';
      return '<a href="' + basePrefix + p.u + '"><b>' + p.t + '</b><span class="sr-cat">' + (p.c || '') + '</span>' +
             (s ? '<br><span class="sr-cat">' + s + '</span>' : '') + '</a>';
    }).join('');
  }
  if (input && panel){
    input.addEventListener('input', function(){
      var q = input.value.trim();
      if (q.length < 1){ panel.classList.remove('on'); return; }
      load().then(function(all){
        var lower = q.toLowerCase();
        var hits = all.filter(function(p){
          return (p.t + ' ' + p.k + ' ' + (p.x || '')).toLowerCase().indexOf(lower) >= 0;
        }).sort(function(a, b){
          var at = a.t.toLowerCase().indexOf(lower) === 0 ? 0 : 1;
          var bt = b.t.toLowerCase().indexOf(lower) === 0 ? 0 : 1;
          return at - bt || b.n - a.n;
        });
        render(hits, q);
        panel.classList.add('on');
      });
    });
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter'){ e.preventDefault(); location.href = './search.html?q=' + encodeURIComponent(input.value.trim()); }
      if (e.key === 'Escape'){ panel.classList.remove('on'); input.blur(); }
    });
    document.addEventListener('click', function(e){
      if (!panel.contains(e.target) && e.target !== input) panel.classList.remove('on');
    });
  }

  // ---------- 剧透横幅关闭 ----------
  document.querySelectorAll('.spoiler-banner .dismiss').forEach(function(b){
    b.addEventListener('click', function(){ b.closest('.spoiler-banner').style.display = 'none'; });
  });

  // ---------- 词条导航折叠 ----------
  document.querySelectorAll('.navbox .nb-toggle').forEach(function(t){
    t.addEventListener('click', function(){
      var off = t.closest('.navbox').classList.toggle('collapsed');
      t.textContent = off ? '[展开]' : '[折叠]';
    });
  });

  // ---------- 词条悬停预览（Page Previews）----------
  // 鼠标停在蓝色词条链接上，浮出目标条目的标题、摘要和缩略图。
  // 数据来自构建期生成的 previews.json（加密作品不在里面，见 build.py）。
  (function(){
    // 触屏 / 只有粗指针的设备上没有「悬停」这回事，整套不启用。
    if (!window.matchMedia || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
    if (typeof fetch !== 'function') return;

    var DELAY = 400;         // 悬停多久才弹（毫秒）
    var GRACE = 200;         // 离开链接/卡片后留一点时间，让人能把鼠标移进卡片
    var GAP = 6, EDGE = 8;
    var PV_VER = 'db86917c';

    var input = document.getElementById('wiki-search-input');
    var indexUrl = input && input.getAttribute('data-index');
    if (!indexUrl) return;                       // 推不出去站点根的前缀，宁可不弹
    var basePrefix = indexUrl.replace(/search\.json.*$/, '');
    var indexFile = basePrefix + 'previews.json' +
                    (PV_VER ? '?v=' + encodeURIComponent(PV_VER) : '');

    // 站点根在 location 里的位置（GitHub Pages 是 /Wiki_for_flygonish/，本地是 /）。
    // 拿它才能把链接的 href（相对当前页面）还原成「相对站点根」，和 u 对得上。
    var rootPath = '';
    try {
      rootPath = new URL(basePrefix + 'previews.json', location.href).pathname.replace(/[^/]*$/, '');
    } catch (e) { rootPath = ''; }
    var selfPath = '';
    try {
      if (rootPath && location.pathname.indexOf(rootPath) === 0) {
        selfPath = safeDecode(location.pathname.slice(rootPath.length));
      }
    } catch (e) { selfPath = ''; }

    var items = null, loading = null, lookup = null;
    var card = null, cardLink = null;
    var hoveredLink = null, showTimer = null, hideTimer = null;

    function safeDecode(s){
      try { return decodeURIComponent(s); } catch (e) { return String(s); }
    }
    function normpath(p){
      var out = [];
      String(p).split('/').forEach(function(seg){
        if (!seg || seg === '.') return;
        if (seg === '..') { out.pop(); return; }
        out.push(seg);
      });
      return out.join('/');
    }
    function esc(s){
      return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }
    function encodePath(p){
      return String(p).split('/').map(function(seg){ return encodeURIComponent(seg); }).join('/');
    }
    // href（已去掉 # 与 ?query）→ 相对站点根的路径；外部链接 / 站外路径返回 ''
    function targetPath(href){
      var h = String(href || '').split('#')[0].split('?')[0];
      if (!h || h.indexOf('//') === 0 || /^[a-zA-Z][a-zA-Z0-9+.\-]*:/.test(h)) return '';
      var path = '';
      if (rootPath && typeof URL === 'function') {
        try { path = new URL(h, location.href).pathname; } catch (e) { return ''; }
        if (path.indexOf(rootPath) !== 0) return '';
        path = path.slice(rootPath.length);
      } else {
        // 老浏览器没有 URL：退回字符串拼接。href 里以 ../ 开头的会算错，
        // 这种链接宁可不弹卡片，也不弹错条目。
        if (h.charAt(0) === '/' || h.indexOf('../') === 0) return '';
        path = normpath(basePrefix + h);
      }
      return safeDecode(path);
    }

    function load(){
      if (items) return Promise.resolve(items);
      if (!loading) {
        loading = fetch(indexFile).then(function(r){ return r.json(); }).then(function(json){
          items = json || [];
          lookup = {};
          items.forEach(function(it){
            if (it && it.u) lookup[safeDecode(it.u)] = it;
          });
          return items;
        }).catch(function(){
          // 双击打开 HTML、或索引读取失败：安静地不弹卡片就是了
          items = []; lookup = {}; return items;
        });
      }
      return loading;
    }

    function hide(){
      clearTimeout(showTimer); clearTimeout(hideTimer);
      showTimer = hideTimer = null;
      if (card && card.parentNode) card.parentNode.removeChild(card);
      card = null; cardLink = null;
    }
    function scheduleHide(){
      clearTimeout(hideTimer);
      hideTimer = setTimeout(hide, GRACE);
    }
    function place(link){
      if (!card) return;
      var r = link.getBoundingClientRect();
      var vw = window.innerWidth || (document.documentElement && document.documentElement.clientWidth) || 0;
      var vh = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 0;
      var cw = card.offsetWidth || 340;
      var ch = card.offsetHeight || 120;
      var left = r.left;
      var top = r.bottom + GAP;
      // 链接贴着视口底部时翻到上方
      if (top + ch + EDGE > vh && r.top - GAP - ch >= EDGE) top = r.top - GAP - ch;
      if (left + cw + EDGE > vw) left = vw - cw - EDGE;    // 右边放不下就左移
      if (left < EDGE) left = EDGE;
      if (top + ch + EDGE > vh) top = vh - ch - EDGE;      // 上下都夹进视口
      if (top < EDGE) top = EDGE;
      card.style.left = Math.round(left) + 'px';
      card.style.top = Math.round(top) + 'px';
    }
    function show(link, item){
      if (card && cardLink === link) return;      // 同一个链接不重复建 DOM
      hide();
      cardLink = link;
      card = document.createElement('div');
      card.className = 'pv-card';
      card.id = 'pv-card';
      var href = esc(basePrefix + item.u);
      var html = '<div class="pv-head"><a href="' + href + '">' + esc(item.t) + '</a></div>';
      var body = '';
      if (item.i) {
        body += '<img class="pv-thumb" src="' + esc(basePrefix + encodePath(item.i)) + '" alt="">';
      }
      if (item.x) {
        body += '<p class="pv-text">' + esc(item.x) + '</p>';
      } else if (item.f) {
        // 正文全在剧透折叠里：不拿折叠内容当摘要，但别让卡片空着
        body += '<p class="pv-text pv-folded">\uD83D\uDD12 本页正文默认折叠，点开查看</p>';
      }
      if (body) html += '<div class="pv-body">' + body + '</div>';
      html += '<div class="pv-foot"><a href="' + href + '">查看条目 \u2192</a></div>';
      card.innerHTML = html;
      card.addEventListener('mouseenter', function(){ clearTimeout(hideTimer); hideTimer = null; });
      card.addEventListener('mouseleave', scheduleHide);
      document.body.appendChild(card);
      place(link);
    }
    function open(link){
      showTimer = null;
      var key = targetPath(link.getAttribute('href'));
      // 查不到条目（含加密作品、未完成页面）就不弹——不做任何兜底猜测
      if (!key || key === selfPath) return;
      load().then(function(){
        if (hoveredLink !== link) return;       // 等数据的时候鼠标已经移开了
        if (!lookup || !lookup[key]) return;
        show(link, lookup[key]);
      });
    }

    document.addEventListener('mouseover', function(e){
      var t = e.target;
      var link = t && t.closest ? t.closest('a.wikilink') : null;
      if (link) {
        clearTimeout(hideTimer); hideTimer = null;
        if (card && cardLink !== link) hide();          // 同一时间只留一张卡片
        if (card) return;
        hoveredLink = link;
        clearTimeout(showTimer);
        showTimer = setTimeout(function(){ open(link); }, DELAY);
        return;
      }
      if (card && (t === card || card.contains(t))) { clearTimeout(hideTimer); hideTimer = null; }
    });
    document.addEventListener('mouseout', function(e){
      var t = e.target;
      var link = t && t.closest ? t.closest('a.wikilink') : null;
      if (!link) return;
      if (hoveredLink === link) hoveredLink = null;
      var to = e.relatedTarget;
      if (to && (link.contains(to) || (card && card.contains(to)))) return;   // 移进卡片，别收
      clearTimeout(showTimer); showTimer = null;
      scheduleHide();
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape' || e.keyCode === 27) hide();
    });
    document.addEventListener('click', function(e){
      if (card && !card.contains(e.target)) hide();     // 点了别处
    });
    window.addEventListener('scroll', hide, true);      // 页面一动，卡片就不跟了
    window.addEventListener('resize', hide);
  })();
})();
