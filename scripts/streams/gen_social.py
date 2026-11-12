"""Social media stream (Twitter v1.1-style objects), D-60 to D+119.

    python3 scripts/streams/gen_social.py

Writes 05_other_sources/social_media/
  <handle>.jsonl                      one file per account in personas.json -> personas
  community_<YYYY-MM>.jsonl           posts by the accounts in personas.json -> accounts_compact, by month
  _account_lookup.jsonl               users/lookup snapshot at the end of the collection (suspended accounts return an error)
  _platform_records_return.jsonl      account access records returned by the platforms under a law-enforcement referral
  _geotagged_index.csv                id, author, time and coordinates of every geo-tagged post (same values as in the posts)
and 06_data_streams/_internal/social_stream_notes.json (internal: which accounts carry the second wave).

Content comes from social_text.py (residents, businesses, groups), social_script.py (agencies at canon times,
the coordinated accounts), the news release (outlets and reporters post their stories when they publish) and the
sensor streams on disk (automated accounts relay real readings and fall silent when the sensor does).
No field marks an account or a post as inauthentic.
"""
import bisect
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
from collections import defaultdict

import numpy as np

import social_script as SS
import social_text as ST
from common import (D0_EPOCH, ROOT, SPAN_END, canon, day_of, geo_handle, internal, iso, load_json, local_dt, local_ts, reg, retire,
                    rng, write_csv)

OUT = "05_other_sources/social_media/"
START_DAY, END_DAY = -60, 119
TW_EPOCH_MS = 1288834974657
DAY = 86400
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
SRC = {"iphone": '<a href="http://twitter.com/download/iphone" rel="nofollow">Twitter for iPhone</a>',
       "android": '<a href="http://twitter.com/download/android" rel="nofollow">Twitter for Android</a>',
       "web": '<a href="https://mobile.twitter.com" rel="nofollow">Twitter Web App</a>',
       "deck": '<a href="https://about.twitter.com/products/tweetdeck" rel="nofollow">TweetDeck</a>',
       "sched": '<a href="https://postdesk.example" rel="nofollow">PostDesk Scheduler</a>',
       "bot": '<a href="https://feeds.example/relay" rel="nofollow">Feed Relay</a>'}
OUTLET_HANDLE = {"The Bayside Ledger": "BaysideLedger", "Harborline 6 News": "Harborline6News", "Coastline Public Radio": "CoastlinePublicRadio",
                 "Gulfwater Maritime Report": "GulfwaterMaritime", "Sabal Energy Wire": "SabalEnergyWire", "Continental Wire Service": "ContinentalWire",
                 "Anchor & Rotor Weekly": "AnchorRotorWeekly", "KNCB Coastal Bend Radio": "KNCB1480"}
OUTLET_SITE = {"The Bayside Ledger": "bayside-ledger.example", "Harborline 6 News": "harborline6.example", "Coastline Public Radio": "coastline-radio.example",
               "Gulfwater Maritime Report": "gulfwater-maritime.example", "Sabal Energy Wire": "sabal-energy.example",
               "Continental Wire Service": "continental-wire.example", "Anchor & Rotor Weekly": "anchor-rotor.example", "KNCB Coastal Bend Radio": "kncb1480.example"}
DRONE_NIGHTS = [1, 2, 4, 6, 8, 10]                 # same nights as the 911 calls about lights over the air station
BLAST_TS = None

# template gates: (substring, earliest day, latest day)
GATES = [("Bridge is open again", 3.55, 9), ("Ya abrieron el puente", 3.55, 9), ("They closed the bays", 4.76, 99), ("Cerraron las bahías", 4.76, 99),
         ("Boom is out", 2.45, 99), ("Andan cuadrillas limpiando", 2.45, 99), ("Black oil on the sand", 2.0, 99), ("Hay petróleo en la arena", 2.0, 99),
         ("Oil sheen all the way across", 2.0, 99), ("Called the wildlife hotline", 2.45, 99), ("Lights are ON", 1.0, 99), ("Ya llegó la luz", 1.0, 99),
         ("Had power for six hours", 7.45, 16), ("Tuvimos luz seis horas", 7.45, 16), ("Power came back for an hour", 7.45, 99), ("Volvió la luz una hora", 7.45, 99),
         ("They say pump parts", 10.5, 36), ("Que ya vienen las piezas", 10.5, 36), ("Week {n}", 11, 99), ("{n} semanas", 11, 99),
         ("LIGHTS. After thirty-five", 35.63, 99), ("LLEGÓ LA LUZ", 35.63, 99), ("Last ones in the city", 35.63, 99), ("Fuimos de los últimos", 35.63, 99),
         ("Five weeks. FIVE", 33, 35.6), ("Cinco semanas sin luz", 33, 35.6), ("Crews restoring by hand", 29.4, 35.6),
         ("Relief ship finally docked", 33.55, 99), ("Big gray cargo planes", 34.4, 44), ("Puro avión grande", 34.4, 44),
         ("Navy says it was an explosive", 46.47, 99), ("La Marina dice", 46.47, 99), ("Navy divers", 46.47, 58.3), ("They found a second one", 52.55, 99),
         ("Encontraron un segundo", 52.55, 99), ("Port closed twice", 44.3, 99), ("Channel reopened today", 58.34, 58.99), ("Ya reabrieron el canal", 58.34, 60),
         ("Gas line, old ordnance", 44.3, 46.4), ("Explosion next to a tug", 44.3, 50), ("Explosión junto a un remolcador", 44.3, 50), ("The tug was the Corrin Bay", 44.4, 52),
         ("FEMA confirms accounts", 66.63, 99), ("They say we will be repaid", 71.6, 99), ("Dicen que nos van a reponer", 71.6, 99), ("Got the letter", 72, 99),
         ("County finally paused", 80.68, 99), ("El condado por fin detuvo", 80.68, 99), ("Navy suspended the fuel supplier", 78, 99),
         ("Study says our neighborhoods", 90.35, 99), ("Dicen que nuestras colonias", 90.35, 99), ("County and FEMA are going door", 92.45, 99),
         ("Ya andan casa por casa", 92.45, 99), ("Somebody actually knocked", 93, 99), ("Hoy tocaron con una tableta", 93, 99), ("Ask for ID from anyone", 92.45, 99),
         ("Thanksgiving", 71.6, 73.4), ("Acción de Gracias", 71.6, 73.4), ("Christmas lights", 82, 103.5), ("Luces de Navidad", 82, 103.5), ("Tree is up", 84, 103),
         ("First Christmas parade", 81.6, 82.9), ("New year", 108.5, 113), ("Año nuevo", 108.5, 113), ("Bait shop reopened", 90, 102),
         ("Part of the bay reopened", 115.4, 99), ("Insurance check came", 25, 99), ("Llegó el cheque", 25, 99), ("Hurricane watch is up", -2.58, -1.5),
         ("Hurricane WARNING now", -1.5, -0.2), ("Ya pusieron aviso", -2.58, -1.5), ("ADVERTENCIA de huracán", -1.5, -0.2), ("Phone just screamed", -1.5, -1.2),
         ("Sonó la alerta", -1.5, -1.2), ("Port is shutting down", -1.66, -0.5), ("Now they extended", -0.7, 0), ("Ya extendieron", -0.7, 0),
         ("Finally got back in", 4, 99), ("County and the base both say", 3.43, 99), ("El condado y la base dicen", 3.43, 99), ("Checked with someone who actually works", 2.6, 99),
         ("That post about seizing homes has the same", 2.7, 99), ("Do NOT click", 5.43, 99), ("The city says the aid emails", 5.43, 99), ("NO le piquen", 5.43, 99),
         ("Half the 'help is only", 6, 99), ("They lifted it for most of town", 39.4, 42.4), ("First day of school pics", -30.75, -29), ("Primer día de clases", -30.75, -29),
         ("Friday night lights are back", -19, -12), ("Viernes de futbol", -19, -12), ("Curfew at dark", 1.4, 16), ("First band just came", -0.8, 0),
         ("Wind is picking up", -0.6, 0), ("Ya empezó el viento", -0.6, 0), ("Power flickered twice", -0.4, 0.04), ("Parpadeó la luz", -0.4, 0.04),
         ("Transformer just blew", -0.3, 0.04), ("Last update before I save", -0.3, 0.04), ("Último mensaje", -0.3, 0.04), ("Bus finally came", -1.6, -0.3),
         ("Por fin llegó el camión", -1.6, -0.3), ("Shelter is full", -1.2, 3), ("El albergue ya se llenó", -1.2, 3), ("Coast Guard says two tankers", 1.48, 99),
         ("Dicen que fueron dos buques", 1.48, 99), ("Base says they are 'aware", 6.56, 99), ("Health department says wash", 6.64, 99),
         ("Health department is asking", 18.64, 99), ("Salud pública anda preguntando", 18.64, 99), ("Doctor said it is a parasite", 23, 99), ("El doctor dijo que es un parásito", 23, 99),
         ("First hot coffee in two days", 1.6, 5), ("'Assessing damage' for a week", 6, 14), ("Five days, no power", 4.5, 6.5), ("Other cities took the same storm", 2, 99),
         ("My street has not seen one CBPWA truck", 1.5, 99), ("Ni una troca de CBPWA", 1.5, 99), ("Sigue el aviso de hervir agua en nuestro distrito", 14.3, 99),
         ("Districts 3 and 4 notice is still on", 14.3, 99), ("Low pressure on our side for days", 13.5, 99), ("Whole block is out helping", 0.4, 4), ("Never want to hear", 0.3, 3),
         ("Toda la cuadra ayudándose", 0.4, 4), ("Chainsaws since sunrise", 0.4, 4), ("Crews from three states", 2, 30), ("Linemen on", 1.3, 36), ("Por fin vimos una troca", 1.3, 36),
         ("Outage map says", 1.5, 36), ("Generator ran out of gas", 0.8, 36), ("Sleeping on the porch", 0.8, 30), ("Durmiendo en el porche", 0.8, 30),
         ("Everything in the freezer is a loss", 2, 12), ("Se echó a perder todo", 2, 12), ("How is it that across", 6, 36),
         ("A company nobody had heard of", 78, 99), ("Paper says Vantorra", 78.3, 99), ("Dicen que Vantorra", 78.3, 99)]


def h(*k):
    return hashlib.sha256("|".join(str(x) for x in k).encode()).hexdigest()


def hi(*k):
    return int(h(*k)[:12], 16)


def tw_time(t):
    d = dt.datetime.fromtimestamp(int(t), dt.timezone.utc)
    return f"{DOW[d.weekday()]} {MON[d.month - 1]} {d.day:02d} {d:%H:%M:%S} +0000 {d.year}"


def dts(x):
    """Epoch of a fractional local scenario day."""
    d = math.floor(x)
    return local_ts(int(d), "00:00") + int(round((x - d) * DAY))


def dayf(t):
    """Fractional local scenario day of an epoch."""
    d = day_of(t)
    return d + (t - local_ts(d, "00:00")) / DAY


def snowflake(t, key):
    ms = int(t) * 1000 + hi("ms", key) % 1000
    return ((ms - TW_EPOCH_MS) << 22) | ((hi("w", key) % 32) << 17) | (hi("s", key) % 4096)


# ======================================================================================
# accounts
# ======================================================================================
class Acct:
    __slots__ = ("handle", "name", "kind", "lang", "home", "area_id", "bio", "loc", "created", "followers", "friends", "verified", "cadence",
                 "hours", "style", "compact", "uid", "storm", "source", "traits", "streets", "net", "stop", "statuses0", "geo_pts")


FOLLOW_MID = {"<100": 45, "100-499": 260, "500-1,999": 900, "2,000-9,999": 4200, "10,000-49,999": 18000, "50,000+": 90000}
COMPACT_BIOS = ["", "", "", "", "dad. fisherman.", "mom of 3", "nurse", "retired", "small business owner", "island time", "teacher", "welder",
                "student", "husband, father, griller", "abuela de 5", "papá y pescador", "enfermera", "just here for the weather updates",
                "refinery hand", "veteran", "coach", "dog person", "", ""]


