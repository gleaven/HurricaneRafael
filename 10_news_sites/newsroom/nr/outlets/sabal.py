"""Sabal Energy Wire: energy and markets wire. Dense, terminal-flavored layout.
Everything shown comes from visible articles and ctx.status; no prices or invented figures."""
import re

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"

CSS = """
:root{--hbg:#1a1a2e;--green:#22c55e;--amber:#f59e0b;--red:#ef4444;--bg:#f8fafc;--card:#fff;--border:#e2e8f0;
--text:#0f172a;--muted:#64748b;--tbg:#0f172a;--blue:#3b82f6}
body{margin:0;font-family:'Space Grotesk',system-ui,sans-serif;background:var(--bg);color:var(--text);font-size:14px;line-height:1.5}
a{color:inherit}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.container{max-width:1200px;margin:0 auto}
.sub-bar{background:#0f172a;color:#94a3b8;font-size:11px;padding-block:6px;display:flex;flex-wrap:wrap;gap:4px 16px;justify-content:space-between;align-items:center}
.sub-bar b{color:#e2e8f0;font-weight:600}
.sub-bar .clk{color:var(--amber);font-weight:600}
.ticker-wrap{background:var(--tbg);overflow:hidden;padding-block:7px;border-bottom:2px solid var(--amber)}
.ticker-track{display:flex;width:max-content;white-space:nowrap;animation:sbscroll 70s linear infinite}
.ticker-track:hover{animation-play-state:paused}
@keyframes sbscroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker-track{animation:none}}
.ti{display:inline-flex;align-items:center;gap:6px;padding:0 22px;font-size:12px;font-weight:600;color:#e2e8f0;text-decoration:none}
.ti .sym{color:#94a3b8;font-weight:500;letter-spacing:.04em}
.ti.hl{font-weight:500;color:#cbd5e1}
.ti.hl::before{content:"\\25B8";color:var(--amber)}
.s-ok{color:var(--green)}.s-warn{color:var(--amber)}.s-bad{color:var(--red)}
header.mast{background:var(--hbg)}
.hi{display:flex;flex-wrap:wrap;gap:10px 24px;align-items:center;justify-content:space-between;padding-block:14px}
.logo{text-decoration:none;display:block}
.logo-name{font-size:24px;font-weight:700;color:#fff;letter-spacing:-.02em;line-height:1}
.logo-name span{color:var(--green)}
.logo-tag{font-size:10px;font-weight:500;color:#64748b;letter-spacing:.14em;text-transform:uppercase;margin-top:4px}
.hbadge{background:var(--amber);color:#0f172a;font-size:10px;font-weight:700;padding:3px 8px;border-radius:2px;letter-spacing:.08em;margin-left:10px;vertical-align:middle}
nav.secnav{display:flex;flex-wrap:wrap;gap:2px}
nav.secnav a{color:#94a3b8;text-decoration:none;padding:7px 11px;font-size:12px;font-weight:500;border-radius:4px}
nav.secnav a:hover{color:#fff;background:rgba(255,255,255,.08)}
nav.secnav a.active{color:var(--amber)}
.alertbar{background:#fef3c7;border-left:4px solid var(--amber);padding-block:9px;font-size:12px;font-weight:600;color:#92400e}
.alertbar .row{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.alertbar .row+.row{margin-top:4px}
.alertbar a{color:#7c2d12}
.badge{display:inline-block;background:var(--amber);color:#fff;padding:2px 7px;border-radius:2px;font-size:10px;letter-spacing:.06em;font-weight:700;text-transform:uppercase}
.badge.red{background:var(--red)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:24px;padding-block:22px}
@media (max-width:880px){.layout{grid-template-columns:minmax(0,1fr)}}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:18px}
.mc{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:13px 15px;min-width:0}
.mc .lbl{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:6px}
.mc .val{font-size:20px;font-weight:700;line-height:1.15}
.mc .val.sm{font-size:14px;line-height:1.35}
.mc .val a{text-decoration:none}.mc .val a:hover{text-decoration:underline}
.mc .sub{font-size:11px;color:var(--muted);margin-top:5px}
.lead{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:22px;margin-bottom:18px}
.slabel{display:inline-block;background:var(--hbg);color:#fff;font-size:9px;font-weight:700;padding:3px 8px;border-radius:2px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px;text-decoration:none}
.slabel.brk{background:var(--red)}
.lead h1,.story h1{font-size:22px;font-weight:700;line-height:1.22;margin:0 0 8px;text-wrap:balance}
.lead h1 a{text-decoration:none}.lead h1 a:hover{text-decoration:underline}
.dek{font-size:14px;color:#334155;margin:0 0 10px}
.byl{font-size:11px;color:var(--muted);margin-bottom:14px}
.byl span{color:var(--text);font-weight:600}
.lead p,.story .body p{font-size:14px;line-height:1.68;color:#1e293b;margin:0 0 11px}
.dl{font-weight:700;color:var(--hbg)}
.more{font-size:12px;font-weight:700;color:var(--blue);text-decoration:none}
.abox{border:2px solid var(--amber);border-radius:6px;padding:15px;background:#fffbeb;margin-bottom:18px}
.abox .albl{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:#92400e;margin-bottom:8px}
.abox blockquote{margin:0;font-size:14px;line-height:1.6;color:#1a1a2e;font-style:italic}
.abox .asrc{font-size:11px;color:var(--muted);margin-top:8px}
.abox .asrc a{color:#92400e}
.dtw{background:var(--card);border:1px solid var(--border);border-radius:6px;overflow:hidden;margin-bottom:18px}
.dtw h3{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;padding:10px 15px;margin:0;background:var(--hbg);color:#94a3b8;display:flex;justify-content:space-between;gap:8px}
.dtw h3 small{font-weight:500;color:#64748b;letter-spacing:.04em}
.scroll{overflow-x:auto}
table.dt{width:100%;border-collapse:collapse;font-size:12.5px}
table.dt th{background:#1e293b;color:#94a3b8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.06em;padding:7px 13px;text-align:left;white-space:nowrap}
table.dt td{padding:9px 13px;border-bottom:1px solid var(--border);vertical-align:top}
table.dt tr:last-child td{border-bottom:none}
table.dt tbody tr:hover{background:#f1f5f9}
table.dt td.t{white-space:nowrap;color:var(--muted);font-weight:600;font-size:11.5px}
table.dt td.s{white-space:nowrap;font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
table.dt td a{text-decoration:none;font-weight:600}
table.dt td a:hover{text-decoration:underline;color:var(--blue)}
table.dt .ex{display:block;font-weight:400;color:var(--muted);font-size:12px;margin-top:3px}
@media (max-width:560px){table.dt td.s,table.dt th.s{display:none}}
.side .panel{background:var(--card);border:1px solid var(--border);border-radius:6px;margin-bottom:16px;overflow:hidden}
.side .panel h4{margin:0;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;padding:9px 14px;background:var(--hbg);color:#94a3b8}
.side .panel .pb{padding:12px 14px}
.portcode{font-size:22px;font-weight:700;letter-spacing:.02em}
.portdet{font-size:12px;color:#334155;margin:6px 0 0}
.since{font-size:11px;color:var(--muted);margin-top:6px}
ul.tl{list-style:none;margin:0;padding:0;font-size:11.5px}
ul.tl li{display:grid;grid-template-columns:auto 1fr;gap:8px;padding:6px 0;border-top:1px dashed var(--border)}
ul.tl li:first-child{border-top:none}
ul.tl .when{color:var(--muted);white-space:nowrap}
ul.lst{list-style:none;margin:0;padding:0}
ul.lst li{padding:8px 0;border-top:1px solid var(--border);font-size:12.5px;line-height:1.35}
ul.lst li:first-child{border-top:none}
ul.lst a{text-decoration:none;font-weight:600}ul.lst a:hover{text-decoration:underline}
ul.lst .m{display:block;font-size:10.5px;color:var(--muted);margin-top:2px;font-weight:500}
.seccount{display:flex;justify-content:space-between;font-size:12px;padding:6px 0;border-top:1px solid var(--border)}
.seccount:first-child{border-top:none}
.seccount a{text-decoration:none;font-weight:600}
.empty{background:var(--card);border:1px dashed #cbd5e1;border-radius:6px;padding:26px;color:#334155}
.empty h2{margin:0 0 6px;font-size:16px}
.ph{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:6px;margin-bottom:14px}
.ph h1{font-size:22px;margin:0}
.ph .cnt{font-size:12px;color:var(--muted)}
.story{background:var(--card);border:1px solid var(--border);border-radius:6px;padding:24px;margin-bottom:18px}
.story h1{font-size:26px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px}
.tag{font-size:10.5px;font-weight:600;background:#eef2f7;color:#334155;border:1px solid var(--border);padding:3px 8px;border-radius:999px}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}
.pager a{display:block;background:var(--card);border:1px solid var(--border);border-radius:6px;padding:11px 13px;text-decoration:none;font-size:12.5px;font-weight:600;min-width:0}
.pager small{display:block;font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:3px}
.pager .nx{text-align:right}
@media (max-width:560px){.pager{grid-template-columns:1fr}.pager .nx{text-align:left}}
form.srch{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
form.srch input{flex:1;min-width:0;padding:9px 11px;border:1px solid #cbd5e1;border-radius:4px;font:inherit;background:#fff;color:var(--text)}
form.srch button{padding:9px 16px;border:0;border-radius:4px;background:var(--hbg);color:#fff;font:600 12px 'Space Grotesk',system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;cursor:pointer}
.filter{font-size:12px;color:#334155;margin-bottom:12px}
.filter a{color:var(--blue)}
.days{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
.days a{font-size:11px;font-weight:600;text-decoration:none;background:var(--card);border:1px solid var(--border);border-radius:3px;padding:4px 8px;color:#334155}
.days a.on{background:var(--hbg);color:#fff;border-color:var(--hbg)}
.days a small{color:var(--muted);font-weight:500}
.days a.on small{color:#94a3b8}
.dayhead{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:18px 0 8px}
footer.ft{background:#0f172a;color:#64748b;font-size:11px;padding-block:22px;margin-top:20px}
footer.ft b{color:#cbd5e1}
footer.ft .row{display:flex;flex-wrap:wrap;gap:6px 18px;justify-content:space-between}
"""

