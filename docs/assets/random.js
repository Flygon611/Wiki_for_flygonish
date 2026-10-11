
fetch('search.json').then(function(r){ return r.json(); }).then(function(all){
  document.getElementById('cnt').textContent = all.length;
  document.getElementById('go').addEventListener('click', function(){
    location.href = all[Math.floor(Math.random() * all.length)].u;
  });
  var p = new URLSearchParams(location.search).get('go');
  if (p) location.href = all[Math.floor(Math.random() * all.length)].u;
});
