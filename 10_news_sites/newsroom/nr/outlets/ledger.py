"""The Bayside Ledger: broadsheet daily newspaper template (see nr/common.py for the contract)."""
import datetime as dt

from nr import common as C
from nr.common import esc

FONTS = ("https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700"
         "&family=Source+Sans+3:wght@300;400;600;700&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap")

CSS = """
body,h1,h2,h3,h4,p,ul,ol,figure{margin:0;padding:0}
:root{--navy:#0a1628;--accent:#1a4b8c;--breaking:#8b1a1a;--text:#1a1a1a;--muted:#5a5a5a;--tan:#d4c4a0;--bg:#f9f7f2;--white:#fff;--border:#e8e0d0}
body{background:var(--bg);color:var(--text);font-family:'Source Serif 4',Georgia,serif;font-size:16px;line-height:1.6;overflow-x:hidden}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.sans{font-family:'Source Sans 3',system-ui,sans-serif}
.utility-bar{background:var(--navy);color:#c8c8c8;font-family:'Source Sans 3',sans-serif;font-size:12px;padding-block:6px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}
.utility-bar a{color:#aac4e8}
.utility-bar .links{display:flex;gap:14px;flex-wrap:wrap}
.masthead{background:#fff;border-bottom:3px solid var(--navy);padding-block:22px 18px;text-align:center}
.masthead-name{font-family:'Playfair Display',serif;font-size:clamp(34px,7vw,72px);font-weight:900;color:var(--navy);letter-spacing:-.02em;line-height:1;display:inline-block}
.masthead-name:hover{text-decoration:none}
.masthead-tagline{font-family:'Source Sans 3',sans-serif;font-size:11px;color:var(--muted);letter-spacing:.15em;text-transform:uppercase;border-top:1px solid var(--tan);border-bottom:1px solid var(--tan);padding:5px 0;margin:12px auto 0;max-width:760px;display:flex;justify-content:center;gap:18px;flex-wrap:wrap}
nav.sections{background:#fff;border-bottom:1px solid var(--tan);position:sticky;top:0;z-index:50;box-shadow:0 1px 4px rgba(0,0,0,.08)}
nav.sections ul{list-style:none;display:flex;justify-content:center;flex-wrap:wrap}
nav.sections a{display:block;padding:11px 12px;font-family:'Source Sans 3',sans-serif;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--navy);border-bottom:3px solid transparent}
nav.sections a:hover,nav.sections a.on{border-bottom-color:var(--accent);color:var(--accent);text-decoration:none}
.breaking-ribbon{background:var(--breaking);color:#fff;padding-block:9px;font-family:'Source Sans 3',sans-serif;font-size:14px;display:flex;align-items:center;gap:12px}
.breaking-ribbon a{color:#fff;font-weight:600}
.breaking-label{background:#fff;color:var(--breaking);font-weight:700;font-size:10px;letter-spacing:.1em;text-transform:uppercase;padding:2px 7px;border-radius:1px;white-space:nowrap}
.container{max-width:1200px;margin:0 auto}
.hero{padding-block:28px 24px;border-bottom:2px solid var(--navy);display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:32px;align-items:start}
@media(max-width:820px){.hero{grid-template-columns:minmax(0,1fr)}}
.kicker{font-family:'Source Sans 3',sans-serif;font-size:11px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:8px}
.kicker.brk{color:var(--breaking)}
.hero h1{font-family:'Playfair Display',serif;font-size:clamp(26px,3.4vw,44px);font-weight:900;line-height:1.12;color:var(--navy);margin-bottom:12px;text-wrap:balance}
.hero h1 a{color:inherit}
.dek{font-family:'Source Sans 3',sans-serif;font-size:17px;color:var(--muted);line-height:1.5;margin-bottom:14px}
.byline{font-family:'Source Sans 3',sans-serif;font-size:12px;color:var(--muted);border-top:1px solid var(--tan);padding-top:10px;margin-bottom:16px}
.byline strong{color:var(--text)}
.body p{margin-bottom:14px;font-size:17px;line-height:1.72}
.read-more{display:inline-block;font-family:'Source Sans 3',sans-serif;font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);border-bottom:2px solid var(--accent);padding-bottom:1px}
.top-list{border-left:1px solid var(--tan);padding-left:22px}
@media(max-width:820px){.top-list{border-left:0;padding-left:0;border-top:1px solid var(--tan);padding-top:16px}}
.top-list h2{font-family:'Source Sans 3',sans-serif;font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--navy);margin-bottom:10px}
.top-list li{list-style:none;padding:10px 0;border-bottom:1px solid var(--border)}
.top-list li:last-child{border-bottom:0}
.top-list h3{font-family:'Playfair Display',serif;font-size:17px;line-height:1.25;font-weight:700}
.top-list h3 a{color:var(--navy)}
.meta{font-family:'Source Sans 3',sans-serif;font-size:11px;color:var(--muted);margin-top:4px}
.section-head{display:flex;align-items:center;gap:12px;margin:30px 0 18px}
.section-head h2{font-family:'Source Sans 3',sans-serif;font-size:11px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:var(--navy);white-space:nowrap}
.section-head h2 a{color:inherit}
.section-head::after{content:'';flex:1;height:1px;background:var(--tan)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:32px;padding-bottom:36px}
@media(max-width:1000px){.layout{grid-template-columns:minmax(0,1fr)}}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
@media(max-width:1000px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.cards{grid-template-columns:minmax(0,1fr)}}
.card{border-top:2px solid var(--navy);padding-top:14px;min-width:0}
.card.brk,.card.inv{border-top-color:var(--breaking)}
.card.op{border-top-color:var(--tan)}
.card-section{font-family:'Source Sans 3',sans-serif;font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:6px}
.card-section.inv,.card-section.brk{color:var(--breaking)}.card-section.op{color:var(--muted)}
.card h3{font-family:'Playfair Display',serif;font-size:18px;font-weight:700;line-height:1.25;color:var(--navy);margin-bottom:8px}
.card h3 a{color:inherit}.card h3 a:hover{color:var(--accent);text-decoration:none}
.card-dek{font-family:'Source Sans 3',sans-serif;font-size:13.5px;color:var(--muted);line-height:1.5;margin-bottom:10px}
.card-byline{font-family:'Source Sans 3',sans-serif;font-size:11px;color:var(--muted);border-top:1px solid var(--tan);padding-top:8px}
.op-rail{background:#fff;border:1px solid var(--border);padding:18px 20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px}
.op-rail article{min-width:0}
.op-rail h3{font-family:'Playfair Display',serif;font-style:italic;font-size:18px;line-height:1.3}
.op-rail h3 a{color:var(--navy)}
.sidebar{min-width:0}
.box{border:1px solid var(--border);background:#fff;margin-bottom:20px}
.box-head{background:var(--navy);color:#fff;font-family:'Source Sans 3',sans-serif;font-size:10px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;padding:8px 12px}
.box-head.red{background:var(--breaking)}
.box-body{padding:12px;font-family:'Source Sans 3',sans-serif;font-size:13px}
.alert-item{padding:8px 0;border-bottom:1px solid var(--tan)}
.alert-item:last-child{border-bottom:0}
.lvl{display:inline-block;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;padding:2px 6px;border-radius:2px;margin-bottom:4px;background:#e9e3d4;color:var(--navy)}
.lvl.emergency{background:var(--breaking);color:#fff}.lvl.warning{background:#c45a14;color:#fff}.lvl.watch{background:#d9a521;color:#1a1a1a}
.calm{color:var(--muted);font-style:italic}
.port{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-top:1px solid var(--tan);margin-top:6px}
.port strong{color:var(--navy)}
.latest li{list-style:none;padding:8px 0;border-bottom:1px solid var(--border)}
.latest li:last-child{border-bottom:0}
.latest a{color:var(--navy);font-weight:600;line-height:1.3}
.ad-box{background:#eeece6;border:1px dashed #c8c0a8;text-align:center;padding:32px 12px;font-family:'Source Sans 3',sans-serif;font-size:10px;color:#a0a0a0;letter-spacing:.1em;text-transform:uppercase;margin-bottom:20px}
.empty{padding:48px 0;text-align:center}
.empty h2{font-family:'Playfair Display',serif;font-size:28px;color:var(--navy);margin-bottom:8px}
.empty p{font-family:'Source Sans 3',sans-serif;color:var(--muted)}
/* section / list pages */
.page-title{font-family:'Playfair Display',serif;font-size:clamp(30px,5vw,48px);font-weight:900;color:var(--navy);padding-block:26px 6px;border-bottom:2px solid var(--navy);margin-bottom:8px}
.page-sub{font-family:'Source Sans 3',sans-serif;font-size:13px;color:var(--muted);margin-bottom:14px}
.row{display:grid;grid-template-columns:150px minmax(0,1fr);gap:20px;padding:18px 0;border-bottom:1px solid var(--tan)}
@media(max-width:560px){.row{grid-template-columns:minmax(0,1fr);gap:6px}}
.row .when{font-family:'Source Sans 3',sans-serif;font-size:12px;color:var(--muted)}
.row h3{font-family:'Playfair Display',serif;font-size:21px;line-height:1.25;margin-bottom:6px}
.row h3 a{color:var(--navy)}
.row.lead h3{font-size:30px}
/* article */
.story-wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:44px;padding-block:28px 40px}
@media(max-width:1000px){.story-wrap{grid-template-columns:minmax(0,1fr)}}
article.story{max-width:680px}
article.story h1{font-family:'Playfair Display',serif;font-size:clamp(30px,4.4vw,46px);font-weight:900;line-height:1.1;color:var(--navy);margin-bottom:14px;text-wrap:balance}
article.story .dek{font-size:19px;font-family:'Source Serif 4',Georgia,serif;font-style:italic}
article.story .body p:first-child::first-letter{font-family:'Playfair Display',serif;float:left;font-size:58px;line-height:.9;padding:6px 8px 0 0;color:var(--navy);font-weight:900}
.op-note{font-family:'Source Sans 3',sans-serif;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);border:1px solid var(--tan);display:inline-block;padding:3px 8px;margin-bottom:12px}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0 10px;font-family:'Source Sans 3',sans-serif;font-size:12px}
.tags span{border:1px solid var(--tan);padding:3px 9px;border-radius:12px;color:var(--navy);background:#fff}
.prevnext{display:grid;grid-template-columns:1fr 1fr;gap:18px;border-top:2px solid var(--navy);margin-top:26px;padding-top:14px;font-family:'Source Sans 3',sans-serif;font-size:13px}
.prevnext div{min-width:0}.prevnext .r{text-align:right}
.prevnext small{display:block;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}
.prevnext a{color:var(--navy);font-weight:600}
.related li{list-style:none;padding:9px 0;border-bottom:1px solid var(--border)}
.related li:last-child{border-bottom:0}
.related a{color:var(--navy);font-weight:600}
.src{display:block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--breaking);font-weight:700;margin-bottom:2px}
/* archive */
.search{display:flex;gap:8px;margin:6px 0 18px;flex-wrap:wrap}
.search input{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--tan);font:15px 'Source Sans 3',sans-serif;background:#fff}
.search button{padding:10px 18px;border:0;background:var(--navy);color:#fff;font:700 12px 'Source Sans 3',sans-serif;letter-spacing:.08em;text-transform:uppercase;cursor:pointer}
.filter{font-family:'Source Sans 3',sans-serif;font-size:13px;background:#fff;border:1px solid var(--border);padding:8px 12px;margin-bottom:14px}
.day-h{font-family:'Source Sans 3',sans-serif;font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);border-bottom:2px solid var(--navy);padding-bottom:4px;margin:24px 0 4px}
.arch li{list-style:none;padding:9px 0;border-bottom:1px solid var(--border)}
.arch a{color:var(--navy);font-family:'Playfair Display',serif;font-size:17px;font-weight:700}
.days h4{font-family:'Source Sans 3',sans-serif;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:12px 0 4px}
.days ul{display:flex;flex-wrap:wrap;gap:4px}
.days li{list-style:none}
.days a{display:inline-block;font-family:'Source Sans 3',sans-serif;font-size:12px;padding:3px 6px;border:1px solid var(--border);background:#fff;color:var(--navy)}
.days a.on{background:var(--navy);color:#fff}
footer.site{background:var(--navy);color:#9ab0cc;font-family:'Source Sans 3',sans-serif;font-size:12px;padding-block:32px;margin-top:36px}
.footer-inner{max-width:1200px;margin:0 auto;display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:24px}
@media(max-width:640px){.footer-inner{grid-template-columns:minmax(0,1fr)}}
.footer-logo{font-family:'Playfair Display',serif;font-size:22px;color:#fff;font-weight:900;margin-bottom:8px}
footer.site h4{font-size:10px;font-weight:700;letter-spacing:.15em;text-transform:uppercase;color:#aac4e8;margin-bottom:10px}
footer.site ul{list-style:none}footer.site li{margin-bottom:5px}footer.site a{color:#9ab0cc}
.footer-bottom{max-width:1200px;margin:20px auto 0;padding-top:14px;border-top:1px solid rgba(255,255,255,.1);font-size:11px;color:#6a8aaa}
"""

