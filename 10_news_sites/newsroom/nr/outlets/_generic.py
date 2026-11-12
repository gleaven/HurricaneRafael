"""Fallback outlet template, and the reference implementation of the template contract
(see nr/common.py). Outlet modules named after the outlet slug replace it."""
from nr import common as C
from nr.common import esc

CSS = """
:root{--bg:#fafaf8;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e0da;--acc:#1f4e79;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--fg:#ecebe7;--muted:#a3a29c;--line:#34332f;--acc:#7fb0dd;--card:#1d1d1b}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 Georgia,serif}
.wrap{max-width:1100px;margin:0 auto;padding-inline:max(16px,env(safe-area-inset-left,0px)) max(16px,env(safe-area-inset-right,0px))}
header{border-bottom:3px double var(--line);padding-block:18px}
header a.name{font:700 34px/1.1 Georgia,serif;color:var(--fg);text-decoration:none}
.date{font:13px system-ui,sans-serif;color:var(--muted)}
nav{display:flex;flex-wrap:wrap;gap:4px 18px;font:600 14px system-ui,sans-serif;padding-block:10px;border-bottom:1px solid var(--line)}
nav a{color:var(--fg);text-decoration:none}
.alert{background:#8b1a1a;color:#fff;font:600 14px system-ui,sans-serif;padding:8px 12px;margin-top:12px;border-radius:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:22px;padding-block:22px}
.card{background:var(--card);border:1px solid var(--line);padding:16px;border-radius:6px;min-width:0}
.card h3{margin:.2em 0;font-size:19px;line-height:1.25}.card a{color:var(--fg);text-decoration:none}
.meta{font:13px system-ui,sans-serif;color:var(--muted)}
article.story{max-width:68ch;margin:28px auto}article.story h1{font-size:34px;line-height:1.15;text-wrap:balance}
.list li{margin-bottom:10px}
form.search input{padding:8px 10px;border:1px solid var(--line);border-radius:4px;font:inherit;background:var(--card);color:var(--fg)}
footer{border-top:1px solid var(--line);margin-top:40px;padding-block:20px;font:13px system-ui,sans-serif;color:var(--muted)}
"""


def frame(ctx, title, inner):
    o = ctx["outlet"]
    nav = "".join(f'<a href="{C.url_section(ctx, s["slug"])}">{esc(s["name"])}</a>' for s in o["sections"])
    alerts = "".join(f'<div class="alert">{esc(a["text"])}</div>' for a in ctx["status"]["alerts"])
    return (C.head(ctx, title, "", CSS) +
            f'<div id="nr-root"><div class="wrap"><header><a class="name" href="{C.url_home(ctx)}">{esc(o["name"])}</a>'
            f'<div class="date">{C.clock_span(ctx, "date-long")}</div></header>'
            f'<nav>{nav}<a href="{C.url_archive(ctx)}">Archive</a></nav>{alerts}{inner}'
            f'<footer>{esc(o["name"])} · {esc(o["kind"])} · All people and events are fictional.</footer></div></div>'
            + C.foot(ctx))


def card(ctx, a):
    return (f'<div class="card" data-article-id="{a["pid"]}"><div class="meta">{esc(a["section"])} · {C.ago_span(ctx, a)}</div>'
            f'<h3><a href="{a["url"]}">{esc(a["headline"])}</a></h3><p>{esc(C.excerpt(a, 30))}</p></div>')


def render(view, ctx, **kw):
    o = ctx["outlet"]
    if view == "home":
        items = ctx["articles"][:24]
        body = '<div class="grid">' + "".join(card(ctx, a) for a in items) + "</div>" if items else "<p>No stories yet.</p>"
        return frame(ctx, o["name"], body)
    if view == "section":
        sec = kw["section"]
        return frame(ctx, f'{sec["name"]} | {o["name"]}', f'<h2>{esc(sec["name"])}</h2><div class="grid">' +
                     "".join(card(ctx, a) for a in kw["items"]) + "</div>")
    if view == "article":
        a = kw["article"]
        rel = "".join(f'<li data-article-id="{r["pid"]}"><a href="{r["url"]}">{esc(r["headline"])}</a> <span class="meta">{esc(r["outlet_name"])}</span></li>' for r in kw["related"])
        return frame(ctx, f'{a["headline"]} | {o["name"]}',
                     f'<article class="story" data-article-id="{a["pid"]}"><div class="meta">{esc(a["section"])}</div>'
                     f'<h1>{esc(a["headline"])}</h1><p><em>{esc(a["summary"])}</em></p>'
                     f'<div class="meta">By {esc(C.byline(a))} · {esc(C.pub_label(a, o["lang"]))}</div>{C.paras(a["body"])}'
                     + (f'<h3>Related</h3><ul class="list">{rel}</ul>' if rel else "") + "</article>")
    if view == "archive":
        groups = C.group_by_day(kw["results"])
        out = [f'<form class="search" action="{C.url_archive(ctx)}"><input name="q" value="{esc(kw["q"])}" placeholder="Search"></form>']
        for d, items in groups:
            out.append(f"<h3>{esc(C.fmt_date_long(items[0]['ts']))}</h3><ul class='list'>")
            out += [f'<li data-article-id="{a["pid"]}"><a href="{a["url"]}">{esc(a["headline"])}</a></li>' for a in items]
            out.append("</ul>")
        return frame(ctx, f'Archive | {o["name"]}', "".join(out) or "<p>No results.</p>")
    return frame(ctx, f'Not found | {o["name"]}', "<h2>Page not found</h2><p>This page is not available.</p>")