LOADINGS = {"OPEN": ("Normal", "s-ok"), "X-RAY": ("Winding down", "s-warn"), "YANKEE": ("Halted", "s-bad"),
            "ZULU": ("Halted", "s-bad"), "CLOSED": ("Halted", "s-bad"), "RESTRICTED": ("Limited", "s-warn")}
PORT_CLS = {"OPEN": "s-ok", "X-RAY": "s-warn", "RESTRICTED": "s-warn"}

_ABBR = {"u.s", "gov", "sen", "rep", "lt", "cmdr", "col", "gen", "capt", "sgt", "jan", "feb", "aug", "sept", "sep",
         "oct", "nov", "dec", "mr", "mrs", "ms", "dr", "st", "no", "inc", "corp", "co", "jr", "sr", "a.m", "p.m", "vs"}


# ------------------------------------------------------------------ helpers
def split_dateline(p):
    m = re.match(r"^([A-Z][A-Z .,'\-]+(?:,\s*[A-Za-z.]+)?\s*\([^)]*\))\s*[—–-]+\s*(.*)$", p)
    if m:
        return m.group(1), m.group(2)
    return None, p


def first_sentence(text):
    for m in re.finditer(r"[.!?][\"”’)]?\s+(?=[\"“A-Z0-9])", text):
        before = text[:m.start()].split()[-1].lower().strip("\"“(") if text[:m.start()].split() else ""
        if before in _ABBR or (len(before) <= 2 and before.isalpha()) or re.fullmatch(r"([a-z]\.)+[a-z]", before):
            continue
        return text[:m.end()].strip()
    return text.strip()


