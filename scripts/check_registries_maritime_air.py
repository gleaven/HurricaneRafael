"""Checks for the maritime and aviation registries (06_data_streams/vessels.json,
terminal_registry.json, aircraft_registry.json, drone_operators.json).

    python3 scripts/check_registries_maritime_air.py        exit 1 on any failure

Checks
  ids         unique vessel ids, MMSIs, IMO numbers, call signs, berth/slip/position ids,
              aircraft ids, ICAO addresses, registrations, call signs, operator ids
  formats     MMSI prefix matches the flag; IMO check digit valid; ICAO address in a US range
  canon       every vessel, aircraft, terminal and operator named in the news corpus is present
  links       home_berth_id / usual_berths / sea_gates / home_base / parking / launch sites resolve
  geography   the check_geo rules for berths, anchorage points and aircraft parking; plus slips
              in water with a water route to the open bay, deep-draft berths within 150 m of a
              40 ft reach and within reach of the channel graph, anchorage points inside the NOAA
              anchorage and outside the fairways, launch sites on land
  hygiene     no scenario truth and no real company names in the participant-facing files
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402
import check_geo  # noqa: E402

ROOT = geo.ROOT
D = os.path.join(ROOT, "06_data_streams")
L = lambda n: json.load(open(os.path.join(D, n), encoding="utf-8"))
MID = {"Marshall Islands": ["538"], "Panama": ["351", "352", "353", "354", "355", "356", "357", "370", "371", "372", "373"],
       "Liberia": ["636", "637"], "Bahamas": ["308", "309", "311"], "Malta": ["215", "229", "248", "249", "256"],
       "Greece": ["237", "239", "240", "241"], "Singapore": ["563", "564", "565", "566"], "Hong Kong": ["477"], "Norway": ["257", "258", "259"],
       "Cyprus": ["209", "210", "212"], "Palau": ["511"], "Antigua and Barbuda": ["304", "305"], "United States": ["338", "366", "367", "368", "369"]}
CANON_VESSELS = ["MT Kalvora Star", "MT Ostrel Bay", "MV Gulf Provider", "FV Pelican Ridge", "Corrin Bay", "MV Halcyon Drift", "Barge 44", "Narwhal Dream"]
CANON_OPERATORS = {"Corrin Bay": "Laguna Towing", "Narwhal Dream": "Nereid Maritime Holdings"}
CANON_TERMINALS = ["Rendal Terminals", "Quellmar"]
CANON_AIRCRAFT = {"registration": ["CG-6033", "CG-6041"], "callsign": ["NOAA42", "CAMCC-04", "SYN41"]}
CANON_DRONE_OPS = ["Argus Aerial Systems", "Meridian Aerial Systems"]
REAL_NAMES = ["Flint Hills", "Buckeye", "NuStar", "Valero", "Citgo", "CITGO", "Cheniere", "Kirby", "Vopak", "Enbridge", "Koch", "Oxy", "Chemours",
              "Caller-Times", "Caller Times", "KIII", "KRIS", "KZTV", "SkyWest", "LifeStar", "Texas Tribune", "Halo-Flight", "Halo Flight",
              "CHRISTUS", "Spohn", "Driscoll", "Moda", "Gulf Copper", "Signet", "Kiewit", "Bludworth", "Maxus", "Southwest Airlines", "American Airlines",
              "United Airlines", "Dependable", "Auriga", "Meridian Star", "Pier 9"]
TRUTH_WORDS = [r"STATE-X", r"KESTREL", r"\"threads\"", r"EVT-\d", r"PUB-\d", r"ARC-", r"spoof", r"hostile", r"sanction", r"adversar", r"attack", r"sabotag",
               r"scenario_role", r"story_refs", r"front company", r"\bD[+-]\d", r"GridWater", r"explosive device", r"\bDEV-0"]
fails = []


def fail(msg):
    fails.append(msg)
    print("  FAIL", msg)


def uniq(items, what):
    seen = set()
    for x in items:
        if x is None:
            continue
        if x in seen:
            fail(f"duplicate {what}: {x}")
        seen.add(x)
    return seen


def main():
    V, T, A, DR = L("vessels.json"), L("terminal_registry.json"), L("aircraft_registry.json"), L("drone_operators.json")
    vs, ac = V["vessels"], A["aircraft"]
    G = geo.Geo(build_roads=False)

    # ---------------- ids and formats
    uniq([v["vessel_id"] for v in vs], "vessel_id")
    uniq([v["mmsi"] for v in vs], "MMSI")
    uniq([v["imo"] for v in vs], "IMO")
    uniq([v["call_sign"] for v in vs], "call sign")
    uniq([v["vessel_name"] for v in vs], "vessel name")
    for v in vs:
        if v["mmsi"] and (not re.fullmatch(r"\d{9}", v["mmsi"]) or v["mmsi"][:3] not in MID.get(v["flag"], [])):
            fail(f"{v['vessel_id']} MMSI {v['mmsi']} does not match flag {v['flag']}")
        if v["imo"]:
            d = [int(c) for c in v["imo"][3:]]
            if len(d) != 7 or sum(a * w for a, w in zip(d[:6], (7, 6, 5, 4, 3, 2))) % 10 != d[6]:
                fail(f"{v['vessel_id']} IMO check digit wrong: {v['imo']}")
        if v["deep_draft"] != (v["draft_m"] >= 9.0 and v["class"] not in ("navy",) and v["vessel_id"] != "VSL-0031"):
            fail(f"{v['vessel_id']} deep_draft flag inconsistent with draft {v['draft_m']}")
        for k in ("vessel_id", "vessel_name", "class", "ais_type_code", "length_m", "beam_m", "draft_m", "operator", "flag", "typical_pattern"):
            if v.get(k) in (None, ""):
                fail(f"{v['vessel_id']} missing {k}")
    bid = uniq([b["berth_id"] for b in T["berths"]], "berth_id") | uniq([s["slip_id"] for s in T["slips"]], "slip_id")
    tid = uniq([t["terminal_id"] for t in T["terminals"]], "terminal_id")
    gid = uniq([g["gate_id"] for g in T["sea_gates"]], "gate_id")
    uniq([a["position_id"] for a in T["anchorage_positions"]], "anchorage position_id")
    uniq([a["aircraft_id"] for a in ac], "aircraft_id")
    uniq([a["icao24"] for a in ac], "icao24")
    uniq([a["registration"] for a in ac], "registration")
    uniq([a["callsign"] for a in ac], "callsign")
    fid = uniq([f["airfield_id"] for f in A["airfields"]], "airfield_id")
    pid = uniq([p["position_id"] for p in A["parking_positions"]], "parking position_id")
    for a in ac:
        if not re.fullmatch(r"a[0-9a-f]{5}", a["icao24"]):
            fail(f"{a['aircraft_id']} icao24 {a['icao24']} not in a US range")
        if a["military"] != a["icao24"].startswith("ae"):
            fail(f"{a['aircraft_id']} military flag and ICAO block disagree")
    sid = uniq([s["site_id"] for s in DR["launch_sites"]], "launch site_id")
    uniq([o["operator_id"] for o in DR["authorized_operators"]], "operator_id")
    uniq([f["airframe_id"] for o in DR["authorized_operators"] for f in o["airframes"]], "airframe_id")

    # ---------------- canon
    names = {v["vessel_name"]: v for v in vs}
    for n in CANON_VESSELS:
        if n not in names:
            fail(f"canon vessel missing: {n}")
    for n, op in CANON_OPERATORS.items():
        if n in names and op not in names[n]["operator"]:
            fail(f"{n} operator should include '{op}'")
    for n in CANON_TERMINALS:
        if not any(n in t["terminal_name"] or n in t["operator"] for t in T["terminals"]):
            fail(f"canon terminal missing: {n}")
    for k, vals in CANON_AIRCRAFT.items():
        for val in vals:
            if not any(a[k] == val for a in ac):
                fail(f"canon aircraft {k} missing: {val}")
    for n in CANON_DRONE_OPS:
        if not any(n == o["org_name"] for o in DR["authorized_operators"]):
            fail(f"canon drone operator missing: {n}")
    if not any(v.get("cargo_control_system_vendor") == "Brightwake Marine Systems" for v in vs):
        fail("Brightwake Marine Systems is not listed as a cargo-control vendor")
    if not any(s["slip_name"] == "Ingleside Marina Berth 7" for s in T["slips"]):
        fail("Ingleside Marina Berth 7 missing")
    yank = json.load(open(os.path.join(D, "_internal", "vessels_truth.json"), encoding="utf-8"))["scenario_sets"]["yankee_queue_14"]["vessels"]
    if len(set(yank)) != 14 or not {"VSL-0012", "VSL-0031"} <= set(yank):
        fail("Yankee queue must list 14 vessels including VSL-0012 and VSL-0031")

    # ---------------- links
    for v in vs:
        if v["home_berth_id"] and v["home_berth_id"] not in bid:
            fail(f"{v['vessel_id']} home_berth_id {v['home_berth_id']} not found")
        for t in v["usual_berths"]:
            if t not in tid:
                fail(f"{v['vessel_id']} usual berth/terminal {t} not found")
        for g in v["sea_gates"]:
            if g not in gid:
                fail(f"{v['vessel_id']} sea gate {g} not found")
        if not v["home_berth_id"] and not v["home_port"]:
            fail(f"{v['vessel_id']} has neither home berth nor home port")
    bmap = {b["berth_id"]: b for b in T["berths"]}
    tmap = {t["terminal_id"]: t for t in T["terminals"]}
    for v in vs:      # a deep-draft ship must have at least one usual berth that fits it
        if v["deep_draft"]:
            fits = [b for t in v["usual_berths"] for b in tmap[t]["berth_ids"]
                    if bmap[b]["max_draft_m"] >= v["draft_m"] - 0.05 and bmap[b]["max_loa_m"] >= v["length_m"]]
            if not fits:
                fail(f"{v['vessel_id']} {v['vessel_name']} (LOA {v['length_m']}, draft {v['draft_m']}) fits none of its usual berths {v['usual_berths']}")
    for t in T["terminals"]:
        for b in t["berth_ids"]:
            if b not in bmap:
                fail(f"{t['terminal_id']} lists unknown berth {b}")
    for a in ac:
        if a["home_base"] and a["home_base"] not in fid:
            fail(f"{a['aircraft_id']} home_base {a['home_base']} not found")
        if a["parking_position_id"] not in pid:
            fail(f"{a['aircraft_id']} parking position {a['parking_position_id']} not found")
    for o in DR["authorized_operators"]:
        for s in o["launch_site_ids"]:
            if s not in sid:
                fail(f"{o['operator_id']} launch site {s} not found")

    # ---------------- geography: shared rules
    C = check_geo.Checker()
    rules = json.load(open(check_geo.RULES, encoding="utf-8"))["sources"]
    for rule in rules:
        if rule["name"] in ("Registry: berths", "Registry: anchorage points", "Registry: aircraft home pads"):
            o = C.run(rule)
            print(f"  check_geo {o['name']:<32} rows {o['rows']:>4}  violations {o['violations']}")
            if o["violations"] or not o["rows"]:
                fail(f"check_geo {o['name']}: {o['violations']} violations, {o['rows']} rows; {o['examples'][:3]}")
    # ---------------- geography: own checks
    for b in T["berths"]:
        p = (b["latitude"], b["longitude"])
        if G.is_land(*p):
            fail(f"{b['berth_id']} on land")
        if b["min_channel_depth_ft"] >= 40:
            if not G.channel_at(p[0], p[1], 150, 40):
                fail(f"{b['berth_id']} deep-draft berth is {G.channel_distance_m(p[0], p[1], 40):.0f} m from a 40 ft reach")
            i, d = G.nav.nearest(p, 40)
            if d > 350:
                fail(f"{b['berth_id']} is {d:.0f} m from the deep channel graph")
            r = G.nav.route((27.7927, -96.9636), p, 40)
            if not r:
                fail(f"{b['berth_id']} has no deep-draft route from the sea buoy")
    for s in T["slips"]:
        p = (s["latitude"], s["longitude"])
        if G.is_land(*p):
            fail(f"{s['slip_id']} on land")
            continue
        r = G.water.route(p, (27.77, -97.25), float(s.get("water_route_clearance_m") or 60.0))
        if r is None or G.path_land_hits(r):
            fail(f"{s['slip_id']} has no water route to Corpus Christi Bay")
        elif geo.dist_m(p, r[0]) > 450:
            fail(f"{s['slip_id']} water route starts {geo.dist_m(p, r[0]):.0f} m away")
    # a small craft moored at a slip or lay berth must also satisfy the AIS vessel rule in check_geo
    docks = C.docks
    for s in list(T["slips"]) + [b for b in T["berths"] if b["min_channel_depth_ft"] < 40]:
        p = (s["latitude"], s["longitude"])
        sid_ = s.get("slip_id") or s.get("berth_id")
        if G.land_clearance_m(*p) < 30 and not G.channel_at(p[0], p[1], 150) and C.near(docks, p[0], p[1]) > 200:
            fail(f"{sid_} would fail the AIS rule for a moored vessel (no water around it, not beside a channel or a real dock)")
    for a in T["anchorage_positions"]:
        p = (a["latitude"], a["longitude"])
        if not G.anchorages.contains(*p) or G.fairways.contains(*p) or G.is_land(*p):
            fail(f"{a['position_id']} not inside the NOAA anchorage / inside a fairway")
    pts = [(a["latitude"], a["longitude"]) for a in T["anchorage_positions"]]
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if geo.dist_m(pts[i], pts[j]) < 1500:
                fail(f"anchorage positions {i + 1} and {j + 1} closer than 1500 m")
    pb = T["pilot_boarding"]
    if G.is_land(pb["latitude"], pb["longitude"]):
        fail("pilot boarding area on land")
    prev = None
    for g in T["sea_gates"]:
        if G.is_land(g["latitude"], g["longitude"]):
            fail(f"{g['gate_id']} on land")
    off = next(g for g in T["sea_gates"] if g["gate_id"] == "GATE-OFFING")
    for g in T["sea_gates"]:
        if g["gate_id"] != "GATE-OFFING" and not G.segment_clear((off["latitude"], off["longitude"]), (g["latitude"], g["longitude"]), 1500.0):
            fail(f"leg GATE-OFFING to {g['gate_id']} crosses land")
    for p in A["parking_positions"]:
        if not G.in_box(p["latitude"], p["longitude"]):
            continue
        if not G.is_land(p["latitude"], p["longitude"]):
            fail(f"{p['position_id']} not on land")
        dr, _ = G.runway_distance_m(p["latitude"], p["longitude"])      # same test as check_geo "aircraft_ground"
        if dr > 500 and C.near(C.pads, p["latitude"], p["longitude"]) > 300:
            fail(f"{p['position_id']} is {dr:.0f} m from a runway: an aircraft parked there would fail the ADS-B ground rule")
    for s in DR["launch_sites"]:
        if G.in_box(s["latitude"], s["longitude"]) and not G.is_land(s["latitude"], s["longitude"]):
            fail(f"launch site {s['site_id']} not on land")

    # ---------------- hygiene
    for fn in ("vessels.json", "terminal_registry.json", "aircraft_registry.json", "drone_operators.json"):
        txt = open(os.path.join(D, fn), encoding="utf-8").read()
        for n in REAL_NAMES:
            if re.search(r"(?<![A-Za-z])" + re.escape(n) + r"(?![a-z])", txt):
                fail(f"{fn}: real or removed name '{n}'")
        for pat in TRUTH_WORDS:
            m = re.search(pat, txt, re.I if pat[0] != "\\" else 0)
            if m:
                fail(f"{fn}: truth wording '{m.group(0)}' near '{txt[max(0, m.start() - 40):m.end() + 40]!r}'")

    print(f"vessels {len(vs)}, berths {len(T['berths'])}, slips {len(T['slips'])}, anchorage positions {len(T['anchorage_positions'])}, "
          f"aircraft {len(ac)}, airfields {len(A['airfields'])}, parking {len(A['parking_positions'])}, drone operators {len(DR['authorized_operators'])}")
    print(f"\n{'PASS' if not fails else 'FAILED'}: {len(fails)} problem(s)")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
