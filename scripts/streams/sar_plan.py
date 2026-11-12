"""Search-and-rescue sortie plan for the hurricane response: the one schedule that the rescue
log (05_other_sources/sar/sar_missions.csv, sar_asset_log.csv) and the aircraft tracks share.

    from sar_plan import SORTIES, HELICOPTER_SORTIES

SORTIES is a list of dicts in launch order, one per sortie (engine start to shutdown for a
helicopter, launch to recovery for a boat, high-water vehicle or foot team). It is read from
sar_plan_data.json, which gen_ground.py writes; nothing here is random at import time.

Every sortie has
  sortie_id        mission id used in sar_missions.csv (SARM-27-NNNN)
  platform         helicopter | rescue_boat | swiftwater_team | civilian_boat | high_water_vehicle | welfare_check_team
  agency, asset_id asset_id is the registration for aircraft (CG-6033, CG-6041, N110TX, N3941A)
  takeoff_utc, landing_utc           launch and recovery (ISO, UTC)
  on_scene_start_utc, on_scene_end_utc   first arrival over a pickup and last departure from one
  persons, hoists  survivors recovered on the sortie; how many of them by hoist
  base             {name, airfield_id, position_id, lat, lon}; for aircraft the parking position in
                   aircraft_registry.json where the sortie starts and ends
  stops            ordered list; each stop has seq, kind, arrive_utc, depart_utc, lat, lon and
                     kind "search"   orbit over an area, nobody recovered (persons 0)
                     kind "pickup"   method HOIST (hover 40-80 ft over the address) or AIR-LANDING
                                     (touch-down on a street or lot beside the address; not an airfield,
                                     so a track should show a low hover there, not a ground report);
                                     persons, address, census_tract, case_numbers, incident_number
                     kind "dropoff"  survivors leave the aircraft with rotors turning at an airfield
                                     ramp position or a hospital helipad: facility_id, position_id, persons
                     kind "land"     return to the base parking position when the last drop-off was elsewhere
Helicopter sorties also carry aircraft_id, registration, icao24, callsign, type_designator and
cruise_speed_kt from aircraft_registry.json. A helicopter flies straight legs between stops; leg
times are distance at 85 percent of cruise speed plus 80 s for climb-out and approach. The last
stop of a helicopter sortie is at its base and its arrive_utc is landing_utc. Surface sorties list their
pickups only (arrive_utc on scene, delivered_to, delivered_utc).

Canon: first launch 06:22Z on 2027-09-14 (CG-6033, NAS Corpus Christi), first hoist 06:51Z in
Flour Bluff; 341 survivors by air and 180 hoists by 20:00Z on 2027-09-15; that day CG-6033 flies
seven sorties and CG-6041 six, with one state and one federal light helicopter after sunrise.
No rescue aircraft is airborne before 06:22Z on landfall day.
"""
import json
import math
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(_HERE, "sar_plan_data.json")


def load():
    if not os.path.exists(DATA):
        return []
    with open(DATA, encoding="utf-8") as f:
        return json.load(f)["sorties"]


SORTIES = load()
HELICOPTER_SORTIES = [s for s in SORTIES if s["platform"] == "helicopter"]

# ======================================================================================
# builder (called by gen_ground.Sar.build; needs the simulation, so not run at import)
# ======================================================================================
H = 3600
M_LAT = 110574.0
AIRCRAFT = {   # asset -> agency, base parking position, where survivors are put down at the air station, seats per lift, hoist share
    "CG-6033": {"agency": "USCG", "base": "PARK-NGP-T01", "drop": "PARK-NGP-T01", "cap": (5, 8), "per_stop": 4, "hoist": 0.62},
    "CG-6041": {"agency": "USCG", "base": "PARK-NGP-T02", "drop": "PARK-NGP-T02", "cap": (5, 8), "per_stop": 4, "hoist": 0.62},
    "N110TX": {"agency": "TXDPS", "base": "PARK-HELI-3TX0", "drop": "PARK-NGP-T04", "cap": (2, 3), "per_stop": 3, "hoist": 0.55},
    "N3941A": {"agency": "CBP", "base": "PARK-NGP-M02", "drop": "PARK-NGP-M02", "cap": (2, 3), "per_stop": 3, "hoist": 0.0},
}
HOSPITAL_PADS = {"FAC-SRMC-001": "PARK-HELI-5TS0", "FAC-BCMC-002": "PARK-HELI-71TT", "FAC-SCMH-012": "PARK-HELI-1XA3", "FAC-GCCH-014": "PARK-HELI-TE42"}
BASE_NAME = {"NGP": "NAS CORPUS CHRISTI", "PARK-HELI-3TX0": "HELIPORT 3TX0"}


