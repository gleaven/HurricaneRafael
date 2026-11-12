"""Apply fix proposals: exact-text swaps (field headline/dek/body), whole-story replacements (field 'story' with
'replacement' = full story object, same id and day) and new stories (field 'new_story' with 'replacement').
Original doc: apply exact-text fix proposals from findings files (status 'proposed').
A fix applies only if 'old' occurs exactly once in the field (body: across all paragraphs).
Takes a snapshot first.  Usage: python scripts/apply_fixes.py 07_validation/findings/<file>.json [...]"""
import sys, os, glob, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, path

def main(files):
    subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "snapshot.py"), "before applying " + ",".join(os.path.basename(f) for f in files)])
    batches = {}
    for f in sorted(glob.glob(path("03_news", "stories", "batch-*.json"))):
        rel = os.path.relpath(f, path()).replace(os.sep, "/")
        batches[rel] = load(rel)
    where = {s["story_id"]: (rel, s) for rel, b in batches.items() for s in b["stories"]}
    dirty, tally = set(), {}
    for fpath in files:
        rel = os.path.relpath(os.path.abspath(fpath), path()).replace(os.sep, "/")
        fd = load(rel)
        for fx in fd["findings"]:
            if fx.get("status") != "proposed":
                continue
            if fx["field"] == "new_story":
                rep = fx.get("replacement") or {}
                target = None
                for brel, b in batches.items():
                    lo, hi = b.get("day_range", [None, None])
                    if lo is not None and lo <= rep.get("day", 10**6) <= hi:
                        target = brel
                if not target or rep.get("story_id") in where:
                    fx["status"] = "bad_new_story"; continue
                batches[target]["stories"].append(rep)
                batches[target]["stories"].sort(key=lambda x: (x["day"], x["time_local"], x["story_id"]))
                where[rep["story_id"]] = (target, rep); fx["status"] = "applied"; dirty.add(target); continue
            loc = where.get(fx["story_id"])
            if not loc:
                fx["status"] = "story_not_found"; continue
            brel, s = loc; field = fx["field"]
            if field == "story":
                rep = fx.get("replacement")
                if not rep or rep.get("story_id") != fx["story_id"] or rep.get("day") != s["day"]:
                    fx["status"] = "bad_replacement"; continue
                b = batches[brel]["stories"]
                b[b.index(s)] = rep; where[fx["story_id"]] = (brel, rep)
                fx["status"] = "applied"; dirty.add(brel); continue
            if field == "body":
                count = sum(p.count(fx["old"]) for p in s["body"])
            else:
                count = s.get(field, "").count(fx["old"])
            if count != 1:
                fx["status"] = "not_found" if count == 0 else "ambiguous"; continue
            if field == "body":
                s["body"] = [p.replace(fx["old"], fx["new"]) for p in s["body"]]
            else:
                s[field] = s[field].replace(fx["old"], fx["new"])
            fx["status"] = "applied"; dirty.add(brel)
        save(rel, fd)
        for fx in fd["findings"]:
            tally[fx["status"]] = tally.get(fx["status"], 0) + 1
    for brel in dirty:
        save(brel, batches[brel])
    print(f"fix statuses: {tally}; batch files changed: {sorted(dirty)}")

if __name__ == "__main__":
    main(sys.argv[1:])
