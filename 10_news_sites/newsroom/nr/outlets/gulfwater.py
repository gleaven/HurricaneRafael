"""Gulfwater Maritime Report — maritime trade publication.

Visual identity from 10_news_sites/gulfwater-maritime.html: deep maritime navy, port orange,
IBM Plex Sans + Mono, dense data bar, port status widget, tabular logs. All content from ctx.
"""
import datetime as dt

from nr import common as C
from nr.common import esc

FONTS = ("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400"
         "&family=IBM+Plex+Mono:wght@400;500;600&display=swap")

CSS = """
:root{--navy:#0d2137;--navy-mid:#132840;--deep:#0a1929;--accent:#e67e22;--alert:#c0392b;--bg:#f2f4f7;--card:#fff;
  --text:#1a2332;--muted:#6b7a8d;--divider:#cbd5e1;--open:#16a34a;--amber:#d97706;--closed:#dc2626}
body{margin:0;font-family:'IBM Plex Sans',system-ui,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.55}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.mono{font-family:'IBM Plex Mono',ui-monospace,monospace}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.inner{max-width:1200px;margin:0 auto}
.data-bar{background:var(--deep);color:#7fb3cc;font:11px/1.4 'IBM Plex Mono',monospace;padding-block:7px;overflow-x:auto;white-space:nowrap}
.data-bar .inner{display:flex;gap:18px;align-items:center}
.seg{display:inline-flex;gap:6px;align-items:center}
.seg .k{color:#4a7a94;text-transform:uppercase;font-size:10px;letter-spacing:.06em}
.seg .v{color:#a8d4e8}
.seg .v.c-open{color:#4ade80}.seg .v.c-amber{color:#fbbf24}.seg .v.c-red{color:#f87171}
.sep{color:#2a4a64}
.sec-banner{background:var(--alert);color:#fff;font:11px/1.4 'IBM Plex Mono',monospace;padding-block:8px}
.sec-banner .inner{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sec-banner a{color:#fff;font-weight:600}
.tagx{background:rgba(0,0,0,.3);padding:2px 8px;border-radius:2px;font-weight:600;font-size:10px;letter-spacing:.08em;white-space:nowrap}
header.mast{background:var(--navy);padding-block:14px;border-bottom:2px solid var(--accent)}
header.mast .inner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.logo{display:flex;align-items:center;gap:12px;color:#fff}
.logo:hover{text-decoration:none}
.logo svg{flex-shrink:0}
.logo-name{font-size:1.3rem;font-weight:700;color:#fff;letter-spacing:-.01em;line-height:1.15}
.logo-sub{font-size:10px;color:#7fb3cc;letter-spacing:.08em;text-transform:uppercase;margin-top:2px}
.header-meta{font:11px/1.6 'IBM Plex Mono',monospace;color:#7fb3cc;text-align:right}
@media(max-width:560px){.header-meta{text-align:left}}
nav.sections{background:var(--navy-mid);border-bottom:1px solid #1e3a55}
nav.sections ul{list-style:none;display:flex;margin:0 auto;padding:0;max-width:1200px;overflow-x:auto}
nav.sections a{display:block;color:#9bb8cc;font-size:12px;font-weight:500;padding:9px 14px;white-space:nowrap;letter-spacing:.03em}
nav.sections a:hover{color:#fff;text-decoration:none;background:rgba(255,255,255,.06)}
nav.sections a.active{color:var(--accent);box-shadow:inset 0 -2px 0 var(--accent)}
.main{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:24px;align-items:start;padding-block:22px}
@media(max-width:920px){.main{grid-template-columns:1fr}}
.main>*{min-width:0}
.label{font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 10px;display:flex;align-items:center;gap:10px}
.label::after{content:'';flex:1;height:1px;background:var(--divider)}
.panel{background:var(--card);border:1px solid var(--divider);border-radius:4px;overflow:hidden;margin-bottom:20px}
.panel-h{background:var(--navy);color:#cfe0ec;padding:9px 14px;font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;display:flex;justify-content:space-between;gap:8px}
.lead .flag{background:var(--accent);color:#fff;padding:6px 14px;font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase}
.lead .flag.brk{background:var(--alert)}
.lead-in{padding:18px 20px}
.hed{font-size:1.3rem;font-weight:700;line-height:1.3;color:var(--navy);margin:0 0 8px;text-wrap:balance}
.hed a{color:var(--navy)}
.hed a:hover{color:var(--accent);text-decoration:none}
.byl{font:11px/1.5 'IBM Plex Mono',monospace;color:var(--muted);margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--divider)}
.dek{font-size:14px;color:#334155;margin:0 0 12px;font-weight:500}
.body{font-size:13.5px;line-height:1.72;color:#2c3e50}
.body p{margin:0 0 12px}
.more{font:600 11px 'IBM Plex Mono',monospace;letter-spacing:.06em;text-transform:uppercase}
.list .item{padding:12px 16px;border-bottom:1px solid var(--divider);display:flex;gap:12px;align-items:flex-start}
.list .item:last-child{border-bottom:0}
.list .item:hover{background:#f8fafb}
.cat{font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:2px;white-space:nowrap;flex-shrink:0;min-width:84px;text-align:center}
.cat-security{background:#fef3cd;color:#92400e;border:1px solid #f59e0b}
.cat-ports{background:#dbeafe;color:#1e40af;border:1px solid #93c5fd}
.cat-tankers{background:#f0fdf4;color:#166534;border:1px solid #86efac}
.cat-regulation{background:#f5f3ff;color:#5b21b6;border:1px solid #c4b5fd}
@media(max-width:520px){.list .item{flex-direction:column;gap:6px}.cat{min-width:0}}
.info{min-width:0}
.ihed{font-size:13.5px;font-weight:600;line-height:1.35;margin:0 0 3px}
.ihed a{color:var(--text)}
.ihed a:hover{color:var(--accent);text-decoration:none}
.imeta{font:10.5px 'IBM Plex Mono',monospace;color:var(--muted)}
.idek{font-size:12.5px;color:#475569;margin:3px 0 0}
.empty{padding:22px 18px;font:12px/1.6 'IBM Plex Mono',monospace;color:var(--muted)}
/* port widget */
.port .code{display:flex;align-items:center;gap:10px;padding:14px;border-bottom:1px solid var(--divider)}
.badge{font:700 12px 'IBM Plex Mono',monospace;letter-spacing:.08em;padding:4px 10px;border-radius:3px;color:#fff}
.b-open{background:var(--open)}.b-amber{background:var(--amber)}.b-red{background:var(--closed)}
.port .lab{font-weight:700;font-size:14px;color:var(--navy)}
.row{display:flex;justify-content:space-between;gap:12px;padding:8px 14px;border-bottom:1px solid var(--divider);font-size:12px}
.row:last-child{border-bottom:0}
.row .k{color:var(--muted);font-weight:500}
.row .v{font:600 11px 'IBM Plex Mono',monospace;text-align:right}
.detail{padding:12px 14px;font-size:12.5px;color:#334155;border-bottom:1px solid var(--divider);line-height:1.55}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{background:#f0f4f8;color:var(--muted);font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;padding:8px 12px;text-align:left;border-bottom:1px solid var(--divider);white-space:nowrap}
td{padding:9px 12px;border-bottom:1px solid var(--divider);font:11.5px 'IBM Plex Mono',monospace;color:var(--text);vertical-align:top}
tr:last-child td{border-bottom:0}
td.cur{color:var(--accent);font-weight:600}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle}
.d-open{background:var(--open)}.d-amber{background:var(--amber)}.d-red{background:var(--closed)}
.notices .n{padding:10px 14px;border-bottom:1px solid var(--divider);font-size:12.5px;line-height:1.5}
.notices .n:last-child{border-bottom:0}
.notices .lv{font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--alert);display:block;margin-bottom:2px}
.secfile .s{padding:10px 14px;border-bottom:1px solid var(--divider)}
.secfile .s:last-child{border-bottom:0}
.secfile a{color:var(--text);font-weight:600;font-size:12.5px;line-height:1.35}
.secfile .imeta{display:block;margin-top:2px}
/* article */
.story{background:var(--card);border:1px solid var(--divider);border-radius:4px;overflow:hidden}
.story .lead-in{padding:22px 24px}
.story h1{font-size:1.65rem;line-height:1.25;color:var(--navy);margin:0 0 10px;text-wrap:balance}
@media(max-width:480px){.story h1{font-size:1.35rem}.story .lead-in{padding:18px 16px}}
.story .body{font-size:14.5px;max-width:72ch}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin:18px 0 4px}
.tag{font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.06em;text-transform:uppercase;background:#eef2f7;color:#334155;border:1px solid var(--divider);padding:3px 8px;border-radius:2px}
.rel .item .src{font:10.5px 'IBM Plex Mono',monospace;color:var(--accent);text-transform:uppercase;letter-spacing:.06em}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}
.pager a{display:block;background:var(--card);border:1px solid var(--divider);border-radius:4px;padding:10px 12px;color:var(--text);font-size:12.5px;font-weight:600;line-height:1.35}
.pager a:hover{border-color:var(--accent);text-decoration:none}
.pager span{display:block;font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:3px}
.pager .nx{text-align:right}
/* archive */
form.search{display:flex;gap:8px;flex-wrap:wrap;padding:14px}
form.search input{flex:1;min-width:0;padding:9px 11px;border:1px solid var(--border,#b8c4d4);border-radius:3px;font:13px 'IBM Plex Mono',monospace}
form.search button{padding:9px 16px;border:0;border-radius:3px;background:var(--accent);color:#fff;font:600 12px 'IBM Plex Sans',sans-serif;cursor:pointer}
.filter{padding:0 14px 12px;font:11px 'IBM Plex Mono',monospace;color:var(--muted)}
.dayh{background:#f0f4f8;padding:7px 16px;font:600 10.5px 'IBM Plex Mono',monospace;letter-spacing:.08em;text-transform:uppercase;color:var(--navy);border-bottom:1px solid var(--divider)}
.days{padding:12px 14px;max-height:620px;overflow:auto}
.days h4{font:600 10px 'IBM Plex Mono',monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:10px 0 6px}
.days h4:first-child{margin-top:0}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chips a{font:11px 'IBM Plex Mono',monospace;border:1px solid var(--divider);border-radius:2px;padding:2px 7px;color:var(--navy);white-space:nowrap}
.chips a.on{background:var(--navy);color:#fff;border-color:var(--navy)}
footer.foot{background:var(--navy);color:#7fb3cc;padding-block:24px;font:11px/1.7 'IBM Plex Mono',monospace;margin-top:28px}
footer.foot .inner{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap}
footer.foot a{color:#a8d4e8}
"""

