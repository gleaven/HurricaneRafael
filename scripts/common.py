"""Shared loaders for the Hurricane Rafael scenario project."""
import json, os, re, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def path(*p):
    return os.path.join(ROOT, *p)

def load(rel):
    with open(path(rel), encoding="utf-8") as f:
        return json.load(f)

def save(rel, obj):
    full = path(rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def story_id(day, seq):
    return f"NWS-{'M' if day < 0 else 'P'}{abs(day):03d}-{seq:02d}"

STORY_ID_RE = re.compile(r"^NWS-([MP])(\d{3})-(\d{2})$")

def day_from_story_id(sid):
    m = STORY_ID_RE.match(sid or "")
    if not m:
        return None
    d = int(m.group(2))
    return -d if m.group(1) == "M" else d

def load_all_stories():
    stories = []
    for f in sorted(glob.glob(path("03_news", "stories", "batch-*.json"))):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        for s in data.get("stories", []):
            s.setdefault("internal", {})["source_file"] = os.path.basename(f)
            stories.append(s)
    stories.sort(key=lambda s: (s.get("day", 0), s.get("time_local", "00:00"), s.get("story_id", "")))
    return stories

def context():
    ctx = {
        "config": load("00_scenario/config.json"),
        "places": {p["place_id"]: p for p in load("00_scenario/places.json")},
        "entities": {e["id"]: e for e in load("00_scenario/entities.json")},
        "msel": {e["event_id"]: e for e in load("00_scenario/msel.json")},
        "characters": {c["id"]: c for c in load("01_characters/characters.json")["characters"]},
        "outlets": {o["outlet_id"]: o for o in load("01_characters/outlets.json")["outlets"]},
        "facts": {f["id"]: f for f in load("02_public_record/public_record.json")["facts"]},
        "terms": load("02_public_record/restricted_terms.json")["terms"],
        "pairs": load("02_public_record/restricted_terms.json").get("pairs", []),
        "allow": load("07_validation/allowlist.json")["entries"],
        "arcs": {a["arc_id"]: a for a in load("03_news/arcs.json")["arcs"]},
        "coverage": load("03_news/coverage_targets.json")["ranges"],
    }
    return ctx


# --- multi-scenario support (added for the gridwater layer) ---------------
# Backward compatible: all functions above keep operating on the Rafael base
# world (root "."). The helpers below resolve paths inside a named scenario.
def load_registry():
    try:
        return load("scenarios/registry.json")["scenarios"]
    except FileNotFoundError:
        return [{"id": "rafael", "root": ".", "id_prefix": ""}]

def scenario(sid="rafael"):
    for s in load_registry():
        if s["id"] == sid:
            return s
    raise KeyError("unknown scenario: " + sid)

def sroot(sid="rafael"):
    r = scenario(sid).get("root", ".")
    return ROOT if r in (".", "") else os.path.join(ROOT, r)

def spath(sid, *p):
    return os.path.join(sroot(sid), *p)

def sload(sid, rel):
    with open(spath(sid, rel), encoding="utf-8") as f:
        return json.load(f)

def public_exclusions():
    """Union of public_exclusions over all registered scenarios."""
    places, phrases = set(), set()
    for s in load_registry():
        try:
            ex = sload(s["id"], s.get("config_file", "00_scenario/config.json")).get("public_exclusions", {})
        except FileNotFoundError:
            continue
        places |= set(ex.get("places", [])); phrases |= set(ex.get("leak_phrases", []))
    return places, phrases

def all_threads():
    """{thread_id: {name, color, scenario}} across every registered scenario."""
    out = {}
    for s in load_registry():
        try:
            rows = sload(s["id"], s.get("threads_file", "00_scenario/threads.json"))
        except FileNotFoundError:
            rows = []
        for t in rows:
            out[t["thread_id"]] = {"name": t["name"], "color": s.get("thread_colors", {}).get(t["thread_id"], "#7a8a99"), "scenario": s["id"]}
    return out

def ssave(sid, rel, obj):
    full = spath(sid, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