def body_html(a):
    out = []
    for i, p in enumerate(a["body"]):
        if i == 0:
            dl, rest = split_dateline(p)
            if dl:
                out.append(f'<p><span class="dl">{esc(dl)}</span> — {esc(rest)}</p>')
                continue
        out.append(f"<p>{esc(p)}</p>")
    return "".join(out)


def loadings(ctx):
    p = ctx["status"]["port"]
    return LOADINGS.get(p["code"], ("—", "")) if p else ("—", "")


def is_hot(ctx, a, hours):
    return a["story_type"] == "breaking" and ctx["now"] - a["ts"] <= hours * 3600


def time_cell(ctx, a):
    return f'{esc(C.fmt_date_short(a["ts"]))} · {esc(C.fmt_time_ap(a["ts"], tz=False))}'


# ------------------------------------------------------------------ frame
def ticker(ctx):
    load, lcls = loadings(ctx)
    p = ctx["status"]["port"]
    items = [f'<span class="ti" data-nr-nobadge><span class="sym">CC CRUDE LOADINGS:</span><span class="{lcls}">{esc(load.upper())}</span></span>',
             f'<span class="ti" data-nr-nobadge><span class="sym">SHIP CHANNEL:</span><span class="{PORT_CLS.get(p["code"], "s-bad") if p else ""}">{esc(p["label"].upper()) if p else "—"}</span></span>']
    for a in ctx["articles"][:8]:
        items.append(f'<a class="ti hl" href="{a["url"]}" data-article-id="{a["pid"]}" data-nr-nobadge>'
                     f'<span class="sym">{esc(a["section"].upper())}</span> {esc(a["headline"])}</a>')
    if len(items) == 2:
        items.append('<span class="ti hl" data-nr-nobadge>Desk monitoring Gulf Coast crude flows</span>')
    track = "".join(items)
    return f'<div class="ticker-wrap" aria-label="Market ticker"><div class="ticker-track">{track}{track}</div></div>'


