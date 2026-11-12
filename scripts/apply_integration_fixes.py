"""Canon corrections found when the data streams were generated (2026-11-09 integration pass).

Idempotent: running it again changes nothing. It edits the MSEL, the canon timeline, the public
record, a few stories and the thread-design copies, then regenerates expected_observations.

    python3 scripts/apply_integration_fixes.py
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
changes = []


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def save(rel, obj):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)


def text_sub(rel, pairs, label):
    p = os.path.join(ROOT, rel)
    s = open(p, encoding="utf-8").read()
    n = 0
    for a, b in pairs:
        if a in s and a != b:
            n += s.count(a)
            s = s.replace(a, b)
    if n:
        open(p, "w", encoding="utf-8").write(s)
        changes.append(f"{label}: {n} replacement(s) in {rel}")
    return n


# mission and report names: no scenario-day numbers (calendar month-day instead)
MISSION = [("FEMA-UAV-D2-", "FEMA-UAV-0916-"), ("FEMA-UAV-D3-", "FEMA-UAV-0917-"), ("FEMA-UAV-D8-", "FEMA-UAV-0922-"), ("FEMA-UAV-D15-", "FEMA-UAV-0929-"),
           ("CBAS-TIR-D11", "CBAS-TIR-0925"), ("FEMA-TIR-D11-UTL", "FEMA-TIR-0925-UTL")]
PHRASES = MISSION + [
    ("State Farm's Special Investigations Unit", "Sabine National Insurance's Special Investigations Unit"),
    ("State Farm SIU", "Sabine National Insurance SIU"), ("State Farm", "Sabine National Insurance"),
    ("11 authenticated sessions under GW-ENG-VELA", "7 authenticated sessions under GW-ENG-VELA"),
    ("between D-7 and D-4, total 4.1 GB outbound", "between D-7 and D-4 (14 in all by D+18), total 4.1 GB outbound"),
    ("has a modification timestamp of D-3 17:11Z", "has a modification timestamp of D-3 22:11Z (17:11 local)"),
    ("last_modified = 2027-09-11T17:11Z", "last_modified = 2027-09-11T22:11:26Z (17:11 local)"),
    ("The sonde nearest the berth (WQ-01, Inner Harbor)", "The sonde nearest the berth (WQ-02, Inner Harbor)"),
    ("Water-quality sonde nearest the berth (WQ-01, Inner Harbor)", "Water-quality sonde nearest the berth (WQ-02, Inner Harbor)"),
    ("Total generator runtime: 195h 03m", "Generator run-hours meter: 195h 03m over about 200 hours on backup power"),
    ("Generator total runtime: 195h 03m", "Generator run-hours meter: 195h 03m (about 200 hours elapsed on backup power)"),
    ("generator runtime (195h)", "generator run-hours (195 h on the meter over about 200 hours on backup power)"),
    ("CBECC handled 44,291 calls over D0 through D+28", "CBECC handled 44,291 calls on all lines (911 and ten-digit) over D0 through D+28"),
    ("volume summary: total 44,291 calls.", "volume summary: total 44,291 calls on all lines (911 and ten-digit)."),
    ("corpus summary: 56,793 total calls;", "corpus summary: 56,793 total calls on all lines (911 and ten-digit);"),
    ("the aid portal (HOST-PORTAL-01) and the NAS logistics system (HOST-DOD-LOG-02)", "the aid portal (EXT-AIDPORTAL-01) and the NAS logistics system (EXT-NASLOG-02)"),
    ("At GW-FAC-SUB-03 (Crosstown), main feeder breaker B3-B is also in open-contact position.",
     "At GW-FAC-SUB-03 (Crosstown) every main feeder breaker is still closed on this pass; B3-B is first seen open on the thermal survey after the D+10 command."),
    ("SUB-02 and SUB-03 circuits are still listed as storm outages on D+8.", "SUB-02 circuits are still listed as storm outages on D+8 (SUB-03 circuits from D+10)."),
    ("Coastal Bend Public Works Authority", "Coastal Bend Power and Water Authority"),
]
# old scenario ids in observation text -> registry ids
OBS_IDS = [("SUP-0390", "ORG-1121"), ("SUP-0388", "ORG-1123"), ("SUP-0219", "ORG-1106"), ("consignee SUP-0102 (Gulf Relief Logistics)", "consignee VND-0006 / ORG-1118 (Gulf Relief Logistics)"),
           ("BANK-SYN-71", "ACCT-40134"), ("FAC-UTL-01-RAW-TPH-MGL", "GW.UTL1.RAW.TPH.PV"), ("ZONE4-DIST-PSI", "GW.DIST.ZONE4.PRESS.PV"),
           ("FAC-UTL-01-PUMP-SP-RPM", "GW.UTL1.PUMP3.SPEED.SP"), ("FAC-UTL-01-P3-SET-PSI", "GW.UTL1.PUMP3.PRESS.SP"), ("GW-FAC-WTR-03-BSTR-SET-PSI", "GW.WTR3.STATION.PRESS.SP"),
           ("PIID-SYN-0075", "N6883627C0075"), ("PIID-SYN-0071", "NC-EM-2027-0071"), ("Ingleside Marina Berth 7", "SLIP-ING-07")]


def local_label(utc_iso):
    t = dt.datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    off = -5 if t < dt.datetime(2027, 11, 7, 7, tzinfo=dt.timezone.utc) else -6
    l = t + dt.timedelta(hours=off)
    day = (l.date() - dt.date(2027, 9, 14)).days
    return {"utc": utc_iso, "local": l.strftime("%Y-%m-%dT%H:%M") + f"{off:+03d}:00", "day": day,
            "label": f"D{'+' if day > 0 else ('-' if day < 0 else '')}{abs(day) if day else '0'} {l:%H:%M} {'CDT' if off == -5 else 'CST'}"}


def fix_msel():
    m = load("00_scenario/msel.json")
    n = 0
    for e in m:
        eid = e["event_id"]
        if eid == "GW-EVT-001" and e["day"] != -15:
            e["day"], e["time_label"] = -15, "D-15"
            for o in e["observed_in"]:
                o["when"] = {"start_utc": "2027-08-30T05:00Z", "end_utc": "2027-08-31T05:00Z"}
                o["what"] = o["what"].replace("at 08:14 CDT", "at 08:14 CDT on 2027-08-30 (13:14Z)").replace("at 08:21 CDT", "at 08:21 CDT (13:21Z)").replace("at 08:23 CDT", "at 08:23 CDT on 2027-08-30 (13:23Z)")
            e["timing_note"] = "The lure is delivered the morning before the first outbound connection (2027-08-31T03:17Z, GW-EVT-101)."
            n += 1
        if eid == "EVT-2102" and e.get("time_utc") == "18:00Z":
            e["time_utc"] = "17:00Z"
            s = json.dumps(e, ensure_ascii=False)
            for a, b in (("18:00Z", "17:00Z"), ("18:03Z", "17:03Z"), ("18:04Z", "17:04Z"), ("18:06Z", "17:06Z"), ("18:08Z", "17:08Z"), ("T18:00Z", "T17:00Z"), ("T20:00Z", "T19:00Z")):
                s = s.replace(a, b)
            e.clear(); e.update(json.loads(s))
            n += 1
        if eid == "EVT-1404":
            for o in e["observed_in"]:
                if o["stream"] == "broadcast_logs" and "web stream" not in o["what"]:
                    o["what"] = o["what"].rstrip(".") + " (carried on the station's web stream and relay: the AM transmitter is off the air from 03:31 local on D0 to 02:00 local on D+1)."
                    n += 1
        for o in e.get("observed_in", []):
            w = o["what"]
            for a, b in OBS_IDS:
                if a in w:
                    w = w.replace(a, b)
            if w != o["what"]:
                o["what"] = w
                n += 1
    if n:
        save("00_scenario/msel.json", m)
        changes.append(f"MSEL structured edits: {n}")


def fix_timeline():
    t = load("00_scenario/canon_timeline.json")
    n = 0
    want = {"Relay undervoltage threshold at SUB-01": "2027-09-11T17:04Z", "SUB-02 breaker-open command": "2027-09-21T14:28Z",
            "Pump P-3 discharge setpoint lowered": "2027-09-23T02:04Z", "SUB-03 breaker-open command": "2027-09-24T19:43Z"}
    for ev in t["utility_cyber"]["events"]:
        for k, u in want.items():
            if ev["what"].startswith(k) and ev["when"].get("utc") != u:
                ev["when"] = local_label(u)
                n += 1
        if ev["what"].startswith("Pump P-3 discharge setpoint lowered") and "(02:04Z)" in ev["what"]:
            ev["what"] = ev["what"].replace("in the same session (02:04Z)", "in the same session (02:08Z)")
            n += 1
        if ev["what"].startswith("Relay configuration file written for SUB-02") and "note" in ev:
            ev["what"] = "Relay configuration file written for SUB-02 (22:11:07Z); the same session leaves a 22:11:26Z (17:11 local) file stamp on the SUB-04 RTU"
            del ev["note"]
            n += 1
        if ev["what"].startswith("Initial access on a corporate workstation") and "lure" not in ev["what"]:
            ev["what"] = "Initial access on a corporate workstation: lure delivered 2027-08-30T13:14Z, protection disabled 13:21Z, lookalike-domain lookup 13:23Z; first outbound connection"
            n += 1
    uc = t["utility_cyber"]
    if "remote_sessions" not in uc:
        uc["remote_sessions"] = {"count": 14, "before_storm_d-7_to_d-4": 7, "total_hours": 11.4, "list": "scripts/streams/ot_model.py KNOWN_REMOTE_SESSIONS (used by the OT and IT log families)",
                                 "sources": ["GW-EVT-002", "GW-EVT-011"]}
        n += 1
    cl = t["closures"]
    if "north_beach_port_road" not in cl:
        cl["north_beach_port_road"] = {"what": "The port road north of the Inner Harbor is closed with the bridges, so North Beach has no road link to downtown until the bridges reopen",
                                       "window": cl["bridges"]["window"], "note": "generated detail (needed for 'North Beach cut off'); not reported in the news", "sources": ["EVT-0304", "PUB-027"]}
        n += 1
    if cl.get("airspace", {}).get("note", "").startswith("No manned flights") and "30 nautical miles" not in cl["airspace"]["note"]:
        cl["airspace"]["note"] = "TFR-2027-CC-0441: all civil aircraft operations, manned and unmanned, within 30 nautical miles of Corpus Christi International, surface to 18,000 ft MSL, except emergency operations. " + cl["airspace"]["note"]
        n += 1
    w = t["water"]
    if "districts_3_4_population" not in w:
        w["districts_3_4_population"] = {"served_by_affected_pressure_zone": 48000, "residents_of_census_tracts_touching_the_districts": 60348,
                                         "note": "Canon's 48,000 is the utility's count of residents on the affected Zone 4 mains inside Water Districts 3 and 4. The census tracts that touch the two districts hold 60,348 people because tract edges do not follow the district line; per-capita work on the notice uses 48,000, tract tables use tract populations."}
        n += 1
    c9 = t["calls_911"]
    if isinstance(c9, dict) and "totals_note" not in c9:
        c9["totals_note"] = "44,291 (D0 to D+28) and 56,793 (D0 to D+45) count calls on all lines, 911 and ten-digit, as in the centre's daily volume report; 911-only incident counts follow the daily figures."
        n += 1
    h = t.get("health", {})
    if isinstance(h, dict) and "generator_hours_note" not in h:
        h["generator_hours_note"] = "Shoreline Regional ran on backup power for about 200 hours (D0 06:17Z to D+8 14:14Z); the lead unit's run-hours meter reads 195h 03m."
        n += 1
    al = t.get("alerts", {})
    if isinstance(al, dict) and "generated_notices" not in al:
        al["generated_notices"] = {"note": "Three NOTICE-* records in the press-release export stand in for events that have no public fact of their own; they state only what the event's public effect was.",
                                   "ids_prefix": "NOTICE-"}
        n += 1
    names = t.get("names", {})
    if isinstance(names, dict) and "mission_names" not in names:
        names["mission_names"] = "Survey mission, tile-set and report names carry the calendar month-day (FEMA-UAV-0917-GRID01, CBAS-TIR-0925, FEMA-TIR-0925-UTL), never a scenario day number."
        names["call_signs"] = "ADS-B carries at most eight characters: long radio call signs are shortened to the first six characters plus the two-digit number (GUNSMOKE02 -> GUNSMO02). Join on icao24."
        n += 1
    oi = [x for x in t.get("open_items", []) if not any(k in x for k in ("Hospital ids", "Insurance totals", "Evacuation orders", "T19 drone geometry", "When the two tankers"))]
    if len(oi) != len(t.get("open_items", [])):
        t["open_items"] = oi
        n += 1
    if n:
        save("00_scenario/canon_timeline.json", t)
        changes.append(f"canon timeline edits: {n}")


def fix_public_record():
    pr = load("02_public_record/public_record.json")
    n = 0
    for f in pr["facts"]:
        if f["id"] == "PUB-203" and "Districts 1 through 6" in f["statement"]:
            f["statement"] = f["statement"].replace("Districts 1 through 6", "Districts 1 through 5")
            n += 1
        if f["id"] == "PUB-180" and "all unmanned aircraft operations" in f["statement"]:
            f["statement"] = f["statement"].replace("The TFR prohibits all unmanned aircraft operations within 30 nautical miles of Corpus Christi International Airport up to 3,000 ft AGL, except for aircraft operating under emergency authorizations issued by the FAA Command Center.",
                                                    "The TFR suspends all civil aircraft operations, manned and unmanned, within 30 nautical miles of Corpus Christi International Airport from the surface to 18,000 ft MSL, except for aircraft operating under emergency authorizations issued by the FAA Command Center.")
            n += 1
    if n:
        save("02_public_record/public_record.json", pr)
        changes.append(f"public record edits: {n}")


def fix_stories():
    n = 0
    for fp in sorted(glob.glob(os.path.join(ROOT, "03_news", "stories", "batch-*.json"))):
        rel = os.path.relpath(fp, ROOT)
        n += text_sub(rel, [("Coastal Bend Public Works Authority", "Coastal Bend Power and Water Authority"),
                            ("covering Corpus Christi Class B airspace to 18,000 feet", "covering airspace within 30 nautical miles of Corpus Christi International to 18,000 feet"),
                            ("The TFR covers Class B airspace surrounding Corpus Christi International Airport from the surface to 18,000 feet mean sea level",
                             "The TFR covers airspace within 30 nautical miles of Corpus Christi International Airport from the surface to 18,000 feet mean sea level"),
                            ("Districts 1 through 6", "Districts 1 through 5")], "stories")
    return n


def fix_registry_text():
    text_sub("06_data_streams/aircraft_registry.json", [("combat aviation brigade (Fort Cavazos)", "combat aviation brigade (Fort Hood)"), ("Robert Gray Army Airfield (Fort Cavazos)", "Robert Gray Army Airfield (Fort Hood)")], "Fort Hood")
    text_sub("06_data_streams/organizations.json", [("combat aviation brigade (Fort Cavazos)", "combat aviation brigade (Fort Hood)")], "Fort Hood")
    for f in ("scripts/build_registries_maritime_air.py",):
        if os.path.exists(os.path.join(ROOT, f)):
            text_sub(f, [("Fort Cavazos", "Fort Hood")], "Fort Hood (builder)")


def main():
    fix_msel()
    for rel in ["00_scenario/msel.json", "00_scenario/canon_timeline.json", "00_scenario/threads.json", "06_answer_key/answer_key.json", "00_scenario/answer_key.json",
                "02_public_record/public_record.json", "scenarios/gridwater/06_answer_key/answer_key.json"] + \
               [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "_thread_designs", "*.json"))]:
        if os.path.exists(os.path.join(ROOT, rel)):
            text_sub(rel, PHRASES, "canon phrases")
    fix_timeline()
    fix_public_record()
    fix_stories()
    fix_registry_text()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_expected_observations.py")], capture_output=True, text=True)
    print(r.stdout.strip()[-400:], r.stderr.strip()[-400:])
    print(f"{len(changes)} change group(s)")
    for c in changes:
        print("  ", c)


if __name__ == "__main__":
    main()
