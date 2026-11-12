"""Continental Wire Service: national news wire. Austere AP/Reuters-style layout.
All content comes from visible dispatches; no invented staff or statistics."""
import re

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Merriweather:ital,wght@0,400;0,700;0,900;1,400&display=swap"

CSS = """
:root{--hbg:#1a1a1a;--red:#d93025;--bg:#ffffff;--text:#111111;--muted:#666666;--border:#dddddd;--lightbg:#f7f7f7}
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--bg);color:var(--text);font-size:15px;line-height:1.6}
a{color:inherit}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.container{max-width:1100px;margin:0 auto}
.sans{font-family:system-ui,-apple-system,'Segoe UI',sans-serif}
.utility-bar{background:var(--hbg);color:#999;font:11px/1.4 system-ui,sans-serif;padding-block:7px}
.utility-bar .row{display:flex;flex-wrap:wrap;gap:4px 16px;justify-content:space-between}
.utility-bar b{color:#ddd;font-weight:600}
header.mast{border-bottom:3px solid var(--hbg)}
.header-inner{padding-block:18px 14px}
.wlabel{font:700 10px/1 system-ui,sans-serif;letter-spacing:.18em;text-transform:uppercase;color:var(--red);margin-bottom:6px}
.masthead{font-family:'Merriweather',Georgia,serif;font-size:34px;font-weight:900;color:var(--hbg);letter-spacing:-.01em;line-height:1;text-decoration:none;display:inline-block}
.masthead .ws{color:var(--red)}
.mrule{height:4px;background:var(--hbg);margin:12px 0 0;position:relative}
.mrule::after{content:'';position:absolute;top:0;left:0;width:120px;height:4px;background:var(--red)}
@media (max-width:480px){.masthead{font-size:26px}}
nav.wn{border-bottom:1px solid var(--border);font-family:system-ui,sans-serif}
nav.wn .nav-inner{display:flex;flex-wrap:wrap}
nav.wn a{color:var(--muted);text-decoration:none;padding:9px 13px;font-size:12px;font-weight:600;letter-spacing:.03em;border-bottom:3px solid transparent;display:inline-block;text-transform:uppercase}
nav.wn a:hover{color:var(--text);border-bottom-color:var(--border)}
nav.wn a.active{color:var(--hbg);border-bottom-color:var(--red)}
.wire-notice{background:#fffde7;border-bottom:1px solid #f0d77a;padding-block:9px;font:12px/1.45 system-ui,sans-serif;color:#5a4700;text-align:center}
.alerts{border-bottom:1px solid var(--border);background:var(--lightbg);padding-block:8px;font:12.5px/1.45 system-ui,sans-serif}
.alerts .a{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.alerts .a+.a{margin-top:3px}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:40px;padding-block:28px}
@media (max-width:860px){.layout{grid-template-columns:minmax(0,1fr);gap:24px}}
.dlbl{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;margin-bottom:12px;font-family:system-ui,sans-serif}
.b-red{background:var(--red);color:#fff;font:700 9px/1 system-ui,sans-serif;padding:4px 8px;letter-spacing:.1em;text-transform:uppercase}
.b-blk{background:var(--hbg);color:#fff;font:700 9px/1 system-ui,sans-serif;padding:4px 8px;letter-spacing:.1em;text-transform:uppercase;text-decoration:none}
.b-sec{border:1px solid var(--border);color:var(--muted);font:700 9px/1 system-ui,sans-serif;padding:3px 7px;letter-spacing:.1em;text-transform:uppercase;text-decoration:none}
.dtime{font-size:11px;color:var(--muted)}
.slug{font:10.5px/1.3 ui-monospace,Menlo,Consolas,monospace;color:#777;background:#f3f3f3;padding:2px 6px;border-radius:2px;letter-spacing:.02em;word-break:break-all}
.lead-h{font-family:'Merriweather',Georgia,serif;font-size:27px;font-weight:700;line-height:1.22;color:var(--hbg);margin:0 0 10px;text-wrap:balance}
.lead-h a{text-decoration:none}.lead-h a:hover{text-decoration:underline}
.deck{font-size:16px;line-height:1.5;color:#333;margin:0 0 14px;font-style:italic;border-left:3px solid var(--red);padding-left:14px}
.byw{font:12px/1.4 system-ui,sans-serif;color:var(--muted);margin-bottom:18px}
.byw strong{color:var(--text)}
.body p{font-size:15px;line-height:1.75;margin:0 0 14px}
.dl{font-weight:700;color:var(--hbg)}
.more{font:700 12px system-ui,sans-serif;color:var(--red);text-decoration:none;letter-spacing:.04em;text-transform:uppercase}
hr.rule{border:none;border-top:2px solid var(--hbg);margin:28px 0 20px}
h2.fh{font-family:'Merriweather',Georgia,serif;font-size:16px;font-weight:700;margin:0 0 6px;color:var(--hbg);border-left:4px solid var(--red);padding-left:10px}
.feed-item{padding:13px 0;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:5px;min-width:0}
.feed-item:last-child{border-bottom:none}
.feed-item .hl{font-family:'Merriweather',Georgia,serif;font-size:15px;font-weight:700;color:var(--hbg);line-height:1.32;text-decoration:none}
.feed-item .hl:hover{text-decoration:underline}
.feed-item .meta{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;font:11px/1.3 system-ui,sans-serif;color:var(--muted)}
.feed-item .sum{font-size:13.5px;color:#444;line-height:1.5}
.box{background:var(--lightbg);border:1px solid var(--border);border-top:3px solid var(--hbg);padding:16px;margin-bottom:18px}
.box h3{font:700 10px/1 system-ui,sans-serif;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);margin:0 0 10px}
.box p{font-size:13px;line-height:1.6;color:#333;margin:0 0 8px}
.box ul{list-style:none;margin:0;padding:0}
.box li{padding:6px 0;border-top:1px solid var(--border);font:12px/1.4 system-ui,sans-serif}
.box li:first-child{border-top:none}
.box li a{text-decoration:none;color:var(--text);font-weight:600}
.box li a:hover{color:var(--red)}
.box .cnt{float:right;color:var(--muted)}
.empty{border:1px solid var(--border);border-left:4px solid var(--red);padding:20px;background:var(--lightbg)}
.empty h2{font-family:'Merriweather',Georgia,serif;font-size:18px;margin:0 0 6px}
.empty p{margin:0;color:#333;font-size:14px}
.ph{margin-bottom:6px}
.ph h1{font-family:'Merriweather',Georgia,serif;font-size:24px;margin:0 0 4px}
.ph p{margin:0;font:12px system-ui,sans-serif;color:var(--muted)}
article.disp{min-width:0}
.endmark{font:700 11px system-ui,sans-serif;letter-spacing:.2em;color:var(--muted);text-align:center;margin:22px 0}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0 4px}
.tag{font:600 10.5px system-ui,sans-serif;border:1px solid var(--border);padding:3px 8px;color:#444;background:#fff}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:22px;font-family:system-ui,sans-serif}
.pager a{display:block;border:1px solid var(--border);padding:11px 13px;text-decoration:none;font-size:13px;font-weight:600;color:var(--text);min-width:0}
.pager small{display:block;font-size:10px;color:var(--red);text-transform:uppercase;letter-spacing:.1em;margin-bottom:3px}
.pager .nx{text-align:right}
@media (max-width:560px){.pager{grid-template-columns:1fr}.pager .nx{text-align:left}}
form.srch{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 10px;font-family:system-ui,sans-serif}
form.srch input{flex:1;min-width:0;padding:9px 11px;border:1px solid #bbb;font:14px system-ui,sans-serif;background:#fff;color:var(--text)}
form.srch button{padding:9px 16px;border:0;background:var(--hbg);color:#fff;font:700 11px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;cursor:pointer}
.filter{font:12px/1.5 system-ui,sans-serif;color:#444;margin-bottom:12px}
.filter a{color:var(--red)}
.days{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px;font-family:system-ui,sans-serif}
.days a{font-size:11px;font-weight:600;text-decoration:none;border:1px solid var(--border);padding:4px 8px;color:#333}
.days a.on{background:var(--hbg);border-color:var(--hbg);color:#fff}
.days small{color:var(--muted);font-weight:500}.days a.on small{color:#bbb}
.dayhead{font:700 11px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--hbg);border-bottom:2px solid var(--hbg);padding-bottom:5px;margin:22px 0 2px}
footer.ft{border-top:3px solid var(--hbg);margin-top:30px;padding-block:18px;font:11.5px/1.5 system-ui,sans-serif;color:var(--muted)}
footer.ft .row{display:flex;flex-wrap:wrap;gap:6px 18px;justify-content:space-between}
footer.ft a{color:var(--muted)}
"""


