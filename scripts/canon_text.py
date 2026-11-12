"""Shared text loading and figure extraction for build_narrative_figures.py and check_canon_decisions.py.

A document is (scope, doc_id, day or None, text, relative_file). Scopes are described in
07_validation/canon_rules.json -> _about.scopes.
"""
import csv, datetime, glob, io, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D0 = datetime.date(2027, 9, 14)
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "twenty-three": 23, "doce": 12, "catorce": 14, "veintitrés": 23}
UNITS = {"billion": "billion", "b": "billion", "mil millones": "billion", "million": "million", "m": "million", "millones": "million"}
SENT = re.compile(r"(?<=[.!?”\"'])\s+(?=[A-Z¿¡\"“'(])")


def jload(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def day_of(date_str):
    """Scenario day of a local ISO date or timestamp (first 10 characters)."""
    try:
        y, m, d = (int(x) for x in date_str[:10].split("-"))
        return (datetime.date(y, m, d) - D0).days
    except Exception:
        return None


def utc_day(ts):
    """Scenario day (local, UTC-5) of a UTC timestamp like 2027-09-14T06:00:00Z."""
    try:
        t = datetime.datetime.strptime(ts[:16], "%Y-%m-%dT%H:%M") - datetime.timedelta(hours=5)
        return (t.date() - D0).days
    except Exception:
        return None


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from strings(x)
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)


def sentences(text):
    for para in text.split("\n"):
        for s in SENT.split(para):
            s = s.strip()
            if s:
                yield s


def stories():
    for fp in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
        for s in json.load(open(fp, encoding="utf-8"))["stories"]:
            yield rel, s


def facts():
    for rel in ("02_public_record/public_record.json", "scenarios/gridwater/02_public_record/public_record.json"):
        if os.path.exists(os.path.join(ROOT, rel)):
            for f in jload(rel).get("facts", []):
                yield rel, f


def docs(scopes=None, other_sources=True):
    want = lambda s: scopes is None or s in scopes
    if want("stories"):
        for rel, s in stories():
            yield ("stories", s["story_id"], s["day"], "\n".join([s["headline"], s["dek"]] + s["body"]), rel)
    if want("facts"):
        for rel, f in facts():
            yield ("facts", f["id"], f["day"], f["statement"] + ("\n" + re.sub(r"\b(?:OUT|ORG|CHR)-\d+\s*", "", f["source"]) if isinstance(f.get("source"), str) else ""), rel)
    if want("newsroom"):
        base = "10_news_sites/newsroom"
        for rel in [base + "/build_data.py"] + [base + "/data/" + n for n in ("milestones.json", "status.json", "outlets.json")]:
            fp = os.path.join(ROOT, rel)
            if os.path.exists(fp):
                yield ("newsroom", rel, None, open(fp, encoding="utf-8").read(), rel)
    if want("internal"):
        for rel in ("00_scenario/msel.json", "scenarios/gridwater/00_scenario/msel.json"):
            if os.path.exists(os.path.join(ROOT, rel)):
                d = jload(rel)
                for e in (d if isinstance(d, list) else d.get("events", [])):
                    yield ("internal", e["event_id"], e.get("day"), "\n".join(strings(e)), rel)
        rels = sorted(os.path.relpath(p, ROOT).replace(os.sep, "/") for p in glob.glob(os.path.join(ROOT, "_thread_designs", "*.json")))
        rels += ["00_scenario/threads.json", "scenarios/gridwater/00_scenario/threads.json", "00_scenario/answer_key.json",
                 "06_answer_key/answer_key.json", "scenarios/gridwater/06_answer_key/answer_key.json",
                 "01_characters/characters.json", "01_characters/canon.json", "03_news/arcs.json"]
        for rel in rels:
            fp = os.path.join(ROOT, rel)
            if os.path.exists(fp):
                yield ("internal", rel, None, open(fp, encoding="utf-8").read(), rel)
    if want("registries"):
        for fp in sorted(glob.glob(os.path.join(ROOT, "06_data_streams", "*.json")) + glob.glob(os.path.join(ROOT, "06_data_streams", "entity_catalogs", "*.json"))):
            rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
            yield ("registries", rel, None, open(fp, encoding="utf-8").read(), rel)
    if want("other_sources") and other_sources:
        yield from other_source_docs()


