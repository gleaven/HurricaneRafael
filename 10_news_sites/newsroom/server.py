"""Coastal Bend Newsroom: time-gated news sites for the Hurricane Rafael exercise.

    python server.py           this computer only     http://localhost:8080
    python server.py --lan     shared network         http://<this computer's IP>:8080

Options
    --port N            port to listen on (default 8080)
    --passphrase TEXT   game-master passphrase (saved to config.json)
    --reset             start the scenario clock over
    --dev               reload outlet templates on every request (template work)

The scenario clock lives on this server. Every page, RSS feed and API response only contains
articles published at or before the clock, so nothing ahead of the clock ever reaches a browser.
Game-master pages (/control, /explorer) need the passphrase unless opened on this computer.
Requires Python 3.8+ and nothing else.
"""
import argparse
import bisect
import datetime as dt
import hashlib
import hmac
import html
import importlib
import json
import os
import secrets
import socket
import sys
import threading
import time
import traceback
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import build_data  # noqa: E402
from nr import common as C  # noqa: E402

DATA = os.path.join(HERE, "data")
STATIC = os.path.join(HERE, "static")
STATE_DIR = os.path.join(HERE, "state")
CONFIG_PATH = os.path.join(HERE, "config.json")
DEFAULT_CONFIG = {"port": 8080, "gm_passphrase": "", "local_gm_without_passphrase": True, "poll_ms": 1500}
PUBLIC_FIELDS = ("pid", "outlet", "outlet_name", "ts", "published", "section", "section_slug", "authors",
                 "headline", "summary", "body", "story_type", "storylines", "people", "places", "topics",
                 "url", "words")
D0 = dt.date(2027, 9, 14)
DEV = False


# ======================================================================================
# corpus
# ======================================================================================
class Corpus:
    def __init__(self):
        with open(os.path.join(DATA, "articles.json"), encoding="utf-8") as fh:
            blob = json.load(fh)
        self.meta = blob["meta"]
        self.articles = blob["articles"]
        self.outlets = json.load(open(os.path.join(DATA, "outlets.json"), encoding="utf-8"))
        self.milestones = json.load(open(os.path.join(DATA, "milestones.json"), encoding="utf-8"))
        self.status = json.load(open(os.path.join(DATA, "status.json"), encoding="utf-8"))
        self.outlet = {o["slug"]: o for o in self.outlets}
        names = {o["slug"]: o["name"] for o in self.outlets}
        for a in self.articles:
            # opaque public id: scenario story ids encode the day relative to landfall
            a["pid"] = hashlib.sha1(("coastal-bend-newsroom:" + a["id"]).encode()).hexdigest()[:12]
            a["outlet_name"] = names[a["outlet"]]
            a["view"] = {k: a[k] for k in PUBLIC_FIELDS}
        self.articles.sort(key=lambda a: (a["ts"], a["id"]))
        self.by_id = {a["id"]: a for a in self.articles}
        self.by_pid = {a["pid"]: a for a in self.articles}
        self.by_url = {a["url"]: a for a in self.articles}
        self.by_outlet = {o["slug"]: [a for a in self.articles if a["outlet"] == o["slug"]] for o in self.outlets}
        self.ts_by_outlet = {k: [a["ts"] for a in v] for k, v in self.by_outlet.items()}
        self.start = self.milestones[0]["ts"] if self.milestones else self.meta["first_ts"] - 3600
        self.end = self.meta["last_ts"] + 86400
        self.all_ts = [a["ts"] for a in self.articles]

    def status_at(self, slug, t):
        st = self.status
        port_hist = [p for p in st["port"] if p["ts"] <= t]
        lang = self.outlet[slug].get("lang", "en") if slug in self.outlet else "en"
        alerts = []
        for a in st["alerts"]:
            start = a["start_es"] if lang == "es" else a["start_en"]
            if start <= t < a["end"]:
                alerts.append({"id": a["id"], "level": a["level"], "text": a["es"] if lang == "es" else a["en"],
                               "text_en": a["en"], "text_es": a["es"], "since": start, "until": a["end"]})
        bc = None
        for b in st["broadcast"].get(slug, []):
            if b["start"] <= t < b["end"]:
                bc = dict(b)
        return {"port": port_hist[-1] if port_hist else None, "port_history": port_hist, "alerts": alerts,
                "broadcast": bc}


def d_label(ts):
    d = C.local(ts)
    n = (d.date() - D0).days
    return f"D{'+' if n >= 0 else '-'}{abs(n)} {d.hour:02d}:{d.minute:02d} {C.tz_abbr(ts)}"


