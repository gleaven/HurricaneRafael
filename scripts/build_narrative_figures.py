"""Build 07_validation/reports/narrative_figures.json: every figure the stories and the public record state, per quantity and day.

For each quantity in 07_validation/canon_rules.json the table holds
  allowed   - the canon values with the day window in which each may be stated,
  by_value  - every stated value with first/last day, count and the ids that state it,
  series    - (day, value) pairs in day order,
  conflicts - statements whose value is not allowed on that day,
  monotonic - for cumulative quantities, whether the running total ever goes down.
scripts/check_canon_decisions.py reads 'allowed' from this file.

    python3 scripts/build_narrative_figures.py
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import canon_text as ct


def main():
    rules = ct.jload("07_validation/canon_rules.json")
    out = {"_about": {"built_by": "scripts/build_narrative_figures.py", "source_rules": "07_validation/canon_rules.json",
                      "scopes": ["stories", "facts"], "note": "Days are scenario days (0 = Tuesday 2027-09-14, landfall)."}, "quantities": {}}
    documents = list(ct.docs(scopes={"stories", "facts"}))
    total_conf = 0
    for q in rules["quantities"]:
        rows = []
        for scope, did, day, text, rel in documents:
            if day < q.get("min_day", -999):
                continue
            for v, s in ct.extract(q, text):
                rows.append({"day": day, "id": did, "scope": scope, "value": v, "text": s[:240]})
        rows.sort(key=lambda r: (r["day"], r["id"]))
        byv = {}
        for r in rows:
            b = byv.setdefault(str(r["value"]), {"value": r["value"], "count": 0, "first_day": r["day"], "last_day": r["day"], "ids": []})
            b["count"] += 1; b["last_day"] = max(b["last_day"], r["day"]); b["first_day"] = min(b["first_day"], r["day"])
            if r["id"] not in b["ids"]:
                b["ids"].append(r["id"])
        conflicts = [r for r in rows if not ct.allowed_on(q["allowed"], r["value"], r["day"])]
        mono = None
        if q.get("monotonic_total"):
            seq = [r for r in rows if r["value"] in q["monotonic_total"]]
            hi, bad = 0, []
            for r in seq:
                # a later story may recall an earlier count only if it also states the current one
                hi = max(hi, r["value"])
            day_max = {}
            for r in seq:
                day_max[r["day"]] = max(day_max.get(r["day"], 0), r["value"])
            prev = 0
            for d in sorted(day_max):
                if day_max[d] < prev:
                    bad.append({"day": d, "value": day_max[d], "previous": prev})
                prev = max(prev, day_max[d])
            mono = {"values": q["monotonic_total"], "ok": not bad, "drops": bad}
        total_conf += len(conflicts) + (0 if mono is None or mono["ok"] else len(mono["drops"]))
        out["quantities"][q["id"]] = {
            "decision": q["decision"], "allowed": q["allowed"],
            "by_value": sorted(byv.values(), key=lambda b: (b["first_day"], str(b["value"]))),
            "series": [[r["day"], r["value"], r["id"]] for r in rows],
            "conflicts": conflicts, **({"monotonic": mono} if mono else {}),
        }
    out["_about"]["statements"] = sum(len(v["series"]) for v in out["quantities"].values())
    out["_about"]["conflicts"] = total_conf
    fp = os.path.join(ct.ROOT, "07_validation", "reports", "narrative_figures.json")
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"narrative figures: {len(out['quantities'])} quantities, {out['_about']['statements']} statements, {total_conf} conflict(s)")
    for k, v in out["quantities"].items():
        for c in v["conflicts"]:
            print(f"  - {k}: D{c['day']:+d} {c['id']}: {c['value']} | {c['text'][:150]}")
        if v.get("monotonic") and not v["monotonic"]["ok"]:
            print(f"  - {k}: running total goes down: {v['monotonic']['drops']}")
    return 1 if total_conf else 0


if __name__ == "__main__":
    sys.exit(main())
