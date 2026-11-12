"""Build 03_news/story_index.json: per-story arc chains (prev/next in each arc) and related stories.
Related = shares public facts, characters or arcs within 10 days; top 5 by score.
Usage: python scripts/link_stories.py"""
import sys, os
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_all_stories, save

def main():
    stories = load_all_stories()
    by_arc = defaultdict(list)
    for s in stories:
        for a in s["tags"].get("arcs", []):
            by_arc[a].append(s["story_id"])
    index = {}
    for s in stories:
        index[s["story_id"]] = {"day": s["day"], "outlet_id": s["outlet_id"], "headline": s["headline"],
                                "arcs": s["tags"].get("arcs", []), "follows_up": s["tags"].get("follows_up"),
                                "prev_in_arc": {}, "next_in_arc": {}, "related": []}
    for arc, ids in by_arc.items():
        for i, sid in enumerate(ids):
            if i > 0:
                index[sid]["prev_in_arc"][arc] = ids[i - 1]
            if i < len(ids) - 1:
                index[sid]["next_in_arc"][arc] = ids[i + 1]
    feats = {s["story_id"]: (set(s["tags"].get("public_facts", [])),
                             set(s["tags"].get("characters_quoted", []) + s["tags"].get("characters_mentioned", [])),
                             set(s["tags"].get("arcs", [])), s["day"]) for s in stories}
    ids = [s["story_id"] for s in stories]
    for a in ids:
        fa, ca, aa, da = feats[a]
        scored = []
        for b in ids:
            if a == b:
                continue
            fb, cb, ab, db = feats[b]
            if abs(da - db) > 10:
                continue
            score = 3 * len(fa & fb) + 2 * len(ca & cb) + len(aa & ab)
            if score >= 4:
                scored.append((score, -abs(da - db), b))
        scored.sort(reverse=True)
        index[a]["related"] = [{"story_id": b, "score": sc} for sc, _, b in scored[:5]]
    save("03_news/story_index.json", {"arcs": {k: v for k, v in sorted(by_arc.items())}, "stories": index})
    print(f"indexed {len(stories)} stories across {len(by_arc)} arcs")

if __name__ == "__main__":
    main()
