"""Coastline Public Radio — regional public radio newsroom (web stories).

Visual identity from 10_news_sites/coastline-radio.html: Lora italic masthead, deep teal and
warm amber, member bar, on-air strip, generous white space. All content comes from ctx.
"""
import datetime as dt
import re

from nr import common as C
from nr.common import esc

FONTS = "https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,600;0,700;1,400;1,600&display=swap"

CSS = """
:root{--teal:#2a7f7f;--teal-dark:#1a4f4f;--teal-light:#e8f5f5;--amber:#e8903a;--amber-dark:#c9731f;--bg:#fafaf8;
  --card:#fff;--text:#1f2937;--muted:#6b7280;--divider:#e5e0d8;--ink:#111827}
body{margin:0;font-family:Georgia,'Times New Roman',serif;background:var(--bg);color:var(--text);font-size:16px;line-height:1.6}
a{color:var(--teal);text-decoration:none}
a:hover{text-decoration:underline;color:var(--teal-dark)}
.gut{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.inner{max-width:1100px;margin:0 auto}
.member-bar{background:var(--teal-dark);color:#c8e6e6;font:12px/1.4 system-ui,sans-serif;padding-block:7px}
.member-bar .inner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.member-bar a{color:#9ed8d8}
.donate-btn{background:var(--amber);color:#fff!important;padding:4px 14px;border-radius:3px;font-weight:600;font-size:11px;letter-spacing:.05em;text-transform:uppercase}
.donate-btn:hover{background:var(--amber-dark);text-decoration:none}
header.mast{background:var(--card);border-bottom:3px solid var(--teal);padding-block:18px 14px}
header.mast .inner{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px}
.site-title{font-family:'Lora',Georgia,serif;font-style:italic;font-size:2rem;font-weight:700;color:var(--teal-dark);line-height:1.1}
.site-title a{color:inherit}
.site-title a:hover{text-decoration:none}
.site-tagline{font:11px system-ui,sans-serif;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;margin-top:3px}
.listen-live-btn{background:var(--teal);color:#fff!important;padding:7px 16px;border-radius:20px;font:600 12px system-ui,sans-serif;display:inline-flex;align-items:center;gap:6px}
.listen-live-btn::before{content:'';width:8px;height:8px;background:#ff4444;border-radius:50%;animation:pd 1.5s infinite}
.listen-live-btn.gen::before{background:#f5b301}
@keyframes pd{0%,100%{opacity:1}50%{opacity:.3}}
.listen-live-btn:hover{text-decoration:none;background:var(--teal-dark)}
nav.sections{background:var(--teal-dark);overflow-x:auto}
nav.sections ul{list-style:none;display:flex;margin:0 auto;padding:0;max-width:1100px}
nav.sections a{display:block;color:#b8dede;font:500 12.5px system-ui,sans-serif;padding:10px 14px;letter-spacing:.03em;white-space:nowrap}
nav.sections a:hover{color:#fff;text-decoration:none;background:rgba(255,255,255,.08)}
nav.sections a.active{color:#fff;box-shadow:inset 0 -2px 0 var(--amber)}
.audio-bar{background:#f0f7f7;border-bottom:1px solid #c8e0e0;padding-block:8px;font:12px/1.4 system-ui,sans-serif;color:var(--teal-dark)}
.audio-bar .inner{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.play-btn-sm{width:28px;height:28px;background:var(--teal);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.play-btn-sm::after{content:'';border:5px solid transparent;border-left:8px solid #fff;margin-left:2px}
.audio-progress{flex:1;height:3px;background:#c8e0e0;border-radius:2px;min-width:60px;max-width:220px;position:relative}
.audio-progress::after{content:'';position:absolute;left:0;top:0;height:100%;width:32%;background:var(--teal);border-radius:2px}
.onair{font-weight:700;letter-spacing:.06em;text-transform:uppercase;font-size:10.5px;padding:2px 8px;border-radius:10px;background:var(--teal);color:#fff}
.onair.gen{background:var(--amber)}
.alerts{background:#fdf6ed;border-bottom:1px solid #f2d3ad;padding-block:10px;font:14px/1.45 system-ui,sans-serif}
.alerts .inner{display:flex;flex-direction:column;gap:6px}
.alert-row{display:flex;gap:10px;align-items:baseline}
.alert-tag{flex-shrink:0;font-weight:700;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:#fff;background:var(--amber-dark);padding:3px 7px;border-radius:3px}
.alert-tag.emergency,.alert-tag.warning{background:#b42318}
main{padding-bottom:12px}
.featured{padding-block:36px 28px;border-bottom:1px solid var(--divider)}
.section-label{font:700 10px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--teal);margin:0 0 14px;display:flex;align-items:center;gap:8px}
.section-label::after{content:'';flex:1;height:1px;background:var(--divider)}
.section-label a{color:inherit}
.featured-grid{display:grid;grid-template-columns:1fr 1.1fr;gap:32px;align-items:start}
@media(max-width:760px){.featured-grid{grid-template-columns:1fr}}
.featured-grid>*{min-width:0}
.featured-image{background:linear-gradient(135deg,#1a5f5f 0%,#2a9f9f 55%,#5ababa 100%);aspect-ratio:4/3;border-radius:4px;position:relative;overflow:hidden;max-width:100%}
.featured-image .wave{position:absolute;inset:auto 0 0 0;height:45%;background:repeating-linear-gradient(90deg,rgba(255,255,255,.18) 0 3px,transparent 3px 9px);
  -webkit-mask:linear-gradient(transparent,#000);mask:linear-gradient(transparent,#000)}
.img-caption{position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.5);color:rgba(255,255,255,.9);font:11px/1.4 system-ui,sans-serif;padding:8px 12px}
.kicker{font:700 11px system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--teal);margin-bottom:8px}
.kicker a{color:inherit}
.featured-hed{font-family:'Lora',Georgia,serif;font-size:1.75rem;font-weight:700;line-height:1.25;color:var(--ink);margin:0 0 12px;text-wrap:balance}
.featured-hed a,.card-hed a,.audio-hed a{color:var(--ink)}
.featured-hed a:hover,.card-hed a:hover,.audio-hed a:hover{color:var(--teal-dark)}
.byline{font:12px/1.5 system-ui,sans-serif;color:var(--muted);margin-bottom:14px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.byline .author{color:var(--teal);font-weight:600}
.listen{display:inline-flex;align-items:center;gap:5px;font:600 11px system-ui,sans-serif;color:var(--teal-dark);background:var(--teal-light);padding:2px 9px;border-radius:10px;white-space:nowrap}
.listen::before{content:'';border:4px solid transparent;border-left:6px solid var(--teal);margin-left:2px}
.dek{font-family:'Lora',Georgia,serif;font-style:italic;font-size:1.06rem;color:#374151;margin:0 0 12px}
.article-body{font-size:1rem;line-height:1.75;color:#374151}
.article-body p{margin:0 0 14px}
.read-more{display:inline-block;margin-top:4px;font:700 12px system-ui,sans-serif;color:var(--teal);letter-spacing:.04em;text-transform:uppercase}
.stories-section{padding-block:32px 24px;border-bottom:1px solid var(--divider)}
.stories-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
@media(max-width:820px){.stories-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:540px){.stories-grid{grid-template-columns:1fr}}
.story-card{background:var(--card);border-radius:4px;overflow:hidden;border:1px solid var(--divider);transition:box-shadow .2s;min-width:0}
.story-card:hover{box-shadow:0 4px 16px rgba(42,127,127,.12)}
.card-img{aspect-ratio:16/9;max-width:100%}
.ci-0{background:linear-gradient(135deg,#1a4f4f,#2a7f7f)}.ci-1{background:linear-gradient(135deg,#7a4a1f,#e8903a)}
.ci-2{background:linear-gradient(135deg,#2c3e50,#4f7a8a)}.ci-3{background:linear-gradient(135deg,#355e3b,#7aa57f)}
.ci-4{background:linear-gradient(135deg,#4b3b5e,#8b7aa5)}
.card-body{padding:16px}
.card-category{font:700 10px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--teal);margin-bottom:7px}
.card-hed{font-family:'Lora',Georgia,serif;font-size:1.05rem;font-weight:600;line-height:1.35;color:var(--ink);margin:0 0 8px}
.card-dek{font-size:.92rem;color:#4b5563;margin:0 0 10px;line-height:1.5}
.card-byline{font:11px/1.5 system-ui,sans-serif;color:var(--muted);display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.card-byline .author{color:var(--teal);font-weight:600}
.audio-stories{display:flex;flex-direction:column;gap:6px}
.audio-item{display:flex;align-items:center;gap:14px;padding:14px 16px;background:var(--card);border:1px solid var(--divider);border-radius:4px}
.audio-item:hover{background:var(--teal-light)}
.audio-play{width:36px;height:36px;background:var(--amber);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.audio-play::after{content:'';border:6px solid transparent;border-left:10px solid #fff;margin-left:3px}
.audio-info{flex:1;min-width:0}
.audio-hed{font-family:'Lora',Georgia,serif;font-size:.98rem;font-weight:600;color:var(--ink);margin:0 0 2px}
.audio-meta{font:11px system-ui,sans-serif;color:var(--muted)}
.audio-duration{font:11px system-ui,sans-serif;color:var(--muted);background:#f0f0ec;padding:3px 10px;border-radius:10px;white-space:nowrap}
@media(max-width:480px){.audio-duration{display:none}}
.pull-quote-large{background:var(--teal-light);border-left:4px solid var(--teal);padding:22px 26px;margin:0;border-radius:0 4px 4px 0}
.pull-quote-large blockquote{font-family:'Lora',Georgia,serif;font-style:italic;font-size:1.3rem;line-height:1.5;color:var(--teal-dark);margin:0 0 10px}
.pull-quote-large cite{font:600 12px system-ui,sans-serif;font-style:normal;color:var(--muted);letter-spacing:.04em}
.blocks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:28px}
@media(max-width:700px){.blocks{grid-template-columns:1fr}}
.block{min-width:0}
.block-desc{font:13px/1.5 system-ui,sans-serif;color:var(--muted);margin:-6px 0 12px}
.block ul{list-style:none;margin:0;padding:0}
.block li{padding:10px 0;border-bottom:1px solid var(--divider)}
.block li:last-child{border-bottom:0}
.block li a{font-family:'Lora',Georgia,serif;font-weight:600;color:var(--ink);font-size:1rem;line-height:1.35}
.block li .meta{display:block;font:11px system-ui,sans-serif;color:var(--muted);margin-top:3px}
.empty{background:var(--card);border:1px dashed var(--divider);border-radius:6px;padding:28px;color:#4b5563;font-size:1rem;max-width:62ch}
.empty h2{font-family:'Lora',Georgia,serif;font-style:italic;color:var(--teal-dark);margin:0 0 8px;font-size:1.4rem}
/* article */
.story-wrap{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:44px;padding-block:32px}
@media(max-width:880px){.story-wrap{grid-template-columns:1fr}}
.story{max-width:68ch;min-width:0}
.story h1{font-family:'Lora',Georgia,serif;font-size:2.15rem;line-height:1.2;color:var(--ink);margin:6px 0 12px;text-wrap:balance}
@media(max-width:480px){.story h1{font-size:1.7rem}}
.story .listen-bar{display:flex;align-items:center;gap:12px;background:#f0f7f7;border:1px solid #c8e0e0;border-radius:30px;padding:8px 14px 8px 8px;margin:16px 0 22px;font:12px system-ui,sans-serif;color:var(--teal-dark)}
.story .article-body{font-size:1.06rem}
.tags{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0}
.tag{font:600 11px system-ui,sans-serif;color:var(--teal-dark);background:var(--teal-light);padding:4px 10px;border-radius:12px}
.related h2,.side h2{font:700 11px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--teal);margin:0 0 10px}
.related ul,.side ul{list-style:none;margin:0;padding:0}
.related li,.side li{padding:10px 0;border-bottom:1px solid var(--divider)}
.related li a,.side li a{font-family:'Lora',Georgia,serif;font-weight:600;color:var(--ink)}
.related .src{display:block;font:11px system-ui,sans-serif;color:var(--muted);margin-top:2px}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:26px;font:13px system-ui,sans-serif}
.pager a{display:block;border:1px solid var(--divider);border-radius:4px;padding:12px;background:var(--card);color:var(--ink)}
.pager span{display:block;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:3px}
.pager .next{text-align:right}
.side{min-width:0}
.side .box{background:var(--card);border:1px solid var(--divider);border-radius:4px;padding:18px;margin-bottom:22px}
/* archive */
.arch-head{padding-block:28px 6px}
.arch-head h1{font-family:'Lora',Georgia,serif;font-style:italic;color:var(--teal-dark);margin:0 0 12px;font-size:2rem}
form.search{display:flex;gap:8px;flex-wrap:wrap;max-width:560px}
form.search input{flex:1;min-width:0;padding:10px 12px;border:1px solid #c8d6d6;border-radius:4px;font:15px system-ui,sans-serif;background:#fff}
form.search button{padding:10px 18px;border:0;border-radius:4px;background:var(--teal);color:#fff;font:600 13px system-ui,sans-serif;cursor:pointer}
.filter{font:13px system-ui,sans-serif;color:var(--muted);margin:12px 0 0}
.arch-grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:40px;padding-block:20px 10px}
@media(max-width:860px){.arch-grid{grid-template-columns:1fr}}
.day-group h2{font:700 12px system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--teal-dark);border-bottom:2px solid var(--teal);padding-bottom:6px;margin:26px 0 6px}
.day-group ul{list-style:none;margin:0;padding:0}
.day-group li{padding:11px 0;border-bottom:1px solid var(--divider)}
.day-group li a{font-family:'Lora',Georgia,serif;font-weight:600;color:var(--ink);font-size:1.02rem}
.day-group .meta{display:block;font:11px system-ui,sans-serif;color:var(--muted);margin-top:3px}
.day-index{background:var(--card);border:1px solid var(--divider);border-radius:4px;padding:16px;max-height:640px;overflow:auto}
.day-index h3{font:700 11px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--teal);margin:12px 0 6px}
.day-index h3:first-child{margin-top:0}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips a{font:12px system-ui,sans-serif;border:1px solid var(--divider);border-radius:12px;padding:3px 9px;color:var(--teal-dark);white-space:nowrap}
.chips a.on{background:var(--teal);color:#fff;border-color:var(--teal)}
footer.foot{background:var(--teal-dark);color:#9ed8d8;padding-block:30px;font:12px/1.6 system-ui,sans-serif;margin-top:48px}
footer.foot .inner{display:grid;grid-template-columns:2fr 1fr 1fr;gap:28px}
@media(max-width:640px){footer.foot .inner{grid-template-columns:1fr}}
footer.foot strong{color:#fff;font-family:'Lora',Georgia,serif;font-style:italic;font-size:1.1rem;font-weight:700}
footer.foot a{color:#c8e6e6}
footer.foot ul{list-style:none;margin:0;padding:0}
"""

