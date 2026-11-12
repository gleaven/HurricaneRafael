"""Participant entry pages: the newsstand (/), team data-feed docs (/feeds) and not-found.

ctx comes from server.portal_ctx: now, outlets (each with visible, latest view or None, held,
slug, name, kind, lang), host, sig, poll_ms. Pages follow the live-update contract in
nr/common.py (outlet "_all"), so counts and latest headlines refresh as the clock moves.
Nothing here may reveal scenario-internal timing (no D-notation, no story ids).
"""
import datetime as dt
import json

from nr import common as C
from nr.common import esc

ACCENTS = {
    "ledger": ("#0a1628", "#1a4b8c"),
    "harborline6": ("#0d1b2e", "#c0392b"),
    "coastline": ("#1a4f4f", "#2a7f7f"),
    "gulfwater": ("#0d2137", "#e67e22"),
    "sabal": ("#0f172a", "#22c55e"),
    "continental": ("#1a1a1a", "#d93025"),
    "anchor-rotor": ("#1a2f1a", "#c8a84b"),
    "kncb": ("#c0392b", "#f39c12"),
}

CSS = """
:root{--bg:#f3f1ec;--panel:#fffdf9;--fg:#1b1a17;--muted:#6a665d;--line:#ddd7cb;--acc:#0f5c63;--code:#f0ece3;
  --serif:"Source Serif 4",Georgia,serif;--sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#121211;--panel:#1b1a18;--fg:#ebe8e1;--muted:#a29d92;--line:#33312c;--acc:#5fb7bf;--code:#24221f;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 var(--sans)}
a{color:var(--acc)}
.wrap{max-width:1180px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header.mast{border-bottom:1px solid var(--line);background:var(--panel)}
header.mast .wrap{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:10px 24px;padding-block:22px 18px}
.title{font:600 clamp(28px,4.4vw,44px)/1.05 var(--serif);letter-spacing:-.01em;margin:0;text-wrap:balance}
.title a{color:inherit;text-decoration:none}
.tag{color:var(--muted);margin:6px 0 0;font-size:15px}
.now{text-align:right;font-size:14px;color:var(--muted)}
.now b{display:block;color:var(--fg);font:600 17px var(--serif)}
nav.sub{display:flex;gap:18px;flex-wrap:wrap;padding-block:10px;font-size:14px;font-weight:500}
nav.sub a{text-decoration:none}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px;padding-block:26px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column;min-width:0}
.band{background:linear-gradient(120deg,var(--a1),var(--a2));color:#fff;padding:16px 16px 14px}
.band h2{margin:0;font:700 21px/1.15 var(--serif);text-wrap:balance}
.band p{margin:4px 0 0;font-size:13px;opacity:.88}
.cbody{padding:14px 16px 16px;display:flex;flex-direction:column;gap:10px;flex:1}
.count{font:500 12px var(--mono);color:var(--muted);letter-spacing:.03em;text-transform:uppercase}
.latest{flex:1}
.latest a{color:var(--fg);text-decoration:none;font:600 17px/1.3 var(--serif)}
.latest a:hover{text-decoration:underline}
.latest .meta{font-size:13px;color:var(--muted);margin-top:4px}
.latest .none{color:var(--muted);font-style:italic;font-size:14px}
.acts{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-block;border:1px solid var(--line);border-radius:8px;padding:7px 12px;font-size:14px;font-weight:600;text-decoration:none;color:var(--fg)}
.btn.go{background:var(--a2);border-color:var(--a2);color:#fff}
.note{color:var(--muted);font-size:14px;padding-block:6px 30px;border-top:1px solid var(--line)}
footer{color:var(--muted);font-size:13px;padding-block:18px 34px;border-top:1px solid var(--line)}
.doc{max-width:76ch;padding-block:26px 10px}
.doc h2{font:600 24px var(--serif);margin:34px 0 10px}
.doc h3{font-size:16px;margin:22px 0 6px}
.doc p,.doc li{max-width:72ch}
code{font:14px var(--mono);background:var(--code);padding:1px 5px;border-radius:4px}
.codebox{position:relative;margin:10px 0 18px}
.codebox pre{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto;font:13.5px/1.5 var(--mono);margin:0}
.codebox button{position:absolute;top:8px;right:8px;border:1px solid var(--line);background:var(--panel);color:var(--fg);border-radius:6px;padding:4px 10px;font:600 12px var(--sans);cursor:pointer}
.tbl{overflow-x:auto;margin:10px 0 18px}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.callout{border-left:4px solid var(--acc);background:var(--panel);padding:12px 16px;border-radius:0 10px 10px 0}
.nf{padding-block:70px;text-align:center}
.nf h2{font:600 34px var(--serif);margin:0 0 8px}
"""

FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&"
         "family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap")

