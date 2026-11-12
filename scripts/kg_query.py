"""Continuity lookups for writers, from the internal knowledge graph and story files.
  python scripts/kg_query.py character CHR-040 [--before DAY]   what a character has said and done so far
  python scripts/kg_query.py arc ARC-SPILL [--before DAY]       an arc's stories in order
  python scripts/kg_query.py story NWS-P044-01                  a story's neighbours
  python scripts/kg_query.py day 44                             everything published on a day, plus facts going public"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, load_all_stories, load

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["character", "arc", "story", "day"])
    ap.add_argument("key")
    ap.add_argument("--before", type=int, default=None)
    a = ap.parse_args()
    ctx = context(); stories = load_all_stories()
    by_id = {s["story_id"]: s for s in stories}
    lim = a.before if a.before is not None else 10**6
    if a.kind == "character":
        c = ctx["characters"][a.key]
        print(f"{c['name']} - {c['role']} ({c['affiliation'].get('org')})\nVoice: {c['voice']}\nBio: {c['bio']}")
        for e in c.get("context_log", []):
            if e["day"] is not None and e["day"] < lim:
                print(f"  day {e['day']:+4d} {e['story_id']}: {e['note']}")
    elif a.kind == "arc":
        for s in stories:
            if a.key in s["tags"].get("arcs", []) and s["day"] < lim:
                print(f"day {s['day']:+4d} {s['story_id']} [{ctx['outlets'][s['outlet_id']]['name']}] {s['headline']}")
    elif a.kind == "story":
        s = by_id[a.key]; idx = load("03_news/story_index.json")["stories"][a.key]
        print(f"{s['headline']}\n{s['dek']}\nprev in arc: {idx['prev_in_arc']}\nnext in arc: {idx['next_in_arc']}")
        for r in idx["related"]:
            print(f"  related ({r['score']}): {r['story_id']} {by_id[r['story_id']]['headline']}")
    else:
        d = int(a.key)
        for f in ctx["facts"].values():
            if f["day"] == d:
                print(f"PUBLIC TODAY {f['id']}: {f['statement']}")
        for s in stories:
            if s["day"] == d:
                print(f"{s['time_local']} {s['story_id']} [{ctx['outlets'][s['outlet_id']]['name']}] {s['headline']}")

if __name__ == "__main__":
    main()
