"""Harborline 6 News: local TV station website template (see nr/common.py for the contract)."""
import datetime as dt

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"

CSS = """
body,h1,h2,h3,h4,p,ul,ol{margin:0;padding:0}
:root{--hdr:#0d1b2e;--red:#c0392b;--blue:#2980b9;--bg:#f0f2f5;--white:#fff;--text:#1a1a1a;--muted:#666;--border:#dde1e7}
body{background:var(--bg);color:var(--text);font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;font-size:15px;line-height:1.5;overflow-x:hidden}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.util-bar{background:#1a2740;color:#a8b8cc;font-size:11.5px;padding-block:5px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px 12px}
.util-bar a{color:#7aa8d0}
.breaking-flash{background:var(--red);color:#fff;padding:2px 8px;border-radius:2px;font-weight:700;font-size:10px;letter-spacing:.08em;text-transform:uppercase;animation:flash 1.4s ease-in-out infinite;margin-left:6px}
@keyframes flash{0%,100%{opacity:1}50%{opacity:.55}}
header.top{background:var(--hdr);padding-block:12px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.logo{display:flex;align-items:flex-end;gap:6px;color:#fff}
.logo:hover{text-decoration:none}
.logo-h6{font-size:clamp(24px,4vw,38px);font-weight:900;color:#fff;letter-spacing:-.01em;text-transform:uppercase;line-height:1}
.logo-6{color:var(--red)}
.logo-news{font-size:clamp(11px,1.5vw,15px);font-weight:800;color:#fff;text-transform:uppercase;letter-spacing:.18em;border-bottom:3px solid var(--red);padding-bottom:2px}
.header-right{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.live-btn{display:flex;align-items:center;gap:7px;background:var(--red);color:#fff;padding:7px 14px;border-radius:3px;font-weight:800;font-size:12px;letter-spacing:.06em;text-transform:uppercase}
.live-dot{width:8px;height:8px;border-radius:50%;background:#fff;animation:pulse 1.2s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.4);opacity:.6}}
.live-btn.off{background:#3a4658;color:#d4dbe5}
.live-btn.off .live-dot{background:#8a96a8;animation:none}
.hdr-search{display:flex}
.hdr-search input{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.2);color:#fff;padding:7px 12px;border-radius:3px;font:13px Inter,system-ui,sans-serif;width:170px;max-width:46vw}
.hdr-search input::placeholder{color:rgba(255,255,255,.5)}
.subnav{background:#162236;border-bottom:2px solid var(--red)}
.subnav ul{list-style:none;display:flex;overflow-x:auto;scrollbar-width:none}
.subnav a{display:block;padding:10px 14px;font-size:12px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:#9ab0cc;border-bottom:3px solid transparent;white-space:nowrap}
.subnav a:hover,.subnav a.on{color:#fff;border-bottom-color:var(--red);text-decoration:none}
.ticker-wrap{background:var(--red);overflow:hidden;display:flex;align-items:stretch}
.ticker-label{background:#8b1515;color:#fff;font-weight:800;font-size:10px;letter-spacing:.12em;text-transform:uppercase;padding:8px 14px;white-space:nowrap;flex-shrink:0;display:flex;align-items:center}
.ticker-track{overflow:hidden;flex:1;min-width:0;display:flex;align-items:center}
.ticker-text{display:inline-flex;gap:34px;white-space:nowrap;animation:scroll-left 60s linear infinite;padding-left:100%}
.ticker-text a{color:#fff;font-size:12.5px;font-weight:600}
.ticker-text a::before{content:'●';font-size:8px;margin-right:10px;opacity:.7;vertical-align:middle}
@keyframes scroll-left{0%{transform:translateX(0)}100%{transform:translateX(-100%)}}
.alert-bar{background:#fff4d6;border-bottom:1px solid #f0d58a;color:#4a3a05;font-size:13.5px;padding-block:8px}
.alert-bar.sev{background:#7f1d1d;border-bottom-color:#5c1212;color:#fff}
.alert-bar strong{text-transform:uppercase;letter-spacing:.06em;font-size:11px;margin-right:8px}
.alert-bar div+div{margin-top:3px}
.breaking-banner{background:linear-gradient(90deg,#9e1f14,var(--red));color:#fff;padding-block:14px}
.breaking-banner .inner{max-width:1180px;margin:0 auto;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.bb-label{background:#fff;color:var(--red);font-weight:900;font-size:12px;letter-spacing:.1em;text-transform:uppercase;padding:4px 10px;border-radius:2px}
.breaking-banner a{color:#fff;font-weight:800;font-size:clamp(16px,2.2vw,21px);line-height:1.25}
.main{max-width:1180px;margin:0 auto;padding-block:20px}
.two-col{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:24px}
@media(max-width:900px){.two-col{grid-template-columns:minmax(0,1fr)}}
.hero-card{background:var(--white);border-radius:4px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);margin-bottom:24px}
.video-thumb{width:100%;aspect-ratio:16/9;max-width:100%;background:radial-gradient(ellipse at 30% 30%,#2c4f7c 0%,#13253d 55%,#0a1320 100%);position:relative;display:flex;align-items:center;justify-content:center}
.video-thumb::before{content:'';position:absolute;inset:0;background:repeating-linear-gradient(0deg,rgba(255,255,255,.025) 0 2px,transparent 2px 4px)}
.play{width:74px;height:74px;border-radius:50%;background:rgba(192,57,43,.92);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 18px rgba(0,0,0,.4);position:relative}
.play::after{content:'';border-left:24px solid #fff;border-top:15px solid transparent;border-bottom:15px solid transparent;margin-left:6px}
.thumb-tag{position:absolute;top:10px;left:10px;background:var(--red);color:#fff;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;padding:3px 8px;border-radius:2px}
.thumb-tag.dark{background:#0d1b2e}
.thumb-len{position:absolute;bottom:10px;right:10px;background:rgba(0,0,0,.75);color:#fff;font-size:11px;font-weight:600;padding:2px 7px;border-radius:2px}
.thumb-brand{position:absolute;bottom:10px;left:12px;color:rgba(255,255,255,.75);font-size:11px;font-weight:900;letter-spacing:.1em}
.hero-body{padding:18px 20px 20px}
.cat{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--red);margin-bottom:7px}
.hero-card h1{font-size:clamp(20px,2.6vw,28px);font-weight:800;line-height:1.2;color:#0d1b2e;margin-bottom:10px;text-wrap:balance}
.hero-card h1 a{color:inherit}
.byl{font-size:12px;color:var(--muted);margin-bottom:12px}
.byl strong{color:var(--text)}
.hero-card p{font-size:14.5px;color:#3a3a3a;line-height:1.65;margin-bottom:10px}
.learned{display:inline-block;background:#0d1b2e;color:#fff;font-size:9.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;padding:3px 8px;border-radius:2px;margin-bottom:10px}
.section-label{font-size:11.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--red);margin:4px 0 14px;padding-left:10px;border-left:3px solid var(--red)}
.card-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:24px}
@media(max-width:700px){.card-row{grid-template-columns:minmax(0,1fr)}}
.news-card{background:#fff;border-radius:4px;overflow:hidden;box-shadow:0 1px 5px rgba(0,0,0,.07);transition:box-shadow .2s;min-width:0}
.news-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.12)}
.news-card .video-thumb .play{width:44px;height:44px}
.news-card .video-thumb .play::after{border-left-width:15px;border-top-width:9px;border-bottom-width:9px;margin-left:4px}
.card-body{padding:12px 14px 14px}
.news-card h3{font-size:15px;font-weight:700;line-height:1.3;color:#0d1b2e;margin-bottom:7px}
.news-card h3 a{color:inherit}.news-card h3 a:hover{color:var(--red);text-decoration:none}
.card-meta{font-size:11.5px;color:var(--muted)}
.latest-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
@media(max-width:600px){.latest-grid{grid-template-columns:minmax(0,1fr)}}
.latest-item{background:#fff;border-radius:4px;padding:14px 16px;display:flex;gap:12px;box-shadow:0 1px 4px rgba(0,0,0,.07);min-width:0}
.latest-num{font-size:22px;font-weight:900;color:#cfd5de;line-height:1;min-width:28px}
.latest-text{min-width:0}
.latest-text h4{font-size:14px;font-weight:700;color:#0d1b2e;line-height:1.3;margin-bottom:4px}
.latest-text h4 a{color:inherit}.latest-text h4 a:hover{color:var(--red);text-decoration:none}
.meta{font-size:11.5px;color:var(--muted)}
.sidebar{min-width:0}
.sidebar>*{margin-bottom:20px}
.wx-card{background:#0d1b2e;border-radius:4px;padding:16px;color:#fff}
.wx-city{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#7aa8d0;margin-bottom:6px;display:flex;justify-content:space-between;gap:8px}
.wx-head{font-size:19px;font-weight:800;margin-bottom:10px}
.wx-alert{border-top:1px solid rgba(255,255,255,.12);padding:10px 0}
.wx-alert:first-of-type{border-top:0}
.lvl{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;padding:2px 7px;border-radius:2px;margin-bottom:5px;background:#2c4060;color:#cfe0f2}
.lvl.emergency{background:#e74c3c;color:#fff}.lvl.warning{background:#e67e22;color:#fff}.lvl.watch{background:#f1c40f;color:#1a1a1a}
.wx-alert p{font-size:13px;color:#dbe6f2;line-height:1.45}
.wx-alert .since{font-size:11px;color:#7aa8d0;margin-top:3px}
.wx-calm{font-size:13px;color:#a0b8cc}
.wx-port{border-top:1px solid rgba(255,255,255,.12);padding-top:10px;margin-top:4px;font-size:12px;color:#a0b8cc}
.wx-port strong{color:#fff}
.tip-box{background:#fff;border-radius:4px;padding:14px 16px;box-shadow:0 1px 4px rgba(0,0,0,.07);border-top:4px solid var(--red)}
.tip-box h4{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#0d1b2e;margin-bottom:10px}
.tip-box h5{font-size:15px;line-height:1.3;margin:0 0 6px}
.tip-box h5 a{color:#0d1b2e}
.tip-box p{font-size:13px;color:#444;margin-bottom:8px}
.tip-box ul{list-style:none}
.tip-box li{padding:7px 0;border-bottom:1px solid var(--border);font-size:13px}
.tip-box li:last-child{border-bottom:0}
.tip-box li a{color:#0d1b2e;font-weight:600}
.ad-side{background:#e8ecf0;border:1px dashed #c0c8d0;text-align:center;padding:36px 12px;font-size:10px;color:#a0a0a0;letter-spacing:.1em;text-transform:uppercase;border-radius:4px}
.empty{background:#fff;border-radius:4px;padding:40px 24px;text-align:center;box-shadow:0 1px 5px rgba(0,0,0,.07)}
.empty h2{font-size:22px;font-weight:800;color:#0d1b2e;margin-bottom:6px}
.empty p{color:var(--muted)}
.page-h{font-size:clamp(24px,4vw,34px);font-weight:900;color:#0d1b2e;text-transform:uppercase;letter-spacing:-.01em;margin-bottom:4px}
.page-sub{font-size:13px;color:var(--muted);margin-bottom:18px}
.story{background:#fff;border-radius:4px;box-shadow:0 1px 5px rgba(0,0,0,.07);overflow:hidden;min-width:0}
.story-in{padding:22px clamp(16px,4vw,32px) 28px}
.story h1{font-size:clamp(24px,3.6vw,36px);font-weight:900;line-height:1.15;color:#0d1b2e;margin-bottom:12px;text-wrap:balance}
.story .dek{font-size:17px;color:#444;line-height:1.5;margin-bottom:14px}
.story .body p{font-size:16.5px;line-height:1.75;margin-bottom:16px;color:#222}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
.tags span{background:#eef2f7;color:#0d1b2e;font-size:12px;font-weight:600;padding:4px 10px;border-radius:12px}
.prevnext{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:22px;border-top:1px solid var(--border);padding-top:14px}
.prevnext div{min-width:0}.prevnext .r{text-align:right}
.prevnext small{display:block;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:var(--red);margin-bottom:3px}
.prevnext a{color:#0d1b2e;font-weight:700;font-size:14px}
.src{display:block;font-size:10px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--red)}
.search-big{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.search-big input{flex:1;min-width:0;padding:11px 14px;border:1px solid #c8d0da;border-radius:4px;font:15px Inter,system-ui,sans-serif;background:#fff}
.search-big button{padding:11px 20px;border:0;border-radius:4px;background:var(--red);color:#fff;font:800 13px Inter,system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em;cursor:pointer}
.filter{background:#fff;border-left:3px solid var(--blue);padding:9px 14px;font-size:13px;margin-bottom:14px;border-radius:2px}
.day-h{font-size:12px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#0d1b2e;margin:22px 0 8px;padding-bottom:5px;border-bottom:2px solid var(--red)}
.arch{list-style:none;display:grid;gap:8px}
.arch li{background:#fff;padding:11px 14px;border-radius:4px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.arch a{color:#0d1b2e;font-weight:700}
.days h5{font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;color:#7aa8d0;margin:10px 0 6px}
.days ul{list-style:none;display:flex;flex-wrap:wrap;gap:4px}
.days a{display:inline-block;min-width:30px;text-align:center;font-size:12px;padding:4px 6px;border-radius:3px;background:#1a2a40;color:#cfe0f2}
.days a.on{background:var(--red);color:#fff}
footer.site{background:var(--hdr);color:#8aaccc;font-size:12px;padding-block:28px;margin-top:32px}
.footer-inner{max-width:1180px;margin:0 auto;display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:24px}
@media(max-width:640px){.footer-inner{grid-template-columns:minmax(0,1fr)}}
.footer-brand{font-size:22px;font-weight:900;color:#fff;text-transform:uppercase;margin-bottom:8px}
.footer-brand span{color:var(--red)}
footer.site h4{font-size:10px;font-weight:800;letter-spacing:.15em;text-transform:uppercase;color:#5a8aaa;margin-bottom:10px}
footer.site ul{list-style:none}footer.site li{margin-bottom:5px}footer.site a{color:#8aaccc}
.footer-bottom{max-width:1180px;margin:18px auto 0;padding-top:14px;border-top:1px solid rgba(255,255,255,.08);font-size:11px;color:#5a7a98}
"""

