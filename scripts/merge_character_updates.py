"""Rebuild every character's context_log from 03_news/character_updates/batch-*.json.
Idempotent: context_log is regenerated from the update files each run (manual notes go in a
character's 'notes' field instead).  Usage: python scripts/merge_character_updates.py"""
import sys, os, glob, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save, path

def main():
    data = load("01_characters/characters.json")
    chars = {c["id"]: c for c in data["characters"]}
    logs = {cid: [] for cid in chars}
    unknown = []
    for f in sorted(glob.glob(path("03_news", "character_updates", "batch-*.json"))):
        with open(f, encoding="utf-8") as fh:
            upd = json.load(fh)
        for u in upd.get("updates", []):
            cid = u.get("character_id")
            if cid in logs:
                logs[cid].append({"day": u.get("day"), "story_id": u.get("story_id"),
                                  "note": u.get("note"), "batch": upd.get("batch")})
            else:
                unknown.append(cid)
    for cid, log in logs.items():
        chars[cid]["context_log"] = sorted(log, key=lambda e: (e["day"] if e["day"] is not None else 0, e["story_id"] or ""))
    save("01_characters/characters.json", data)
    total = sum(len(v) for v in logs.values())
    print(f"merged {total} notes into {sum(1 for v in logs.values() if v)} characters; unknown ids: {sorted(set(unknown))}")

if __name__ == "__main__":
    main()
