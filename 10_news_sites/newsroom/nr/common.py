"""Shared helpers for outlet templates.

Every outlet module in nr/outlets/ exposes:

    render(view, ctx, **kw) -> str      # a complete HTML document

    view == "home"      kw: none
    view == "section"   kw: section={"name","slug","count"}, items=[article, ...] newest first
    view == "article"   kw: article=article, related=[article, ...], newer=article|None, older=article|None
    view == "archive"   kw: q=str, date=str|None ("YYYY-MM-DD"), results=[article, ...], days=[(date_str, n), ...]
    view == "notfound"  kw: none

Contract every template must follow so live updates work:
  * build the page with head(ctx, title, fonts_href, css) + body + foot(ctx)
  * put everything that depends on the clock inside <div id="nr-root"> ... </div>
  * give each article card / list item / article page data-article-id="{a['pid']}"
  * show times with clock_span() / ago_span() so they tick between refreshes
  * use only the visible articles in ctx (never read the data files directly)

ctx keys
  outlet       {"id","slug","name","kind","site","lang","sections":[{"name","slug","count"}],"authors"}
  outlets      all outlets (same shape), for cross links
  now          effective scenario time for this outlet (UTC epoch seconds)
  articles     this outlet's visible articles, newest first
  visible      {pid: article} visible articles from every outlet
  status       {"port": {code,label,detail,ts}|None, "port_history": [...oldest first...],
                "alerts": [{"id","level","text","text_en","text_es","since","until"}],
                "broadcast": {"status","note","start","end"}|None}
  sig          content signature (used by live.js)

article keys
  pid, outlet, outlet_name, ts, published (ISO local), section, section_slug, authors, headline,
  summary, body [paragraph strings], story_type, storylines, people, places, topics, url, words
"""
import datetime as dt
import html
import json
import re
import urllib.parse

esc = html.escape

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]
AP_MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
ES_MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
             "octubre", "noviembre", "diciembre"]
ES_DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


# ---------------------------------------------------------------- time
def central_offset(ts):
    """US Central UTC offset (hours) at a UTC epoch: -5 during daylight time, -6 otherwise."""
    u = dt.datetime.utcfromtimestamp(ts)
    y = u.year

    def nth_sunday(month, n):
        d = dt.datetime(y, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)

    start = nth_sunday(3, 2) + dt.timedelta(hours=8)
    end = nth_sunday(11, 1) + dt.timedelta(hours=7)
    return -5 if start <= u < end else -6


def local(ts):
    off = central_offset(ts)
    return dt.datetime.fromtimestamp(ts, dt.timezone(dt.timedelta(hours=off)))


def tz_abbr(ts):
    return "CDT" if central_offset(ts) == -5 else "CST"


def fmt_date_long(ts):
    d = local(ts)
    return f"{DAYS[d.weekday()]}, {MONTHS[d.month - 1]} {d.day}, {d.year}"


def fmt_date_ap(ts):
    d = local(ts)
    return f"{AP_MONTHS[d.month - 1]} {d.day}, {d.year}"


def fmt_date_short(ts):
    d = local(ts)
    return f"{AP_MONTHS[d.month - 1]} {d.day}"


def fmt_time_ap(ts, tz=True):
    d = local(ts)
    h = d.hour % 12 or 12
    ap = "a.m." if d.hour < 12 else "p.m."
    t = "noon" if (d.hour, d.minute) == (12, 0) else ("midnight" if (d.hour, d.minute) == (0, 0) else f"{h}:{d.minute:02d} {ap}")
    return f"{t} {tz_abbr(ts)}" if tz else t


def fmt_dt_ap(ts):
    return f"{fmt_date_ap(ts)}, {fmt_time_ap(ts)}"


def fmt_time_24(ts):
    d = local(ts)
    return f"{d.hour:02d}:{d.minute:02d} {tz_abbr(ts)}"


def fmt_date_es(ts):
    d = local(ts)
    return f"{ES_DAYS[d.weekday()]}, {d.day} de {ES_MONTHS[d.month - 1]} de {d.year}"


def fmt_time_es(ts):
    d = local(ts)
    h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'a.m.' if d.hour < 12 else 'p.m.'}"


def ago(ts, now, lang="en"):
    s = max(0, int(now - ts))
    if lang == "es":
        if s < 60: return "hace un momento"
        if s < 3600: return f"hace {s // 60} min"
        if s < 86400: return f"hace {s // 3600} h"
        if s < 172800: return "ayer"
        return fmt_date_es(ts).split(", ", 1)[1]
    if s < 60: return "just now"
    if s < 3600: return f"{s // 60} min ago"
    if s < 86400:
        h = s // 3600
        return f"{h} hour{'s' if h > 1 else ''} ago"
    if s < 172800: return "Yesterday"
    return fmt_date_ap(ts)


# ------------------------------------------------------------ live elements
def clock_span(ctx, fmt, cls=""):
    """Text that tracks the scenario clock. fmt: date-long | date-ap | time-ap | time-24 | date-es | time-es | datetime-ap"""
    f = {"date-long": fmt_date_long, "date-ap": fmt_date_ap, "time-ap": fmt_time_ap, "time-24": fmt_time_24,
         "date-es": fmt_date_es, "time-es": fmt_time_es, "datetime-ap": fmt_dt_ap}[fmt]
    c = f' class="{cls}"' if cls else ""
    return f'<span data-nr-clock="{fmt}"{c}>{esc(f(ctx["now"]))}</span>'