def _dist(a, b):
    mlon = M_LAT * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * M_LAT, (a[1] - b[1]) * mlon)


def _bounded_split(total, n, lo, hi, rg):
    out = [lo] * n
    left = total - lo * n
    assert 0 <= left <= (hi - lo) * n, (total, n, lo, hi)
    while left:
        i = int(rg.integers(n))
        if out[i] < hi:
            out[i] += 1; left -= 1
    return out


def plan_air(sar, Z, reg):
    """Build every helicopter sortie. Returns mission dicts in the shape Sar.missions uses, with
    'stops', 'base' and 'aircraft' added. sar gives rg, tract(weights), sim.tracts pools."""
    rg, sim = sar.rg, sar.sim
    areg = reg("aircraft_registry")
    pos = {p["position_id"]: p for p in areg["parking_positions"]}
    acf = {a["registration"]: a for a in areg["aircraft"]}
    P = lambda pid: (pos[pid]["latitude"], pos[pid]["longitude"])
    pads = {fid: P(pid) for fid, pid in HOSPITAL_PADS.items()}
    FB = {"Flour Bluff Shore": .45, "Flour Bluff Central": .3, "Flour Bluff East": .25}
    D0W = {"Flour Bluff Shore": .35, "Flour Bluff Central": .2, "Flour Bluff East": .1, "North Beach": .25, "Rincon Point": .1}
    P1 = {"Flour Bluff Shore": .16, "Flour Bluff Central": .08, "Flour Bluff East": .06, "North Beach": .14, "Rincon Point": .06,
          "Mustang Island N": .08, "East Flats": .07, "Hillcrest": .1, "Port/Channel S": .06, "Port/Channel N": .04,
          "Bayfront Downtown": .1, "Padre Island NW": .05}
    # ---------------------------------------------------------------- pass 1: who is lifted where
    def near(pool, first, used):
        d = sorted(((_dist((p["lat"], p["lon"]), (first["lat"], first["lon"])), i) for i, p in enumerate(pool) if i not in used))
        cand = [i for dist, i in d[1:14] if dist < 900] or [d[min(1, len(d) - 1)][1]]
        return cand[int(rg.integers(len(cand)))]

    def make(asset, day, nominal, persons, weights, storm):
        a = AIRCRAFT[asset]
        lo, hi = a["cap"]
        n_cyc = max(1, int(math.ceil(persons / rg.uniform(lo + 0.6, hi))))
        loads = _bounded_split(persons, n_cyc, 1, hi, rg) if persons >= n_cyc else [persons]
        loads = [x for x in loads if x]
        cycles = []
        for load in loads:
            tr = sar.tract(weights)
            pool = sim.tracts[tr]["pool"]
            sizes, left = [], load
            while left:
                k = min(left, int(rg.integers(1, a["per_stop"] + 1)))
                sizes.append(k); left -= k
            used, evs, first = set(), [], None
            for k in sizes:
                i = int(rg.integers(len(pool))) if first is None else near(pool, first, used)
                used.add(i)
                first = first or pool[i]
                evs.append({"tract": tr, "loc": pool[i], "persons": k, "method": "HOIST" if rg.random() < a["hoist"] else "AIR-LANDING"})
            medical = rg.random() < (0.13 if load <= 4 else 0.05)
            if medical:
                fid = min(pads, key=lambda f: _dist(pads[f], (evs[-1]["loc"]["lat"], evs[-1]["loc"]["lon"])))
                dest = (fid, HOSPITAL_PADS[fid])
            else:
                dest = ("FAC-DOD-01", a["drop"])
            cycles.append({"events": evs, "dest": dest})
        return {"asset": asset, "day": day, "nominal": nominal, "persons": persons, "cycles": cycles, "storm": storm}

    plan = []
    d0 = {"CG-6033": [("06:22", 3, FB), ("09:37", 5, D0W), ("13:14", 7, D0W), ("16:43", 7, D0W), ("20:26", 6, D0W)],
          "CG-6041": [("07:08", 3, D0W), ("10:52", 6, D0W), ("14:27", 7, D0W), ("18:21", 6, D0W)]}
    for asset, lst in d0.items():
        for hm, n, w in lst:
            plan.append(make(asset, 0, Z(0, hm), n, w, True))
    d1 = {"CG-6033": ("05:06", 7, 130, 13, 24), "CG-6041": ("05:31", 6, 112, 13, 24), "N110TX": ("12:26", 4, 30, 5, 10), "N3941A": ("12:41", 3, 19, 5, 8)}
    for asset, (hm, n, total, lo, hi) in d1.items():
        for k, persons in enumerate(_bounded_split(total, n, lo, hi, rg)):
            plan.append(make(asset, 1, Z(1, hm) if k == 0 else None, persons, P1, False))
    # the first rescue of the storm (canon): a hoist on Flour Bluff Drive at 06:51Z
    first = plan[0]
    f_ev = first["cycles"][0]["events"][0]
    fb_dr = [p for nm in FB for p in sim.tracts[sim.tract_by_name[nm]]["pool"] if p["street"] == "Flour Bluff Dr"]
    if fb_dr:
        f_ev["loc"] = dict(fb_dr[0], number=4418)
        f_ev["tract"] = sim.tract_of(f_ev["loc"]["lat"], f_ev["loc"]["lon"]) or f_ev["tract"]
    first["cycles"][0]["dest"] = ("FAC-DOD-01", AIRCRAFT["CG-6033"]["drop"])
    # ---------------------------------------------------------------- pass 2: exactly 180 persons hoisted (canon)
    evs = [e for s in plan for c in s["cycles"] for e in c["events"]]
    f_ev["method"] = "HOIST"
    can_hoist = [e for s in plan if AIRCRAFT[s["asset"]]["hoist"] > 0 for c in s["cycles"] for e in c["events"] if e is not f_ev]
    for _ in range(4000):
        diff = 180 - sum(e["persons"] for e in evs if e["method"] == "HOIST")
        if diff == 0:
            break
        want = "AIR-LANDING" if diff > 0 else "HOIST"
        cand = [e for e in can_hoist if e["method"] == want and e["persons"] <= abs(diff)]
        if not cand:
            cand = [e for e in can_hoist if e["method"] != want and e["persons"] == 1]     # step back by one, then retry
            want = "HOIST" if want == "AIR-LANDING" else "AIR-LANDING"
        e = cand[int(rg.integers(len(cand)))]
        e["method"] = "HOIST" if want == "AIR-LANDING" else "AIR-LANDING"
    assert sum(e["persons"] for e in evs if e["method"] == "HOIST") == 180
    # ---------------------------------------------------------------- pass 3: times from geometry
    def timeline(s):
        """Offsets in seconds from take-off: list of stops, landing offset, last pickup departure."""
        a = AIRCRAFT[s["asset"]]
        v = acf[s["asset"]]["cruise_speed_kt"] * 0.5144 * 0.85
        cur = P(a["base"])
        t = 0.0
        stops = []
        last_pick = 0.0
        if s is first:           # looks for the first caller in the dark before the hoist on Flour Bluff Drive
            pool = sim.tracts[sim.tract_by_name["Flour Bluff Shore"]]["pool"]
            p = pool[int(rg.integers(len(pool)))]
            q = (f_ev["loc"]["lat"], f_ev["loc"]["lon"])
            arr = _dist(cur, (p["lat"], p["lon"])) / v + 80
            dep = (Z(0, "06:51") - s["nominal"]) - (_dist((p["lat"], p["lon"]), q) / v + 80)
            stops.append({"kind": "search", "arrive": arr, "depart": dep, "lat": p["lat"], "lon": p["lon"], "persons": 0})
            cur, t = (p["lat"], p["lon"]), dep
        for c in s["cycles"]:
            for e in c["events"]:
                q = (e["loc"]["lat"], e["loc"]["lon"])
                t += _dist(cur, q) / v + 80
                if s is first and e is f_ev:
                    t = float(Z(0, "06:51") - s["nominal"])
                locate = rg.uniform(240, 800) if s["storm"] else rg.uniform(45, 230)
                if e["method"] == "HOIST":
                    work = 110 + sum(rg.uniform(80, 125) for _ in range(e["persons"]))
                else:
                    work = 140 + 35 * e["persons"] + rg.uniform(0, 90)
                e["_arr"], e["_dep"] = t, t + locate + work
                stops.append({"kind": "pickup", "arrive": t, "depart": e["_dep"], "lat": q[0], "lon": q[1], "persons": e["persons"], "event": e})
                t = e["_dep"]; cur = q; last_pick = t
            fid, pid = c["dest"]
            q = P(pid)
            t += _dist(cur, q) / v + 80
            n = sum(e["persons"] for e in c["events"])
            off = (230 + 28 * n if fid != "FAC-DOD-01" else 140 + 18 * n) + rg.uniform(0, 110)
            for e in c["events"]:
                e["delivered"], e["_deliv"] = fid, t + rg.uniform(50, 60 + 15 * n)
            stops.append({"kind": "dropoff", "arrive": t, "depart": t + off, "lat": q[0], "lon": q[1], "persons": n, "facility_id": fid, "position_id": pid})
            t += off; cur = q
        base = P(a["base"])
        if _dist(cur, base) > 30:
            t += _dist(cur, base) / v + 80
            stops.append({"kind": "land", "arrive": t, "depart": t, "lat": base[0], "lon": base[1], "persons": 0, "position_id": a["base"]})
        else:
            t = stops[-1]["arrive"]
            stops[-1]["depart"] = t
        return stops, t, last_pick

    missions = []
    by_asset = {}
    for s in plan:
        s["stops"], s["dur"], s["last_pick"] = timeline(s)
        by_asset.setdefault((s["asset"], s["day"]), []).append(s)
    deadline = Z(1, "19:54")
    for (asset, day), lst in by_asset.items():
        if day == 0:
            for s in lst:
                s["t0"] = s["nominal"]
            for a, b in zip(lst, lst[1:]):
                assert b["t0"] > a["t0"] + a["dur"] + 600, (asset, "overlap on landfall day")
            continue
        t0 = lst[0]["nominal"]
        n = len(lst)
        slack = deadline - t0 - sum(s["dur"] for s in lst[:-1]) - lst[-1]["last_pick"]
        min_gap = 11 * 60
        assert slack >= (n - 1) * min_gap, (asset, "sorties do not fit before 20:00Z", slack / 60)
        spare = min(slack - (n - 1) * min_gap, (n - 1) * 26 * 60) * rg.uniform(0.75, 0.97)
        w = rg.dirichlet([2.0] * (n - 1))
        t = t0
        for i, s in enumerate(lst):
            s["t0"] = int(t)
            if i < n - 1:
                t = s["t0"] + s["dur"] + min_gap + spare * w[i] + rg.uniform(0, 45)
    for s in plan:
        a = AIRCRAFT[s["asset"]]
        t0 = s["t0"]
        events = []
        for st in s["stops"]:
            st["arrive"], st["depart"] = int(round(t0 + st["arrive"])), int(round(t0 + st["depart"]))
            e = st.pop("event", None)
            if e is not None:
                e["t"], e["depart"], e["deliv_t"] = st["arrive"], st["depart"], int(round(t0 + e["_deliv"]))
                st["method"] = e["method"]
                st["_event"] = e
                events.append(e)
        if s is first:
            f_ev["persons_note"] = "first"
        b = pos[a["base"]]
        base = {"name": BASE_NAME.get(b.get("airfield_id") or a["base"], a["base"]), "airfield_id": b.get("airfield_id"), "position_id": a["base"],
                "lat": b["latitude"], "lon": b["longitude"]}
        missions.append({"agency": a["agency"], "asset": s["asset"], "type": "helicopter", "element": "", "launch": int(t0),
                         "recovery": int(round(t0 + s["dur"])), "events": events, "stops": s["stops"], "base": base, "aircraft": acf[s["asset"]]})
    return missions