PROGRAMS = [(0, 5, "Overnight"), (5, 9, "Coastal Morning"), (9, 12, "Bay Midday"), (12, 15, "Here on the Coast"),
            (15, 19, "Evening Tide"), (19, 24, "Night Desk")]

SECTION_DESC = {
    "Equity": "Who gets help, who waits, and why.",
    "Environment": "The bays, the weather and the water we live beside.",
    "Health": "Clinics, hospitals and community health across the Coastal Bend.",
    "Military & Community": "The bases, the depot and the families around them.",
    "Investigations": "Records, data and accountability reporting.",
}

FEATURE_TYPES = ("feature", "analysis", "explainer", "profile")


# ---------------------------------------------------------------- helpers
def program(ctx):
    h = C.local(ctx["now"]).hour
    for a, b, name in PROGRAMS:
        if a <= h < b:
            return name
    return "Overnight"


def listen_min(a):
    return max(1, round(a.get("words", 300) / 150))


def listen_badge(a):
    return f'<span class="listen">Listen · {listen_min(a)} min</span>'


def authors_html(a):
    names = a.get("authors") or []
    if not names:
        return '<span class="author">Coastline Public Radio</span>'
    return " and ".join(f'<span class="author">{esc(n)}</span>' for n in names)


def date_label(iso):
    d = dt.date.fromisoformat(iso)
    return f"{C.DAYS[d.weekday()]}, {C.MONTHS[d.month - 1]} {d.day}, {d.year}"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{C.AP_MONTHS[d.month - 1]} {d.day}"