def alertbar(ctx):
    rows = []
    hot = [a for a in ctx["articles"] if is_hot(ctx, a, 6)]
    if hot:
        a = hot[0]
        rows.append(f'<div class="row" data-article-id="{a["pid"]}" data-nr-nobadge><span class="badge red">Breaking</span>'
                    f'<a href="{a["url"]}">{esc(a["headline"])}</a></div>')
    for al in ctx["status"]["alerts"]:
        rows.append(f'<div class="row"><span class="badge">Advisory</span><span>{esc(al["text"])}</span></div>')
    if not rows:
        return ""
    return f'<div class="alertbar"><div class="container gut">{"".join(rows)}</div></div>'


def frame(ctx, title, inner, active=None):
    o = ctx["outlet"]
    nav = [f'<a href="{C.url_home(ctx)}"{" class=active" if active == "_home" else ""}>Latest</a>']
    for s in o["sections"]:
        nav.append(f'<a href="{C.url_section(ctx, s["slug"])}"{" class=active" if active == s["slug"] else ""}>{esc(s["name"])}</a>')
    nav.append(f'<a href="{C.url_archive(ctx)}"{" class=active" if active == "_archive" else ""}>Archive</a>')
    return (C.head(ctx, title, FONTS, CSS) +
            '<div id="nr-root">'
            f'<div class="sub-bar gut"><span><b>SABAL ENERGY WIRE</b> · Professional Edition · Energy &amp; markets intelligence</span>'
            f'<span>{C.clock_span(ctx, "date-long")} · <span class="clk">{C.clock_span(ctx, "time-24")}</span></span></div>'
            + ticker(ctx) +
            f'<header class="mast"><div class="container gut hi"><a class="logo" href="{C.url_home(ctx)}">'
            f'<div class="logo-name">Sabal <span>Energy</span> Wire<span class="hbadge">ENERGY &amp; MARKETS</span></div>'
            f'<div class="logo-tag">Crude · Refining · Power · Markets</div></a>'
            f'<nav class="secnav" aria-label="Sections">{"".join(nav)}</nav></div></header>'
            + alertbar(ctx) +
            f'<div class="container gut">{inner}</div>'
            f'<footer class="ft"><div class="container gut row"><span><b>Sabal Energy Wire</b> · {esc(o["kind"])} · '
            f'<a href="{C.url_rss(ctx)}" style="color:#94a3b8">RSS</a></span>'
            '<span>Professional energy market intelligence. All companies, people and incidents are fictional.</span></div></footer>'
            '</div>' + C.foot(ctx))