def export(missions, units, tracts, fac_name, iso, address, path=DATA):
    """Write sar_plan_data.json from the final mission list (ids, case numbers and incident numbers set)."""
    out = []
    for m in missions:
        ev = m["events"]
        s = {"sortie_id": m["id"], "platform": m["type"], "agency": m["agency"], "asset_id": m["asset"], "crew_element": m["element"],
             "takeoff_utc": iso(m["launch"]), "landing_utc": iso(m["recovery"]),
             "on_scene_start_utc": iso(min(e["t"] for e in ev)), "on_scene_end_utc": iso(max(e.get("depart", e["t"]) for e in ev)),
             "persons": sum(e["persons"] for e in ev), "hoists": sum(e["persons"] for e in ev if e["method"] == "HOIST")}
        def pick(e, seq):
            return {"seq": seq, "kind": "pickup", "method": e["method"], "arrive_utc": iso(e["t"]), "depart_utc": iso(e.get("depart", e["t"])),
                    "lat": round(e["loc"]["lat"], 6), "lon": round(e["loc"]["lon"], 6), "persons": e["persons"], "address": address(e["loc"]),
                    "census_tract": tracts[e["tract"]]["tract"], "case_numbers": e["cases"], "incident_number": e["inc"].get("_no", ""),
                    "delivered_to": e["delivered"], "delivered_utc": iso(e["deliv_t"])}
        if m["type"] == "helicopter":
            a = m["aircraft"]
            s.update({"aircraft_id": a["aircraft_id"], "registration": a["registration"], "icao24": a["icao24"], "callsign": a["callsign"],
                      "type_designator": a["type_designator"], "cruise_speed_kt": a["cruise_speed_kt"], "base": m["base"]})
            stops = []
            for i, st in enumerate(m["stops"]):
                if st["kind"] == "pickup":
                    stops.append(pick(st["_event"], i + 1))
                else:
                    x = {"seq": i + 1, "kind": st["kind"], "arrive_utc": iso(st["arrive"]), "depart_utc": iso(st["depart"]),
                         "lat": round(st["lat"], 6), "lon": round(st["lon"], 6), "persons": st["persons"]}
                    if st["kind"] == "dropoff":
                        x.update({"facility_id": st["facility_id"], "facility_name": fac_name.get(st["facility_id"], ""), "position_id": st["position_id"]})
                    elif st["kind"] == "land":
                        x["position_id"] = st["position_id"]
                    stops.append(x)
            s["stops"] = stops
        else:
            u = units.get(m["asset"])
            s["base"] = ({"name": u["station"], "airfield_id": None, "position_id": None, "lat": round(u["home"]["lat"], 6), "lon": round(u["home"]["lon"], 6)}
                         if u else None)
            s["stops"] = [pick(e, i + 1) for i, e in enumerate(sorted(ev, key=lambda e: e["t"]))]
        out.append(s)
    out.sort(key=lambda s: (s["takeoff_utc"], s["sortie_id"]))
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_about": "Search-and-rescue sortie plan; written by scripts/streams/gen_ground.py, read through scripts/streams/sar_plan.py",
                   "sorties": out}, f, indent=1)
    return len(out)
