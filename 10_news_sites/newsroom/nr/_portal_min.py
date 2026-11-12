"""Minimal newsstand used until nr/portal.py exists."""
import json
from nr import common as C
from nr.common import esc


def _page(ctx, title, inner):
    cfg = {"outlet": "_all", "sig": ctx["sig"], "now": ctx["now"], "lang": "en"}
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{C.BASE_CSS} body{{font:16px/1.5 system-ui,sans-serif;margin:0;padding:24px max(16px,env(safe-area-inset-left,0px))}}</style></head>'
            f'<body><div id="nr-root">{inner}</div><div id="nr-toast"></div>'
            f'<script id="nr-config" type="application/json">{json.dumps(cfg)}</script><script src="/static/live.js" defer></script></body></html>')


def render_portal(ctx):
    rows = "".join(f'<li><a href="/{o["slug"]}/">{esc(o["name"])}</a> ({o["visible"]})</li>' for o in ctx["outlets"])
    return _page(ctx, "Coastal Bend Newsstand", f"<h1>Coastal Bend Newsstand</h1><p>{esc(C.fmt_dt_ap(ctx['now']))}</p><ul>{rows}</ul>")


def render_feeds(ctx):
    return _page(ctx, "Data Feeds", "<h1>Feeds</h1><p>/api/articles, /&lt;outlet&gt;/rss.xml, /rss/all.xml</p>")


def render_notfound(ctx):
    return _page(ctx, "Not Found", "<h1>Not found</h1><p><a href='/'>Newsstand</a></p>")