LEVEL = {"emergency": "Emergency", "warning": "Warning", "watch": "Watch", "advisory": "Advisory"}


# ------------------------------------------------------------------ helpers
def _cls(a):
    if a["section"] == "Opinion":
        return "op"
    if a["section"] == "Investigations":
        return "inv"
    if C.is_breaking(a):
        return "brk"
    return ""


def _kicker(a):
    if a["section"] == "Opinion":
        return "Opinion"
    if C.is_breaking(a):
        return "Breaking · " + a["section"]
    return a["section"]


def _byline(ctx, a):
    by = C.byline(a)
    return f'{"By <strong>" + esc(by) + "</strong> · " if by else ""}{C.ago_span(ctx, a)}'


def _breaking(ctx, hours):
    return [a for a in ctx["articles"] if C.is_breaking(a) and ctx["now"] - a["ts"] <= hours * 3600]


def _card(ctx, a, dek=True):
    k = _cls(a)
    return (f'<article class="card {k}" data-article-id="{a["pid"]}">'
            f'<div class="card-section {k}">{esc(_kicker(a))}</div>'
            f'<h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            + (f'<p class="card-dek">{esc(C.excerpt(a, 28))}</p>' if dek else "")
            + f'<div class="card-byline">{_byline(ctx, a)}</div></article>')


