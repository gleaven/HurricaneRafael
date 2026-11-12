"""Registry entries that the stream generators needed and the registries did not have, plus
'reference_only' marks for registry entries no delivered stream uses.

Idempotent. Run after the build_registr*.py scripts and after the streams exist:

    python3 scripts/apply_registry_additions.py            add missing entries
    python3 scripts/apply_registry_additions.py --mark     also mark unused entries reference_only
                                                           (reads 07_validation/reports/entity_usage.json,
                                                            written by check_entities.py --usage)
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REG = os.path.join(ROOT, "06_data_streams")
SRC = os.path.join(ROOT, "05_other_sources")
sys.path.insert(0, HERE)
log = []


def load(name):
    with open(os.path.join(REG, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def save(name, obj):
    with open(os.path.join(REG, name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def add_records(lst, key, recs, label):
    have = {r.get(key) for r in lst}
    n = 0
    for r in recs:
        if r[key] not in have:
            lst.append(r)
            have.add(r[key])
            n += 1
    if n:
        log.append(f"{label}: +{n}")
    return n


def sensors():
    import geo
    G = geo.Geo(build_roads=False)
    s = load("sensor_registry")
    port = []
    with open(os.path.join(SRC, "port_surveillance", "sensors.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            lat = float(r["latitude"]) if r["latitude"] else None
            lon = float(r["longitude"]) if r["longitude"] else None
            water = r["sensor_type"] == "radar buoy"
            if lat is not None:
                assert G.is_land(lat, lon) != water, f"{r['sensor_id']} is on the wrong side of the shoreline"
            port.append({"sensor_id": r["sensor_id"], "sensor_name": r["name"], "sensor_type": r["sensor_type"], "operator": "Port of Corpus Christi Authority / Coast Guard Sector Corpus Christi",
                         "latitude": lat, "longitude": lon, "range_nm": float(r["range_nm"]) if r["range_nm"] else None, "berths_in_view": [b for b in r["berths_in_view"].split(";") if b],
                         "position_basis": ("in water (scripts/geo.py)" if water else "on land beside the channel (scripts/geo.py)") if lat is not None else "a log kept at the vessel traffic centre; no position", "stream": "port_surveillance"})
    add = json.load(open(os.path.join(REG, "_internal", "registry_additions_aviation.json"), encoding="utf-8"))["drone_detection_sensors"]
    det = []
    for r in add:
        lat = float(r["latitude"]) if r.get("latitude") not in (None, "") else None
        lon = float(r["longitude"]) if r.get("longitude") not in (None, "") else None
        water = "radar buoy" in r["name"].lower() or "surface-search radar" in r["sensor_type"].lower()
        if lat is not None and G.in_box(lat, lon):
            assert G.is_land(lat, lon) != water, f"{r['sensor_id']} is on the wrong side of the shoreline"
        det.append(dict(r, sensor_name=r["name"], operator=r.get("owner"), position_basis="in water (scripts/geo.py)" if water else "on land (scripts/geo.py)", stream="drone_detections"))
    n = add_records(s.setdefault("port_surveillance_sensors", []), "sensor_id", port, "sensor_registry.port_surveillance_sensors")
    n += add_records(s.setdefault("drone_detection_sensors", []), "sensor_id", det, "sensor_registry.drone_detection_sensors")
    if n:
        save("sensor_registry", s)
    rules = {"sources": [
        {"name": "Registry: port radar buoys", "glob": "06_data_streams/sensor_registry.json", "items": "port_surveillance_sensors", "lat": "latitude", "lon": "longitude", "rule": "water_fixed", "id": "sensor_id", "where": ["sensor_type", "radar buoy"]},
        {"name": "Registry: port cameras and VTS", "glob": "06_data_streams/sensor_registry.json", "items": "port_surveillance_sensors", "lat": "latitude", "lon": "longitude", "rule": "land_fixed", "id": "sensor_id", "allow_missing": True, "where": ["sensor_type", sorted({r["sensor_type"] for r in port if r["sensor_type"] != "radar buoy"})]},
        {"name": "Registry: drone-detection radar buoys", "glob": "06_data_streams/sensor_registry.json", "items": "drone_detection_sensors", "lat": "latitude", "lon": "longitude", "rule": "water_fixed", "id": "sensor_id", "allow_missing": True, "where": ["sensor_type", "X-band surface-search radar, raw plot archive"]},
    ]}
    with open(os.path.join(ROOT, "99_reference", "geo", "position_rules.d", "registry_additions.json"), "w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=1)


def cad():
    c = load("cad_units")
    n = add_records(c["nature_codes"], "code", [{"code": "WATERSAFE", "description": "WATER SAFETY INQUIRY", "default_priority": "P4", "agency": ["CCPD"]}], "cad_units.nature_codes")
    for k, v in (("USCG", "U.S. Coast Guard Sector / Air Station Corpus Christi"), ("TXDPS", "Texas Department of Public Safety, Aircraft Operations"), ("CBP", "U.S. Customs and Border Protection, Air and Marine Operations"),
                 ("TXARNG", "Texas Army National Guard"), ("NCOEM", "Nueces County Office of Emergency Management"), ("FEMA", "FEMA Region 6 field operations"), ("CIVBOAT", "Registered volunteer boats"),
                 ("CBPWA", "Coastal Bend Power and Water Authority field crews"), ("NCPW", "Nueces County Public Works and debris contractors")):
        if k not in c["agencies"]:
            c["agencies"][k] = {"name": v, "dispatch_channel": "NuecesNet interop", "unit_count": sum(1 for u in c["units"] if u.get("agency") == k), "partner_agency": True}
            n += 1
    extra = []
    for i in range(1, 7):
        extra.append({"unit_id": f"RLF-{i}", "agency": "NCOEM", "type": "relief truck", "home_station": "STG-FAIR", "description": f"Relief supply truck {i} (water and ice distribution)", "vehicle": "Box truck",
                      "staffing": 2, "avl_equipped": False})
    for i in range(1, 9):
        extra.append({"unit_id": f"DBR-{i}", "agency": "NCPW", "type": "debris hauler", "home_station": "STG-FAIR", "description": f"Debris haul truck {i} (county debris contract)", "vehicle": "Knuckle-boom loader",
                      "staffing": 2, "avl_equipped": False})
    for i in range(1, 9):
        extra.append({"unit_id": f"UTL-{i}", "agency": "CBPWA", "type": "utility crew", "home_station": "STG-FAIR", "description": f"Line and water crew {i}", "vehicle": "Bucket truck" if i <= 5 else "Service truck",
                      "staffing": 3, "avl_equipped": False})
    for u in extra:
        u["reference_only"] = True
        u["reference_reason"] = "no vehicle-location feed for this fleet; appears in work orders and stories as crews, not as tracked units"
    n += add_records(c["units"], "unit_id", extra, "cad_units.units")
    if n:
        for k in c["agencies"]:
            c["agencies"][k]["unit_count"] = sum(1 for u in c["units"] if u.get("agency") == k)
        save("cad_units", c)
        log.append("cad_units: nature code, partner agencies, non-tracked fleets")


def terminals():
    t = load("terminal_registry")
    segs = {}
    with open(os.path.join(SRC, "supply", "port_conditions.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["segment_id"]:
                segs[r["segment_id"]] = r["segment_name"]
    reach = {"SEG-ENT": ["CESWG_CC_01_SBC_1", "CESWG_CC_02_JEC_2", "CESWG_CC_03_IMC_3", "CESWG_CC_04_IHI_4"], "SEG-BAY": ["CESWG_CC_05_HLQ_5", "CESWG_CC_06_LQB_6", "CESWG_CC_07_BTB_7"],
             "SEG-LAQ": ["CESWG_LA_01_CLQ_1", "CESWG_LA_02_LTB_2", "CESWG_LA_03_LEX_3"], "SEG-INNER-E": ["CESWG_CC_08_MTB_8"],
             "SEG-INNER-W": ["CESWG_CC_09_INC_9", "CESWG_CC_10_ATB_10", "CESWG_CC_11_CTB_11", "CESWG_CC_12_TLC_12", "CESWG_CC_13_TTB_13", "CESWG_CC_14_VCH_14", "CESWG_CC_15_VTB_15"],
             "SEG-GIWW": ["CESWG_GI_1A_ABL_21", "CESWG_GI_1B_LCC_21", "CESWG_GI_21_ACC_21", "CESWG_GI_22_CCM_22"], "SEG-ANCH": []}
    n = add_records(t.setdefault("channel_segments", []), "segment_id",
                    [{"segment_id": k, "segment_name": v, "usace_reach_ids": reach.get(k, []), "geometry": "99_reference/geo/channels_usace.geojson" if reach.get(k) else "99_reference/geo/anchorages_fairways_noaa.geojson"}
                     for k, v in sorted(segs.items())], "terminal_registry.channel_segments")
    for b in t["berths"]:
        if b["berth_id"] in ("TERM-13-B01", "TERM-15-B01") and not b.get("lay_berth"):
            b["lay_berth"] = True
            b["lay_berth_note"] = "also used as a lay berth for vessels held in port"
            n += 1
    if n:
        save("terminal_registry", t)
        log.append("terminal_registry: channel segments, lay-berth flags")


def organizations():
    o = load("organizations")
    orgs = o["organizations"]
    nxt = max(int(x["org_id"].split("-")[1]) for x in orgs) + 1
    names = {x["name"] for x in orgs}
    new = []
    for nm, typ, role in (("Lone Star Vessel Agency", "ship agent", "Files notices of arrival and arranges pilots, tugs and berths for calling ships"),
                          ("Gulf Coast Marine Agency", "ship agent", "Files notices of arrival and arranges pilots, tugs and berths for calling ships"),
                          ("Coastal Bend Ship Agency", "ship agent", "Files notices of arrival and arranges pilots, tugs and berths for calling ships"),
                          ("Aransas Maritime Agents", "ship agent", "Files notices of arrival and arranges pilots, tugs and berths for calling ships"),
                          ("Tidewater Bulk Fuels", "fuel supplier", "Regular bulk fuel supplier to Naval Air Station Corpus Christi; its depot flooded in the storm"),
                          ("WKCB-AM", "broadcast relay station", "Emergency Alert System relay station for the Corpus Christi market")):
        if nm not in names:
            rec = {"org_id": f"ORG-{nxt}", "name": nm, "type": typ, "parent": None, "jurisdiction": "Coastal Bend", "public_role": role, "abbr": None, "parent_name": None}
            if nm == "Tidewater Bulk Fuels":
                rec["reference_only"] = True
                rec["reference_reason"] = "named as background (the supplier that flooded); makes no deliveries in the data"
            new.append(rec)
            nxt += 1
    n = add_records(orgs, "org_id", new, "organizations")
    outlets = json.load(open(os.path.join(ROOT, "01_characters", "outlets.json"), encoding="utf-8"))["outlets"]
    by_name = {x["name"]: x["org_id"] for x in orgs}
    st = [{"station_id": x["outlet_id"], "name": x["name"], "kind": x["type"], "org_id": by_name.get(x["name"])} for x in outlets]
    st.append({"station_id": "WKCB-AM", "name": "WKCB-AM relay station", "kind": "Emergency Alert System relay station", "org_id": by_name.get("WKCB-AM") or next((r["org_id"] for r in new if r["name"] == "WKCB-AM"), None)})
    n += add_records(o.setdefault("broadcast_stations", []), "station_id", st, "organizations.broadcast_stations")
    if n:
        save("organizations", o)


def hosts_and_assets():
    h = load("gw_host_registry")
    n = add_records(h["equipment"], "equipment_id",
                    [{"equipment_id": "GW-SUB02-CB-7", "label": "CB-7", "type": "feeder circuit breaker", "site_id": "GW-FAC-SUB-02", "served_by": "GW-SYS-RTU-02"},
                     {"equipment_id": "GW-SUB03-CB-12", "label": "CB-12", "type": "feeder circuit breaker", "site_id": "GW-FAC-SUB-03", "served_by": "GW-SYS-RTU-03"}], "gw_host_registry.equipment")
    if n:
        save("gw_host_registry", h)
    a = load("infrastructure_assets")
    n = add_records(a.setdefault("maintenance_sites", []), "site_id",
                    [{"site_id": "CBPWA-CC", "name": "Coastal Bend Power and Water Authority, Corpus Christi (work-order site code)", "org": "Coastal Bend Power and Water Authority"},
                     {"site_id": "CCAD", "name": "Corpus Christi Army Depot (work-order site code)", "org": "U.S. Army"},
                     {"site_id": "NASCC", "name": "Naval Air Station Corpus Christi (work-order site code)", "org": "U.S. Navy"}], "infrastructure_assets.maintenance_sites")
    if n:
        save("infrastructure_assets", a)


def aircraft():
    a = load("aircraft_registry")
    n = 0
    for x in a["aircraft"]:
        cs = x.get("callsign") or ""
        if len(cs) > 8:
            x["callsign_voice"] = cs
            x["callsign"] = cs[:6] + cs[-2:]
            n += 1
    if n:
        a.setdefault("metadata", {})["callsign_note"] = "callsign is what the transponder sends (eight characters at most); callsign_voice is the radio call sign where it is longer"
        save("aircraft_registry", a)
        log.append(f"aircraft_registry: {n} call signs shortened to the eight characters ADS-B carries")


REASONS = {"vessels": "in the port's register but makes no call and sends no position inside the scenario window",
           "aircraft": "based in the area but flies no tracked sortie in the scenario window", "units": "not AVL-equipped or not dispatched in the data window",
           "hosts": "ordinary host with no alert, session or audit record in the sampled logs", "users": "staff account with no remote session or alert in the logs",
           "service_accounts": "service account with no audited session in the logs", "tags": "catalogued point that is not archived by the historian",
           "policies": "policy in force with no transaction or claim in the sampled period", "policyholders": "policyholder with no claim in the sample",
           "organizations": "named in registries or stories; has no record of its own in the data streams", "personas": "account that exists but does not post in the window",
           "areas": "geographic reference used for joins; no stream keys on this id", "default": "reference entry; no record in the delivered streams"}


def mark():
    up = os.path.join(ROOT, "07_validation", "reports", "entity_usage.json")
    used = {tuple(x[:3]) for x in json.load(open(up, encoding="utf-8"))["used"]}
    import check_entities as CE
    _, lists = CE.registry_classes()
    by_file = {}
    for file, key, field, recs, cls in lists:
        by_file.setdefault(file, []).append((key, field))
    total = 0
    for file, keys in by_file.items():
        d = load(file)
        changed = 0
        for key, field in keys:
            recs = d.get(key)
            if not isinstance(recs, list):
                continue
            for r in recs:
                rid = str(r.get(field))
                if (file, key, rid) in used:
                    if r.get("reference_only") and r.get("reference_reason", "").startswith(tuple(REASONS.values())):
                        del r["reference_only"], r["reference_reason"]
                        changed += 1
                elif not r.get("reference_only"):
                    r["reference_only"] = True
                    r["reference_reason"] = REASONS.get(key, REASONS["default"])
                    changed += 1
        if changed:
            save(file, d)
            total += changed
            log.append(f"{file}: {changed} reference_only marks updated")
    return total


if __name__ == "__main__":
    sensors(); cad(); terminals(); organizations(); hosts_and_assets(); aircraft()
    if "--mark" in sys.argv:
        mark()
    print("\n".join(log) if log else "nothing to add")
