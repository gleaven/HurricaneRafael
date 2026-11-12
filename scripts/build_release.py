"""Write 08_release/news_stories_public.json: stories with public fields only (no ids from the
scenario registry, no ground-truth links).  Usage: python scripts/build_release.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import context, load_all_stories, save, public_exclusions
EXCLUDED = public_exclusions()[0]
from build_rss import pubdate

def main():
    ctx = context(); out = []
    for s in load_all_stories():
        _, dt = pubdate(s["day"], s["time_local"])
        out.append({"id": s["story_id"], "published": dt.isoformat(), "outlet": ctx["outlets"][s["outlet_id"]]["name"],
                    "section": s["section"], "authors": [ctx["characters"][b]["name"] for b in s["byline"]],
                    "headline": s["headline"], "summary": s["dek"], "body": s["body"],
                    "story_type": s["tags"].get("story_type"),
                    "storylines": [ctx["arcs"][a]["name"] for a in s["tags"].get("arcs", []) if a in ctx["arcs"]],
                    "people": [ctx["characters"][c]["name"] for c in s["tags"].get("characters_quoted", []) + s["tags"].get("characters_mentioned", []) if c in ctx["characters"]],
                    "places": [ctx["places"][p]["name"] for p in s["tags"].get("places", []) if p in ctx["places"] and p not in EXCLUDED],
                    "topics": s["tags"].get("topics", [])})
    save("08_release/news_stories_public.json", {"scenario": "Hurricane Rafael (fictional)", "count": len(out), "stories": out})
    print(f"release: {len(out)} stories")

if __name__ == "__main__":
    main()
