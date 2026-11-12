"""Utility and installation records: outage_map, work_orders, base_status_reports, fuel_deliveries.

    python3 scripts/streams/gen_ot_records.py

All four are written from scripts/streams/ot_model.py and the registries, so they agree with the
SCADA historian (gen_ot_scada.py): the outage map's customers out are the numbers that scale the
feeder currents, crew visits are the control-house door openings, generator fuel delivered here is
the fuel the historian shows being burned.
"""
import csv
import math
import os

import numpy as np

import fuel_ledger
from common import (D0_EPOCH, ROOT, SPAN_END, SPAN_START, day_of, iso, local_dt, local_ts, out_path, reg, retire, rng, ts,
                    write_csv)
import ot_model as M
from ot_model import DAY, T, E, ev_sec

HOSTS = reg("gw_host_registry")
USERS = HOSTS["users"]
BY_DEPT = {}
for u in USERS:
    BY_DEPT.setdefault(u["department"], []).append(u)


def zs(t):
    return iso(int(t))


# =========================================================================== outage map
def gen_outage_map():
    tab = M.outage_table()
    grid = M.OUT_GRID
    g = rng("outage_map")
    lf = T["landfall"]
    storm_a, storm_b = lf, T["all_restored"] + 3600
    rows = []
    feeder_meta = {f[0]: f for f in M.FEEDERS}
    extra_times = {  # feeder -> exact event instants shown as their own rows (minute resolution)
        "GW-DSS01-FDR-11": [ts("2027-09-14T06:17Z"), ts("2027-09-22T14:14Z")],
        "GW-SUB05-CB-18": [ts("2027-10-24T19:16Z"), ts("2027-10-24T20:08Z")],
        "GW-SUB01-CB-2": [ts("2027-09-14T07:12Z")], "GW-SUB01-CB-3": [ts("2027-09-14T07:12Z")], "GW-SUB01-CB-4": [ts("2027-09-14T07:12Z")],
    }
    bg_causes = ["EQUIPMENT", "TREE", "VEHICLE", "ANIMAL", "PLANNED", "UNKNOWN"]
    for fid in M.FEEDER_IDS:
        _, sub, _, served, area = feeder_meta[fid]
        vals = tab[fid]
        cause_bg = bg_causes[int(g.integers(0, len(bg_causes)))]
        prev_out = 0
        series = [(int(t), int(v)) for t, v in zip(grid.tolist(), vals.tolist())]
        for te in extra_times.get(fid, []):
            if fid == "GW-DSS01-FDR-11":
                v = 5200 if te == ts("2027-09-14T06:17Z") else 0
            elif fid == "GW-SUB05-CB-18":
                v = served if te == ts("2027-10-24T19:16Z") else 0
            else:
                v = served
            series.append((te, v))
        series.sort()
        for t, out in series:
            if out == 0:
                cause, crews, etr = "", 0, ""
            else:
                in_storm = storm_a - 9 * 3600 <= t <= storm_b
                if not in_storm and prev_out == 0:
                    cause_bg = bg_causes[int(g.integers(0, len(bg_causes)))]
                    if out == served:
                        cause_bg = "EQUIPMENT"             # a whole circuit at once is a line or station fault
                cause = "STORM" if in_storm else cause_bg
                if in_storm and t < lf + 12 * 3600:
                    crews = 0 if t >= lf - 3 * 3600 else min(2, max(1, math.ceil(out / 400)))    # crews stood down as the wind rose
                else:
                    crews = min(9, max(1, math.ceil(out / 1600)))
                if in_storm:
                    late = sub in ("GW-FAC-SUB-02", "GW-FAC-SUB-03") and t >= ts("2027-09-21T14:30Z")
                    if t < lf + 24 * 3600:
                        etr = ""                                      # damage assessment under way
                    elif late and t < T["isolate"]:
                        etr = zs((t // DAY + 3) * DAY + 23 * 3600)    # keeps slipping
                    elif late:
                        etr = "2027-10-19T23:00:00Z"
                    else:
                        etr = zs((t // DAY + 1 + min(4, out // 1500)) * DAY + 23 * 3600)
                else:
                    etr = zs(t + 2 * 3600 - t % 900)
            rows.append([zs(t), area, fid, sub, served, out, cause, crews, etr])
            prev_out = out
    rows.sort(key=lambda r: (r[0], r[3], r[2]))
    n = write_csv("05_other_sources/telemetry/outage_map.csv",
                  ["timestamp_utc", "area_id", "feeder_id", "substation_id", "customers_served", "customers_out", "cause",
                   "crews_assigned", "est_restoration_utc"], rows)
    return n


# =========================================================================== work orders
WO_COLS = ["wonum", "org_id", "site_id", "description", "work_type", "status", "status_date", "reported_date", "asset_id", "location",
           "priority", "sched_start", "sched_finish", "actual_start", "actual_finish", "labor_hours", "reported_by", "lead", "crew",
           "failure_code", "vendor_id", "pr_number", "parent_wonum", "status_history", "work_log"]


class WOBook:
    def __init__(self):
        self.rows = []

    def add(self, wonum=None, org="CBPWA", site="CBPWA-CC", desc="", wtype="PM", reported=0, asset="", location="", priority=3,
            start=None, finish=None, hours=None, reported_by="", lead="", crew="", failure="", vendor="", pr="", parent="",
            history=None, log="", status=None, sched=None):
        """history: [(status, epoch)]; the last entry is the status at export."""
        if history is None:
            history = [("WAPPR", reported), ("APPR", reported + 1800)]
            if start:
                history.append(("INPRG", start))
            if finish:
                history += [("COMP", finish), ("CLOSE", finish + 20 * 3600)]
        history = [(s, t) for s, t in history if t <= SPAN_END]
        st, st_t = history[-1]
        if status:
            st = status
        sched = sched or ((start, finish) if start and finish else ("", ""))
        self.rows.append({
            "wonum": wonum, "org_id": org, "site_id": site, "description": desc, "work_type": wtype, "status": st, "status_date": zs(st_t),
            "reported_date": zs(reported), "asset_id": asset, "location": location, "priority": priority,
            "sched_start": zs(sched[0]) if sched[0] else "", "sched_finish": zs(sched[1]) if sched[1] else "",
            "actual_start": zs(start) if start and start <= SPAN_END else "", "actual_finish": zs(finish) if finish and finish <= SPAN_END else "",
            "labor_hours": f"{hours:.1f}" if hours is not None and finish and finish <= SPAN_END else "",
            "reported_by": reported_by, "lead": lead, "crew": crew, "failure_code": failure, "vendor_id": vendor, "pr_number": pr,
            "parent_wonum": parent, "status_history": ";".join(f"{s}@{zs(t)}" for s, t in history), "work_log": log,
            "_t": reported,
        })


def pick(g, dept, title_part=None):
    pool = [u for u in BY_DEPT.get(dept, []) if not title_part or title_part.lower() in u["title"].lower()] or BY_DEPT.get(dept, [])
    return pool[int(g.integers(0, len(pool)))]["username"]


def gen_work_orders():
    g = rng("work_orders")
    B = WOBook()
    assets = reg("infrastructure_assets")["assets"]
    tags = reg("scada_tags")["tags"]
    equip_by_site = {}
    for t in tags:
        equip_by_site.setdefault(t["site_id"], set()).add(t["equipment_id"])
    lf = T["landfall"]
    sub_ids = [M.SUBS[n][0] for n in range(1, 6)]
    tanks = [a["asset_id"] for a in assets if a["asset_type"] == "water_storage_tank"]
    lifts = [a["asset_id"] for a in assets if a["asset_type"] == "wastewater_lift_station"]
    ptest = [a["asset_id"] for a in assets if a["asset_type"] == "pressure_test_point"]
    pumps = ["EQP-1101", "EQP-1102", "EQP-1103", "EQP-1104"]
    boosters = sorted(e for s in ("GW-FAC-WTR-01", "GW-FAC-WTR-02", "GW-FAC-WTR-03") for e in equip_by_site.get(s, []) if "BP" in e)
    visits = __import__("gen_ot_scada").site_visits()

    # ---------------------------------------------------------------- routine work, whole span
    templates = [
        ("PM - Monthly breaker inspection and operation count", "PM", lambda: (next_breaker(), "SUBSTATION"), "Field Services", "Substation", "SUBTECH", 2.5),
        ("PM - Transformer T1 oil sample and DGA", "PM", lambda: (f"GW-SUB0{int(g.integers(1, 6))}-T1", "SUBSTATION"), "Field Services", "Substation", "SUBTECH", 2.0),
        ("PM - Station battery bank inspection", "PM", lambda: (g.choice(sub_ids), "SUBSTATION"), "Field Services", "Substation", "SUBTECH", 1.5),
        ("PM - Vegetation patrol, distribution feeder", "PM", lambda: (g.choice(M.FEEDER_IDS), "FEEDER"), "Field Services", "Line", "LINE", 6.0),
        ("CM - Replace failed lightning arrester", "CM", lambda: (g.choice(M.FEEDER_IDS), "FEEDER"), "Field Services", "Line", "LINE", 4.0),
        ("CM - Pole-top recloser will not close; inspect and repair", "CM", lambda: (g.choice(M.FEEDER_IDS), "FEEDER"), "Field Services", "Trouble", "TRBL", 3.5),
        ("PM - High-service pump bearing lubrication and vibration reading", "PM", lambda: (g.choice(pumps), "PUMP-STATION-1"), "Water Operations", "Mechanic", "WTP-MECH", 2.0),
        ("PM - Booster pump inspection", "PM", lambda: (g.choice(boosters), "RAW-WATER-PIPELINE"), "Water Operations", "Mechanic", "WTP-MECH", 5.0),
        ("PM - Chlorine feed system calibration check", "PM", lambda: ("EQP-1130", "WATER-PLANT"), "Water Operations", "Instrumentation", "WTP-INST", 3.0),
        ("PM - Raw water analyzer calibration", "PM", lambda: ("EQP-1120", "WATER-PLANT"), "Water Operations", "Instrumentation", "WTP-INST", 2.0),
        ("PM - Storage tank level transmitter check", "PM", lambda: (g.choice(tanks), "DISTRIBUTION"), "Water Operations", "Instrumentation", "WTP-INST", 2.5),
        ("PM - Pressure test point gauge verification", "PM", lambda: (g.choice(ptest), "DISTRIBUTION"), "Water Distribution", "Technician", "DIST", 1.5),
        ("CM - Lift station pump ragging; pull and clear", "CM", lambda: (g.choice(lifts), "COLLECTION"), "Water Distribution", "Crew", "DIST", 3.0),
        ("CM - Main break repair", "CM", lambda: (g.choice(tanks), "DISTRIBUTION"), "Water Distribution", "Crew", "DIST", 7.5),
        ("PM - Fill valve actuator stroke test", "PM", lambda: (g.choice(tanks), "DISTRIBUTION"), "Water Distribution", "Technician", "DIST", 2.0),
        # everyday corrective work that uses the rest of the failure-code list
        ("CM - Relay target found after lightning; download event record, test and return to service", "CM", lambda: (f"GW-SUB0{int(g.integers(1, 6))}-REL-27", "SUBSTATION"), "Protection and Control", "Relay", "P&C", 4.0, "RELAY"),
        ("CM - Recloser control setting group does not match setting sheet; re-enter approved settings", "CM", lambda: (g.choice(M.FEEDER_IDS), "FEEDER"), "Protection and Control", "Relay", "P&C", 3.0, "SETTING"),
        ("CM - Analyser reads off after calibration; setting found changed during maintenance, restore", "CM", lambda: ("EQP-1120", "WATER-PLANT"), "Water Operations", "Instrumentation", "WTP-INST", 2.0, "SETTING"),
        ("CM - Low pressure complaint; check pressure test point and regulating valve", "CM", lambda: (g.choice(ptest), "DISTRIBUTION"), "Water Distribution", "Technician", "DIST", 2.5, "LOWPRES"),
        ("CM - Nuisance alarm chattering; check transmitter and alarm deadband", "CM", lambda: (g.choice(tanks), "DISTRIBUTION"), "Water Operations", "Instrumentation", "WTP-INST", 2.0, "ALARM"),
        ("CM - Pump motor bearing running hot; inspect and regrease", "CM", lambda: (g.choice(boosters), "RAW-WATER-PIPELINE"), "Water Operations", "Mechanic", "WTP-MECH", 4.0, "OVERHEAT"),
        ("CM - Pump vibration above alert level; check alignment", "CM", lambda: (g.choice(boosters), "RAW-WATER-PIPELINE"), "Water Operations", "Mechanic", "WTP-MECH", 5.0, "VIB"),
        ("CM - Intermittent fault, cause not found; monitor", "CM", lambda: (g.choice(M.FEEDER_IDS), "FEEDER"), "Field Services", "Trouble", "TRBL", 3.0, "UNK"),
    ]
    weights = np.array([1.0] * 15 + [0.22, 0.3, 0.2, 0.4, 0.35, 0.25, 0.25, 0.3])
    weights /= weights.sum()
    last_insp = {f: -10 ** 9 for f in M.FEEDER_IDS}
    now = [0]

    def next_breaker():
        """The breaker that has gone longest without its monthly inspection."""
        f = min(M.FEEDER_IDS, key=lambda x: (last_insp[x], x))
        last_insp[f] = now[0]
        return f
    seq = 31200
    t = SPAN_START
    while t < SPAN_END - DAY:
        ld = local_dt(t + 12 * 3600)
        dday = (t + 12 * 3600 - D0_EPOCH) / DAY
        weekday = ld.weekday() < 5
        lam = 5.6 if weekday else 1.2
        if -2 <= dday <= 9:
            lam = 0.0                                        # everything is storm work
        elif 9 < dday <= 40:
            lam *= 0.45
        for _ in range(int(g.poisson(lam))):
            tpl = templates[int(g.choice(len(templates), p=weights))]
            desc, wtype, pick_asset, dept, title, crew, hrs = tpl[:7]
            now[0] = t
            if desc.startswith("PM - Monthly breaker") and t - min(last_insp.values()) < 26 * DAY:
                continue                                     # every breaker already inspected this month
            asset, loc = pick_asset()
            rep = t + int(g.integers(12 * 3600, 22 * 3600))
            start = rep + int(g.integers(1, 5)) * DAY + int(g.integers(-3600, 7200))
            start = start - start % 900
            dur = hrs * 3600 * float(g.uniform(0.7, 1.5))
            fin = start + int(dur)
            if lf - 2 * DAY < start < lf + 9 * DAY:
                start += 12 * DAY
                fin += 12 * DAY
            seq += int(g.integers(1, 4))
            who = pick(g, dept, title)
            if who == "rvela" and ts("2027-09-06T22:00Z") <= start <= ts("2027-09-22T12:00Z"):      # on leave, out of state
                who = next(u["username"] for u in BY_DEPT[dept] if u["username"] != "rvela")
            B.add(wonum=f"WO-2027-{seq}", desc=desc, wtype=wtype, reported=rep, asset=str(asset), location=loc, priority=int(g.choice([3, 3, 4, 4, 2])),
                  start=start, finish=fin, hours=dur / 3600 * float(g.choice([1, 2, 2, 3])), reported_by="MAINT-SCHED" if wtype == "PM" else pick(g, "System Operations"),
                  lead=who, crew=f"{crew}-{int(g.integers(1, 5))}", failure="" if wtype == "PM" else (tpl[7] if len(tpl) > 7 else str(g.choice(["WEAR", "ELEC", "MECH", "CORR", "LEAK"]))))
        # weekly standby generator test at the plant (Wednesday)
        if ld.weekday() == 2 and not (-3 <= dday <= 5):
            a = t - t % DAY + 15 * 3600
            seq += 1
            B.add(wonum=f"WO-2027-{seq}", desc="PM - Standby generator weekly test run (30 min under load)", wtype="PM", reported=a - 2 * DAY, asset="EQP-1140",
                  location="WATER-PLANT", priority=3, start=a - 600, finish=a + 2400, hours=1.0, reported_by="MAINT-SCHED",
                  lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-1", log="Started and carried load; no alarms.")
        t += DAY

    def won():
        nonlocal seq
        seq += int(g.integers(1, 3))
        return f"WO-2027-{seq}"

    pc = lambda title="Relay": pick(g, "Protection and Control", title)

    # ---------------------------------------------------------------- canon orders, CBPWA
    # annual relay test at Riverside, thirty days before landfall
    a = ts("2027-08-15T14:10Z")
    B.add(wonum="WO-2027-31187", desc="PM - Annual protective relay test, Riverside Switching Station (27-UV, 50/51)", wtype="PM", reported=a - 9 * DAY,
          asset="GW-SUB01-REL-27", location="SUBSTATION", priority=3, start=a, finish=ts("2027-08-15T19:40Z"), hours=11.0,
          reported_by="MAINT-SCHED", lead=pc(), crew="P&C-1",
          log="Secondary injection test complete. 27-UV pickup verified at 0.88 pu, time delay 2.0 s; 50/51 elements within tolerance. As-left settings match commissioning record.")
    # P-2 vibration, reported before the record starts and deferred
    B.add(wonum="WO-2027-30911", desc="CM - High-service pump P-2 vibration trending up; inspect bearings and coupling", wtype="CM", reported=ts("2027-07-21T14:12Z"),
          asset="EQP-1102", location="PUMP-STATION-1", priority=2, reported_by=pick(g, "Water Operations", "Operator"), lead=pick(g, "Water Operations", "Mechanic"),
          crew="WTP-MECH-2", failure="VIB",
          history=[("WAPPR", ts("2027-07-21T14:12Z")), ("APPR", ts("2027-07-22T13:30Z")), ("DEFERRED", ts("2027-07-28T15:40Z")), ("CAN", T["plant_feeds"] + 4 * 3600)],
          sched=(ts("2027-11-08T14:00Z"), ts("2027-11-12T22:00Z")),
          log="2027-07-21 operator reports rising vibration on P-2, 0.14 in/s. 2027-07-28 deferred to the November low-demand outage: pump needed through peak season, readings below alarm. "
              "2027-08-25 reading 0.21 in/s, continue to monitor. 2027-09-08 reading 0.27 in/s. 2027-09-14 superseded by the emergency order for the P-2 failure.")
    # storm preparation
    for i, (d, desc, asset, crew) in enumerate([
            (-4, "EM - Storm preparation: top off standby generator fuel and test transfer switch", "EQP-1140", "WTP-MECH-1"),
            (-4, "EM - Storm preparation: secure substation yards, sandbag control houses", "GW-FAC-SUB-02", "SUBTECH-2"),
            (-3, "EM - Storm preparation: secure substation yards, sandbag control houses", "GW-FAC-SUB-05", "SUBTECH-1"),
            (-3, "EM - Storm preparation: fill all storage tanks to high level", "GW-FAC-TK-03", "DIST-2"),
            (-2, "EM - Storm preparation: stage line crews and material", "GW-FAC-OPS-01", "LINE-1"),
            (-2, "EM - Storm preparation: change freeze on protection and SCADA settings until further notice", "GW-FAC-OPS-01", "P&C-1")]):
        a = local_ts(d, "08:00") + i * 1200
        B.add(wonum=won(), desc=desc, wtype="EM", reported=a, asset=asset, location="SYSTEM", priority=1, start=a + 3600, finish=a + 8 * 3600, hours=14.0,
              reported_by=pick(g, "System Operations", "Supervisor"), lead=pick(g, "Field Services"), crew=crew)
    # landfall: plant power feeds and P-2
    pf = T["plant_feeds"]
    w_p2 = won()
    B.add(wonum=w_p2, desc="EM - High-service pump P-2 failed on loss of both plant power feeds; will not restart", wtype="EM", reported=pf + 2460, asset="EQP-1102",
          location="PUMP-STATION-1", priority=1, start=pf + 9 * 3600, finish=T["p2_back"], hours=212.0, failure="BRG",
          reported_by=pick(g, "Water Operations", "Operator"), lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-2",
          history=[("WAPPR", pf + 2460), ("APPR", pf + 3000), ("INPRG", pf + 9 * 3600), ("WMATL", ts("2027-09-16T15:30Z")),
                   ("INPRG", ts("2027-10-20T16:10Z")), ("COMP", T["p2_back"]), ("CLOSE", T["p2_back"] + 5 * 3600)],
          log="2027-09-14 P-2 tripped when both feeds were lost at 04:00 local; motor megger good, pump end seized, inboard bearing and shaft sleeve damaged. "
              "2027-09-16 parts on order, waiting on material. 2027-09-24 supplier advises its local warehouse flooded. 2027-10-04 parts shipping from out of state. "
              "2027-10-20 parts received; rebuild started. 2027-10-22 rebuild complete, pump test run, returned to service.")
    B.add(wonum=won(), desc="EM - Loss of primary power feed A to O.N. Stevens; patrol and repair line", wtype="EM", reported=pf + 900, asset="FAC-UTL-02",
          location="WATER-PLANT", priority=1, start=pf + 26 * 3600, finish=T["feed_a_back"], hours=96.0, failure="STORM",
          reported_by=pick(g, "System Operations", "Supervisor"), lead=pick(g, "Field Services", "Foreman"), crew="LINE-3",
          log="Feed A de-energized 04:00 local on 2027-09-14. Patrol found three structures down and conductor on the ground. Repaired and re-energized 2027-09-16.")
    B.add(wonum=won(), desc="EM - Loss of backup power feed B to the pump room; patrol and repair", wtype="EM", reported=pf + 1100, asset="FAC-UTL-02",
          location="WATER-PLANT", priority=1, start=pf + 80 * 3600, finish=T["feed_b_back"], hours=74.0, failure="STORM",
          reported_by=pick(g, "System Operations", "Supervisor"), lead=pick(g, "Field Services", "Foreman"), crew="LINE-2",
          log="Feed B from Crosstown lost with feed A. Two spans and one crossarm replaced; re-energized 2027-09-19.")
    B.add(wonum=won(), desc="EM - Pump P-3 motor over-temperature trip while on standby power; inspect before restart", wtype="EM", reported=pf + 1500, asset="EQP-1103",
          location="PUMP-STATION-1", priority=1, start=pf + 20 * 3600, finish=T["p3_restart"], hours=18.0, failure="OVERHEAT",
          reported_by=pick(g, "Water Operations", "Operator"), lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-1",
          log="Winding temperature 131 C at trip. Insulation resistance marginal on one phase. Returned to service at reduced load pending rewind; add to the parts request.")
    # purchase request for pump parts
    pr = "PR-2027-4417"
    B.add(wonum=pr, desc="Purchase request - P-2 bearing set, shaft sleeve, mechanical seal; P-3 stator rewind kit", wtype="PR", reported=ts("2027-09-16T15:10Z"),
          asset="EQP-1102", location="PUMP-STATION-1", priority=1, vendor="VND-0005", pr=pr, parent=w_p2,
          reported_by=pick(g, "Water Operations", "Superintendent"), lead=pick(g, "Finance and Procurement"),
          history=[("WAPPR", ts("2027-09-16T15:10Z")), ("APPR", ts("2027-09-16T17:40Z")), ("ORDERED", ts("2027-09-16T19:05Z")),
                   ("RECEIVED", ts("2027-10-20T15:20Z")), ("CLOSE", ts("2027-10-22T21:00Z"))],
          log="Quoted delivery nine days (2027-09-25). 2027-09-24 vendor: local warehouse flooded, stock lost. 2027-10-04 vendor: shipping from out-of-state plant. "
              "2027-10-20 received complete, 34 days after order.")
    for k, (name, when) in enumerate((("TP-1", T["tp1_on"]), ("TP-2", T["tp2_on"]))):
        B.add(wonum=won(), desc=f"EM - Install and commission temporary pump {name} at high-service header", wtype="EM", reported=when - 30 * 3600,
              asset=f"GW-FAC-UTL-01-TP{k + 1}", location="PUMP-STATION-1", priority=1, start=when - 20 * 3600, finish=when, hours=64.0, vendor="VND-0095",
              reported_by=pick(g, "Water Operations", "Superintendent"), lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-1",
              log="Rental diesel-driven pump set and piping; capacity well below a high-service pump.")
    # storm damage repair by feeder
    tab = M.outage_table()
    for fid in M.FEEDER_IDS:
        vals = tab[fid]
        peak = int(vals.max())
        if peak < 300:
            continue
        nz = np.where(vals > 0.02 * M.SERVED[fid])[0]
        first, last = int(M.OUT_GRID[nz[0]]), int(M.OUT_GRID[nz[-1]])
        if fid in ("GW-SUB02-CB-5", "GW-SUB02-CB-6", "GW-SUB02-CB-8", "GW-SUB03-CB-9", "GW-SUB03-CB-10", "GW-SUB03-CB-11"):
            last = min(last, ts("2027-09-21T03:00Z") if fid == "GW-SUB02-CB-6" else (ts("2027-09-20T00:00Z") if fid == "GW-SUB03-CB-10" else last))
        nwo = max(1, min(6, peak // 1500))
        for j in range(nwo):
            a = first + 14 * 3600 + int((last - first) * j / nwo) + int(g.integers(0, 4 * 3600))
            dur = int(g.integers(10, 40)) * 3600
            fin = min(a + dur, last + 3600) if last > a else a + dur
            B.add(wonum=won(), desc=f"EM - Storm damage repair, feeder {fid.split('-', 2)[-1]}: " + str(g.choice(["replace broken poles and crossarms", "re-string downed primary", "replace pad-mount transformers flooded by surge",
                                                                                                           "clear trees and repair laterals", "replace damaged reclosers and fuses"])),
                  wtype="EM", reported=a - 3600, asset=fid, location="FEEDER", priority=1, start=a, finish=fin, hours=(fin - a) / 3600 * 5, failure="STORM",
                  reported_by=pick(g, "System Operations"), lead=pick(g, "Field Services", "Foreman"), crew=f"LINE-{int(g.integers(1, 9))}")
    # D+7: SUB-02 breaker
    c2 = T["sub2_cmd"]
    v2 = visits["GW-FAC-SUB-02"]
    a2 = [v for v in v2 if abs(v[0] - ts("2027-09-21T15:22Z")) < 60][0]
    b2 = [v for v in v2 if abs(v[0] - ts("2027-09-22T13:05Z")) < 60][0]
    B.add(wonum=won(), desc="EM - Harbor View main breaker CB-7 open; restored circuits lost again. Inspect breaker, relays and yard", wtype="EM", reported=c2 + 660,
          asset="GW-SUB02-BKR-MAIN", location="SUBSTATION", priority=1, start=a2[0], finish=b2[1], hours=11.5, failure="RELAY",
          reported_by=pick(g, "System Operations", "Supervisor"), lead=pick(g, "Field Services", "Substation"), crew="SUBTECH-2",
          history=[("WAPPR", c2 + 660), ("APPR", c2 + 900), ("INPRG", a2[0]), ("COMP", b2[1]), ("CLOSE", ts("2027-09-22T21:10Z"))],
          log="2027-09-21 crew on site 10:22 local. Breaker found open, mechanism and trip coil test normal, no targets on the overcurrent relays, no fault evidence in the yard. "
              "2027-09-22 terminal block on the trip circuit found loose with storm debris in the cabinet; cleaned and tightened. No other physical cause found. "
              "Closed as loose protective relay connection. Breaker left open for switching by operations.")
    # D+10: SUB-03 breaker
    c3 = T["sub3_cmd"]
    v3 = visits["GW-FAC-SUB-03"]
    a3 = [v for v in v3 if abs(v[0] - ts("2027-09-24T20:31Z")) < 60][0]
    b3 = [v for v in v3 if abs(v[0] - ts("2027-09-25T13:10Z")) < 60][0]
    B.add(wonum=won(), desc="EM - Crosstown main breaker CB-12 open; 6,800 customers and pump-room backup feed lost. Inspect", wtype="EM", reported=c3 + 540,
          asset="GW-SUB03-BKR-MAIN", location="SUBSTATION", priority=1, start=a3[0], finish=b3[1], hours=13.0, failure="UNK",
          reported_by=pick(g, "System Operations", "Supervisor"), lead=pick(g, "Field Services", "Substation"), crew="SUBTECH-1",
          history=[("WAPPR", c3 + 540), ("APPR", c3 + 800), ("INPRG", a3[0]), ("COMP", b3[1]), ("CLOSE", ts("2027-09-25T22:30Z"))],
          log="2027-09-24 crew on site 15:31 local. Breaker open, no relay targets, no flashover marks, insulation tests normal. 2027-09-25 second inspection in daylight: "
              "no apparent physical cause. Second unexplained main-breaker operation this week; referred to protection engineering.")
    # D+12: field report of low pressure
    fr = ts("2027-09-26T15:44Z")
    B.add(wonum="GW-FR-0912", desc="Field report - minimal flow at residential hydrant test point, Loma Alta / Holly Rd; household taps at a trickle", wtype="FR", reported=fr,
          asset="GW-PT-Z4-03", location="DISTRIBUTION", priority=1, start=fr - 1500, finish=ts("2027-09-26T16:30Z"), hours=1.5, failure="LOWPRES",
          reported_by=pick(g, "Water Distribution", "Field Operator"), lead=pick(g, "Water Distribution", "Superintendent"), crew="DIST-3",
          history=[("REPORTED", fr), ("ESCALATED", ts("2027-09-26T15:52Z")), ("CLOSE", ts("2027-09-26T22:40Z"))],
          log="Field operator checking Zone 4 valves found household taps in Loma Alta running at a trickle; hydrant gauge about 16 to 18 psi. Control room queried the Zone 4 pressure "
              "point at 10:52 local: 16.4 psi, below the 20 psi limit, with no alarm showing. Boil-water notice for Districts 3 and 4 ordered.")
    B.add(wonum=won(), desc="CM - Zone 4 low-pressure alarm did not annunciate; check alarm configuration", wtype="CM", reported=ts("2027-09-26T17:20Z"), asset="GW-PT-Z4-03",
          location="CONTROL-CENTER", priority=1, start=ts("2027-09-27T14:00Z"), finish=ts("2027-09-27T19:30Z"), hours=5.5, failure="ALARM",
          reported_by=pick(g, "System Operations", "Water"), lead=pick(g, "OT Engineering", "SCADA"), crew="OT-1",
          log="Alarm point found in the suppression list. No request on file. Removed from suppression; reason for the entry not determined. Many other points also suppressed; list to be reviewed.")
    # D+14: relay threshold noticed
    a = ts("2027-09-28T22:10Z")
    B.add(wonum=won(), desc="CM - Riverside 27-UV pickup reads 0.94 pu, commissioning record 0.88 pu; possible configuration drift (grid operator ticket TXRC-2027-09-28-004)",
          wtype="CM", reported=a, asset="GW-SUB01-REL-27", location="SUBSTATION", priority=2, start=ts("2027-10-19T15:20Z"), finish=T["relay_reset_sub1"] + 1500, hours=3.0,
          failure="SETTING", reported_by=pc("engineer"), lead=pc(), crew="P&C-1",
          history=[("WAPPR", a), ("APPR", ts("2027-09-29T14:05Z")), ("HOLD", ts("2027-09-29T16:30Z")), ("INPRG", ts("2027-10-19T15:20Z")),
                   ("COMP", T["relay_reset_sub1"] + 1500), ("CLOSE", ts("2027-10-20T15:00Z"))],
          log="2027-09-28 setting dump shows 27-UV at 0.94 pu. No approved change on record since the August test (0.88 pu). 2027-09-29 held: settings changes frozen during restoration. "
              "2027-10-19 reset to 0.88 pu under relay audit GW-RAR-001 and verified by secondary injection.")
    # D+16: SUB-04 recommissioning
    a = T["rtu4_found"]
    B.add(wonum=won(), desc="CM - Southside recommissioning: relay configuration file on the RTU does not match the approved file", wtype="CM", reported=a,
          asset="GW-FAC-SUB-04", location="SUBSTATION", priority=1, start=ts("2027-09-30T15:10Z"), finish=ts("2027-09-30T21:05Z"), hours=9.0, failure="SETTING",
          reported_by=pc(), lead=pc("engineer"), crew="P&C-2",
          log="During recommissioning checks the RTU held a relay configuration file last modified 2027-09-11, during the storm-preparation change freeze, with no work order. "
              "Active relay settings were not affected. Approved file reloaded and checksum verified. Reported to OT engineering and the operations director.")
    # D+28: isolation and manual operation
    iso_t = ts("2027-10-12T08:00Z")
    B.add(wonum="WO-2027-OT-0881", desc="EM - Isolate SCADA and control networks from external connectivity; remote-access gateway offline", wtype="EM", reported=iso_t,
          asset="GW-FAC-OPS-01", location="CONTROL-CENTER", priority=1, start=iso_t + 3600, finish=T["reconnect"], hours=160.0,
          reported_by=pick(g, "OT Engineering", "Manager"), lead=pick(g, "OT Engineering", "SCADA"), crew="OT-1",
          history=[("WAPPR", iso_t), ("APPR", iso_t + 600), ("INPRG", iso_t + 3600), ("COMP", T["reconnect"]), ("CLOSE", T["reconnect"] + 20 * 3600)],
          log="2027-10-12 external connectivity cut at 07:00 local; remote-access gateway powered off; all remote sessions ended. Setpoints reviewed against approved values; "
              "P-3 discharge setpoint found at 68 psi and restored to 85 psi; Colorado River booster station setpoint found at 54 psi and restored to 72 psi. "
              "2027-10-19 rebuilt systems reconnected after verification.")
    for n in range(1, 6):
        asset = M.SUBS[n][0]
        vv = [v for v in visits[asset] if ts("2027-10-12T12:00Z") < v[0] < ts("2027-10-13T05:00Z")]
        a = vv[0][0] if vv else ts("2027-10-12T15:00Z")
        b = vv[0][1] if vv else a + 7200
        B.add(wonum=won(), desc=f"EM - Place {M.SUBS[n][1].replace('GW.', '')} protection and breaker control in local manual operation", wtype="EM",
              reported=ts("2027-10-12T12:20Z") + n * 240, asset=asset, location="SUBSTATION", priority=1, start=a, finish=b, hours=6.0,
              reported_by=pick(g, "System Operations", "Director"), lead=pick(g, "Field Services", "Substation"), crew=f"SUBTECH-{1 + n % 3}",
              log="Supervisory control disabled at the RTU; station staffed for manual switching until further notice.")
    B.add(wonum=won(), desc="EM - Temporary generator supply for pump P-4 (pump-room backup feed out of service)", wtype="EM", reported=ts("2027-10-12T12:30Z"),
          asset="EQP-1104", location="PUMP-STATION-1", priority=1, start=ts("2027-10-12T12:40Z"), finish=T["p4_tempgen"], hours=4.0, vendor="VND-0095",
          reported_by=pick(g, "Water Operations", "Superintendent"), lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-1",
          log="Rental generator connected at the pump-room MCC; P-4 started 08:31 local.")
    # D+35: relay audit and restoration
    a = ts("2027-10-19T13:30Z")
    B.add(wonum=won(), desc="EM - Relay audit GW-RAR-001: verify and reset protection settings at all five substations", wtype="EM", reported=ts("2027-10-14T14:00Z"),
          asset="GW-FAC-SUB-02", location="SUBSTATION", priority=1, start=ts("2027-10-15T13:00Z"), finish=T["all_restored"], hours=188.0,
          reported_by=pc("engineer"), lead=pc(), crew="P&C-1",
          history=[("WAPPR", ts("2027-10-14T14:00Z")), ("APPR", ts("2027-10-14T15:10Z")), ("INPRG", ts("2027-10-15T13:00Z")), ("COMP", T["all_restored"]),
                   ("CLOSE", ts("2027-10-20T16:00Z"))],
          log="Relay audit GW-RAR-001 complete: all five substations confirmed at commissioning-baseline settings. Riverside 27-UV reset from 0.94 to 0.88 pu; "
              "Harbor View overcurrent pickups reset from 2400 A to 1200 A; Crosstown, Southside and Bayside found at baseline. Harbor View CB-7 and Crosstown CB-12 closed; "
              "last customers restored 15:00 local 2027-10-19.")
    # afterwards
    B.add(wonum=won(), desc="CM - Rewind P-3 stator and replace bearings (storm over-temperature damage)", wtype="CM", reported=ts("2027-10-21T14:00Z"), asset="EQP-1103",
          location="PUMP-STATION-1", priority=2, start=ts("2027-10-23T02:00Z"), finish=T["p3_full"], hours=22.0, vendor="VND-0005", pr=pr,
          reported_by=pick(g, "Water Operations", "Superintendent"), lead=pick(g, "Water Operations", "Mechanic"), crew="WTP-MECH-2",
          log="Done overnight at low demand with P-2 back in service. Returned to full load.")
    B.add(wonum=won(), desc="CAP - Study: harden both power feeds to O.N. Stevens (underground section, second source)", wtype="CAP", reported=ts("2028-01-03T15:30Z"),
          asset="FAC-UTL-02", location="WATER-PLANT", priority=3, reported_by=pick(g, "Transmission and Distribution Engineering"),
          lead=pick(g, "Transmission and Distribution Engineering"), history=[("WAPPR", ts("2028-01-03T15:30Z"))],
          log="Requested after the city announced plans to harden the plant's power feeds.")
    B.add(wonum=won(), desc="PM - Bayside relay settings update per coordination study (approved change)", wtype="PM", reported=ts("2027-11-08T15:00Z"),
          asset="GW-SUB05-REL-27", location="SUBSTATION", priority=3, start=ts("2027-11-16T14:30Z"), finish=ts("2027-11-16T17:10Z"), hours=5.0,
          reported_by=pc("engineer"), lead=pc(), crew="P&C-2", log="Approved settings file loaded and verified; change ticket attached.")

    # ---------------------------------------------------------------- Army depot (CCAD)
    n_ccad = 4100

    def ccad(desc, wtype, rep, start=None, fin=None, hours=None, asset="", log="", prio=2, history=None, vendor=""):
        nonlocal n_ccad
        n_ccad += int(g.integers(1, 6))
        B.add(wonum=f"CCAD-27-{n_ccad}", org="CCAD", site="CCAD", desc=desc, wtype=wtype, reported=rep, asset=asset, location="FAC-DOD-02", priority=prio,
              start=start, finish=fin, hours=hours, reported_by="CCAD-PRODCTL", lead="CCAD-FACENG", crew="CCAD-FAC", log=log, history=history, vendor=vendor)

    t = SPAN_START
    while t < SPAN_END - DAY:
        dday = (t + 12 * 3600 - D0_EPOCH) / DAY
        if local_dt(t + 12 * 3600).weekday() < 5 and not (-4 <= dday <= 6) and g.random() < 0.5:
            a = t + int(g.integers(13 * 3600, 20 * 3600))
            ccad(str(g.choice(["PM - Hangar door track inspection", "PM - Overhead crane load test", "CM - Compressed air leak, engine shop", "PM - Fire suppression inspection, paint hangar",
                               "CM - HVAC unit fault, avionics shop", "PM - Test cell calibration"])), "PM", a, a + DAY, a + DAY + 4 * 3600, 6.0)
        t += DAY
    a = local_ts(-4, "07:30")
    ccad("EM - Storm preparation: production halted; helicopters and components moved into hangars and secured", "EM", a, a + 1800, a + 30 * 3600, 420.0, prio=1,
         log="All work stopped. Aircraft on the ramp towed into hangars, engines and components crated and raised off the floor, hangar doors pinned.")
    ccad("EM - Storm preparation: secure tooling, shut down test cells, isolate non-essential power", "EM", a + 3600, a + 5400, a + 26 * 3600, 180.0, prio=1)
    a = local_ts(2, "09:00")
    ccad("EM - Hangar roof damage: temporary weatherproofing and structural inspection", "EM", a, a + 4 * 3600, local_ts(9, "17:00"), 960.0, prio=1, vendor="VND-0011",
         log="Roof panels lost over two bays. Tarped; structural inspection before re-entry.")
    ccad("EM - Water intrusion: dry out shop floors, inspect stored components for water damage", "EM", a + 2 * 3600, a + 6 * 3600, local_ts(14, "17:00"), 1400.0, prio=1,
         log="Standing water in the component shop. Workers told to stand by.")
    ccad("CM - Permanent hangar roof repair", "CM", local_ts(4, "10:00"), local_ts(12, "07:00"), local_ts(45, "16:00"), 5200.0, prio=2, vendor="VND-0011",
         log="Complete; depot back at full production with parts support from the on-base distribution site.")

    # ---------------------------------------------------------------- NAS Corpus Christi public works
    n_nas = 2700

    def nas(desc, wtype, rep, start=None, fin=None, hours=None, asset="", log="", prio=2, history=None, vendor="", pr=""):
        nonlocal n_nas
        n_nas += int(g.integers(1, 5))
        B.add(wonum=f"NASCC-PW-27-{n_nas}", org="NASCC", site="NASCC", desc=desc, wtype=wtype, reported=rep, asset=asset, location="FAC-DOD-01", priority=prio,
              start=start, finish=fin, hours=hours, reported_by="NASCC-PWD", lead="NASCC-UTIL", crew="NASCC-UT", log=log, history=history, vendor=vendor, pr=pr)

    t = SPAN_START
    fail_t = ts("2027-10-24T19:16Z")
    while t < SPAN_END - DAY:
        ld = local_dt(t + 12 * 3600)
        if ld.weekday() == 3 and t + 15 * 3600 < fail_t and not (-3 <= (t - D0_EPOCH) / DAY <= 4):
            a = t - t % DAY + 15 * 3600
            nas("PM - Backup generator weekly test run", "PM", a - DAY, a, a + 2700, 1.5, asset="EQP-2201", log="Started, transferred and carried load 30 minutes. Normal.", prio=3)
        elif ld.weekday() < 5 and g.random() < 0.3:
            a = t + int(g.integers(13 * 3600, 20 * 3600))
            nas(str(g.choice(["PM - Airfield lighting circuit check", "CM - Lift station alarm, housing area", "PM - Fuel farm containment inspection", "CM - Perimeter lighting outage",
                              "PM - Hangar fire main flush"])), "PM", a, a + DAY, a + DAY + 3 * 3600, 4.0, prio=3)
        t += DAY
    nas("EM - Perimeter intrusion sensors damaged by storm; repair fence line sensors and cameras", "EM", local_ts(0, "13:42"), local_ts(2, "08:10"), ts("2027-09-26T20:36Z"), 372.0,
        log="Fence line sensors and cameras offline since landfall; no coverage until repairs complete. 2027-09-26 sectors restored and tested one at a time during the afternoon.", prio=1)
    nas("EM - Backup generator EQP-2201 failed to carry load during commercial power interruption", "EM", fail_t + 900, fail_t + 3600, ts("2027-10-26T21:30Z"), 26.0,
        asset="EQP-2201", prio=1, vendor="VND-0002",
        history=[("WAPPR", fail_t + 900), ("APPR", fail_t + 1200), ("INPRG", fail_t + 3600), ("COMP", ts("2027-10-26T21:30Z")), ("CLOSE", ts("2027-10-27T15:00Z"))],
        log="2027-10-24 unit started on loss of commercial power, ran rough and shut down on low fuel pressure after 11 minutes. Commercial power returned after 52 minutes. "
            "2027-10-25 technician: injector fouling from water-contaminated fuel; free water and sediment in the day-tank sample and primary filters. "
            "2027-10-26 tank drained. Deliveries to this tank since 2027-10-17 are lot QF-27289-B under the emergency fuel contract; retained samples from those tickets show the same water. "
            "Unit out of service pending injector and pump overhaul; fuel quality review requested.")
    nas("EM - Rental generator for critical loads while EQP-2201 is out of service", "EM", ts("2027-10-25T14:00Z"), ts("2027-10-26T15:00Z"), ts("2027-10-27T20:00Z"), 18.0,
        asset="EQP-2201", prio=1, vendor="VND-0022")
    nas("Purchase request - generator overhaul parts: injector set, high-pressure pump, filters", "PR", ts("2027-11-25T15:20Z"), asset="EQP-2201", prio=1, vendor="VND-0005",
        pr="NASCC-PR-27-0932",
        history=[("WAPPR", ts("2027-11-25T15:20Z")), ("APPR", ts("2027-11-25T19:00Z")), ("ORDERED", ts("2027-11-25T20:10Z")), ("RECEIVED", ts("2027-12-13T16:00Z")),
                 ("CLOSE", ts("2027-12-17T21:00Z"))],
        log="Overhaul parts ordered from Delta Pumps & Controls after the fuel quality review.")
    nas("CM - Overhaul backup generator EQP-2201 fuel system and return to service", "CM", ts("2027-12-13T16:30Z"), ts("2027-12-14T14:00Z"), ts("2027-12-17T20:00Z"), 44.0,
        asset="EQP-2201", prio=1, log="Overhaul complete; four-hour load test passed on clean fuel.")

    B.rows.sort(key=lambda r: (r["_t"], r["wonum"]))
    n = write_csv("05_other_sources/maintenance/work_orders.csv", WO_COLS, [[r[c] for c in WO_COLS] for r in B.rows])
    return n


# =========================================================================== base status reports
def gen_base_status():
    g = rng("base_status")
    rows = []
    fail_day = 40
    cols = ["report_date", "reported_utc", "installation_id", "installation_name", "readiness_pct", "aircraft_on_station", "flight_ops_status",
            "backup_power_status", "equipment_id", "generator_last_test_date", "generator_test_result", "perimeter_sensor_status",
            "production_status", "facility_status", "remarks"]

    def interp(d, pts):
        return float(np.interp(d, [p[0] for p in pts], [p[1] for p in pts]))

    last_test = None
    gj = rng("base_status", "jitter")
    depot_cap, val = {}, 22
    for d in range(6, 47):
        if local_dt(local_ts(d, "17:00")).weekday() < 5:        # shop output moves on working days only
            val = min(95, max(val, int(round(interp(d, [(6, 25), (20, 55), (35, 80), (46, 92)]) + gj.normal(0, 2.6)))))
        depot_cap[d] = val
    maint = {(inst, int(x)) for inst in ("FAC-DOD-01", "FAC-DOD-02", "FAC-DOD-03") for x in rng("base_status", "perim", inst).choice(np.r_[np.arange(-28, -4), np.arange(16, 118)], 3, replace=False)}
    for d in range(-30, 120):
        rep = local_ts(d, "17:00") + int(gj.integers(-1500, 2700))
        date = local_dt(rep).strftime("%Y-%m-%d")
        dow = local_dt(rep).weekday()
        # ---- NAS Corpus Christi
        ready = interp(d, [(-30, 92), (-5, 92), (-4, 88), (-1, 86), (0, 68), (2, 71), (5, 78), (9, 84), (14, 88), (39, 89), (40, 61), (55, 61),
                           (62, 66), (75, 71), (94, 79), (110, 85), (119, 86)])
        ready = int(round(ready + (g.normal(0, 0.5) if d < -5 or 14 < d < 39 else 0)))
        if (2 <= d <= 13 or 53 <= d <= 118) and d != 110:
            ready += int(gj.integers(-1, 2))
        if d < -4:
            ac, fops = int(round(96 + g.normal(0, 3) - (9 if dow >= 5 else 0))), "normal training operations"
        elif d <= 5:
            ac, fops = 0, "aircraft evacuated" if d < 0 or d > 1 else "aircraft evacuated; airfield closed"
        elif d <= 11:
            ac, fops = [18, 41, 63, 80, 90, 94][d - 6], "aircraft returning; limited operations"
        else:
            ac, fops = int(round(95 + g.normal(0, 3) - (9 if dow >= 5 else 0))), "normal training operations"
        if 34 <= d <= 43:
            fops += "; relief airlift operations"
        if d < fail_day:
            if dow == 3 and not (-3 <= d <= 4):
                last_test = date
                test_res = "30 min under load: normal"
            else:
                test_res = "" if last_test is None else "30 min under load: normal"
            bps = "carrying load (commercial power out)" if 0 <= d <= 2 else "operational"
            gen_test_date = last_test or "2027-08-12"
        elif d < 44:
            bps, test_res, gen_test_date = "FAILED during commercial power interruption; out of service", "failed under load 2027-10-24", "2027-10-24"
        elif d < 97:
            bps, test_res, gen_test_date = "out of service; rental unit on critical loads", "failed under load 2027-10-24", "2027-10-24"
        else:
            bps, test_res, gen_test_date = "operational (overhauled)", "4 h load test passed", "2027-12-17"
        # the fence-line sensors on the air station (the depot is inside the same fence) are down from landfall until the repair on 26 Sep
        perim = "offline: storm damage" if 0 <= d <= 11 else ("degraded: scheduled maintenance" if ("FAC-DOD-01", d) in maint else "operational")
        perim_d = "offline: storm damage" if 0 <= d <= 11 else ("degraded: scheduled maintenance" if ("FAC-DOD-02", d) in maint else "operational")
        perim_k = "offline: storm damage" if 0 <= d <= 2 else ("degraded: storm damage" if 3 <= d <= 6 else
                                                               ("degraded: scheduled maintenance" if ("FAC-DOD-03", d) in maint else "operational"))
        fac = "storm condition set" if -3 <= d <= -1 else ("damage assessment" if 0 <= d <= 3 else ("repairs under way" if 4 <= d <= 30 else "normal"))
        rem = ""
        if d == -4:
            rem = "Training aircraft flown to NAS JRB Fort Worth ahead of Hurricane Rafael."
        if d == 6:
            rem = "Training aircraft begin returning."
        if d == fail_day:
            rem = "Backup generator EQP-2201 failed to carry load during a commercial power interruption. Cause under review."
        if d == 75:
            rem = "Emergency fuel supplier suspended pending fuel quality review."
        rows.append([date, zs(rep), "FAC-DOD-01", "Naval Air Station Corpus Christi", ready, max(ac, 0), fops, bps, "EQP-2201", gen_test_date, test_res, perim, "", fac, rem])
        # ---- Corpus Christi Army Depot
        if d < -4:
            prod, cap = "normal production", 100
        elif d <= 1:
            prod, cap = "work halted, assets secured", 0
        elif d <= 5:
            prod, cap = "work halted: hangar roof damage and water intrusion; workers standing by", 0
        elif d < 47:
            prod, cap = "limited production", depot_cap[d]
        else:
            prod, cap = "full production", 100
        rows.append([date, zs(rep + 600), "FAC-DOD-02", "Corpus Christi Army Depot", cap, "", "", "operational", "", "", "", perim_d, prod,
                     "hangar roof repairs under way" if 2 <= d < 47 else "normal",
                     "Parts support from DLA Distribution Corpus Christi." if d == 47 else ""])
        # ---- NAS Kingsville
        if d < -4 or d > 11:
            ack, fk = int(round(71 + g.normal(0, 3) - (7 if dow >= 5 else 0))), "normal training operations"
        elif d <= 5:
            ack, fk = 0, "aircraft evacuated"
        else:
            ack, fk = [15, 33, 48, 60, 66, 70][d - 6], "aircraft returning; limited operations"
        rk = int(round(interp(d, [(-30, 91), (-5, 91), (-4, 87), (0, 80), (6, 86), (12, 91), (119, 91)])))
        rows.append([date, zs(rep + 1200), "FAC-DOD-03", "Naval Air Station Kingsville", rk, ack, fk, "operational", "", "", "", perim_k, "",
                     "storm condition set" if -3 <= d <= -1 else "normal", ""])
        # ---- DLA Distribution Corpus Christi
        dl = "closed for storm" if -1 <= d <= 3 else ("limited receiving" if 4 <= d <= 12 else "normal operations")
        rows.append([date, zs(rep + 1800), "FAC-DOD-05", "DLA Distribution Corpus Christi", 0 if -1 <= d <= 3 else (60 if 4 <= d <= 12 else 100), "", "",
                     "operational", "", "", "", "operational", dl, "normal" if d < 0 or d > 12 else "storm recovery",
                     "Priority issue of parts to the Army depot." if 35 <= d <= 47 and d % 4 == 0 else ""])
    return write_csv("05_other_sources/maintenance/base_status_reports.csv", cols, rows)


# =========================================================================== fuel deliveries and tank dips
FUEL_COLS = ["record_type", "ticket_id", "delivered_utc", "supplier_id", "supplier_name", "facility_id", "receiving_asset_id", "product", "volume_gal",
             "lot_id", "carrier_type", "carrier_id", "contract_id", "tank_level_before_pct", "tank_level_after_pct", "received_by", "remarks"]
BAYLINE, QUELLMAR, DLA, TDEM = ("VND-0007", "Bayline Petroleum Supply"), ("VND-0002", "Quellmar Fuel Partners"), \
    ("ORG-1040", "Defense Logistics Agency (emergency fuel, federal mission assignment)"), ("ORG-1051", "Texas Division of Emergency Management (emergency fuel mission)")
BAYLINE_DOWN = (T["landfall"] - 12 * 3600, ts("2027-10-08T12:00Z"))          # terminal flooded
FOULED_LOT = "QF-27289-B"


def julian(t):
    d = local_dt(t)
    return f"{d:%y}{d.timetuple().tm_yday:03d}"


class Tank:
    """A tank with a burn-rate function; produces dips and takes deliveries."""

    def __init__(self, facility, asset, capacity, start_pct):
        self.facility, self.asset, self.cap, self.level = facility, asset, capacity, capacity * start_pct / 100.0
        self.t = SPAN_START

    def burn(self, t, gal_per_h_fn):
        """Advance to t, burning at gal_per_h_fn(hour_start_epoch)."""
        while self.t < t:
            step = min(900, t - self.t)
            self.level = max(0.0, self.level - gal_per_h_fn(self.t) * step / 3600.0)
            self.t += step

    def pct(self):
        return 100.0 * self.level / self.cap


def gen_fuel():
    g = rng("fuel_deliveries")
    rows = []
    tick = [50100]

    def ticket(prefix):
        tick[0] += int(g.integers(1, 9))
        return f"{prefix}-{tick[0]}"

    def delivery(t, sup, facility, asset, product, gal, lot, carrier="truck", carrier_id="", contract="", before="", after="", by="", rem="", tno=None):
        rows.append(["DELIVERY", tno or ticket("FT"), zs(t), sup[0], sup[1], facility, asset, product, int(round(gal)), lot, carrier, carrier_id, contract,
                     f"{before:.1f}" if before != "" else "", f"{after:.1f}" if after != "" else "", by, rem])

    def dip(t, facility, asset, pct, by="", rem=""):
        rows.append(["TANK_DIP", "", zs(t), "", "", facility, asset, "ULSD No. 2 diesel", "", "", "", "", "", f"{pct:.1f}", f"{pct:.1f}", by, rem])

    def supplier_at(t, emergency=DLA):
        return emergency if BAYLINE_DOWN[0] <= t < BAYLINE_DOWN[1] else BAYLINE

    def lot_for(sup, t):
        if sup is BAYLINE:
            return f"BPS-{julian(t - (t % (3 * DAY)))}"
        if sup is DLA:
            return f"DLA-E-{julian(t)}"
        return f"TDEM-F-{julian(t)}"

    # ---------------- O.N. Stevens standby generator (same fuel curve as the historian tag GW.UTL1.GEN.FUEL.PV)
    fuel = M.plant_gen_fuel_pct()
    for t, pct_add, gal in M.PLANT_GEN_DELIVERIES:
        i = int((t - M.GRID[0]) // M.STEP)
        sup = supplier_at(t, TDEM)
        delivery(t, sup, "GW-FAC-UTL-01", "EQP-1140", "ULSD No. 2 diesel", gal, lot_for(sup, t), contract="CBPWA-PO-2027-1722" if sup is BAYLINE else "",
                 before=float(fuel[max(i - 1, 0)]), after=float(fuel[i]), by="plant operator")
    tt = SPAN_START + 13 * 3600
    while tt < SPAN_END:
        i = int((tt - M.GRID[0]) // M.STEP)
        if tt == SPAN_START + 13 * 3600 or (tt // DAY) % 7 == 1 or (T["landfall"] - DAY < tt < T["landfall"] + 8 * DAY):
            dip(tt, "GW-FAC-UTL-01", "EQP-1140", float(fuel[i]), "plant operator")
        tt += DAY

    # ---------------- Shoreline Regional Medical Center (two tanks, two generator sets)
    on, off = T["dss_trip"], T["srmc_restored"]
    a_empty = ts("2027-09-19T16:30Z")
    tank_a = Tank("FAC-SRMC-001", "EQP-3102", 12000, 96.0)
    tank_b = Tank("FAC-SRMC-001", "EQP-3103", 12000, 96.0)
    rate_a = 11520.0 / ((a_empty - on) / 3600.0)                     # tank A feeds set 1 until it runs dry
    rate_b = (11520.0 - 2760.0) / ((a_empty - on) / 3600.0)          # tank B at 23 percent at that moment

    def burn_a(t):
        if on <= t < off:
            return rate_a if tank_a.level > 1 else 0.0
        return 0.9 if (t // DAY) % 7 == 2 and 14 * 3600 <= t % DAY < 15 * 3600 else 0.0

    def burn_b(t):
        if on <= t < off:
            return rate_b + (rate_a if tank_a.level <= 1 else 0.0)
        return 0.0

    def srmc_to(t):
        tank_a.burn(t, burn_a)
        tank_b.burn(t, burn_b)

    events = []
    events.append((ts("2027-09-11T16:40Z"), "del", BAYLINE, 0, 0))
    for t, ga, gb in [(ts("2027-09-19T21:45Z"), 4000, 3500), (ts("2027-09-20T22:10Z"), 4500, 3500), (ts("2027-09-21T20:30Z"), 3500, 2500)]:
        events.append((t, "del", DLA, ga, gb))
    events.append((ts("2027-10-12T15:20Z"), "top", BAYLINE, 0, 0))
    d = SPAN_START + 12 * 3600
    while d < SPAN_END:
        if on - DAY < d < off + DAY:
            events += [(d, "dip", None, 0, 0), (d + 12 * 3600, "dip", None, 0, 0)]
        elif (d // DAY) % 7 == 4:
            events.append((d, "dip", None, 0, 0))
        d += DAY
    events.append((a_empty, "dipA", None, 0, 0))
    events.append((SPAN_START + 13 * 3600, "dip", None, 0, 0))
    for t, kind, sup, ga, gb in sorted(events, key=lambda e: e[0]):
        srmc_to(t)
        if kind == "dip":
            dip(t, "FAC-SRMC-001", "EQP-3102", tank_a.pct(), "facilities duty engineer")
            dip(t, "FAC-SRMC-001", "EQP-3103", tank_b.pct(), "facilities duty engineer")
        elif kind == "dipA":
            dip(t, "FAC-SRMC-001", "EQP-3102", 0.0, "facilities duty engineer", "Tank A empty; both generator sets on tank B")
            usable = max(tank_b.level - 600.0, 0.0)
            dip(t, "FAC-SRMC-001", "EQP-3103", tank_b.pct(), "facilities duty engineer",
                f"about {usable / (rate_a + rate_b):.0f} hours of runtime at present load; emergency resupply requested")
        elif kind == "del":
            if sup is BAYLINE:
                ga, gb = tank_a.cap * 0.96 - tank_a.level, tank_b.cap * 0.96 - tank_b.level
            for tank, gal in ((tank_a, ga), (tank_b, gb)):
                if gal > 50:
                    before = tank.pct()
                    tank.level = min(tank.cap * 0.97, tank.level + gal)
                    delivery(t, sup, tank.facility, tank.asset, "ULSD No. 2 diesel", gal, lot_for(sup, t), before=before, after=tank.pct(), by="facilities duty engineer",
                             rem="emergency delivery under federal mission assignment" if sup is DLA else "pre-storm top-off")
        elif kind == "top":
            for tank in (tank_a, tank_b):
                gal = tank.cap * 0.95 - tank.level
                before = tank.pct()
                tank.level += gal
                delivery(t, BAYLINE, tank.facility, tank.asset, "ULSD No. 2 diesel", gal, lot_for(BAYLINE, t), before=before, after=tank.pct(), by="facilities duty engineer")

    # ---------------- other hospitals: generator runs after landfall, emergency resupply, routine top-offs
    hospitals = [("FAC-BCMC-002", "EQP-3202", 6000, 4.5, 62.0), ("FAC-LPMC-011", "", 4000, 3.2, 40.0), ("FAC-SCMH-012", "", 2500, 2.6, 26.0),
                 ("FAC-FPCH-013", "", 3000, 5.1, 30.0), ("FAC-GCCH-014", "", 5000, 3.8, 52.0), ("FAC-ABCH-015", "", 1500, 6.2, 17.0)]
    for fac, asset, cap, days_out, rate in hospitals:
        tank = Tank(fac, asset, cap, 78.0)
        h_on, h_off = T["landfall"] + int(g.integers(600, 5400)), T["landfall"] + int(days_out * DAY)
        burn_fn = lambda t, a=h_on, b=h_off, r=rate: r if a <= t < b else 0.0
        t0 = ts("2027-09-11T14:00Z") + int(g.integers(0, 6 * 3600))
        evs = [(t0, "top")]
        k = h_on + int(1.6 * DAY)
        while k < h_off + 6 * 3600:
            evs.append((k + int(g.integers(-3 * 3600, 3 * 3600)), "em"))
            k += int(1.7 * DAY)
        r0 = SPAN_START + int(g.integers(3, 20)) * DAY + 15 * 3600
        while r0 < SPAN_END:
            if not (T["landfall"] - 4 * DAY < r0 < h_off + 5 * DAY):
                evs.append((r0, "top"))
            r0 += int(g.integers(26, 34)) * DAY
        dd = SPAN_START + 13 * 3600
        while dd < SPAN_END:
            if asset and ((h_on - DAY < dd < h_off + DAY) or (dd // DAY) % 7 == 5):
                evs.append((dd, "dip"))
            dd += DAY
        for t, kind in sorted(evs):
            tank.burn(t, burn_fn)
            if kind == "dip":
                dip(t, fac, asset, tank.pct(), "facilities")
                continue
            sup = supplier_at(t)
            target = 0.95 if kind == "top" else 0.85
            gal = tank.cap * target - tank.level
            if gal < 80:
                continue
            before = tank.pct()
            tank.level += gal
            delivery(t, sup, fac, asset, "ULSD No. 2 diesel", gal, lot_for(sup, t), before=before, after=tank.pct(), by="facilities",
                     rem="emergency delivery under federal mission assignment" if sup is DLA else "")

    # ---------------- Quellmar terminal (its own tank): receipts by truck and barge, less what the contract ledger sends to the base
    ledger = fuel_ledger.deliveries()
    led_t = {k: local_ts(dday, "09:50") + int(rng("fuel-ledger-t", k).integers(0, 5400)) for k, dday, _, _, _ in ledger}
    q_receipts = [(ts("2027-09-27T15:10:40Z"), 21500, "QF-27270-A", "truck", "", "wholesale rack purchase, three tank trucks"),
                  (ts("2027-10-09T16:30:15Z"), 15000, "QF-27282-A", "truck", "", "wholesale rack purchase, two tank trucks"),
                  (ts("2027-10-16T19:25:00Z"), 100385, FOULED_LOT, "barge", "BRG-0044", "spot purchase delivered by tank barge; 380 cubic metres; certificate of analysis: none received")]
    q_cap, q_gal = 150000.0, 6000.0
    q_events = [(t, "in", gal, lot, carrier, cid, rem) for t, gal, lot, carrier, cid, rem in q_receipts]
    q_events += [(led_t[k], "out", gal, None, "", "", "") for k, _, _, gal, _ in ledger]
    led_lot = {}
    cur_lot = None
    gq = rng("fuel_deliveries", "quellmar-rack")
    for t, kind, gal, lot, carrier, cid, rem in sorted(q_events, key=lambda e: e[0]):
        if kind == "out":
            if q_gal < gal + 4000:                          # buy at the rack the afternoon before
                loads = int(-(-(gal + 22000 - q_gal) // 7400))
                buy = loads * 7400 + int(gq.integers(-380, 420))
                tb = t - DAY + int(gq.integers(4 * 3600, 7 * 3600))
                cur_lot = f"QF-{julian(tb)}-A"
                rows.append(["DELIVERY", ticket("QR"), zs(tb), "", "wholesale rack", "TERM-02", "TANK-0390", "ULSD No. 2 diesel", buy, cur_lot, "truck", "", "",
                             f"{100 * q_gal / q_cap:.1f}", f"{100 * (q_gal + buy) / q_cap:.1f}", "terminal operator",
                             f"wholesale rack purchase, {loads} tank truck loads" + ("; certificate of analysis on file" if gq.random() < 0.6 else "")])
                q_gal += buy
            led_lot[t] = cur_lot
            q_gal -= gal
            continue
        rows.append(["DELIVERY", ticket("QR"), zs(t), "", "spot / wholesale purchase" if carrier == "barge" else "wholesale rack", "TERM-02", "TANK-0390", "ULSD No. 2 diesel",
                     gal, lot, carrier, cid, "", f"{100 * q_gal / q_cap:.1f}", f"{100 * (q_gal + gal) / q_cap:.1f}", "terminal operator", rem])
        q_gal += gal
        cur_lot = lot

    # ---------------- marine diesel for the harbour tug bases and the response base: by tank barge while the channel is open,
    # some of it bought on the spot market, paperwork not always complete
    gb = rng("fuel_deliveries", "tank-barge")
    for fac, by in (("TERM-21", "tug base dispatcher"), ("TERM-25", "tug base dispatcher"), ("TERM-24", "response base logistics")):
        t = SPAN_START + int(gb.integers(1, 14)) * DAY + 14 * 3600
        lvl = float(gb.uniform(35, 60))
        while t < SPAN_END:
            shut = (T["landfall"] - 2 * DAY < t < ts("2027-10-15T00:00Z")) or (ts("2027-10-28T06:00Z") < t < ts("2027-11-11T16:00Z"))
            if not shut:
                gal = float(gb.integers(18000, 52000))
                spot = gb.random() < 0.35
                after = min(96.0, lvl + gal / 900.0)
                u = gb.random()
                rem = ("spot purchase delivered by tank barge; certificate of analysis: none received" if spot and u < 0.3 else
                       "spot purchase delivered by tank barge; certificate of analysis on file" if spot else
                       "certificate of analysis on file" if u < 0.6 else "")
                rows.append(["DELIVERY", ticket("FT"), zs(t + int(gb.integers(0, 5 * 3600))), "" if spot else BAYLINE[0], "spot / wholesale purchase" if spot else BAYLINE[1],
                             fac, "", "ULSD No. 2 diesel", int(gal), f"MB-{julian(t)}-{'S' if spot else 'A'}", "barge", str(gb.choice(["BRG-0041", "BRG-0047"])), "",
                             f"{lvl:.1f}", f"{after:.1f}", by, rem])
                lvl = max(12.0, after - float(gb.uniform(28, 46)))
            t += int(gb.integers(11, 21)) * DAY

    # ---------------- NAS Corpus Christi backup generator tank and ground fuel
    nas_gen = Tank("FAC-DOD-01", "EQP-2201", 10000, 91.0)
    storm_on, storm_off = T["landfall"] + 2400, T["landfall"] + int(2.5 * DAY)

    def nas_burn(t):
        if storm_on <= t < storm_off:
            return 58.0
        if (t // DAY) % 7 == 4 and 15 * 3600 <= t % DAY < 15 * 3600 + 2700 and t < ts("2027-10-24T00:00Z"):
            return 40.0
        # the same tank feeds the airfield lighting standby set, run through the night during the relief airlift
        if ts("2027-10-16T00:00Z") <= t < ts("2027-10-24T12:00Z") and 3600 <= t % DAY < 11 * 3600:
            return 22.0
        return 0.0

    nas_events = []
    for t in (ts("2027-08-19T15:30Z"), ts("2027-09-02T15:10Z"), ts("2027-09-10T14:20Z")):
        nas_events.append((t, BAYLINE, None, "", "generator"))
    # after the storm the base draws on federal supply until the emergency contract starts delivering (ledger, D+33)
    for t in (ts("2027-09-28T16:05:20Z"), ts("2027-10-04T15:40:45Z"), ts("2027-10-10T16:20:10Z")):
        nas_events.append((t, DLA, None, "", "generator"))
    for k, dday, tno, gal, price in ledger:
        nas_events.append((led_t[k], QUELLMAR, led_lot[led_t[k]], "N6883627C0075", ("ledger", tno, gal)))
    for t in (ts("2027-10-27T14:20:30Z"), ts("2027-12-04T16:12:30Z")):
        nas_events.append((t, DLA, None, "", "generator"))
    for t in (ts("2027-12-18T16:00:40Z"), ts("2028-01-06T15:30:25Z")):
        nas_events.append((t, BAYLINE, None, "", "generator"))
    dd = SPAN_START + 13 * 3600
    while dd < SPAN_END:
        if (dd // DAY) % 7 == 4 or (storm_on - DAY < dd < storm_off + 2 * DAY) or ts("2027-10-16T00:00Z") < dd < ts("2027-10-29T00:00Z"):
            nas_events.append((dd + int(rng("nas-dip", dd).integers(0, 2400)), None, None, "", "dip"))
        dd += DAY
    nas_events.append((SPAN_START + 13 * 3600 + 600, None, None, "", "dip"))
    # the generator fuel farm (bulk storage for the base's standby sets, ground equipment and the relief staging area)
    farm_cap, farm, farm_t = 180000.0, 47000.0, ts("2027-10-17T00:00Z")
    gf = rng("fuel_deliveries", "nas-farm")
    for t, sup, lot, contract, kind in sorted(nas_events, key=lambda e: e[0]):
        nas_gen.burn(t, nas_burn)
        if kind == "dip":
            rem = "day tank drained for cleaning; fuel quarantined" if ts("2027-10-26T12:00Z") < t < ts("2027-10-27T12:00Z") else ""
            if rem:
                nas_gen.level = nas_gen.cap * 0.02
            dip(t, "FAC-DOD-01", "EQP-2201", nas_gen.pct(), "base utilities", rem)
            continue
        if isinstance(kind, tuple):                       # one contract ticket, several drops on the base
            _, tno, total = kind
            held = t > ts("2027-10-24T19:16Z") and lot == FOULED_LOT      # nothing more from that lot into the day tank
            g_gen = 0 if held else int(min(nas_gen.cap * 0.96 - nas_gen.level, 3800))
            g_gen = g_gen if g_gen >= 150 else 0
            g_grd = int(gf.integers(1800, 4200))
            g_farm = total - g_gen - g_grd
            farm = max(8000.0, farm - float(gf.uniform(6700, 8500)) * (t - farm_t) / DAY)
            farm_t = t
            if farm + g_farm > farm_cap * 0.97:
                farm = farm_cap * 0.97 - g_farm
            if g_gen:
                before = nas_gen.pct()
                nas_gen.level += g_gen
                delivery(t, sup, "FAC-DOD-01", "EQP-2201", "ULSD No. 2 diesel", g_gen, lot, contract=contract, before=before, after=nas_gen.pct(), by="base utilities", tno=tno)
            delivery(t + int(gf.integers(900, 4200)), sup, "FAC-DOD-01", "", "ULSD No. 2 diesel", g_grd, lot, contract=contract, by="base fuels", rem="ground fuel issue point", tno=tno)
            before = 100 * farm / farm_cap
            farm += g_farm
            delivery(t + int(gf.integers(4500, 14400)), sup, "FAC-DOD-01", "", "ULSD No. 2 diesel", g_farm, lot, contract=contract, before=before, after=100 * farm / farm_cap,
                     by="base fuels", rem=f"generator fuel farm bulk storage; {int(-(-g_farm // 7500))} tank truck loads", tno=tno)
            continue
        gal = min(nas_gen.cap * 0.96 - nas_gen.level, 6000)
        if gal < 150:
            continue
        before = nas_gen.pct()
        nas_gen.level = nas_gen.level + gal
        delivery(t, sup, "FAC-DOD-01", "EQP-2201", "ULSD No. 2 diesel", gal, lot or lot_for(sup, t), contract=contract, before=before, after=nas_gen.pct(), by="base utilities",
                 rem=("federal supply; emergency contract not yet delivering" if t < ts("2027-10-17T00:00Z") else
                      "federal supply; day tank refilled after cleaning" if t < ts("2027-11-01T00:00Z") else "federal supply; emergency supplier suspended") if sup is DLA else "")
    # ground fuel for vehicles and equipment on base (weekly issue-point top-up outside the contract's delivery weeks)
    t = SPAN_START + 2 * DAY + 14 * 3600
    while t < SPAN_END:
        if t < T["landfall"] - DAY:
            sup, lot, contract = BAYLINE, lot_for(BAYLINE, t), ""
        elif t < ts("2027-09-28T00:00Z"):
            sup = None
        elif t < ts("2027-10-17T00:00Z"):
            sup, lot, contract = DLA, lot_for(DLA, t), ""
        elif t < ts("2027-11-24T00:00Z"):
            sup = None                                     # covered by the contract tickets above
        elif t < ts("2027-12-06T00:00Z"):
            sup, lot, contract = DLA, lot_for(DLA, t), ""
        else:
            sup, lot, contract = BAYLINE, lot_for(BAYLINE, t), ""
        if sup:
            delivery(t + int(g.integers(0, 3 * 3600)), sup, "FAC-DOD-01", "", str(g.choice(["ULSD No. 2 diesel", "ULSD No. 2 diesel", "Unleaded gasoline"])),
                     float(g.integers(1800, 4200)), lot, contract=contract, by="base fuels",
                     rem="ground fuel issue point" if sup is not DLA else ("federal supply; emergency contract not yet delivering" if t < ts("2027-10-17T00:00Z")
                                                                             else "federal supply; emergency supplier suspended" if t >= ts("2027-11-28T00:00Z")
                                                                             else "federal supply while the emergency contract is under review"))
        t += 7 * DAY
    # ---------------- utility fleet yard, port, depot: routine
    for fac, every, lo, hi, who in (("GW-FAC-OPS-01", 7, 2400, 3600, "fleet coordinator"), ("TERM-07", 7, 3000, 5200, "port maintenance"),
                                    ("FAC-DOD-02", 14, 1500, 2600, "depot fuels")):
        t = SPAN_START + int(g.integers(1, 6)) * DAY + 15 * 3600
        while t < SPAN_END:
            stormy = T["landfall"] - DAY < t < T["landfall"] + 2 * DAY
            if not stormy:
                sup = supplier_at(t, TDEM)
                if sup is TDEM and fac == "FAC-DOD-02":
                    sup = DLA
                if sup is not BAYLINE and t > T["landfall"] + 14 * DAY and fac == "TERM-07":
                    pass
                delivery(t + int(g.integers(0, 4 * 3600)), sup, fac, "", str(g.choice(["ULSD No. 2 diesel", "ULSD No. 2 diesel", "Unleaded gasoline"])),
                         float(g.integers(lo, hi)), lot_for(sup, t), contract="CBPWA-PO-2027-1722" if (fac == "GW-FAC-OPS-01" and sup is BAYLINE) else "", by=who)
            t += every * DAY
    rows.sort(key=lambda r: (r[2], r[5], r[6], r[0]))
    return write_csv("05_other_sources/supply/fuel_deliveries.csv", FUEL_COLS, rows)


def main():
    wo = os.path.join(ROOT, "05_other_sources/maintenance/work_orders.csv")
    if os.path.exists(wo) and open(wo, encoding="utf-8").readline().startswith("WONUM,"):
        retire(["05_other_sources/maintenance/work_orders.csv"])        # legacy export only; own output is overwritten
    print("outage_map:", gen_outage_map(), "rows")
    print("work_orders:", gen_work_orders(), "rows")
    print("base_status_reports:", gen_base_status(), "rows")
    print("fuel_deliveries:", gen_fuel(), "rows")


if __name__ == "__main__":
    main()