def split_dateline(p):
    m = re.match(r"^([A-Z][A-Z .,'\-]+(?:,\s*[A-Za-z.]+)?\s*\([^)]*\))\s*[—–-]+\s*(.*)$", p)
    return (m.group(1), m.group(2)) if m else (None, p)


def body_html(a, limit=None):
    out = []
    for i, p in enumerate(a["body"][:limit] if limit else a["body"]):
        if i == 0:
            dl, rest = split_dateline(p)
            if dl:
                out.append(f'<p><span class="dl">{esc(dl)}</span> — {esc(rest)}</p>')
                continue
        out.append(f"<p>{esc(p)}</p>")
    return "".join(out)


def slug(a):
    """Wire slug trimmed on a word boundary (C.wire_slug cuts mid-word at 48 chars)."""
    full = "-".join(re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").upper() for t in a.get("topics", [])[:3]).strip("-")
    if len(full) <= 40:
        return full or "CORPUS-CHRISTI"
    parts, out = full.split("-"), []
    for w in parts:
        if len("-".join(out + [w])) > 40:
            break
        out.append(w)
    return "-".join(out) or full[:40]


def hot(ctx, a):
    return a["story_type"] == "breaking" and ctx["now"] - a["ts"] <= 6 * 3600


def filed(a):
    return f"{C.fmt_date_ap(a['ts'])}, {C.fmt_time_ap(a['ts'])}"


def feed_item(ctx, a, summary=True):
    badge = '<span class="b-red">Breaking</span>' if hot(ctx, a) else ""
    return (f'<div class="feed-item" data-article-id="{a["pid"]}">'
            f'<div class="meta">{badge}<span class="slug">{esc(slug(a))}</span>'
            f'<a class="b-sec" href="{C.url_section(ctx, a["section_slug"])}">{esc(a["section"])}</a>'
            f'<span>{esc(filed(a))}</span></div>'
            f'<a class="hl" href="{a["url"]}">{esc(a["headline"])}</a>'
            + (f'<div class="sum">{esc(a["summary"])}</div>' if summary and a["summary"] else "") + "</div>")


def empty(title, text):
    return f'<div class="empty"><h2>{esc(title)}</h2><p>{esc(text)}</p></div>'


def side(ctx):
    arts = ctx["articles"]
    out = []
    if arts:
        li = "".join(f'<li data-article-id="{a["pid"]}" data-nr-nobadge><span class="slug">{esc(slug(a))}</span></li>' for a in arts[:5])
        out.append('<div class="box"><h3>Copy desk</h3>'
                   '<p>All dispatches are cleared for immediate publication with attribution to Continental Wire Service. '
                   'Corrections and write-throughs move as separate dispatches.</p>'
                   f'<p style="margin-bottom:4px"><strong style="font:700 11px system-ui,sans-serif">Latest slugs</strong></p><ul>{li}</ul></div>')
    secs = []
    for s in ctx["outlet"]["sections"]:
        n = sum(1 for a in arts if a["section"] == s["name"])
        secs.append(f'<li><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a><span class="cnt">{n}</span></li>')
    out.append(f'<div class="box"><h3>Wires</h3><ul>{"".join(secs)}'
               f'<li><a href="{C.url_archive(ctx)}">Search all dispatches</a></li>'
               f'<li><a href="{C.url_rss(ctx)}">RSS feed</a></li></ul></div>')
    out.append('<div class="box"><h3>About the wire</h3>'
               '<p>Continental Wire Service files national, security and world dispatches for subscribing newspapers, '
               'broadcasters and websites.</p><p>From the Texas Coastal Bend, the wire moves copy when a story carries '
               'national significance. Datelines are as filed.</p></div>')
    return '<aside>' + "".join(out) + "</aside>"


def frame(ctx, title, inner, active=None):
    o = ctx["outlet"]
    nav = [f'<a href="{C.url_home(ctx)}"{" class=active" if active == "_home" else ""}>All Wires</a>']
    for s in o["sections"]:
        nav.append(f'<a href="{C.url_section(ctx, s["slug"])}"{" class=active" if active == s["slug"] else ""}>{esc(s["name"])}</a>')
    nav.append(f'<a href="{C.url_archive(ctx)}"{" class=active" if active == "_archive" else ""}>Archive</a>')
    alerts = ""
    if ctx["status"]["alerts"]:
        alerts = ('<div class="alerts"><div class="container gut">' +
                  "".join(f'<div class="a"><span class="b-blk">Official alert</span><span>{esc(a["text"])}</span></div>'
                          for a in ctx["status"]["alerts"]) + "</div></div>")
    return (C.head(ctx, title, FONTS, CSS) +
            '<div id="nr-root">'
            '<div class="utility-bar"><div class="container gut row">'
            '<span><b>CONTINENTAL WIRE SERVICE</b> · Subscribing organizations may republish with attribution</span>'
            f'<span>{C.clock_span(ctx, "date-long")} · {C.clock_span(ctx, "time-ap")}</span></div></div>'
            '<header class="mast"><div class="container gut header-inner"><div class="wlabel">National News Wire</div>'
            f'<a class="masthead" href="{C.url_home(ctx)}">CONTINENTAL <span class="ws">WIRE</span></a><div class="mrule"></div></div></header>'
            f'<nav class="wn" aria-label="Wires"><div class="container gut nav-inner">{"".join(nav)}</div></nav>'
            '<div class="wire-notice gut">These dispatches are filed for subscribing news organizations. All are cleared '
            'for publication with attribution to Continental Wire Service. Datelines as filed.</div>'
            + alerts +
            f'<div class="container gut">{inner}</div>'
            '<footer class="ft"><div class="container gut row">'
            f'<span>© Continental Wire Service · {esc(o["kind"])} · <a href="{C.url_rss(ctx)}">RSS</a></span>'
            '<span>A fictional wire service for training purposes. All people and events are fictional.</span></div></footer>'
            '</div>' + C.foot(ctx))


# ------------------------------------------------------------------ views
def home(ctx):
    arts = ctx["articles"]
    if not arts:
        main = empty("No dispatches have moved from the Coastal Bend",
                     "Continental files from the Texas Gulf Coast on nationally significant days. "
                     "Dispatches will appear on this wire as they are filed.")
        return frame(ctx, "Continental Wire Service", f'<div class="layout"><div>{main}</div>{side(ctx)}</div>', "_home")
    lead = arts[0]
    badge = '<span class="b-red">Breaking</span>' if hot(ctx, lead) else '<span class="b-blk">Top dispatch</span>'
    lead_html = (f'<article class="disp" data-article-id="{lead["pid"]}">'
                 f'<div class="dlbl">{badge}<span class="slug">{esc(slug(lead))}</span>'
                 f'<span class="dtime">Filed {esc(filed(lead))} · {C.ago_span(ctx, lead)}</span></div>'
                 f'<h1 class="lead-h"><a href="{lead["url"]}">{esc(lead["headline"])}</a></h1>'
                 f'<p class="deck">{esc(lead["summary"])}</p>'
                 f'<div class="byw">By <strong>{esc(C.byline(lead))}</strong>, Continental Wire Service</div>'
                 f'<div class="body">{body_html(lead, 3)}</div>'
                 f'<a class="more" href="{lead["url"]}">Full dispatch →</a></article>')
    rest = arts[1:25]
    feed = ""
    if rest:
        feed = ('<hr class="rule"><section class="wire-feed"><h2 class="fh">Wire feed</h2>'
                + "".join(feed_item(ctx, a) for a in rest) + "</section>")
    return frame(ctx, "Continental Wire Service | National News Wire",
                 f'<div class="layout"><div>{lead_html}{feed}</div>{side(ctx)}</div>', "_home")


def section(ctx, sec, items):
    head = f'<div class="ph"><h1>{esc(sec["name"])} wire</h1><p>{len(items)} dispatch{"es" if len(items) != 1 else ""}</p></div>'
    main = "".join(feed_item(ctx, a) for a in items) if items else empty(
        f"No {sec['name']} dispatches", "Nothing has moved on this wire so far.")
    return frame(ctx, f'{sec["name"]} | Continental Wire Service',
                 f'<div class="layout"><div>{head}{main}</div>{side(ctx)}</div>', sec["slug"])


def article(ctx, a, related, newer, older):
    badge = '<span class="b-red">Breaking</span>' if hot(ctx, a) else ""
    tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a["storylines"])
    disp = (f'<article class="disp" data-article-id="{a["pid"]}">'
            f'<div class="dlbl">{badge}<span class="slug">{esc(slug(a))}</span>'
            f'<a class="b-sec" href="{C.url_section(ctx, a["section_slug"])}">{esc(a["section"])}</a></div>'
            f'<h1 class="lead-h">{esc(a["headline"])}</h1>'
            f'<p class="deck">{esc(a["summary"])}</p>'
            f'<div class="byw">By <strong>{esc(C.byline(a))}</strong>, Continental Wire Service<br>'
            f'Filed {esc(C.pub_label(a))}</div>'
            f'<div class="body">{body_html(a)}</div><div class="endmark">— END —</div>'
            + (f'<div class="tags">{tags}</div>' if tags else "") + "</article>")
    pager = ""
    if newer or older:
        pager = '<div class="pager">'
        pager += (f'<a href="{older["url"]}" data-article-id="{older["pid"]}" data-nr-nobadge><small>← Previous dispatch</small>{esc(older["headline"])}</a>'
                  if older else "<span></span>")
        pager += (f'<a class="nx" href="{newer["url"]}" data-article-id="{newer["pid"]}" data-nr-nobadge><small>Next dispatch →</small>{esc(newer["headline"])}</a>'
                  if newer else "<span></span>")
        pager += "</div>"
    rel = ""
    if related:
        rel = ('<hr class="rule"><section><h2 class="fh">Related coverage</h2>' +
               "".join(f'<div class="feed-item" data-article-id="{r["pid"]}"><div class="meta"><span class="b-sec">{esc(r["outlet_name"])}</span>'
                       f'<span>{esc(filed(r))}</span></div><a class="hl" href="{r["url"]}">{esc(r["headline"])}</a></div>'
                       for r in related) + "</section>")
    return frame(ctx, f'{a["headline"]} | Continental Wire Service',
                 f'<div class="layout"><div>{disp}{pager}{rel}</div>{side(ctx)}</div>', a["section_slug"])