class Accounts:
    def __init__(self, G):
        P = reg("personas")
        T = internal("personas")
        self.truth = T
        areas = {a["area_id"]: a for a in reg("areas")["areas"]}
        self.areas = areas
        self.by = {}
        self.G = G
        # road names near each area, for {street}
        self.road_mid = []
        bad = re.compile(r"Bayshore|Northridge|State Hwy|US Hwy|^I-|Farm|^FM |Co Rd|Hwy", re.I)
        for name, cls, pts in G.roads.features:
            if name and cls in ("local", "arterial", "secondary") and not bad.search(name):
                m = pts[len(pts) // 2]
                self.road_mid.append((m[0], m[1], re.sub(r"^[NSEW] ", "", name)))
        self._streets = {}
        for p in P["personas"]:
            a = Acct()
            a.handle = p["handle"].lstrip("@")
            a.name, a.kind, a.lang = p["display_name"], p["account_type"], p["language"]
            a.home, a.area_id, a.bio, a.loc = p.get("home_area"), p.get("home_area_id"), p.get("bio") or "", p.get("location") or ""
            a.created = self._created(p["account_created"], a.handle)
            a.followers, a.friends, a.verified = int(p["followers"]), int(p["following"]), bool(p["verified"])
            a.cadence = float(p["cadence"]["typical_posts_per_day"])
            a.hours = self._hours(p["cadence"].get("active_hours_local", "07:00-23:00"))
            a.style, a.storm = p.get("posting_style", ""), p["cadence"].get("during_storm", "")
            a.compact = False
            tr = T["personas"].get(p["persona_id"], {})
            a.net = set(tr.get("network", [])) if not tr.get("authentic", True) else set()
            self._finish(a)
            self.by[a.handle] = a
        cols = P["accounts_compact"]["columns"]
        for row in P["accounts_compact"]["rows"]:
            r = dict(zip(cols, row))
            a = Acct()
            a.handle = r["handle"].lstrip("@")
            a.name = self._display(a.handle)
            a.kind, a.lang = "individual", r["language"]
            a.home, a.area_id = r["home_area"], r["home_area_id"]
            a.bio = COMPACT_BIOS[hi("bio", a.handle) % len(COMPACT_BIOS)]
            if a.lang == "en" and re.search(r"abuela|papá|enfermera", a.bio):
                a.bio = ""
            a.loc = (f"{a.home}, TX" if hi("loc", a.handle) % 3 else "Corpus Christi, TX") if a.home else ["", "Texas", "USA", "Houston, TX", "San Antonio, TX", ""][hi("loc", a.handle) % 6]
            a.created = self._created(r["account_created"], a.handle)
            mid = FOLLOW_MID.get(r["follower_range"], 120)
            a.followers = max(3, int(mid * (0.5 + (hi("fol", a.handle) % 1000) / 1000.0)))
            a.friends = int(a.followers * (0.6 + (hi("fr", a.handle) % 1500) / 1000.0)) + 20
            a.verified, a.cadence, a.hours = False, 0.11 + (hi("cad", a.handle) % 100) / 900.0, (7, 24)
            a.style, a.storm, a.compact, a.net = "", "", True, set()
            self._finish(a)
            self.by[a.handle] = a
        self.personas = [a for a in self.by.values() if not a.compact]
        self.compact = [a for a in self.by.values() if a.compact]
        amp = {x.lstrip("@") for x in T["networks"]["removed_d38_847"]["amplifiers_800"]}
        self.amplifiers = [self.by[x] for x in sorted(amp) if x in self.by]
        for a in self.amplifiers:
            a.stop = dts(38 + 11 / 24)
        self.base40 = sorted((a for a in self.personas if "base_40" in a.net), key=lambda a: a.handle)
        self.t15 = sorted((a for a in self.personas if "t15_47" in a.net), key=lambda a: a.handle)
        for a in self.t15:
            a.stop = dts(38 + 11 / 24)
            a.source = SRC["web"] if hi("nsrc", a.handle) % 4 else SRC["sched"]
        for hd in ("CoastTruthTX", "GulfWatchPatriot"):
            self.by[hd].stop = dts(17 + 12.2 / 24)
        for hd in (SS.LEAD_A, SS.LEAD_B):
            self.by[hd].stop = dts(30 + 15 / 24)
        # second wave: 40 accounts that were never removed (see module docstring of probes for why)
        cand = [a for a in self.compact if a not in self.amplifiers and a.lang == "en" and ts_date(2027, 5, 1) <= a.created < ts_date(2027, 9, 1)]
        cand.sort(key=lambda a: h("sleeper", a.handle))
        self.sleepers = sorted(cand[:40], key=lambda a: a.handle)
        for a in self.sleepers:
            a.source = SRC["web"] if hi("nsrc", a.handle) % 4 else SRC["sched"]

    def _created(self, date, handle):
        y, m, d = map(int, date.split("-"))
        sec = hi("ctime", handle) % DAY
        t = int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp()) + sec
        if date == "2027-09-09" and sec > 12 * 3600 - 60:      # canon: the cluster closes at 12:00Z on Sept. 9
            t -= 12 * 3600
        return t

    def _hours(self, s):
        m = re.match(r"(\d+):\d+-(\d+):\d+", s)
        a, b = (int(m.group(1)), int(m.group(2))) if m else (7, 23)
        if b <= a:
            b += 24
        return (a, b)

    def _display(self, handle):
        s = re.sub(r"\d+$", "", handle)
        s = re.sub(r"(CC|TX)$", "", s)
        s = s.replace("_", " ")
        s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
        s = s.replace(" fam", " family").replace(" in ", " in ")
        return s.strip() or handle

    def _finish(self, a):
        k = hi("uid", a.handle)
        a.uid = snowflake(a.created, a.handle) if a.created >= 1356998400 else 20000000 + k % 900000000
        a.stop = None
        r = rng("traits", a.handle)
        a.traits = {"lower": r.random() < 0.13, "nodot": r.random() < 0.3, "emoji": float(r.uniform(0, 0.3)) if r.random() < 0.6 else 0.0,
                    "tags": float(r.uniform(0.08, 0.55)), "excl": r.random() < 0.15, "geo": r.random() < 0.3}
        a.source = SRC[["iphone", "iphone", "android", "android", "web"][k % 5]]
        if a.kind in ("official", "media", "organization"):
            a.source = SRC[["web", "deck", "deck", "web"][k % 4]]
        if a.kind == "automated":
            a.source = SRC["bot"]
        age_days = max(30, (D0_EPOCH - a.created) / DAY)
        a.statuses0 = int(min(age_days, 3000) * max(a.cadence, 0.2) * (0.25 + (k % 100) / 160.0))
        a.streets = None
        a.geo_pts = None

    def streets(self, a):
        if a.streets is None:
            ar = self.areas.get(a.area_id)
            rp = (ar or {}).get("reference_point") or {"latitude": 27.75 + (hi("lat", a.handle) % 100) / 1500.0, "longitude": -97.42 + (hi("lon", a.handle) % 100) / 1200.0}
            key = (round(rp["latitude"], 3), round(rp["longitude"], 3))
            if key not in self._streets:
                d = sorted(((abs(m[0] - key[0]) + abs(m[1] - key[1]) * 0.9, m[2]) for m in self.road_mid))
                names = []
                for _, n in d:
                    if n not in names:
                        names.append(n)
                    if len(names) >= 12:
                        break
                self._streets[key] = names
            a.streets = self._streets[key]
        return a.streets

    def geo_points(self, a):
        """A few points on land beside streets in the author's home area (None if it cannot be placed)."""
        if a.geo_pts is None:
            a.geo_pts = []
            ar = self.areas.get(a.area_id)
            if ar and ar.get("reference_point") and self.G.in_box(ar["reference_point"]["latitude"], ar["reference_point"]["longitude"]):
                lat, lon = ar["reference_point"]["latitude"], ar["reference_point"]["longitude"]
                b = ar.get("bbox") or [lon - 0.01, lat - 0.01, lon + 0.01, lat + 0.01]
                box = (max(b[0], lon - 0.02), max(b[1], lat - 0.018), min(b[2], lon + 0.02), min(b[3], lat + 0.018))
                r = rng("geo", a.handle)
                for _ in range(12):
                    p = self.G.roads.random_point(r, box=box, classes=("local", "arterial"), setback_m=14)
                    if p and self.G.is_land(p[0], p[1]) and self.G.shore_distance_m(p[0], p[1]) > 15:
                        a.geo_pts.append((round(p[0], 5), round(p[1], 5)))
                    if len(a.geo_pts) >= 4:
                        break
        return a.geo_pts


def ts_date(y, m, d):
    return int(dt.datetime(y, m, d, tzinfo=dt.timezone.utc).timestamp())


# ======================================================================================
# the stream under construction
# ======================================================================================
class Stream:
    def __init__(self, A):
        self.A = A
        self.tw = []                 # dicts: t, a(handle), text, lang, kind, ref, url, geo, pool, src
        self.req = []                # unresolved retweets, quotes and replies
        self.pools = defaultdict(list)

    def post(self, t, a, text, lang="en", pool=None, url=None, geo=None, src=None, topic=""):
        acct = self.A.by[a] if isinstance(a, str) else a
        if t < dts(START_DAY) or t >= SPAN_END or (acct.stop and t >= acct.stop) or t < acct.created + 120:
            return None
        text = text.strip()
        if len(text) > 280:
            text = text[:277].rsplit(" ", 1)[0] + "…"
        i = len(self.tw)
        self.tw.append({"t": int(t), "a": acct.handle, "text": text, "lang": lang, "kind": "o", "ref": None, "url": url, "geo": geo,
                        "src": src or acct.source, "topic": topic})
        if pool:
            for p in (pool if isinstance(pool, (list, tuple)) else [pool]):
                self.pools[p].append(i)
        return i

    def ask(self, t, a, kind, pools, text="", lang="en", window=8 * 3600, topic=""):
        acct = self.A.by[a] if isinstance(a, str) else a
        if t < dts(START_DAY) or t >= SPAN_END or (acct.stop and t >= acct.stop) or t < acct.created + 120:
            return
        self.req.append({"t": int(t), "a": acct.handle, "kind": kind, "pools": pools, "text": text, "lang": lang, "window": window, "topic": topic})

    def resolve(self):
        """Attach every retweet, quote and reply to an earlier post in one of its pools."""
        idx = {}
        for p, lst in self.pools.items():
            lst.sort(key=lambda i: self.tw[i]["t"])
            idx[p] = [self.tw[i]["t"] for i in lst]
        made = 0
        for q in sorted(self.req, key=lambda q: (q["t"], q["a"])):
            r = rng("resolve", q["a"], q["t"])
            target = None
            for p in q["pools"]:
                ts_ = idx.get(p)
                if not ts_:
                    continue
                hi_ = bisect.bisect_left(ts_, q["t"] - 20)
                lo_ = bisect.bisect_left(ts_, q["t"] - q["window"])
                if hi_ > lo_:
                    # prefer recent posts
                    k = hi_ - 1 - int(min(hi_ - lo_ - 1, abs(r.exponential(max(1.0, (hi_ - lo_) / 4.0)))))
                    cand = self.pools[p][k]
                    if self.tw[cand]["a"] != q["a"]:
                        target = cand
                        break
            if target is None:
                continue
            src = self.tw[target]
            acct = self.A.by[q["a"]]
            if q["kind"] == "rt":
                text = f"RT @{src['a']}: {src['text']}"
                if len(text) > 300:
                    text = text[:297] + "…"
                lang = src["lang"]
            elif q["kind"] == "q":
                text, lang = q["text"], q["lang"]
            else:
                text, lang = f"@{src['a']} {q['text']}", q["lang"]
            self.tw.append({"t": q["t"], "a": q["a"], "text": text, "lang": lang, "kind": q["kind"], "ref": target, "url": src["url"] if q["kind"] == "rt" else None,
                            "geo": None, "src": acct.source, "topic": q["topic"]})
            made += 1
        return made


