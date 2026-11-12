"""Check that no text contradicts a canon decision (00_scenario/canon_decisions.md).

Rules live in 07_validation/canon_rules.json; every rule names the decision it enforces.
  banned      - phrases and names that may not appear in the listed scopes
  gated       - phrases that may appear only from a given scenario day (dated text only)
  windows     - statements of an ongoing state (notice in effect, channel closed, curfew, new sightings) only inside their days
  event_dates - a calendar date attached to a canon event must be the canon date
  weekday     - 'Tuesday, Sept. 14' must be a real pairing on the scenario calendar
  quantities  - each stated figure must be a canon value for that day (windows from 07_validation/reports/narrative_figures.json)

Scopes: stories, public record, newsroom data, MSEL / thread designs / answer keys / characters ('internal'),
registries, and the public-voice files under 05_other_sources. The narrative layer must pass. Hits under
05_other_sources and in registries this pass does not own are listed and written to the report but do not fail the run
(use --strict to make them fail).

    python3 scripts/check_canon_decisions.py [--strict] [--no-other-sources]
Writes 07_validation/reports/canon_decisions_check.json. Exit 1 on any narrative-layer violation.
"""
import datetime, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canon_text as ct

STRICT = "--strict" in sys.argv
REPORT_ONLY_SCOPES = {"other_sources"}
# registry files owned by other passes: reported, not failed
REPORT_ONLY_FILES = {"06_data_streams/facility_registry.json", "06_data_streams/vessels.json", "06_data_streams/gw_host_registry.json",
                     "06_data_streams/scada_tags.json", "06_data_streams/infrastructure_assets.json"}
MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WD_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS_ES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9,
             "octubre": 10, "noviembre": 11, "diciembre": 12}
EXPL = re.compile(r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),? (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})\b")
EXPL_ES = re.compile(r"\b(lunes|martes|miércoles|jueves|viernes|sábado|domingo),? (\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)", re.I)
LEAD = re.compile(r"\b(?:said|announced|confirmed|reported|dijo|dijeron|informó|anunció|anunciaron|confirmó) (?:on |late |early |el )?"
                  r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|lunes|martes|miércoles|jueves|viernes|sábado|domingo)\b")


def nearest_date(month, dom, day):
    base = ct.D0 + datetime.timedelta(days=day if day is not None else 0)
    best = None
    for y in (2027, 2028, 2026):
        try:
            d = datetime.date(y, month, dom)
        except ValueError:
            continue
        if best is None or abs((d - base).days) < abs((best - base).days):
            best = d
    return best


