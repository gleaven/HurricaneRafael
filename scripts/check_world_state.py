"""Check the shared state timeline against the ground-truth events and the public record.
Usage: python scripts/check_world_state.py  -> 07_validation/reports/world_state_report.json; exit 1 on failures"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, save

D = "09_shared_state_timeline/data/"
V = load(D + "variables.json"); SEG = load(D + "segments.json"); SER = load(D + "series_hourly.json"); EV = load(D + "events.json"); TR = load(D + "storm_track.json")
T0 = SER["t0"]; T1 = V["meta"]["t1_hour"]
def H(d, h=0, m=0): return d * 24 + h + m / 60
def num(v, t): return SER["series"][v][int(round(t)) - T0]
def st(v, t):
    for s, e, val, _ in SEG[v]:
        if s <= t < e: return val
results = []
def check(name, ok, detail=""):
    results.append({"check": name, "pass": bool(ok), "detail": detail})

# structure
for v, segs in SEG.items():
    ok = segs[0][0] == T0 and segs[-1][1] == T1 + 1 and all(a[1] == b[0] for a, b in zip(segs, segs[1:]))
    check(f"segments contiguous: {v}", ok)
for v, arr in SER["series"].items():
    check(f"series length: {v}", len(arr) == T1 - T0 + 1)
cat = {x["id"]: x for x in V["variables"]}
for v in SEG:
    vals = {s[2] for s in SEG[v]}
    check(f"state colors defined: {v}", vals <= set(cat[v].get("states", {})), str(vals - set(cat[v].get("states", {}))))
# storm
lf = [p for p in TR if p.get("landfall")]
check("landfall at Mustang Island 06:00Z D0", len(lf) == 1 and lf[0]["t"] == 6 and abs(lf[0]["lat"] - 27.75) < 0.05 and abs(lf[0]["lon"] + 97.13) < 0.05)
check("Category 3 at landfall", st("storm_stage", 6) == "Hurricane Cat 3" and num("storm_max_wind_kt", 6) >= 96)
check("storm forms D-10 in NW Caribbean", st("storm_stage", H(-10, 12)) == "Tropical storm" and [p for p in TR if p["t"] == H(-10, 6)][0]["lon"] < -80)
check("hurricane after crossing Yucatan (D-6)", st("storm_stage", H(-7)) == "Tropical storm" and st("storm_stage", H(-6, 18)).startswith("Hurricane"))
check("no watch before D-3; watch D-3; warning D-2", st("nws_advisory", H(-4, 12)) == "Cone covers Corpus Christi" and st("nws_advisory", H(-3, 20)) == "Hurricane watch" and st("nws_advisory", H(-2, 22)) == "Hurricane warning")
check("surge peak about 11 ft at landfall", 10.5 <= max(num("bay_water_level_ft", t) for t in range(0, 12)) <= 13)
# port
check("X-Ray D-3 with port open", st("port_condition", H(-3, 20)) == "X-Ray" and st("channel_status", H(-3, 20)) == "Open")
check("Yankee D-2: closed to inbound, 14 vessels, exports halted", st("channel_status", H(-2, 20)) == "Closed to inbound" and num("vessels_at_anchorage", H(-2, 23)) == 14 and st("crude_exports", H(-2, 20)) == "Halted")
check("Zulu D-1: closed to all, ships to sea", st("channel_status", H(-1, 14)) == "Closed to all" and num("vessels_at_anchorage", H(0, 6)) == 0)
check("ships back at anchorage from D+3", num("vessels_at_anchorage", H(3, 22)) >= 14 and num("vessels_at_anchorage", H(2, 12)) == 0)
check("partial reopening D+30 to D+44", st("channel_status", H(31)) == "Open (inner channel restricted)" and st("channel_status", H(43, 20)) == "Open (inner channel restricted)")
check("blast closure D+44 to D+58, open after", st("channel_status", H(44, 7)) == "Closed (explosive device)" and st("channel_status", H(57, 20)) == "Closed (explosive device)" and st("channel_status", H(58, 20)) == "Open")
check("brigade sails D+59 to D+64", st("brigade_outload", H(59, 18)) == "Loading" and st("brigade_outload", H(62)) == "Sailing" and st("brigade_outload", H(65)) == "Departed")
# water, spill, health
check("boil notice exactly D+4 to D+39", st("boil_water_notice", H(4, 14)) == "No notice" and st("boil_water_notice", H(4, 16)) == "Boil-water notice" and st("boil_water_notice", H(39, 17)) == "Boil-water notice" and st("boil_water_notice", H(39, 19)) == "No notice")
check("O.N. Stevens feeds fail D0 09:00Z", st("onstevens_power_feeds", H(0, 8)) == "Both feeds up" and st("onstevens_power_feeds", H(0, 10)) == "Both feeds down")
check("pump P-2 restored D+38", num("pump_p2_vibration_mm_s", H(38, 12)) == 0 and num("pump_p2_vibration_mm_s", H(38, 20)) > 1)
check("9,000 barrels by 05:30Z D0, none before 04:00Z", num("oil_released_bbl", H(0, 3)) == 0 and abs(num("oil_released_bbl", H(0, 6)) - 9000) < 1)
check("slick about 85 km2 on D+2", 78 <= num("oil_slick_km2", H(2, 12)) <= 92)
check("closures from D+4", st("fishing_closure", H(4, 18)).startswith("Closed") and st("shellfish_closure", H(4, 18)).startswith("Closed") and st("fishing_closure", H(4, 12)) == "Open")
check("911 about 2,900 on landfall day, about 310 baseline", 2600 <= num("calls_911_per_day", H(0, 12)) <= 3200 and 270 <= num("calls_911_per_day", H(-40, 12)) <= 360)
check("stomach illness +180% around D+8", 2.6 <= num("er_stomach_illness_x", H(9)) <= 3.0)
check("low-income tracts +40% on D+45", 1.3 <= num("er_low_income_tracts_x", H(45, 12)) <= 1.5)
check("spill claims about 4,200 by D+115", 4000 <= num("spill_claims_cumulative", H(115, 20)) <= 4400)
# military, threats
check("40 relief flights D+34 to D+43", sum(SER["series"]["relief_flights"]) == 40 and sum(SER["series"]["relief_flights"][int(H(34)) - T0:int(H(44)) - T0]) == 40)
check("generator fails D+40; readiness 61", st("base_generator", H(40, 13)).startswith("Failed") and 60 <= num("nas_readiness_pct", H(40, 16)) <= 62)
check("readiness 92 baseline, 85 by D+110", num("nas_readiness_pct", H(-50)) == 92 and 84 <= num("nas_readiness_pct", H(110)) <= 86)
check("six drone nights D+1 to D+10", sum(1 for s in SEG["drone_overflights"] if s[2] == "Overflight" and H(1) <= s[0] < H(11)) == 6)
check("GPS interference D+38 to D+43", st("gps_interference", H(38, 20)).startswith("Active") and st("gps_interference", H(43, 20)).startswith("Active") and st("gps_interference", H(44, 2)) == "None")
check("AIS dark window D+31 02-16Z", st("halcyon_drift", H(31, 3)) == "AIS dark" and st("spoofed_identity", H(31, 10)).startswith("Broadcasting") and st("halcyon_drift", H(31, 17)).startswith("At anchorage"))
check("devices: 2 from D+31, 1 after blast, 0 after D+52", num("devices_in_channel", H(31, 6)) == 2 and num("devices_in_channel", H(44, 7)) == 1 and num("devices_in_channel", H(53)) == 0)
check("accounts taken over 410 by D+70", num("accounts_taken_over", H(70, 23)) == 410)
check("diverted aid $3.9M by D+80", abs(num("diverted_aid_musd", H(80, 12)) - 3.9) < 0.01)
check("FEMA: declaration D+4, request D+25, approval D+57, registration D+60", st("fema_status", H(4, 18)).startswith("Declaration") and st("fema_status", H(25, 18)).startswith("State requests") and st("fema_status", H(57, 18)) == "Household aid approved" and st("fema_status", H(60, 18)) == "Registration open")
check("48,000 registrations by D+89", abs(num("aid_registrations_cumulative", H(89, 23)) - 48000) <= 50)
check("searches D+104 (not Christmas)", st("debris_contract_vantorra", H(102, 18)) == "Inspector general review" and st("debris_contract_vantorra", H(104, 18)) == "FBI search warrants")
# public-knowledge lanes never run ahead of the public record
facts = {f["id"]: f for f in load("02_public_record/public_record.json")["facts"]}
pk = [("spill_cause_public", "Possible unauthorized remote access", "PUB-042"), ("spill_cause_public", "Attributed to a foreign government", "PUB-097"),
      ("blast_cause_public", "Explosive device confirmed", "PUB-070"), ("blast_cause_public", "Second device found", "PUB-078"),
      ("drones_public", "Residents' videos", "PUB-032"), ("gps_public", "FAA notice: interference", "PUB-064"), ("gps_public", "Transmitter found (parked vehicle)", "PUB-074"),
      ("ais_anomaly_public", "Identity in two places reported", "PUB-062"), ("ais_anomaly_public", "Analysts note timing vs blast", "PUB-076")]
for v, val, pid in pk:
    start = [s[0] for s in SEG[v] if s[2] == val][0]
    check(f"public lane {v} '{val}' not before {pid}", start >= facts[pid]["day"] * 24, f"starts day {start/24:.1f}, fact day {facts[pid]['day']}")
# every MSEL event falls inside the timeline
msel = load("00_scenario/msel.json")
check("every MSEL event has a timed marker", all(any(e["id"] == m["event_id"] and e["kind"] == "truth" for e in EV) for m in msel))
check("every public fact has a timed marker", all(any(e["id"] == f and e["kind"] == "public" for e in EV) for f in facts))
fails = [r for r in results if not r["pass"]]
save("07_validation/reports/world_state_report.json", {"checks": len(results), "failed": fails, "results": results})
print(f"world state: {len(results)} checks, {len(fails)} failed")
for r in fails: print("  FAIL", r["check"], r["detail"])
sys.exit(1 if fails else 0)
