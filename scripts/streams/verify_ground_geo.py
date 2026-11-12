"""Run the official geo rules (scripts/check_geo.py Checker) on every position source of the
ground emergency family, one file at a time, so that it fits in short calls:

  vehicle locations (AVL)             moving or parked within 30 m of a street
  911 incidents, rescue positions     on land and within 150 m of a street
  flood soundings                     within 30 m of a street
  damage-assessment structures        on land and within 150 m of a street
  utility site surveys, the land-side registries (rules as listed in position_rules.json)

A tally is kept in 07_validation/reports/geo_check_ground.json (the AVL part also in
geo_check_avl.json); files that have not changed since they were checked are skipped.

    python3 scripts/streams/verify_ground_geo.py            # check what is not yet checked (about 40 s per call)
    python3 scripts/streams/verify_ground_geo.py --reset    # start over
"""
import glob
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import check_geo  # noqa: E402

ROOT = check_geo.ROOT
OUT = os.path.join(ROOT, "07_validation", "reports", "geo_check_ground.json")
OUT_AVL = os.path.join(ROOT, "07_validation", "reports", "geo_check_avl.json")
BUDGET = float(os.environ.get("AVL_CHECK_SECONDS", "38"))
REGISTRY_FILES = ("facility_registry.json", "infrastructure_assets.json", "sensor_registry.json", "cad_units.json")


def units():
    """(key, rule) for every piece: one per file, or one per registry rule."""
    out = []
    rel = lambda f: os.path.relpath(f, ROOT).replace(os.sep, "/")
    for f in sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "avl", "*.csv")), key=os.path.getsize):
        out.append(("AVL " + os.path.basename(f), f, {"name": "AVL " + os.path.basename(f), "glob": rel(f), "lat": "latitude", "lon": "longitude", "rule": "vehicle", "id": "unit_id"}))
    for f in sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "911", "cad_incidents_*.csv"))):
        out.append(("911 " + os.path.basename(f), f, {"name": "911 " + os.path.basename(f), "glob": rel(f), "lat": "latitude", "lon": "longitude", "rule": "incident", "id": "incident_number"}))
    f = os.path.join(ROOT, "05_other_sources", "sar", "sar_missions.csv")
    out.append(("SAR rescue positions", f, {"name": "SAR rescue positions", "glob": rel(f), "lat": "latitude", "lon": "longitude", "rule": "incident", "id": "case_number"}))
    f = os.path.join(ROOT, "05_other_sources", "sar", "flood_depth_soundings.csv")
    out.append(("SAR flood depth soundings", f, {"name": "SAR flood depth soundings", "glob": rel(f), "lat": "latitude", "lon": "longitude", "rule": "vehicle", "tolerance_m": 30, "id": "unit_id"}))
    f = os.path.join(ROOT, "05_other_sources", "infrastructure", "damage_assessment.csv")
    out.append(("Damage structures (street rule)", f, {"name": "Damage structures (street rule)", "glob": rel(f), "lat": "LATITUDE", "lon": "LONGITUDE", "rule": "incident", "id": "structure_id"}))
    f = os.path.join(ROOT, "05_other_sources", "infrastructure", "utility_site_survey.csv")
    out.append(("Utility site surveys", f, {"name": "Utility site surveys", "glob": rel(f), "lat": "LATITUDE", "lon": "LONGITUDE", "rule": "land_fixed", "id": "asset_id"}))
    rules = json.load(open(os.path.join(ROOT, "99_reference", "geo", "position_rules.json"), encoding="utf-8"))["sources"]
    for r in rules:
        if os.path.basename(r["glob"]) in REGISTRY_FILES:
            out.append((r["name"], os.path.join(ROOT, r["glob"]), r))
    return out


def main():
    done = {}
    if os.path.exists(OUT) and "--reset" not in sys.argv:
        done = json.load(open(OUT))
    U = units()
    sig = lambda f: f"{os.path.getsize(f)}:{int(os.path.getmtime(f))}" if os.path.exists(f) else "missing"
    done = {k: v for k, v in done.items() if any(k == key for key, _, _ in U)}
    todo = [(k, f, r) for k, f, r in U if done.get(k, {}).get("sig") != sig(f)]
    if todo:
        C = check_geo.Checker()
        t0 = time.time()
        for k, f, rule in todo:
            if time.time() - t0 > BUDGET:
                break
            o = C.run(rule)
            done[k] = {"sig": sig(f), "rows": o["rows"], "violations": o["violations"], "examples": o["examples"][:3]}
            print(f"{'ok  ' if not o['violations'] else 'FAIL'} {k:<44} rows {o['rows']:>8} violations {o['violations']}")
            json.dump(done, open(OUT, "w"), indent=1)
            json.dump({kk[4:]: v for kk, v in done.items() if kk.startswith("AVL ")}, open(OUT_AVL, "w"), indent=1)
    left = [k for k, f, r in U if done.get(k, {}).get("sig") != sig(f)]
    if left:
        print(f"{len(left)} piece(s) left; run again")
        sys.exit(3)
    tot = sum(v["violations"] for v in done.values()); rows = sum(v["rows"] for v in done.values())
    avl = sum(v["rows"] for k, v in done.items() if k.startswith("AVL "))
    print(f"ground geo check: {len(done)} pieces, {rows} positions ({avl} vehicle fixes), {tot} violations  ->  {'COMPLETE - PASS' if tot == 0 else 'COMPLETE - FAILED'}")
    sys.exit(0 if tot == 0 else 1)


if __name__ == "__main__":
    main()