def find_quote(a):
    for p in a.get("body", []):
        for m in re.finditer(r'"([^"]{40,280})"', p):
            q = m.group(1).strip()
            if len(q.split()) >= 7:
                return q
    return None


def section_href(ctx, name):
    for s in ctx["outlet"]["sections"]:
        if s["name"] == name:
            return C.url_section(ctx, s["slug"])
    return C.url_home(ctx)


# ---------------------------------------------------------------- frame
def frame(ctx, title, inner, active=None):
    o = ctx["outlet"]
    bc = ctx["status"].get("broadcast")
    gen = bool(bc and bc.get("status") == "generator")
    nav = [f'<li><a href="{C.url_home(ctx)}" class="{"active" if active == "home" else ""}">Home</a></li>']
    for s in o["sections"]:
        cls = "active" if active == s["slug"] else ""
        nav.append(f'<li><a href="{C.url_section(ctx, s["slug"])}" class="{cls}">{esc(s["name"])}</a></li>')
    nav.append(f'<li><a href="{C.url_archive(ctx)}" class="{"active" if active == "archive" else ""}">Archive</a></li>')

    onair = ('<span class="onair gen">On the air · generator power</span>' if gen
             else '<span class="onair">On the air</span>')
    audio = (f'<div class="audio-bar gut"><div class="inner"><span class="play-btn-sm" aria-hidden="true"></span>'
             f'{onair}<span>Now playing: <strong>{esc(program(ctx))}</strong></span>'
             f'<span class="audio-progress" aria-hidden="true"></span>'
             f'<span>{C.clock_span(ctx, "time-ap")}</span></div></div>')

    alerts = ""
    if ctx["status"]["alerts"]:
        rows = "".join(f'<div class="alert-row"><span class="alert-tag {esc(a["level"])}">{esc(a["level"])}</span>'
                       f'<span>{esc(a["text"])}</span></div>' for a in ctx["status"]["alerts"])
        alerts = f'<div class="alerts gut" role="region" aria-label="Emergency information"><div class="inner">{rows}</div></div>'

    secs = "".join(f'<li><a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a></li>' for s in o["sections"])
    body = (
        f'<div id="nr-root">'
        f'<div class="member-bar gut"><div class="inner"><span>{C.clock_span(ctx, "date-long")} · Public radio for the Coastal Bend, '
        f'powered by members</span><span><a href="{C.url_home(ctx)}">Become a member</a> &nbsp; '
        f'<a class="donate-btn" href="{C.url_home(ctx)}">Donate</a></span></div></div>'
        f'<header class="mast gut"><div class="inner"><div><div class="site-title"><a href="{C.url_home(ctx)}">{esc(o["name"])}</a></div>'
        f'<div class="site-tagline">News for the Coastal Bend</div></div>'
        f'<a class="listen-live-btn{" gen" if gen else ""}" href="{C.url_home(ctx)}">Listen live</a></div></header>'
        f'<nav class="sections gut" aria-label="Sections"><ul>{"".join(nav)}</ul></nav>'
        f'{audio}{alerts}<main>{inner}</main>'
        f'<footer class="foot gut"><div class="inner"><div><strong>{esc(o["name"])}</strong>'
        f'<p>Explanatory, people-first reporting on the environment, equity, health and the military community '
        f'of the Coastal Bend. Member-supported public radio.</p><p>All people and events on this site are fictional.</p></div>'
        f'<div><ul>{secs}</ul></div><div><ul><li><a href="{C.url_archive(ctx)}">Story archive</a></li>'
        f'<li><a href="{C.url_rss(ctx)}">RSS feed</a></li></ul></div></div></footer>'
        f'</div>')
    return C.head(ctx, title, FONTS, CSS) + body + C.foot(ctx)