def side(ctx, show_sections=True):
    out = []
    p = ctx["status"]["port"]
    if p:
        hist = ctx["status"]["port_history"][-6:][::-1]
        tl = "".join(f'<li><span class="when">{esc(C.fmt_date_short(h["ts"]))}</span><span>{esc(h["label"])}</span></li>' for h in hist)
        out.append(f'<div class="panel"><h4>Port of Corpus Christi</h4><div class="pb">'
                   f'<div class="portcode {PORT_CLS.get(p["code"], "s-bad")}">{esc(p["label"])}</div>'
                   f'<p class="portdet">{esc(p["detail"])}</p><div class="since">Since {esc(C.fmt_dt_ap(p["ts"]))}</div></div>'
                   f'<div class="pb" style="padding-top:0"><ul class="tl">{tl}</ul></div></div>')
    if show_sections and ctx["articles"]:
        rows = []
        for s in ctx["outlet"]["sections"]:
            n = sum(1 for a in ctx["articles"] if a["section"] == s["name"])
            if n:
                rows.append(f'<div class="seccount"><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a><span>{n}</span></div>')
        if rows:
            out.append(f'<div class="panel"><h4>Desk coverage</h4><div class="pb">{"".join(rows)}</div></div>')
    recent = ctx["articles"][:6]
    if recent:
        li = "".join(f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                     f'<span class="m">{esc(a["section"])} · {C.ago_span(ctx, a)}</span></li>' for a in recent)
        out.append(f'<div class="panel"><h4>Latest dispatches</h4><div class="pb"><ul class="lst">{li}</ul></div></div>')
    return '<aside class="side">' + "".join(out) + "</aside>"