def _day_label(day_str, long=False):
    d = dt.date.fromisoformat(day_str)
    if long:
        return f"{C.DAYS[d.weekday()]}, {C.MONTHS[d.month - 1]} {d.day}, {d.year}"
    return f"{C.AP_MONTHS[d.month - 1]} {d.day}"


def _sidebar(ctx, extra=""):
    st = ctx["status"]
    alerts = st.get("alerts") or []
    port = st.get("port")
    rows = "".join(
        f'<div class="alert-item"><span class="lvl {esc(a["level"])}">{esc(LEVEL.get(a["level"], a["level"]))}</span>'
        f'<div>{esc(a["text"])}</div></div>' for a in alerts)
    if not rows:
        rows = '<p class="calm">No active alerts for the Coastal Bend.</p>'
    port_html = ""
    if port and port.get("code") != "OPEN":
        port_html = (f'<div class="port"><span>Port of Corpus Christi</span><strong>{esc(port["label"])}</strong></div>'
                     f'<div class="meta">{esc(port["detail"])}</div>')
    head_cls = "red" if any(a["level"] in ("emergency", "warning") for a in alerts) else ""
    latest = "".join(f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                     f'<div class="meta">{esc(a["section"])} · {C.ago_span(ctx, a)}</div></li>'
                     for a in ctx["articles"][:8])
    latest_box = (f'<div class="box"><div class="box-head">Latest</div><div class="box-body"><ul class="latest">{latest}</ul></div></div>'
                  if latest else "")
    return (f'<aside class="sidebar">{extra}<div class="box"><div class="box-head {head_cls}">Storm &amp; Alerts</div>'
            f'<div class="box-body">{rows}{port_html}</div></div>{latest_box}'
            f'<div class="ad-box">Advertisement</div></aside>')