def card(ctx, a, i=0):
    return (f'<article class="story-card" data-article-id="{a["pid"]}"><a href="{a["url"]}" aria-hidden="true" tabindex="-1">'
            f'<div class="card-img ci-{i % 5}"></div></a><div class="card-body">'
            f'<div class="card-category">{esc(a["section"])}</div>'
            f'<h3 class="card-hed"><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'<p class="card-dek">{esc(C.excerpt(a, 26))}</p>'
            f'<div class="card-byline">{authors_html(a)} · {C.ago_span(ctx, a)} · {listen_badge(a)}</div></div></article>')


def list_item(ctx, a, show_section=True):
    sec = f'{esc(a["section"])} · ' if show_section else ""
    return (f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
            f'<span class="meta">{sec}{esc(C.byline(a) or "Coastline Public Radio")} · {C.ago_span(ctx, a)}</span></li>')


def empty(title, text):
    return f'<div class="empty"><h2>{esc(title)}</h2><p>{esc(text)}</p></div>'


# ---------------------------------------------------------------- views
def home(ctx):
    arts = ctx["articles"]
    if not arts:
        inner = (f'<section class="featured gut"><div class="inner">'
                 + empty("Our newsroom is just getting started",
                         "Coastline Public Radio has not published any web stories yet. Tune in live for news and "
                         "conversation from across the Coastal Bend, and check back here for reporting.")
                 + '</div></section>')
        return frame(ctx, ctx["outlet"]["name"], inner, "home")

    feat = next((a for a in arts if a["story_type"] in FEATURE_TYPES), arts[0])
    paras = "".join(f"<p>{esc(p)}</p>" for p in feat["body"][:2])
    featured = (
        f'<section class="featured gut"><div class="inner"><div class="section-label">Featured</div>'
        f'<div class="featured-grid" data-article-id="{feat["pid"]}">'
        f'<a class="featured-image" href="{feat["url"]}" aria-hidden="true" tabindex="-1"><div class="wave"></div>'
        f'<div class="img-caption">{esc(feat["section"])} · {esc(C.fmt_date_ap(feat["ts"]))}</div></a>'
        f'<div><div class="kicker"><a href="{section_href(ctx, feat["section"])}">{esc(feat["section"])}</a></div>'
        f'<h2 class="featured-hed"><a href="{feat["url"]}">{esc(feat["headline"])}</a></h2>'
        f'<div class="byline">By {authors_html(feat)} · {C.ago_span(ctx, feat)} · {listen_badge(feat)}</div>'
        f'<p class="dek">{esc(feat["summary"])}</p><div class="article-body">{paras}</div>'
        f'<a class="read-more" href="{feat["url"]}">Read the full story →</a></div></div></div></section>')

    rest = [a for a in arts if a["pid"] != feat["pid"]]
    latest = rest[:6]
    latest_html = ""
    if latest:
        latest_html = (f'<section class="stories-section gut"><div class="inner"><div class="section-label">Latest from the newsroom</div>'
                       f'<div class="stories-grid">{"".join(card(ctx, a, i) for i, a in enumerate(latest))}</div></div></section>')

    listen = rest[6:10] if len(rest) > 6 else rest[:4]
    listen_html = ""
    if listen:
        items = "".join(
            f'<div class="audio-item" data-article-id="{a["pid"]}"><a class="audio-play" href="{a["url"]}" aria-label="Listen"></a>'
            f'<div class="audio-info"><h3 class="audio-hed"><a href="{a["url"]}">{esc(a["headline"])}</a></h3>'
            f'<div class="audio-meta">{esc(a["section"])} · {esc(C.byline(a) or "Coastline Public Radio")} · {C.ago_span(ctx, a)}</div></div>'
            f'<span class="audio-duration">{listen_min(a)} min</span></div>' for a in listen)
        listen_html = (f'<section class="stories-section gut"><div class="inner"><div class="section-label">Listen</div>'
                       f'<div class="audio-stories">{items}</div></div></section>')

    quote_html = ""
    qsrc = next((a for a in arts if a["story_type"] in FEATURE_TYPES and find_quote(a)), None)
    if qsrc:
        q = find_quote(qsrc)
        quote_html = (f'<section class="stories-section gut"><div class="inner"><div class="section-label">In their words</div>'
                      f'<div class="pull-quote-large" data-article-id="{qsrc["pid"]}" data-nr-nobadge><blockquote>“{esc(q)}”</blockquote>'
                      f'<cite>From <a href="{qsrc["url"]}">{esc(qsrc["headline"])}</a></cite></div></div></section>')

    blocks = []
    for name in ("Equity", "Environment", "Health", "Military & Community", "Investigations"):
        items = [a for a in arts if a["section"] == name][:3]
        if not items:
            continue
        blocks.append(f'<div class="block"><div class="section-label"><a href="{section_href(ctx, name)}">{esc(name)}</a></div>'
                      f'<p class="block-desc">{esc(SECTION_DESC.get(name, ""))}</p>'
                      f'<ul>{"".join(list_item(ctx, a, False) for a in items)}</ul></div>')
    blocks_html = (f'<section class="stories-section gut"><div class="inner"><div class="blocks">{"".join(blocks)}</div></div></section>'
                   if blocks else "")
    return frame(ctx, f'{ctx["outlet"]["name"]} | News for the Coastal Bend',
                 featured + latest_html + quote_html + listen_html + blocks_html, "home")


