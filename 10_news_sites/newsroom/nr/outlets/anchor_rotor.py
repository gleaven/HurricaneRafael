"""Anchor & Rotor Weekly: military community weekly for NAS Corpus Christi, NAS Kingsville
and the Army depot. Olive, navy and gold; Oswald headlines over Georgia body text."""
import datetime as dt

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Oswald:wght@400;600;700&display=swap"

CSS = """
:root{--olive:#1a2f1a;--olive2:#2a3e1a;--gold:#c8a84b;--gold-l:#e8c86b;--navy:#1a3a5c;--khaki:#f5f3ef;--tan:#c8b89a;
--white:#fff;--text:#1a1a1a;--muted:#6b6b5b;--alert:#8b1a1a;--amber:#8a6512;--border:#d4c8ae}
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--khaki);color:var(--text);font-size:16px;line-height:1.6}
a{color:var(--navy);text-decoration:none}a:hover{color:#8a6f22;text-decoration:underline}
p{margin:0 0 12px}h1,h2,h3,h4{margin:0}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.osw{font-family:'Oswald','Arial Narrow',Arial,sans-serif}
.utility{background:var(--navy);color:#b8c2d6;font:11px/1.4 'Oswald','Arial Narrow',sans-serif;letter-spacing:.08em;text-transform:uppercase;padding-block:6px;text-align:center}
.masthead{background:var(--olive);border-bottom:4px solid var(--gold);padding-block:16px 14px}
.mast-in{max-width:1100px;margin:0 auto;display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.mast-in svg{flex-shrink:0}
.mast-titles{min-width:0;flex:1}
.mast-titles h1 a{font-family:'Oswald','Arial Narrow',sans-serif;font-size:2.4rem;font-weight:700;color:var(--gold);letter-spacing:.06em;line-height:1;text-decoration:none}
.tagline{font-style:italic;color:#9aad9a;font-size:.88rem;margin-top:4px}
.edition{font-family:'Oswald','Arial Narrow',sans-serif;color:var(--gold-l);font-size:.85rem;letter-spacing:.1em;text-transform:uppercase;text-align:right}
.edition .date{display:block;color:#c9d4c0;font-size:.78rem;letter-spacing:.06em;text-transform:none;font-family:Georgia,serif;font-style:italic}
nav.secnav{background:var(--navy);border-bottom:2px solid var(--gold)}
nav.secnav .in{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap}
nav.secnav a{display:block;color:#d4dbe8;font:600 .82rem/1 'Oswald','Arial Narrow',sans-serif;letter-spacing:.08em;text-transform:uppercase;padding:11px 14px;border-right:1px solid rgba(255,255,255,.08)}
nav.secnav a:hover,nav.secnav a.on{background:var(--olive);color:var(--gold);text-decoration:none}
.advisory{background:var(--olive2);border-left:5px solid var(--gold);color:#d8e8c8;padding-block:12px}
.advisory .in{max-width:1100px;margin:0 auto;display:flex;flex-direction:column;gap:8px}
.adv-row{display:flex;align-items:flex-start;gap:12px;font:.9rem/1.45 'Oswald','Arial Narrow',sans-serif;letter-spacing:.03em}
.adv-label{background:var(--gold);color:var(--olive);font-weight:700;padding:3px 10px;font-size:.72rem;letter-spacing:.12em;white-space:nowrap;flex-shrink:0;margin-top:1px}
.adv-label.emergency,.adv-label.warning{background:#c0392b;color:#fff}
.adv-label.watch,.adv-label.advisory{background:var(--gold);color:var(--olive)}
.adv-label.calm{background:#4f6b3a;color:#e7efd9}
.adv-since{display:block;font-family:Georgia,serif;font-style:italic;font-size:.75rem;color:#a9bb9a;letter-spacing:0}
.opsec{font-family:Georgia,serif;font-style:italic;font-size:.78rem;color:#b9c8aa}
.main{max-width:1100px;margin:0 auto;padding-block:24px;display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px}
.col{min-width:0}
.label{font:700 .7rem/1 'Oswald','Arial Narrow',sans-serif;letter-spacing:.15em;text-transform:uppercase;color:#fff;background:var(--navy);display:inline-block;padding:4px 10px;margin-bottom:10px}
.label.gold{background:var(--gold);color:var(--olive)}.label.red{background:var(--alert)}
.label a{color:inherit}
.lead{background:var(--white);border:1px solid var(--border);border-top:4px solid var(--navy);padding:24px;margin-bottom:22px}
.lead h2{font:700 1.8rem/1.2 'Oswald','Arial Narrow',sans-serif;color:var(--navy);margin-bottom:10px;text-wrap:balance}
.lead h2 a{color:inherit}
.photo{height:210px;background:linear-gradient(135deg,#2a3e1a 0%,#3a5020 50%,#2a4418 100%);position:relative;overflow:hidden;margin-bottom:18px;display:flex;align-items:center;justify-content:center}
.photo::before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(45deg,transparent,transparent 20px,rgba(0,0,0,.06) 20px,rgba(0,0,0,.06) 40px)}
.photo span{position:relative;font:700 .8rem 'Oswald',sans-serif;letter-spacing:.3em;color:rgba(200,168,75,.55);text-transform:uppercase}
.byline{font-size:.8rem;color:var(--muted);font-style:italic;margin-bottom:12px}
.byline strong{font-style:normal;color:var(--text)}
.dek{font-size:1.02rem;color:#333;font-style:italic;border-left:3px solid var(--gold);padding-left:12px;margin-bottom:14px}
.more{font:600 .8rem 'Oswald',sans-serif;letter-spacing:.1em;text-transform:uppercase}
.h-sec{font:700 1.05rem/1.2 'Oswald','Arial Narrow',sans-serif;color:var(--olive);letter-spacing:.08em;text-transform:uppercase;border-bottom:2px solid var(--tan);padding-bottom:6px;margin:4px 0 14px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:24px}
.card{background:var(--white);border:1px solid var(--border);border-top:3px solid var(--gold);padding:16px;min-width:0}
.card h3{font:600 1.02rem/1.3 'Oswald','Arial Narrow',sans-serif;color:var(--navy);margin-bottom:8px}
.card h3 a{color:inherit}
.card p{font-size:.86rem;color:#444;margin-bottom:8px}
.meta{font-size:.76rem;color:var(--muted);font-style:italic}
.meta .sec{font-style:normal;font-family:'Oswald',sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--navy);font-size:.7rem}
.board{background:#efe6cf;border:1px solid var(--tan);border-top:4px solid var(--gold);padding:18px;margin-bottom:24px;
background-image:radial-gradient(rgba(120,95,40,.12) 1px,transparent 1px);background-size:14px 14px}
.board h3{font:700 1.05rem 'Oswald',sans-serif;color:var(--olive);letter-spacing:.08em;text-transform:uppercase;margin-bottom:12px}
.notes{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.note{background:#fffdf5;border:1px solid #e3d6b2;padding:14px 14px 12px;box-shadow:2px 3px 0 rgba(0,0,0,.08);position:relative;min-width:0}
.note:nth-child(2n){transform:rotate(.6deg)}.note:nth-child(2n+1){transform:rotate(-.5deg)}
.note::before{content:'';position:absolute;top:-7px;left:50%;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:#b0392b;box-shadow:0 1px 2px rgba(0,0,0,.4)}
.note h4{font:600 .95rem/1.3 'Oswald',sans-serif;color:var(--navy);margin-bottom:6px}
.note h4 a{color:inherit}
.note p{font-size:.82rem;color:#4a4a3e;margin-bottom:6px}
.side{display:flex;flex-direction:column;gap:18px;min-width:0}
.box{background:var(--white);border:1px solid var(--border);padding:16px}
.box h4{font:700 .82rem 'Oswald',sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--navy);margin-bottom:10px;border-bottom:1px solid var(--tan);padding-bottom:6px}
.navy{background:var(--navy);color:#fff;border:0}
.navy h4{color:var(--gold);border-color:rgba(200,168,75,.3)}
.navy a{display:flex;justify-content:space-between;gap:8px;color:#c6cfe0;font-size:.85rem;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.08)}
.navy a:hover{color:var(--gold)}
.navy a .n{font-family:'Oswald',sans-serif;color:var(--gold)}
.olive{background:var(--olive);color:#d5e1c8;border:0}
.olive h4{color:var(--gold);border-color:rgba(200,168,75,.3)}
.olive p{font-size:.84rem;margin-bottom:8px}
.chapel{border:2px solid var(--gold);position:relative;margin-top:10px}
.chapel::before{content:'\\271D';position:absolute;top:-14px;left:50%;transform:translateX(-50%);background:var(--white);padding:0 8px;color:var(--gold);font-size:1.15rem}
.chapel p{font-size:.85rem;color:#333;margin-bottom:8px}
.latest li{margin:0 0 9px;font-size:.86rem;line-height:1.35}
.latest{list-style:none;margin:0;padding:0}
.latest .meta{display:block}
.story{background:var(--white);border:1px solid var(--border);border-top:4px solid var(--navy);padding:26px}
.story h1{font:700 2rem/1.15 'Oswald','Arial Narrow',sans-serif;color:var(--navy);margin-bottom:12px;text-wrap:balance}
.story .body p{font-size:1.02rem;line-height:1.7;margin-bottom:14px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 6px}
.tag{font:600 .7rem 'Oswald',sans-serif;letter-spacing:.08em;text-transform:uppercase;background:var(--khaki);border:1px solid var(--tan);color:var(--olive);padding:3px 8px}
.pager{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-top:18px;border-top:2px solid var(--tan);padding-top:12px;font-size:.88rem}
.pager a{max-width:48%}
.pager small{display:block;font:600 .68rem 'Oswald',sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.list{list-style:none;margin:0;padding:0}
.list li{background:var(--white);border:1px solid var(--border);border-left:4px solid var(--gold);padding:12px 14px;margin-bottom:10px}
.list li h3{font:600 1.02rem/1.3 'Oswald',sans-serif;color:var(--navy);margin-bottom:4px}
.list li h3 a{color:inherit}
.list li p{font-size:.85rem;color:#444;margin:4px 0 0}
.search{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.search input{flex:1;min-width:0;padding:9px 11px;border:1px solid var(--tan);font:inherit;background:#fff}
.search button{background:var(--olive);color:var(--gold);border:0;padding:9px 16px;font:600 .82rem 'Oswald',sans-serif;letter-spacing:.1em;text-transform:uppercase;cursor:pointer}
.filter{font-size:.85rem;color:var(--muted);margin-bottom:14px}
.filter a{font-family:'Oswald',sans-serif;font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;margin-left:8px}
.dayhead{font:700 .9rem 'Oswald',sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--olive);margin:18px 0 8px}
.days{display:flex;flex-wrap:wrap;gap:6px}
.days a{font:600 .74rem 'Oswald',sans-serif;letter-spacing:.04em;background:var(--khaki);border:1px solid var(--tan);padding:3px 7px;color:var(--navy)}
.days a.on{background:var(--olive);color:var(--gold);border-color:var(--olive)}
.empty{background:var(--white);border:1px dashed var(--tan);padding:28px;text-align:center;color:var(--muted);font-style:italic}
footer{background:var(--olive);border-top:4px solid var(--gold);color:#a9bb9a;padding-block:20px;text-align:center;font-size:.8rem;line-height:1.8;margin-top:12px}
footer a{color:var(--gold)}
@media (max-width:860px){.main{grid-template-columns:minmax(0,1fr)}.edition{text-align:left;width:100%}}
@media (max-width:600px){.grid,.notes{grid-template-columns:minmax(0,1fr)}.mast-titles h1 a{font-size:1.65rem}
.lead,.story{padding:18px}.story h1{font-size:1.55rem}.lead h2{font-size:1.4rem}.mast-in svg{width:38px;height:48px}
nav.secnav a{padding:10px 10px;font-size:.76rem}.pager a{max-width:100%}}
"""

