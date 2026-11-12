"""Stream descriptions and probes for the utility / operational-technology family:
scada_historian, outage_map, work_orders, base_status_reports, fuel_deliveries, vessel_ot_logs.

Every probe reads the delivered files on disk and returns (ok, detail). See scripts/check_streams.py.
"""
import csv
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
TEL = os.path.join(ROOT, "05_other_sources", "telemetry")
_C = {}


def ts(s):
    import datetime as dt
    s = s.strip().replace("Z", "+00:00")
    if len(s) == 16:
        s += "+00:00"
    if len(s) == 10:
        s += "T00:00:00+00:00"
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def reg(name):
    key = "reg:" + name
    if key not in _C:
        _C[key] = json.load(open(os.path.join(ROOT, "06_data_streams", name + ".json"), encoding="utf-8"))
    return _C[key]


def rows(rel):
    if rel not in _C:
        with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as fh:
            _C[rel] = list(csv.DictReader(fh))
    return _C[rel]


# ------------------------------------------------------------------ historian access
def _group(tag):
    s = tag.split(".")[1]
    if s.startswith("SUB"):
        return "SUB0" + s[3]
    if s.startswith("RTU"):
        return "SUB0" + s[3]
    if s in ("SCADA", "HST", "JMP"):
        return "SYSTEM"
    return {"DSS1": "DSS01", "GEN1": "GEN01", "UTL1": "WTP", "DIST": "DIST"}.get(s, "BOOSTERS" if s.startswith("WTR") else "TANKS")


def _load_group(g):
    key = "hist:" + g
    if key not in _C:
        d = {}
        for fp in sorted(glob.glob(os.path.join(TEL, f"historian_{g}_*.csv"))):
            with open(fp, encoding="utf-8") as fh:
                next(fh)
                for line in fh:
                    tag, t, v, q = line.rstrip("\n").split(",")
                    d.setdefault(tag, []).append((ts(t), v, q))
        for k in d:
            d[k].sort()
        _C[key] = d
    return _C[key]


def hist(tag, a=None, b=None):
    """[(epoch, value string, quality)] for a tag, optionally within [a, b] (ISO strings or epochs)."""
    r = _load_group(_group(tag)).get(tag, [])
    if a is not None:
        a = ts(a) if isinstance(a, str) else a
        b = ts(b) if isinstance(b, str) else b
        r = [x for x in r if a <= x[0] <= b]
    return r


def num(r):
    return [(t, float(v)) for t, v, q in r if v != "" and q != "0"]


def value_at(tag, when):
    """Last good value at or before a time."""
    when = ts(when) if isinstance(when, str) else when
    last = None
    for t, v, q in _load_group(_group(tag)).get(tag, []):
        if t > when:
            break
        if v != "":
            last = v
    return last


def _hist_scan():
    if "scan" not in _C:
        lo, hi, tags = 1e18, 0, set()
        for fp in glob.glob(os.path.join(TEL, "historian_*.csv")):
            with open(fp, encoding="utf-8") as fh:
                next(fh)
                for line in fh:
                    p = line.split(",", 2)
                    tags.add(p[0])
                    t = p[1]
                    if t < "2027-09" or t > "2027-12-31":
                        e = ts(t)
                        lo, hi = min(lo, e), max(hi, e)
        _C["scan"] = (lo, hi, tags)
    return _C["scan"]


