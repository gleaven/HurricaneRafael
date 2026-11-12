"""Cross-file integrity checks not covered by the other gates.
Errors: public facts never reported; quotes before a character could know anything; follow-ups pointing forward;
broken RSS/release/graph; wire stories without a dateline.
For review: weak citations (a cited fact shares almost no key words with the story); facts first reported late;
gaps in a day's story numbering.
Usage: python scripts/check_integrity.py -> 07_validation/reports/integrity_report.json; exit 1 on errors"""
import sys, os, re, json, glob
import xml.etree.ElementTree as ET
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, load_all_stories, load, path, save, STORY_ID_RE
from textutil import full_text, allowed

STOP = set("the a an and or of to in on at for by with from as is are was were be been it its this that than then into over after before about near off up down out who what when how their his her they them there here not no yes new two three four five one all any each per via says said say will would could can may".split())

def keywords(statement):
    toks = re.findall(r"[A-Za-z][A-Za-z.'-]+|\d[\d,.]*", statement)
    keys = []
    for t in toks:
        low = t.lower().strip(".")
        if low in STOP or len(low) < 4 and not low[0].isdigit():
            continue
        keys.append(low)
    return list(dict.fromkeys(keys))

def main():
    ctx = context(); stories = load_all_stories(); allow = load("07_validation/allowlist.json")["entries"]
    errors, review = [], []
    by_id = {s["story_id"]: s for s in stories}
    cited = defaultdict(list)
    for s in stories:
        text = full_text(s).lower()
        for p in s["tags"]["public_facts"]:
            cited[p].append(s["day"])
            f = ctx["facts"].get(p)
            if not f:
                continue
            keys = keywords(f["statement"])
            hits = [k for k in keys if k in text]
            if keys and len(hits) / len(keys) < 0.12 and len(hits) < 3 and not allowed(allow, "integrity", s["story_id"], p):
                review.append({"type": "weak_citation", "story_id": s["story_id"], "fact": p, "hits": hits, "keys": keys[:15]})
        for c in s["tags"].get("characters_quoted", []):
            ch = ctx["characters"].get(c)
            if ch and ch["kind"] != "journalist" and ch["knowledge_timeline"]:
                first = min(k["from_day"] for k in ch["knowledge_timeline"])
                if s["day"] < first and not allowed(allow, "integrity", s["story_id"], c):
                    errors.append(f"{s['story_id']}: quotes {c} ({ch['name']}) on day {s['day']}, before their knowledge starts (day {first})")
        fu = s["tags"].get("follows_up")
        if fu:
            o = by_id.get(fu)
            if not o:
                errors.append(f"{s['story_id']}: follows_up {fu} does not exist")
            elif (o["day"], o["time_local"]) >= (s["day"], s["time_local"]):
                errors.append(f"{s['story_id']}: follows_up {fu} is not earlier")
        if s["outlet_id"] in ("OUT-05", "OUT-06") and not re.match(r"^(CORPUS CHRISTI, Texas|WASHINGTON) \((Sabal Energy Wire|Continental Wire)\) — ", s["body"][0]):
            errors.append(f"{s['story_id']}: wire story without standard dateline")
    for pid, f in ctx["facts"].items():
        days = cited.get(pid, [])
        if not days:
            errors.append(f"{pid} (day {f['day']}) is never reported: {f['statement'][:90]}")
        elif min(days) > f["day"] + 3:
            review.append({"type": "late_first_report", "fact": pid, "public_day": f["day"], "first_reported": min(days)})
    seqs = defaultdict(list)
    for s in stories:
        m = STORY_ID_RE.match(s["story_id"]); seqs[s["day"]].append(int(m.group(3)))
    for d, q in seqs.items():
        if sorted(q) != list(range(1, len(q) + 1)):
            review.append({"type": "id_gap", "day": d, "seqs": sorted(q)})
    try:
        items = ET.parse(path("03_news", "rss", "all.xml")).getroot().findall("./channel/item")
        guids = [i.find("guid").text for i in items]
        if len(items) != len(stories): errors.append(f"RSS all.xml has {len(items)} items, expected {len(stories)}")
        if len(set(guids)) != len(guids): errors.append("RSS guids not unique")
        per = sum(len(ET.parse(f).getroot().findall("./channel/item")) for f in glob.glob(path("03_news", "rss", "*.xml")) if not f.endswith("all.xml"))
        if per != len(stories): errors.append(f"per-outlet RSS items {per} != {len(stories)}")
    except ET.ParseError as e:
        errors.append(f"RSS parse error: {e}")
    rel = load("08_release/news_stories_public.json")
    if rel["count"] != len(stories): errors.append(f"release has {rel['count']} stories, expected {len(stories)}")
    if any(k in s for s in rel["stories"] for k in ("internal", "tags", "truth_events")): errors.append("release contains internal fields")
    for view in ("internal", "public"):
        g = load(f"04_knowledge_graph/{view}/graph.json"); ids = {n["id"] for n in g["nodes"]}
        dang = [e for e in g["links"] if e["source"] not in ids or e["target"] not in ids]
        if dang: errors.append(f"{view} graph has {len(dang)} dangling edges")
        if view == "public" and any(n.get("internal") for n in g["nodes"]): errors.append("public graph contains internal nodes")
        if view == "public" and sum(1 for n in g["nodes"] if n["type"] == "Story") != len(stories): errors.append("public graph story count mismatch")
    save("07_validation/reports/integrity_report.json", {"errors": errors, "for_review": review})
    print(f"integrity: {len(errors)} errors, {len(review)} items for review "
          f"({sum(1 for r in review if r['type']=='weak_citation')} weak citations, {sum(1 for r in review if r['type']=='late_first_report')} late first reports, {sum(1 for r in review if r['type']=='id_gap')} id gaps)")
    for e in errors[:60]: print("  ERROR", e)
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main())