ANCHOR = ('<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#e67e22" stroke-width="2" '
          'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="2.2"/>'
          '<path d="M12 7.2V21"/><path d="M7.5 11h9"/><path d="M4 14a8 8 0 0 0 16 0"/><path d="M4 14l-1.5 1.5M20 14l1.5 1.5"/></svg>')

RED = ("YANKEE", "ZULU", "CLOSED")
AMBER = ("X-RAY", "RESTRICTED")


def tone(code):
    if code in RED:
        return "red"
    if code in AMBER:
        return "amber"
    return "open"


def cat_html(section):
    cls = "".join(ch for ch in section.lower() if ch.isalpha())
    return f'<span class="cat cat-{cls}">{esc(section)}</span>'


def stamp(ts):
    """Compact trade-press timestamp: 14 SEP 2027 01:15 CDT"""
    d = C.local(ts)
    return f"{d.day:02d} {C.MONTHS[d.month - 1][:3].upper()} {d.year} {d.hour:02d}:{d.minute:02d} {C.tz_abbr(ts)}"


def day_stamp(ts):
    d = C.local(ts)
    return f"{d.day:02d} {C.MONTHS[d.month - 1][:3].upper()} {d.year}"


def date_label(iso):
    d = dt.date.fromisoformat(iso)
    return f"{C.DAYS[d.weekday()]}, {C.MONTHS[d.month - 1]} {d.day}, {d.year}"