def section(ctx, sec, items):
    if items:
        lead, rest = items[:6], items[6:]
        body = f'<div class="stories-grid">{"".join(card(ctx, a, i) for i, a in enumerate(lead))}</div>'
        if rest:
            body += (f'<div class="block" style="margin-top:32px"><div class="section-label">More {esc(sec["name"])}</div>'
                     f'<ul>{"".join(list_item(ctx, a, False) for a in rest)}</ul></div>')
    else:
        body = empty(f'No {sec["name"]} stories yet', "Our reporters haven't filed in this section yet. Check back soon.")
    inner = (f'<section class="stories-section gut"><div class="inner"><div class="section-label">{esc(sec["name"])}</div>'
             f'<p class="block-desc">{esc(SECTION_DESC.get(sec["name"], ""))}</p>{body}</div></section>')
    return frame(ctx, f'{sec["name"]} | {ctx["outlet"]["name"]}', inner, sec["slug"])


def article(ctx, a, related, newer, older):
    tags = "".join(f'<span class="tag">{esc(s)}</span>' for s in a.get("storylines", []))
    rel = ""
    if related:
        rel = ('<div class="related"><h2>Related coverage</h2><ul>' + "".join(
            f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(r["headline"])}</a>'
            f'<span class="src">{esc(r["outlet_name"])} · {C.ago_span(ctx, r)}</span></li>' for r in related) + '</ul></div>')
    pager = ""
    if newer or older:
        pager = '<div class="pager">'
        pager += (f'<a href="{older["url"]}" data-article-id="{older["pid"]}" data-nr-nobadge><span>← Earlier</span>{esc(older["headline"])}</a>'
                  if older else '<div></div>')
        pager += (f'<a class="next" href="{newer["url"]}" data-article-id="{newer["pid"]}" data-nr-nobadge><span>Later →</span>{esc(newer["headline"])}</a>'
                  if newer else '<div></div>')
        pager += '</div>'
    more = [x for x in ctx["articles"] if x["section"] == a["section"] and x["pid"] != a["pid"]][:4]
    side = ""
    if more:
        side = (f'<div class="box"><h2>More {esc(a["section"])}</h2><ul>' +
                "".join(f'<li data-article-id="{x["pid"]}"><a href="{x["url"]}">{esc(x["headline"])}</a></li>' for x in more) +
                '</ul></div>')
    side += (f'<div class="box"><h2>Coastline Public Radio</h2><p style="font:14px/1.55 system-ui,sans-serif;margin:0;color:#4b5563">'
             f'Now playing: <strong>{esc(program(ctx))}</strong>. Public radio for the Coastal Bend, supported by members like you.</p></div>')
    inner = (
        f'<div class="gut"><div class="inner story-wrap"><article class="story" data-article-id="{a["pid"]}">'
        f'<div class="kicker"><a href="{section_href(ctx, a["section"])}">{esc(a["section"])}</a></div>'
        f'<h1>{esc(a["headline"])}</h1><p class="dek">{esc(a["summary"])}</p>'
        f'<div class="byline">By {authors_html(a)} · <time datetime="{esc(a["published"])}">{esc(C.pub_label(a))}</time></div>'
        f'<div class="listen-bar"><span class="play-btn-sm" aria-hidden="true"></span><span>Listen to this story</span>'
        f'<span class="audio-progress" aria-hidden="true"></span><span>{listen_min(a)} min</span></div>'
        f'<div class="article-body">{C.paras(a["body"])}</div>'
        + (f'<div class="tags">{tags}</div>' if tags else "")
        + rel + pager +
        f'</article><aside class="side">{side}</aside></div></div>')
    return frame(ctx, f'{a["headline"]} | {ctx["outlet"]["name"]}', inner, a["section_slug"])


