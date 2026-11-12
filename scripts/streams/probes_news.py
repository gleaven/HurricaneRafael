"""Probes for the news stream (08_release/news_stories_public.json): one per expected observation.

A probe passes when stories published inside the observation's window (plus PUBLISH_LAG for
observations that describe a reporter's phone call or interview, which reach print later) contain
the stated coverage. Reads the release file on disk.
"""
import datetime as dt
import json
import os

from common import ROOT, canon

PUBLISH_LAG = {"EVT-1408": 48, "EVT-1409": 48}       # hours after the window in which the piece may run
_c = {}


def stories():
    if "s" not in _c:
        d = json.load(open(os.path.join(ROOT, "08_release", "news_stories_public.json"), encoding="utf-8"))["stories"]
        for s in d:
            s["_t"] = dt.datetime.fromisoformat(s["published"]).timestamp()
            s["_text"] = " ".join([s["headline"], s.get("summary", "")] + s["body"]).lower()
        _c["s"] = d
    return _c["s"]


def window(eid):
    e = next(x for x in canon()["expected_observations"]["items"] if x["event_id"] == eid and x["stream"] == "news")
    f = lambda z: dt.datetime.fromisoformat(z.replace("Z", "+00:00")).timestamp()
    return f(e["start_utc"]), f(e["end_utc"]) + PUBLISH_LAG.get(eid, 0) * 3600


def find(eid, all_of=(), any_of=(), outlet=None):
    a, b = window(eid)
    out = []
    for s in stories():
        if not (a <= s["_t"] < b):
            continue
        if outlet and s["outlet"] != outlet:
            continue
        t = s["_text"]
        if all(k in t for k in all_of) and (not any_of or any(k in t for k in any_of)):
            out.append(s)
    return out


def mk(eid, min_stories=1, min_outlets=1, **kw):
    def probe():
        hit = find(eid, **kw)
        outs = sorted({s["outlet"] for s in hit})
        ok = len(hit) >= min_stories and len(outs) >= min_outlets
        return ok, f"{len(hit)} stories from {len(outs)} outlets" + (f", first: {hit[0]['headline'][:70]}" if hit else "")
    return probe


def p_0309():
    checks = find("EVT-0309", any_of=("fact check", "fact-check", "false", "not true", "denial", "rumor"))
    a = dt.datetime(2027, 9, 30, 5, tzinfo=dt.timezone.utc).timestamp()
    coord = [s for s in stories() if a <= s["_t"] < a + 2 * 86400 and "coordinated" in s["_text"] and "accounts" in s["_text"]]
    return (len(checks) >= 2 and len(coord) >= 1, f"{len(checks)} fact-checks or denials; {len(coord)} coordinated-network stories on D+16/17")


PROBES = {
    ("EVT-0108", "news"): mk("EVT-0108", all_of=("exercise",), outlet="Continental Wire Service"),
    ("EVT-0201", "news"): mk("EVT-0201", any_of=("busy rest of hurricane season", "above-normal", "busy season", "rest of hurricane season")),
    ("EVT-0202", "news"): mk("EVT-0202", 3, 2, all_of=("rafael",), any_of=("cone", "forms", "tropical storm")),
    ("EVT-0301", "news"): mk("EVT-0301", 6, 4, all_of=("rafael",), any_of=("landfall", "ashore", "category 3")),
    ("EVT-0314", "news"): mk("EVT-0314", 2, 2, all_of=("oil",), any_of=("sheen", "33 square miles", "shoreline", "spill")),
    ("EVT-0315", "news"): mk("EVT-0315", all_of=("unified command",)),
    ("EVT-0309", "news"): p_0309,
    ("EVT-0317", "news"): mk("EVT-0317", 2, 1, any_of=("respiratory", "skin complaints", "shellfish", "fishing closure", "avoid contact with oil")),
    ("EVT-2007", "news"): mk("EVT-2007", any_of=("responsible party", "claims", "liability")),
    ("EVT-1408", "news"): mk("EVT-1408", all_of=("spanish",), any_of=("trejo-morales", "delayed", "12 hours", "twelve hours")),
    ("EVT-1409", "news"): mk("EVT-1409", all_of=("fuentes-vega",), outlet="Coastline Public Radio"),
    ("EVT-1908", "news"): mk("EVT-1908", all_of=("drone",), any_of=("counter", "program", "unmanned")),
    ("EVT-1509", "news"): mk("EVT-1509", all_of=("accounts",), any_of=("removed", "removal", "taken down", "suspended")),
    ("EVT-0413", "news"): mk("EVT-0413", 2, 2, all_of=("tug",), any_of=("explosion", "blast")),
    ("EVT-0415", "news"): mk("EVT-0415", any_of=("overseas", "military operations"), outlet="Continental Wire Service"),
    ("EVT-0507", "news"): mk("EVT-0507", any_of=("rumor", "rumors", "false claims")),
    ("EVT-0605", "news"): mk("EVT-0605", all_of=("advisory",), any_of=("vendor", "remote access")),
    ("EVT-0604", "news"): mk("EVT-0604", all_of=("bridge",), any_of=("review", "harden")),
}


def _range():
    t = [s["_t"] for s in stories()]
    return min(t), max(t)


STREAMS = {"news": {"time_range": _range, "public_voice": True, "text": lambda: (s["_text"] for s in stories())}}