ANCHOR_SVG = ('<svg width="52" height="64" viewBox="0 0 52 64" fill="none" aria-hidden="true">'
              '<circle cx="26" cy="11" r="8" stroke="#c8a84b" stroke-width="2.5"/><circle cx="26" cy="11" r="4" fill="#c8a84b"/>'
              '<line x1="26" y1="19" x2="26" y2="52" stroke="#c8a84b" stroke-width="2.5"/>'
              '<line x1="10" y1="30" x2="42" y2="30" stroke="#c8a84b" stroke-width="2"/>'
              '<path d="M8 42 Q2 50 10 56 Q26 64 42 56 Q50 50 44 42" stroke="#c8a84b" stroke-width="2.5" stroke-linecap="round"/></svg>')

LEVEL = {"emergency": "EMERGENCY", "warning": "WARNING", "watch": "WATCH", "advisory": "ADVISORY"}


def week_of(ctx):
    d = C.local(ctx["now"]).date()
    monday = d - dt.timedelta(days=d.weekday())
    return f"{C.AP_MONTHS[monday.month - 1]} {monday.day}, {monday.year}"


def sec_slug(name):
    return C.esc(name.lower().replace(" & ", "-").replace(" ", "-"))


def frame(ctx, title, inner, active=""):
    o = ctx["outlet"]
    nav = [f'<a href="{C.url_home(ctx)}"{" class=on" if active == "home" else ""}>Front Page</a>']
    for s in o["sections"]:
        on = ' class="on"' if active == s["slug"] else ""
        nav.append(f'<a href="{C.url_section(ctx, s["slug"])}"{on}>{esc(s["name"])}</a>')
    nav.append(f'<a href="{C.url_archive(ctx)}"{" class=on" if active == "archive" else ""}>Archive</a>')

    alerts = ctx["status"]["alerts"]
    if alerts:
        rows = "".join(
            f'<div class="adv-row"><span class="adv-label {a["level"]}">{LEVEL.get(a["level"], "ADVISORY")}</span>'
            f'<span>{esc(a["text"])}<span class="adv-since">In effect since {esc(C.fmt_dt_ap(a["since"]))}</span></span></div>'
            for a in alerts)
    else:
        rows = ('<div class="adv-row"><span class="adv-label calm">STATUS</span>'
                '<span>No active advisories for the Coastal Bend installations. Routine operations.</span></div>')
    advisory = (f'<div class="advisory gut" role="region" aria-label="Base advisories"><div class="in">{rows}'
                f'<div class="opsec">Operational details are released by public affairs only.</div></div></div>')

    return (C.head(ctx, title, FONTS, CSS) +
            '<div id="nr-root">'
            f'<div class="utility gut">Community publication · NAS Corpus Christi · NAS Kingsville · Corpus Christi Army Depot · {C.clock_span(ctx, "date-long")}</div>'
            f'<header class="masthead gut"><div class="mast-in">{ANCHOR_SVG}'
            f'<div class="mast-titles"><h1><a href="{C.url_home(ctx)}">ANCHOR &amp; ROTOR WEEKLY</a></h1>'
            '<div class="tagline">Serving those who serve the Coastal Bend</div></div>'
            f'<div class="edition">Week of {esc(week_of(ctx))}<span class="date">Updated {C.clock_span(ctx, "time-ap")}</span></div>'
            '</div></header>'
            f'<nav class="secnav gut" aria-label="Sections"><div class="in">{"".join(nav)}</div></nav>'
            f'{advisory}{inner}'
            '<footer class="gut">Anchor &amp; Rotor Weekly is a community publication for service members, civilians and families '
            'of the Coastal Bend installations. Opinions in community sections are those of contributors. '
            f'Operational details are released by public affairs only.<br><a href="{C.url_rss(ctx)}">RSS feed</a> · '
            'All people and events are fictional.</footer>'
            '</div>' + C.foot(ctx))