LEVEL = {"emergency": "Emergency", "warning": "Warning", "watch": "Watch", "advisory": "Advisory"}


# ------------------------------------------------------------------ helpers
def _breaking(ctx, hours):
    return [a for a in ctx["articles"] if C.is_breaking(a) and ctx["now"] - a["ts"] <= hours * 3600]


def _learned(a):
    return any("harborline 6 has learned" in p.lower() for p in a["body"])


def _tag(a):
    if C.is_breaking(a):
        return '<span class="thumb-tag">Breaking</span>'
    if _learned(a):
        return '<span class="thumb-tag dark">Harborline 6 has learned</span>'
    return ""


def _thumb(a, brand=True):
    return (f'<div class="video-thumb" aria-hidden="true">{_tag(a)}<span class="play"></span>'
            + ('<span class="thumb-brand">HARBORLINE 6</span>' if brand else "")
            + f'<span class="thumb-len">{C.read_minutes(a)} min read</span></div>')


def _cat(a):
    return "Breaking" if C.is_breaking(a) and a["section"] != "Breaking" else a["section"]


def _card(ctx, a):
    return (f'<article class="news-card" data-article-id="{a["pid"]}"><a href="{a["url"]}" tabindex="-1">{_thumb(a, False)}</a>'
            f'<div class="card-body"><div class="cat">{esc(_cat(a))}</div>'
            f'<h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'<div class="card-meta">{C.ago_span(ctx, a)}{(" · " + esc(C.byline(a))) if a["authors"] else ""}</div></div></article>')


def _latest_item(ctx, a, n):
    return (f'<div class="latest-item" data-article-id="{a["pid"]}"><div class="latest-num">{n}</div>'
            f'<div class="latest-text"><h4><a href="{a["url"]}">{esc(a["headline"])}</a></h4>'
            f'<div class="meta">{esc(_cat(a))} · {C.ago_span(ctx, a)}</div></div></div>')


def _day_label(day_str):
    d = dt.date.fromisoformat(day_str)
    return f"{C.DAYS[d.weekday()]}, {C.MONTHS[d.month - 1]} {d.day}, {d.year}"


def _alerts_widget(ctx):
    st = ctx["status"]
    alerts = st.get("alerts") or []
    port = st.get("port")
    rows = "".join(f'<div class="wx-alert"><span class="lvl {esc(a["level"])}">{esc(LEVEL.get(a["level"], a["level"]))}</span>'
                   f'<p>{esc(a["text"])}</p><div class="since">Issued {esc(C.fmt_dt_ap(a["since"]))}</div></div>' for a in alerts)
    if not rows:
        rows = '<p class="wx-calm">No active weather or emergency alerts for the Coastal Bend right now.</p>'
    port_html = ""
    if port and port.get("code") != "OPEN":
        port_html = f'<div class="wx-port">Port of Corpus Christi: <strong>{esc(port["label"])}</strong><br>{esc(port["detail"])}</div>'
    return (f'<div class="wx-card"><div class="wx-city"><span>Corpus Christi</span>{C.clock_span(ctx, "time-ap")}</div>'
            f'<div class="wx-head">Weather &amp; Alerts</div>{rows}{port_html}</div>')


def _know_box(ctx):
    exp = next((a for a in ctx["articles"] if a["story_type"] == "explainer"), None)
    if not exp:
        return ""
    return (f'<div class="tip-box" data-article-id="{exp["pid"]}"><h4>What you need to know</h4>'
            f'<h5><a href="{exp["url"]}">{esc(exp["headline"])}</a></h5><p>{esc(C.excerpt(exp, 32))}</p>'
            f'<div class="meta">{C.ago_span(ctx, exp)}</div></div>')


def _sidebar(ctx, extra=""):
    recent = "".join(f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                     f'<div class="meta">{C.ago_span(ctx, a)}</div></li>' for a in ctx["articles"][:6])
    recent_box = f'<div class="tip-box"><h4>Latest headlines</h4><ul>{recent}</ul></div>' if recent and not extra else ""
    return (f'<aside class="sidebar">{_alerts_widget(ctx)}{extra}{_know_box(ctx)}{recent_box}'
            f'<div class="ad-side">Advertisement</div></aside>')


def _frame(ctx, title, inner, active=None, banner=True):
    o = ctx["outlet"]
    bc = ctx["status"].get("broadcast")
    off = bc and bc.get("status") == "off-air"
    live = ('<span class="live-btn off" title="Transmitter off the air"><span class="live-dot"></span>Off air · Web updates continue</span>'
            if off else '<span class="live-btn"><span class="live-dot"></span>Live</span>')
    brk6 = _breaking(ctx, 6)
    nav = [f'<li><a href="{C.url_home(ctx)}"{" class=on" if active == "_home" else ""}>Home</a></li>']
    nav += [f'<li><a href="{C.url_section(ctx, s["slug"])}"{" class=on" if active == s["slug"] else ""}>{esc(s["name"])}</a></li>'
            for s in o["sections"]]
    nav.append(f'<li><a href="{C.url_archive(ctx)}"{" class=on" if active == "_archive" else ""}>Archive</a></li>')
    tick = ctx["articles"][:8]
    ticker = ""
    if tick:
        ticker = ('<div class="ticker-wrap"><div class="ticker-label">Latest</div><div class="ticker-track"><div class="ticker-text">'
                  + "".join(f'<a href="{a["url"]}" data-article-id="{a["pid"]}" data-nr-nobadge>{esc(a["headline"])}</a>' for a in tick)
                  + "</div></div></div>")
    alerts = ctx["status"].get("alerts") or []
    sev = [a for a in alerts if a["level"] in ("emergency", "warning")]
    alert_bar = ""
    if sev:
        alert_bar = ('<div class="alert-bar sev gut">' + "".join(
            f'<div><strong>{esc(LEVEL.get(a["level"], a["level"]))}</strong>{esc(a["text"])}</div>' for a in sev) + "</div>")
    bb = ""
    if banner and brk6:
        b = brk6[0]
        bb = (f'<div class="breaking-banner gut" data-article-id="{b["pid"]}" data-nr-nobadge><div class="inner">'
              f'<span class="bb-label">Breaking news</span><a href="{b["url"]}">{esc(b["headline"])}</a></div></div>')
    secs = "".join(f'<li><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a></li>' for s in o["sections"])
    return (C.head(ctx, title, FONTS, CSS) + '<div id="nr-root">'
            + f'<div class="util-bar gut"><span>Corpus Christi, Texas · {C.clock_span(ctx, "date-long")} · {C.clock_span(ctx, "time-ap")}'
              + ('<span class="breaking-flash">Breaking</span>' if brk6 else "") + '</span>'
              f'<span><a href="{C.url_rss(ctx)}">RSS</a> · <a href="/">All outlets</a></span></div>'
            + f'<header class="top gut"><a class="logo" href="{C.url_home(ctx)}" aria-label="Harborline 6 News home">'
              f'<span class="logo-h6">Harborline <span class="logo-6">6</span></span><span class="logo-news">News</span></a>'
              f'<div class="header-right">{live}<form class="hdr-search" action="{C.url_archive(ctx)}" role="search">'
              f'<input type="search" name="q" placeholder="Search stories" aria-label="Search"></form></div></header>'
            + f'<nav class="subnav" aria-label="Sections"><ul>{"".join(nav)}</ul></nav>'
            + ticker + alert_bar + bb
            + f'<main class="main gut">{inner}</main>'
            + f'<footer class="site gut"><div class="footer-inner"><div><div class="footer-brand">Harborline <span>6</span> News</div>'
              f'<p>Breaking news, weather and traffic for Corpus Christi and the Coastal Bend.</p></div>'
              f'<div><h4>Sections</h4><ul>{secs}</ul></div>'
              f'<div><h4>More</h4><ul><li><a href="{C.url_archive(ctx)}">Story archive</a></li><li><a href="{C.url_rss(ctx)}">RSS feed</a></li>'
              f'<li><a href="/">Coastal Bend newsstand</a></li></ul></div></div>'
              f'<div class="footer-bottom">Harborline 6 News · harborline6.example · All people, organizations and events depicted are fictional.</div></footer>'
            + "</div>" + C.foot(ctx))


# ------------------------------------------------------------------ views
def _home(ctx):
    arts = ctx["articles"]
    if not arts:
        inner = ('<div class="empty"><h2>Stay with Harborline 6</h2>'
                 '<p>Our team is working on the first stories of the day. New updates will post here as soon as they are ready.</p></div>')
        return _frame(ctx, "Harborline 6 News | Corpus Christi, Coastal Bend", f'<div class="two-col"><div>{inner}</div>{_sidebar(ctx)}</div>', "_home")
    brk = _breaking(ctx, 24)
    hero = brk[0] if brk else arts[0]
    used = {hero["pid"]}
    paras = "".join(f"<p>{esc(p)}</p>" for p in hero["body"][:2])
    hero_html = (f'<article class="hero-card" data-article-id="{hero["pid"]}"><a href="{hero["url"]}" tabindex="-1">{_thumb(hero)}</a>'
                 f'<div class="hero-body"><div class="cat">{esc(_cat(hero))}</div>'
                 + ('<span class="learned">Harborline 6 has learned</span>' if _learned(hero) else "")
                 + f'<h1><a href="{hero["url"]}">{esc(hero["headline"])}</a></h1>'
                 f'<div class="byl">{("By <strong>" + esc(C.byline(hero)) + "</strong> · ") if hero["authors"] else ""}{C.ago_span(ctx, hero)}</div>'
                 f'{paras}<a href="{hero["url"]}"><strong>Read the full story →</strong></a></div></article>')
    top = [a for a in arts if a["pid"] not in used][:3]
    used |= {a["pid"] for a in top}
    rest = [a for a in arts if a["pid"] not in used][:10]
    main = hero_html
    if top:
        main += '<div class="section-label">Top stories</div><div class="card-row">' + "".join(_card(ctx, a) for a in top) + "</div>"
    if rest:
        main += ('<div class="section-label">Latest stories</div><div class="latest-grid">'
                 + "".join(_latest_item(ctx, a, i + 1) for i, a in enumerate(rest)) + "</div>")
    return _frame(ctx, "Harborline 6 News | Corpus Christi, Coastal Bend",
                  f'<div class="two-col"><div style="min-width:0">{main}</div>{_sidebar(ctx)}</div>', "_home")


def _section(ctx, sec, items):
    if items:
        body = '<div class="card-row">' + "".join(_card(ctx, a) for a in items[:3]) + "</div>"
        if items[3:]:
            body += '<div class="latest-grid">' + "".join(_latest_item(ctx, a, i + 4) for i, a in enumerate(items[3:])) + "</div>"
    else:
        body = f'<div class="empty"><h2>No {esc(sec["name"])} stories yet</h2><p>Stories will post here as soon as they air.</p></div>'
    n = len(items)
    inner = (f'<h1 class="page-h">{esc(sec["name"])}</h1><p class="page-sub">{n} stor{"y" if n == 1 else "ies"} from the Harborline 6 newsroom</p>'
             f'<div class="two-col"><div style="min-width:0">{body}</div>{_sidebar(ctx)}</div>')
    return _frame(ctx, f'{sec["name"]} | Harborline 6 News', inner, sec["slug"])


def _article(ctx, a, related, newer, older):
    tags = "".join(f"<span>{esc(s)}</span>" for s in a["storylines"])
    pn = ('<div class="prevnext">'
          + (f'<div data-article-id="{older["pid"]}" data-nr-nobadge><small>Previous</small><a href="{older["url"]}">{esc(older["headline"])}</a></div>' if older else "<div></div>")
          + (f'<div class="r" data-article-id="{newer["pid"]}" data-nr-nobadge><small>Next</small><a href="{newer["url"]}">{esc(newer["headline"])}</a></div>' if newer else "<div></div>")
          + "</div>")
    story = (f'<article class="story" data-article-id="{a["pid"]}">{_thumb(a)}<div class="story-in">'
             f'<div class="cat"><a href="{C.url_section(ctx, a["section_slug"])}" style="color:inherit">{esc(_cat(a))}</a></div>'
             + ('<span class="learned">Harborline 6 has learned</span>' if _learned(a) else "")
             + f'<h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
             f'<div class="byl">{("By <strong>" + esc(C.byline(a)) + "</strong> · ") if a["authors"] else ""}'
             f'Published {esc(C.pub_label(a))}</div><div class="body">{C.paras(a["body"])}</div>'
             + (f'<div class="tags">{tags}</div>' if tags else "") + pn + "</div></article>")
    rel = "".join(f'<li data-article-id="{r["pid"]}">'
                  + (f'<span class="src">{esc(r["outlet_name"])}</span>' if r["outlet"] != a["outlet"] else "")
                  + f'<a href="{r["url"]}">{esc(r["headline"])}</a></li>' for r in related)
    more = [x for x in ctx["articles"] if x["pid"] != a["pid"]][:5]
    more_html = "".join(f'<li data-article-id="{x["pid"]}"><a href="{x["url"]}">{esc(x["headline"])}</a>'
                        f'<div class="meta">{C.ago_span(ctx, x)}</div></li>' for x in more)
    extra = ""
    if rel:
        extra += f'<div class="tip-box"><h4>Related coverage</h4><ul>{rel}</ul></div>'
    if more_html:
        extra += f'<div class="tip-box"><h4>More from Harborline 6</h4><ul>{more_html}</ul></div>'
    inner = f'<div class="two-col"><div style="min-width:0">{story}</div>{_sidebar(ctx, extra or " ")}</div>'
    return _frame(ctx, f'{a["headline"]} | Harborline 6 News', inner, a["section_slug"], banner=False)


def _archive(ctx, q, date, results, days):
    form = (f'<form class="search-big" action="{C.url_archive(ctx)}" role="search">'
            f'<input type="search" name="q" value="{esc(q)}" placeholder="Search Harborline 6 stories" aria-label="Search">'
            + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "")
            + '<button type="submit">Search</button></form>')
    bits = []
    if q:
        bits.append(f'for “<strong>{esc(q)}</strong>”')
    if date:
        bits.append(f'on <strong>{esc(_day_label(date))}</strong>')
    filt = (f'<div class="filter">{len(results)} result{"s" if len(results) != 1 else ""} {" ".join(bits)} · '
            f'<a href="{C.url_archive(ctx)}">Clear</a></div>') if bits else ""
    groups = C.group_by_day(results)
    if groups:
        lst = "".join(f'<h2 class="day-h">{esc(_day_label(d))}</h2><ul class="arch">'
                      + "".join(f'<li data-article-id="{a["pid"]}"><div class="cat">{esc(_cat(a))}</div>'
                                f'<a href="{a["url"]}">{esc(a["headline"])}</a><div class="meta">{esc(C.fmt_time_ap(a["ts"]))}'
                                f'{(" · " + esc(C.byline(a))) if a["authors"] else ""}</div></li>' for a in items)
                      + "</ul>" for d, items in groups)
    elif ctx["articles"]:
        lst = '<div class="empty"><h2>No stories found</h2><p>Try another search or clear the filters.</p></div>'
    else:
        lst = '<div class="empty"><h2>No stories yet</h2><p>The archive fills in as stories post.</p></div>'
    months, idx = [], {}
    for d, n in days:
        if d[:7] not in idx:
            idx[d[:7]] = []
            months.append(d[:7])
        idx[d[:7]].append((d, n))
    dh = ""
    for m in months:
        y, mo = m.split("-")
        dh += (f'<h5>{C.MONTHS[int(mo) - 1]} {y}</h5><ul>'
               + "".join(f'<li><a href="{C.url_archive(ctx, date=d)}"{" class=on" if d == date else ""} title="{n} stories">'
                         f'{dt.date.fromisoformat(d).day}</a></li>' for d, n in idx[m]) + "</ul>")
    side = (f'<aside class="sidebar"><div class="wx-card days"><div class="wx-head">Browse by date</div>{dh}</div></aside>'
            if dh else f'<aside class="sidebar">{_alerts_widget(ctx)}</aside>')
    inner = (f'<h1 class="page-h">Story archive</h1><p class="page-sub">Every Harborline 6 story, newest first.</p>'
             f'<div class="two-col"><div style="min-width:0">{form}{filt}{lst}</div>{side}</div>')
    return _frame(ctx, "Archive | Harborline 6 News", inner, "_archive", banner=False)


def _notfound(ctx):
    inner = ('<div class="empty"><h2>Page not found</h2><p>This story may have been moved or removed. '
             f'<a href="{C.url_home(ctx)}">Go to the homepage</a> or <a href="{C.url_archive(ctx)}">search our stories</a>.</p></div>')
    return _frame(ctx, "Page not found | Harborline 6 News", f'<div class="two-col"><div>{inner}</div>{_sidebar(ctx)}</div>', banner=False)


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