# ======================================================================================
# clock
# ======================================================================================
class Clock:
    def __init__(self, corpus, reset=False, persist=True):
        self.c = corpus
        self.persist = persist
        self.lock = threading.RLock()
        self.now = corpus.start
        self.playing = False
        self.rate = 3600.0           # scenario seconds per real second
        self.pause_on_breaking = False
        self.holds = {}              # outlet slug -> scenario ts the hold began
        self.forced = set()          # article ids released early
        self.log = []
        self.seq = 0
        self._last_save = 0
        self.path = os.path.join(STATE_DIR, "clock.json")
        if not reset and os.path.exists(self.path):
            try:
                s = json.load(open(self.path, encoding="utf-8"))
                self.now = float(s.get("now", self.now))
                self.rate = float(s.get("rate", self.rate))
                self.pause_on_breaking = bool(s.get("pause_on_breaking", False))
                self.holds = {k: float(v) for k, v in s.get("holds", {}).items()}
                self.forced = set(s.get("forced", []))
                self.log = s.get("log", [])[-300:]
            except Exception:
                print("  (could not read saved clock; starting fresh)")
        self.now = min(max(self.now, corpus.start), corpus.end)

    # ------------------------------------------------------------ persistence
    def save(self, force=False):
        if not self.persist:
            return
        if not force and time.time() - self._last_save < 3:
            return
        self._last_save = time.time()
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"now": self.now, "rate": self.rate, "pause_on_breaking": self.pause_on_breaking,
                       "holds": self.holds, "forced": sorted(self.forced), "log": self.log[-300:]}, fh)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------ visibility
    def eff(self, slug, now=None):
        t = self.now if now is None else now
        h = self.holds.get(slug)
        return min(t, h) if h is not None else t

    def visible_list(self, slug, now=None):
        """This outlet's visible articles, oldest first."""
        e = self.eff(slug, now)
        arts = self.c.by_outlet.get(slug, [])
        n = bisect.bisect_right(self.c.ts_by_outlet.get(slug, []), e)
        out = arts[:n]
        extra = [a for a in arts[n:] if a["id"] in self.forced]
        return out + extra if extra else out

    def is_visible(self, a, now=None):
        return a["ts"] <= self.eff(a["outlet"], now) or a["id"] in self.forced

    def sig(self, slug, now=None):
        if slug == "_all":
            return hashlib.md5("|".join(self.sig(o["slug"], now) for o in self.c.outlets).encode()).hexdigest()[:12]
        e = self.eff(slug, now)
        n = bisect.bisect_right(self.c.ts_by_outlet.get(slug, []), e)
        extra = sorted(i for i in self.forced if self.c.by_id.get(i, {}).get("outlet") == slug)
        st = self.c.status_at(slug, e)
        raw = "|".join([str(n), ",".join(extra), (st["port"] or {}).get("code", ""),
                        ",".join(a["id"] for a in st["alerts"]), (st["broadcast"] or {}).get("status", ""),
                        str(int(e // 21600))])
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    # ------------------------------------------------------------ changes
    def _released(self, old_now, new_now, old_holds):
        items = []
        for o in self.c.outlets:
            s = o["slug"]
            h_old, h_new = old_holds.get(s), self.holds.get(s)
            e_old = min(old_now, h_old) if h_old is not None else old_now
            e_new = min(new_now, h_new) if h_new is not None else new_now
            if e_new > e_old:
                ts = self.c.ts_by_outlet[s]
                lo, hi = bisect.bisect_right(ts, e_old), bisect.bisect_right(ts, e_new)
                items += [a for a in self.c.by_outlet[s][lo:hi] if a["id"] not in self.forced]
        items.sort(key=lambda a: a["ts"])
        return items

    def _log(self, kind, items=(), note=""):
        self.log.append({"wall": dt.datetime.now().strftime("%H:%M:%S"), "scen": self.now, "d": d_label(self.now),
                         "kind": kind, "note": note, "count": len(items),
                         "items": [{"id": a["id"], "outlet": a["outlet"], "headline": a["headline"],
                                    "story_type": a["story_type"]} for a in list(items)[-25:]]})
        self.log = self.log[-300:]

    def _bump(self, force_save=True):
        self.seq += 1
        self.save(force=force_save)

    def set_time(self, t, kind="set", note=""):
        with self.lock:
            t = min(max(float(t), self.c.start), self.c.end)
            old, old_holds = self.now, dict(self.holds)
            self.now = t
            if t < old:
                self._log("rewind", note=note or f"back to {d_label(t)}")
            else:
                rel = self._released(old, t, old_holds)
                if rel or kind not in ("set", "tick"):
                    self._log("release" if kind == "tick" else kind, rel, note)
            self._bump(force_save=(kind != "tick"))

    def step(self, seconds):
        self.set_time(self.now + float(seconds), "step", f"{'+' if seconds >= 0 else ''}{fmt_span(seconds)}")

    def next_article(self, slug=None):
        with self.lock:
            cands = []
            for o in self.c.outlets:
                s = o["slug"]
                if (slug and s != slug) or s in self.holds:
                    continue
                ts = self.c.ts_by_outlet[s]
                i = bisect.bisect_right(ts, self.now)
                while i < len(ts) and self.c.by_outlet[s][i]["id"] in self.forced:
                    i += 1
                if i < len(ts):
                    cands.append(ts[i])
            if not cands:
                return False
            self.set_time(min(cands), "next", f"next {self.c.outlet[slug]['name'] if slug else 'article'}")
            return True

    def tick(self, real_dt):
        with self.lock:
            if not self.playing:
                return
            target = self.now + self.rate * real_dt
            note = ""
            if self.pause_on_breaking:
                i = bisect.bisect_right(self.c.all_ts, self.now)
                while i < len(self.c.all_ts) and self.c.all_ts[i] <= target:
                    a = self.c.articles[i]
                    if a["story_type"] == "breaking" and a["outlet"] not in self.holds and a["id"] not in self.forced:
                        target, note = a["ts"], "paused on breaking story"
                        break
                    i += 1
            if target >= self.c.end:
                target, note = self.c.end, "end of scenario"
            self.set_time(target, "tick")
            if note:
                self.playing = False
                self._log("pause", note=note)
                self._bump()

    def play(self, rate=None):
        with self.lock:
            if rate:
                self.rate = max(1.0, float(rate))
            self.playing = True
            self._log("play", note=f"{fmt_span(self.rate)} per second")
            self._bump()

    def pause(self):
        with self.lock:
            self.playing = False
            self._log("pause")
            self._bump()

    def hold(self, slug, on):
        with self.lock:
            if slug not in self.c.outlet:
                return
            if on and slug not in self.holds:
                self.holds[slug] = self.now
                self._log("hold", note=f"holding {self.c.outlet[slug]['name']}")
            elif not on and slug in self.holds:
                old_holds = dict(self.holds)
                del self.holds[slug]
                rel = self._released(self.now, self.now, old_holds)
                self._log("unhold", rel, f"released hold on {self.c.outlet[slug]['name']}")
            self._bump()

    def release(self, article_id):
        with self.lock:
            a = self.c.by_id.get(article_id)
            if not a or self.is_visible(a):
                return
            self.forced.add(article_id)
            self._log("forced", [a], "released early")
            self._bump()

    def reset(self):
        with self.lock:
            self.now, self.playing, self.holds, self.forced = self.c.start, False, {}, set()
            self.log = []
            self._log("reset", note="clock reset to scenario start")
            self._bump()


def fmt_span(sec):
    sec = abs(float(sec))
    if sec >= 86400 and sec % 86400 == 0: return f"{int(sec // 86400)} day{'s' if sec >= 172800 else ''}"
    if sec >= 3600 and sec % 3600 == 0: return f"{int(sec // 3600)} h"
    if sec >= 60: return f"{int(sec // 60)} min"
    return f"{int(sec)} s"


def ticker(clock):
    last = time.time()
    while True:
        time.sleep(0.25)
        now = time.time()
        try:
            clock.tick(now - last)
        except Exception:
            traceback.print_exc()
        last = now


# ======================================================================================
# rendering
# ======================================================================================
_modules = {}


def outlet_module(slug):
    name = "nr.outlets." + slug.replace("-", "_")
    try:
        if name in _modules and not DEV:
            return _modules[name]
        mod = importlib.import_module(name)
        if DEV:
            importlib.reload(C)
            mod = importlib.reload(mod)
    except ModuleNotFoundError:
        mod = importlib.import_module("nr.outlets._generic")
    _modules[name] = mod
    return mod


def outlet_ctx(slug, clock, now=None):
    c = clock.c
    with clock.lock:
        e = clock.eff(slug, now)
        mine = clock.visible_list(slug, now)
        vis_all = {}
        for o in c.outlets:
            for a in clock.visible_list(o["slug"], now):
                vis_all[a["pid"]] = a["view"]
        sig = clock.sig(slug, now)
    return {"outlet": c.outlet[slug], "outlets": c.outlets, "now": int(e),
            "articles": [a["view"] for a in sorted(mine, key=lambda a: a["ts"], reverse=True)],
            "visible": vis_all, "status": c.status_at(slug, e), "sig": sig}


def search(views, q):
    terms = [t for t in q.lower().split() if t]
    if not terms:
        return views
    out = []
    for a in views:
        hay = " ".join([a["headline"], a["summary"], " ".join(a["body"]), " ".join(a["topics"]),
                        " ".join(a["people"]), " ".join(a["places"]), " ".join(a["authors"])]).lower()
        if all(t in hay for t in terms):
            out.append(a)
    return out


def render_outlet(slug, path, query, clock, now=None):
    """Return (status, html) for an outlet path such as /ledger/section/local/."""
    c = clock.c
    ctx = outlet_ctx(slug, clock, now)
    mod = outlet_module(slug)
    rest = path[len(slug) + 2:].strip("/")
    parts = rest.split("/") if rest else []
    try:
        if not parts:
            return 200, mod.render("home", ctx)
        if parts[0] == "section" and len(parts) == 2:
            sec = next((s for s in ctx["outlet"]["sections"] if s["slug"] == parts[1]), None)
            if sec:
                items = [a for a in ctx["articles"] if a["section"] == sec["name"]]
                return 200, mod.render("section", ctx, section=sec, items=items)
        if parts[0] == "archive" and len(parts) == 1:
            q = (query.get("q", [""])[0] or "").strip()[:120]
            date = (query.get("date", [""])[0] or "").strip()[:10] or None
            res = search(ctx["articles"], q)
            if date:
                res = [a for a in res if C.local(a["ts"]).date().isoformat() == date]
            days = [(d, len(items)) for d, items in C.group_by_day(ctx["articles"])]
            return 200, mod.render("archive", ctx, q=q, date=date, results=res, days=days)
        a = c.by_url.get("/" + slug + "/" + rest)
        if a and a["pid"] in ctx["visible"]:
            mine = ctx["articles"]
            i = next(k for k, v in enumerate(mine) if v["pid"] == a["pid"])
            rel_ids = []
            for rid in ([a["follows_up"]] if a["follows_up"] else []) + a["related"] + a["arc_links"]:
                r = c.by_id.get(rid)
                if r and r["pid"] in ctx["visible"] and r["pid"] not in rel_ids and r["pid"] != a["pid"]:
                    rel_ids.append(r["pid"])
            related = [ctx["visible"][p] for p in rel_ids][:6]
            return 200, mod.render("article", ctx, article=a["view"], related=related,
                                   newer=mine[i - 1] if i > 0 else None,
                                   older=mine[i + 1] if i + 1 < len(mine) else None)
        return 404, mod.render("notfound", ctx)
    except Exception:
        traceback.print_exc()
        return 500, "<h1>Template error</h1><pre>" + html.escape(traceback.format_exc()) + "</pre>"


def public_article(a, visible_pids, clock):
    v = dict(a["view"])
    v["id"] = v.pop("pid")
    v["related"] = [clock.c.by_id[r]["pid"] for r in a["related"] if clock.c.by_id[r]["pid"] in visible_pids]
    v["published_utc"] = dt.datetime.utcfromtimestamp(a["ts"]).isoformat() + "Z"
    del v["ts"]
    return v


def rss_xml(items, title, link, desc, host, now, lang="en-us"):
    def rfc822(ts):
        return C.local(ts).strftime("%a, %d %b %Y %H:%M:%S %z")
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="http://purl.org/dc/elements/1.1/">',
           "<channel>", f"<title>{html.escape(title)}</title>", f"<link>{html.escape(link)}</link>",
           f"<description>{html.escape(desc)}</description>", f"<language>{lang}</language>",
           f"<lastBuildDate>{rfc822(now)}</lastBuildDate>"]
    for a in items:
        body = "".join(f"<p>{html.escape(p)}</p>" for p in a["body"]).replace("]]>", "]]&gt;")
        out += ["<item>", f"<title>{html.escape(a['headline'])}</title>",
                f"<link>http://{html.escape(host)}{a['url']}</link>",
                f'<guid isPermaLink="false">{a["pid"]}</guid>', f"<pubDate>{rfc822(a['ts'])}</pubDate>",
                f"<dc:creator>{html.escape(', '.join(a['authors']))}</dc:creator>",
                f"<source url=\"http://{html.escape(host)}/{a['outlet']}/rss.xml\">{html.escape(a['outlet_name'])}</source>",
                f"<category>{html.escape(a['section'])}</category>"]
        out += [f"<category>{html.escape(s)}</category>" for s in a["storylines"]]
        out += [f"<description>{html.escape(a['summary'])}</description>",
                f"<content:encoded><![CDATA[{body}]]></content:encoded>", "</item>"]
    out += ["</channel>", "</rss>"]
    return "\n".join(out)


# ======================================================================================
# HTTP
# ======================================================================================
class App:
    clock = None
    config = None
    token = None


class Handler(BaseHTTPRequestHandler):
    server_version = "CoastalBendNewsroom/1.0"

    def log_message(self, fmt, *args):
        pass

    # ------------------------------------------------------------ helpers
    def send(self, status, body, ctype="text/html; charset=utf-8", headers=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def json(self, obj, status=200):
        self.send(status, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def redirect(self, to, headers=None):
        h = {"Location": to}
        h.update(headers or {})
        self.send(303, "", headers=h)

    def is_gm(self):
        ip = self.client_address[0]
        if App.config.get("local_gm_without_passphrase", True) and ip in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            return True
        c = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        tok = c.get("nr_gm")
        return bool(tok and App.token and hmac.compare_digest(tok.value, App.token))

    def host(self):
        return self.headers.get("Host") or f"localhost:{App.config['port']}"

    def body_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(n, 100000)) if n else b""
        try:
            return json.loads(raw or b"{}")
        except Exception:
            return {}

    # ------------------------------------------------------------ dispatch
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            self.route_get()
        except BrokenPipeError:
            pass
        except Exception:
            traceback.print_exc()
            self.send(500, "Server error")

    def do_POST(self):
        try:
            self.route_post()
        except Exception:
            traceback.print_exc()
            self.send(500, "Server error")

    def route_get(self):
        u = urllib.parse.urlsplit(self.path)
        path, q = urllib.parse.unquote(u.path), urllib.parse.parse_qs(u.query)
        clock, c = App.clock, App.clock.c

        if path == "/" or path == "/index.html":
            return self.send(200, portal_module().render_portal(portal_ctx(clock, self.host())))
        if path == "/feeds":
            return self.send(200, portal_module().render_feeds(portal_ctx(clock, self.host())))
        if path.startswith("/static/"):
            return self.static(path[8:])
        if path == "/favicon.ico":
            return self.send(204, "")

        # ---------------- public API (always time-gated)
        if path == "/api/clock":
            slug = (q.get("outlet", [""])[0])
            with clock.lock:
                out = {"now": int(clock.now), "local": C.fmt_dt_ap(clock.now), "playing": clock.playing,
                       "poll_ms": App.config.get("poll_ms", 1500)}
                if slug in c.outlet or slug == "_all":
                    out["outlet_now"] = int(clock.eff(slug)) if slug in c.outlet else int(clock.now)
                    out["sig"] = clock.sig(slug)
            return self.json(out)
        if path == "/api/outlets":
            with clock.lock:
                return self.json({"outlets": [{"slug": o["slug"], "name": o["name"], "kind": o["kind"],
                                               "lang": o["lang"], "home": f"/{o['slug']}/",
                                               "rss": f"/{o['slug']}/rss.xml",
                                               "visible": len(clock.visible_list(o["slug"]))} for o in c.outlets]})
        if path == "/api/articles":
            return self.api_articles(q)
        if path.startswith("/api/articles/"):
            a = c.by_pid.get(path.rsplit("/", 1)[-1])
            with clock.lock:
                ok = a and clock.is_visible(a)
                vis = {x["pid"] for o in c.outlets for x in clock.visible_list(o["slug"])} if ok else set()
            return self.json(public_article(a, vis, clock)) if ok else self.json({"error": "not found"}, 404)
        if path == "/rss/all.xml":
            with clock.lock:
                items = sorted([a for o in c.outlets for a in clock.visible_list(o["slug"])],
                               key=lambda a: a["ts"], reverse=True)[:100]
                now = clock.now
            return self.send(200, rss_xml(items, "Coastal Bend News: all outlets", f"http://{self.host()}/",
                                          "Latest stories from every Coastal Bend outlet", self.host(), now),
                             "application/rss+xml; charset=utf-8")

        # ---------------- game master
        if path == "/gm/login":
            return self.send(200, login_page(q.get("next", ["/control"])[0], q.get("err", [""])[0]))
        if path == "/gm/logout":
            return self.redirect("/", {"Set-Cookie": "nr_gm=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
        if path in ("/control", "/explorer") or path.startswith("/api/gm/"):
            if not self.is_gm():
                if path.startswith("/api/"):
                    return self.json({"error": "game master login required"}, 401)
                return self.redirect("/gm/login?next=" + urllib.parse.quote(path))
            if path == "/control":
                return self.static("control.html")
            if path == "/explorer":
                return self.static("explorer.html")
            if path == "/api/gm/state":
                return self.json(gm_state(clock))
            if path == "/api/gm/articles":
                return self.json(gm_articles(clock))
            return self.json({"error": "unknown"}, 404)

        # ---------------- outlets
        slug = path.strip("/").split("/")[0]
        if slug in c.outlet:
            if path == f"/{slug}":
                return self.redirect(f"/{slug}/")
            if path == f"/{slug}/rss.xml":
                with clock.lock:
                    items = sorted(clock.visible_list(slug), key=lambda a: a["ts"], reverse=True)[:50]
                    now = clock.eff(slug)
                o = c.outlet[slug]
                return self.send(200, rss_xml(items, o["name"], f"http://{self.host()}/{slug}/", o["kind"],
                                              self.host(), now, "es-us" if o["lang"] == "es" else "en-us"),
                                 "application/rss+xml; charset=utf-8")
            status, page = render_outlet(slug, path, q, clock)
            return self.send(status, page)
        return self.send(404, portal_module().render_notfound(portal_ctx(clock, self.host())))

    def route_post(self):
        path = urllib.parse.urlsplit(self.path).path
        clock = App.clock
        if path == "/gm/login":
            n = int(self.headers.get("Content-Length") or 0)
            form = urllib.parse.parse_qs(self.rfile.read(min(n, 10000)).decode("utf-8", "replace"))
            pw = form.get("passphrase", [""])[0]
            nxt = form.get("next", ["/control"])[0]
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = "/control"
            if App.config.get("gm_passphrase") and hmac.compare_digest(pw, App.config["gm_passphrase"]):
                return self.redirect(nxt, {"Set-Cookie": f"nr_gm={App.token}; Path=/; HttpOnly; SameSite=Lax"})
            time.sleep(1.0)
            return self.redirect("/gm/login?err=1&next=" + urllib.parse.quote(nxt))
        if path == "/api/gm/action":
            if not self.is_gm():
                return self.json({"error": "game master login required"}, 401)
            act = self.body_json()
            gm_action(clock, act)
            return self.json(gm_state(clock))
        return self.send(404, "Not found")

    def api_articles(self, q):
        clock, c = App.clock, App.clock.c
        slug = q.get("outlet", ["all"])[0]
        limit = max(1, min(500, int((q.get("limit", ["50"])[0] or 50))))
        offset = max(0, int((q.get("offset", ["0"])[0] or 0)))
        since = q.get("since", [""])[0]
        with clock.lock:
            slugs = [slug] if slug in c.outlet else [o["slug"] for o in c.outlets]
            arts = sorted([a for s in slugs for a in clock.visible_list(s)], key=lambda a: a["ts"], reverse=True)
            vis = {x["pid"] for o in c.outlets for x in clock.visible_list(o["slug"])}
            now = clock.now
        if since:
            try:
                t = float(since) if since.replace(".", "").isdigit() else dt.datetime.fromisoformat(since.replace("Z", "+00:00")).timestamp()
                arts = [a for a in arts if a["ts"] > t]
            except ValueError:
                pass
        sq = q.get("q", [""])[0]
        if sq:
            keep = {v["pid"] for v in search([a["view"] for a in arts], sq)}
            arts = [a for a in arts if a["pid"] in keep]
        page = arts[offset:offset + limit]
        return self.json({"as_of": C.local(now).isoformat(), "total": len(arts), "offset": offset,
                          "articles": [public_article(a, vis, clock) for a in page]})

    def static(self, name):
        name = os.path.normpath(name).replace("\\", "/")
        if name.startswith("..") or name.startswith("/"):
            return self.send(404, "Not found")
        fp = os.path.join(STATIC, name)
        if not os.path.isfile(fp):
            return self.send(404, "Not found")
        ext = os.path.splitext(fp)[1].lower()
        ctype = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".html": "text/html; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
                 ".json": "application/json"}.get(ext, "application/octet-stream")
        with open(fp, "rb") as fh:
            return self.send(200, fh.read(), ctype)


# ======================================================================================
# game master
# ======================================================================================
def gm_action(clock, act):
    a = act.get("action")
    if a == "set" and "ts" in act:
        clock.set_time(float(act["ts"]), "jump", act.get("note", ""))
    elif a == "step":
        clock.step(float(act.get("seconds", 3600)))
    elif a == "next":
        clock.next_article(act.get("outlet") or None)
    elif a == "milestone":
        i = int(act.get("index", -1))
        if 0 <= i < len(clock.c.milestones):
            m = clock.c.milestones[i]
            clock.set_time(m["ts"], "jump", m["label"])
    elif a == "play":
        clock.play(act.get("rate"))
    elif a == "pause":
        clock.pause()
    elif a == "rate":
        with clock.lock:
            clock.rate = max(1.0, float(act.get("rate", 3600)))
            clock._bump()
    elif a == "hold":
        clock.hold(act.get("outlet"), bool(act.get("on")))
    elif a == "release":
        clock.release(act.get("id"))
    elif a == "pause_on_breaking":
        with clock.lock:
            clock.pause_on_breaking = bool(act.get("on"))
            clock._bump()
    elif a == "reset":
        clock.reset()


def gm_state(clock):
    c = clock.c
    with clock.lock:
        outlets = []
        for o in c.outlets:
            vis = clock.visible_list(o["slug"])
            last = vis[-1] if vis else None
            ts = c.ts_by_outlet[o["slug"]]
            i = bisect.bisect_right(ts, clock.eff(o["slug"]))
            nxt = next((x for x in c.by_outlet[o["slug"]][i:] if x["id"] not in clock.forced), None)
            outlets.append({"slug": o["slug"], "name": o["name"], "kind": o["kind"], "lang": o["lang"],
                            "visible": len(vis), "total": o["count"], "held": o["slug"] in clock.holds,
                            "held_since": d_label(clock.holds[o["slug"]]) if o["slug"] in clock.holds else None,
                            "last": {"headline": last["headline"], "d": d_label(last["ts"]), "url": last["url"]} if last else None,
                            "next": {"headline": nxt["headline"], "d": d_label(nxt["ts"]), "ts": nxt["ts"]} if nxt else None,
                            "status": c.status_at(o["slug"], clock.eff(o["slug"]))["broadcast"]})
        upcoming = []
        for a in c.articles[bisect.bisect_right(c.all_ts, clock.now - 1):]:
            if not clock.is_visible(a):
                upcoming.append({"id": a["id"], "outlet": a["outlet"], "outlet_name": a["outlet_name"], "ts": a["ts"],
                                 "d": d_label(a["ts"]), "local": C.fmt_dt_ap(a["ts"]), "headline": a["headline"],
                                 "story_type": a["story_type"], "section": a["section"],
                                 "held": a["outlet"] in clock.holds})
            if len(upcoming) >= 20:
                break
        # outlets on hold have older unreleased stories too
        for s, h in clock.holds.items():
            for a in c.by_outlet[s]:
                if h < a["ts"] <= clock.now and a["id"] not in clock.forced:
                    upcoming.append({"id": a["id"], "outlet": s, "outlet_name": a["outlet_name"], "ts": a["ts"],
                                     "d": d_label(a["ts"]), "local": C.fmt_dt_ap(a["ts"]), "headline": a["headline"],
                                     "story_type": a["story_type"], "section": a["section"], "held": True})
        upcoming.sort(key=lambda x: x["ts"])
        st = c.status_at("ledger", clock.now)
        return {"now": clock.now, "d": d_label(clock.now), "local": C.fmt_dt_ap(clock.now),
                "date_long": C.fmt_date_long(clock.now), "playing": clock.playing, "rate": clock.rate,
                "pause_on_breaking": clock.pause_on_breaking, "start": c.start, "end": c.end,
                "start_d": d_label(c.start), "end_d": d_label(c.end), "seq": clock.seq,
                "published": sum(o["visible"] for o in outlets), "total": len(c.articles),
                "outlets": outlets, "upcoming": upcoming[:25], "log": clock.log[-60:][::-1],
                "milestones": [{"i": i, "label": m["label"], "d": d_label(m["ts"]), "ts": m["ts"],
                                "passed": m["ts"] <= clock.now} for i, m in enumerate(c.milestones)],
                "port": st["port"], "alerts": [{"id": x["id"], "level": x["level"], "text": x["text_en"]} for x in st["alerts"]]}


def gm_articles(clock):
    c = clock.c
    with clock.lock:
        rows = []
        for a in c.articles:
            rows.append({"id": a["id"], "pid": a["pid"], "outlet": a["outlet"], "outlet_name": a["outlet_name"],
                         "ts": a["ts"], "d": d_label(a["ts"]), "day": a["day"], "local": C.fmt_dt_ap(a["ts"]),
                         "section": a["section"], "authors": a["authors"], "headline": a["headline"],
                         "summary": a["summary"], "body": a["body"], "story_type": a["story_type"],
                         "storylines": a["storylines"], "people": a["people"], "places": a["places"],
                         "topics": a["topics"], "url": a["url"], "words": a["words"],
                         "related": a["related"], "arc_links": a["arc_links"], "follows_up": a["follows_up"],
                         "visible": clock.is_visible(a)})
    return {"now": clock.now, "d": d_label(clock.now), "outlets": [{"slug": o["slug"], "name": o["name"]} for o in c.outlets],
            "articles": rows}


def login_page(nxt, err):
    msg = '<p class="err">That passphrase did not match.</p>' if err else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Game Master Sign-in</title><style>
:root{{--bg:#f4f1ea;--fg:#1c1b19;--card:#fff;--line:#d9d3c7;--acc:#0f5c63}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--fg:#ecebe6;--card:#1e1d1b;--line:#3a3833;--acc:#5fb7bf}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;display:grid;place-items:center;min-height:100vh;padding:16px}}
form{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:28px;width:100%;max-width:360px}}
h1{{font-size:20px;margin:0 0 4px}}p{{margin:0 0 16px;opacity:.8;font-size:14px}}
input{{width:100%;padding:11px 12px;border:1px solid var(--line);border-radius:8px;font:inherit;background:transparent;color:inherit}}
button{{margin-top:12px;width:100%;padding:11px;border:0;border-radius:8px;background:var(--acc);color:#fff;font:600 15px system-ui;cursor:pointer}}
.err{{color:#c0392b;opacity:1}}</style></head><body>
<form method="post" action="/gm/login"><h1>Game master</h1><p>Enter the passphrase shown in the server window.</p>{msg}
<input type="hidden" name="next" value="{html.escape(nxt)}"><input type="password" name="passphrase" autofocus autocomplete="current-password" aria-label="Passphrase">
<button type="submit">Sign in</button></form></body></html>"""


# ======================================================================================
# portal
# ======================================================================================
def portal_module():
    try:
        mod = importlib.import_module("nr.portal")
        if DEV:
            mod = importlib.reload(mod)
        return mod
    except ModuleNotFoundError:
        return importlib.import_module("nr._portal_min")


def portal_ctx(clock, host):
    c = clock.c
    with clock.lock:
        outs = []
        for o in c.outlets:
            vis = clock.visible_list(o["slug"])
            last = vis[-1]["view"] if vis else None
            outs.append(dict(o, visible=len(vis), latest=last, held=o["slug"] in clock.holds))
        return {"now": int(clock.now), "outlets": outs, "host": host, "sig": clock.sig("_all"),
                "poll_ms": App.config.get("poll_ms", 1500)}


# ======================================================================================
def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        ips |= {i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except Exception:
        pass
    return sorted(i for i in ips if not i.startswith("127."))


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            cfg.update(json.load(open(CONFIG_PATH, encoding="utf-8")))
        except Exception:
            print("  config.json could not be read; using defaults")
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)


def make_token(passphrase):
    os.makedirs(STATE_DIR, exist_ok=True)
    kp = os.path.join(STATE_DIR, "secret.key")
    if not os.path.exists(kp):
        with open(kp, "wb") as fh:
            fh.write(secrets.token_bytes(32))
    key = open(kp, "rb").read()
    return hmac.new(key, passphrase.encode("utf-8"), hashlib.sha256).hexdigest() if passphrase else None


def main():
    global DEV
    ap = argparse.ArgumentParser(description="Coastal Bend Newsroom")
    ap.add_argument("--lan", action="store_true", help="serve on the shared network")
    ap.add_argument("--port", type=int)
    ap.add_argument("--passphrase")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--no-save", action="store_true", help="testing: don't write config.json or the saved clock")
    args = ap.parse_args()
    DEV = args.dev

    if build_data.sources_present():
        try:
            build_data.build(verbose=False)
        except Exception as e:
            print(f"  could not rebuild data from the corpus ({e}); using cached data")
    if not os.path.exists(os.path.join(DATA, "articles.json")):
        sys.exit("No article data found in newsroom/data. Run build_data.py inside the News Stories folder.")

    cfg = load_config()
    if args.passphrase:
        cfg["gm_passphrase"] = args.passphrase
    if args.lan and not cfg.get("gm_passphrase"):
        words = ["harbor", "jetty", "pelican", "tarpon", "causeway", "mustang", "laguna", "nueces", "aransas", "bayfront"]
        cfg["gm_passphrase"] = f"{secrets.choice(words)}-{secrets.choice(words)}-{secrets.randbelow(900) + 100}"
    if not args.no_save:
        save_config(cfg)        # a --port override applies to this run only
    if args.port:
        cfg = dict(cfg, port=args.port)
    App.config = cfg
    App.token = make_token(cfg.get("gm_passphrase", ""))

    corpus = Corpus()
    App.clock = Clock(corpus, reset=args.reset or args.no_save, persist=not args.no_save)
    threading.Thread(target=ticker, args=(App.clock,), daemon=True).start()

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    srv = ThreadingHTTPServer((host, cfg["port"]), Handler)
    srv.daemon_threads = True
    line = "=" * 64
    print(line)
    print("  COASTAL BEND NEWSROOM  (Hurricane Rafael exercise)")
    print(line)
    print(f"  {len(corpus.articles)} articles across {len(corpus.outlets)} outlets")
    print(f"  Scenario clock: {C.fmt_dt_ap(App.clock.now)}   ({d_label(App.clock.now)})")
    print()
    print(f"  Control page (game master):  http://localhost:{cfg['port']}/control")
    print(f"  Corpus explorer:             http://localhost:{cfg['port']}/explorer")
    print(f"  Newsstand (all outlets):     http://localhost:{cfg['port']}/")
    if args.lan:
        print()
        for ip in lan_ips() or ["<this computer's IP address>"]:
            print(f"  Participants browse:         http://{ip}:{cfg['port']}/")
        print(f"  Game-master passphrase:      {cfg['gm_passphrase']}")
        print("  (Windows may ask to allow Python through the firewall: allow it on private networks.)")
    print()
    print("  Press Ctrl+C to stop. The clock is saved and resumes where you left it.")
    print(line)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        App.clock.save(force=True)
        print("\n  Stopped. Clock saved.")


if __name__ == "__main__":
    main()
