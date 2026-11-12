/* Corpus Explorer: every article regardless of the scenario clock (game master only). */
(function () {
  'use strict';
  var COLORS = { ledger: '#1f4e8c', harborline6: '#c0392b', coastline: '#2a7f7f', gulfwater: '#e67e22',
    sabal: '#22a35a', continental: '#d93025', 'anchor-rotor': '#8a7a2c', kncb: '#e0a800' };
  var A = [], byId = {}, OUTLETS = [], NAMES = {}, seq = -1, lastFetch = 0, clockNow = 0;
  var F = { q: '', type: '', arc: '', vis: 'all', dmin: -60, dmax: 120, outlets: {} };
  var view = 'list', sort = { key: 'ts', asc: true }, sel = null, dayPick = null;
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  var D0 = Date.UTC(2027, 8, 14), MONTHS = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  var WD = ['Sun.', 'Mon.', 'Tue.', 'Wed.', 'Thu.', 'Fri.', 'Sat.'];
  function dayDate(day) { var d = new Date(D0 + day * 86400000); return WD[d.getUTCDay()] + ' ' + MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear(); }
  function dTag(day) { return 'D' + (day >= 0 ? '+' : '-') + Math.abs(day); }
  function timeOf(a) { return a.d.split(' ').slice(1).join(' '); }

  // ------------------------------------------------------------ data
  function load(keepSel) {
    lastFetch = Date.now();
    return fetch('/api/gm/articles', { cache: 'no-store' })
      .then(function (r) { if (r.status === 401) { location.href = '/gm/login?next=/explorer'; throw new Error('auth'); } return r.json(); })
      .then(function (d) {
        A = d.articles; byId = {}; A.forEach(function (a) { byId[a.id] = a; a._hay = [a.headline, a.summary, a.body.join(' '), a.topics.join(' '), a.people.join(' '), a.places.join(' '), a.authors.join(' '), a.id].join(' ').toLowerCase(); });
        OUTLETS = d.outlets; OUTLETS.forEach(function (o) { NAMES[o.slug] = o.name; });
        clockNow = d.now;
        $('clock').textContent = 'Clock: ' + d.d + ' · ' + A.filter(function (a) { return a.visible; }).length + '/' + A.length + ' published';
        if (!keepSel) buildControls();
        render();
        if (sel) read(sel);
      }).catch(function () {});
  }
  function watchClock() {
    fetch('/api/gm/state', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (s) {
      if (seq !== -1 && s.seq !== seq && Date.now() - lastFetch > 15000) load(true);
      else $('clock').textContent = 'Clock: ' + s.d + ' · ' + s.published + '/' + s.total + ' published' + (s.playing ? ' · playing' : '');
      seq = s.seq;
    }).catch(function () {}).then(function () { setTimeout(watchClock, 5000); });
  }

  function buildControls() {
    var types = {}, arcs = {}, dmin = 999, dmax = -999;
    A.forEach(function (a) { types[a.story_type] = (types[a.story_type] || 0) + 1; a.storylines.forEach(function (s) { arcs[s] = (arcs[s] || 0) + 1; }); dmin = Math.min(dmin, a.day); dmax = Math.max(dmax, a.day); });
    $('type').innerHTML = '<option value="">All types</option>' + Object.keys(types).sort().map(function (t) { return '<option value="' + esc(t) + '">' + esc(t) + ' (' + types[t] + ')</option>'; }).join('');
    $('arc').innerHTML = '<option value="">All storylines</option>' + Object.keys(arcs).sort().map(function (t) { return '<option value="' + esc(t) + '">' + esc(t) + ' (' + arcs[t] + ')</option>'; }).join('');
    F.dmin = dmin; F.dmax = dmax; $('dmin').value = dmin; $('dmax').value = dmax; $('dmin').min = $('dmax').min = dmin; $('dmin').max = $('dmax').max = dmax;
    $('outlets').innerHTML = OUTLETS.map(function (o) {
      var n = A.filter(function (a) { return a.outlet === o.slug; }).length;
      return '<button class="chip" data-o="' + o.slug + '" aria-pressed="false"><span class="dot" style="background:' + COLORS[o.slug] + '"></span>' + esc(o.name) + ' <span class="count">' + n + '</span></button>';
    }).join('');
  }

  function filtered() {
    var terms = F.q.toLowerCase().split(/\s+/).filter(Boolean), any = Object.keys(F.outlets).length;
    return A.filter(function (a) {
      if (any && !F.outlets[a.outlet]) return false;
      if (F.type && a.story_type !== F.type) return false;
      if (F.arc && a.storylines.indexOf(F.arc) < 0) return false;
      if (F.vis === 'pub' && !a.visible) return false;
      if (F.vis === 'up' && a.visible) return false;
      if (a.day < F.dmin || a.day > F.dmax) return false;
      for (var i = 0; i < terms.length; i++) if (a._hay.indexOf(terms[i]) < 0) return false;
      return true;
    });
  }

  // ------------------------------------------------------------ views
  function render() {
    var rows = filtered();
    $('count').textContent = rows.length + ' of ' + A.length + ' articles';
    if (view === 'list') renderList(rows);
    else if (view === 'day') renderDay(rows);
    else renderArc(rows);
  }
  function typeTag(a) { return '<span class="type' + (a.story_type === 'breaking' ? ' breaking' : '') + '">' + esc(a.story_type) + '</span>'; }

  function renderList(rows) {
    var k = sort.key, dir = sort.asc ? 1 : -1;
    rows = rows.slice().sort(function (x, y) {
      var a = k === 'ts' ? x.ts : k === 'outlet' ? x.outlet_name : (x[k] || ''), b = k === 'ts' ? y.ts : k === 'outlet' ? y.outlet_name : (y[k] || '');
      return (a < b ? -1 : a > b ? 1 : x.ts - y.ts) * dir;
    });
    var cols = [['ts', 'When'], ['local', 'Local time'], ['outlet', 'Outlet'], ['section', 'Section'], ['story_type', 'Type'], ['headline', 'Headline']];
    var h = '<table><thead><tr>' + cols.map(function (c) {
      var on = sort.key === c[0] || (c[0] === 'local' && sort.key === 'ts');
      return '<th data-k="' + (c[0] === 'local' ? 'ts' : c[0]) + '" class="' + (on ? 'sorted' + (sort.asc ? ' asc' : '') : '') + '">' + c[1] + '</th>';
    }).join('') + '</tr></thead><tbody>';
    h += rows.map(function (a) {
      return '<tr data-id="' + esc(a.id) + '" class="' + (a.visible ? '' : 'future') + (sel === a.id ? ' sel' : '') + '">' +
        '<td class="m">' + esc(a.d) + '</td><td class="m">' + esc(a.local) + '</td>' +
        '<td><span class="dot" style="background:' + COLORS[a.outlet] + '"></span> ' + esc(a.outlet_name) + '</td>' +
        '<td>' + esc(a.section) + '</td><td>' + typeTag(a) + '</td><td>' + esc(a.headline) + '</td></tr>';
    }).join('');
    h += '</tbody></table>';
    $('results').innerHTML = rows.length ? h : '<div class="empty">No articles match these filters.</div>';
  }

  function renderDay(rows) {
    var days = {};
    rows.forEach(function (a) { days[a.day] = (days[a.day] || 0) + 1; });
    var list = Object.keys(days).map(Number).sort(function (a, b) { return a - b; });
    if (!list.length) { $('results').innerHTML = '<div class="empty">No articles match these filters.</div>'; return; }
    if (dayPick === null || !days[dayPick]) dayPick = list.indexOf(0) >= 0 ? 0 : list[0];
    var i = list.indexOf(dayPick);
    var opts = list.map(function (d) { return '<option value="' + d + '"' + (d === dayPick ? ' selected' : '') + '>' + dTag(d) + ' · ' + dayDate(d) + ' (' + days[d] + ')</option>'; }).join('');
    var outs = Object.keys(F.outlets).length ? OUTLETS.filter(function (o) { return F.outlets[o.slug]; }) : OUTLETS;
    var cols = outs.map(function (o) {
      var items = rows.filter(function (a) { return a.day === dayPick && a.outlet === o.slug; }).sort(function (x, y) { return x.ts - y.ts; });
      return '<div class="col" style="--oc:' + COLORS[o.slug] + '"><h3>' + esc(o.name) + '</h3>' +
        (items.length ? items.map(function (a) {
          return '<div class="it' + (sel === a.id ? ' sel' : '') + '" data-id="' + esc(a.id) + '"><div class="t">' + esc(timeOf(a)) + ' ' + typeTag(a) + '</div>' + esc(a.headline) + '</div>';
        }).join('') : '<div class="none">No stories this day.</div>') + '</div>';
    }).join('');
    $('results').innerHTML = '<div class="dayhead"><button class="btn" data-day="' + (list[i - 1] !== undefined ? list[i - 1] : '') + '"' + (i > 0 ? '' : ' disabled') + '>◂ Prev</button>' +
      '<select id="daysel" aria-label="Day">' + opts + '</select>' +
      '<button class="btn" data-day="' + (list[i + 1] !== undefined ? list[i + 1] : '') + '"' + (i < list.length - 1 ? '' : ' disabled') + '>Next ▸</button>' +
      '<span class="note">Side-by-side coverage of one day</span></div><div class="daycols">' + cols + '</div>';
  }

  function renderArc(rows) {
    if (!F.arc) {
      var arcs = {};
      rows.forEach(function (a) { a.storylines.forEach(function (s) { (arcs[s] = arcs[s] || []).push(a); }); });
      var names = Object.keys(arcs).sort(function (x, y) { return arcs[y].length - arcs[x].length; });
      $('results').innerHTML = names.length ? '<div class="tline"><p class="note">Pick a storyline to see it across every outlet.</p>' + names.map(function (n) {
        var first = arcs[n].reduce(function (m, a) { return Math.min(m, a.day); }, 999), last = arcs[n].reduce(function (m, a) { return Math.max(m, a.day); }, -999);
        return '<div class="ev" style="--oc:var(--acc)" data-arc="' + esc(n) + '"><span class="t">' + arcs[n].length + ' stories</span><span><b>' + esc(n) + '</b><br><span class="o">' + dTag(first) + ' to ' + dTag(last) + '</span></span></div>';
      }).join('') + '</div>' : '<div class="empty">No storylines in these results.</div>';
      return;
    }
    var items = rows.filter(function (a) { return a.storylines.indexOf(F.arc) >= 0; }).sort(function (x, y) { return x.ts - y.ts; });
    var h = '<div class="tline"><p class="note"><b>' + esc(F.arc) + '</b> · ' + items.length + ' stories across ' + Object.keys(items.reduce(function (m, a) { m[a.outlet] = 1; return m; }, {})).length + ' outlets</p>', cur = null;
    items.forEach(function (a) {
      if (a.day !== cur) { cur = a.day; h += '<div class="date">' + dTag(a.day) + ' · ' + dayDate(a.day) + '</div>'; }
      h += '<div class="ev' + (sel === a.id ? ' sel' : '') + '" style="--oc:' + COLORS[a.outlet] + '" data-id="' + esc(a.id) + '"><span class="t">' + esc(timeOf(a)) + '</span><span>' + typeTag(a) + ' ' + esc(a.headline) + '<br><span class="o">' + esc(a.outlet_name) + ' · ' + esc(a.section) + (a.visible ? '' : ' · upcoming') + '</span></span></div>';
    });
    $('results').innerHTML = items.length ? h + '</div>' : '<div class="empty">No stories in this storyline match the filters.</div>';
  }

  // ------------------------------------------------------------ reader
  function linkList(ids) {
    return ids.filter(function (i) { return byId[i]; }).map(function (i) {
      var r = byId[i];
      return '<li><a data-go="' + esc(i) + '" tabindex="0"><span class="t">' + esc(r.d) + '</span><span class="dot" style="background:' + COLORS[r.outlet] + '"></span> ' + esc(r.headline) + '</a> <span class="note">' + esc(r.outlet_name) + '</span></li>';
    }).join('');
  }
  function read(id) {
    var a = byId[id]; if (!a) return;
    sel = id;
    var tags = function (arr) { return arr.length ? '<div class="tags">' + arr.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('') + '</div>' : '<p class="note">None</p>'; };
    var rel = linkList(a.related), arc = linkList(a.arc_links), fu = a.follows_up ? linkList([a.follows_up]) : '';
    $('reader').innerHTML =
      '<div>' + typeTag(a) + ' <span class="vis ' + (a.visible ? 'on">PUBLISHED' : 'off">UPCOMING') + '</span></div>' +
      '<h1>' + esc(a.headline) + '</h1><p class="dek">' + esc(a.summary) + '</p>' +
      '<div class="acts"><button class="btn primary" id="setclock">Set clock to this story</button>' +
      '<a class="btn" href="' + esc(a.url) + '" target="_blank" rel="noopener"' + (a.visible ? '' : ' aria-disabled="true" tabindex="-1"') + '>Open on site ↗</a></div>' +
      '<dl class="meta"><dt>ID</dt><dd>' + esc(a.id) + ' · public ' + esc(a.pid) + '</dd><dt>When</dt><dd>' + esc(a.d) + ' · ' + esc(a.local) + '</dd>' +
      '<dt>Outlet</dt><dd>' + esc(a.outlet_name) + ' · ' + esc(a.section) + '</dd><dt>By</dt><dd>' + esc(a.authors.join(', ')) + '</dd>' +
      '<dt>Words</dt><dd>' + a.words + '</dd><dt>Storylines</dt><dd>' + esc(a.storylines.join(' · ') || '—') + '</dd><dt>URL</dt><dd>' + esc(a.url) + '</dd></dl>' +
      '<div class="body">' + a.body.map(function (p) { return '<p>' + esc(p) + '</p>'; }).join('') + '</div>' +
      '<h4>People</h4>' + tags(a.people) + '<h4>Places</h4>' + tags(a.places) + '<h4>Topics</h4>' + tags(a.topics) +
      (fu ? '<h4>Follows up</h4><ul class="rl">' + fu + '</ul>' : '') +
      (arc ? '<h4>Storyline neighbors</h4><ul class="rl">' + arc + '</ul>' : '') +
      (rel ? '<h4>Related coverage</h4><ul class="rl">' + rel + '</ul>' : '');
    $('setclock').addEventListener('click', function () {
      fetch('/api/gm/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'set', ts: a.ts, note: 'from explorer: ' + a.headline.slice(0, 60) }) })
        .then(function () { return load(true); });
    });
    document.querySelectorAll('#results .sel').forEach(function (e) { e.classList.remove('sel'); });
    document.querySelectorAll('#results [data-id="' + CSS.escape(id) + '"]').forEach(function (e) { e.classList.add('sel'); });
    if (window.matchMedia('(max-width:1000px)').matches) $('reader').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // ------------------------------------------------------------ events
  var t;
  $('q').addEventListener('input', function () { clearTimeout(t); t = setTimeout(function () { F.q = $('q').value; render(); }, 150); });
  $('type').addEventListener('change', function () { F.type = this.value; render(); });
  $('arc').addEventListener('change', function () { F.arc = this.value; render(); });
  $('vis').addEventListener('change', function () { F.vis = this.value; render(); });
  $('dmin').addEventListener('change', function () { F.dmin = +this.value; render(); });
  $('dmax').addEventListener('change', function () { F.dmax = +this.value; render(); });
  $('outlets').addEventListener('click', function (e) {
    var b = e.target.closest('[data-o]'); if (!b) return;
    var s = b.dataset.o; if (F.outlets[s]) delete F.outlets[s]; else F.outlets[s] = 1;
    b.classList.toggle('on', !!F.outlets[s]); b.setAttribute('aria-pressed', F.outlets[s] ? 'true' : 'false'); render();
  });
  $('views').addEventListener('click', function (e) {
    var b = e.target.closest('[data-v]'); if (!b) return;
    view = b.dataset.v; document.querySelectorAll('#views button').forEach(function (x) { x.classList.toggle('on', x === b); }); render();
  });
  $('clear').addEventListener('click', function () {
    F.q = ''; F.type = ''; F.arc = ''; F.vis = 'all'; F.outlets = {};
    $('q').value = ''; $('type').value = ''; $('arc').value = ''; $('vis').value = 'all';
    F.dmin = +$('dmin').min; F.dmax = +$('dmax').max; $('dmin').value = F.dmin; $('dmax').value = F.dmax;
    document.querySelectorAll('#outlets .chip').forEach(function (c) { c.classList.remove('on'); c.setAttribute('aria-pressed', 'false'); });
    render();
  });
  $('dl').addEventListener('click', function () {
    var rows = filtered().map(function (a) { var o = {}; Object.keys(a).forEach(function (k) { if (k[0] !== '_') o[k] = a[k]; }); return o; });
    var blob = new Blob([JSON.stringify({ exported: new Date().toISOString(), filters: { q: F.q, type: F.type, storyline: F.arc, status: F.vis, day_from: F.dmin, day_to: F.dmax, outlets: Object.keys(F.outlets) }, count: rows.length, articles: rows }, null, 1)], { type: 'application/json' });
    var url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = 'rafael-news-corpus-' + rows.length + '.json';
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
  });
  $('results').addEventListener('click', function (e) {
    var th = e.target.closest('th[data-k]');
    if (th) { var k = th.dataset.k; sort = { key: k, asc: sort.key === k ? !sort.asc : true }; render(); return; }
    var dayb = e.target.closest('[data-day]');
    if (dayb && dayb.dataset.day !== '') { dayPick = +dayb.dataset.day; render(); return; }
    var arcb = e.target.closest('[data-arc]');
    if (arcb) { F.arc = arcb.dataset.arc; $('arc').value = F.arc; render(); return; }
    var row = e.target.closest('[data-id]');
    if (row) read(row.dataset.id);
  });
  $('results').addEventListener('change', function (e) { if (e.target.id === 'daysel') { dayPick = +e.target.value; render(); } });
  $('reader').addEventListener('click', function (e) { var g = e.target.closest('[data-go]'); if (g) { e.preventDefault(); read(g.dataset.go); } });
  $('reader').addEventListener('keydown', function (e) { var g = e.target.closest('[data-go]'); if (g && e.key === 'Enter') read(g.dataset.go); });

  load(false).then(watchClock);
})();