def _frame(ctx, title, inner, active=None):
    o = ctx["outlet"]
    nav = [f'<li><a href="{C.url_home(ctx)}"{" class=on" if active == "_home" else ""}>Home</a></li>']
    for s in o["sections"]:
        on = ' class="on"' if active == s["slug"] else ""
        nav.append(f'<li><a href="{C.url_section(ctx, s["slug"])}"{on}>{esc(s["name"])}</a></li>')
    nav.append(f'<li><a href="{C.url_archive(ctx)}"{" class=on" if active == "_archive" else ""}>Archive</a></li>')
    brk = _breaking(ctx, 12)
    ribbon = ""
    if brk:
        b = brk[0]
        ribbon = (f'<div class="breaking-ribbon gut" data-article-id="{b["pid"]}" data-nr-nobadge>'
                  f'<span class="breaking-label">Breaking</span><a href="{b["url"]}">{esc(b["headline"])}</a></div>')
    secs = "".join(f'<li><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a></li>' for s in o["sections"])
    return (C.head(ctx, title, FONTS, CSS)
            + '<div id="nr-root">'
            + f'<div class="utility-bar gut"><span>{C.clock_span(ctx, "date-long")} · Corpus Christi, Texas</span>'
              f'<span class="links"><a href="{C.url_archive(ctx)}">Search &amp; Archive</a><a href="{C.url_rss(ctx)}">RSS</a><a href="/">All outlets</a></span></div>'
            + f'<header class="masthead gut"><a class="masthead-name" href="{C.url_home(ctx)}">The Bayside Ledger</a>'
              f'<div class="masthead-tagline"><span>The Coastal Bend\'s Daily Newspaper</span><span>{C.clock_span(ctx, "date-ap")}</span></div></header>'
            + f'<nav class="sections" aria-label="Sections"><ul>{"".join(nav)}</ul></nav>'
            + ribbon
            + f'<main class="container gut">{inner}</main>'
            + f'<footer class="site gut"><div class="footer-inner"><div><div class="footer-logo">The Bayside Ledger</div>'
              f'<p>Local news for Corpus Christi and the Coastal Bend.</p></div>'
              f'<div><h4>Sections</h4><ul>{secs}</ul></div>'
              f'<div><h4>Reader tools</h4><ul><li><a href="{C.url_archive(ctx)}">Search the archive</a></li>'
              f'<li><a href="{C.url_rss(ctx)}">RSS feed</a></li><li><a href="/">Coastal Bend newsstand</a></li></ul></div></div>'
              f'<div class="footer-bottom">© The Bayside Ledger · bayside-ledger.example · All people, organizations and events depicted are fictional.</div></footer>'
            + "</div>" + C.foot(ctx))


