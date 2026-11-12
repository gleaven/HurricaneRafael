/* Coastal Bend Newsroom live updates.
   Polls the scenario clock, keeps on-page dates ticking, and when this outlet's content
   changes, refetches the page and swaps #nr-root, flagging stories that just appeared. */
(function () {
  var cfgEl = document.getElementById('nr-config');
  if (!cfgEl) return;
  var cfg = JSON.parse(cfgEl.textContent);
  var sig = cfg.sig, lang = cfg.lang || 'en', pollMs = 1500, busy = false;

  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  var AP = ['Jan.','Feb.','March','April','May','June','July','Aug.','Sept.','Oct.','Nov.','Dec.'];
  var DAYS = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
  var ESM = ['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
  var ESD = ['lunes','martes','miércoles','jueves','viernes','sábado','domingo'];

  function nthSunday(y, m, n) { var d = new Date(Date.UTC(y, m, 1)); var add = (7 - d.getUTCDay()) % 7; return Date.UTC(y, m, 1 + add + 7 * (n - 1)); }
  function offset(ts) {
    var y = new Date(ts * 1000).getUTCFullYear();
    var start = nthSunday(y, 2, 2) / 1000 + 8 * 3600, end = nthSunday(y, 10, 1) / 1000 + 7 * 3600;
    return (ts >= start && ts < end) ? -5 : -6;
  }
  function parts(ts) {
    var o = offset(ts), d = new Date((ts + o * 3600) * 1000);
    return { y: d.getUTCFullYear(), m: d.getUTCMonth(), d: d.getUTCDate(), wd: (d.getUTCDay() + 6) % 7,
             h: d.getUTCHours(), mi: d.getUTCMinutes(), tz: o === -5 ? 'CDT' : 'CST' };
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function timeAp(p, tz) {
    var t;
    if (p.h === 12 && p.mi === 0) t = 'noon';
    else if (p.h === 0 && p.mi === 0) t = 'midnight';
    else t = ((p.h % 12) || 12) + ':' + pad(p.mi) + ' ' + (p.h < 12 ? 'a.m.' : 'p.m.');
    return tz ? t + ' ' + p.tz : t;
  }
  var F = {
    'date-long': function (p) { return DAYS[p.wd] + ', ' + MONTHS[p.m] + ' ' + p.d + ', ' + p.y; },
    'date-ap': function (p) { return AP[p.m] + ' ' + p.d + ', ' + p.y; },
    'time-ap': function (p) { return timeAp(p, true); },
    'time-24': function (p) { return pad(p.h) + ':' + pad(p.mi) + ' ' + p.tz; },
    'date-es': function (p) { return ESD[p.wd] + ', ' + p.d + ' de ' + ESM[p.m] + ' de ' + p.y; },
    'time-es': function (p) { return ((p.h % 12) || 12) + ':' + pad(p.mi) + ' ' + (p.h < 12 ? 'a.m.' : 'p.m.'); },
    'datetime-ap': function (p) { return AP[p.m] + ' ' + p.d + ', ' + p.y + ', ' + timeAp(p, true); }
  };
  function ago(ts, now, lg) {
    var s = Math.max(0, Math.floor(now - ts));
    if (lg === 'es') {
      if (s < 60) return 'hace un momento';
      if (s < 3600) return 'hace ' + Math.floor(s / 60) + ' min';
      if (s < 86400) return 'hace ' + Math.floor(s / 3600) + ' h';
      if (s < 172800) return 'ayer';
      var q = parts(ts); return q.d + ' de ' + ESM[q.m] + ' de ' + q.y;
    }
    if (s < 60) return 'just now';
    if (s < 3600) return Math.floor(s / 60) + ' min ago';
    if (s < 86400) { var h = Math.floor(s / 3600); return h + ' hour' + (h > 1 ? 's' : '') + ' ago'; }
    if (s < 172800) return 'Yesterday';
    var p = parts(ts); return AP[p.m] + ' ' + p.d + ', ' + p.y;
  }
  function tick(now) {
    var p = parts(now);
    document.querySelectorAll('[data-nr-clock]').forEach(function (el) {
      var f = F[el.getAttribute('data-nr-clock')]; if (f) el.textContent = f(p);
    });
    document.querySelectorAll('[data-nr-ago]').forEach(function (el) {
      el.textContent = ago(+el.getAttribute('data-nr-ago'), now, el.getAttribute('data-nr-lang') || lang);
    });
  }

  function ids() {
    var s = {};
    document.querySelectorAll('[data-article-id]').forEach(function (e) { s[e.getAttribute('data-article-id')] = 1; });
    return s;
  }
  var known = ids();

  function toast(n) {
    var t = document.getElementById('nr-toast'); if (!t) return;
    t.textContent = lang === 'es' ? (n === 1 ? '1 noticia nueva' : n + ' noticias nuevas') : (n === 1 ? '1 new story' : n + ' new stories');
    t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(function () { t.classList.remove('show'); }, 5000);
    t.onclick = function () { window.scrollTo({ top: 0, behavior: 'smooth' }); t.classList.remove('show'); };
  }
  function mark(fresh) {
    if (!fresh.length) return;
    fresh.forEach(function (id) {
      document.querySelectorAll('[data-article-id="' + id + '"]').forEach(function (el) {
        el.classList.add('nr-new');
        if (el.hasAttribute('data-nr-nobadge') || el.querySelector('.nr-new-badge')) return;
        var b = document.createElement('span'); b.className = 'nr-new-badge'; b.textContent = lang === 'es' ? 'Nuevo' : 'New';
        var h = el.querySelector('h1,h2,h3,h4') || el.querySelector('a') || el;
        h.insertBefore(b, h.firstChild);
      });
    });
    toast(fresh.length);
  }

  function refresh() {
    return fetch(location.href, { cache: 'no-store', headers: { 'X-NR-Live': '1' } })
      .then(function (r) { return r.text(); })
      .then(function (t) {
        var doc = new DOMParser().parseFromString(t, 'text/html');
        var src = doc.getElementById('nr-root'), dst = document.getElementById('nr-root');
        if (!src || !dst) { location.reload(); return; }
        dst.innerHTML = src.innerHTML;
        document.title = doc.title;
        var nc = doc.getElementById('nr-config');
        if (nc) { try { sig = JSON.parse(nc.textContent).sig; } catch (e) {} }
        var now = ids(), fresh = [];
        Object.keys(now).forEach(function (k) { if (!known[k]) fresh.push(k); });
        var first = Object.keys(known).length === 0 && fresh.length > 30;
        known = now;
        if (!first) mark(fresh);
        document.dispatchEvent(new CustomEvent('nr:refreshed'));
      });
  }

  function poll() {
    if (busy) return schedule();
    busy = true;
    fetch('/api/clock?outlet=' + encodeURIComponent(cfg.outlet), { cache: 'no-store' })
      .then(function (r) { return r.json(); })
      .then(function (c) {
        if (c.poll_ms) pollMs = c.poll_ms;
        tick(c.outlet_now || c.now);
        if (c.sig && c.sig !== sig) { sig = c.sig; return refresh(); }
      })
      .catch(function () {})
      .then(function () { busy = false; schedule(); });
  }
  function schedule() { setTimeout(poll, document.hidden ? 6000 : pollMs); }
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
  schedule();
})();
