"""Validate news story batches against the scenario rules.

Usage:
  python scripts/validate.py                    # all batches + coverage
  python scripts/validate.py 03_news/stories/batch-C.json   # one batch (no coverage check)
Writes 07_validation/reports/validation_report.json when run on all batches.
Exit code 1 if any errors.
"""
import sys, re, json, glob, os
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, path, day_from_story_id, save

ALLOWED_PLACEHOLDERS = {"FAC-HOS-xx", "WW-xx"}
import re as _re
def outlet_range(style):
    m = _re.search(r"(\d{3})\s*-\s*(\d{3})\s*words", style)
    return (int(m.group(1)), int(m.group(2))) if m else None
OUTLET_RANGE = True
TYPES = {"breaking", "update", "feature", "explainer", "profile", "analysis", "fact-check", "brief", "opinion"}

def words(body):
    return sum(len(p.split()) for p in body)

def check_story(s, ctx, errors, warnings, batch_range=None):
    sid = s.get("story_id", "?")
    def err(m): errors.append(f"{sid}: {m}")
    def warn(m): warnings.append(f"{sid}: {m}")
    for k in ["story_id", "day", "time_local", "outlet_id", "section", "byline", "headline", "dek", "body", "tags", "internal"]:
        if k not in s:
            err(f"missing field {k}")
    if errors and errors[-1].startswith(f"{sid}: missing"):
        return
    day = s["day"]
    if day_from_story_id(sid) != day:
        err(f"story_id does not match day {day}")
    lo, hi = ctx["config"]["day_range"]
    if not (lo <= day <= hi):
        err(f"day {day} outside scenario range")
    if batch_range and not (batch_range[0] <= day <= batch_range[1]):
        err(f"day {day} outside batch range {batch_range}")
    if not re.match(r"^\d{2}:\d{2}$", str(s["time_local"])):
        err("time_local must be HH:MM")
    o = ctx["outlets"].get(s["outlet_id"])
    if not o:
        err(f"unknown outlet {s['outlet_id']}")
    else:
        if s["section"] not in o["sections"]:
            warn(f"section '{s['section']}' not in {o['name']} sections")
        for b in s["byline"]:
            if b not in o["staff"]:
                err(f"byline {b} is not on {o['name']} staff")
    if not isinstance(s["body"], list) or len(s["body"]) < 3:
        err("body must be a list of at least 3 paragraphs")
    else:
        w = words(s["body"])
        if w < 220 or w > 500:
            err(f"body is {w} words (target 250-450)")
        elif w < 250 or w > 450:
            warn(f"body is {w} words (target 250-450)")
        if o:
            rng = outlet_range(o["style"])
            if rng and (w < rng[0] - 10 or w > rng[1] + 10):
                warn(f"body is {w} words; {o['name']} style range is {rng[0]}-{rng[1]}")
    t = s["tags"]
    if t.get("story_type") not in TYPES:
        err(f"bad story_type {t.get('story_type')}")
    arcs = t.get("arcs", [])
    if not (1 <= len(arcs) <= 4):
        err("needs 1-4 arcs")
    for a in arcs:
        if a not in ctx["arcs"]:
            err(f"unknown arc {a}")
    pubs = t.get("public_facts", [])
    if not pubs:
        err("no public_facts cited")
    for p in pubs:
        f = ctx["facts"].get(p)
        if not f:
            err(f"unknown public fact {p}")
        elif f["day"] > day:
            err(f"cites {p} (public from day {f['day']}) before it is public")
    text = " ".join([s["headline"], s["dek"]] + list(s["body"]))
    for c in t.get("characters_quoted", []) + t.get("characters_mentioned", []):
        ch = ctx["characters"].get(c)
        if not ch:
            err(f"unknown character {c}")
            continue
        if not ch["public_facing"]:
            err(f"non-public character {c} used")
        name = ch["name"]
        key = name.split()[-1] if not name.startswith("@") and not name.startswith("A ") else name
        if name.startswith("A foreign"):
            key = "foreign state broadcaster"
        if key.lower() not in text.lower():
            warn(f"{c} ({name}) tagged but '{key}' not found in text")
    for p in t.get("places", []):
        if p not in ctx["places"] and p not in ALLOWED_PLACEHOLDERS:
            err(f"unknown place {p}")
    for term in ctx["terms"]:
        if re.search(term["pattern"], text, flags=re.I):
            fd = term["public_from_day"]
            if fd is None or day < fd:
                err(f"restricted term /{term['pattern']}/ ({term['why']})")
    for pr in ctx.get("pairs", []):
        if (pr["until_day"] is None or day < pr["until_day"]) and re.search(pr["a"], text, re.I) and re.search(pr["b"], text, re.I):
            if not any(e["check"] == "pair" and e["story_id"] == sid and e["match"] == pr["a"] for e in ctx.get("allow", [])):
                err(f"co-mention /{pr['a']}/ + /{pr['b']}/ ({pr['why']})")
    return

def coverage(stories, ctx, errors, warnings):
    per_day = Counter(s["day"] for s in stories)
    for r in ctx["coverage"]:
        for d in range(r["start_day"], r["end_day"] + 1):
            n = per_day.get(d, 0)
            if n == 0:
                errors.append(f"day {d}: no stories")
            elif n < r["min"] or n > r["max"]:
                warnings.append(f"day {d}: {n} stories (target {r['min']}-{r['max']})")
    return per_day

def main(argv):
    ctx = context()
    files = argv or sorted(glob.glob(path("03_news", "stories", "batch-*.json")))
    full_run = not argv
    errors, warnings, stories = [], [], []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        br = data.get("day_range")
        for s in data.get("stories", []):
            check_story(s, ctx, errors, warnings, br)
            stories.append(s)
    ids = Counter(s.get("story_id") for s in stories)
    for k, v in ids.items():
        if v > 1:
            errors.append(f"{k}: duplicate story_id ({v}x)")
    known = set(ids)
    for s in stories:
        fu = s.get("tags", {}).get("follows_up")
        if fu and fu not in known:
            warnings.append(f"{s['story_id']}: follows_up {fu} not found")
    per_day = coverage(stories, ctx, errors, warnings) if full_run else Counter(s["day"] for s in stories)
    summary = {"files": [os.path.basename(f) for f in files], "stories": len(stories),
               "words": sum(words(s.get("body", [])) for s in stories),
               "errors": len(errors), "warnings": len(warnings)}
    print(json.dumps(summary, indent=2))
    for e in errors[:200]:
        print("ERROR", e)
    for w in warnings[:80]:
        print("WARN ", w)
    if full_run:
        save("07_validation/reports/validation_report.json",
             {"summary": summary, "errors": errors, "warnings": warnings,
              "stories_per_day": {str(k): v for k, v in sorted(per_day.items())}})
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