# ------------------------------------------------------------------ views
def _home(ctx):
    arts = ctx["articles"]
    if not arts:
        inner = ('<div class="empty"><h2>Today\'s edition is on its way</h2>'
                 '<p>Our newsroom is filing. Check back shortly for the latest from the Coastal Bend.</p></div>')
        return _frame(ctx, "The Bayside Ledger | Corpus Christi and the Coastal Bend", inner, "_home")
    brk = _breaking(ctx, 24)
    lead = brk[0] if brk else next((a for a in arts if a["section"] != "Opinion"), arts[0])
    used = {lead["pid"]}
    top = [a for a in arts if a["pid"] not in used and a["section"] != "Opinion"][:4]
    used |= {a["pid"] for a in top}
    paras = "".join(f"<p>{esc(p)}</p>" for p in lead["body"][:2])
    top_html = "".join(f'<li data-article-id="{a["pid"]}"><div class="kicker {"brk" if C.is_breaking(a) else ""}">{esc(_kicker(a))}</div>'
                       f'<h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3><div class="meta">{C.ago_span(ctx, a)}</div></li>'
                       for a in top)
    hero = (f'<section class="hero"><div data-article-id="{lead["pid"]}">'
            f'<div class="kicker {"brk" if C.is_breaking(lead) else ""}">{esc(_kicker(lead))}</div>'
            f'<h1><a href="{lead["url"]}">{esc(lead["headline"])}</a></h1><p class="dek">{esc(lead["summary"])}</p>'
            f'<div class="byline">{_byline(ctx, lead)}</div><div class="body">{paras}</div>'
            f'<a class="read-more" href="{lead["url"]}">Continue reading</a></div>'
            + (f'<div class="top-list"><h2>Top stories</h2><ul>{top_html}</ul></div>' if top_html else "")
            + "</section>")

    latest = [a for a in arts if a["pid"] not in used and a["section"] != "Opinion"][:6]
    used |= {a["pid"] for a in latest}
    main = []
    if latest:
        main.append('<div class="section-head"><h2>Latest news</h2></div><div class="cards">'
                    + "".join(_card(ctx, a) for a in latest) + "</div>")
    for s in ctx["outlet"]["sections"]:
        if s["name"] == "Opinion":
            continue
        items = [a for a in C.by_section(ctx, s["name"]) if a["pid"] not in used][:3]
        if not items:
            continue
        main.append(f'<div class="section-head"><h2><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a></h2></div>'
                    f'<div class="cards">{"".join(_card(ctx, a) for a in items)}</div>')
    ops = C.by_section(ctx, "Opinion")[:4]
    if ops:
        main.append('<div class="section-head"><h2><a href="' + C.url_section(ctx, "opinion") + '">Opinion</a></h2></div><div class="op-rail">'
                    + "".join(f'<article data-article-id="{a["pid"]}"><h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
                              f'<div class="meta">{esc(C.byline(a))} · {C.ago_span(ctx, a)}</div></article>' for a in ops)
                    + "</div>")
    inner = hero + f'<div class="layout"><div style="min-width:0">{"".join(main)}</div>{_sidebar(ctx)}</div>'
    return _frame(ctx, "The Bayside Ledger | Corpus Christi and the Coastal Bend", inner, "_home")