# ======================================================================================
# text rendering
# ======================================================================================
EMOJI = {"worry": ["🙏", "😟", "😬"], "anger": ["😡", "🤬", "😤"], "joy": ["🙌", "😭", "🎉"], "plain": ["🌊", "☀️", "🌴", "🤷"]}
MOOD = {"blame": "anger", "power_out": "anger", "waiting_help": "anger", "morning_after": "worry", "landfall_night": "worry", "staying": "worry",
        "evac_zoneA": "worry", "boil_lifted": "joy", "d34_lifted": "joy", "power_last": "joy"}


def gate_ok(text, x):
    for sub, lo, hi_ in GATES:
        if sub in text and not (lo <= x <= hi_):
            return False
    return True


def pick_lang(a, r):
    if a.lang == "es":
        return "es"
    if a.lang == "es/en":
        return "es" if r.random() < 0.75 else "en"
    if a.lang == "en/es":
        return "es" if r.random() < 0.25 else "en"
    return "en"


def fill(A, a, text, x, r, beat=""):
    if "{n}" in text:
        if re.search(r"Day \{n\}|Día \{n\}", text):
            n = max(1, int(x) - (12 if beat.startswith("d34") else 0))
        elif "Week {n}" in text or "{n} semanas" in text:
            n = max(1, int((x - 4) // 7) + 1)
        elif "{n}0" in text:
            n = int(r.integers(2, 7))
        else:
            n = int(r.integers(2, 9))
        text = text.replace("{n}", str(n))
    if "{street}" in text:
        st = A.streets(a)
        text = text.replace("{street}", st[int(r.integers(len(st)))] if st else "Staples")
    if "{nbh}" in text:
        text = text.replace("{nbh}", a.home or "Corpus Christi")
    if "{rel}" in text:
        pool = ST.REL_ES if re.search(r"[áéíóúñ¿¡]| la | el | de ", text) else ST.REL
        text = text.replace("{rel}", pool[int(r.integers(len(pool)))])
    if "{h}" in text:
        text = text.replace("{h}", str(r.choice(["10:30", "11", "midnight", "1am"])) if beat == "nas_lights" else str(int(r.integers(5, 9))))
    if "{city}" in text:
        text = text.replace("{city}", a.home or "Corpus Christi")
    if "{area}" in text:
        text = text.replace("{area}", ST.JOURNO_AREAS[int(r.integers(len(ST.JOURNO_AREAS)))])
    return text


OPEN_EN = ["Honestly,", "Y'all,", "Update:", "So.", "Welp.", "Not gonna lie,", "Listen,", "OK.", "Real talk:", "For the record,", "Again:", "Morning update:"]
OPEN_ES = ["La verdad,", "Oigan,", "Pues,", "Bueno,", "Miren,", "Otra vez:", "Les aviso:"]
CLOSE_EN = ["Stay safe.", "Lord.", "Unreal.", "Pray for us.", "That is all.", "smh", "Hang in there.", "We will get through it.", "Tired.", "Anyway."]
CLOSE_ES = ["Cuídense.", "Dios mío.", "Ni modo.", "Ánimo.", "Qué cosas.", "Bendiciones."]


def styled(a, text, r, tags=(), mood="plain", force_tag=None):
    tr = a.traits
    if a.kind == "individual" and not text.startswith(("@", "RT ")):
        es = bool(re.search(r"[áéíóúñ¿¡]|\b(el|la|los|las|de|que|y)\b", text))
        u = r.random()
        if u < 0.3:
            o = (OPEN_ES if es else OPEN_EN)
            text = o[int(r.integers(len(o)))] + " " + text
        if 0.2 < u < 0.42 or u > 0.9:
            c = (CLOSE_ES if es else CLOSE_EN)
            text = text + " " + c[int(r.integers(len(c)))]
    if tr["lower"]:
        text = re.sub(r"(?<![@#\w])([A-Z][a-z]+)", lambda m: m.group(1).lower(), text)
    if tr["nodot"] and text.endswith("."):
        text = text[:-1]
    if tr["excl"] and text.endswith("."):
        text = text[:-1] + "!"
    if tr["emoji"] and r.random() < tr["emoji"]:
        e = EMOJI[mood]
        text += " " + e[int(r.integers(len(e)))]
    add = []
    if force_tag:
        add.append(force_tag)
    if tags and r.random() < tr["tags"]:
        k = 1 + (r.random() < 0.3)
        for t in r.choice(list(tags), size=min(k, len(tags)), replace=False):
            if t not in add and t not in text:
                add.append(str(t))
    if add:
        text += " " + " ".join(add)
    return text


# ======================================================================================
# who is connected, who is paying attention
# ======================================================================================
def phase(d):
    if d < -12: return 0.30
    if d < -5: return 0.55
    if d < -1: return 1.0
    if d < 0: return 1.25
    if d <= 3: return 1.3
    if d <= 20: return 1.0
    if d <= 45: return 0.6
    if d <= 59: return 0.55
    if d <= 90: return 0.45
    return 0.33


def connected(a, x):
    """Chance that a local account can post at fractional day x (power and cell service after landfall)."""
    if not a.home:
        return 1.0
    f = 1.0
    if 0.0 <= x < 0.5:
        f = 0.2
    elif 0.5 <= x < 1.0:
        f = 0.33
    elif 1.0 <= x < 3.0:
        f = 0.6
    elif 3.0 <= x < 7.0:
        f = 0.85
    if a.home in ST.SURGE and -0.1 <= x < 5.0:
        f *= 0.55
    return f


HOURW = np.array([.25, .12, .07, .05, .05, .12, .45, .9, 1.1, 1.1, 1.1, 1.2, 1.35, 1.2, 1.1, 1.1, 1.2, 1.35, 1.5, 1.6, 1.6, 1.4, 1.0, .55])


def sample_time(a, day, r):
    lo, hi_ = a.hours
    hrs = np.arange(lo, hi_)
    w = HOURW[hrs % 24]
    hr = int(r.choice(hrs, p=w / w.sum()))
    return local_ts(day, "00:00") + hr * 3600 + int(r.integers(0, 3600))


# ======================================================================================
# residents
# ======================================================================================
BEAT = {b[0]: b for b in ST.BEATS}
INJECT_ONLY = {"landfall_night", "blast_night", "nas_lights", "oil_first"}
LIFE = {"life_heat", "life_beach", "life_school", "life_misc", "life_port", "life_prep_season"}
BLAME_BEAT = ("blame", ST.F(0, "10:00"), ST.F(36), 4.2, 8.0, None, {"en": ST.BLAME_EN, "es": ST.BLAME_ES}, ST.BLAME_TAGS)
OFFICIAL_POOLS = ["official"]


def beat_weights(a, x):
    out = []
    for b in ST.BEATS + [BLAME_BEAT]:
        bid, s, e, w, tau, areas, texts, tags = b
        if bid in INJECT_ONLY or not (s <= x < e):
            continue
        if areas is not None and (a.home not in areas):
            continue
        if bid == "blame" and not a.home:
            continue
        if bid == "d34_boil_en" and a.lang in ("es", "es/en") and x < 13.26:
            continue
        ww = w * (math.exp(-(x - s) / tau) if tau else 1.0)
        if bid in LIFE:
            if -5 <= x <= 20:
                ww *= 0.12
            elif 20 < x <= 60:
                ww *= 0.5
        if bid == "blame":
            if "angry at the utility" in a.style:
                ww *= 3.0
            if a.home in ST.LATE_POWER and x > 12:
                ww *= 2.5
        if not a.home and bid not in LIFE and bid not in ("rafael_forms", "cyber_reveal", "attribution", "watch_warning"):
            ww *= 0.25                          # people far away talk about it less, and never first-hand
        out.append((b, ww))
    return out


def render_beat(S, a, b, x, r, t):
    bid, s, e, w, tau, areas, texts, tags = b
    lang = pick_lang(a, r)
    pool = [tx for tx in texts.get(lang, []) if gate_ok(tx, x)]
    if not pool:
        lang = "en" if lang == "es" else "es"
        pool = [tx for tx in texts.get(lang, []) if gate_ok(tx, x)]
        if not pool or (lang == "es" and a.lang == "en") or (lang == "en" and a.lang == "es"):
            return None
    text = fill(S.A, a, pool[int(r.integers(len(pool)))], x, r, bid)
    force = None
    if bid == "blame":
        force = ST.BLAME_TAGS[int(r.integers(len(ST.BLAME_TAGS)))]
    text = styled(a, text, r, tags, MOOD.get(bid, "plain"), force)
    geo = None
    if a.traits["geo"] and a.home and r.random() < 0.13:
        pts = S.A.geo_points(a)
        if pts:
            geo = pts[int(r.integers(len(pts)))]
    pools = ["res:" + bid]
    if bid == "blame":
        pools.append("blame")
    return S.post(t, a, text, lang, pool=pools, geo=geo, topic=bid)


def outsider_post(S, a, t, r):
    """Accounts outside the Coastal Bend: they repost and comment, they do not report first-hand."""
    x = dayf(t)
    if x < -10:
        return
    lang = pick_lang(a, r)
    u = r.random()
    if u < 0.5:
        S.ask(t, a, "rt", ["media", "official"] if r.random() < 0.7 else ["official", "media"], lang=lang, window=10 * 3600, topic="outside")
    elif u < 0.7:
        txt = ST.QUOTE_ES if lang == "es" else ST.QUOTE_EN
        txt = [q for q in txt if "{nbh}" not in q]
        S.ask(t, a, "q", ["media", "official"], txt[int(r.integers(len(txt)))], lang, window=10 * 3600, topic="outside")
    else:
        pool = [q for q in (ST.OUTSIDER_ES if lang == "es" else ST.OUTSIDER_EN)
                if all(not (k in q) or (lo <= x <= hi_) for k, (lo, hi_) in ST.OUTSIDER_GATES.items())]
        if not pool:
            return
        txt = pool[int(r.integers(len(pool)))].replace("{far}", str(r.choice(["Flour Bluff", "Calallen", "the Southside", "North Beach", "Portland", "Port Aransas"])))
        S.post(t, a, styled(a, txt, r, ["#Rafael", "#CorpusChristi", "#Texas"], "worry"), lang, pool=["res:outside"], topic="outside")


def resident_post(S, a, t, r):
    x = dayf(t)
    if not a.home:
        return outsider_post(S, a, t, r)
    bw = beat_weights(a, x)
    if not bw:
        return
    ws = np.array([w for _, w in bw])
    b = bw[int(r.choice(len(bw), p=ws / ws.sum()))][0]
    bid = b[0]
    u = r.random()
    rt_p, q_p, re_p = 0.17, 0.06, 0.09
    if "shares official" in a.style:
        rt_p, q_p = 0.42, 0.12
    elif "reposts with commentary" in a.style:
        rt_p, q_p = 0.2, 0.4
    elif "asks neighbours" in a.style:
        re_p = 0.25
    if bid in LIFE or x < -10:
        rt_p, q_p, re_p = rt_p * 0.3, q_p * 0.3, re_p * 0.3
    lang = pick_lang(a, r)
    es = lang == "es"
    if bid.startswith("rumor_react") and u < 0.45:
        txt = (ST.REPLY_RUMOR_ES if es else ST.REPLY_RUMOR_EN)
        S.ask(t, a, "re", ["rumor"], fill(S.A, a, txt[int(r.integers(len(txt)))], x, r), lang, window=6 * 3600, topic=bid)
        return
    if u < rt_p:
        pools = ["blame", "res:blame"] if bid == "blame" else (["official", "media"] if r.random() < 0.6 else ["res:" + bid, "media"])
        S.ask(t, a, "rt", pools, lang=lang, topic=bid)
    elif u < rt_p + q_p:
        txt = ST.QUOTE_ES if es else ST.QUOTE_EN
        S.ask(t, a, "q", ["official", "media"] if bid != "blame" else ["blame", "media"], fill(S.A, a, txt[int(r.integers(len(txt)))], x, r), lang, topic=bid)
    elif u < rt_p + q_p + re_p and x > -6:
        if r.random() < 0.6:
            txt = ST.REPLY_OFFICIAL_ES if es else ST.REPLY_OFFICIAL_EN
            S.ask(t, a, "re", ["official"], fill(S.A, a, txt[int(r.integers(len(txt)))], x, r), lang, window=10 * 3600, topic=bid)
        else:
            txt = ST.REPLY_MEDIA_ES if es else ST.REPLY_MEDIA_EN
            S.ask(t, a, "re", ["media"], fill(S.A, a, txt[int(r.integers(len(txt)))], x, r), lang, window=10 * 3600, topic=bid)
    else:
        render_beat(S, a, b, x, r, t)


def run_residents(S):
    A = S.A
    people = [a for a in A.personas if a.kind == "individual" and not a.net]
    for a in people + A.compact:
        r = rng("res", a.handle)
        scale = 0.5 if not a.compact else 1.0
        if a in A.sleepers:
            scale *= 0.6
        for day in range(START_DAY, END_DAY + 1):
            lam = a.cadence * phase(day) * scale
            if a.compact and a.home is None:
                lam *= 0.5
            n = int(r.poisson(lam))
            for _ in range(n):
                t = sample_time(a, day, r)
                if r.random() > connected(a, dayf(t)):
                    continue
                resident_post(S, a, t, r)
        # "posts more often while power and signal last": the evening before landfall
        if a.home and not a.compact:
            for _ in range(int(r.poisson(1.2))):
                t = dts(-1 + float(r.uniform(0.7, 1.03)))
                render_beat(S, a, BEAT["staying"], dayf(t), r, t)


def inject(S, bid, accts, p, t0, t1, n_lo=1, n_hi=2, lang_only=None, ignore_conn=False):
    b = BEAT[bid] if bid != "blame" else BLAME_BEAT
    for a in accts:
        if b[5] is not None and a.home not in b[5]:
            continue
        r = rng("inj", bid, a.handle, t0)
        if r.random() > p:
            continue
        if lang_only == "es" and a.lang == "en":
            continue
        if lang_only == "en" and a.lang in ("es", "es/en"):
            continue
        for _ in range(int(r.integers(n_lo, n_hi + 1))):
            t = int(t0 + (t1 - t0) * float(r.beta(1.3, 2.6)))
            if not ignore_conn and r.random() > connected(a, dayf(t)):
                continue
            render_beat(S, a, b, dayf(t), r, t)


def run_injections(S):
    A = S.A
    locals_ = [a for a in A.personas if a.kind == "individual" and not a.net and a.home] + [a for a in A.compact if a.home]
    blast = int(dt.datetime.fromisoformat(canon()["channel_attack"]["blast"]["when"]["utc"].replace("Z", "+00:00")).timestamp())
    inject(S, "landfall_night", locals_, 0.3, dts(0 + 0.6 / 24), dts(0 + 8 / 24), 1, 2)
    inject(S, "oil_first", locals_, 0.3, dts(0 + 9 / 24), dts(1 + 8 / 24), 1, 1)
    inject(S, "blast_night", locals_, 0.75, blast + 25, blast + 3 * 3600, 1, 2, ignore_conn=True)
    for d in DRONE_NIGHTS:
        inject(S, "nas_lights", locals_, 0.3, local_ts(d, "21:30"), local_ts(d, "21:30") + 5 * 3600, 1, 2)
    inject(S, "watch_warning", locals_, 0.25, dts(-2 + 12.02 / 24), dts(-2 + 15 / 24))
    inject(S, "evac_zoneA", locals_, 0.5, dts(-2 + 6.1 / 24), dts(-2 + 12 / 24))
    inject(S, "morning_after", locals_, 0.5, dts(0 + 7 / 24), dts(0 + 20 / 24))
    inject(S, "boil_city", locals_, 0.3, dts(4 + 7.1 / 24), dts(4 + 12 / 24))
    inject(S, "d34_boil_en", locals_, 0.55, dts(12 + 17.55 / 24), dts(12 + 22 / 24), lang_only="en")
    inject(S, "d34_boil_es", locals_, 0.7, dts(13 + 6.1 / 24), dts(13 + 11 / 24), lang_only="es")
    inject(S, "cyber_reveal", locals_, 0.25, dts(21 + 12.1 / 24), dts(21 + 20 / 24))
    inject(S, "boil_lifted", locals_, 0.3, dts(39 + 9.1 / 24), dts(39 + 15 / 24))
    inject(S, "d34_lifted", locals_, 0.5, dts(42 + 11.1 / 24), dts(42 + 17 / 24))
    inject(S, "fema_reg", locals_, 0.2, dts(60 + 7.5 / 24), dts(60 + 18 / 24))
    inject(S, "arrests", locals_, 0.15, dts(90 + 14.5 / 24), dts(90 + 22 / 24))
    inject(S, "attribution", locals_, 0.2, dts(112 + 9 / 24), dts(112 + 21 / 24))
    inject(S, "blast_after", locals_, 0.2, dts(44 + 7 / 24), dts(44 + 20 / 24))
    inject(S, "power_last", locals_, 0.5, dts(35 + 15.1 / 24), dts(35 + 22 / 24))


# ======================================================================================
# businesses, community groups, reporters, outlets, agencies
# ======================================================================================
def run_phased(S, accts, phases, scale):
    for a in accts:
        r = rng("phased", a.handle)
        for day in range(START_DAY, END_DAY + 1):
            for _ in range(int(r.poisson(a.cadence * scale * (1.6 if -5 <= day <= 20 else 0.7)))):
                t = sample_time(a, day, r)
                x = dayf(t)
                if r.random() > connected(a, x) * (0.4 if 0 <= x < 3 else 1.0):
                    continue
                ph = [p for p in phases if p[0] <= x < p[1]]
                if not ph:
                    continue
                p = ph[int(r.integers(len(ph)))]
                lang = pick_lang(a, r)
                pool = p[4] if (lang == "es" and p[4]) else p[3]
                lang = "es" if pool is p[4] else "en"
                text = fill(S.A, a, pool[int(r.integers(len(pool)))], x, r)
                S.post(t, a, text, lang, pool="res:local", topic="local")
            if a.kind == "organization" and -3 <= day <= 45 and r.random() < 0.25:
                S.ask(sample_time(a, day, r), a, "rt", ["official"], topic="local")


def tco(url):
    return "https://t.co/" + hashlib.md5(url.encode()).hexdigest()[:10]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:70]


def first_sentence(s):
    s = re.sub(r"\s*\([^)]*scenario[^)]*\)", "", s)
    m = re.match(r"(.{30,235}?[.!?])(\s|$)", s)
    return (m.group(1) if m else s[:235]).strip()


def run_news(S):
    A = S.A
    rel = load_json("08_release/news_stories_public.json")["stories"]
    by_name = {a.name: a for a in A.personas if a.kind == "journalist"}
    n = 0
    for s in rel:
        hd = OUTLET_HANDLE.get(s["outlet"])
        if not hd or hd not in A.by:
            continue
        pub = dt.datetime.fromisoformat(s["published"])
        t = int(pub.timestamp())
        r = rng("story", s["id"])
        url = f"https://{OUTLET_SITE[s['outlet']]}/{pub:%Y/%m/%d}/{slug(s['headline'])}"
        head = s["headline"]
        lang = "en"
        if hd == "KNCB1480":
            head, lang = head.split(" / ")[0], "es"
        if len(head) > 240:
            head = head[:237] + "…"
        pre = ""
        if s.get("story_type") == "breaking" and hd == "Harborline6News":
            pre = "BREAKING: "
        t_out = t + int(r.integers(20, 240))
        acct = A.by[hd]
        # outlets off the air still post from backup power, except the radio station while its transmitter is down
        if hd == "KNCB1480" and dts(0 + 3.52 / 24) <= t_out < dts(1 + 2 / 24):
            t_out = dts(1 + 2 / 24) + int(r.integers(60, 3600))
        i = S.post(t_out, acct, f"{pre}{head} {tco(url)}", lang, pool=["media", "media:" + hd], url=url, topic="story")
        n += i is not None
        for au in s.get("authors", []):
            j = by_name.get(au)
            if j:
                if r.random() < 0.55:
                    lead = str(r.choice(["New from me:", "Our story:", "Latest:", "Just published:", "Thread on this soon.", "Filed:"]))
                    S.post(t_out + int(r.integers(120, 1800)), j, f"{lead} {head} {tco(url)}", lang, pool=["media"], url=url, topic="story")
                else:
                    S.ask(t_out + int(r.integers(90, 1500)), j, "rt", ["media:" + hd], window=3600, topic="story")
    # reporters' notes
    for j in by_name.values():
        r = rng("journo", j.handle)
        for day in range(START_DAY, END_DAY + 1):
            for _ in range(int(r.poisson(j.cadence * 0.3 * phase(day)))):
                t = sample_time(j, day, r)
                x = dayf(t)
                if r.random() < 0.3 and x > -6:
                    S.ask(t, j, "rt", ["official"], topic="journo")
                else:
                    line = ST.JOURNO[int(r.integers(len(ST.JOURNO)))]
                    if x < 1.0 and "after the storm" in line:          # nobody has waited for help before the storm has passed
                        line = "Asked the agency for comment. Will update."
                    S.post(t, j, fill(A, j, line, x, r), "en", topic="journo")
    # public facts as short items from the local outlets
    facts = load_json("02_public_record/public_record.json")["facts"]
    for f in facts:
        if f.get("type") or f["day"] < START_DAY:
            continue
        fs = first_sentence(f["statement"])
        if re.search(r"[Nn]ever name|scenario|^[A-Z ,\-—:0-9]{25,}", fs):
            continue
        r = rng("fact", f["id"])
        base = local_ts(f["day"], f.get("time_local") or "00:00")
        if not f.get("time_local"):
            base += int(r.integers(int(8.5 * 3600), 17 * 3600))
        if f["day"] == 0 and base < dts(0 + 6 / 24):
            base = dts(0 + 6.5 / 24) + int(r.integers(0, 5400))
        for hd, pr_, lead in (("Harborline6News", 0.8, ["NEW: ", "JUST IN: ", "UPDATE: ", ""]), ("BaysideLedger", 0.45, ["", "Developing: ", ""]),
                              ("CoastlinePublicRadio", 0.2, [""])):
            if r.random() < pr_:
                S.post(base + int(r.integers(300, 5400)), A.by[hd], str(r.choice(lead)) + fs, "en", pool=["media", "media:" + hd], topic="fact")
    # service posts from the two daily local outlets
    for hd, per_day in (("Harborline6News", 3.0), ("BaysideLedger", 1.2), ("KNCB1480", 1.0)):
        a = A.by[hd]
        r = rng("fill", hd)
        for day in range(START_DAY, END_DAY + 1):
            for _ in range(int(r.poisson(per_day * (1.5 if -5 <= day <= 20 else 0.6)))):
                t = sample_time(a, day, r)
                if hd == "KNCB1480":
                    if dts(0 + 3.52 / 24) <= t < dts(1 + 2 / 24):
                        continue
                    S.ask(t, a, "rt", ["official_es", "official"], window=12 * 3600, topic="fill")
                elif r.random() < 0.5:
                    S.ask(t, a, "rt", ["official"], window=6 * 3600, topic="fill")
                else:
                    S.post(t, a, fill(A, a, ST.MEDIA_FILL[int(r.integers(len(ST.MEDIA_FILL)))], dayf(t), r), "en", pool=["media"], topic="fill")
    # national wire and the two aggregators
    a = A.by["ContinentalWire"]
    r = rng("wire")
    for day in range(START_DAY, END_DAY + 1):
        for _ in range(int(r.poisson(9))):
            t = local_ts(day, "00:00") + int(r.integers(5 * 3600, 23 * 3600))
            S.post(t, a, ST.WIRE[int(r.integers(len(ST.WIRE)))], "en", topic="wire")
    for hd, rate in (("GulfEnergyDesk", 3.0), ("WorldLineNews24", 3.5)):
        a = A.by[hd]
        r = rng("agg", hd)
        for day in range(START_DAY, END_DAY + 1):
            for _ in range(int(r.poisson(rate * (1.4 if -3 <= day <= 60 else 0.6)))):
                t = local_ts(day, "00:00") + int(r.integers(0, DAY))
                x = dayf(t)
                if hd == "WorldLineNews24" and 46.3 <= x <= 52 and r.random() < 0.5:
                    S.post(t, a, str(r.choice(["The great export port, closed again by a single blast. So much for strength.",
                                               "Twice in two months the Americans cannot keep one channel open. The world is watching.",
                                               "A superpower that cannot guard its own harbor lectures others about security."])), "en", pool=["media"], topic="mock")
                elif r.random() < 0.7:
                    S.ask(t, a, "q" if r.random() < 0.6 else "rt", ["media:SabalEnergyWire", "media:GulfwaterMaritime", "media", "official"],
                          str(r.choice(["Worth watching.", "Markets will notice.", "Exports at stake.", "More on this.", "Developing.", "Via local reporting."])),
                          window=18 * 3600, topic="agg")
                else:
                    S.post(t, a, ST.WIRE[int(r.integers(len(ST.WIRE)))], "en", topic="wire")


def run_official(S):
    A = S.A
    for hd, day, hm, en, es in SS.OFFICIAL:
        if hd not in A.by:
            continue
        a = A.by[hd]
        r = rng("off", hd, day, hm)
        t = local_ts(day, hm) + int(r.integers(5, 55))
        if en:
            i = S.post(t, a, en, "en", pool=["official", "official:" + hd] + (["media"] if a.kind == "media" else []), topic="official")
            t += int(r.integers(60, 240))
        if es:
            S.post(t, a, es, "es", pool=["official", "official_es", "official:" + hd], topic="official")
    # hurricane center advisories, as issued (weather stream on disk)
    p = os.path.join(ROOT, "05_other_sources/weather/nhc_advisories.json")
    if os.path.exists(p):
        adv = json.load(open(p, encoding="utf-8"))["advisories"]
        nhc, nws = A.by["NationalHurricaneCenter"], A.by["NWSCorpusChristi"]
        for ad in adv:
            t = int(dt.datetime.fromisoformat(ad["issued_utc"].replace("Z", "+00:00")).timestamp())
            name = ad["storm_name"].title()
            text = f"{ad['classification']} {name} Advisory {ad['advisory_number']}: {ad['headline']}. Maximum sustained winds {ad['max_sustained_winds_mph']} mph. Moving {ad['movement']}."
            i = S.post(t + 90, nhc, text, "en", pool=["official", "official:NationalHurricaneCenter"], topic="advisory")
            if ad.get("distance_to_corpus_christi_nm", 9999) < 700:
                S.ask(t + 400, nws, "rt", ["official:NationalHurricaneCenter"], window=900, topic="advisory")
    # weather office: a morning forecast and an evening summary that agree with what the airport station recorded
    obs = read_series("05_other_sources/weather/KCRP_ASOS_observations.csv", "ObsDateTime", ["DryBulbTemp_C", "WindSpeed_mps", "WindDir_deg"])
    byday = defaultdict(list)
    for t, (tc, ws, wd) in obs:
        try:
            byday[day_of(t)].append((float(tc) * 9 / 5 + 32, float(ws) / 0.44704, float(wd)))
        except ValueError:
            continue
    nws = A.by["NWSCorpusChristi"]
    for d in sorted(byday):
        v = byday[d]
        if len(v) < 18 or -1 <= d <= 2:
            continue
        hi_f, lo_f = round(max(x[0] for x in v)), round(min(x[0] for x in v))
        wind = sorted(x[1] for x in v)[len(v) // 2]
        wdir = compass(sorted(x[2] for x in v)[len(v) // 2])
        r = rng("nwsfc", d)
        S.post(local_ts(d, "04:45") + int(r.integers(0, 600)), nws, f"Today: high near {hi_f}. {wdir} wind {max(5, int(wind // 5 * 5))} to {int(wind // 5 * 5) + 10} mph. Tonight: low around {lo_f}.",
               "en", pool=["official", "official:NWSCorpusChristi"], topic="forecast")
        S.post(local_ts(d + 1, "07:10") + int(r.integers(0, 900)), nws, f"Yesterday at Corpus Christi International: high {hi_f}, low {lo_f}.", "en", topic="forecast")
    # routine reminders so agency feeds are not only emergencies
    remind = {"CBECC_911": ["Text-to-911 is available in Nueces County when you cannot make a voice call.", "Teach children their address and when to call 911."],
              "NWSCorpusChristi": ["Forecast discussion updated. See our page for the seven-day outlook.", "Rip current risk is posted daily for area beaches. Check before you swim."],
              "CCFDCCPD": ["Never drive around barricades.", "Check your smoke alarm batteries this weekend.", "Generators outside only, far from windows."],
              "txdot_coastal": ["Lane closures this week are posted on our district page.", "Ferry wait times are on the ferry page."],
              "CCRTA_Rides": ["Service changes and detours are posted on the rider alerts page."],
              "NuecesSheriff": ["Scam reminder: no deputy will ever call asking for payment by gift card."],
              "CityofPortAransas": ["Beach and street updates are posted on the city page every morning."],
              "SanPatCountyOEM": ["Know your zone. Evacuation zone maps are on the county page."],
              "AransasCountyOEM": ["Sign up for county alerts by text."],
              "TAMUCC_Island": ["Campus status updates are on the university page."],
              "CCIntlAirport": ["Check with your airline for flight status before you travel."],
              "GulfCoastReliefNet": ["Cash donations help most after a disaster. Volunteers: register before you come."],
              "TxTaskForce1": ["Swift-water teams train year round. Turn around, don't drown."],
              "USACE_Galveston": ["Channel survey results are posted as they are completed."],
              "NuecesInfoLine": ["Questions about county services? Call or text the information line.", "¿Preguntas sobre servicios del condado? Llame o envíe un mensaje a la línea de información."]}
    for hd, lines in remind.items():
        a = A.by.get(hd)
        if not a:
            continue
        r = rng("remind", hd)
        for day in range(START_DAY, END_DAY + 1):
            if r.random() < min(0.5, a.cadence * 0.18):
                tx = lines[int(r.integers(len(lines)))]
                S.post(sample_time(a, day, r), a, tx, "es" if tx.startswith("¿") else "en", pool=["official", "official:" + hd], topic="remind")
            if -3 <= day <= 45 and r.random() < 0.3:
                S.ask(sample_time(a, day, r), a, "rt", ["official"], window=6 * 3600, topic="remind")
    for hd in ("CCEmergencyMgmt", "NuecesOEM", "FEMARegion6", "TDEM_Region", "CBPWA_Alerts", "CityofCCWater", "USCGSectorCC", "PortCorpusChristi", "NASCorpusChristi"):
        a = A.by[hd]
        r = rng("xrt", hd)
        for day in range(-5, 46):
            for _ in range(int(r.poisson(1.1))):
                S.ask(sample_time(a, day, r), a, "rt", ["official"], window=5 * 3600, topic="remind")


# ======================================================================================
# automated accounts: relay what the sensors published
# ======================================================================================
def read_series(rel, tcol, cols):
    p = os.path.join(ROOT, rel)
    out = []
    if not os.path.exists(p):
        return out
    with open(p, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                t = int(dt.datetime.fromisoformat(row[tcol]).replace(tzinfo=dt.timezone.utc).timestamp())
                out.append((t, [row.get(c, "") for c in cols]))
            except (ValueError, KeyError):
                continue
    return out


def hourly(series):
    """One reading per hour: the first observation at or after each top of the hour (within 30 minutes)."""
    out, last_h = [], None
    for t, vals in series:
        hkey = t // 3600
        if hkey != last_h:
            out.append((t, vals))
            last_h = hkey
    return out


def compass(deg):
    return ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][int((float(deg) + 11.25) // 22.5) % 16]


_OUTAGE = {}


def outage_count(t):
    """Customers without power according to the utility's outage map: the sum over feeders in
    05_other_sources/telemetry/outage_map.csv at the quarter hour at or before t (None outside the map's span)."""
    if not _OUTAGE:
        with open(os.path.join(ROOT, "05_other_sources/telemetry/outage_map.csv"), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                k = r["timestamp_utc"]
                if k[14:16] in ("00", "15", "30", "45") and k[17:19] == "00":
                    _OUTAGE[k] = _OUTAGE.get(k, 0) + int(r["customers_out"])
        _OUTAGE["_lo"], _OUTAGE["_hi"] = min(k for k in _OUTAGE if k[0] == "2"), max(k for k in _OUTAGE if k[0] == "2")
    q = int(t) - int(t) % 900
    k = dt.datetime.fromtimestamp(q, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not (_OUTAGE["_lo"] <= k <= _OUTAGE["_hi"]):
        return None
    return _OUTAGE.get(k, 0)


_FERRY = set()


def ferry_running(t):
    """True if any Port Aransas ferry is under way in the AIS feed during the UTC hour of t."""
    if not _FERRY:
        import glob as _glob
        mmsi = {str(v["mmsi"]) for v in json.load(open(os.path.join(ROOT, "06_data_streams/vessels.json"), encoding="utf-8"))["vessels"] if v.get("class") == "ferry"}
        for fp in sorted(_glob.glob(os.path.join(ROOT, "05_other_sources/ais/ais_*.csv"))):
            with open(fp, encoding="utf-8", newline="") as fh:
                rd = csv.reader(fh)
                hd = next(rd)
                im, it, isog = hd.index("MMSI"), hd.index("BaseDateTime"), hd.index("SOG")
                for row in rd:
                    if row[im] in mmsi and row[isog] and float(row[isog]) > 1.0:
                        _FERRY.add(row[it][:13])
        _FERRY.add("loaded")
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%dT%H") in _FERRY


def run_automated(S):
    A = S.A
    # weather at the airport
    ser = hourly(read_series("05_other_sources/weather/KCRP_ASOS_observations.csv", "ObsDateTime",
                             ["DryBulbTemp_C", "WindDir_deg", "WindSpeed_mps", "WindGust_mps", "SeaLevelPressure_mb", "PresentWx"]))
    for t, (tc, wd, ws, wg, slp, wx) in ser:
        try:
            f = round(float(tc) * 9 / 5 + 32)
            kt = round(float(ws) / 0.514444)
            txt = f"KCRP {dt.datetime.fromtimestamp(t, dt.timezone.utc):%H%MZ}: {f}°F, wind {compass(wd) if kt > 2 else 'calm'}{' ' + str(kt) + ' kt' if kt > 2 else ''}"
            if wg:
                txt += f" gusting {round(float(wg) / 0.514444)}"
            if slp:
                txt += f", {float(slp):.1f} mb"
            if wx:
                txt += f", {wx}"
        except ValueError:
            continue
        S.post(t + 240, "CC_WxBot", txt, "en", topic="auto")
    ser = hourly(read_series("05_other_sources/env_sensors/gauge_GAUGE-12.csv", "ObsDateTime", ["Stage_ft", "Discharge_cfs"]))
    for t, (st, q) in ser[::2]:
        if st:
            S.post(t + 300, "NuecesRiverGauge", f"Nueces River at Calallen: stage {float(st):.2f} ft, flow {float(q):,.0f} cfs" if q else f"Nueces River at Calallen: stage {float(st):.2f} ft", "en", topic="auto")
    ser = hourly(read_series("05_other_sources/env_sensors/gauge_GAUGE-14.csv", "ObsDateTime", ["WaterLevel_ft_MLLW", "Predicted_ft_MLLW"]))
    for t, (wl, pr) in ser:
        if wl:
            d = float(wl) - float(pr or wl)
            S.post(t + 200, "TideBotCC", f"Corpus Christi Bay (USS Lexington): water level {float(wl):.2f} ft MLLW, {abs(d):.2f} ft {'above' if d >= 0 else 'below'} prediction", "en", topic="auto")
    ser = hourly(read_series("05_other_sources/weather/BUOY42020_observations.csv", "ObsDateTime", ["WVHT_m", "DPD_s", "WSPD_mps", "WDIR_degT"]))
    for t, (wv, dp, ws, wd) in ser[::2]:
        try:
            S.post(t + 600, "GulfBuoyBot", f"Buoy 42020: seas {float(wv) * 3.281:.1f} ft at {float(dp):.0f} s, wind {compass(wd)} {round(float(ws) / 0.514444)} kt", "en", topic="auto")
        except ValueError:
            continue
    # outage counter: only when there is something to count, every hour
    r = rng("outage")
    t = dts(0 + 1 / 24)
    while t < dts(36):
        n = outage_count(t + 420)
        if n:
            S.post(t + 420, "TXOutageCount", f"Nueces County, TX: {n:,} customers without power (CBPWA outage map)", "en", topic="auto")
        t += 3600
    for day in range(-30, END_DAY + 1):
        if not (0 <= day < 36) and r.random() < 0.5:
            tp = local_ts(day, "08:00") + int(r.integers(0, 600))
            n = outage_count(tp)
            if n is None:                                   # the map file does not cover this day: an ordinary day's handful of small outages
                n = int(r.choice([0, 0, 12, 25, 40, 64, 110, 180, 260]))
            S.post(tp, "TXOutageCount", f"Nueces County, TX: {n:,} customers without power (CBPWA outage map)", "en", topic="auto")
    # ferry wait: suspended ahead of the storm, back after island access is restored; shut again after the blast
    r = rng("ferry")
    for day in range(-30, END_DAY + 1):
        for hr in range(6, 23):
            t = local_ts(day, f"{hr:02d}:00") + int(r.integers(0, 300))
            x = dayf(t)
            if not ferry_running(t):                        # nothing under way in this hour (storm, channel closed, overnight lull)
                day_idle = not any(ferry_running(local_ts(day, f"{hh:02d}:00")) for hh in range(6, 23))
                if day_idle and hr in (7, 17):
                    S.post(t, "AransasFerryWait", "Port Aransas ferry: service suspended", "en", topic="auto")
                continue
            wd = (dt.date(2027, 9, 14) + dt.timedelta(days=day)).weekday()
            base = (22 if wd >= 5 else 9) * (1.0 if day < -5 else 0.55) * (1.0 + 0.8 * math.exp(-((hr - 16) / 3.0) ** 2))
            wait = max(0, int(r.normal(base, base * 0.35) // 5 * 5))
            S.post(t, "AransasFerryWait", f"Port Aransas ferry wait: {wait} min" + (f", {int(r.integers(3, 7))} boats running" if wait > 15 else ""), "en", topic="auto")
    # traffic alerts on real roads
    r = rng("traffic")
    G = A.G
    cross = ["Staples St", "Everhart Rd", "Airline Rd", "Weber Rd", "Kostoryz Rd", "Ayers St", "Greenwood Dr", "Leopard St", "Port Ave", "Navigation Blvd",
             "Rodd Field Rd", "Nile Dr", "Flour Bluff Dr", "Violet Rd", "McKinzie Rd"]
    main = ["SH 358 (SPID)", "I-37", "SH 286 (Crosstown)", "US 181", "Saratoga Blvd", "Holly Rd", "Ocean Dr", "Agnes St"]
    kinds = ["Crash reported", "Stalled vehicle", "Debris in roadway", "Signal out", "Crash cleared", "Lane blocked"]
    for day in range(-30, END_DAY + 1):
        lam = 9 if day < -2 else (2 if day < 3 else (14 if day < 30 else 9))
        for _ in range(int(r.poisson(lam))):
            t = local_ts(day, "00:00") + int(r.choice(24, p=HOURW / HOURW.sum())) * 3600 + int(r.integers(0, 3600))
            x = dayf(t)
            if 0 <= x < 0.5:
                continue
            k = str(r.choice(kinds))
            if 0.3 < x < 20 and r.random() < 0.45:
                k = str(r.choice(["Signal out", "Debris in roadway", "Tree down", "High water", "Lines down"]))
            S.post(t, "CCTrafficAlerts", f"{k}: {main[int(r.integers(len(main)))]} at {cross[int(r.integers(len(cross)))]}", "en", topic="auto")
    for (x0, x1, txt) in ((-0.1, 3.5, "CLOSED: Harbor Bridge and Nueces Bay Causeway"), (-1.0, -0.02, "Contraflow in effect: US 181 northbound")):
        t = dts(x0)
        while t < dts(x1):
            S.post(t + int(r.integers(0, 600)), "CCTrafficAlerts", txt, "en", topic="auto")
            t += 6 * 3600


# ======================================================================================
# the coordinated accounts
# ======================================================================================
def mutate(text, r, k):
    """Small per-account differences on a shared text (the wording stays the same)."""
    pre, suf = SS.PREFIX[int(r.integers(len(SS.PREFIX)))], SS.SUFFIX[int(r.integers(len(SS.SUFFIX)))]
    if text.startswith(("BREAKING", "PSA", "CONFIRMED", "Heads up")):
        pre = ""
    out = pre + text + suf
    if k % 5 == 1:
        out = out.replace(". ", ".  ", 1)
    if k % 7 == 2 and "#" in out:
        tags = re.findall(r"#\w+", out)
        body = re.sub(r"\s*#\w+", "", out).strip()
        out = body + " " + " ".join(reversed(tags))
    if k % 9 == 3:
        out = out.replace("NOTHING", "nothing").replace("NOW", "now")
    return out


def lure_url(r):
    path = str(r.choice(["apply", "register", "claim", "check", "protect"]))
    return f"{SS.LURE}/{path}?ref={int(r.integers(1000, 9999))}"


CLUSTER_WIN = None


def net_post(S, t, a, text, r, pool, topic, k=0, link_p=0.0):
    url = None
    if topic == "phase1" and CLUSTER_WIN and CLUSTER_WIN[0] - 5400 <= t <= CLUSTER_WIN[1] + 5400 and "Zavala" in text:
        t = CLUSTER_WIN[1] + 5400 + int(r.integers(60, 7200))
    if "{url}" in text or (link_p and r.random() < link_p):
        url = lure_url(r)
        text = text.replace("{url}", tco(url)) if "{url}" in text else text + " " + tco(url)
    return S.post(t, a, mutate(text, r, k), "en", pool=pool, url=url, topic=topic)


def run_network(S):
    A = S.A
    r = rng("network")
    t15 = A.t15
    leadA, leadB = A.by[SS.LEAD_A], A.by[SS.LEAD_B]
    followers = [a for a in t15 if a not in (leadA, leadB)]
    anchors = {(hd, iso_): txt for hd, iso_, txt in SS.ANCHOR_POSTS}

    def anchor_t(s):
        return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp())

    global CLUSTER_WIN
    CLUSTER_WIN = (dts(-2 + (11 + 20 / 60) / 24), dts(-2 + (13 + 37 / 60) / 24))
    # --- profile building
    for a in t15:
        ra = rng("aging", a.handle)
        t_end = dts(-5 + 3 / 24)
        if a.created > dts(-20):
            for _ in range(int(ra.integers(4, 9))):
                S.post(int(ra.integers(a.created + 600, t_end)), a, SS.AGING[int(ra.integers(len(SS.AGING)))], "en", topic="aging")
        else:
            for day in range(START_DAY, -5):
                if ra.random() < 0.35:
                    S.post(sample_time(a, day, ra), a, SS.AGING[int(ra.integers(len(SS.AGING)))], "en", topic="aging")
    # --- phase 1: false shelter and route posts, D-5 03:00 local to landfall
    p1_start, p1_end = dts(-5 + 3 / 24), dts(0 + 1 / 24)
    for (hd, s), txt in anchors.items():
        if s.startswith("2027-09-09"):
            S.post(anchor_t(s), hd, txt, "en", pool=["rumor", "phase1"], topic="phase1")
        elif s.startswith("2027-09-14"):
            S.post(anchor_t(s), hd, txt, "en", pool=["rumor", "blame", "blame_seed"], topic="phase2")
        else:
            S.post(anchor_t(s), hd, txt, "en", pool=["rumor", "coverup"], topic="phase3")
    for lead, n in ((leadA, 21), (leadB, 18)):                     # 22 and 19 posts from D-5 to D-2, anchors included
        rl = rng("p1lead", lead.handle)
        for _ in range(n):
            t = int(rl.integers(p1_start + 3600, dts(-1)))
            pool_txt = SS.SHELTER_FALSE if rl.random() < 0.5 else (SS.ROUTE_FALSE if rl.random() < 0.7 else SS.SURGE_FEAR)
            net_post(S, t, lead, pool_txt[int(rl.integers(len(pool_txt)))], rl, ["rumor", "phase1"], "phase1", int(rl.integers(0, 12)))
        for _ in range(4):
            t = int(rl.integers(dts(-1), p1_end))
            net_post(S, t, lead, SS.SURGE_FEAR[int(rl.integers(2))], rl, ["rumor", "phase1"], "phase1", int(rl.integers(0, 12)))
    for a in followers:
        ra = rng("p1", a.handle)
        for _ in range(int(ra.integers(3, 8))):
            t = int(ra.integers(p1_start + 2 * 3600, p1_end))
            pool_txt = SS.SHELTER_FALSE if ra.random() < 0.45 else (SS.ROUTE_FALSE if ra.random() < 0.7 else SS.SURGE_FEAR)
            net_post(S, t, a, pool_txt[int(ra.integers(len(pool_txt)))], ra, ["rumor", "phase1"], "phase1", int(ra.integers(0, 12)))
    # the D-2 cluster: 11 accounts, 34 near-identical shelter posts in 2 h 17 min (11:20 to 13:37 local)
    cl = sorted(followers, key=lambda a: h("cluster", a.handle))[:11]
    c0, c1 = dts(-2 + (11 + 20 / 60) / 24), dts(-2 + (13 + 37 / 60) / 24)
    times = sorted([c0, c1] + [int(x) for x in r.integers(c0 + 30, c1 - 30, size=32)])
    for k, t in enumerate(times):
        net_post(S, t, cl[k % 11], SS.SHELTER_FALSE[k % 2], r, ["rumor", "phase1", "cluster"], "cluster", k)

    # --- phase 2: the utility is to blame. Seeds from the two anchor accounts, the rest follow within minutes
    def seeds_for(day):
        """(lead A count, lead B count, follower posts) for a local day."""
        if day == 0: return 30, 27, 40
        if day in (1, 2): return 3, 3, 19
        if 3 <= day <= 10: return 11, 10, 189
        if 11 <= day <= 20: return 1, 1, max(8, 44 - 3 * (day - 11))
        return 0, 0, 0

    for day in range(0, 21):
        nA, nB, nF = seeds_for(day)
        day0 = max(dts(day), dts(0 + 1.02 / 24))
        seed_times = []
        for lead, n in ((leadA, nA), (leadB, nB)):
            for _ in range(n):
                t = int(r.integers(day0 + 600, dts(day + 1) - 600))
                txt = SS.BLAME_NET[int(r.integers(len(SS.BLAME_NET)))]
                if lead is leadB and seed_times and r.random() < 0.4:
                    st, txt = seed_times[int(r.integers(len(seed_times)))]
                    t = st + int(r.integers(60, 230))
                i = net_post(S, t, lead, txt, r, ["rumor", "blame", "blame_seed"], "phase2", int(r.integers(0, 12)))
                if i is not None:
                    seed_times.append((t, txt))
        if day == 0:
            for (hd, s), txt in anchors.items():
                if s.startswith("2027-09-14"):
                    seed_times.append((anchor_t(s), txt))
        if not seed_times:
            continue
        for k in range(nF):
            a = followers[int(r.integers(len(followers)))]
            st, stxt = seed_times[int(r.integers(len(seed_times)))]
            if r.random() < (0.95 if day <= 2 else 0.72):
                t = st + int(r.integers(35, 236))            # inside four minutes of the seed, same wording
                txt = stxt if r.random() < 0.8 else SS.BLAME_NET[int(r.integers(len(SS.BLAME_NET)))]
            else:
                t = int(r.integers(day0 + 600, dts(day + 1) - 60))
                txt = SS.BLAME_NET[int(r.integers(len(SS.BLAME_NET)))]
            if txt.startswith(("Sources inside", "A utility worker")):
                txt = SS.BLAME_NET[int(r.integers(2))]
            net_post(S, t, a, txt, r, ["rumor", "blame"], "phase2", k)

    # --- the rumour network: 40 accounts, three narratives, shared slots, D+2 to D+20
    base = A.base40
    total_target, made = 18000, 0
    days = list(range(2, 21))
    wday = np.array([0.8, 1.2, 1.3, 1.25, 1.2, 1.1, 1.05, 1.0, 1.0, 1.0, 0.95, 0.95, 0.9, 0.9, 0.85, 0.85, 0.85, 0.8, 0.75])
    per_day = np.round(wday / wday.sum() * total_target).astype(int)
    per_day[-1] += total_target - per_day.sum()
    for day, n_day in zip(days, per_day):
        active = [a for a in base if not a.stop or dts(day + 0.5) < a.stop]
        if day >= 5:                                   # the two anchor accounts leave the rumour slots and go quiet
            active = [a for a in active if a not in (leadA, leadB)]
        left = int(n_day)
        while left > 0:
            hr = int(r.choice(24, p=NETHOUR))
            slot = local_ts(day, "00:00") + hr * 3600 + int(r.choice([7, 22, 37, 52])) * 60 + int(r.integers(0, 40))
            x = dayf(slot)
            w_seize = 3.0 * math.exp(-(x - 2) / 2.5)
            w_wealthy = 1.6 if x >= 2 else 0
            w_ref = 1.5 if x >= 3 else 0
            pick = r.choice(3, p=np.array([w_seize, w_wealthy, w_ref]) / (w_seize + w_wealthy + w_ref))
            pool_txt = (SS.SEIZE, SS.WEALTHY, SS.REFINERY)[int(pick)]
            topic = ("seize", "wealthy", "refinery")[int(pick)]
            txt = pool_txt[int(r.integers(len(pool_txt)))]
            k = min(left, int(r.integers(12, 27)), len(active))
            who = list(r.choice(len(active), size=k, replace=False))
            # the two public-facing accounts lead their narratives
            for hd, tp in (("CoastTruthTX", ("seize", "wealthy")), ("GulfWatchPatriot", ("refinery",))):
                a = A.by[hd]
                if topic in tp and a in active and active.index(a) not in who and r.random() < 0.7:
                    who[0] = active.index(a)
            for j, ai in enumerate(who):
                i = net_post(S, slot + int(r.integers(0, 110)), active[ai], txt, r, ["rumor", "rumor:" + topic], topic, j, link_p=0.3)
                made += i is not None
            left -= k

    # --- phase 3: "it was not an attack", after the federal announcement on D+21
    p3 = dts(21) + int(13.5 * 3600)
    for day in range(21, 39):
        nA = nB = 0
        if day <= 30:
            nA, nB = (31, 30) if day <= 24 else (13, 12)
        nF = 60 if day <= 24 else (34 if day <= 30 else 18)
        day0 = max(dts(day), p3)
        seed_times = []
        for lead, n in ((leadA, nA), (leadB, nB)):
            for _ in range(n):
                t = int(r.integers(day0 + 300, dts(day + 1) - 300))
                txt = SS.COVERUP_NET[int(r.integers(len(SS.COVERUP_NET)))]
                if net_post(S, t, lead, txt, r, ["rumor", "coverup"], "phase3", int(r.integers(0, 12))) is not None:
                    seed_times.append((t, txt))
        if day == 21:
            for (hd, s), txt in anchors.items():
                if s.startswith("2027-10-05"):
                    seed_times.append((anchor_t(s), SS.COVERUP_NET[0 if hd == SS.LEAD_A else 3]))
        for k in range(nF):
            a = followers[int(r.integers(len(followers)))]
            if seed_times and r.random() < 0.65:
                st, stxt = seed_times[int(r.integers(len(seed_times)))]
                t, txt = st + int(r.integers(35, 236)), stxt
            else:
                t, txt = int(r.integers(day0 + 300, dts(day + 1) - 60)), SS.COVERUP_NET[int(r.integers(len(SS.COVERUP_NET)))]
            net_post(S, t, a, txt, r, ["rumor", "coverup"], "phase3", k)

    # --- amplifiers and ordinary users pass the rumours on while they are live
    amps = A.amplifiers
    locals_ = [a for a in A.compact if a not in amps and a not in A.sleepers]
    rumor_idx = list(S.pools["rumor"])
    for i in rumor_idx:
        src = S.tw[i]
        heat = 1.0 if src["topic"] in ("seize", "wealthy", "refinery") else (2.2 if src["topic"] in ("phase2", "phase3") else 0.6)
        for _ in range(int(r.poisson(0.38 * heat))):
            a = amps[int(r.integers(len(amps)))]
            S.req.append({"t": src["t"] + int(r.exponential(900)) + 40, "a": a.handle, "kind": "rt", "pools": ["__direct__"], "text": "", "lang": "en",
                          "window": 0, "topic": "amp", "direct": i})
        if r.random() < 0.07 * heat:
            a = locals_[int(r.integers(len(locals_)))]
            S.req.append({"t": src["t"] + int(r.exponential(2400)) + 60, "a": a.handle, "kind": "rt", "pools": ["__direct__"], "text": "", "lang": "en",
                          "window": 0, "topic": "amp", "direct": i})

    # --- second wave, D+75 to D+85: the same playbook from accounts that were never removed
    sl = A.sleepers
    for a in sl:                                    # a little history first
        ra = rng("sl-age", a.handle)
        for day in range(START_DAY, 75):
            if ra.random() < 0.05:
                S.post(sample_time(a, day, ra), a, SS.AGING[int(ra.integers(len(SS.AGING)))], "en", topic="aging")
    for day in range(75, 86):
        n_day = int(r.integers(190, 250))
        left = n_day
        while left > 0:
            hr = int(r.choice(24, p=NETHOUR))
            slot = local_ts(day, "00:00") + hr * 3600 + int(r.choice([7, 22, 37, 52])) * 60 + int(r.integers(0, 40))
            txt = SS.SECOND_WAVE[int(r.integers(len(SS.SECOND_WAVE)))]
            k = min(left, int(r.integers(10, 22)))
            for j, ai in enumerate(r.choice(len(sl), size=k, replace=False)):
                net_post(S, slot + int(r.integers(0, 110)), sl[int(ai)], txt, r, ["rumor2"], "wave2", j, link_p=0.12)
            left -= k
    for i in list(S.pools["rumor2"]):
        if r.random() < 0.25:
            a = locals_[int(r.integers(len(locals_)))]
            S.req.append({"t": S.tw[i]["t"] + int(r.exponential(1800)) + 60, "a": a.handle, "kind": "rt", "pools": ["__direct__"], "text": "", "lang": "en",
                          "window": 0, "topic": "amp", "direct": i})
    return made


NETHOUR = np.array([2, 1.5, 1, .5, .3, .3, .6, 1, 1.4, 1.6, 1.8, 2, 2.2, 2.2, 2, 2, 2.2, 2.4, 2.8, 3, 3, 3, 2.8, 2.4])
NETHOUR = NETHOUR / NETHOUR.sum()
BLAME_RX = re.compile(r"#CBPWA\b|#CorpusChristiOUT|#CBPWAfail|#LightsOutCC|#SinLuzCC", re.I)


def run_blame_fill(S, target_total=14200):
    """Ordinary accounts pick up the utility-blame framing: by D+10 the tracked hashtags reach about 14,200 posts."""
    A = S.A
    r = rng("blamefill")
    t0, t1 = dts(0) + 3600, dts(11)
    have = sum(1 for t in S.tw if t0 <= t["t"] < t1 and BLAME_RX.search(t["text"]))
    have += sum(1 for q in S.req if q.get("topic") == "amp" and t0 <= q["t"] < t1 and BLAME_RX.search(S.tw[q["direct"]]["text"]))
    # retweet requests that will resolve into the blame pools are few; leave a small margin for them
    need = max(0, target_total - have - 260)
    old = [a for a in A.compact if a.home and a not in A.sleepers and a.created < ts_date(2027, 6, 10)]
    new = [a for a in A.compact if a.home and a not in A.sleepers and a.created >= ts_date(2027, 6, 10) and a not in A.amplifiers]
    amp_local = [a for a in A.amplifiers if a.home]
    wday = np.array([0.35, 0.8, 1.05, 1.2, 1.25, 1.2, 1.15, 1.4, 1.2, 1.1, 1.3])
    wday = wday / wday.sum()
    b = BLAME_BEAT
    for _ in range(need):
        day = int(r.choice(11, p=wday))
        u = r.random()
        a = (old if u < 0.86 else (amp_local if u < 0.95 else new))
        a = a[int(r.integers(len(a)))]
        t = sample_time(a, day, r)
        if day == 0 and t < dts(0 + 10 / 24):
            t = dts(0 + 10 / 24) + int(r.integers(0, 12 * 3600))
        v = r.random()
        if v < 0.5:
            render_beat(S, a, b, dayf(t), r, t)
        elif v < 0.85:
            S.ask(t, a, "rt", ["blame_seed", "blame", "res:blame"], window=10 * 3600, topic="blame")
        else:
            txt = ST.QUOTE_EN[int(r.integers(len(ST.QUOTE_EN)))]
            S.ask(t, a, "q", ["blame"], fill(A, a, txt, dayf(t), r) + " " + ST.BLAME_TAGS[int(r.integers(3))], "en", window=10 * 3600, topic="blame")
    # the anger does not stop on day ten
    for _ in range(3200):
        day = 11 + int(min(24, abs(r.exponential(8))))
        a = old[int(r.integers(len(old)))]
        if day > 14 and a.home not in ST.LATE_POWER and r.random() < 0.6:
            continue
        t = sample_time(a, day, r)
        render_beat(S, a, b, dayf(t), r, t) if r.random() < 0.6 else S.ask(t, a, "rt", ["blame", "res:blame"], window=12 * 3600, topic="blame")
    return need


# ======================================================================================
# output
# ======================================================================================
def followers_at(a, t):
    d = (t - D0_EPOCH) / DAY
    g = {"official": 0.35, "media": 0.3, "journalist": 0.25, "organization": 0.4, "automated": 0.15}.get(a.kind, 0.04)
    if a.net:
        g = 0.9 if a.handle in ("CoastTruthTX", "GulfWatchPatriot", SS.LEAD_A, SS.LEAD_B) else 0.5
    surge = g / (1.0 + math.exp(-(d - 3) / 4.0))
    drift = 0.0006 * (d + 60)
    return max(1, int(a.followers * (1.0 + surge + drift)) + (hi("fj", a.handle, int(d)) % 5) - 2)


def entities(text, A, url):
    ents = {"hashtags": [{"text": m.group(1), "indices": [m.start(), m.end()]} for m in re.finditer(r"#(\w+)", text)],
            "user_mentions": [], "urls": []}
    for m in re.finditer(r"@(\w+)", text):
        b = A.by.get(m.group(1))
        if b:
            ents["user_mentions"].append({"screen_name": b.handle, "id_str": str(b.uid), "indices": [m.start(), m.end()]})
    for m in re.finditer(r"https://t\.co/\w+", text):
        exp = url or m.group(0)
        ents["urls"].append({"url": m.group(0), "expanded_url": exp, "display_url": re.sub(r"^https://", "", exp)[:40], "indices": [m.start(), m.end()]})
    return ents


def main():
    old = sorted(f for f in os.listdir(os.path.join(ROOT, OUT)) if f.endswith("_tweets.jsonl")) if os.path.isdir(os.path.join(ROOT, OUT)) else []
    if old:
        retire([OUT + f for f in old] + [OUT + "_consolidated/tweets.jsonl"])
    G = geo_handle()
    A = Accounts(G)
    S = Stream(A)
    run_official(S)
    run_news(S)
    run_automated(S)
    made = run_network(S)
    run_residents(S)
    run_injections(S)
    industry = {"RendalTerminals", "LagunaTowing", "GulfReliefLogistics"}
    run_phased(S, [a for a in A.personas if a.kind == "business" and a.handle.lstrip("@") not in industry], ST.BUSINESS, 0.8)
    run_phased(S, [a for a in A.personas if a.kind == "business" and a.handle.lstrip("@") in industry], ST.INDUSTRY, 0.3)
    run_phased(S, [a for a in A.personas if a.kind == "organization" and a.style.startswith(("needs", "first-hand", "advocacy"))], ST.GROUPS, 0.7)
    need = run_blame_fill(S)
    # direct retweets (amplifiers) and pooled requests
    direct = [q for q in S.req if q.get("direct") is not None]
    S.req = [q for q in S.req if q.get("direct") is None]
    for q in direct:
        acct, src = A.by[q["a"]], S.tw[q["direct"]]
        srca = A.by[src["a"]]
        if (acct.stop and q["t"] >= acct.stop) or q["t"] >= SPAN_END or (srca.stop and q["t"] >= srca.stop):
            continue
        S.tw.append({"t": q["t"], "a": q["a"], "text": f"RT @{src['a']}: {src['text']}"[:300], "lang": src["lang"], "kind": "rt", "ref": q["direct"],
                     "url": src["url"], "geo": None, "src": acct.source, "topic": q["topic"]})
    S.resolve()

    # retweets of a suspended author's post after the suspension cannot exist
    tw = S.tw
    keep = []
    for i, t in enumerate(tw):
        if t["kind"] != "o":
            sa = A.by[tw[t["ref"]]["a"]]
            if sa.stop and t["t"] >= sa.stop:
                t["drop"] = True
    order = sorted((i for i in range(len(tw)) if not tw[i].get("drop")), key=lambda i: (tw[i]["t"], tw[i]["a"], tw[i]["text"]))
    # ids
    used, ids = set(), {}
    for i in order:
        x = snowflake(tw[i]["t"], (tw[i]["a"], tw[i]["text"]))
        while x in used:
            x += 1
        used.add(x)
        ids[i] = x
    # engagement
    rts, favs, reps = defaultdict(int), defaultdict(int), defaultdict(int)
    for i in order:
        t = tw[i]
        if t["kind"] == "rt" and t["ref"] in ids:
            rts[t["ref"]] += 1
        elif t["kind"] == "re" and t["ref"] in ids:
            reps[t["ref"]] += 1
    n_status = defaultdict(int)
    files = defaultdict(list)
    geo_rows, lookup_seen = [], {}
    for i in order:
        t = tw[i]
        if t["kind"] != "o" and t["ref"] not in ids:
            continue
        a = A.by[t["a"]]
        n_status[a.handle] += 1
        fol = followers_at(a, t["t"])
        r = rng("eng", ids[i])
        heat = 3.0 if t["topic"] in ("seize", "wealthy", "refinery", "phase2", "phase3", "official", "story") else 1.0
        base_rt = (fol ** 0.62) * 0.012 * heat
        rc = rts[i] + int(r.poisson(base_rt)) if t["kind"] != "rt" else 0
        fc = int(r.poisson(base_rt * 2.6 + reps[i] * 0.5)) if t["kind"] != "rt" else 0
        user = {"id": a.uid, "id_str": str(a.uid), "name": a.name, "screen_name": a.handle, "location": a.loc, "description": a.bio,
                "verified": a.verified, "followers_count": fol, "friends_count": a.friends + (hi("frd", a.handle, t["t"] // (7 * DAY)) % 7),
                "statuses_count": a.statuses0 + n_status[a.handle], "created_at": tw_time(a.created)}
        obj = {"created_at": tw_time(t["t"]), "id": ids[i], "id_str": str(ids[i]), "full_text": t["text"], "truncated": False,
               "entities": entities(t["text"], A, t["url"]), "source": t["src"], "in_reply_to_status_id_str": None, "in_reply_to_user_id_str": None,
               "in_reply_to_screen_name": None, "user": user, "coordinates": None, "place": None, "is_quote_status": False,
               "retweet_count": rc, "favorite_count": fc, "lang": t["lang"]}
        if t["kind"] == "re":
            ra_ = A.by[tw[t["ref"]]["a"]]
            obj["in_reply_to_status_id_str"], obj["in_reply_to_user_id_str"], obj["in_reply_to_screen_name"] = str(ids[t["ref"]]), str(ra_.uid), ra_.handle
        elif t["kind"] == "q":
            ra_ = A.by[tw[t["ref"]]["a"]]
            obj["is_quote_status"], obj["quoted_status_id_str"] = True, str(ids[t["ref"]])
            link = f"https://twitter.com/{ra_.handle}/status/{ids[t['ref']]}"
            obj["full_text"] = t["text"] + " " + tco(link)
            obj["entities"] = entities(obj["full_text"], A, link)
            obj["quoted_status_permalink"] = {"url": tco(link), "expanded": link}
        elif t["kind"] == "rt":
            ra_ = A.by[tw[t["ref"]]["a"]]
            obj["retweeted_status"] = {"id_str": str(ids[t["ref"]]), "created_at": tw_time(tw[t["ref"]]["t"]),
                                       "user": {"id_str": str(ra_.uid), "screen_name": ra_.handle}}
            obj["retweet_count"] = rts[t["ref"]] + int(r.poisson(0.5))
        if t["geo"]:
            obj["coordinates"] = {"type": "Point", "coordinates": [t["geo"][1], t["geo"][0]]}
            city = a.home if a.home in ("Port Aransas", "Portland", "Rockport", "Aransas Pass", "Ingleside", "Robstown", "Fulton", "Gregory") else "Corpus Christi"
            obj["place"] = {"place_type": "city", "name": city, "full_name": f"{city}, TX", "country_code": "US"}
            geo_rows.append([str(ids[i]), a.handle, iso(t["t"]), t["geo"][0], t["geo"][1]])
        key = a.handle if not a.compact else "community_" + dt.datetime.fromtimestamp(t["t"], dt.timezone.utc).strftime("%Y-%m")
        files[key].append(obj)
        lookup_seen[a.handle] = user

    # SOCIAL_STAGE_DIR lets a slow network drive be filled in two steps: generate to local disk, then copy
    d = os.environ.get("SOCIAL_STAGE_DIR") or os.path.join(ROOT, OUT)
    os.makedirs(d, exist_ok=True)
    keep_names = {k + ".jsonl" for k in files} | {"_account_lookup.jsonl", "_platform_records_return.jsonl"}
    for f in os.listdir(d):                      # files of accounts that no longer post must not linger
        if f.endswith(".jsonl") and f not in keep_names:
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                open(os.path.join(d, f), "w").close()
    total = 0
    for key in sorted(files):
        with open(os.path.join(d, key + ".jsonl"), "w", encoding="utf-8") as fh:
            for o in files[key]:
                fh.write(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n")
                total += 1
    # account lookup at the end of the collection
    with open(os.path.join(d, "_account_lookup.jsonl"), "w", encoding="utf-8") as fh:
        for hd in sorted(A.by):
            a = A.by[hd]
            if a.stop:
                fh.write(json.dumps({"screen_name": hd, "lookup_utc": iso(SPAN_END - 3600), "errors": [{"code": 63, "message": "User has been suspended."}],
                                     "suspended": True}, ensure_ascii=False) + "\n")
            else:
                u = lookup_seen.get(hd) or {"id": a.uid, "id_str": str(a.uid), "name": a.name, "screen_name": a.handle, "location": a.loc,
                                            "description": a.bio, "verified": a.verified, "followers_count": followers_at(a, SPAN_END),
                                            "friends_count": a.friends, "statuses_count": a.statuses0, "created_at": tw_time(a.created)}
                u = dict(u)
                u.update({"lookup_utc": iso(SPAN_END - 3600), "suspended": False})
                fh.write(json.dumps(u, ensure_ascii=False) + "\n")
    # account access records returned on D+30 under the referral
    T = A.truth["personas"]
    ret = int(dt.datetime(2027, 10, 14, 16, 0, tzinfo=dt.timezone.utc).timestamp())
    with open(os.path.join(d, "_platform_records_return.jsonl"), "w", encoding="utf-8") as fh:
        for hd, ips in ((SS.LEAD_A, ["198.51.47.112", "198.51.47.118", "198.51.47.203"]), (SS.LEAD_B, ["198.51.48.44", "198.51.48.91"])):
            a = A.by[hd]
            r = rng("iplog", hd)
            mine = [tw[i]["t"] for i in order if tw[i]["a"] == hd and dts(-5) <= tw[i]["t"] < dts(23)]
            for t in mine:
                fh.write(json.dumps({"record_type": "account_access", "referral": "FB-2027-TXCYB-1148", "returned_utc": iso(ret), "screen_name": hd,
                                     "user_id_str": str(a.uid), "event_utc": iso(t - int(r.integers(5, 90))), "event": "post_create",
                                     "source_ip": ips[int(r.integers(len(ips)))], "asn": 198765, "asn_name": "Meridian Transit Hosting", "asn_country": "NL",
                                     "client": "web"}) + "\n")
    with open(os.path.join(d, "_geotagged_index.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id_str", "screen_name", "created_utc", "latitude", "longitude"])
        w.writerows(geo_rows)
    # internal notes for the answer key
    notes = {"_about": "Internal. Never delivered. How the social stream carries the two networks.",
             "second_wave_accounts": ["@" + a.handle for a in A.sleepers],
             "second_wave_note": "The scenario says the second wave (D+75 to D+85) comes from 'the same 40 accounts', but all 40 were removed on D+38. "
                                 "The stream carries the second wave on 40 other operator accounts that were never removed: same slot rhythm, same text reuse, "
                                 "same scheduling client and the same lure domain. They are ordinary rows in accounts_compact.",
             "suspended": {a.handle: iso(a.stop) for a in A.by.values() if a.stop and (a.net)},
             "amplifiers_suspended_utc": iso(dts(38 + 11 / 24)),
             "drone_nights_local": DRONE_NIGHTS,
             "blame_hashtags": ST.BLAME_TAGS,
             "rumour_posts_made": made}
    with open(os.path.join(ROOT, "06_data_streams/_internal/social_stream_notes.json"), "w", encoding="utf-8") as fh:
        json.dump(notes, fh, indent=1, ensure_ascii=False)
    size = sum(os.path.getsize(os.path.join(d, f)) for f in os.listdir(d) if f.endswith(".jsonl"))
    print(f"social_media: {total:,} posts in {len(files)} files, {size / 1e6:.1f} MB; geo-tagged {len(geo_rows)}; rumour posts {made:,}; blame fill {need:,}")


if __name__ == "__main__":
    main()
