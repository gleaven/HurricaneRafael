"""Check every story against 01_characters/canon.json.
For each canon character, sentences that name them (plus the next two) are tested against the forbid
patterns of facts in force on the story's day; bylined journalists count as mentioned throughout.
Ages are checked wherever 'Name, NN' or 'NN-year-old ... Name' appears.
Usage: python scripts/check_canon.py   -> 07_validation/reports/canon_report.json; exit 1 on violations"""
import sys, os, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, load_all_stories, save
from textutil import segments, allowed

def main():
    canon = load("01_characters/canon.json")["characters"]
    allow = load("07_validation/allowlist.json")["entries"]
    stories = load_all_stories()
    viol = []
    for s in stories:
        segs = segments(s); n = len(segs)
        for c in canon:
            toks = [t for t in c["name_tokens"] if t]
            tok_re = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(t) for t in toks))
            bylined = c["id"] in s["byline"]
            idx = set(range(n)) if bylined else set()
            for i, (_, sent) in enumerate(segs):
                if tok_re.search(sent):
                    idx.update(range(i, min(n, i + 3)))
            if not idx:
                continue
            window = [segs[i][1] for i in sorted(idx)]
            wtext = " ".join(window)
            for fact in c.get("facts", []):
                if fact.get("since_day", -999) > s["day"]:
                    continue
                for fb in fact.get("forbid", []):
                    for sent in window:
                        m = re.search(fb["pattern"], sent, flags=re.I)
                        if m and not allowed(allow, "canon", s["story_id"], m.group(0)):
                            viol.append({"story_id": s["story_id"], "character": c["id"], "fact": fact["key"],
                                         "match": m.group(0), "why": fb["why"], "sentence": sent[:240]})
            if c.get("age"):
                surn = [re.escape(t) for t in toks]
                for m in re.finditer(r"\b(?:%s),\s+(\d{1,3})\b" % "|".join(surn), wtext):
                    if int(m.group(1)) != c["age"] and not allowed(allow, "canon", s["story_id"], m.group(0)):
                        viol.append({"story_id": s["story_id"], "character": c["id"], "fact": "age", "match": m.group(0), "why": f"canon age {c['age']}", "sentence": ""})
                for m in re.finditer(r"\b(\d{1,3})-year-old\b[^.]{0,60}?\b(?:%s)\b" % "|".join(surn), wtext):
                    if int(m.group(1)) != c["age"] and not allowed(allow, "canon", s["story_id"], m.group(0)):
                        viol.append({"story_id": s["story_id"], "character": c["id"], "fact": "age", "match": m.group(0), "why": f"canon age {c['age']}", "sentence": ""})
    seen, uniq = set(), []
    for v in viol:
        k = (v["story_id"], v["character"], v["match"])
        if k not in seen:
            seen.add(k); uniq.append(v)
    save("07_validation/reports/canon_report.json", {"violations": uniq, "count": len(uniq)})
    print(f"canon check: {len(uniq)} violations across {len(stories)} stories, {len(canon)} characters")
    for v in uniq[:40]:
        print(f"  {v['story_id']} {v['character']} [{v['fact']}] '{v['match']}' - {v['why']}")
    return 1 if uniq else 0

if __name__ == "__main__":
    sys.exit(main())