COPY_JS = """<script>
document.addEventListener('click',function(e){var b=e.target.closest('[data-copy]');if(!b)return;
var pre=document.getElementById(b.getAttribute('data-copy'));if(!pre)return;var txt=pre.textContent;
function sel(){var r=document.createRange();r.selectNodeContents(pre);var s=getSelection();s.removeAllRanges();s.addRange(r);b.textContent='Press Ctrl+C';}
var p=navigator.clipboard?navigator.clipboard.writeText(txt):Promise.reject();
p.then(function(){b.textContent='Copied';},sel).then(function(){setTimeout(function(){b.textContent='Copy';},1800);});});
</script>"""


def _page(ctx, title, inner, extra_js=""):
    cfg = {"outlet": "_all", "sig": ctx["sig"], "now": ctx["now"], "lang": "en"}
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{esc(title)}</title>'
            '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            f'<link rel="stylesheet" href="{FONTS}"><link rel="alternate" type="application/rss+xml" title="All Coastal Bend outlets" href="/rss/all.xml">'
            f'<style>{C.BASE_CSS}{CSS}</style></head><body>'
            f'<div id="nr-root">{inner}</div>'
            '<div id="nr-toast" role="status" aria-live="polite"></div>'
            f'<script id="nr-config" type="application/json">{json.dumps(cfg)}</script>'
            f'<script src="/static/live.js" defer></script>{extra_js}</body></html>')


def _mast(ctx):
    return ('<header class="mast"><div class="wrap"><div><h1 class="title"><a href="/">Coastal Bend Newsstand</a></h1>'
            '<p class="tag">Eight newsrooms covering Corpus Christi and the Coastal Bend</p></div>'
            f'<div class="now"><b>{C.clock_span(ctx, "date-long")}</b>{C.clock_span(ctx, "time-ap")}</div></div>'
            '<div class="wrap"><nav class="sub"><a href="/">All outlets</a><a href="/feeds">Data feeds for teams</a>'
            '<a href="/rss/all.xml">Combined RSS</a></nav></div></header>')


def _footer():
    return ('<footer class="wrap">Hurricane Rafael exercise. All outlets, people and events on these sites are fictional; '
            'places are real. Stories appear as they are published.</footer>')


def _ago(a, now, lang):
    return (f'<time datetime="{esc(a["published"])}" data-nr-ago="{a["ts"]}" data-nr-lang="{lang}">'
            f'{esc(C.ago(a["ts"], now, lang))}</time>')


def render_portal(ctx):
    cards = []
    for o in ctx["outlets"]:
        a1, a2 = ACCENTS.get(o["slug"], ("#333", "#666"))
        lang = o.get("lang", "en")
        n = o["visible"]
        count = (f"{n} historia{'s' if n != 1 else ''} · {n} stor{'ies' if n != 1 else 'y'}" if lang == "es"
                 else f"{n} stor{'ies' if n != 1 else 'y'}")
        a = o.get("latest")
        if a:
            latest = (f'<div class="latest" data-article-id="{a["pid"]}"><a href="{esc(a["url"])}">{esc(a["headline"])}</a>'
                      f'<div class="meta">{esc(a["section"])} · {_ago(a, ctx["now"], lang)}</div></div>')
        else:
            latest = ('<div class="latest"><span class="none">' +
                      ("Sin noticias publicadas todavía. / No stories published yet." if lang == "es" else "No stories published yet.") +
                      "</span></div>")
        cards.append(
            f'<article class="card" style="--a1:{a1};--a2:{a2}">'
            f'<div class="band"><h2>{esc(o["name"])}</h2><p>{esc(o["kind"])}</p></div>'
            f'<div class="cbody"><div class="count">{esc(count)}</div>{latest}'
            f'<div class="acts"><a class="btn go" href="/{o["slug"]}/">{"Visitar sitio" if lang == "es" else "Visit site"} →</a>'
            f'<a class="btn" href="/{o["slug"]}/rss.xml">RSS</a></div></div></article>')
    inner = (_mast(ctx) + '<main class="wrap"><div class="grid">' + "".join(cards) + '</div>'
             '<p class="note">Building something that reads the news automatically? '
             'See <a href="/feeds">data feeds for teams</a> for the JSON API and RSS feeds.</p></main>' + _footer())
    return _page(ctx, "Coastal Bend Newsstand", inner)


def _code(cid, text):
    return (f'<div class="codebox"><button type="button" data-copy="{cid}">Copy</button>'
            f'<pre id="{cid}">{esc(text)}</pre></div>')