def by(a):
    return C.byline(a) or "Gulfwater staff"


def section_href(ctx, name):
    for s in ctx["outlet"]["sections"]:
        if s["name"] == name:
            return C.url_section(ctx, s["slug"])
    return C.url_home(ctx)


# ---------------------------------------------------------------- sidebar widgets
def port_widget(ctx):
    p = ctx["status"].get("port")
    if not p:
        return ('<div class="panel port"><div class="panel-h"><span>Port conditions</span><span>Corpus Christi</span></div>'
                '<div class="empty">No port condition reported.</div></div>')
    t = tone(p["code"])
    return (f'<div class="panel port"><div class="panel-h"><span>Port conditions</span><span>Corpus Christi</span></div>'
            f'<div class="code"><span class="badge b-{t}">{esc(p["code"])}</span><span class="lab">{esc(p["label"])}</span></div>'
            f'<div class="detail">{esc(p["detail"])}</div>'
            f'<div class="row"><span class="k">In effect since</span><span class="v">{esc(stamp(p["ts"]))}</span></div>'
            f'<div class="row"><span class="k">As of</span><span class="v">{C.clock_span(ctx, "datetime-ap")}</span></div></div>')


def port_log(ctx, limit=8):
    hist = ctx["status"].get("port_history") or []
    if not hist:
        return ""
    rows = []
    for i, p in enumerate(hist):
        to = hist[i + 1]["ts"] if i + 1 < len(hist) else None
        rows.append((p, to))
    rows = rows[::-1][:limit]
    body = "".join(
        f'<tr><td><span class="dot d-{tone(p["code"])}"></span>{esc(p["label"])}</td><td>{esc(day_stamp(p["ts"]))}</td>'
        + (f'<td>{esc(day_stamp(to))}</td>' if to else '<td class="cur">Current</td>') + '</tr>' for p, to in rows)
    return (f'<div class="panel"><div class="panel-h"><span>Port condition log</span><span>CC Ship Channel</span></div>'
            f'<div class="tablewrap"><table><thead><tr><th>Condition</th><th>From</th><th>To</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>')