def ago_span(ctx, a, cls=""):
    lang = ctx["outlet"].get("lang", "en")
    c = f' class="{cls}"' if cls else ""
    return (f'<time datetime="{esc(a["published"])}" data-nr-ago="{a["ts"]}" data-nr-lang="{lang}"{c}>'
            f'{esc(ago(a["ts"], ctx["now"], lang))}</time>')


# ------------------------------------------------------------ text helpers
def paras(body):
    return "".join(f"<p>{esc(p)}</p>" for p in body)


def excerpt(a, words=40):
    text = a.get("summary") or (a["body"][0] if a["body"] else "")
    w = text.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def byline(a, joiner=" and "):
    names = a.get("authors") or []
    if len(names) <= 2:
        return joiner.join(names)
    return ", ".join(names[:-1]) + "," + joiner + names[-1]


def read_minutes(a):
    return max(1, round(a.get("words", 300) / 230))


def wire_slug(a):
    words = []
    for t in a.get("topics", [])[:3]:
        words.append(re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").upper())
    slug = "-".join(w for w in words if w)
    if len(slug) > 48:
        slug = slug[:48].rsplit("-", 1)[0]
    return slug or "CORPUS-CHRISTI"


def is_breaking(a):
    return a.get("story_type") == "breaking"


def recent(ctx, hours):
    """Visible articles of this outlet published within the last N scenario hours."""
    return [a for a in ctx["articles"] if ctx["now"] - a["ts"] <= hours * 3600]


def by_section(ctx, name):
    return [a for a in ctx["articles"] if a["section"] == name]


def group_by_day(articles):
    out, cur, key = [], None, None
    for a in articles:
        k = local(a["ts"]).date().isoformat()
        if k != key:
            cur, key = [], k
            out.append((k, cur))
        cur.append(a)
    return out


# ------------------------------------------------------------ urls
def url_home(ctx): return f"/{ctx['outlet']['slug']}/"
def url_section(ctx, slug): return f"/{ctx['outlet']['slug']}/section/{slug}/"
def url_archive(ctx, q=None, date=None):
    u = f"/{ctx['outlet']['slug']}/archive/"
    p = []
    if q: p.append("q=" + urllib.parse.quote_plus(q))
    if date: p.append("date=" + urllib.parse.quote_plus(date))
    return u + ("?" + "&amp;".join(p) if p else "")
def url_rss(ctx): return f"/{ctx['outlet']['slug']}/rss.xml"


# ------------------------------------------------------------ page frame
BASE_CSS = """
*,*::before,*::after{box-sizing:border-box}
img{max-width:100%}
.nr-new{animation:nrflash 2.4s ease-out 1;position:relative}
@keyframes nrflash{0%{box-shadow:0 0 0 3px #f5b301;background-color:rgba(245,179,1,.18)}100%{box-shadow:0 0 0 0 rgba(245,179,1,0);background-color:transparent}}
.nr-new-badge{display:inline-block;font:700 10px/1 system-ui,sans-serif;letter-spacing:.08em;background:#f5b301;color:#111;
  padding:3px 6px;border-radius:3px;margin-right:6px;vertical-align:middle;text-transform:uppercase}
#nr-toast{position:fixed;left:50%;bottom:calc(18px + env(safe-area-inset-bottom,0px));transform:translateX(-50%) translateY(140%);
  background:#111;color:#fff;font:600 14px/1.2 system-ui,sans-serif;padding:11px 18px;border-radius:999px;
  box-shadow:0 6px 24px rgba(0,0,0,.3);transition:transform .35s ease;z-index:9999;cursor:pointer;max-width:calc(100% - 32px)}
#nr-toast.show{transform:translateX(-50%) translateY(0)}
.nr-visually-hidden{position:absolute!important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
"""


def head(ctx, title, fonts_href, css):
    o = ctx["outlet"]
    fonts = f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="{esc(fonts_href)}">' if fonts_href else ""
    return (f'<!doctype html><html lang="{o.get("lang", "en")}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<title>{esc(title)}</title>'
            f'<link rel="alternate" type="application/rss+xml" title="{esc(o["name"])}" href="{url_rss(ctx)}">'
            f'{fonts}<style>{BASE_CSS}{css}</style></head><body>')


def foot(ctx):
    cfg = {"outlet": ctx["outlet"]["slug"], "sig": ctx["sig"], "now": ctx["now"], "lang": ctx["outlet"].get("lang", "en")}
    return (f'<div id="nr-toast" role="status" aria-live="polite"></div>'
            f'<script id="nr-config" type="application/json">{json.dumps(cfg)}</script>'
            f'<script src="/static/live.js" defer></script></body></html>')


def pub_label(a, lang="en"):
    if lang == "es":
        return f"{fmt_date_es(a['ts'])}, {fmt_time_es(a['ts'])}"
    return fmt_dt_ap(a["ts"])