def archive(ctx, q, date, results, days):
    filt = []
    if q:
        filt.append(f'matching “{esc(q)}”')
    if date:
        filt.append(f'from {esc(date_label(date))}')
    filt_html = ""
    if filt:
        filt_html = (f'<p class="filter">{len(results)} {"story" if len(results) == 1 else "stories"} {" ".join(filt)} · '
                     f'<a href="{C.url_archive(ctx)}">Clear</a></p>')
    groups = C.group_by_day(results)
    if groups:
        listing = "".join(
            f'<div class="day-group"><h2>{esc(date_label(d))}</h2><ul>' +
            "".join(f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a>'
                    f'<span class="meta">{esc(a["section"])} · {esc(C.byline(a) or "Coastline Public Radio")} · '
                    f'{esc(C.fmt_time_ap(a["ts"]))}</span></li>' for a in items) + '</ul></div>' for d, items in groups)
    else:
        listing = empty("Nothing found", "No stories match that search yet. Try different words or browse by day.")

    months, idx = [], []
    for d, n in days:
        m = d[:7]
        if not months or months[-1][0] != m:
            months.append((m, []))
        months[-1][1].append((d, n))
    for m, ds in months:
        y, mo = int(m[:4]), int(m[5:7])
        chips = "".join(f'<a href="{C.url_archive(ctx, q=q or None, date=d)}" class="{"on" if d == date else ""}">'
                        f'{esc(short_date(d))} ({n})</a>' for d, n in ds)
        idx.append(f'<h3>{C.MONTHS[mo - 1]} {y}</h3><div class="chips">{chips}</div>')
    index = (f'<aside><div class="day-index"><h3>Browse by day</h3>{"".join(idx) or "<p>No stories yet.</p>"}</div></aside>')

    inner = (f'<div class="gut"><div class="inner"><div class="arch-head"><h1>Story archive</h1>'
             f'<form class="search" action="{C.url_archive(ctx)}" method="get" role="search">'
             f'<input type="search" name="q" value="{esc(q)}" placeholder="Search Coastline stories" aria-label="Search stories">'
             + (f'<input type="hidden" name="date" value="{esc(date)}">' if date else "") +
             f'<button type="submit">Search</button></form>{filt_html}</div>'
             f'<div class="arch-grid"><div>{listing}</div>{index}</div></div></div>')
    return frame(ctx, f'Archive | {ctx["outlet"]["name"]}', inner, "archive")


def notfound(ctx):
    latest = ctx["articles"][:5]
    lst = ""
    if latest:
        lst = ('<div class="block" style="margin-top:24px"><div class="section-label">Latest stories</div><ul>' +
               "".join(list_item(ctx, a) for a in latest) + '</ul></div>')
    inner = (f'<section class="featured gut"><div class="inner">'
             + empty("We can't find that page",
                     "The story you're looking for isn't available. It may have moved, or the link may be incomplete.")
             + f'<p style="font:14px system-ui,sans-serif"><a href="{C.url_home(ctx)}">Go to the homepage</a> · '
               f'<a href="{C.url_archive(ctx)}">Search the archive</a></p>{lst}</div></section>')
    return frame(ctx, f'Page not found | {ctx["outlet"]["name"]}', inner)


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