def render_feeds(ctx):
    host = ctx["host"]
    base = f"http://{host}"
    rows = "".join(
        f'<tr><td><code>{esc(o["slug"])}</code></td><td>{esc(o["name"])}</td><td>{esc(o["kind"])}</td>'
        f'<td>{"Spanish and English" if o.get("lang") == "es" else "English"}</td>'
        f'<td><a href="/{o["slug"]}/">site</a> · <a href="/{o["slug"]}/rss.xml">RSS</a></td></tr>'
        for o in ctx["outlets"])
    # Example values come from the current clock so the docs never hint at what lies ahead.
    now_l = C.local(ctx["now"]).replace(second=0, microsecond=0)
    pub_l = C.local(ctx["now"] - 1800).replace(second=0, microsecond=0)
    pub_u = dt.datetime.utcfromtimestamp(ctx["now"] - 1800).replace(second=0, microsecond=0).isoformat() + "Z"
    day_start = now_l.replace(hour=0, minute=0).isoformat()
    shape = """{
  "as_of": "@NOW@",   // the exercise clock when you asked
  "total": 42,                            // matching stories published so far
  "offset": 0,
  "articles": [
    {
      "id": "3f9c0a1b2c4d",               // stable public id
      "outlet": "harborline6",
      "outlet_name": "Harborline 6 News",
      "published": "@PUB@",
      "published_utc": "@PUBU@",
      "section": "Local",
      "authors": ["..."],
      "headline": "...",
      "summary": "...",
      "body": ["paragraph", "paragraph"],
      "story_type": "update",             // breaking, update, feature, explainer, analysis, ...
      "storylines": ["..."],
      "people": ["..."], "places": ["..."], "topics": ["..."],
      "url": "/harborline6/@PATH@/...",
      "words": 312,
      "related": ["<id>", "..."]          // related stories already published
    }
  ]
}""".replace("@NOW@", now_l.isoformat()).replace("@PUBU@", pub_u).replace("@PUB@", pub_l.isoformat()).replace("@PATH@", pub_l.strftime("%Y/%m/%d"))
    curl = (f'curl "{base}/api/articles?limit=20"\n'
            f'curl "{base}/api/articles?outlet=gulfwater&q=channel"\n'
            f'curl "{base}/api/articles?since={day_start}&limit=200"\n'
            f'curl "{base}/harborline6/rss.xml"')
    py = f'''import json, time, urllib.request

BASE = "{base}"
seen = set()

def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.load(r)

while True:
    data = fetch("/api/articles?limit=200")
    for a in reversed(data["articles"]):          # oldest first
        if a["id"] not in seen:
            seen.add(a["id"])
            print(a["published"], "|", a["outlet_name"], "|", a["headline"])
    time.sleep(15)                                # please poll no faster than this
'''
    inner = (_mast(ctx) + '<main class="wrap doc">'
             '<h2 style="margin-top:0">Data feeds for teams</h2>'
             '<p>Every outlet on the newsstand is also available as JSON and RSS, so your tools can read the news the same way people do.</p>'
             '<div class="callout"><p><b>Stories are released as the exercise clock advances.</b> A story is not available anywhere, '
             'on the sites, in RSS or in the API, until its publish time. Poll for new stories rather than downloading once, '
             'and please poll no faster than every 15 seconds.</p></div>'
             '<p>Times are US Central and carry their UTC offset. Each response says when it was generated in <code>as_of</code>.</p>'
             '<h2>Endpoints</h2><div class="tbl"><table><thead><tr><th>Endpoint</th><th>Returns</th></tr></thead><tbody>'
             '<tr><td><code>GET /api/articles</code></td><td>Published stories, newest first. Parameters: '
             '<code>outlet</code> (a slug below, or <code>all</code>), <code>q</code> (words that must all appear), '
             '<code>since</code> (ISO time or Unix seconds; only stories published after it), '
             '<code>limit</code> (1–500, default 50), <code>offset</code> (for paging).</td></tr>'
             '<tr><td><code>GET /api/articles/&lt;id&gt;</code></td><td>One story by its public id.</td></tr>'
             '<tr><td><code>GET /api/outlets</code></td><td>The outlets, with links and how many stories each has published.</td></tr>'
             '<tr><td><code>GET /&lt;slug&gt;/rss.xml</code></td><td>RSS 2.0 for one outlet: the latest 50 stories with full text.</td></tr>'
             '<tr><td><code>GET /rss/all.xml</code></td><td>RSS 2.0 across every outlet: the latest 100 stories.</td></tr>'
             '</tbody></table></div>'
             '<h2>Outlets</h2><div class="tbl"><table><thead><tr><th>Slug</th><th>Name</th><th>Type</th><th>Language</th><th>Links</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>'
             '<h2>Response shape</h2>' + _code("shape", shape) +
             '<h2>Examples</h2><h3>curl</h3>' + _code("curl", curl) +
             '<h3>Python (standard library only)</h3>' + _code("py", py) +
             '<p>The <code>id</code> field is stable for the whole exercise, so you can use it to avoid processing a story twice.</p>'
             '</main>' + _footer())
    return _page(ctx, "Data Feeds for Teams | Coastal Bend Newsstand", inner, COPY_JS)


def render_notfound(ctx):
    inner = (_mast(ctx) + '<main class="wrap nf"><h2>Page not found</h2>'
             '<p>That page does not exist, or it has not been published yet.</p>'
             '<p><a class="btn" href="/">Back to the newsstand</a></p></main>' + _footer())
    return _page(ctx, "Not Found | Coastal Bend Newsstand", inner)
