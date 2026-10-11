
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
})();