def _row(ctx, a, lead=False):
    return (f'<div class="row{" lead" if lead else ""}" data-article-id="{a["pid"]}">'
            f'<div class="when">{esc(C.fmt_date_ap(a["ts"]))}<br>{esc(C.fmt_time_ap(a["ts"]))}</div>'
            f'<div><div class="kicker {"brk" if C.is_breaking(a) else ""}">{esc(_kicker(a))}</div>'
            f'<h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3><p class="card-dek">{esc(a["summary"])}</p>'
            f'<div class="meta">{esc(C.byline(a))}</div></div></div>')


def _section(ctx, sec, items):
    if items:
        body = "".join(_row(ctx, a, i == 0) for i, a in enumerate(items))
    else:
        body = f'<div class="empty"><h2>No {esc(sec["name"])} stories yet</h2><p>New stories will appear here as they are published.</p></div>'
    n = len(items)
    inner = (f'<h1 class="page-title">{esc(sec["name"])}</h1><p class="page-sub">{n} stor{"y" if n == 1 else "ies"} · '
             f'Updated {C.clock_span(ctx, "date-ap")}</p>'
             f'<div class="layout"><div style="min-width:0">{body}</div>{_sidebar(ctx)}</div>')
    return _frame(ctx, f'{sec["name"]} | The Bayside Ledger', inner, sec["slug"])


def _article(ctx, a, related, newer, older):
    is_op = a["section"] == "Opinion"
    sec_link = f'<a href="{C.url_section(ctx, a["section_slug"])}">{esc(_kicker(a))}</a>'
    tags = "".join(f"<span>{esc(s)}</span>" for s in a["storylines"])
    pn = ('<div class="prevnext">'
          + (f'<div data-article-id="{older["pid"]}" data-nr-nobadge><small>Previous story</small><a href="{older["url"]}">{esc(older["headline"])}</a></div>' if older else "<div></div>")
          + (f'<div class="r" data-article-id="{newer["pid"]}" data-nr-nobadge><small>Next story</small><a href="{newer["url"]}">{esc(newer["headline"])}</a></div>' if newer else "<div></div>")
          + "</div>")
    same = [r for r in related if r["outlet"] == a["outlet"]]
    other = [r for r in related if r["outlet"] != a["outlet"]]
    more = same + [x for x in ctx["articles"] if x["pid"] != a["pid"] and x["pid"] not in {r["pid"] for r in same}]
    more_html = "".join(f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(r["headline"])}</a>'
                        f'<div class="meta">{esc(r["section"])} · {C.ago_span(ctx, r)}</div></li>' for r in more[:5])
    around = "".join(f'<li data-article-id="{r["pid"]}"><span class="src">{esc(r["outlet_name"])}</span>'
                     f'<a href="{r["url"]}">{esc(r["headline"])}</a></li>' for r in other)
    extra = ""
    if more_html:
        extra += f'<div class="box"><div class="box-head">More from the Ledger</div><div class="box-body"><ul class="related">{more_html}</ul></div></div>'
    if around:
        extra += f'<div class="box"><div class="box-head">Around the Coastal Bend</div><div class="box-body"><ul class="related">{around}</ul></div></div>'
    story = (f'<article class="story" data-article-id="{a["pid"]}">'
             f'<div class="kicker {"brk" if C.is_breaking(a) else ""}">{sec_link}</div>'
             + ('<div class="op-note">Opinion · This column reflects the writer\'s views</div>' if is_op else "")
             + f'<h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
             f'<div class="byline">{"By <strong>" + esc(C.byline(a)) + "</strong><br>" if a["authors"] else ""}'
             f'Published {esc(C.pub_label(a))} · {C.read_minutes(a)} min read</div>'
             f'<div class="body">{C.paras(a["body"])}</div>'
             + (f'<div class="tags">{tags}</div>' if tags else "")
             + pn + "</article>")
    inner = f'<div class="story-wrap">{story}{_sidebar(ctx, extra)}</div>'
    return _frame(ctx, f'{a["headline"]} | The Bayside Ledger', inner, a["section_slug"])