def table(ctx, items, title, note="", excerpts=False):
    rows = []
    for a in items:
        ex = f'<span class="ex">{esc(C.excerpt(a, 26))}</span>' if excerpts else ""
        badge = '<span class="badge red" style="margin-right:6px">Breaking</span>' if is_hot(ctx, a, 6) else ""
        rows.append(f'<tr data-article-id="{a["pid"]}"><td class="t">{time_cell(ctx, a)}</td>'
                    f'<td class="s">{esc(a["section"])}</td><td>{badge}<a href="{a["url"]}">{esc(a["headline"])}</a>{ex}</td></tr>')
    return (f'<div class="dtw"><h3><span>{esc(title)}</span><small>{esc(note)}</small></h3><div class="scroll"><table class="dt">'
            '<thead><tr><th>Filed (CT)</th><th class="s">Desk</th><th>Headline</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def empty_box(title, text):
    return f'<div class="empty"><h2>{esc(title)}</h2><p>{esc(text)}</p></div>'


# ------------------------------------------------------------------ views
def home(ctx):
    arts = ctx["articles"]
    if not arts:
        main = empty_box("No dispatches filed yet",
                         "The Sabal desk is monitoring Gulf Coast crude loadings, refining and power markets. "
                         "Dispatches will appear here as they are filed.")
        return frame(ctx, "Sabal Energy Wire", f'<div class="layout"><div>{main}</div>{side(ctx)}</div>', "_home")

    p = ctx["status"]["port"]
    load, lcls = loadings(ctx)
    crude = next((a for a in arts if a["section"] == "Crude"), None)
    week = sum(1 for a in arts if ctx["now"] - a["ts"] <= 7 * 86400)
    metrics = [
        f'<div class="mc"><div class="lbl">Port status · Corpus Christi</div><div class="val {PORT_CLS.get(p["code"], "s-bad") if p else ""}">'
        f'{esc(p["label"]) if p else "—"}</div><div class="sub">Crude loadings: <b class="{lcls}">{esc(load)}</b></div></div>',
        (f'<div class="mc" data-article-id="{crude["pid"]}" data-nr-nobadge><div class="lbl">Latest crude dispatch</div>'
         f'<div class="val sm"><a href="{crude["url"]}">{esc(crude["headline"])}</a></div><div class="sub">{C.ago_span(ctx, crude)}</div></div>')
        if crude else '<div class="mc"><div class="lbl">Latest crude dispatch</div><div class="val sm">None filed yet</div></div>',
        f'<div class="mc"><div class="lbl">Dispatches · last 7 days</div><div class="val">{week}</div>'
        f'<div class="sub">{len(arts)} on file</div></div>',
    ]
    hot = [a for a in arts if a["story_type"] == "breaking" and ctx["now"] - a["ts"] <= 86400]
    lead = hot[0] if hot else arts[0]
    paras = body_html(dict(lead, body=lead["body"][:2]))
    brk = " brk" if lead["story_type"] == "breaking" else ""
    lead_html = (f'<article class="lead" data-article-id="{lead["pid"]}">'
                 f'<a class="slabel{brk}" href="{C.url_section(ctx, lead["section_slug"])}">{esc("Breaking · " if brk else "")}{esc(lead["section"])}</a>'
                 f'<h1><a href="{lead["url"]}">{esc(lead["headline"])}</a></h1>'
                 f'<p class="dek">{esc(lead["summary"])}</p>'
                 f'<div class="byl">By <span>{esc(C.byline(lead))}</span> · {esc(C.pub_label(lead))} · {C.ago_span(ctx, lead)}</div>'
                 f'{paras}<a class="more" href="{lead["url"]}">Full dispatch →</a></article>')
    analysis = next((a for a in arts if a["story_type"] == "analysis"), None)
    note = ""
    if analysis and analysis["body"]:
        _, txt = split_dateline(analysis["body"][0])
        note = (f'<div class="abox" data-article-id="{analysis["pid"]}" data-nr-nobadge><div class="albl">Desk note</div>'
                f'<blockquote>“{esc(first_sentence(txt))}”</blockquote>'
                f'<div class="asrc">From <a href="{analysis["url"]}">{esc(analysis["headline"])}</a>, {esc(C.fmt_date_ap(analysis["ts"]))}</div></div>')
    rest = [a for a in arts if a["pid"] != lead["pid"]][:15]
    tbl = table(ctx, rest, "Wire log", f"{len(arts)} dispatches") if rest else ""
    main = f'<div class="metrics">{"".join(metrics)}</div>{lead_html}{note}{tbl}'
    return frame(ctx, "Sabal Energy Wire | Energy & Markets", f'<div class="layout"><div>{main}</div>{side(ctx)}</div>', "_home")


def section(ctx, sec, items):
    if items:
        main = table(ctx, items, sec["name"], f"{len(items)} dispatches", excerpts=True)
    else:
        main = empty_box(f"No {sec['name']} dispatches yet", "Nothing has been filed to this desk so far.")
    head = f'<div class="ph"><h1>{esc(sec["name"])}</h1><span class="cnt">{len(items)} on file</span></div>'
    return frame(ctx, f'{sec["name"]} | Sabal Energy Wire',
                 f'<div class="layout"><div>{head}{main}</div>{side(ctx)}</div>', sec["slug"])


def article(ctx, a, related, newer, older):
    tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a["storylines"])
    brk = " brk" if a["story_type"] == "breaking" else ""
    story = (f'<article class="story" data-article-id="{a["pid"]}">'
             f'<a class="slabel{brk}" href="{C.url_section(ctx, a["section_slug"])}">{esc(a["section"])}</a>'
             f'<h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
             f'<div class="byl">By <span>{esc(C.byline(a))}</span>, Sabal Energy Wire · {esc(C.pub_label(a))} · {C.read_minutes(a)} min read</div>'
             f'<div class="body">{body_html(a)}</div>'
             + (f'<div class="tags">{tags}</div>' if tags else "") + "</article>")
    pager = ""
    if newer or older:
        pager = '<div class="pager">'
        pager += (f'<a href="{older["url"]}" data-article-id="{older["pid"]}" data-nr-nobadge><small>← Earlier dispatch</small>{esc(older["headline"])}</a>'
                  if older else "<span></span>")
        pager += (f'<a class="nx" href="{newer["url"]}" data-article-id="{newer["pid"]}" data-nr-nobadge><small>Later dispatch →</small>{esc(newer["headline"])}</a>'
                  if newer else "<span></span>")
        pager += "</div>"
    rel = ""
    if related:
        li = "".join(f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(r["headline"])}</a>'
                     f'<span class="m">{esc(r["outlet_name"])} · {esc(C.fmt_date_ap(r["ts"]))}</span></li>' for r in related)
        rel = f'<div class="dtw"><h3><span>Related coverage</span><small>across outlets</small></h3><div style="padding:4px 15px 10px"><ul class="lst">{li}</ul></div></div>'
    return frame(ctx, f'{a["headline"]} | Sabal Energy Wire',
                 f'<div class="layout"><div>{story}{pager}{rel}</div>{side(ctx, show_sections=False)}</div>', a["section_slug"])


