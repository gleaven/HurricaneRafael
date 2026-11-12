"""Compile the newsroom's data from the scenario's public release.

Reads (paths relative to the "News Stories" folder):
  08_release/news_stories_public.json     public article text and metadata
  03_news/story_index.json                related-story and storyline links
  03_news/arcs.json                       storyline names
  02_public_record/restricted_terms.json  leak guard (a term may appear only on or after a day)

Writes newsroom/data/: articles.json, outlets.json, milestones.json, status.json

server.py runs this automatically at startup when the sources are present. If the newsroom
folder is copied somewhere without the rest of the corpus, the server uses the cached files.

Usage: python build_data.py
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(HERE, "data")
D0 = dt.date(2027, 9, 14)  # landfall day (local)

# --------------------------------------------------------------------------------------
# Outlets. Section maps fold the corpus's ad-hoc section names into each outlet's own nav.
# --------------------------------------------------------------------------------------
OUTLETS = [
    {"id": "OUT-01", "slug": "ledger", "name": "The Bayside Ledger", "kind": "Local daily newspaper",
     "site": "bayside-ledger.example", "lang": "en",
     "sections": ["Local", "Weather", "Business", "Health", "Military", "Investigations", "Opinion"],
     "section_map": {"News": "Local"}},
    {"id": "OUT-02", "slug": "harborline6", "name": "Harborline 6 News", "kind": "Local TV station",
     "site": "harborline6.example", "lang": "en",
     "sections": ["Breaking", "Local", "Weather", "Traffic"],
     "section_map": {"Breaking News": "Breaking", "Special Report": "Breaking"}},
    {"id": "OUT-03", "slug": "coastline", "name": "Coastline Public Radio", "kind": "Regional public radio",
     "site": "coastline-radio.example", "lang": "en",
     "sections": ["Environment", "Equity", "Health", "Military & Community", "Investigations"],
     "section_map": {"Weather": "Environment", "Community": "Equity", "Features": "Equity", "News": "Equity"},
     "headline_rules": [["hospital", "Health"]]},
    {"id": "OUT-04", "slug": "gulfwater", "name": "Gulfwater Maritime Report", "kind": "Maritime trade publication",
     "site": "gulfwater-maritime.example", "lang": "en",
     "sections": ["Ports", "Tankers", "Security", "Regulation"],
     "section_map": {"Marine Law": "Regulation", "Maritime": "Ports", "Port Operations": "Ports",
                     "Marine Pollution": "Tankers", "Maritime Security": "Security"}},
    {"id": "OUT-05", "slug": "sabal", "name": "Sabal Energy Wire", "kind": "Energy and markets wire",
     "site": "sabal-energy.example", "lang": "en",
     "sections": ["Crude", "Refining", "Power & Utilities", "Markets", "Policy"],
     "section_map": {"Utilities": "Power & Utilities", "Energy": "Power & Utilities",
                     "Environment": "Power & Utilities", "Analysis": "Power & Utilities", "Regulatory": "Policy"}},
    {"id": "OUT-06", "slug": "continental", "name": "Continental Wire Service", "kind": "National news wire",
     "site": "continental-wire.example", "lang": "en",
     "sections": ["National", "Security", "World"],
     "section_map": {"Business": "National"}},
    {"id": "OUT-07", "slug": "anchor-rotor", "name": "Anchor & Rotor Weekly", "kind": "Military community weekly",
     "site": "anchor-rotor.example", "lang": "en",
     "sections": ["Base News", "Readiness", "Families"],
     "section_map": {"Military and Aviation": "Base News", "Aviation": "Base News", "Security": "Readiness"}},
    {"id": "OUT-08", "slug": "kncb", "name": "KNCB Coastal Bend Radio", "kind": "Spanish-language AM radio (1480 AM)",
     "site": "kncb1480.example", "lang": "es",
     "sections": ["Emergencias", "Local", "Comunidad", "Salud"],
     "section_map": {"Noticias / News": "Emergencias", "Emergencies": "Emergencias", "News": "Local",
                     "Noticias": "Local", "Community": "Comunidad", "Health": "Salud"}},
]

# --------------------------------------------------------------------------------------
# Game-master milestones (control page only). (label, scenario day, local HH:MM)
# Times come from the public record where it gives one; otherwise 05:45, before the
# morning news cycle, so the GM lands just ahead of the day's coverage.
# --------------------------------------------------------------------------------------
MILESTONES = [
    ("Scenario start: summer on the Coastal Bend", -60, "05:45"),
    ("Forecast cone shifts toward Corpus Christi", -5, "05:45"),
    ("Hurricane watch; Port Condition X-Ray", -3, "05:45"),
    ("Zone A evacuation ordered", -2, "05:45"),
    ("Hurricane warning issued", -2, "11:45"),
    ("Evacuation extended to Zones B and C", -1, "06:45"),
    ("Shelter-in-place alert", 0, "00:40"),
    ("Landfall near Port Aransas", 0, "00:55"),
    ("First post-storm broadcast", 1, "08:45"),
    ("Oil spreads into the bays", 2, "05:45"),
    ("Citywide boil-water notice", 4, "06:45"),
    ("Coast Guard: possible remote access to tankers", 6, "05:45"),
    ("Boil-water notice, Districts 3 and 4 (English)", 12, "17:15"),
    ("Spanish boil-water notice reaches KNCB listeners", 13, "05:50"),
    ("FBI and CISA confirm utility cyber investigation", 21, "05:45"),
    ("Ship channel partly reopens", 30, "05:45"),
    ("AIS identity anomaly reported", 38, "05:45"),
    ("Citywide boil-water notice lifted", 39, "08:45"),
    ("Districts 3 and 4 boil-water notice lifted", 42, "10:45"),
    ("Explosion beside harbor tug near the jetties", 44, "00:45"),
    ("Navy: explosive device caused the blast", 46, "05:45"),
    ("Second device found and rendered safe", 52, "05:45"),
    ("Ship channel reopens after sweep", 58, "05:45"),
    ("FBI searches two storm contractors", 104, "05:45"),
    ("Coast Guard and CISA maritime cyber advisory", 105, "05:45"),
    ("U.S. attributes attacks to a foreign government", 112, "05:45"),
    ("Forfeiture filing names contractors' owner", 114, "05:45"),
    ("Four months after landfall", 119, "05:45"),
]

# --------------------------------------------------------------------------------------
# Public status layers shown in outlet widgets. All drawn from the public record.
# Times are local (day, "HH:MM") and follow 00_scenario/canon_decisions.md and
# 00_scenario/canon_timeline.json. Alerts carry separate English and Spanish start times:
# the Districts 3 and 4 boil-water notice went out in English at 17:30 on D+12 and
# reached Spanish-language listeners at 06:03 on D+13 (PUB-143, PUB-144); it was lifted at
# 11:00 on D+42 (PUB-206). The sites reproduce that gap.
# --------------------------------------------------------------------------------------
PORT_CONDITIONS = [
    (-60, "00:00", "OPEN", "Open", "Normal operations. All terminals working."),
    (-3, "08:00", "X-RAY", "Port Condition X-Ray",
     "Gale-force winds possible within 48 hours. Ocean-going vessels must plan departure or request approval to stay."),
    (-2, "08:00", "YANKEE", "Port Condition Yankee",
     "Port closed to inbound traffic. Ocean-going vessels departing; inbound ships holding at the offshore anchorage."),
    (-1, "12:00", "ZULU", "Port Condition Zulu",
     "Ship channel closed to all traffic. Vessels at the anchorage putting to sea."),
    (0, "01:00", "CLOSED", "Closed",
     "Channel closed after Hurricane Rafael. Damage surveys and oil spill response under way."),
    (30, "08:00", "RESTRICTED", "Partially open",
     "Channel partly reopened. Inner channel restricted for spill decontamination; anchorage backlog."),
    (44, "01:00", "CLOSED", "Closed",
     "Channel closed after an explosion near the Port Aransas jetties. Security sweep under way."),
    (58, "08:00", "OPEN", "Open", "Channel open to all traffic after a full sweep. Exports resuming."),
]

ALERTS = [
    {"id": "hurricane-watch", "level": "watch", "start_en": (-3, "10:00"), "start_es": (-3, "10:05"), "end": (-2, "12:00"),
     "en": "Hurricane watch in effect for the Coastal Bend. Rafael could approach the coast within 48 hours.",
     "es": "Aviso de huracán en efecto para el Coastal Bend. Rafael podría acercarse a la costa en 48 horas."},
    {"id": "hurricane-warning", "level": "warning", "start_en": (-2, "12:00"), "start_es": (-2, "12:08"), "end": (0, "12:00"),
     "en": "Hurricane warning: Rafael expected to make landfall near Port Aransas. Finish preparations now.",
     "es": "Advertencia de huracán: se espera que Rafael toque tierra cerca de Port Aransas. Termine sus preparativos ahora."},
    {"id": "evacuation-zone-a", "level": "emergency", "start_en": (-2, "06:00"), "start_es": (-2, "08:47"), "end": (-1, "07:00"),
     "en": "Mandatory evacuation ordered for Zone A: the barrier islands and low-lying surge areas. Shelters are open inland.",
     "es": "Evacuación obligatoria para la Zona A: las islas de barrera y las áreas bajas de marejada. Los albergues están abiertos tierra adentro."},
    {"id": "evacuation", "level": "emergency", "start_en": (-1, "07:00"), "start_es": (-1, "07:15"), "end": (0, "00:45"),
     "en": "Mandatory evacuation extended to Zones B and C; Zones A, B and C must leave. Shelters are open inland.",
     "es": "Evacuación obligatoria para las zonas de marejada A, B y C. Los albergues están abiertos tierra adentro."},
    {"id": "shelter-in-place", "level": "emergency", "start_en": (0, "00:45"), "start_es": (0, "00:50"), "end": (0, "09:00"),
     "en": "Shelter in place. Hurricane Rafael is making landfall. Do not go outside.",
     "es": "Refúgiese donde está. El huracán Rafael está tocando tierra. No salga."},
    {"id": "boil-citywide", "level": "advisory", "start_en": (4, "07:00"), "start_es": (4, "07:15"), "end": (39, "09:00"),
     "en": "Citywide boil-water notice: bring water to a rolling boil for two minutes before drinking or cooking.",
     "es": "Aviso de hervir agua en toda la ciudad: hierva el agua durante dos minutos antes de beberla o cocinar."},
    {"id": "boil-d3-d4", "level": "advisory", "start_en": (12, "17:30"), "start_es": (13, "06:03"), "end": (42, "11:00"),
     "en": "Boil-water notice for Districts 3 and 4. Do not drink tap water without boiling it first.",
     "es": "Aviso de hervir agua para los Distritos 3 y 4. No beba agua de la llave sin hervirla primero."},
    {"id": "fishing-closure", "level": "advisory", "start_en": (4, "12:00"), "start_es": (4, "12:00"), "end": (115, "12:00"),
     "en": "Fishing and shellfish harvesting closed in Nueces and Corpus Christi bays because of the oil spill.",
     "es": "Pesca y recolección de mariscos cerradas en las bahías de Nueces y Corpus Christi por el derrame de petróleo."},
]

BROADCAST = {
    "harborline6": [
        (0, "01:00", 1, "08:52", "off-air", "Transmitter off the air. Web updates continue."),
    ],
    "coastline": [
        (0, "00:00", 0, "09:00", "generator", "On the air on generator power."),
    ],
    "kncb": [
        (0, "03:31", 1, "02:00", "off-air", "Transmisor fuera del aire. Las noticias en la web continúan."),
    ],
}


# --------------------------------------------------------------------------------------
def us_central_offset(utc):
    """UTC offset in hours for US Central at a UTC datetime (CDT -5 / CST -6)."""
    y = utc.year

    def nth_sunday(month, n):
        d = dt.datetime(y, month, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)

    start = nth_sunday(3, 2) + dt.timedelta(hours=8)   # 2:00 CST = 08:00 UTC
    end = nth_sunday(11, 1) + dt.timedelta(hours=7)    # 2:00 CDT = 07:00 UTC
    naive = utc.replace(tzinfo=None)
    return -5 if start <= naive < end else -6


def local_to_epoch(day, hhmm):
    d = D0 + dt.timedelta(days=day)
    h, m = map(int, hhmm.split(":"))
    naive = dt.datetime(d.year, d.month, d.day, h, m)
    # find the offset that applies at that local wall time (good enough outside the DST hour)
    off = us_central_offset(naive - dt.timedelta(hours=-6))
    return int((naive - dt.timedelta(hours=off)).replace(tzinfo=dt.timezone.utc).timestamp())


def slugify(text, n=70):
    t = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:n].strip("-")


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def sources_present():
    return os.path.exists(os.path.join(ROOT, "08_release", "news_stories_public.json"))


def build(verbose=True):
    rel = load("08_release/news_stories_public.json")["stories"]
    try:
        idx = load("03_news/story_index.json").get("stories", {})
    except FileNotFoundError:
        idx = {}
    try:
        terms = load("02_public_record/restricted_terms.json")["terms"]
    except FileNotFoundError:
        terms = []

    by_name = {o["name"]: o for o in OUTLETS}
    arts, blocked, unmapped = [], [], set()
    used_paths = set()
    for s in rel:
        o = by_name.get(s["outlet"])
        if not o:
            unmapped.add(("outlet", s["outlet"]))
            continue
        pub = dt.datetime.fromisoformat(s["published"])
        ts = int(pub.timestamp())
        day = (pub.date() - D0).days

        # leak guard on everything a reader can see
        text = " ".join([s["headline"], s.get("summary", "")] + s["body"] + s.get("topics", [])
                        + s.get("people", []) + s.get("places", []))
        bad = [t["pattern"] for t in terms
               if re.search(t["pattern"], text, re.I) and (t["public_from_day"] is None or day < t["public_from_day"])]
        if bad:
            blocked.append((s["id"], bad))
            continue

        sec = o.get("section_map", {}).get(s["section"], s["section"])
        for kw, target in o.get("headline_rules", []):
            if kw in s["headline"].lower():
                sec = target
        if sec not in o["sections"]:
            unmapped.add((o["slug"], s["section"]))
            sec = o["sections"][0]

        base = f"/{o['slug']}/{pub.strftime('%Y/%m/%d')}/{slugify(s['headline'])}"
        path, n = base, 2
        while path in used_paths:
            path, n = f"{base}-{n}", n + 1
        used_paths.add(path)

        ix = idx.get(s["id"], {})
        related = [r["story_id"] for r in ix.get("related", [])][:6]
        arc_links = sorted(set(list(ix.get("prev_in_arc", {}).values()) + list(ix.get("next_in_arc", {}).values())))

        arts.append({
            "id": s["id"], "outlet": o["slug"], "ts": ts, "published": s["published"], "day": day,
            "section": sec, "section_slug": slugify(sec), "section_raw": s["section"],
            "authors": s.get("authors", []), "headline": s["headline"], "summary": s.get("summary", ""),
            "body": s["body"], "story_type": s.get("story_type") or "update",
            "storylines": s.get("storylines", []), "people": s.get("people", []), "places": s.get("places", []),
            "topics": s.get("topics", []), "url": path, "follows_up": ix.get("follows_up"),
            "related": related, "arc_links": arc_links,
            "words": sum(len(p.split()) for p in s["body"]),
        })

    arts.sort(key=lambda a: (a["ts"], a["id"]))
    ids = {a["id"] for a in arts}
    for a in arts:  # drop links to blocked/missing stories
        a["related"] = [r for r in a["related"] if r in ids and r != a["id"]]
        a["arc_links"] = [r for r in a["arc_links"] if r in ids and r != a["id"]]
        if a["follows_up"] not in ids:
            a["follows_up"] = None

    outlets = []
    for o in OUTLETS:
        mine = [a for a in arts if a["outlet"] == o["slug"]]
        secs = [{"name": n, "slug": slugify(n), "count": sum(1 for a in mine if a["section"] == n)}
                for n in o["sections"]]
        entry = {k: v for k, v in o.items() if k not in ("section_map", "headline_rules")}
        entry.update({"sections": [x for x in secs if x["count"]], "count": len(mine),
                      "authors": sorted({n for a in mine for n in a["authors"]})})
        outlets.append(entry)

    milestones = [{"label": lab, "day": d, "local": hm, "ts": local_to_epoch(d, hm)} for lab, d, hm in MILESTONES]

    status = {
        "port": [{"ts": local_to_epoch(d, hm), "code": c, "label": lab, "detail": det}
                 for d, hm, c, lab, det in PORT_CONDITIONS],
        "alerts": [{"id": a["id"], "level": a["level"], "en": a["en"], "es": a["es"],
                    "start_en": local_to_epoch(*a["start_en"]), "start_es": local_to_epoch(*a["start_es"]),
                    "end": local_to_epoch(*a["end"])} for a in ALERTS],
        "broadcast": {k: [{"start": local_to_epoch(d1, h1), "end": local_to_epoch(d2, h2), "status": st, "note": note}
                          for d1, h1, d2, h2, st, note in v] for k, v in BROADCAST.items()},
    }

    meta = {"built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "first_ts": arts[0]["ts"], "last_ts": arts[-1]["ts"], "count": len(arts),
            "d0_local_date": D0.isoformat(), "blocked": blocked}

    os.makedirs(DATA, exist_ok=True)
    for name, obj in (("articles", {"meta": meta, "articles": arts}), ("outlets", outlets),
                      ("milestones", milestones), ("status", status)):
        with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1 if name != "articles" else None)

    if verbose:
        print(f"newsroom data: {len(arts)} articles, {len(blocked)} blocked by leak guard")
        for o in outlets:
            print(f"  {o['slug']:<13} {o['count']:>4}  " + ", ".join(f"{s['name']} {s['count']}" for s in o["sections"]))
        for b in blocked:
            print("  BLOCKED", b)
        for u in sorted(unmapped):
            print("  UNMAPPED", u)
    return meta


if __name__ == "__main__":
    if not sources_present():
        sys.exit("08_release/news_stories_public.json not found; run from inside the News Stories folder tree.")
    build()
