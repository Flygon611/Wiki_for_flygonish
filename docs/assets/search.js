
(function(){
  var form = document.getElementById('sform');
  var box = document.getElementById('sresults');
  var input = document.getElementById('q');
  var params = new URLSearchParams(location.search);
  var initial = params.get('q') || '';
  input.value = initial;
  box.setAttribute('data-index', 'search.json');

  fetch('search.json').then(function(r){ return r.json(); }).then(function(all){
    run(initial, all);
    form.addEventListener('submit', function(e){
      e.preventDefault();
      var u = new URL(location.href); u.searchParams.set('q', input.value); history.replaceState(null, '', u);
      run(input.value, all);
    });
    input.addEventListener('input', function(){ run(input.value, all); });
  }).catch(function(){ box.innerHTML = '<p class="hit-count">搜索索引加载失败。' +
      '如果你是双击打开 HTML 文件，浏览器会禁止读取索引——请改用 ' +
      '<code>python3 build.py --open</code> 预览，或访问已发布的站点。</p>'; });

  function run(q, all){
    q = (q || '').trim();
    if (!q){ box.innerHTML = '<p class="hit-count">这个 wiki 共收录 ' + all.length + ' 个页面。输入关键词开始搜索。</p>'; return; }
    var lower = q.toLowerCase();
    var hits = all.filter(function(p){
      return (p.t + ' ' + p.k + ' ' + (p.x || '')).toLowerCase().indexOf(lower) >= 0;
    });
    if (!hits.length){ box.innerHTML = '<p class="hit-count">没有找到「' + q + '」。</p>'; return; }
    box.innerHTML = '<p class="hit-count">找到 ' + hits.length + ' 个页面：</p>' + hits.map(function(p){
      return '<div class="recent-row"><div style="flex:1 1 auto"><a href="' + p.u + '"><b>' + p.t + '</b></a>' +
             ' <span class="sr-cat">' + (p.w || '') + (p.c ? ' › ' + p.c : '') + '</span>' +
             (p.x ? '<div class="sr-cat">' + p.x.slice(0, 130) + '…</div>' : '') + '</div></div>';
    }).join('');
  }
})();