def _archive(ctx, q, date, results, days):
    form = (f'<form class="search" action="{C.url_archive(ctx)}" method="get" role="search">'
            f'<input type="search" name="q" value="{esc(q)}" placeholder="Search the Ledger archive" aria-label="Search">'
            + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "")
            + '<button type="submit">Search</button></form>')
    bits = []
    if q:
        bits.append(f'matching “<strong>{esc(q)}</strong>”')
    if date:
        bits.append(f'from <strong>{esc(_day_label(date, True))}</strong>')
    filt = ""
    if bits:
        filt = (f'<div class="filter">{len(results)} result{"s" if len(results) != 1 else ""} {" ".join(bits)} · '
                f'<a href="{C.url_archive(ctx)}">Clear filters</a></div>')
    groups = C.group_by_day(results)
    if groups:
        lst = "".join(f'<h2 class="day-h">{esc(_day_label(d, True))}</h2><ul class="arch">'
                      + "".join(f'<li data-article-id="{a["pid"]}"><div class="kicker {"brk" if C.is_breaking(a) else ""}">{esc(_kicker(a))}</div>'
                                f'<a href="{a["url"]}">{esc(a["headline"])}</a>'
                                f'<div class="meta">{esc(C.byline(a))} · {esc(C.fmt_time_ap(a["ts"]))}</div></li>' for a in items)
                      + "</ul>" for d, items in groups)
    elif ctx["articles"]:
        lst = '<div class="empty"><h2>No matching stories</h2><p>Try a different word or clear the filters.</p></div>'
    else:
        lst = '<div class="empty"><h2>The archive is empty</h2><p>Stories will appear here once they are published.</p></div>'
    # day index grouped by month
    months, idx = [], {}
    for d, n in days:
        key = d[:7]
        if key not in idx:
            idx[key] = []
            months.append(key)
        idx[key].append((d, n))
    dayhtml = ""
    for m in months:
        y, mo = m.split("-")
        dayhtml += (f'<h4>{C.MONTHS[int(mo) - 1]} {y}</h4><ul>'
                    + "".join(f'<li><a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""} title="{n} stories">{dt.date.fromisoformat(d).day}</a></li>'
                              for d, n in idx[m]) + "</ul>")
    extra = (f'<div class="box"><div class="box-head">Browse by date</div><div class="box-body days">{dayhtml}</div></div>'
             if dayhtml else "")
    inner = (f'<h1 class="page-title">Archive</h1><p class="page-sub">Every story the Ledger has published, newest first.</p>'
             f'<div class="layout"><div style="min-width:0">{form}{filt}{lst}</div>'
             f'<aside class="sidebar">{extra}</aside></div>')
    return _frame(ctx, "Archive | The Bayside Ledger", inner, "_archive")


def _notfound(ctx):
    inner = ('<div class="empty"><h2>We couldn\'t find that page</h2>'
             f'<p>The story you were looking for may have been moved or removed. '
             f'<a href="{C.url_home(ctx)}">Return to the front page</a> or <a href="{C.url_archive(ctx)}">search the archive</a>.</p></div>')
    return _frame(ctx, "Page not found | The Bayside Ledger", inner)


def render(view, ctx, **kw):
    if view == "home":
        return _home(ctx)
    if view == "section":
        return _section(ctx, kw["section"], kw["items"])
    if view == "article":
        return _article(ctx, kw["article"], kw.get("related") or [], kw.get("newer"), kw.get("older"))
    if view == "archive":
        return _archive(ctx, kw.get("q", ""), kw.get("date"), kw.get("results") or [], kw.get("days") or [])
    return _notfound(ctx)
