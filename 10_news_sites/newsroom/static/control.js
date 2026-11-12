/* Newsroom Control: game-master console. Polls /api/gm/state, sends /api/gm/action. */
(function () {
  'use strict';
  var COLORS = { ledger: '#1f4e8c', harborline6: '#c0392b', coastline: '#2a7f7f', gulfwater: '#e67e22',
    sabal: '#22a35a', continental: '#d93025', 'anchor-rotor': '#8a7a2c', kncb: '#e0a800' };
  var S = null, dragging = false, stamps = null, cache = {}, failures = 0;
  var $ = function (id) { return document.getElementById(id); };

  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function nthSunday(y, m, n) { var d = new Date(Date.UTC(y, m, 1)); return Date.UTC(y, m, 1 + (7 - d.getUTCDay()) % 7 + 7 * (n - 1)); }
  function off(ts) { var y = new Date(ts * 1000).getUTCFullYear(); var a = nthSunday(y, 2, 2) / 1000 + 28800, b = nthSunday(y, 10, 1) / 1000 + 25200; return ts >= a && ts < b ? -5 : -6; }
  var D0 = Date.UTC(2027, 8, 14);
  var MONTHS = ['Jan.', 'Feb.', 'March', 'April', 'May', 'June', 'July', 'Aug.', 'Sept.', 'Oct.', 'Nov.', 'Dec.'];
  function dlabel(ts) {
    var o = off(ts), d = new Date((ts + o * 3600) * 1000);
    var day = Math.round((Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()) - D0) / 86400000);
    return 'D' + (day >= 0 ? '+' : '-') + Math.abs(day) + ' ' + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes()) + ' ' + (o === -5 ? 'CDT' : 'CST');
  }
  function ldate(ts) { var o = off(ts), d = new Date((ts + o * 3600) * 1000); return MONTHS[d.getUTCMonth()] + ' ' + d.getUTCDate() + ', ' + d.getUTCFullYear(); }
  function span(sec) {
    sec = Math.abs(sec);
    if (sec >= 86400) return (sec / 86400).toFixed(sec % 86400 ? 1 : 0) + ' day' + (sec >= 172800 ? 's' : '');
    if (sec >= 3600) return (sec / 3600).toFixed(sec % 3600 ? 1 : 0) + ' h';
    return Math.round(sec / 60) + ' min';
  }
  function setOnce(key, el, html) { if (cache[key] !== html) { cache[key] = html; el.innerHTML = html; } }

  // ------------------------------------------------------------ server calls
  function act(body) {
    return fetch('/api/gm/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      .then(function (r) { if (r.status === 401) { location.href = '/gm/login?next=/control'; throw new Error('auth'); } return r.json(); })
      .then(function (s) { S = s; render(); })
      .catch(function () {});
  }
  function poll() {
    fetch('/api/gm/state', { cache: 'no-store' })
      .then(function (r) { if (r.status === 401) { location.href = '/gm/login?next=/control'; throw new Error('auth'); } return r.json(); })
      .then(function (s) { S = s; failures = 0; conn(true); render(); })
      .catch(function () { failures++; conn(false); })
      .then(function () { setTimeout(poll, 1000); });
  }
  function conn(ok) {
    var c = $('conn');
    c.textContent = ok ? 'live · ' + new Date().toLocaleTimeString() : 'server not responding (' + failures + ')';
    c.className = 'conn' + (ok ? '' : ' bad');
  }
  function loadStamps() {
    fetch('/api/gm/articles', { cache: 'no-store' }).then(function (r) { return r.json(); }).then(function (d) {
      stamps = d.articles.map(function (a) { return a.ts; }).sort(function (a, b) { return a - b; });
      drawDensity();
    }).catch(function () {});
  }

  // ------------------------------------------------------------ render
  function render() {
    if (!S) return;
    $('dlabel').textContent = S.d;
    $('local').textContent = S.date_long + ' · ' + S.local.split(', ').slice(-1)[0];
    var st = $('state');
    st.textContent = S.playing ? '▶ PLAYING' : '❚❚ PAUSED';
    st.className = 'state ' + (S.playing ? 'play' : 'pause');
    $('pub').textContent = S.published + ' of ' + S.total + ' stories published';
    $('rate').textContent = span(S.rate) + ' per second';
    $('seq').textContent = '#' + S.seq;
    $('lamp').className = 'lamp' + (S.playing ? ' on' : '');
    $('play').textContent = S.playing ? 'Pause' : 'Play';
    document.querySelectorAll('#speeds button').forEach(function (b) { b.classList.toggle('on', +b.dataset.rate === S.rate); });
    $('pob').checked = !!S.pause_on_breaking;

    // port + alerts
    var strip = '<div class="chiprow">';
    if (S.port) strip += '<span class="chip" title="' + esc(S.port.detail) + '"><b>PORT</b>' + esc(S.port.label) + '</span>';
    strip += '</div><div class="chiprow">';
    if (S.alerts && S.alerts.length) S.alerts.forEach(function (a) { strip += '<span class="chip lvl-' + esc(a.level) + '"><b>' + esc(a.level.toUpperCase()) + '</b>' + esc(a.text) + '</span>'; });
    else strip += '<span class="chip">No active public alerts</span>';
    setOnce('strip', $('strip'), strip + '</div>');

    // timeline
    if (!dragging) {
      var sc = $('scrub');
      sc.min = S.start; sc.max = S.end; sc.value = S.now;
    }
    $('tl-start').textContent = S.start_d + ' · ' + ldate(S.start);
    $('tl-end').textContent = S.end_d + ' · ' + ldate(S.end);
    placeHead(dragging ? +$('scrub').value : S.now);
    var ticks = S.milestones.map(function (m) {
      var p = (m.ts - S.start) / (S.end - S.start) * 100;
      return '<div class="tick' + (/Landfall/.test(m.label) ? ' d0' : '') + '" style="left:' + p.toFixed(3) + '%" title="' + esc(m.d + ' · ' + m.label) + '"></div>';
    }).join('');
    setOnce('ticks', $('ticks'), ticks);
    if (stamps) { $('tl-count').textContent = stamps.length + ' stories'; if (cache.densNow !== Math.floor(S.now / 3600)) drawDensity(); }

    // up next
    var up = S.upcoming.length ? S.upcoming.map(function (u) {
      return '<li class="q' + (u.story_type === 'breaking' ? ' breaking' : '') + '">' +
        '<span class="when">' + esc(u.d) + '</span>' +
        '<span class="hl"><span class="type' + (u.story_type === 'breaking' ? ' breaking' : '') + '">' + esc(u.story_type) + '</span>' + esc(u.headline) + '</span>' +
        '<button class="btn sm" data-release="' + esc(u.id) + '" title="Publish this story now">Release now</button>' +
        '<span class="sub"><span class="odot" style="background:' + (COLORS[u.outlet] || '#888') + '"></span>' + esc(u.outlet_name) + ' · ' + esc(u.section) + ' · ' + esc(u.local) + (u.held ? ' · <b>outlet on hold</b>' : '') + '</span></li>';
    }).join('') : '<li class="empty">Nothing left to publish.</li>';
    setOnce('up', $('upnext'), up);

    // outlets
    var held = 0;
    var og = S.outlets.map(function (o) {
      if (o.held) held++;
      var pct = o.total ? Math.round(o.visible / o.total * 100) : 0;
      var bc = o.status ? '<span class="bc">' + esc(o.status.status === 'off-air' ? 'OFF AIR' : o.status.status.toUpperCase()) + '</span>' : '';
      return '<div class="oc' + (o.held ? ' held' : '') + '" style="--oc:' + (COLORS[o.slug] || 'var(--acc)') + '">' +
        '<div class="nm"><span>' + esc(o.name) + '</span><small>' + o.visible + '/' + o.total + '</small></div>' +
        '<div class="bar"><i style="width:' + pct + '%"></i></div>' +
        (bc || o.held ? '<div>' + bc + (o.held ? ' <span class="bc">ON HOLD since ' + esc(o.held_since) + '</span>' : '') + '</div>' : '') +
        '<div class="ln">Last: ' + (o.last ? '<b>' + esc(o.last.headline) + '</b> · ' + esc(o.last.d) : '<i>nothing yet</i>') + '</div>' +
        '<div class="ln">Next: ' + (o.next ? '<b>' + esc(o.next.headline) + '</b> · ' + esc(o.next.d) : '<i>none</i>') + '</div>' +
        '<div class="acts"><button class="btn sm" data-hold="' + o.slug + '" data-on="' + (o.held ? 0 : 1) + '">' + (o.held ? 'Resume' : 'Hold') + '</button>' +
        '<button class="btn sm" data-next="' + o.slug + '"' + (o.next && !o.held ? '' : ' disabled') + '>Next story</button>' +
        '<a class="btn sm" href="/' + o.slug + '/" target="_blank" rel="noopener" style="text-decoration:none">Open site ↗</a></div></div>';
    }).join('');
    setOnce('og', $('outlets'), og);
    $('outlets-sum').textContent = held ? held + ' on hold' : 'all live';

    // milestones
    var firstFuture = S.milestones.findIndex(function (m) { return !m.passed; });
    var ms = S.milestones.map(function (m, i) {
      return '<li class="ms' + (m.passed ? ' passed' : '') + (i === firstFuture ? ' next' : '') + '" data-ms="' + m.i + '" tabindex="0" role="button">' +
        '<span class="when">' + esc(m.d) + '</span><span>' + esc(m.label) + '</span></li>';
    }).join('');
    setOnce('ms', $('milestones'), ms);

    // log
    var lg = S.log.length ? S.log.map(function (e) {
      var items = (e.items || []).slice(-5).reverse().map(function (x) { return '<li>' + esc(x.headline) + '</li>'; }).join('');
      var more = e.count > 5 ? '<li><i>+' + (e.count - 5) + ' more</i></li>' : '';
      return '<li class="lg ' + esc(e.kind) + '"><div class="h"><span class="k">' + esc(e.kind) + '</span><span>' + esc(e.d) + '</span><span>at ' + esc(e.wall) + '</span>' +
        (e.count ? '<span>' + e.count + ' stor' + (e.count === 1 ? 'y' : 'ies') + '</span>' : '') + (e.note ? '<span>' + esc(e.note) + '</span>' : '') + '</div>' +
        (items ? '<ul>' + items + more + '</ul>' : '') + '</li>';
    }).join('') : '<li class="empty">No activity yet.</li>';
    setOnce('log', $('log'), lg);
  }

  function placeHead(ts) {
    if (!S) return;
    var p = (ts - S.start) / (S.end - S.start) * 100;
    $('playhead').style.left = Math.max(0, Math.min(100, p)).toFixed(3) + '%';
  }

  function drawDensity() {
    if (!stamps || !S) return;
    var cv = $('density'), box = cv.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    cv.width = Math.max(1, Math.round(box.width * dpr)); cv.height = Math.max(1, Math.round(box.height * dpr));
    var g = cv.getContext('2d'), days = Math.ceil((S.end - S.start) / 86400), bins = new Array(days).fill(0), past = new Array(days).fill(0);
    stamps.forEach(function (t) { var i = Math.floor((t - S.start) / 86400); if (i >= 0 && i < days) { bins[i]++; if (t <= S.now) past[i]++; } });
    var max = Math.max.apply(null, bins) || 1, w = cv.width / days, cs = getComputedStyle(document.documentElement);
    var cBar = cs.getPropertyValue('--bar').trim(), cPast = cs.getPropertyValue('--bar-past').trim();
    g.clearRect(0, 0, cv.width, cv.height);
    for (var i = 0; i < days; i++) {
      if (!bins[i]) continue;
      var h = (bins[i] / max) * (cv.height - 10 * dpr), x = i * w;
      g.fillStyle = cBar; g.fillRect(x + w * 0.12, cv.height - h, Math.max(1, w * 0.76), h);
      if (past[i]) { var hp = (past[i] / max) * (cv.height - 10 * dpr); g.fillStyle = cPast; g.fillRect(x + w * 0.12, cv.height - hp, Math.max(1, w * 0.76), hp); }
    }
    cache.densNow = Math.floor(S.now / 3600);
  }

  // ------------------------------------------------------------ events
  $('play').addEventListener('click', function () { act(S && S.playing ? { action: 'pause' } : { action: 'play' }); });
  $('speeds').addEventListener('click', function (e) { var b = e.target.closest('button[data-rate]'); if (b) act({ action: 'rate', rate: +b.dataset.rate }); });
  document.querySelectorAll('[data-step]').forEach(function (b) { b.addEventListener('click', function () { act({ action: 'step', seconds: +b.dataset.step }); }); });
  $('next').addEventListener('click', function () { act({ action: 'next' }); });
  $('pob').addEventListener('change', function (e) { act({ action: 'pause_on_breaking', on: e.target.checked }); });
  $('reset').addEventListener('click', function () { $('confirm').classList.add('show'); $('reset-yes').focus(); });
  $('reset-no').addEventListener('click', function () { $('confirm').classList.remove('show'); });
  $('reset-yes').addEventListener('click', function () { $('confirm').classList.remove('show'); act({ action: 'reset' }); });

  var sc = $('scrub');
  sc.addEventListener('input', function () { dragging = true; $('tl-preview').textContent = dlabel(+sc.value) + ' · ' + ldate(+sc.value); placeHead(+sc.value); });
  sc.addEventListener('change', function () {
    var ts = +sc.value;
    act({ action: 'set', ts: ts }).then(function () { dragging = false; $('tl-preview').textContent = 'drag to move the clock'; });
  });

  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-release],[data-hold],[data-next],[data-ms]');
    if (!t) return;
    if (t.dataset.release) act({ action: 'release', id: t.dataset.release });
    else if (t.dataset.hold) act({ action: 'hold', outlet: t.dataset.hold, on: t.dataset.on === '1' });
    else if (t.dataset.next) act({ action: 'next', outlet: t.dataset.next });
    else if (t.dataset.ms) act({ action: 'milestone', index: +t.dataset.ms });
  });
  $('milestones').addEventListener('keydown', function (e) {
    var t = e.target.closest('[data-ms]'); if (t && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); act({ action: 'milestone', index: +t.dataset.ms }); }
  });
  document.addEventListener('keydown', function (e) {
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === ' ' && tag !== 'button') { e.preventDefault(); act(S && S.playing ? { action: 'pause' } : { action: 'play' }); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); act({ action: 'step', seconds: e.shiftKey ? 86400 : 3600 }); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); act({ action: 'step', seconds: e.shiftKey ? -86400 : -3600 }); }
    else if (e.key === 'n' || e.key === 'N') { act({ action: 'next' }); }
  });
  window.addEventListener('resize', function () { cache.densNow = null; drawDensity(); });
  if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { cache.densNow = null; drawDensity(); });

  poll();
  loadStamps();
})();
