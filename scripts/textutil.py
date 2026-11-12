import re
SPLIT = re.compile(r'(?:(?<=[.!?])|(?<=[.!?]["\u201d]))\s+(?=[A-Z"\u201c(])')
def segments(story):
    """List of (field, sentence) for headline, dek and every body paragraph."""
    out = [("headline", story["headline"]), ("dek", story["dek"])]
    for p in story["body"]:
        out += [("body", s) for s in SPLIT.split(p) if s.strip()]
    return out
def full_text(story):
    return " ".join([story["headline"], story["dek"]] + list(story["body"]))
def allowed(allow, check, sid, match):
    return any(e["check"] == check and e["story_id"] == sid and e["match"] == match for e in allow)