def notices(ctx):
    al = ctx["status"].get("alerts") or []
    if not al:
        return ""
    items = "".join(f'<div class="n"><span class="lv">{esc(a["level"])}</span>{esc(a["text"])}</div>' for a in al)
    return f'<div class="panel notices"><div class="panel-h"><span>Public notices in effect</span></div>{items}</div>'


def security_file(ctx, exclude=None, limit=8):
    items = [a for a in ctx["articles"] if a["section"] == "Security" and a["pid"] != exclude][:limit]
    if not items:
        body = '<div class="empty">No security reporting on file.</div>'
    else:
        body = "".join(f'<div class="s" data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                       f'<span class="imeta">{esc(day_stamp(a["ts"]))} · {esc(by(a))}</span></div>' for a in items)
    return f'<div class="panel secfile"><div class="panel-h"><span>Security file</span><span>{len(items)}</span></div>{body}</div>'


def sidebar(ctx, exclude=None):
    return port_widget(ctx) + notices(ctx) + port_log(ctx) + security_file(ctx, exclude)


# ---------------------------------------------------------------- frame
def frame(ctx, title, inner, active=None):
    o = ctx["outlet"]
    p = ctx["status"].get("port")
    t = tone(p["code"]) if p else "open"
    plabel = p["label"].upper() if p else "NO REPORT"
    since = f'<span class="sep">|</span><span class="seg"><span class="k">Since</span><span class="v">{esc(stamp(p["ts"]))}</span></span>' if p else ""
    last24 = sum(1 for a in ctx["articles"] if ctx["now"] - a["ts"] <= 86400)
    bar = (f'<div class="data-bar gut"><div class="inner">'
           f'<span class="seg"><span class="k">Corpus Christi Ship Channel:</span><span class="v c-{t}">{esc(plabel)}</span></span>{since}'
           f'<span class="sep">|</span><span class="seg"><span class="k">Local</span><span class="v">{C.clock_span(ctx, "date-ap")} {C.clock_span(ctx, "time-24")}</span></span>'
           f'<span class="sep">|</span><span class="seg"><span class="k">Reports, 24h</span><span class="v">{last24}</span></span>'
           f'</div></div>')

    banner = ""
    sec = next((a for a in ctx["articles"] if a["section"] == "Security" and ctx["now"] - a["ts"] <= 48 * 3600), None)
    if sec:
        banner = (f'<div class="sec-banner gut"><div class="inner" data-article-id="{sec["pid"]}" data-nr-nobadge>'
                  f'<span class="tagx">SECURITY</span><a href="{sec["url"]}">{esc(sec["headline"])}</a>'
                  f'<span>· {esc(stamp(sec["ts"]))}</span></div></div>')

    nav = [f'<li><a href="{C.url_home(ctx)}" class="{"active" if active == "home" else ""}">Latest</a></li>']
    for s in o["sections"]:
        nav.append(f'<li><a href="{C.url_section(ctx, s["slug"])}" class="{"active" if active == s["slug"] else ""}">{esc(s["name"])}</a></li>')
    nav.append(f'<li><a href="{C.url_archive(ctx)}" class="{"active" if active == "archive" else ""}">Archives</a></li>')
    nav.append(f'<li><a href="{C.url_rss(ctx)}">RSS</a></li>')

    body = (f'<div id="nr-root">{bar}{banner}'
            f'<header class="mast gut"><div class="inner"><a class="logo" href="{C.url_home(ctx)}">{ANCHOR}<div>'
            f'<div class="logo-name">{esc(o["name"])}</div><div class="logo-sub">Ports · Tankers · Security · Regulation</div></div></a>'
            f'<div class="header-meta">{C.clock_span(ctx, "date-long")}<br>Published for maritime professionals</div></div></header>'
            f'<nav class="sections gut" aria-label="Sections"><ul>{"".join(nav)}</ul></nav>'
            f'<main class="gut"><div class="inner">{inner}</div></main>'
            f'<footer class="foot gut"><div class="inner"><span>{esc(o["name"])} · Port and shipping intelligence for the Gulf Coast</span>'
            f'<span>Reports public observations; does not speculate on attribution. All vessels, incidents and people are fictional.</span>'
            f'</div></footer></div>')
    return C.head(ctx, title, FONTS, CSS) + body + C.foot(ctx)


def item(ctx, a, dek=False, show_cat=True):
    d = f'<p class="idek">{esc(C.excerpt(a, 28))}</p>' if dek else ""
    c = cat_html(a["section"]) if show_cat else ""
    return (f'<div class="item" data-article-id="{a["pid"]}">{c}<div class="info">'
            f'<h3 class="ihed"><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'<div class="imeta">{esc(stamp(a["ts"]))} · {esc(by(a))} · {C.ago_span(ctx, a)}</div>{d}</div></div>')


# ---------------------------------------------------------------- views
def home(ctx):
    arts = ctx["articles"]
    if not arts:
        main = ('<div class="label">Latest reports</div><div class="panel"><div class="empty">'
                'No reports filed yet. Port conditions and channel status are updated in the sidebar as the Coast Guard '
                'posts them.</div></div>')
        return frame(ctx, ctx["outlet"]["name"], f'<div class="main"><div>{main}</div><aside>{sidebar(ctx)}</aside></div>', "home")
    lead = arts[0]
    flag = "Breaking" if lead["story_type"] == "breaking" else lead["section"]
    paras = "".join(f"<p>{esc(p)}</p>" for p in lead["body"][:2])
    lead_html = (f'<div class="label">Lead report</div>'
                 f'<div class="panel lead" data-article-id="{lead["pid"]}"><div class="flag{" brk" if lead["story_type"] == "breaking" else ""}">'
                 f'{esc(flag)} · {esc(stamp(lead["ts"]))}</div><div class="lead-in">'
                 f'<h2 class="hed"><a href="{lead["url"]}">{esc(lead["headline"])}</a></h2>'
                 f'<div class="byl">{esc(by(lead))} · {esc(lead["section"])} · {C.ago_span(ctx, lead)}</div>'
                 f'<p class="dek">{esc(lead["summary"])}</p><div class="body">{paras}</div>'
                 f'<a class="more" href="{lead["url"]}">Full report →</a></div></div>')
    rest = arts[1:21]
    lst = ""
    if rest:
        lst = (f'<div class="label">Latest reports</div><div class="panel list">'
               f'{"".join(item(ctx, a, dek=(i < 4)) for i, a in enumerate(rest))}</div>')
    if len(arts) > 21:
        lst += f'<p class="more"><a href="{C.url_archive(ctx)}">All reports in the archive →</a></p>'
    return frame(ctx, f'{ctx["outlet"]["name"]} | Ports, tankers and maritime security',
                 f'<div class="main"><div>{lead_html}{lst}</div><aside>{sidebar(ctx, exclude=None)}</aside></div>', "home")


def section(ctx, sec, items):
    if items:
        body = f'<div class="panel list">{"".join(item(ctx, a, dek=True, show_cat=False) for a in items)}</div>'
    else:
        body = f'<div class="panel"><div class="empty">No {esc(sec["name"]).lower()} reports filed yet.</div></div>'
    main = f'<div class="label">{esc(sec["name"])} · {len(items)} report{"s" if len(items) != 1 else ""}</div>{body}'
    return frame(ctx, f'{sec["name"]} | {ctx["outlet"]["name"]}',
                 f'<div class="main"><div>{main}</div><aside>{sidebar(ctx)}</aside></div>', sec["slug"])


def article(ctx, a, related, newer, older):
    tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a.get("storylines", []))
    story = (f'<article class="story" data-article-id="{a["pid"]}"><div class="lead flag{" brk" if a["story_type"] == "breaking" else ""}" '
             f'style="padding:6px 14px;color:#fff;font:600 10px \'IBM Plex Mono\',monospace;letter-spacing:.1em;text-transform:uppercase;'
             f'background:{"var(--alert)" if a["story_type"] == "breaking" else "var(--accent)"}">'
             f'<a href="{section_href(ctx, a["section"])}" style="color:#fff">{esc(a["section"])}</a> · {esc(a["story_type"])}</div>'
             f'<div class="lead-in"><h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
             f'<div class="byl">By {esc(by(a))} · <time datetime="{esc(a["published"])}">{esc(C.pub_label(a))}</time></div>'
             f'<div class="body">{C.paras(a["body"])}</div>'
             + (f'<div class="tags">{tags}</div>' if tags else "") + '</div></article>')
    pager = ""
    if newer or older:
        pager = '<div class="pager" style="margin-top:16px">'
        pager += (f'<a href="{older["url"]}" data-article-id="{older["pid"]}" data-nr-nobadge><span>← Previous report</span>{esc(older["headline"])}</a>'
                  if older else '<div></div>')
        pager += (f'<a class="nx" href="{newer["url"]}" data-article-id="{newer["pid"]}" data-nr-nobadge><span>Next report →</span>{esc(newer["headline"])}</a>'
                  if newer else '<div></div>')
        pager += '</div>'
    rel = ""
    if related:
        rel = ('<div class="label">Related coverage</div><div class="panel list rel">' + "".join(
            f'<div class="item" data-article-id="{r["pid"]}"><span class="cat cat-ports" style="min-width:0">{esc(r["outlet_name"])}</span>'
            f'<div class="info"><h3 class="ihed"><a href="{r["url"]}">{esc(r["headline"])}</a></h3>'
            f'<div class="imeta">{esc(stamp(r["ts"]))} · {esc(r["section"])}</div></div></div>' for r in related) + '</div>')
    return frame(ctx, f'{a["headline"]} | {ctx["outlet"]["name"]}',
                 f'<div class="main"><div>{story}{pager}{rel}</div><aside>{sidebar(ctx, exclude=a["pid"])}</aside></div>',
                 a["section_slug"])


def archive(ctx, q, date, results, days):
    filt = []
    if q:
        filt.append(f'query “{esc(q)}”')
    if date:
        filt.append(f'date {esc(date_label(date))}')
    filt_html = (f'<div class="filter">{len(results)} result{"s" if len(results) != 1 else ""} · {" · ".join(filt)} · '
                 f'<a href="{C.url_archive(ctx)}">Clear filter</a></div>') if filt else ""
    search = (f'<div class="panel"><div class="panel-h"><span>Search the archive</span><span>{len(ctx["articles"])} reports</span></div>'
              f'<form class="search" action="{C.url_archive(ctx)}" method="get" role="search">'
              f'<input type="search" name="q" value="{esc(q)}" placeholder="Vessel, terminal, agency…" aria-label="Search reports">'
              + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "") +
              f'<button type="submit">Search</button></form>{filt_html}</div>')
    groups = C.group_by_day(results)
    if groups:
        listing = '<div class="panel list">' + "".join(
            f'<div class="dayh">{esc(date_label(d))}</div>' + "".join(item(ctx, a) for a in items) for d, items in groups) + '</div>'
    else:
        listing = '<div class="panel"><div class="empty">No reports match. Try a vessel name, agency or place.</div></div>'

    months = []
    for d, n in days:
        if not months or months[-1][0] != d[:7]:
            months.append((d[:7], []))
        months[-1][1].append((d, n))
    idx = ""
    for m, ds in months:
        y, mo = int(m[:4]), int(m[5:7])
        chips = "".join(f'<a href="{C.url_archive(ctx, q=q or None, date=d)}" class="{"on" if d == date else ""}">'
                        f'{int(d[8:10]):02d} {C.MONTHS[mo - 1][:3].upper()} ({n})</a>' for d, n in ds)
        idx += f'<h4>{C.MONTHS[mo - 1]} {y}</h4><div class="chips">{chips}</div>'
    index = (f'<div class="panel"><div class="panel-h"><span>Reports by day</span></div>'
             f'<div class="days">{idx or "<div class=empty>No reports yet.</div>"}</div></div>')
    return frame(ctx, f'Archives | {ctx["outlet"]["name"]}',
                 f'<div class="main"><div>{search}{listing}</div><aside>{index}{port_widget(ctx)}</aside></div>', "archive")


def notfound(ctx):
    latest = ctx["articles"][:6]
    lst = (f'<div class="label">Latest reports</div><div class="panel list">{"".join(item(ctx, a) for a in latest)}</div>'
           if latest else "")
    main = (f'<div class="label">Error 404</div><div class="panel"><div class="empty">REPORT NOT FOUND. The page you requested is '
            f'not available. <a href="{C.url_home(ctx)}">Return to latest reports</a> or '
            f'<a href="{C.url_archive(ctx)}">search the archives</a>.</div></div>{lst}')
    return frame(ctx, f'Not found | {ctx["outlet"]["name"]}',
                 f'<div class="main"><div>{main}</div><aside>{port_widget(ctx)}</aside></div>')


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
