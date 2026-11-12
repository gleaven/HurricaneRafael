"""Trace material numbers and explicit dates to the public record and the calendar.
Rules live in 02_public_record/quantity_rules.json: each rule has a regex with one capture group (the number)
and the allowed values with the day each becomes public.  A number that is not allowed, or used before its day,
is a violation unless allowlisted in 07_validation/allowlist.json (check 'facts').
Dates: 'Weekday, Mon. D' pairs must agree with the calendar; dates after the story's own date are listed for review.
Usage: python scripts/check_facts.py  -> 07_validation/reports/facts_report.json; exit 1 on violations"""
import sys, os, re, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, load_all_stories, save
from textutil import full_text, allowed
from dates import date_for_day

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20, "forty": 40, "half": 0.5, "second": 2}
MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "June": 6, "July": 7, "Aug": 8, "Sept": 9, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def num(tok):
    if tok is None:
        return None
    tok = tok.strip().lower().replace(",", "")
    if tok in WORDS:
        return float(WORDS[tok])
    try:
        return float(tok)
    except ValueError:
        return None

def main():
    rules = load("02_public_record/quantity_rules.json")["rules"]
    allow = load("07_validation/allowlist.json")["entries"]
    stories = load_all_stories()
    viol, future, wkd = [], [], []
    for s in stories:
        text = full_text(s); day = s["day"]
        for r in rules:
            for m in re.finditer(r["pattern"], text, flags=re.I):
                v = num(m.group(1))
                if v is None:
                    continue
                ok = [a for a in r["allowed"] if abs(a["value"] - v) < 1e-9]
                bad = None
                if not ok:
                    bad = f"value {m.group(1)} not in public record for '{r['name']}'"
                elif min(a["from_day"] for a in ok) > day:
                    bad = f"value {m.group(1)} for '{r['name']}' is public only from day {min(a['from_day'] for a in ok)}"
                if bad and not allowed(allow, "facts", s["story_id"], m.group(0)):
                    lo = max(0, m.start() - 80)
                    viol.append({"story_id": s["story_id"], "day": day, "rule": r["name"], "match": m.group(0), "problem": bad,
                                 "context": text[lo:m.end() + 80]})
        sdate = date_for_day(day)
        for m in re.finditer(r"\b(?:(%s),?\s+)?(Jan|Feb|Mar|Apr|May|June|July|Aug|Sept?|Oct|Nov|Dec)\.?\s+(\d{1,2})\b" % "|".join(WEEKDAYS), text):
            mon, dd = MONTHS[m.group(2)], int(m.group(3))
            year = 2028 if mon <= 6 else 2027
            try:
                d = datetime.date(year, mon, dd)
            except ValueError:
                wkd.append({"story_id": s["story_id"], "match": m.group(0), "problem": "invalid date"}); continue
            if m.group(1) and WEEKDAYS[d.weekday()] != m.group(1) and not allowed(allow, "facts", s["story_id"], m.group(0)):
                wkd.append({"story_id": s["story_id"], "match": m.group(0), "problem": f"{d} is a {WEEKDAYS[d.weekday()]}"})
            if d > sdate:
                future.append({"story_id": s["story_id"], "story_date": str(sdate), "match": m.group(0),
                               "context": text[max(0, m.start() - 80):m.end() + 40]})
    save("07_validation/reports/facts_report.json", {"violations": viol, "weekday_errors": wkd, "future_dates_for_review": future})
    print(f"facts check: {len(viol)} quantity violations, {len(wkd)} weekday/date errors, {len(future)} future-date mentions to review")
    for v in viol[:60]:
        print(f"  {v['story_id']} [{v['rule']}] '{v['match']}': {v['problem']}")
    for w in wkd[:20]:
        print(f"  DATE {w['story_id']} '{w['match']}': {w['problem']}")
    return 1 if (viol or wkd) else 0

if __name__ == "__main__":
    sys.exit(main())
