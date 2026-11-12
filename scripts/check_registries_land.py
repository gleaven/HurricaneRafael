"""Checks for the land-side registries (facilities, CAD stations/units, infrastructure, sensors, areas).

    python scripts/check_registries_land.py

1. ids are unique within and across the five registries
2. every canon name the news corpus and public record use for these things is present
3. cross-references resolve (home stations, parents, 'serves', 'within', asset links)
4. reference data only: no scenario ids, thread ids or outcome words; no real company / hospital-system / broadcaster names
5. geography: the registry rules in 99_reference/geo/position_rules.json (via check_geo.Checker) report zero violations,
   plus checks the rules file does not cover yet (stream gauges, bridge sensors, area reference points)
Exit code 1 if anything fails.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402
import check_geo  # noqa: E402

ROOT = geo.ROOT
DS = os.path.join(ROOT, "06_data_streams")
MINE = ("facility_registry.json", "cad_units.json", "infrastructure_assets.json", "sensor_registry.json", "areas.json")

CANON_NAMES = [
    # facilities
    "Shoreline Regional Medical Center", "Bay City Medical Center", "Coastal Bend Emergency Communications Center", "Nueces County Medical Examiner",
    "South Texas Community Health Center", "Nueces Bay Blood Services", "Corpus Christi-Nueces County Public Health District",
    "Richard M. Borchard Regional Fairgrounds", "Robstown Fairgrounds", "Calallen ISD Fieldhouse", "Calallen High School", "Richard King High School", "West Oso High School",
    "Alice High School", "Solomon P. Ortiz Community Center", "Flour Bluff ISD", "Zavala Elementary", "Collier Elementary", "Yeager Elementary School",
    "Tuloso-Midway High School", "Woodlawn Community Center", "Cefe Valenzuela Park", "Cunningham Middle School", "Brownie's Corner Community Center",
    "Oveal Williams Senior Center", "Memorial Coliseum", "5301 Ayers Street", "St. John's Episcopal Church", "Del Mar College", "Texas A&M University-Corpus Christi",
    "Joint Field Office", "Unified Command", "Joint Information Center", "Naval Air Station Corpus Christi", "Corpus Christi Army Depot", "DLA Distribution Corpus Christi",
    "Naval Air Station Kingsville", "NAS Joint Reserve Base Fort Worth", "Fort Hood", "US Coast Guard Sector Corpus Christi", "National Weather Service Corpus Christi",
    "Nueces County Office of Emergency Management",
    # infrastructure
    "O.N. Stevens Water Treatment Plant", "Riverside Switching Station", "Harbor View", "Crosstown", "Southside Substation", "Bayside Substation", "McKinley Substation",
    "Palisade Energy Center", "CBPWA Operations Center", "Harbor Bridge", "Nueces Bay Causeway", "JFK Causeway", "Corpus Christi International Airport",
    "Northwest Storage Tank 1", "Clarkwood Tank", "Texana Booster Station 1", "Colorado River Booster Station", "P-1", "P-2", "P-3", "P-4", "EQP-1102", "EQP-2201",
    "GW-FAC-SUB-01", "GW-FAC-SUB-05", "FAC-UTL-01", "FAC-UTL-02", "FAC-INF-01", "TANK-0390", "WW-0",
    # sensors
    "WQ-01", "WQ-06", "GAUGE-12", "GAUGE-14", "Nueces River gauge at Calallen", "KCRP", "KNGP", "42019", "AQS-MOB-001",
    # CAD
    "Station 18", "Waldron Road", "Texas Task Force 1", "CC-SAR-001", "CC-SAR-023", "Corpus Christi Boating Association", "NuecesInfoLine",
    "Corpus Christi Police Department", "Corpus Christi Fire Department", "Nueces County Sheriff's Office",
    # areas
    "North Beach", "Hillcrest", "Oak Park", "Molina", "Greenwood", "Flour Bluff", "Calallen", "Violet", "Annaville", "Port Aransas", "Portland", "Ingleside", "Aransas Pass",
    "Rockport", "Robstown", "Mustang Island", "Padre Island", "Inner Harbor", "Water District 3", "Water District 4", "Zone 4", "Evacuation Zone A", "Evacuation Zone C",
    "Evacuation Zone D", "Evacuation Zone E", "78401", "78405", "78407", "78408", "78416", "78417", "Nueces County", "San Patricio County", "Aransas County", "Kleberg County",
]
REAL_BRANDS = r"CHRISTUS|Spohn|Driscoll Children|HCA\b|Corpus Christi Medical Center|Doctors Regional|Bay Area Medical|Flint Hills|Valero|Citgo|CITGO|NuStar|Buckeye|" \
              r"Halo-Flight|Third Coast Ambulance|Reliable Ambulance|Caller-Times|KIII|KRIS|KZTV|AEP Texas|Barney M\. Davis|Tri - County|Star of Texas|North Bay General|Lazarus"
TRUTH_WORDS = r"\bT\d{1,2}\b thread|\bthread\b|\bEVT-\d|\bGW-EVT-|\bPUB-\d|\bNWS-[MP]\d|KESTREL|STATE-X|Halcyon|scenario_role|scenario_events|story_refs|" \
              r"\battack(ed|er|s)?\b|malicious|sabotage|compromis|\bD[+-]\d+\b|targeted|answer key|spoof|adversar"


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(o, str):
        yield path, o


def main():
    fails = []

    def fail(msg):
        fails.append(msg)
        print("  FAIL", msg)

    docs = {n: json.load(open(os.path.join(DS, n), encoding="utf-8")) for n in MINE}
    fac, cad, inf, sen, ar = (docs[n] for n in MINE)

    # ---------------------------------------------------------------- 1. unique ids
    groups = {
        "facility": [f["facility_id"] for f in fac["facilities"]] + [f["facility_id"] for f in fac["out_of_area"]],
        "station": [s["station_id"] for s in cad["stations"]],
        "unit": [u["unit_id"] for u in cad["units"]],
        "asset": [a["asset_id"] for a in inf["assets"]] + [a["asset_id"] for a in inf["remote_assets"]],
        "sensor": [s.get("sensor_id") or s.get("site_id") for k, v in sen.items() if isinstance(v, list) for s in v if k != "wastewater_sampling_sites"],
        "area": [a["area_id"] for a in ar["areas"]],
    }
    seen = {}
    for g, ids in groups.items():
        for i in ids:
            if i in seen:
                fail(f"duplicate id {i} ({seen[i]} and {g})")
            seen[i] = g
    print(f"1. ids: " + ", ".join(f"{g} {len(v)}" for g, v in groups.items()))

    # ---------------------------------------------------------------- 2. canon names
    blob = "\n".join(json.dumps(d, ensure_ascii=False) for d in docs.values())
    missing = [n for n in CANON_NAMES if n not in blob]
    for n in missing:
        fail(f"canon name missing: {n}")
    print(f"2. canon names: {len(CANON_NAMES) - len(missing)} of {len(CANON_NAMES)} present")

    # ---------------------------------------------------------------- 3. cross references
    known = set(seen)
    nref = 0
    for u in cad["units"]:
        nref += 1
        if u["home_station"] not in groups["station"]:
            fail(f"unit {u['unit_id']} home_station {u['home_station']} unknown")
    for s in cad["stations"]:
        for uid in s.get("units", []):
            nref += 1
            if uid not in groups["unit"]:
                fail(f"station {s['station_id']} lists unknown unit {uid}")
        if s.get("facility_id") and s["facility_id"] not in known:
            fail(f"station {s['station_id']} facility {s['facility_id']} unknown")
    for a in inf["assets"]:
        for key in ("parent_asset_id",):
            if a.get(key):
                nref += 1
                if a[key] not in known:
                    fail(f"asset {a['asset_id']} {key} {a[key]} unknown")
        for t in a.get("serves", []) + a.get("connects", []):
            nref += 1
            if t not in known:
                fail(f"asset {a['asset_id']} serves/connects unknown {t}")
    for k, v in sen.items():
        if isinstance(v, list):
            for s in v:
                if s.get("asset_id"):
                    nref += 1
                    if s["asset_id"] not in known:
                        fail(f"sensor {s.get('sensor_id') or s.get('site_id')} asset {s['asset_id']} unknown")
    for a in ar["areas"]:
        for t in a.get("within", []) + a.get("members", []) + a.get("member_tracts", []) + a.get("water_districts", []):
            nref += 1
            if t not in known:
                fail(f"area {a['area_id']} refers to unknown {t}")
    print(f"3. cross-references checked: {nref}")

    # ---------------------------------------------------------------- 4. reference data only
    nstr = 0
    for name, d in docs.items():
        for path, text in walk(d):
            nstr += 1
            m = re.search(REAL_BRANDS, text)
            if m:
                fail(f"{name}{path}: real brand name '{m.group(0)}' in: {text[:90]}")
            m = re.search(TRUTH_WORDS, text, re.I)
            if m and not path.endswith(".description") or (m and "nature_codes" not in path and "disposition" not in path and path.endswith(".description")):
                # CAD code descriptions legitimately contain words like THREAD? none do; report everything
                fail(f"{name}{path}: scenario/truth wording '{m.group(0)}' in: {text[:90]}")
    print(f"4. strings scanned for brand names and scenario wording: {nstr}")

    # ---------------------------------------------------------------- 5. geography
    rules = json.load(open(check_geo.RULES, encoding="utf-8"))["sources"]
    mine_rules = [r for r in rules if any(r["glob"].endswith(n) for n in MINE)]
    C = check_geo.Checker()
    G = C.G
    total = 0
    for r in mine_rules:
        o = C.run(r)
        total += o["violations"]
        tag = "ok  " if not o["violations"] else "FAIL"
        note = "" if o["rows"] else "   (no rows: key not present in the registry)"
        print(f"   {tag} {o['name']:<34} rows {o['rows']:>4}  violations {o['violations']}{note}")
        for e in o["examples"]:
            fail("geo: " + e)
    # extra checks not in the rules file yet
    extra = 0
    for s in sen.get("stream_gauges", []):
        d = G.roads.nearest(s["latitude"], s["longitude"])[0]
        if d > 30:
            fail(f"stream gauge {s['sensor_id']} is {d:.0f} m from the bridge road it is mounted on")
        extra += 1
    for s in sen.get("bridge_wind_sensors", []) + sen.get("wastewater_sampling_sites", []):
        if not G.is_land(s["latitude"], s["longitude"]):
            fail(f"{s.get('sensor_id') or s.get('site_id')} not on land")
        extra += 1
    for a in ar["areas"]:
        rp = a.get("reference_point")
        if rp:
            extra += 1
            if not G.is_land(rp["latitude"], rp["longitude"]):
                fail(f"area {a['area_id']} reference point in water")
            b = a.get("bbox")
            if b and not (b[0] <= rp["longitude"] <= b[2] and b[1] <= rp["latitude"] <= b[3]):
                fail(f"area {a['area_id']} reference point outside its own bbox")
    for a in inf["assets"]:
        sm = a.get("span_midpoint")
        if sm:
            extra += 1
            if G.roads.nearest(sm["latitude"], sm["longitude"])[0] > 30:
                fail(f"{a['asset_id']} span midpoint is not on its road")
    for f in fac["out_of_area"]:
        if "latitude" in f:
            extra += 1
            if not G.is_land(f["latitude"], f["longitude"]):
                fail(f"out-of-area facility {f['facility_id']} not on land")
    for f in fac["facilities"]:
        if G.in_box(f["latitude"], f["longitude"]):
            extra += 1
            d = G.roads.nearest(f["latitude"], f["longitude"])[0]
            if d > 900:
                fail(f"facility {f['facility_id']} is {d:.0f} m from any road in the reference network")
    print(f"5. geography: {total} rule violations; {extra} extra position checks")

    print(f"\n{'PASS' if not fails else 'FAILED'}: {len(fails)} problem(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