def meta(ctx, a, section=True):
    sec = f'<span class="sec">{esc(a["section"])}</span> · ' if section else ""
    by = f'By {esc(C.byline(a))} · ' if a["authors"] else ""
    return f'<div class="meta">{sec}{by}{C.ago_span(ctx, a)}</div>'


def card(ctx, a):
    return (f'<div class="card" data-article-id="{a["pid"]}"><h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'<p>{esc(C.excerpt(a, 28))}</p>{meta(ctx, a)}</div>')


def list_item(ctx, a):
    return (f'<li data-article-id="{a["pid"]}"><h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'{meta(ctx, a)}<p>{esc(C.excerpt(a, 34))}</p></li>')


def sidebar(ctx, extra=""):
    o = ctx["outlet"]
    counts = {}
    for a in ctx["articles"]:
        counts[a["section"]] = counts.get(a["section"], 0) + 1
    links = "".join(f'<a href="{C.url_section(ctx, s["slug"])}"><span>{esc(s["name"])}</span><span class="n">{counts.get(s["name"], 0)}</span></a>'
                    for s in o["sections"])
    latest = "".join(f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                     f'<span class="meta">{C.ago_span(ctx, a)}</span></li>' for a in ctx["articles"][:5])
    latest_box = f'<div class="box"><h4>Latest Updates</h4><ul class="latest">{latest}</ul></div>' if latest else ""
    return (f'<aside class="side">{extra}'
            f'<div class="box navy"><h4>Sections</h4>{links}<a href="{C.url_archive(ctx)}"><span>Back issues &amp; search</span><span class="n">→</span></a></div>'
            f'{latest_box}'
            '<div class="box olive"><h4>Family Readiness</h4>'
            '<p>After a storm, check in with your command first. Your command ombudsman and family readiness group can '
            'connect you with housing, child care and financial assistance.</p>'
            '<p>Keep your contact information current in your command\'s accountability system so leaders can reach you.</p></div>'
            '<div class="box chapel"><h4>Chaplain\'s Corner</h4>'
            '<p>Chapel programs and confidential pastoral care are open to service members, civilians and families of every faith '
            'or none. Ask your command or the installation chapel office for current service times.</p></div>'
            '</aside>')


def render(view, ctx, **kw):
    o = ctx["outlet"]
    name = o["name"]

    if view == "home":
        arts = ctx["articles"]
        if not arts:
            inner = ('<div class="main gut"><div class="col"><div class="empty">The first edition of Anchor &amp; Rotor Weekly is on '
                     'its way. Check back for base news, readiness updates and family resources.</div></div>'
                     + sidebar(ctx) + '</div>')
            return frame(ctx, f"{name} | Front Page", inner, "home")
        recent_breaking = [a for a in C.recent(ctx, 48) if C.is_breaking(a)]
        lead = recent_breaking[0] if recent_breaking else arts[0]
        rest = [a for a in arts if a["pid"] != lead["pid"]]
        families = [a for a in rest if a["section"] == "Families"][:4]
        grid_items = [a for a in rest if a not in families][:6]
        label_cls = "red" if C.is_breaking(lead) and lead in recent_breaking else ""
        label_txt = "Special Edition" if label_cls else esc(lead["section"])
        paras = "".join(f"<p>{esc(p)}</p>" for p in lead["body"][:2])
        by = f'By <strong>{esc(C.byline(lead))}</strong> · ' if lead["authors"] else ""
        lead_html = (f'<article class="lead" data-article-id="{lead["pid"]}"><span class="label {label_cls}">{label_txt}</span>'
                     f'<div class="photo"><span>{esc(lead["section"])}</span></div>'
                     f'<h2><a href="{lead["url"]}">{esc(lead["headline"])}</a></h2>'
                     f'<div class="byline">{by}{esc(C.pub_label(lead))}</div>'
                     f'<p class="dek">{esc(lead["summary"])}</p>{paras}'
                     f'<a class="more" href="{lead["url"]}">Continue reading →</a></article>')
        grid = ('<h3 class="h-sec">This Week on Base</h3><div class="grid">' + "".join(card(ctx, a) for a in grid_items) + '</div>') if grid_items else ""
        board = ""
        if families:
            notes = "".join(f'<div class="note" data-article-id="{a["pid"]}"><h4><a href="{a["url"]}">{esc(a["headline"])}</a></h4>'
                            f'<p>{esc(C.excerpt(a, 22))}</p><div class="meta">{C.ago_span(ctx, a)}</div></div>' for a in families)
            fam = next((s for s in o["sections"] if s["name"] == "Families"), None)
            more = f' <a class="more" href="{C.url_section(ctx, fam["slug"])}">All family news →</a>' if fam else ""
            board = f'<section class="board"><h3>Families Bulletin Board</h3><div class="notes">{notes}</div><p style="margin:12px 0 0">{more}</p></section>'
        inner = f'<div class="main gut"><div class="col">{lead_html}{board}{grid}</div>{sidebar(ctx)}</div>'
        return frame(ctx, f"{name} | Front Page", inner, "home")

    if view == "section":
        sec, items = kw["section"], kw["items"]
        body = ("<ul class='list'>" + "".join(list_item(ctx, a) for a in items) + "</ul>") if items else \
            f'<div class="empty">No {esc(sec["name"])} stories have been published yet.</div>'
        inner = (f'<div class="main gut"><div class="col"><span class="label gold">Section</span>'
                 f'<h2 class="h-sec">{esc(sec["name"])}</h2>{body}</div>{sidebar(ctx)}</div>')
        return frame(ctx, f'{sec["name"]} | {name}', inner, sec["slug"])

    if view == "article":
        a = kw["article"]
        sec = next((s for s in o["sections"] if s["name"] == a["section"]), None)
        sec_lbl = f'<a href="{C.url_section(ctx, sec["slug"])}">{esc(a["section"])}</a>' if sec else esc(a["section"])
        tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a["storylines"])
        tags = f'<div class="tags">{tags}</div>' if tags else ""
        by = f'By <strong>{esc(C.byline(a))}</strong> · ' if a["authors"] else ""
        pager = ""
        if kw.get("newer") or kw.get("older"):
            nw, ol = kw.get("newer"), kw.get("older")
            left = f'<a href="{ol["url"]}" data-article-id="{ol["pid"]}" data-nr-nobadge><small>← Previous story</small>{esc(ol["headline"])}</a>' if ol else "<span></span>"
            right = f'<a href="{nw["url"]}" data-article-id="{nw["pid"]}" data-nr-nobadge style="text-align:right"><small>Next story →</small>{esc(nw["headline"])}</a>' if nw else "<span></span>"
            pager = f'<nav class="pager" aria-label="More stories">{left}{right}</nav>'
        rel = kw.get("related") or []
        rel_box = ""
        if rel:
            items = "".join(f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(r["headline"])}</a>'
                            f'<span class="meta">{esc(r["outlet_name"])} · {C.ago_span(ctx, r)}</span></li>' for r in rel)
            rel_box = f'<div class="box"><h4>Related Coverage</h4><ul class="latest">{items}</ul></div>'
        story = (f'<article class="story" data-article-id="{a["pid"]}"><span class="label">{sec_lbl}</span>'
                 f'<h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
                 f'<div class="byline">{by}{esc(C.pub_label(a))} · {C.read_minutes(a)} min read</div>'
                 f'<div class="body">{C.paras(a["body"])}</div>{tags}{pager}</article>')
        inner = f'<div class="main gut"><div class="col">{story}</div>{sidebar(ctx, rel_box)}</div>'
        return frame(ctx, f'{a["headline"]} | {name}', inner, sec["slug"] if sec else "")

    if view == "archive":
        q, date, results, days = kw.get("q", ""), kw.get("date"), kw.get("results", []), kw.get("days", [])
        form = (f'<form class="search" action="{C.url_archive(ctx)}" role="search">'
                f'<input name="q" value="{esc(q)}" placeholder="Search back issues" aria-label="Search back issues">'
                + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "")
                + '<button type="submit">Search</button></form>')
        filt = []
        if q:
            filt.append(f'matching “{esc(q)}”')
        if date:
            try:
                d = dt.date.fromisoformat(date)
                filt.append(f'from {C.MONTHS[d.month - 1]} {d.day}, {d.year}')
            except ValueError:
                filt.append(esc(date))
        filter_html = (f'<div class="filter">{len(results)} {"story" if len(results) == 1 else "stories"} {" ".join(filt)}'
                       f'<a href="{C.url_archive(ctx)}">Clear</a></div>') if filt else \
            f'<div class="filter">{len(results)} {"story" if len(results) == 1 else "stories"} in the archive</div>'
        groups = C.group_by_day(results)
        if groups:
            body = "".join(f'<h3 class="dayhead">{esc(C.fmt_date_long(items[0]["ts"]))}</h3><ul class="list">'
                           + "".join(list_item(ctx, a) for a in items) + "</ul>" for _, items in groups)
        else:
            body = '<div class="empty">No stories match. Try a different word or clear the filter.</div>'
        day_links = "".join(
            f'<a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""}>'
            f'{esc(C.AP_MONTHS[int(d[5:7]) - 1])} {int(d[8:10])} <span style="opacity:.6">({n})</span></a>'
            for d, n in days)
        day_box = f'<div class="box"><h4>Issues by Day</h4><div class="days">{day_links}</div></div>' if day_links else ""
        inner = (f'<div class="main gut"><div class="col"><span class="label gold">Back Issues</span>'
                 f'<h2 class="h-sec">Archive</h2>{form}{filter_html}{body}</div>{sidebar(ctx, day_box)}</div>')
        return frame(ctx, f"Archive | {name}", inner, "archive")

    inner = ('<div class="main gut"><div class="col"><span class="label red">Not Available</span>'
             '<h2 class="h-sec">This page isn\'t available</h2>'
             '<div class="empty">The story you are looking for is not in our pages. It may have moved, or the link may be wrong.<br><br>'
             f'<a class="more" href="{C.url_home(ctx)}">Front page</a> · <a class="more" href="{C.url_archive(ctx)}">Search back issues</a></div>'
             f'</div>{sidebar(ctx)}</div>')
    return frame(ctx, f"Page not found | {name}", inner)