def archive(ctx, q, date, results, days):
    form = (f'<form class="srch" action="{C.url_archive(ctx)}" method="get" role="search">'
            f'<input type="search" name="q" value="{esc(q)}" placeholder="Search dispatches: terminal, exports, CISA…" aria-label="Search dispatches">'
            + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "") +
            '<button type="submit">Search</button></form>')
    bits = []
    if q:
        bits.append(f'matching “{esc(q)}”')
    if date:
        bits.append(f"filed {esc(C.fmt_date_long(results[0]['ts'])) if results else esc(date)}")
    filt = (f'<div class="filter">{len(results)} dispatch{"es" if len(results) != 1 else ""} {" ".join(bits)} · '
            f'<a href="{C.url_archive(ctx)}">Clear filters</a></div>') if bits else f'<div class="filter">{len(results)} dispatches on file</div>'
    chips = []
    for d, n in days:
        y, m, dd = d.split("-")
        lab = f"{C.AP_MONTHS[int(m) - 1]} {int(dd)}"
        chips.append(f'<a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""}>{lab} <small>{n}</small></a>')
    dayidx = f'<div class="days" aria-label="Days with dispatches">{"".join(chips)}</div>' if chips else ""
    groups = []
    for d, items in C.group_by_day(results):
        groups.append(f'<div class="dayhead">{esc(C.fmt_date_long(items[0]["ts"]))}</div>' +
                      table(ctx, items, "Dispatches", f"{len(items)}", excerpts=True))
    body = "".join(groups) or empty_box("No dispatches found", "Try a different search term or clear the filters.")
    head = '<div class="ph"><h1>Archive</h1><span class="cnt">Search every dispatch on file</span></div>'
    return frame(ctx, "Archive | Sabal Energy Wire",
                 f'<div class="layout"><div>{head}{form}{filt}{dayidx}{body}</div>{side(ctx)}</div>', "_archive")


def notfound(ctx):
    main = empty_box("Dispatch not available",
                     "The page you requested is not on the Sabal Energy Wire. Check the address or return to the latest dispatches.")
    return frame(ctx, "Not found | Sabal Energy Wire",
                 f'<div class="layout"><div>{main}<p style="margin-top:14px"><a class="more" href="{C.url_home(ctx)}">← Latest dispatches</a></p></div>{side(ctx)}</div>')


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