def snippet(text, m, width=170):
    i = max(0, m.start() - width // 2)
    return text[i:i + width].replace("\n", " ")


def main():
    rules = ct.jload("07_validation/canon_rules.json")
    fig = ct.jload("07_validation/reports/narrative_figures.json")
    allow = ct.jload("07_validation/canon_rules_allowlist.json") if os.path.exists(os.path.join(ct.ROOT, "07_validation", "canon_rules_allowlist.json")) else {}
    allowed_pairs = {(a["rule"], a["id"]) for a in allow.get("allow", [])}
    banned = [(b, re.compile(b["pattern"], re.I if b.get("flags", "i") == "i" else 0)) for b in rules["banned"]]
    gated = []
    for g in rules["gated"]:
        if g.get("from_file"):
            for t in ct.jload(g["from_file"])["terms"]:
                gated.append(({"id": g["id"], "decision": g["decision"] + ": " + t.get("why", ""), "from_day": t["public_from_day"], "term": t["pattern"], "prose_only": True}, re.compile(t["pattern"], re.I)))
        else:
            gated.append((g, re.compile(g["pattern"], re.I)))
    windows = [(w, re.compile(w["pattern"], re.I)) for w in rules["windows"]]
    evd = [(e, re.compile(e["pattern"], re.I)) for e in rules["event_dates"]]
    quantities = rules["quantities"]
    for q in quantities:
        q["allowed"] = fig["quantities"][q["id"]]["allowed"]
    fails, reports, review = [], [], []
    counts = {}

    def hit(rule, scope, did, day, rel, msg):
        rec = {"rule": rule["id"], "decision": rule["decision"], "scope": scope, "id": did, "day": day, "file": rel, "what": msg}
        if (rule["id"], did) in allowed_pairs:
            return
        soft = (scope in REPORT_ONLY_SCOPES or rel in REPORT_ONLY_FILES) and not STRICT
        (reports if soft else fails).append(rec)

    for scope, did, day, text, rel in ct.docs(other_sources="--no-other-sources" not in sys.argv):
        counts[scope] = counts.get(scope, 0) + 1
        public = scope in ("stories", "facts", "other_sources")
        for b, rx in banned:
            if scope in b["scopes"]:
                m = rx.search(text)
                if m:
                    hit(b, scope, did, day, rel, f"banned text '{m.group(0)}': …{snippet(text, m)}…")
        if not public:
            continue
        if day is not None:
            for g, rx in gated:
                if g.get("prose_only") and scope == "other_sources":
                    continue  # internal ids are legitimate in data rows
                m = rx.search(text)
                if not m:
                    continue
                fd = g.get("from_day")
                if fd is None:
                    hit(g, scope, did, day, rel, f"never-public term '{m.group(0)}'")
                elif day < fd and day >= g.get("not_before_day", -999):
                    hit(g, scope, did, day, rel, f"'{m.group(0)}' on day {day}, public from day {fd}: …{snippet(text, m)}…")
            if scope == "stories":
                for w, rx in windows:
                    m = rx.search(text)
                    if m:
                        spans = w.get("story_days_any") or [w["story_days"]]
                        if not any(a <= day <= b for a, b in spans):
                            hit(w, scope, did, day, rel, f"'{m.group(0)}' on day {day}, outside {spans}: …{snippet(text, m)}…")
            for e, rx in evd:
                for m in rx.finditer(text):
                    g = [x for x in m.groups() if x]
                    mon, dom = MONTHS[g[0][:3].lower()], int(g[1])
                    if [mon, dom] not in e["expect"]:
                        hit(e, scope, did, day, rel, f"date {g[0]} {dom} for this event; canon {e['expect']}: …{snippet(text, m)}…")
            for q in quantities:
                if day < q.get("min_day", -999) or (q.get("narrative_only") and scope == "other_sources"):
                    continue
                for v, s in ct.extract(q, text):
                    if not ct.allowed_on(q["allowed"], v, day):
                        ok = [a for a in q["allowed"]]
                        hit({"id": "Q-" + q["id"], "decision": q["decision"]}, scope, did, day, rel, f"{q['id']} = {v} on day {day}; allowed {ok}: {s[:170]}")
            wrule = rules["weekday"]
            for m in EXPL.finditer(text):
                d = nearest_date(MONTHS[m.group(2)[:3].lower()], int(m.group(3)), day)
                if d and WD[d.weekday()] != m.group(1).lower():
                    hit(wrule, scope, did, day, rel, f"'{m.group(0)}' is a {WD[d.weekday()].title()}")
            for m in EXPL_ES.finditer(text):
                d = nearest_date(MONTHS_ES[m.group(3).lower()], int(m.group(2)), day)
                if d and WD_ES[d.weekday()] != m.group(1).lower():
                    hit(wrule, scope, did, day, rel, f"'{m.group(0)}' es {WD_ES[d.weekday()]}")
            if scope == "stories":
                lead = text.split("\n")[2] if text.count("\n") >= 2 else ""
                wd = (ct.D0 + datetime.timedelta(days=day)).weekday()
                for m in LEAD.finditer(lead):
                    w = m.group(1).lower()
                    wi = WD_ES.index(w) if w in WD_ES else WD.index(w)
                    if (wd - wi) % 7 >= 2:
                        review.append({"id": did, "day": day, "what": f"lead says '{m.group(0)}', story day is a {WD[wd].title()}"})
    # one value per quantity and cumulative totals never falling (from the figures table)
    for qid, q in fig["quantities"].items():
        if q.get("monotonic") and not q["monotonic"]["ok"]:
            fails.append({"rule": "Q-" + qid, "decision": q["decision"], "scope": "stories", "id": qid, "day": None, "file": "07_validation/reports/narrative_figures.json",
                          "what": f"running total goes down: {q['monotonic']['drops']}"})
        for c in q["conflicts"]:
            pass  # already raised above from the live text
    out = {"checked": counts, "rules": {k: len(v) for k, v in rules.items() if isinstance(v, list)}, "violations": fails,
           "reported_not_owned": reports, "review": review}
    fp = os.path.join(ct.ROOT, "07_validation", "reports", "canon_decisions_check.json")
    with open(fp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("canon decisions check: documents", counts)
    print(f"  violations in the narrative layer: {len(fails)}")
    for r in fails[:60]:
        print(f"   - [{r['rule']}] {r['id']} (day {r['day']}): {r['what'][:230]}")
    by = {}
    for r in reports:
        by.setdefault((r["rule"], r["file"]), []).append(r)
    print(f"  reported in files this pass does not own: {len(reports)} hit(s) in {len(by)} rule/file group(s)")
    byrule = {}
    for (rule, rel), lst in sorted(by.items()):
        byrule.setdefault(rule, []).append((rel, lst))
    for rule, groups in sorted(byrule.items()):
        n = sum(len(l) for _, l in groups)
        files = ", ".join(sorted({rel.split("05_other_sources/")[-1].split("/")[0] if "05_other_sources" in rel else rel for rel, _ in groups}))
        print(f"   - [{rule}] {n} hit(s) in {files}; e.g. {groups[0][1][0]['id'].split('/')[-1]}: {groups[0][1][0]['what'][:150]}")
    if review:
        print(f"  to review (not failures): {len(review)}")
        for r in review[:10]:
            print(f"   - {r['id']}: {r['what']}")
    print("PASS" if not fails else "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