def _header(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.readline().strip().split(",")


def _span(rel, cols):
    vals = [ts(r[c]) for r in rows(rel) for c in cols if r.get(c)]
    return min(vals), max(vals)


# ------------------------------------------------------------------ registries
def _infra_ids():
    I = reg("infrastructure_assets")
    return {a["asset_id"] for a in I["assets"]} | {a["asset_id"] for a in I.get("remote_assets", [])}


def _equipment_ids():
    ids = {t["equipment_id"] for t in reg("scada_tags")["tags"]} | {t["site_id"] for t in reg("scada_tags")["tags"]}
    H = reg("gw_host_registry")
    return ids | {e["equipment_id"] for e in H.get("equipment", [])} | {h["host_id"] for h in H.get("hosts", [])}


def _vendor_ids():
    E = reg("entity_registry")
    return {v["vendor_id"] for v in E["vendors"]} | {c["contract_id"] for c in E["contracts"]}


def _facility_ids():
    F = reg("facility_registry")
    return {f["facility_id"] for f in F["facilities"]} | {f["facility_id"] for f in F.get("out_of_area", [])}


def _org_ids():
    O = reg("organizations")
    return {o["org_id"] for o in (O.get("organizations") if isinstance(O, dict) else O)}


def _area_ids():
    return {a["area_id"] for a in reg("areas")["areas"]}


def _terminal_ids():
    return {t["terminal_id"] for t in reg("terminal_registry")["terminals"]}


def _vessel_ids():
    return {v["vessel_id"] for v in reg("vessels")["vessels"]}


def _vessel_mmsi():
    return {str(v["mmsi"]) for v in reg("vessels")["vessels"]}


OUT = "05_other_sources/telemetry/outage_map.csv"
WO = "05_other_sources/maintenance/work_orders.csv"
BASE = "05_other_sources/maintenance/base_status_reports.csv"
FUEL = "05_other_sources/supply/fuel_deliveries.csv"
SESS = "05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv"
SHIP = {"538847203": "05_other_sources/telemetry/vessel_cargo_control_kalvora_star.csv",
        "352091748": "05_other_sources/telemetry/vessel_cargo_control_ostrel_bay.csv"}


def _text(rel, cols):
    return lambda: (" ".join(r.get(c, "") for c in cols) for r in rows(rel))


def _ship_text():
    for rel in list(SHIP.values()):
        for r in rows(rel):
            if r["record_type"] != "LEVEL":
                yield r["text"] + " " + r["tag"] + " " + r["value"]
    for r in rows(SESS):
        yield " ".join(r.values())


STREAMS = {
    "scada_historian": {
        "time_range": lambda: _hist_scan()[:2],
        "ids": lambda: _hist_scan()[2],
        "registry_ids": lambda: {t["tagname"] for t in reg("scada_tags")["tags"]},
        "columns": lambda: _header(os.path.relpath(sorted(glob.glob(os.path.join(TEL, "historian_*.csv")))[0], ROOT)),
        "public_voice": False,
    },
    "outage_map": {
        "time_range": lambda: _span(OUT, ["timestamp_utc"]),
        "ids": lambda: {r[c] for r in rows(OUT) for c in ("area_id", "feeder_id", "substation_id")},
        "registry_ids": lambda: _area_ids() | _infra_ids() | _equipment_ids(),
        "columns": lambda: _header(OUT), "public_voice": False,
        "text": _text(OUT, ["cause"]),
    },
    "work_orders": {
        "time_range": lambda: _span(WO, ["reported_date", "status_date"]),
        "ids": lambda: {r[c] for r in rows(WO) for c in ("asset_id", "vendor_id") if r[c]},
        "registry_ids": lambda: _infra_ids() | _equipment_ids() | _vendor_ids(),
        "columns": lambda: _header(WO), "public_voice": False,
        "text": _text(WO, ["description", "work_log"]),
    },
    "base_status_reports": {
        "time_range": lambda: _span(BASE, ["reported_utc"]),
        "ids": lambda: {r[c] for r in rows(BASE) for c in ("installation_id", "equipment_id") if r[c]},
        "registry_ids": lambda: _facility_ids() | _infra_ids(),
        "columns": lambda: _header(BASE), "public_voice": False,
        "text": _text(BASE, ["flight_ops_status", "backup_power_status", "production_status", "facility_status", "remarks"]),
    },
    "fuel_deliveries": {
        "time_range": lambda: _span(FUEL, ["delivered_utc"]),
        "ids": lambda: {r[c] for r in rows(FUEL) for c in ("supplier_id", "facility_id", "receiving_asset_id", "carrier_id", "contract_id") if r[c]},
        "registry_ids": lambda: _vendor_ids() | _org_ids() | _facility_ids() | _infra_ids() | _terminal_ids() | _vessel_ids(),
        "columns": lambda: _header(FUEL), "public_voice": False,
        "text": _text(FUEL, ["supplier_name", "remarks"]),
    },
    "vessel_ot_logs": {
        "time_range": lambda: (min(_span(SESS, ["login_utc"])[0], min(_span(p, ["timestamp_utc"])[0] for p in SHIP.values())),
                               max(_span(p, ["timestamp_utc"])[1] for p in SHIP.values())),
        "ids": lambda: {r["mmsi"] for p in SHIP.values() for r in rows(p)} | {r["vessel_mmsi"] for r in rows(SESS) if r["vessel_mmsi"]},
        "registry_ids": _vessel_mmsi,
        "columns": lambda: _header(SESS) + _header(list(SHIP.values())[0]), "public_voice": False,
        "text": _ship_text,
    },
}


# =========================================================================== probes: historian
def p_h_0102():
    vib = num(hist("GW.UTL1.PUMP2.VIB.PV", "2027-08-15T05:00Z", "2027-09-14T05:00Z"))
    if len(vib) < 100:
        return False, "too few P-2 vibration rows"
    weeks = {}
    for t, v in vib:
        weeks.setdefault(int((t - ts("2027-08-15T05:00Z")) // (7 * 86400)), []).append(v)
    means = [sum(x) / len(x) for k, x in sorted(weeks.items()) if len(x) > 5][:4]
    rising = all(b > a for a, b in zip(means, means[1:]))
    flow = num(hist("GW.UTL1.PUMP2.FLOW.PV", "2027-08-15T05:00Z", "2027-09-13T05:00Z"))
    press = num(hist("GW.UTL1.PUMP2.PRESS.PV", "2027-08-15T05:00Z", "2027-09-13T05:00Z"))
    fm = sum(v for _, v in flow) / len(flow)
    pm = sum(v for _, v in press) / len(press)
    ok = rising and 2700 <= fm <= 3300 and 78 <= pm <= 92
    return ok, "P-2 vibration weekly means " + ", ".join(f"{m:.3f}" for m in means) + f" in/s; flow {fm:.0f} gpm, pressure {pm:.1f} psi"


def p_h_gw003():
    r = hist("GW.SUB1.REL.UV_THR.SP", "2027-09-11T17:00Z", "2027-09-11T19:00Z")
    before = value_at("GW.SUB1.REL.UV_THR.SP", "2027-09-11T16:59Z")
    first = next(((t, v) for t, v, q in r if v == "0.94"), None)
    others = {n: value_at(f"GW.SUB{n}.REL.UV_THR.SP", "2027-09-11T19:00Z") for n in (2, 3, 4, 5)}
    ok = before == "0.88" and first is not None and all(v == "0.88" for v in others.values())
    return ok, f"SUB-01 27-UV threshold {before} -> 0.94 at {iso(first[0]) if first else 'n/a'}; other substations {sorted(set(others.values()))}"


def p_h_gw004():
    b = hist("GW.SUB1.BKR1.STATUS.STS", "2027-09-14T07:10Z", "2027-09-14T07:15Z")
    trip = next(((t, v) for t, v, q in b if v == "2"), None)
    if not trip:
        return False, "no SUB-01 breaker trip between 07:10Z and 07:15Z"
    v = num(hist("GW.SUB1.BUS.VOLT.PV", trip[0] - 120, trip[0]))
    pu = v[-1][1] / 138.0 if v else 0
    thr = value_at("GW.SUB1.REL.UV_THR.SP", trip[0])
    s5 = num(hist("GW.SUB5.BUS.VOLT.PV", "2027-09-14T07:00Z", "2027-09-14T08:10Z"))
    low5 = min(x for _, x in s5) / 138.0 if s5 else 9
    b5 = {vv for _, vv, _q in hist("GW.SUB5.BKR1.STATUS.STS", "2027-09-14T06:00Z", "2027-09-14T08:10Z")}
    test = value_at("GW.SUB1.REL.UV_THR.SP", "2027-08-16T00:00Z")
    ok = iso(trip[0]).startswith("2027-09-14T07:12") and 0.935 <= pu < 0.94 and thr == "0.94" and test == "0.88" and low5 < pu and b5 == {"1"}
    return ok, (f"SUB-01 trips {iso(trip[0])} at {pu:.3f} pu with threshold {thr} (0.88 at the August test); "
                f"SUB-05 sags to {low5:.3f} pu and stays closed")


def p_h_0302():
    a, b = "2027-09-14T08:30Z", "2027-09-14T14:00Z"
    fa = next((t for t, v in num(hist("GW.UTL1.FEEDA.VOLT.PV", a, b)) if v < 1), None)
    fb = next((t for t, v in num(hist("GW.UTL1.FEEDB.VOLT.PV", a, b)) if v < 1), None)
    p2 = hist("GW.UTL1.PUMP2.RUN.STS", a, "2027-09-20T00:00Z")
    trip = next((t for t, v, q in p2 if v == "2"), None)
    stays = all(v != "1" for t, v, q in p2 if trip and t > trip and v != "")
    wt = max((v for _, v in num(hist("GW.UTL1.PUMP3.WINDTEMP.PV", a, b))), default=0)
    hp = num(hist("GW.UTL1.HSP.DISCH.PRESS.PV", a, b))
    before, after = hp[0][1], min(v for _, v in hp)
    gap = any(q == "0" for _, _, q in hist("GW.UTL1.HSP.DISCH.PRESS.PV", a, b))
    ok = bool(fa and fb and trip) and iso(fa).startswith("2027-09-14T09:00") and iso(fb).startswith("2027-09-14T09:00") and stays and wt > 95 and after < before - 20 and gap
    return ok, (f"feeds A/B lose voltage {iso(fa) if fa else '-'} / {iso(fb) if fb else '-'}; P-2 trips {iso(trip) if trip else '-'} and stays out; "
                f"P-3 winding {wt:.0f} C; header {before:.0f} -> {after:.0f} psi; telemetry gap follows: {gap}")


def p_h_2003():
    want = [("2027-09-15T00:00Z", 0.02), ("2027-09-16T06:00Z", 0.42), ("2027-09-16T12:00Z", 0.38), ("2027-09-18T00:00Z", 0.19),
            ("2027-09-22T00:00Z", 0.08), ("2027-09-28T00:00Z", 0.03)]
    got = []
    for when, val in want:
        v = value_at("GW.UTL1.RAW.TPH.PV", ts(when) + 60)
        got.append((when[5:13], v))
        if v is None or abs(float(v) - val) > 0.011:
            return False, f"raw-water TPH at {when} is {v}, expected {val}"
    return True, "raw-water TPH " + ", ".join(f"{w}={v}" for w, v in got) + " mg/L"


def _breaker_cmd(n, day, minute):
    stem = f"GW.SUB{n}"
    cmd = [x for x in hist(f"{stem}.BKR1.CMD.SP", f"{day}T{minute}:00Z", ts(f"{day}T{minute}:00Z") + 59) if x[1] == "0"]
    if not cmd:
        return False, f"no open command on {stem}.BKR1.CMD.SP at {day} {minute}Z"
    t = cmd[0][0]
    st = next((x for x in hist(f"{stem}.BKR1.STATUS.STS", t, t + 30) if x[1] == "0"), None)
    sess = value_at("GW.SCADA.OPS02.SESSION.STS", t)
    volt = num(hist(f"{stem}.BUS.VOLT.PV", t, t + 600))
    trips = [x for L in "ABC" for x in hist(f"{stem}.REL{L}.TRIP.STS", t - 1800, t + 60) if x[1] == "1"]
    ok = st is not None and sess == "0" and volt and volt[0][1] < 1 and not trips
    return ok, (f"open command {iso(t)}; breaker open {iso(st[0]) if st else '-'}; console GW-WS-OPS-02 session state {sess}; "
                f"bus {volt[0][1] if volt else '-'} kV; relay trip outputs before it: {len(trips)}")


def p_h_gw005():
    return _breaker_cmd(2, "2027-09-21", "14:28")


def p_h_gw007():
    ok, d = _breaker_cmd(3, "2027-09-24", "19:43")
    fb = next((t for t, v in num(hist("GW.UTL1.FEEDB.VOLT.PV", "2027-09-24T19:40Z", "2027-09-24T21:00Z")) if v < 1), None)
    return ok and fb is not None, d + f"; plant feed B lost {iso(fb) if fb else '-'}"


def p_h_gw006():
    sp = hist("GW.UTL1.PUMP3.PRESS.SP", "2027-09-23T02:00Z", "2027-09-23T04:00Z")
    first = next((t for t, v, q in sp if v and float(v) == 68.0), None)
    before = value_at("GW.UTL1.PUMP3.PRESS.SP", "2027-09-23T01:59Z")
    z4 = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-09-23T02:00Z", "2027-09-23T08:00Z"))
    cross = next((t for t, v in z4 if v < 20.0), None)
    c0 = num(hist("GW.UTL1.PUMP3.CURR.PV", "2027-09-22T20:00Z", "2027-09-23T02:03Z"))
    c1 = num(hist("GW.UTL1.PUMP3.CURR.PV", "2027-09-23T02:05Z", "2027-09-23T06:00Z"))
    drop = (sum(v for _, v in c0) / len(c0) - sum(v for _, v in c1) / len(c1)) if c0 and c1 else 0
    ok = bool(first and cross) and before and float(before) == 85.0 and iso(first).startswith("2027-09-23T02:04") and iso(cross).startswith("2027-09-23T05:51") and 9 <= drop <= 13
    return ok, f"P-3 setpoint 85 -> 68 psi at {iso(first) if first else '-'}; Zone 4 first below 20 psi at {iso(cross) if cross else '-'}; P-3 current down {drop:.1f} A"


def p_h_gw008():
    r = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-09-26T15:50Z", "2027-09-26T15:54Z"))
    hit = [x for x in r if abs(x[1] - 16.4) < 0.05]
    win = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-09-26T16:00Z", "2027-09-26T18:00Z"))
    ok = bool(hit) and win and all(v < 20 for _, v in win)
    return ok, f"Zone 4 reads {hit[0][1] if hit else '-'} psi at {iso(hit[0][0]) if hit else '-'}; {min(v for _, v in win):.1f}-{max(v for _, v in win):.1f} psi over the next two hours"


def p_h_gw013():
    sp = hist("GW.WTR3.STATION.PRESS.SP", "2027-09-23T02:00Z", "2027-09-23T03:00Z")
    first = next((t for t, v, q in sp if v and float(v) == 54.0), None)
    before = value_at("GW.WTR3.STATION.PRESS.SP", "2027-09-23T02:07Z")
    later = {v for _, v, _q in hist("GW.WTR3.STATION.PRESS.SP", "2027-10-07T08:00Z", "2027-10-07T10:00Z")}
    still = value_at("GW.WTR3.STATION.PRESS.SP", "2027-10-07T10:00Z")
    ok = first is not None and iso(first).startswith("2027-09-23T02:08") and float(before) == 72.0 and float(still) == 54.0
    return ok, f"booster station setpoint 72 -> 54 psi at {iso(first) if first else '-'}; still {still} psi on 2027-10-07"


def p_h_1609():
    a = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-10-11T05:00Z", "2027-10-12T05:00Z"))
    b = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-10-14T05:00Z", "2027-10-15T05:00Z"))
    ma, mb = sum(v for _, v in a) / len(a), sum(v for _, v in b) / len(b)
    return mb > ma + 15, f"Zone 4 mean {ma:.1f} psi the day before the setpoint is restored, {mb:.1f} psi two days after"


def p_h_gw014():
    iso_t = next((t for t, v, q in hist("GW.SCADA.EXT_ISOLATED.STS", "2027-10-12T12:00Z", "2027-10-12T18:00Z") if v == "1"), None)
    sp = next((t for t, v, q in hist("GW.UTL1.PUMP3.PRESS.SP", "2027-10-12T12:00Z", "2027-10-12T18:00Z") if v and float(v) == 85.0), None)
    z0 = float(value_at("GW.DIST.ZONE4.PRESS.PV", "2027-10-12T12:10Z"))
    z1 = float(value_at("GW.DIST.ZONE4.PRESS.PV", "2027-10-12T18:00Z"))
    ok = bool(iso_t and sp) and iso(iso_t).startswith("2027-10-12T12:00") and iso(sp).startswith("2027-10-12T12:14") and z1 > z0 + 8
    return ok, f"isolation flag set {iso(iso_t) if iso_t else '-'}; P-3 setpoint back to 85 psi {iso(sp) if sp else '-'}; Zone 4 {z0:.1f} -> {z1:.1f} psi by 18:00Z"


def p_h_0406():
    r = hist("GW.UTL1.PUMP2.RUN.STS", "2027-10-22T05:00Z", "2027-10-24T05:00Z")
    on = next((t for t, v, q in r if v == "1"), None)
    hp = num(hist("GW.UTL1.HSP.DISCH.PRESS.PV", "2027-10-23T05:00Z", "2027-10-24T05:00Z"))
    m = sum(v for _, v in hp) / len(hp)
    was = value_at("GW.UTL1.PUMP2.RUN.STS", "2027-10-22T05:00Z")
    return bool(on) and was == "2" and 78 <= m <= 92, f"P-2 running again {iso(on) if on else '-'}; header pressure mean {m:.1f} psi the next day"


def p_h_gw016():
    sps = {k: value_at(f"GW.UTL1.PUMP{k}.PRESS.SP", "2027-10-26T12:00Z") for k in (1, 2, 3, 4)}
    runs = {k: value_at(f"GW.UTL1.PUMP{k}.RUN.STS", "2027-10-26T12:00Z") for k in (1, 2, 3, 4)}
    z = num(hist("GW.DIST.ZONE4.PRESS.PV", "2027-10-26T05:00Z", "2027-10-27T05:00Z"))
    lo = min(v for _, v in z)
    ok = all(float(v) == 85.0 for v in sps.values()) and all(v == "1" for v in runs.values()) and lo >= 41.0
    return ok, f"all four pumps running at 85 psi setpoints; Zone 4 minimum {lo:.1f} psi on 2027-10-26"


# =========================================================================== probes: outage map
def _out_total(when):
    t = when if when.endswith("Z") and len(when) == 20 else when[:16] + ":00Z"
    return sum(int(r["customers_out"]) for r in rows(OUT) if r["timestamp_utc"] == t)


def _feeder(fid, a, b):
    return [(r["timestamp_utc"], int(r["customers_out"]), r["cause"]) for r in rows(OUT) if r["feeder_id"] == fid and a <= r["timestamp_utc"] <= b]


def p_o_0302():
    r = [x for f in ("GW-SUB01-CB-2", "GW-SUB01-CB-3", "GW-SUB01-CB-4") for x in _feeder(f, "2027-09-14T08:00:00Z", "2027-09-18T05:00:00Z")]
    morning = [x for x in r if x[0] < "2027-09-14T15:00:00Z"]
    ok = bool(morning) and min(x[1] for x in morning) > 6000 and max(x[1] for x in r) == 9500
    return ok, f"Riverside feeders (Calallen, Annaville, Tuloso and the plant) fully out from {morning[0][0]}; still {sum(x[1] for x in r if x[0] == '2027-09-17T12:00:00Z')} out on D+3"


def p_o_1604():
    r = _feeder("GW-DSS01-FDR-11", "2027-09-19T05:00:00Z", "2027-09-20T05:00:00Z")
    first = _feeder("GW-DSS01-FDR-11", "2027-09-14T06:00:00Z", "2027-09-14T07:00:00Z")
    ok = bool(r) and all(x[1] == 5200 for x in r) and any(x[0] == "2027-09-14T06:17:00Z" and x[1] == 5200 for x in first)
    return ok, "feeder serving Shoreline Regional (McKinley FDR-11) out from 06:17Z on D0 and still fully out throughout D+5"


def p_o_gw004():
    b = _out_total("2027-09-14T07:00:00Z")
    a = _out_total("2027-09-14T07:15:00Z")
    sub1 = sum(x[1] for f in ("GW-SUB01-CB-2", "GW-SUB01-CB-3", "GW-SUB01-CB-4") for x in _feeder(f, "2027-09-14T07:12:00Z", "2027-09-14T07:12:00Z"))
    peak = _out_total("2027-09-14T10:00:00Z")
    ok = sub1 == 24000 and a - b > 20000 and 71000 <= peak <= 73000
    return ok, f"customers out {b} at 07:00Z, {a} at 07:15Z; all 24,000 on Riverside feeders out at 07:12Z; system peak {peak} at 10:00Z"


def p_o_1105():
    day = "2027-09-22T12:00:00Z"
    r = [x for x in rows(OUT) if x["timestamp_utc"] == day and x["substation_id"] in ("GW-FAC-SUB-02", "GW-FAC-SUB-03") and int(x["customers_out"]) > 0]
    ok = len(r) >= 4 and all(x["cause"] == "STORM" for x in r)
    return ok, f"{len(r)} SUB-02/SUB-03 circuits out on D+8, {sum(int(x['customers_out']) for x in r)} customers, all listed with cause STORM"


def p_o_gw005():
    b = _feeder("GW-SUB02-CB-6", "2027-09-21T03:00:00Z", "2027-09-21T14:15:00Z")
    a = _feeder("GW-SUB02-CB-6", "2027-09-21T14:30:00Z", "2027-09-22T05:00:00Z")
    tb, ta = _out_total("2027-09-21T14:15:00Z"), _out_total("2027-09-21T14:30:00Z")
    ok = b and a and all(x[1] == 0 for x in b) and all(x[1] == 8400 for x in a) and abs((ta - tb) - 8400) < 60 and 47500 <= tb <= 48500
    return ok, f"8,400 customers on Harbor View CB-6 restored overnight and out again from 14:30Z; system total {tb} -> {ta}"


def p_o_1605():
    r = _feeder("GW-DSS01-FDR-11", "2027-09-22T13:00:00Z", "2027-09-22T16:00:00Z")
    at = next((x for x in r if x[1] == 0), None)
    ok = at is not None and at[0] == "2027-09-22T14:14:00Z" and all(x[1] == 5200 for x in r if x[0] < at[0])
    return ok, f"feeder serving Shoreline Regional restored at {at[0] if at else '-'} (09:14 local on D+8)"


def p_o_gw007():
    b = _feeder("GW-SUB03-CB-10", "2027-09-24T12:00:00Z", "2027-09-24T19:30:00Z")
    a = _feeder("GW-SUB03-CB-10", "2027-09-24T19:45:00Z", "2027-09-25T05:00:00Z")
    tb, ta = _out_total("2027-09-24T19:30:00Z"), _out_total("2027-09-24T19:45:00Z")
    ok = b and a and all(x[1] == 0 for x in b) and all(x[1] == 6800 for x in a) and abs((ta - tb) - 6800) < 60
    return ok, f"6,800 customers on Crosstown CB-10 lose power at 19:45Z; system total {tb} -> {ta}"


def p_o_gw015():
    t1, t2, t3 = _out_total("2027-10-19T19:45:00Z"), _out_total("2027-10-19T20:00:00Z"), _out_total("2027-10-20T04:00:00Z")
    held = _out_total("2027-10-10T12:00:00Z")
    ok = 3100 <= t1 <= 3300 and t2 == 0 and t3 == 0 and 35500 <= held <= 36500
    return ok, f"about {held} out until the control systems are isolated; {t1} left at 19:45Z on D+35; none from 20:00Z"


# =========================================================================== probes: work orders
def _wo(pred):
    return [r for r in rows(WO) if pred(r)]


def _status_at(r, when):
    """Status of an order at a time, from its status history."""
    cur = None
    for part in r["status_history"].split(";"):
        s, t = part.split("@")
        if t <= when:
            cur = s
    return cur


def p_w_0102():
    r = _wo(lambda r: r["asset_id"] == "EQP-1102" and "vibration" in r["description"].lower())
    if not r:
        return False, "no P-2 vibration order"
    r = r[0]
    s1, s2 = _status_at(r, "2027-08-15T05:00:00Z"), _status_at(r, "2027-09-14T05:00:00Z")
    ok = r["reported_date"] < "2027-08-15" and s1 == "DEFERRED" and s2 == "DEFERRED" and not r["actual_finish"]
    return ok, f"{r['wonum']} reported {r['reported_date'][:10]}, status {s1} throughout 15 Aug-14 Sep, never completed"


def p_w_0206():
    r = _wo(lambda r: r["org_id"] == "CCAD" and "2027-09-10T05:00" <= r["reported_date"] <= "2027-09-12T05:00" and "production halted" in r["description"].lower())
    ok = bool(r) and "secured" in r[0]["description"].lower()
    return ok, f"{r[0]['wonum']} reported {r[0]['reported_date']}: {r[0]['description']}" if r else "no depot storm-preparation order"


def p_w_0302():
    a, b = "2027-09-14T05:00", "2027-09-17T05:00"
    p2 = _wo(lambda r: r["work_type"] == "EM" and r["asset_id"] == "EQP-1102" and a <= r["reported_date"] <= b)
    feeds = _wo(lambda r: r["work_type"] == "EM" and r["asset_id"] == "FAC-UTL-02" and a <= r["reported_date"] <= b)
    ok = len(p2) >= 1 and len(feeds) >= 2
    return ok, f"emergency orders: P-2 failure {p2[0]['wonum'] if p2 else '-'} ({p2[0]['reported_date'] if p2 else ''}); power feeds {', '.join(x['wonum'] for x in feeds)}"


def p_w_0307():
    r = _wo(lambda r: r["org_id"] == "CCAD" and "2027-09-16T05:00" <= r["reported_date"] <= "2027-09-19T05:00")
    roof = [x for x in r if "roof" in x["description"].lower()]
    water = [x for x in r if "water intrusion" in x["description"].lower()]
    return bool(roof and water), f"depot repair orders: {roof[0]['wonum'] if roof else '-'} (roof), {water[0]['wonum'] if water else '-'} (water intrusion)"


def p_w_0308():
    r = _wo(lambda r: r["work_type"] == "PR" and r["vendor_id"] == "VND-0005" and "2027-09-16T05:00" <= r["reported_date"] <= "2027-09-17T05:00")
    ok = bool(r) and "nine days" in r[0]["work_log"].lower() and "P-2" in r[0]["description"]
    return ok, f"{r[0]['wonum']} to VND-0005 (Delta Pumps & Controls) reported {r[0]['reported_date']}; quoted nine days" if r else "no purchase request"


def p_w_gw005():
    r = _wo(lambda r: r["asset_id"] == "GW-SUB02-BKR-MAIN" and "2027-09-21T05:00" <= r["reported_date"] <= "2027-09-23T05:00")
    ok = bool(r) and "loose" in r[0]["work_log"].lower() and "no other physical cause" in r[0]["work_log"].lower() and _status_at(r[0], "2027-09-23T05:00:00Z") == "CLOSE"
    return ok, f"{r[0]['wonum']}: crew finds no physical cause; closed {r[0]['status_date']} as a loose relay connection" if r else "no SUB-02 crew order"


def p_w_gw007():
    r = _wo(lambda r: r["asset_id"] == "GW-SUB03-BKR-MAIN" and "2027-09-24T05:00" <= r["reported_date"] <= "2027-09-26T05:00")
    ok = bool(r) and "no apparent physical cause" in r[0]["work_log"].lower()
    return ok, f"{r[0]['wonum']} reported {r[0]['reported_date']}: no apparent physical cause" if r else "no SUB-03 crew order"


def p_w_gw008():
    r = _wo(lambda r: "2027-09-26T15:30" <= r["reported_date"] <= "2027-09-26T18:00" and "loma alta" in r["description"].lower())
    ok = bool(r) and "trickle" in (r[0]["description"] + r[0]["work_log"]).lower()
    return ok, f"{r[0]['wonum']} reported {r[0]['reported_date']}: taps at a trickle in Loma Alta" if r else "no field report"


def p_w_gw014():
    r = _wo(lambda r: "2027-10-12T05:00" <= r["reported_date"] <= "2027-10-14T05:00" and "manual operation" in r["description"].lower())
    subs = {x["asset_id"] for x in r}
    return len(subs) == 5, f"{len(r)} orders placing substations in manual operation: {sorted(subs)}"


def p_w_gw107():
    r = _wo(lambda r: r["wonum"] == "WO-2027-OT-0881")
    ok = bool(r) and r[0]["reported_date"] == "2027-10-12T08:00:00Z" and "gateway" in r[0]["description"].lower()
    return ok, f"WO-2027-OT-0881 opened {r[0]['reported_date']}: {r[0]['description']}" if r else "WO-2027-OT-0881 missing"


def p_w_gw015():
    r = _wo(lambda r: "GW-RAR-001" in r["description"] and "2027-10-19T05:00" <= r["actual_finish"] <= "2027-10-20T05:00")
    ok = bool(r) and "all five substations confirmed at commissioning-baseline settings" in r[0]["work_log"]
    return ok, f"{r[0]['wonum']} finished {r[0]['actual_finish']}: relay audit GW-RAR-001 complete" if r else "no relay audit order"


def p_w_0406():
    r = _wo(lambda r: r["asset_id"] == "EQP-1102" and r["work_type"] == "EM" and "2027-10-20T05:00" <= r["actual_finish"] <= "2027-10-23T05:00")
    ok = bool(r) and r[0]["status"] == "CLOSE" and r[0]["actual_finish"].startswith("2027-10-22")
    return ok, f"{r[0]['wonum']}: P-2 rebuild finished {r[0]['actual_finish']} and closed" if r else "no P-2 rebuild order"


def p_w_0407():
    r = _wo(lambda r: r["asset_id"] == "EQP-2201" and "2027-10-24T05:00" <= r["reported_date"] <= "2027-10-27T05:00" and "injector fouling" in r["work_log"].lower())
    ok = bool(r) and "water-contaminated fuel" in r[0]["work_log"] and r[0]["vendor_id"] == "VND-0002" and "QF-27289-B" in r[0]["work_log"]
    return ok, f"{r[0]['wonum']}: injector fouling from water-contaminated fuel; lot QF-27289-B, supplier VND-0002" if r else "no generator failure order"


def p_w_0506():
    r = _wo(lambda r: r["asset_id"] == "EQP-2201" and r["work_type"] == "PR" and "2027-11-25T06:00" <= r["reported_date"] <= "2027-11-26T06:00")
    ok = bool(r) and r[0]["vendor_id"] == "VND-0005"
    return ok, f"{r[0]['wonum']} reported {r[0]['reported_date']}: generator overhaul parts from VND-0005" if r else "no parts order"


# =========================================================================== probes: base status
def _base(inst, a, b):
    return [r for r in rows(BASE) if r["installation_id"] == inst and a <= r["report_date"] <= b]


def p_b_0103():
    r = _base("FAC-DOD-01", "2027-08-15", "2027-09-08")
    rd = [int(x["readiness_pct"]) for x in r]
    tests = {x["generator_test_result"] for x in r if x["generator_test_result"]}
    ok = r and 90 <= min(rd) and max(rd) <= 94 and tests == {"30 min under load: normal"} and all(x["equipment_id"] == "EQP-2201" for x in r)
    return ok, f"NAS Corpus Christi readiness {min(rd)}-{max(rd)} percent; EQP-2201 weekly tests: {sorted(tests)}"


def p_b_0602():
    pre = [int(x["readiness_pct"]) for x in _base("FAC-DOD-01", "2027-08-15", "2027-09-08")]
    post = [int(x["readiness_pct"]) for x in _base("FAC-DOD-01", "2027-10-24", "2027-11-05")]
    late = [int(x["readiness_pct"]) for x in _base("FAC-DOD-01", "2028-01-02", "2028-01-03")]
    ok = round(sum(pre) / len(pre)) == 92 and set(post) == {61} and late and late[0] == 85
    return ok, f"readiness {sum(pre) / len(pre):.0f} percent before the storm, {post[0]} after the generator failure, {late[0]} on 2028-01-02"


def p_b_0205():
    a = _base("FAC-DOD-01", "2027-09-10", "2027-09-19")
    k = _base("FAC-DOD-03", "2027-09-10", "2027-09-19")
    ok = a and k and all(int(x["aircraft_on_station"]) == 0 and "aircraft evacuated" in x["flight_ops_status"] for x in a + k)
    before = _base("FAC-DOD-01", "2027-09-09", "2027-09-09")[0]["aircraft_on_station"]
    return ok, f"aircraft on station {before} on 9 Sep, 0 at both air stations 10-19 Sep, status 'aircraft evacuated'"


def p_b_0206():
    r = _base("FAC-DOD-02", "2027-09-10", "2027-09-15")
    ok = r and all(x["production_status"] == "work halted, assets secured" for x in r)
    return ok, "depot production status 'work halted, assets secured' from 10 Sep"


def p_b_0318():
    r = _base("FAC-DOD-01", "2027-09-14", "2027-09-25") + _base("FAC-DOD-02", "2027-09-14", "2027-09-25")
    after = _base("FAC-DOD-01", "2027-09-26", "2027-09-27")
    ok = len(r) == 24 and all(x["perimeter_sensor_status"].startswith("offline") for x in r) and all(x["perimeter_sensor_status"] == "operational" for x in after)
    return ok, "perimeter sensors offline (storm damage) at the air station and depot 14-25 Sep, operational from 26 Sep"


def p_b_0407():
    r = _base("FAC-DOD-01", "2027-10-24", "2027-10-25")
    prev = _base("FAC-DOD-01", "2027-10-23", "2027-10-23")[0]
    ok = r and all(x["backup_power_status"].startswith("FAILED") and int(x["readiness_pct"]) == 61 for x in r) and prev["backup_power_status"] == "operational"
    return ok, f"EQP-2201 '{r[0]['backup_power_status']}' on {r[0]['report_date']}; readiness {prev['readiness_pct']} -> {r[0]['readiness_pct']} percent"


def p_b_0409():
    r = _base("FAC-DOD-02", "2027-10-31", "2027-11-17")
    prev = _base("FAC-DOD-02", "2027-10-30", "2027-10-30")[0]
    ok = r and all(x["production_status"] == "full production" for x in r) and prev["production_status"] != "full production"
    return ok, f"depot '{prev['production_status']}' on 30 Oct, 'full production' from 31 Oct"


# =========================================================================== probes: fuel
def _fuel(pred):
    return [r for r in rows(FUEL) if r["record_type"] == "DELIVERY" and pred(r)]


def p_f_0103():
    r = _fuel(lambda r: r["facility_id"] == "FAC-DOD-01" and "2027-08-15T05:00" <= r["delivered_utc"] <= "2027-09-14T05:00")
    sup = {x["supplier_id"] for x in r}
    gen = [x for x in r if x["receiving_asset_id"] == "EQP-2201"]
    return len(r) >= 3 and sup == {"VND-0007"} and bool(gen), f"{len(r)} deliveries to NAS Corpus Christi before the storm, all from VND-0007 (regular supplier), {len(gen)} to the generator tank"


def p_f_0312():
    reg_ = _fuel(lambda r: r["facility_id"] == "FAC-DOD-01" and r["supplier_id"] == "VND-0007" and "2027-09-14T05:00" <= r["delivered_utc"] <= "2027-10-17T05:00")
    anyone = _fuel(lambda r: r["supplier_id"] == "VND-0007" and "2027-09-14T05:00" <= r["delivered_utc"] <= "2027-09-26T05:00")
    first_new = min((x["delivered_utc"] for x in _fuel(lambda r: r["facility_id"] == "FAC-DOD-01" and r["supplier_id"] == "VND-0002")), default="")
    last_reg = max(x["delivered_utc"] for x in _fuel(lambda r: r["facility_id"] == "FAC-DOD-01" and r["supplier_id"] == "VND-0007" and r["delivered_utc"] < "2027-09-14"))
    ok = not reg_ and not anyone and first_new > "2027-09-26"
    return ok, f"regular supplier's last delivery to the base {last_reg}; none after the storm; first delivery under the new contract {first_new}"


def p_f_1604():
    dips = [r for r in rows(FUEL) if r["record_type"] == "TANK_DIP" and r["facility_id"] == "FAC-SRMC-001" and r["delivered_utc"] == "2027-09-19T16:30:00Z"]
    a = next((x for x in dips if x["receiving_asset_id"] == "EQP-3102"), None)
    b = next((x for x in dips if x["receiving_asset_id"] == "EQP-3103"), None)
    em = _fuel(lambda r: r["facility_id"] == "FAC-SRMC-001" and r["supplier_id"] == "ORG-1040" and "2027-09-19T16:30" < r["delivered_utc"] < "2027-09-20T05:00")
    ok = a and b and float(a["tank_level_after_pct"]) == 0.0 and abs(float(b["tank_level_after_pct"]) - 23.0) <= 0.5 and "14 hours" in b["remarks"] and bool(em)
    return ok, (f"tank A {a['tank_level_after_pct'] if a else '-'} percent and tank B {b['tank_level_after_pct'] if b else '-'} percent at 11:30 local on D+5 ({b['remarks'] if b else ''}); "
                f"federal delivery {em[0]['delivered_utc'] if em else '-'}")


def p_f_0404():
    rec = _fuel(lambda r: r["receiving_asset_id"] == "TANK-0390" and r["carrier_id"] == "BRG-0044")
    if not rec:
        return False, "no barge receipt at TANK-0390"
    lot = rec[0]["lot_id"]
    nas = sorted(x["delivered_utc"] for x in _fuel(lambda r: r["facility_id"] == "FAC-DOD-01" and r["lot_id"] == lot))
    ok = rec[0]["delivered_utc"].startswith("2027-10-16") and abs(int(rec[0]["volume_gal"]) - 100385) < 200 and nas and nas[0].startswith("2027-10-17")
    return ok, f"{rec[0]['volume_gal']} gal (380 cubic metres) received at TANK-0390 from BRG-0044 on {rec[0]['delivered_utc'][:10]}, lot {lot}; deliveries from that lot to the base start {nas[0][:10] if nas else '-'}"


def p_f_0407():
    rec = _fuel(lambda r: r["receiving_asset_id"] == "TANK-0390" and r["carrier_id"] == "BRG-0044")
    lot = rec[0]["lot_id"] if rec else ""
    gen = _fuel(lambda r: r["receiving_asset_id"] == "EQP-2201" and "2027-10-17T05:00" <= r["delivered_utc"] <= "2027-10-25T05:00")
    wo = [r for r in rows(WO) if r["asset_id"] == "EQP-2201" and lot and lot in r["work_log"]]
    ok = bool(gen) and all(x["lot_id"] == lot and x["supplier_id"] == "VND-0002" for x in gen) and bool(wo)
    return ok, f"{len(gen)} deliveries to the generator tank after D+33, all lot {lot} from VND-0002; the same lot id is on work order {wo[0]['wonum'] if wo else '-'}"


# =========================================================================== probes: tanker cargo control
def _sess(pred):
    return [r for r in rows(SESS) if pred(r)]


def _ship(mmsi, a, b, rtype=None):
    return [r for r in rows(SHIP[mmsi]) if a <= r["timestamp_utc"] <= b and (rtype is None or r["record_type"] == rtype)]


def p_v_0107():
    odd = _sess(lambda r: r["src_asn"] == "ASN 64512" and r["result"] == "SUCCESS")
    first = min(odd, key=lambda r: r["login_utc"]) if odd else None
    usual = {r["src_asn"] for r in _sess(lambda r: r["result"] == "SUCCESS" and r["login_utc"] < (first["login_utc"] if first else "9"))}
    ok = first is not None and "2027-08-12T05:00" <= first["login_utc"] <= "2027-08-16T05:00" and "ASN 64512" not in usual and len(usual) >= 1
    return ok, f"first successful login from ASN 64512 at {first['login_utc']} with account {first['vendor_account']}; earlier sessions only from {sorted(usual)}" if first else "no login"


def p_v_0209():
    r = _sess(lambda r: r["src_asn"] == "ASN 64512" and r["result"] == "SUCCESS" and r["vessel_mmsi"] and "2027-08-25T05:00" <= r["login_utc"] <= "2027-09-14T03:00")
    ships = {x["vessel_name"] for x in r}
    ok = len(r) >= 4 and ships == {"MT Kalvora Star", "MT Ostrel Bay"} and all(x["access_level"] == "read-only" and not x["ticket_ref"] and 1200 <= int(x["duration_s"]) <= 5400 for x in r)
    # what sets them apart is the combination: a network no other session ever comes from, no ticket, and never in the
    # vendor's working day (13:00-22:00Z); ordinary engineers do take night call-outs, over the company VPN and mostly ticketed
    legit = _sess(lambda r: r["src_asn"] != "ASN 64512" and r["result"] == "SUCCESS" and r["vessel_mmsi"])
    office = lambda x: 13 <= int(x["login_utc"][11:13]) < 22
    night = [x for x in legit if not office(x)]
    ok = ok and all(not office(x) for x in r) and len(night) >= 3 and sum(1 for x in legit if office(x)) > 4 * len(night)
    return ok, (f"{len(r)} read-only sessions to {sorted(ships)} from ASN 64512, 20-90 minutes each, no ticket, all outside the vendor's working day "
                f"({len(night)} of {len(legit)} ordinary ship sessions are night call-outs, none from that network; "
                f"{sum(1 for x in legit if not x['ticket_ref'])} of {len(legit)} lack a ticket)")


def _d0(mmsi):
    a, b = "2027-09-14T03:45:00Z", "2027-09-14T05:45:00Z"
    ev = _ship(mmsi, a, b)
    opens = [r for r in ev if r["record_type"] == "CMD" and r["value"] == "OPEN" and r["tag"].startswith("MV-")]
    closes = [r for r in ev if r["record_type"] == "CMD" and r["value"] == "CLOSE" and r["tag"].startswith("MV-")]
    inh = [r for r in ev if r["record_type"] == "ALARM" and r["value"] == "INHIBIT ON"]
    off = [r for r in ev if r["record_type"] == "ALARM" and r["value"] == "INHIBIT OFF"]
    lv = [r for r in rows(SHIP[mmsi]) if r["record_type"] == "LEVEL"]

    def total(when):
        best = {}
        for r in lv:
            if r["timestamp_utc"] <= when:
                best[r["tag"]] = float(r["text"].split()[0])
        return sum(best.values())
    lost = total("2027-09-14T03:45:00Z") - total("2027-09-14T06:00:00Z")
    sess = _sess(lambda r: r["vessel_mmsi"] == mmsi and r["login_utc"] <= "2027-09-14T04:00:00Z" and r["logout_utc"] >= "2027-09-14T05:30:00Z")
    return opens, closes, inh, off, lost, sess


def p_v_0313():
    tot, parts = 0.0, []
    for mmsi in SHIP:
        opens, closes, inh, off, lost, sess = _d0(mmsi)
        if not (opens and closes and inh and sess):
            return False, f"{mmsi}: missing open/close commands, inhibit or session"
        if not all(r["timestamp_utc"].startswith("2027-09-14T04:00") and r["station"] == "RMT-GW" for r in opens):
            return False, f"{mmsi}: manifold open commands not at 04:00Z from the remote gateway"
        if not all(r["station"].startswith("CCR") and r["timestamp_utc"] <= "2027-09-14T05:30:00Z" for r in closes):
            return False, f"{mmsi}: valves not closed from the crew console by 05:30Z"
        if not (inh[0]["timestamp_utc"] < opens[0]["timestamp_utc"] and sess[0]["src_asn"] == "ASN 64512"):
            return False, f"{mmsi}: alarms not inhibited first or session not from ASN 64512"
        tot += lost
        parts.append(f"{mmsi}: open {opens[0]['timestamp_utc'][11:19]}Z via {opens[0]['station']}, closed {closes[-1]['timestamp_utc'][11:19]}Z via {closes[-1]['station']}, {lost:.0f} bbl")
    return 8500 <= tot <= 9500, "; ".join(parts) + f"; total {tot:.0f} bbl; vendor session from ASN 64512 active throughout"


def p_v_2001():
    tot, parts = 0.0, []
    for mmsi in SHIP:
        ev = _ship(mmsi, "2027-09-14T03:45:00Z", "2027-09-14T05:45:00Z", "STATE")
        op = [r for r in ev if r["tag"].startswith("MV-") and r["value"] == "OPEN"]
        cl = [r for r in ev if r["tag"].startswith("MV-") and r["value"] == "CLOSED"]
        _, _, inh, off, lost, sess = _d0(mmsi)
        if not (op and cl and inh and sess):
            return False, f"{mmsi}: valve feedback, inhibit or session missing"
        if not (op[0]["timestamp_utc"].startswith("2027-09-14T04:0") and "2027-09-14T05:20" <= cl[-1]["timestamp_utc"] <= "2027-09-14T05:31"):
            return False, f"{mmsi}: valves not open 04:00Z to about 05:30Z"
        tot += lost
        parts.append(f"{mmsi} valves read open {op[0]['timestamp_utc'][11:19]}Z-{cl[-1]['timestamp_utc'][11:19]}Z")
    return 8500 <= tot <= 9500, "; ".join(parts) + f"; alarms inhibited; tank levels fall {tot:.0f} bbl in total"


def p_v_0316():
    cmds = [r for m in SHIP for r in _ship(m, "2027-09-14T03:45:00Z", "2027-09-14T04:10:00Z", "CMD") if r["value"] == "OPEN"]
    via_remote = bool(cmds) and all(r["station"] == "RMT-GW" for r in cmds)
    dis = _sess(lambda r: "DISABLED" in r["result"].upper() and r["login_utc"].startswith("2027-09-22"))
    after = _sess(lambda r: r["result"] == "SUCCESS" and r["login_utc"] > (dis[0]["login_utc"] if dis else "0"))
    denied = _sess(lambda r: r["result"].startswith("DENIED") and r["login_utc"] > (dis[0]["login_utc"] if dis else "9"))
    ok = via_remote and bool(dis) and not after and bool(denied)
    return ok, f"{len(cmds)} valve-open commands logged from station RMT-GW, none from a crew console; vendor access disabled {dis[0]['login_utc'] if dis else '-'}; no session after, {len(denied)} attempts refused"


def p_v_1207():
    tot, parts = 0.0, []
    for mmsi in SHIP:
        sv = _ship(mmsi, "2027-09-19T08:00:00Z", "2027-09-19T10:00:00Z", "SURVEY")
        short = next((r for r in sv if r["tag"] == "CARGO-SHORTFALL"), None)
        rec = next((r for r in sv if r["tag"] == "VALVE-RECORD"), None)
        _, _, inh, off, _, _ = _d0(mmsi)
        if not (short and rec and inh and off):
            return False, f"{mmsi}: survey entries or alarm inhibit records missing"
        if not ("no console or deck-log entry" in rec["text"] and inh[0]["timestamp_utc"] < "2027-09-14T04:00:00Z" and off[0]["timestamp_utc"] > "2027-09-14T05:25:00Z"):
            return False, f"{mmsi}: valve record or inhibit window wrong"
        tot += float(short["value"])
        parts.append(f"{mmsi} shortfall {short['value']} bbl")
    return 8500 <= tot <= 9500, "; ".join(parts) + f" (combined {tot:.0f} bbl); alarms inhibited from before 04:00Z until reset after 05:30Z; no console entry ordering the valves open"


PROBES = {
    ("EVT-0102", "scada_historian"): p_h_0102, ("GW-EVT-003", "scada_historian"): p_h_gw003, ("GW-EVT-004", "scada_historian"): p_h_gw004,
    ("EVT-0302", "scada_historian"): p_h_0302, ("EVT-2003", "scada_historian"): p_h_2003, ("GW-EVT-005", "scada_historian"): p_h_gw005,
    ("GW-EVT-006", "scada_historian"): p_h_gw006, ("GW-EVT-007", "scada_historian"): p_h_gw007, ("GW-EVT-008", "scada_historian"): p_h_gw008,
    ("GW-EVT-013", "scada_historian"): p_h_gw013, ("EVT-1609", "scada_historian"): p_h_1609, ("GW-EVT-014", "scada_historian"): p_h_gw014,
    ("EVT-0406", "scada_historian"): p_h_0406, ("GW-EVT-016", "scada_historian"): p_h_gw016,
    ("EVT-0302", "outage_map"): p_o_0302, ("EVT-1604", "outage_map"): p_o_1604, ("GW-EVT-004", "outage_map"): p_o_gw004,
    ("EVT-1105", "outage_map"): p_o_1105, ("GW-EVT-005", "outage_map"): p_o_gw005, ("EVT-1605", "outage_map"): p_o_1605,
    ("GW-EVT-007", "outage_map"): p_o_gw007, ("GW-EVT-015", "outage_map"): p_o_gw015,
    ("EVT-0102", "work_orders"): p_w_0102, ("EVT-0206", "work_orders"): p_w_0206, ("EVT-0302", "work_orders"): p_w_0302,
    ("EVT-0307", "work_orders"): p_w_0307, ("EVT-0308", "work_orders"): p_w_0308, ("GW-EVT-005", "work_orders"): p_w_gw005,
    ("GW-EVT-007", "work_orders"): p_w_gw007, ("GW-EVT-008", "work_orders"): p_w_gw008, ("GW-EVT-014", "work_orders"): p_w_gw014,
    ("GW-EVT-107", "work_orders"): p_w_gw107, ("GW-EVT-015", "work_orders"): p_w_gw015, ("EVT-0406", "work_orders"): p_w_0406,
    ("EVT-0407", "work_orders"): p_w_0407, ("EVT-0506", "work_orders"): p_w_0506,
    ("EVT-0103", "base_status_reports"): p_b_0103, ("EVT-0602", "base_status_reports"): p_b_0602, ("EVT-0205", "base_status_reports"): p_b_0205,
    ("EVT-0206", "base_status_reports"): p_b_0206, ("EVT-0318", "base_status_reports"): p_b_0318, ("EVT-0407", "base_status_reports"): p_b_0407,
    ("EVT-0409", "base_status_reports"): p_b_0409,
    ("EVT-0103", "fuel_deliveries"): p_f_0103, ("EVT-0312", "fuel_deliveries"): p_f_0312, ("EVT-1604", "fuel_deliveries"): p_f_1604,
    ("EVT-0404", "fuel_deliveries"): p_f_0404, ("EVT-0407", "fuel_deliveries"): p_f_0407,
    ("EVT-0107", "vessel_ot_logs"): p_v_0107, ("EVT-0209", "vessel_ot_logs"): p_v_0209, ("EVT-0313", "vessel_ot_logs"): p_v_0313,
    ("EVT-2001", "vessel_ot_logs"): p_v_2001, ("EVT-0316", "vessel_ot_logs"): p_v_0316, ("EVT-1207", "vessel_ot_logs"): p_v_1207,
}