def other_source_docs():
    """Public-voice files in 05_other_sources (read-only)."""
    base = os.path.join(ROOT, "05_other_sources")
    for fp in sorted(glob.glob(os.path.join(base, "press_releases", "*.jsonl"))):
        rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
        for line in open(fp, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                yield ("other_sources", f"{rel}#{r.get('id')}", day_of(r.get("date_local", "")), r.get("text", "") + "\n" + " ".join(x for x in strings(r.get("speakers", []))), rel)
    csvs = glob.glob(os.path.join(base, "broadcast", "*.csv")) + [os.path.join(base, "public_health", "eas_broadcasts.csv")] + \
        glob.glob(os.path.join(base, "shelters", "*.csv"))
    for fp in sorted(csvs):
        if not os.path.exists(fp):
            continue
        rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
        with open(fp, encoding="utf-8", newline="") as fh:
            for i, row in enumerate(csv.reader(fh)):
                if i == 0:
                    continue
                txt = " | ".join(row)
                m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", txt)
                m2 = re.search(r"\d{4}-\d{2}-\d{2}", txt)
                day = utc_day(m.group(0)) if m else (day_of(m2.group(0)) if m2 else None)
                yield ("other_sources", f"{rel}#row{i + 1}", day, txt, rel)
    try:
        per = jload("06_data_streams/personas.json")
        per = per if isinstance(per, list) else next(v for v in per.values() if isinstance(v, list))
        handles = {p["handle"].lstrip("@") for p in per if p.get("account_type") in ("official", "media", "organization", "journalist")}
    except Exception:
        handles = set()
    for h in sorted(handles):
        fp = os.path.join(base, "social_media", h + ".jsonl")
        if not os.path.exists(fp):
            continue
        rel = os.path.relpath(fp, ROOT).replace(os.sep, "/")
        for line in open(fp, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            try:
                t = datetime.datetime.strptime(r["created_at"], "%a %b %d %H:%M:%S %z %Y").replace(tzinfo=None) - datetime.timedelta(hours=5)
                day = (t.date() - D0).days
            except Exception:
                day = None
            yield ("other_sources", f"{rel}#{r.get('id_str')}", day, r.get("full_text") or r.get("text") or "", rel)


def number(tok):
    tok = tok.lower()
    if tok in WORDS:
        return float(WORDS[tok])
    return float(tok.replace(",", ""))


def extract(rule, text):
    """Yield (value, sentence) for one quantity rule. value is a float or 'N unit' for dollars."""
    pat = rule.setdefault("_re", re.compile(rule["pattern"], re.I))
    req = rule.get("requires")
    req = rule.setdefault("_req", re.compile(req, re.I)) if req else None
    ug = rule.get("unit_group")
    for s in sentences(text):
        if req and not req.search(s):
            continue
        for m in pat.finditer(s):
            groups = [g for i, g in enumerate(m.groups(), 1) if g and i != ug]
            if not groups:
                continue
            try:
                v = number(groups[0])
            except ValueError:
                continue
            if v in rule.get("ignore", []) or v < rule.get("ignore_below", 0):
                continue
            if ug:
                u = UNITS.get(m.group(ug).lower(), m.group(ug).lower())
                yield f"{v:g} {u}", s
            else:
                yield v, s


def allowed_on(allowed, value, day):
    """True when value is allowed on day (day None = undated text: any listed value passes)."""
    for a in allowed:
        av = a["value"]
        same = (av == value) if isinstance(av, str) or isinstance(value, str) else abs(float(av) - float(value)) < 1e-9
        if same and (day is None or (a.get("from_day", -999) <= day <= a.get("to_day", 999))):
            return True
    return False