def archive(ctx, q, date, results, days):
    form = (f'<form class="srch" action="{C.url_archive(ctx)}" method="get" role="search">'
            f'<input type="search" name="q" value="{esc(q)}" placeholder="Search dispatches" aria-label="Search dispatches">'
            + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "") +
            '<button type="submit">Search</button></form>')
    bits = []
    if q:
        bits.append(f'matching “{esc(q)}”')
    if date:
        bits.append("filed " + (esc(C.fmt_date_long(results[0]["ts"])) if results else esc(date)))
    n = len(results)
    filt = (f'<div class="filter">{n} dispatch{"es" if n != 1 else ""} {" ".join(bits)} · <a href="{C.url_archive(ctx)}">Clear</a></div>'
            if bits else f'<div class="filter">{n} dispatch{"es" if n != 1 else ""} on the wire</div>')
    chips = []
    for d, cnt in days:
        _, m, dd = d.split("-")
        chips.append(f'<a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""}>'
                     f'{C.AP_MONTHS[int(m) - 1]} {int(dd)} <small>{cnt}</small></a>')
    dayidx = f'<div class="days" aria-label="Days with dispatches">{"".join(chips)}</div>' if chips else ""
    groups = "".join(f'<div class="dayhead">{esc(C.fmt_date_long(items[0]["ts"]))}</div>' +
                     "".join(feed_item(ctx, a) for a in items) for _, items in C.group_by_day(results))
    if not groups:
        groups = empty("No dispatches found", "Try a different search or clear the filters.")
    head = '<div class="ph"><h1>Dispatch archive</h1><p>Every dispatch moved on the wire, newest first</p></div>'
    return frame(ctx, "Archive | Continental Wire Service",
                 f'<div class="layout"><div>{head}{form}{filt}{dayidx}{groups}</div>{side(ctx)}</div>', "_archive")


def notfound(ctx):
    main = empty("Dispatch not available", "This page is not on the Continental wire. Check the address or return to the wire feed.")
    return frame(ctx, "Not found | Continental Wire Service",
                 f'<div class="layout"><div>{main}<p style="margin-top:16px"><a class="more" href="{C.url_home(ctx)}">← All wires</a></p></div>{side(ctx)}</div>')


def render(view, ctx, **kw):
    if view == "home":
        return home(ctx)
    if view == "section":
        return section(ctx, kw["section"], kw["items"])
    if view == "article":
        return article(ctx, kw["article"], kw.get("related", []), kw.get("newer"), kw.get("older"))
    if view == "archive":
        return archive(ctx, kw.get("q", ""), kw.get("date"), kw.get("results", []), kw.get("days", []))
    return notfound(ctx)
