"""Utility SCADA historian (stream scada_historian).

    python3 scripts/streams/gen_ot_scada.py              everything (about 30 s)
    python3 scripts/streams/gen_ot_scada.py e1           one part at a time: e1 e2 w1 w2 sys

Writes 05_other_sources/telemetry/historian_<GROUP>_<YYYYMM>.csv with columns
Tagname,Timestamp,Value,Quality for every tag in 06_data_streams/scada_tags.json over the whole
stream span. Values come from scripts/streams/ot_model.py.

Archive behaviour (what a compressed historian export looks like):
  analog points   a row when the value moves by more than the point's compression deadband, and at
                  least every hour (every 15 minutes for the key pressures and voltages)
  status points   a row on every change (exact second) and an hourly heartbeat
  setpoints       a row on every write (exact second) and a heartbeat
  command points  a row only when a command is written
  quality         192 good, 0 no data (first row of a telemetry gap, empty value), 64 uncertain
                  (first scan after a gap), 216 manually entered
No column or value says why anything happened.
"""
import math
import os
import re
from collections import defaultdict

import numpy as np

from common import ROOT, iso, load_json, out_path, reg, retire, rng, ts
import ot_model as M
from ot_model import GRID, N, STEP, T, DAY, step_fn, pl, smooth_noise

OUT_DIR = "05_other_sources/telemetry"
TAGS = reg("scada_tags")["tags"]
TAG = {t["tagname"]: t for t in TAGS}

DEC = {"kV": 2, "MW": 1, "A": 1, "Hz": 3, "pu": 2, "psi": 2, "gpm": 0, "MGD": 2, "ppm": 2, "%": 1, "ft": 2, "degF": 1, "degC": 1,
       "in/s": 3, "RPM": 0, "V DC": 1, "MVA": 2, "seconds": 0, "count": 0, "writes/hr": 0, "tags/sec": 0, "score": 0, "step": 0,
       "mg/L": 2, "NTU": 2, "count/hr": 0}

ROWS = defaultdict(list)          # (group, yyyymm) -> list of "tag,ts,value,quality"
COUNT = defaultdict(int)


def group_of(tagname):
    s = tagname.split(".")[1]
    if s.startswith("SUB"):
        return "SUB0" + s[3]
    if s.startswith("RTU"):
        return "SUB0" + s[3]
    if s in ("SCADA", "HST", "JMP"):
        return "SYSTEM"
    return {"DSS1": "DSS01", "GEN1": "GEN01", "UTL1": "WTP", "DIST": "DIST"}.get(s, "BOOSTERS" if s.startswith("WTR") else "TANKS")


def site_offset(site):
    return int(rng("scada", "scan-offset", site).integers(3, 58))


def fmt(v, dec):
    if isinstance(v, str):
        return v
    if dec == 0:
        return str(int(round(float(v))))
    return f"{float(v):.{dec}f}"


def put(tagname, rows, raw=False):
    """rows: list of (epoch, value_string, quality) in time order."""
    g = group_of(tagname)
    if raw:
        rows = [r for r in rows if not any(a <= r[0] < b for a, b in CUR_GAPS)]
    last_t = None
    for t, v, q in rows:
        if t < GRID[0] or t > GRID[-1] + STEP:
            continue
        if last_t is not None and t <= last_t:
            if t == last_t:
                continue
        last_t = t
        ROWS[(g, iso(t)[:7].replace("-", ""))].append(f"{tagname},{iso(t)},{v},{q}")
        COUNT[tagname] += 1


CUR_GAPS = []        # telemetry gaps of the site being written; exact-time rows inside a gap are dropped


def set_site(site):
    global CUR_GAPS
    CUR_GAPS = M.COMMS_GAPS.get(site, []) if site else []


def merge(rows, extras):
    if not extras:
        return rows
    extras = [r for r in extras if not any(a <= r[0] < b for a, b in CUR_GAPS)]
    allr = rows + list(extras)
    allr.sort(key=lambda r: (r[0], 0))
    out, seen = [], set()
    for r in allr:
        if r[0] in seen:
            continue
        seen.add(r[0])
        out.append(r)
    return out


def emit_analog(tagname, tt, v, ok=None, deadband=None, maxgap=12, extras=(), dec=None, manual=()):
    """Deadband-compressed analog history. tt epochs, v floats, ok mask (False = no telemetry)."""
    tag = TAG[tagname]
    dec = DEC.get(tag["engineering_units"], 2) if dec is None else dec
    if deadband is None:
        lo, hi = tag.get("normal_low"), tag.get("normal_high")
        deadband = (hi - lo) * 0.02 if lo is not None and hi is not None and hi > lo else 0.5
    n = len(tt)
    ok = np.ones(n, bool) if ok is None else ok
    vv = v.tolist()
    tl = tt.tolist()
    okl = ok.tolist()
    rows = []
    last, lasti, prev_ok = None, -10 ** 9, True
    for i in range(n):
        if not okl[i]:
            if prev_ok:
                rows.append((tl[i], "", 0))
            prev_ok = False
            continue
        x = vv[i]
        if not prev_ok:
            rows.append((tl[i], fmt(x, dec), 64))
            last, lasti, prev_ok = x, i, True
            continue
        if last is None or abs(x - last) >= deadband or i - lasti >= maxgap:
            rows.append((tl[i], fmt(x, dec), 192))
            last, lasti = x, i
    ex = [(t, fmt(val, dec) if not isinstance(val, str) else val, q) for t, val, q in extras]
    rows = merge(rows, ex)
    if manual:
        rows = sorted(rows + [(t, fmt(val, dec), 216) for t, val in manual])
    put(tagname, rows)


def emit_discrete(tagname, tt, v, ok=None, heartbeat=12, extras=(), strings=None):
    """Status / setpoint history: on change plus heartbeat. v numeric array (or use strings list)."""
    n = len(tt)
    ok = np.ones(n, bool) if ok is None else ok
    tag = TAG[tagname]
    dec = 0 if tag["data_type"] == "integer" or tag["engineering_units"] in ("enum", "count", "step") else DEC.get(tag["engineering_units"], 2)
    vv = v.tolist() if strings is None else strings
    tl, okl = tt.tolist(), ok.tolist()
    rows = []
    last, lasti, prev_ok = None, -10 ** 9, True
    for i in range(n):
        if not okl[i]:
            if prev_ok:
                rows.append((tl[i], "", 0))
            prev_ok = False
            continue
        x = vv[i]
        if not prev_ok:
            rows.append((tl[i], fmt(x, dec), 64))
            last, lasti, prev_ok = x, i, True
            continue
        if last is None or x != last or i - lasti >= heartbeat:
            rows.append((tl[i], fmt(x, dec), 192))
            last, lasti = x, i
    ex = [(t, fmt(val, dec) if not isinstance(val, str) else val, q) for t, val, q in extras]
    put(tagname, merge(rows, ex))


def change_rows(events, quality=192):
    """Exact-second rows for step changes: events [(epoch, value)]."""
    return [(int(t), v, quality) for t, v in events]


def noise(key, sigma, corr=6):
    return smooth_noise(("scada", key), N, sigma, corr)


def lag(x, steps):
    """First-order lag of an array (time constant in grid steps)."""
    a = 1.0 / max(1.0, steps)
    out = np.empty_like(x)
    acc = x[0]
    for i, val in enumerate(x.tolist()):
        acc += a * (val - acc)
        out[i] = acc
    return out


HASH = {}


def cfg_hash(key):
    if key not in HASH:
        HASH[key] = "0x%08X" % int(rng("scada", "hash", key).integers(0x10000000, 0xFFFFFFFF))
    return HASH[key]


# =========================================================================== substations
def gen_substations(which=(1, 2, 3, 4, 5)):
    lf_grid = M.load_factor(GRID)
    amb = M.ambient_c(GRID)
    freq_common = noise("freq", 0.006, 3)
    visits = site_visits()
    for n, (asset, stem, peak, mainlbl, feeders) in M.SUBS.items():
        if n not in which:
            continue
        site = f"SUB{n}"
        set_site(site)
        tt = GRID + site_offset(site)
        ok = M.comms_ok(site, tt)
        mb = M.main_breaker(n, tt)
        live = mb == 1
        quiet = 1 - np.clip(1 - np.abs(M.day_frac(tt) - 0.3) / 1.5, 0, 1)
        pu = (1.0 + (0.010 * (0.55 - lf_grid) + noise(f"{site}-pu", 0.0013, 4)) * quiet) * M.storm_sag_pu(n, tt)
        volt = 138.0 * pu * live
        fr = {f: M.energized_fraction(f, tt) for f in feeders}
        served = np.array([M.SERVED[f] for f in feeders], float)
        frac = sum(fr[f] * M.SERVED[f] for f in feeders) / served.sum()
        mw = peak * lf_grid * (0.2 + 0.8 * frac) * live * (1 + noise(f"{site}-mw", 0.012, 3))
        # exact rows around the main-breaker events
        vx, mx, bx, cx = [], [], [], []
        if n == 1:
            tr = T["sub1_trip"]
            vx = [(tr - 2, 138.0 * 0.9390, 192), (tr + 1, 0.0, 192)]
            mx = [(tr + 1, 0.0, 192)]
            bx = [(tr, 2, 192), (T["sub1_back"], 1, 192)]
            cx = [(GRID[0], 1, 192), (T["sub1_back"] - 4, 1, 192)]
        elif n in (2, 3):
            c = T["sub2_cmd"] if n == 2 else T["sub3_cmd"]
            cl = T["sub2_close"] if n == 2 else T["sub3_close"]
            vx = [(c + 3, 0.0, 192)]
            mx = [(c + 3, 0.0, 192)]
            bx = [(c + 2, 0, 192), (cl + 3, 1, 192)]
            cx = [(GRID[0], 1, 192), (c, 0, 192), (cl, 1, 192)]
        else:
            cx = [(GRID[0], 1, 192)]
        emit_analog(f"{stem}.BUS.VOLT.PV", tt, volt, ok, deadband=0.45, maxgap=3, extras=vx)
        emit_analog(f"{stem}.BUS.MW.PV", tt, mw, ok, deadband=peak * 0.022, extras=mx)
        emit_discrete(f"{stem}.BKR1.STATUS.STS", tt, mb, ok, extras=bx)
        put(f"{stem}.BKR1.CMD.SP", [(int(t), str(v), q) for t, v, q in cx], raw=True)
        # bus voltage setpoint (AVR): constant with one ordinary seasonal adjustment at SUB-04
        sp = np.full(N, 138.0)
        spx = []
        if n == 4:
            a, b = ts("2027-08-31T14:05Z") + 17, ts("2027-10-29T15:40Z") + 41
            sp = step_fn(tt, [(a, 139.0), (b, 138.0)], 138.0)
            spx = [(a, 139.0, 192), (b, 138.0, 192)]
        emit_discrete(f"{stem}.BUS.VOLT.SP", tt, sp, ok, heartbeat=72, extras=spx)
        # feeders
        letters = ["A", "B", "C"]
        energized_at_cmd = {"GW-SUB02-CB-6", "GW-SUB03-CB-10"}
        for k, f in enumerate(feeders):
            cb = f.rsplit("-", 2)[-2] + f.rsplit("-", 1)[-1]          # CB2, CB10 ...
            imax = min(900.0, 250.0 + 600.0 * M.SERVED[f] / 9500.0)
            cur = imax * lf_grid * fr[f] * live * (1 + noise(f"{f}-i", 0.02, 3))
            full_out = fr[f] <= 1e-9
            if n == 1:
                tripped = np.zeros(N, bool)
            elif f in energized_at_cmd:
                c = T["sub2_cmd"] if n == 2 else T["sub3_cmd"]
                tripped = full_out & (tt < c)
            else:
                tripped = full_out
            st = np.where(tripped, 2, 1)
            # ordinary planned switching (operator commands) on healthy feeders
            sw = planned_switching().get(f, [])
            cmd_rows = [(GRID[0], "1", 192)]
            st_x = []
            for a, b in sw:
                m = (tt >= a + 2) & (tt < b + 2)
                st = np.where(m, 0, st)
                cur = np.where(m, 0.0, cur)
                cmd_rows += [(a, "0", 192), (b, "1", 192)]
                st_x += [(a + 2, 0, 192), (b + 2, 1, 192)]
            # protection trips: relay output pulses just before the breaker opens
            edges = np.where((st[1:] == 2) & (st[:-1] != 2))[0] + 1
            rel = letters[k] if f"{stem}.REL{letters[k]}.TRIP.STS" in TAG else "B"
            for e in edges:
                t_trip = int(tt[e]) - int(rng("scada", "trip", f, int(e)).integers(20, 240))
                RELAY_PULSES[f"{stem}.REL{rel}.TRIP.STS"] += [(t_trip - 1, 1, 192), (t_trip + 4, 0, 192)]
                st_x.append((t_trip, 2, 192))
            back = np.where((st[1:] == 1) & (st[:-1] == 2))[0] + 1
            for e in back:
                t_close = int(tt[e]) - int(rng("scada", "close", f, int(e)).integers(30, 200))
                if n in (2, 3) and t_close > (T["sub2_cmd"] if n == 2 else T["sub3_cmd"]) and t_close < (T["sub2_close"] if n == 2 else T["sub3_close"]):
                    continue
                cmd_rows.append((t_close - 2, "1", 192))
                st_x.append((t_close, 1, 192))
            emit_analog(f"{stem}.{cb}.CURR.PV", tt, cur, ok, deadband=14.0)
            emit_discrete(f"{stem}.{cb}.STATUS.STS", tt, st, ok, extras=st_x)
            put(f"{stem}.{cb}.CMD.SP", sorted(cmd_rows), raw=True)
            if TAG[f"{stem}.FDR1.CURR.PV"]["equipment_id"] == f:
                emit_analog(f"{stem}.FDR1.CURR.PV", tt, cur * (1 + noise(f"{f}-fdr", 0.004, 2)), ok, deadband=14.0)
        # relays
        for L in letters:
            name = f"{stem}.REL{L}.TRIP.STS"
            if name in TAG:
                emit_discrete(name, tt, np.zeros(N), ok, extras=sorted(RELAY_PULSES[name]))
            name = f"{stem}.REL{L}.OC_THR.SP"
            if name in TAG:
                if n == 2:
                    oc = step_fn(tt, [(T["cfg_sub2"], 2400), (T["relay_reset_sub2"], 1200)], 1200)
                    ox = [(T["cfg_sub2"], 2400, 192), (T["relay_reset_sub2"], 1200, 192)]
                else:
                    oc, ox = np.full(N, 1200.0), []
                emit_discrete(name, tt, oc, ok, heartbeat=72, extras=ox)
        if n == 1:
            uv = step_fn(tt, [(T["uv_thr_sub1"], 0.94), (T["relay_reset_sub1"], 0.88)], 0.88)
            ux = [(T["uv_thr_sub1"], 0.94, 192), (T["relay_reset_sub1"], 0.88, 192)]
        else:
            uv, ux = np.full(N, 0.88), []
        emit_discrete(f"{stem}.REL.UV_THR.SP", tt, uv, ok, heartbeat=72, extras=ux)
        # relay configuration CRC as reported by the relay
        base = cfg_hash(f"relay-{n}")
        ev = []
        if n == 1:
            ev = [(T["uv_thr_sub1"] + 3, cfg_hash("relay-1-b")), (T["relay_reset_sub1"] + 5, base)]
        if n == 2:
            ev = [(T["cfg_sub2"] + 2, cfg_hash("relay-2-b")), (T["relay_reset_sub2"] + 4, base)]
        if n == 5:
            ev = [(ts("2027-11-16T15:22Z") + 9, cfg_hash("relay-5-b"))]
        emit_hash(f"{stem}.REL.CFG_HASH.PV", tt, base, ev, ok)
        # transformer, frequency, door, battery
        load_frac = np.clip(mw / peak, 0, 1.1)
        oil = lag(amb + 9.0 + 34.0 * load_frac, 30) + noise(f"{site}-oil", 0.3, 12)
        emit_analog(f"{stem}.T1.OILTEMP.PV", tt, oil, ok, deadband=1.2)
        tap = np.clip(np.rint(9 + 7.0 * (lf_grid - 0.55) + 14 * (1 - M.storm_sag_pu(n, tt))), 1, 17)
        tap = np.rint(lag(tap, 6))
        emit_discrete(f"{stem}.T1.TAP.PV", tt, tap, ok, heartbeat=36)
        f_ev = freq_events(tt)
        freq = (60.0 + freq_common + noise(f"{site}-f", 0.002, 2) - f_ev) * live
        emit_analog(f"{stem}.BUS.FREQ.PV", tt, freq, ok, deadband=0.02)
        door = np.zeros(N)
        dx = []
        for a, b in visits.get(asset, []):
            door = np.where((tt >= a) & (tt < b), 1, door)
            dx += [(a, 1, 192), (b, 0, 192)]
        emit_discrete(f"{stem}.YARD.DOOR.STS", tt, door, ok, heartbeat=72, extras=dx)
        dead_for = np.zeros(N)
        acc = 0.0
        lv = live.tolist()
        for i in range(N):
            acc = 0.0 if lv[i] else acc + STEP
            dead_for[i] = acc
        batt = 130.2 + noise(f"{site}-batt", 0.12, 24)
        batt = np.where(dead_for > 0, np.where(dead_for < 7200, 130.2 - 8.7 * dead_for / 7200.0, 127.8 + noise(f"{site}-batt2", 0.2, 12)), batt)
        emit_analog(f"{stem}.BATT.VOLT.PV", tt, batt, ok, deadband=0.5, maxgap=36)

        # ---- RTU health (computed by the master station: no telemetry gap)
        set_site(None)
        rt = f"GW.RTU{n}"
        gaps = M.COMMS_GAPS.get(site, [])
        cst = np.where(ok, 1, 0)
        cxr = []
        for a, b in gaps:
            cxr += [(int(a), 0, 192), (int(b), 1, 192)]
        emit_discrete(f"{rt}.COMMS.STS", tt, cst, None, extras=cxr)
        age = 2.6 + np.abs(noise(f"{rt}-age", 1.1, 2))
        for a, b in gaps:
            m = (tt >= a) & (tt < b)
            age = np.where(m, tt - a, age)
        emit_analog(f"{rt}.SCAN_AGE.PV", tt, age, None, deadband=4.0, maxgap=12)
        set_site(site)
        cpu = 19.0 + 5.0 * lf_grid + np.abs(noise(f"{rt}-cpu", 3.0, 2))
        emit_analog(f"{rt}.CPU_LOAD.PV", tt, cpu, ok, deadband=6.0, maxgap=24)
        rbase = cfg_hash(f"rtu-{n}")
        rev = []
        if n == 1:
            rev = [(T["uv_thr_sub1"] + 3, cfg_hash("rtu-1-b")), (T["relay_reset_sub1"] + 5, rbase)]
        if n == 2:
            rev = [(T["cfg_sub2"] + 2, cfg_hash("rtu-2-b")), (T["relay_reset_sub2"] + 4, rbase)]
        if n == 4:
            rev = [(T["cfg_rtu4"], cfg_hash("rtu-4-b")), (T["rtu4_found"] + 2 * 3600 + 610, rbase)]
        if n == 5:
            rev = [(ts("2027-11-16T15:22Z") + 9, cfg_hash("rtu-5-b"))]
        emit_hash(f"{rt}.CFG_HASH.PV", tt, rbase, rev, ok)


RELAY_PULSES = defaultdict(list)


def emit_hash(tagname, tt, base, events, ok):
    events = sorted(events)
    times = np.array([e[0] for e in events], dtype=np.float64) if events else np.array([])
    idx = np.searchsorted(times, tt.astype(np.float64), side="right") if events else np.zeros(N, int)
    vals = [base] + [e[1] for e in events]
    strings = [vals[i] for i in idx.tolist()]
    emit_discrete(tagname, tt, np.zeros(N), ok, heartbeat=72, strings=strings,
                  extras=[(int(t), v, 192) for t, v in events])


def freq_events(tt):
    """System frequency excursions when large blocks of load drop."""
    out = np.zeros(len(tt))
    for t0, depth, tau in ((T["sub1_trip"], 0.21, 240.0), (T["sub2_cmd"] + 2, 0.034, 150.0), (T["sub3_cmd"] + 2, 0.029, 150.0),
                           (T["plant_feeds"], 0.04, 120.0)):
        dt_ = tt - t0
        out += np.where(dt_ >= 0, depth * np.exp(-np.clip(dt_ / tau, 0, 50)), 0.0)
    return out


def planned_switching():
    """Ordinary operator switching on healthy feeders: {feeder: [(open, close)]}."""
    return {
        "GW-SUB04-CB-15": [(ts("2027-08-24T07:10Z") + 21, ts("2027-08-24T10:42Z") + 8)],
        "GW-SUB05-CB-20": [(ts("2027-08-31T06:32Z") + 44, ts("2027-08-31T09:15Z") + 3)],
        "GW-SUB01-CB-4": [(ts("2027-11-09T07:05Z") + 12, ts("2027-11-09T11:20Z") + 37)],
        "GW-SUB04-CB-14": [(ts("2027-11-30T07:30Z") + 5, ts("2027-11-30T09:48Z") + 26)],
        "GW-SUB05-CB-18": [(ts("2027-12-14T07:12Z") + 31, ts("2027-12-14T10:05Z") + 19)],
        "GW-SUB05-CB-19": [(ts("2028-01-04T07:40Z") + 2, ts("2028-01-04T09:58Z") + 48)],
    }


def site_visits():
    """Control-house door openings (crews on site): {asset: [(open, close)]}. The storm-period
    visits match the crew work orders in gen_ot_records.py."""
    v = defaultdict(list)
    g = rng("scada", "visits")
    for n in range(1, 6):
        asset = M.SUBS[n][0]
        day = ts("2027-08-16T14:00Z") + n * DAY
        while day < GRID[-1]:
            if not (T["landfall"] - 2 * DAY < day < T["landfall"] + 2 * DAY):
                a = day + int(g.integers(0, 4 * 3600))
                v[asset].append((a, a + int(g.integers(1500, 5400))))
            day += 7 * DAY
    v["GW-FAC-SUB-01"] += [(ts("2027-08-15T14:10Z"), ts("2027-08-15T19:40Z")), (ts("2027-09-15T10:20Z"), ts("2027-09-15T13:10Z")),
                           (ts("2027-09-28T19:30Z"), ts("2027-09-28T22:40Z")), (ts("2027-10-19T15:20Z"), ts("2027-10-19T17:05Z"))]
    v["GW-FAC-SUB-02"] += [(ts("2027-09-21T15:22Z"), ts("2027-09-21T18:47Z")), (ts("2027-09-22T13:05Z"), ts("2027-09-22T15:30Z")),
                           (ts("2027-10-12T14:10Z"), ts("2027-10-12T17:30Z")), (ts("2027-10-19T16:20Z"), ts("2027-10-19T20:15Z"))]
    v["GW-FAC-SUB-03"] += [(ts("2027-09-24T20:31Z"), ts("2027-09-24T23:58Z")), (ts("2027-09-25T13:10Z"), ts("2027-09-25T16:02Z")),
                           (ts("2027-10-12T15:05Z"), ts("2027-10-12T18:10Z")), (ts("2027-10-19T17:10Z"), ts("2027-10-19T20:20Z"))]
    v["GW-FAC-SUB-04"] += [(ts("2027-09-30T15:10Z"), ts("2027-09-30T21:05Z")), (ts("2027-10-12T16:00Z"), ts("2027-10-12T18:45Z"))]
    v["GW-FAC-SUB-05"] += [(ts("2027-10-12T16:40Z"), ts("2027-10-12T19:05Z")), (ts("2027-11-16T14:30Z"), ts("2027-11-16T17:10Z"))]
    return {k: sorted(x) for k, x in v.items()}


# =========================================================================== McKinley distribution substation
def gen_dss():
    site = "DSS1"
    set_site(site)
    tt = GRID + site_offset(site)
    ok = M.comms_ok(site, tt)
    lf = M.load_factor(GRID)
    st = step_fn(tt, [(T["dss_trip"], 2), (T["srmc_restored"] - 64, 1)], 1)
    live = st == 1
    pu = (1.0 + 0.008 * (0.55 - lf) + noise("dss-pu", 0.0015, 4)) * M.storm_sag_pu(5, tt)
    emit_analog("GW.DSS1.BUS.VOLT.PV", tt, 12.55 * pu * live, ok, deadband=0.05, maxgap=3,
                extras=[(T["dss_trip"] + 1, 0.0, 192)])
    emit_discrete("GW.DSS1.BKR1.STATUS.STS", tt, st, ok, extras=[(T["dss_trip"], 2, 192), (T["srmc_restored"] - 64, 1, 192)])
    tot = 0
    for fdr, tagstem in (("GW-DSS01-FDR-11", "GW.DSS1.FDR11"), ("GW-DSS01-FDR-12", "GW.DSS1.FDR12")):
        fr = M.energized_fraction(fdr, tt)
        cur = 410.0 * (M.SERVED[fdr] / 5200.0) * lf * fr * live * (1 + noise(fdr, 0.02, 3))
        fst = np.ones(N)
        fx = []
        if fdr == "GW-DSS01-FDR-11":
            fx = [(T["srmc_restored"], 1, 192)]
        emit_analog(f"{tagstem}.CURR.PV", tt, cur, ok, deadband=7.0, extras=[(T["srmc_restored"] + 20, 96.0, 192)] if fx else ())
        emit_discrete(f"{tagstem}.STATUS.STS", tt, fst, ok, extras=fx)
        tot = tot + lf * fr * live * M.SERVED[fdr]
    emit_analog("GW.DSS1.T1.LOAD.PV", tt, 21.0 * tot / 9000.0 * (1 + noise("dss-mva", 0.015, 3)), ok, deadband=0.35)


# =========================================================================== Palisade Energy Center
def gen_generation():
    site = "GEN1"
    set_site(site)
    tt = GRID + site_offset(site)
    ok = M.comms_ok(site, tt)
    lf = M.load_factor(GRID)
    amb = M.ambient_c(GRID)
    hl = M.local_hour(tt)
    d = M.day_frac(tt)
    hot = lag(amb, 288) > 24.5
    sched = hot & (hl >= 11.5) & (hl < 22.0)
    test = (((tt // DAY + 4) % 7) == 2) & ((tt % DAY) >= 16 * 3600) & ((tt % DAY) < 18 * 3600)
    restoration = (tt >= ts("2027-09-15T14:00Z")) & (tt < ts("2027-09-27T05:00Z"))
    storm_off = (tt >= ts("2027-09-13T17:00Z")) & (tt < ts("2027-09-15T14:00Z"))
    on = (sched | test | restoration) & ~storm_off
    sp = np.where(on, np.rint((150 + 200 * np.clip((lf - 0.55) / 0.35, 0, 1)) / 10) * 10, 0.0)
    mwv = lag(sp, 3) * (1 + noise("gen-mw", 0.006, 2))
    mwv = np.where(mwv < 3, 0.0, mwv)
    run = (mwv > 3).astype(int)
    emit_analog("GW.GEN1.UNIT1.MW.PV", tt, mwv, ok, deadband=8.0)
    emit_discrete("GW.GEN1.UNIT1.MW.SP", tt, sp, ok, heartbeat=36)
    emit_analog("GW.GEN1.UNIT1.VOLT.PV", tt, np.where(run == 1, 138.2 + noise("gen-v", 0.25, 6), 0.0), ok, deadband=0.5, maxgap=12)
    emit_discrete("GW.GEN1.UNIT1.RUN.STS", tt, run, ok)
    freq = 60.0 + noise("freq", 0.006, 3) + noise("gen-f", 0.002, 2) - freq_events(tt)
    fx = [(T["sub1_trip"] + 2, 59.788, 192), (T["sub1_trip"] + 60, 59.836, 192), (T["sub2_cmd"] + 4, 59.965, 192),
          (T["sub3_cmd"] + 4, 59.970, 192)]
    emit_analog("GW.GEN1.UNIT1.FREQ.PV", tt, freq, ok, deadband=0.02, extras=fx)


# =========================================================================== raw-water booster stations
def gen_boosters():
    amb = M.ambient_c(GRID)
    d, r_all, _ = M.supply_ratios(GRID)
    q = d * r_all
    for n in (1, 2, 3):
        site = f"WTR{n}"
        set_site(site)
        stem = f"GW.WTR{n}"
        tt = GRID + site_offset(site)
        ok = M.comms_ok(site, tt)
        week = ((tt - ts("2027-08-09T14:00Z")) // (7 * DAY)).astype(int)
        duty1 = (week + n) % 2 == 0
        both = lag(q, 12) > 66.0
        st_sp = step_fn(tt, [(T["bstr_sp"], 54.0), (T["bstr_restore"], 72.0)], 72.0) if n == 3 else None
        low = (st_sp < 60) if n == 3 else np.zeros(N, bool)
        for p in (1, 2):
            run = (duty1 if p == 1 else ~duty1) | both
            base_flow = 3000.0 * (0.95 + 0.07 * (lag(q, 6) / 70.0 - 0.9))
            flow = np.where(run, base_flow * np.where(low, 0.82, 1.0) * (1 + noise(f"{site}-p{p}-q", 0.008, 3)), 0.0)
            if n == 3:
                psp = st_sp + 9.0
                spx = [(T["bstr_sp"] + 1, 63.0, 192), (T["bstr_restore"] + 1, 81.0, 192)]
            else:
                psp = np.full(N, 85.0)
                spx = []
            press = np.where(run, psp - 0.7 + noise(f"{site}-p{p}-p", 0.45, 3), 5.5 + noise(f"{site}-p{p}-ps", 0.2, 12))
            cur = np.where(run, (103.0 + 9.0 * (flow / 3000.0 - 0.95) * 4 - np.where(low, 9.0, 0.0)) + noise(f"{site}-p{p}-i", 0.8, 3), 0.0)
            amb_f = amb * 1.8 + 32
            bt = lag(np.where(run, amb_f * 0.35 + 96.0 + 18.0 * flow / 3000.0, amb_f + 4.0), 18) + noise(f"{site}-p{p}-bt", 0.5, 12)
            emit_analog(f"{stem}.PUMP{p}.FLOW.PV", tt, flow, ok, deadband=45.0)
            emit_analog(f"{stem}.PUMP{p}.PRESS.PV", tt, press, ok, deadband=1.2)
            emit_discrete(f"{stem}.PUMP{p}.PRESS.SP", tt, psp, ok, heartbeat=72, extras=spx)
            emit_analog(f"{stem}.PUMP{p}.CURR.PV", tt, cur, ok, deadband=2.5)
            emit_analog(f"{stem}.PUMP{p}.BEARTEMP.PV", tt, bt, ok, deadband=2.5, maxgap=24)
            emit_discrete(f"{stem}.PUMP{p}.RUN.STS", tt, run.astype(int), ok)
        if n == 3:
            emit_discrete("GW.WTR3.STATION.PRESS.SP", tt, st_sp, ok, heartbeat=72,
                          extras=[(T["bstr_sp"], 54.0, 192), (T["bstr_restore"], 72.0, 192)])


# =========================================================================== O.N. Stevens plant
def tph_series(t):
    pts = [(ts("2027-09-14T04:00Z"), 0.02), (ts("2027-09-15T00:00Z"), 0.02), (ts("2027-09-15T16:00Z"), 0.06), (ts("2027-09-16T00:00Z"), 0.21),
           (ts("2027-09-16T06:00Z"), 0.42), (ts("2027-09-16T12:00Z"), 0.38), (ts("2027-09-17T00:00Z"), 0.30), (ts("2027-09-18T00:00Z"), 0.19),
           (ts("2027-09-20T00:00Z"), 0.13), (ts("2027-09-22T00:00Z"), 0.08), (ts("2027-09-28T00:00Z"), 0.03), (ts("2027-10-02T00:00Z"), 0.05),
           (ts("2027-10-04T12:00Z"), 0.08), (ts("2027-10-08T00:00Z"), 0.05), (ts("2027-10-20T00:00Z"), 0.03), (ts("2027-11-13T00:00Z"), 0.02)]
    return pl(t, pts)


def gen_plant():
    site = "UTL1"
    set_site(site)
    stem = "GW.UTL1"
    tt = GRID + site_offset(site)
    ok = M.comms_ok(site, tt)
    amb = M.ambient_c(GRID)
    amb_f = amb * 1.8 + 32
    d, r_all, r_gen = M.supply_ratios(tt)
    q = d * r_all
    p1, p2, p3, p4, tp1, tp2 = M.pump_state(tt)
    fa, fb = M.feed_dead(tt)
    d3 = M.p3_derate(tt)
    low = M.p3_lowered(tt)
    pf = T["plant_feeds"]
    hsp = np.maximum(25.0, 85.5 - 58.0 * (1 - r_all)) + noise("hsp", 0.35, 3)
    te = np.array([pf + 20, pf + 120], dtype=np.float64)
    de, re_, _ = M.supply_ratios(te)
    q_plant = lag(q, 24)                       # clearwell and tanks buffer the plant from the hourly swing in demand
    emit_analog(f"{stem}.PLANT.FLOW.PV", tt, q_plant * (1 + noise("plantq", 0.008, 3)), ok, deadband=1.1, maxgap=6)
    emit_analog(f"{stem}.HSP.DISCH.PRESS.PV", tt, hsp, ok, deadband=0.9, maxgap=3,
                extras=[(pf + 20, float(85.5 - 58.0 * (1 - re_[0])), 192), (pf + 120, float(85.5 - 58.0 * (1 - re_[1])), 192)])
    # per-pump quantities
    load_base = np.clip(0.99 + 0.10 * (d / 70.0 - 1.0), 0.935, 1.05)
    sp_all = {1: step_fn(tt, [(ts("2027-08-23T13:10Z") + 12, 87.0), (ts("2027-08-30T14:25Z") + 40, 85.0)], 85.0),
              2: np.full(N, 85.0),
              3: step_fn(tt, [(T["p3_sp"], 68.0), (T["p3_restore"], 85.0)], 85.0),
              4: step_fn(tt, [(ts("2027-11-18T15:02Z") + 27, 83.0), (ts("2027-11-23T14:11Z") + 6, 85.0)], 85.0)}
    sp_x = {1: [(ts("2027-08-23T13:10Z") + 12, 87.0, 192), (ts("2027-08-30T14:25Z") + 40, 85.0, 192)], 2: [],
            3: [(T["p3_sp"], 68.0, 192), (T["p3_restore"], 85.0, 192)],
            4: [(ts("2027-11-18T15:02Z") + 27, 83.0, 192), (ts("2027-11-23T14:11Z") + 6, 85.0, 192)]}
    run_x = {1: [(pf, 2, 192), (pf + 205, 1, 192)],
             2: [(pf, 2, 192), (T["p2_back"], 1, 192)],
             3: [(pf + 385, 2, 192), (T["p3_restart"], 1, 192)],
             4: [(pf, 2, 192), (pf + 1260, 0, 192), (T["p4_restart"], 1, 192), (T["sub3_cmd"] + 2, 2, 192),
                 (T["sub3_cmd"] + 1500, 0, 192), (T["p4_tempgen"], 1, 192)]}
    states = {1: p1, 2: p2, 3: p3, 4: p4}
    vib_trend = pl(tt, [(GRID[0], 0.165), (pf, 0.292)]) + 0.006 * np.sin(2 * np.pi * (tt - GRID[0]) / (7 * DAY))
    for k in (1, 2, 3, 4):
        run = states[k] == 1
        kload = load_base.copy()
        if k == 1:
            kload = kload * np.where(fa == 1, 0.70, 1.0)
        if k == 3:
            kload = kload * d3 * np.where(low == 1, 0.35, 1.0)
        flow = np.where(run, 3000.0 * kload * (1 + noise(f"p{k}-q", 0.007, 3)), 0.0)
        spv = sp_all[k]
        press = np.where(run, np.minimum(spv - 0.8, hsp + 4.5) + noise(f"p{k}-p", 0.35, 3), 1.1 + np.abs(noise(f"p{k}-ps", 0.3, 12)))
        if k == 3:
            # P-3 discharges into the Zone 4 transmission main and holds its own setpoint, at reduced flow while derated
            press = np.where(run & (low == 0) & (tt >= T["p3_restart"]), spv - 0.8 + noise("p3-phold", 0.35, 3), press)
            press = np.where(run & (low == 1), 68.0 - 0.7 + noise("p3-plow", 0.3, 3), press)
            cur_run = np.where(low == 1, 93.0, np.where(d3 < 1, 104.0, 112.0 + 6 * (load_base - 0.95)))
        else:
            cur_run = 111.0 + 22.0 * (kload - 0.95)
        cur = np.where(run, cur_run + noise(f"p{k}-i", 0.7, 3), 0.0)
        bt = lag(np.where(run, amb_f * 0.35 + 94.0 + 20.0 * kload, amb_f + 5.0), 18) + noise(f"p{k}-bt", 0.5, 12)
        wt = lag(np.where(run, 60.0 + 19.0 * kload + 0.3 * (amb - 25.0), amb + 3.0), 9) + noise(f"p{k}-wt", 0.4, 6)
        wt_x = []
        if k == 3:
            heat = (tt >= pf) & (tt < pf + 385)
            wt = np.where(heat, pl(tt, [(pf, 76.0), (pf + 60, 97.4), (pf + 180, 112.8), (pf + 300, 124.6), (pf + 380, 131.2)]), wt)
            cool = (tt >= pf + 385) & (tt < T["p3_restart"])
            wt = np.where(cool, amb + 3.0 + (131.0 - amb - 3.0) * np.exp(-np.clip((tt - pf - 385) / 5400.0, 0, 50)), wt)
            wt_x = [(pf + 60, 97.4, 192), (pf + 180, 112.8, 192), (pf + 300, 124.6, 192), (pf + 380, 131.2, 192)]
            vib = np.where(d3 < 1, 0.19, 0.11) + noise("p3-vib", 0.012, 4)
        elif k == 2:
            vib = np.where(tt < pf, vib_trend, 0.082) + noise("p2-vib", 0.007, 4)
        else:
            vib = 0.11 + 0.03 * (kload - 0.95) + noise(f"p{k}-vib", 0.010, 4)
        vib = np.where(run, vib, 0.0)
        base_speed = np.rint((1420.0 + 60.0 * (lag(d, 6) / 65.0 - 1.0)) / 10) * 10
        if k == 3:
            speed = np.where(low == 1, 1268.0, 1420.0)
            spd_x = [(T["p3_sp"] + 1, 1268, 192), (T["p3_restore"] + 1, 1420, 192)]
        else:
            speed, spd_x = base_speed, []
        speed = np.where(run, speed, 0.0)
        emit_analog(f"{stem}.PUMP{k}.FLOW.PV", tt, flow, ok, deadband=40.0)
        emit_analog(f"{stem}.PUMP{k}.PRESS.PV", tt, press, ok, deadband=1.0)
        emit_discrete(f"{stem}.PUMP{k}.PRESS.SP", tt, spv, ok, heartbeat=72, extras=sp_x[k])
        emit_analog(f"{stem}.PUMP{k}.CURR.PV", tt, cur, ok, deadband=2.2)
        emit_analog(f"{stem}.PUMP{k}.BEARTEMP.PV", tt, bt, ok, deadband=2.5, maxgap=24)
        emit_discrete(f"{stem}.PUMP{k}.RUN.STS", tt, states[k], ok, extras=run_x[k])
        emit_analog(f"{stem}.PUMP{k}.VIB.PV", tt, vib, ok, deadband=0.012, maxgap=12)
        emit_discrete(f"{stem}.PUMP{k}.SPEED.SP", tt, speed, ok, heartbeat=36, extras=spd_x)
        emit_analog(f"{stem}.PUMP{k}.WINDTEMP.PV", tt, wt, ok, deadband=1.8, maxgap=24, extras=wt_x)
    # chlorine
    dose_sp = step_fn(tt, [(ts("2027-09-14T10:30Z"), 3.6), (ts("2027-09-24T15:00Z"), 3.2), (ts("2027-10-23T14:00Z"), 2.6),
                           (ts("2027-10-27T15:00Z"), 2.2)], 2.2)
    emit_discrete(f"{stem}.CL2.DOSE.SP", tt, dose_sp, ok, heartbeat=72)
    emit_analog(f"{stem}.CL2.DOSE.PV", tt, dose_sp + noise("cl2dose", 0.04, 6), ok, deadband=0.12, maxgap=24)
    lvl = np.empty(N)
    cur_lvl = 71.0
    use = (dose_sp / 2.2) * (q / 62.0) * 9.0 / 288.0
    hl = M.local_hour(tt)
    ul, hll = use.tolist(), hl.tolist()
    for i in range(N):
        cur_lvl -= ul[i]
        if cur_lvl < 24.0 and 8.0 <= hll[i] <= 15.0:
            cur_lvl = 96.0
        lvl[i] = max(cur_lvl, 4.0)
    emit_analog(f"{stem}.CL2.TANK_LVL.PV", tt, lvl, ok, deadband=1.0, maxgap=36)
    emit_discrete(f"{stem}.CL2.PUMP1.RUN.STS", tt, step_fn(tt, [(pf, 0), (pf + 205, 1)], 1), ok)
    # raw and finished water
    tph = tph_series(tt) + noise("tph", 0.002, 12)
    tph_x = [(ts("2027-09-15T00:00Z"), 0.02, 192), (ts("2027-09-16T06:00Z"), 0.42, 192), (ts("2027-09-16T12:00Z"), 0.38, 192),
             (ts("2027-09-18T00:00Z"), 0.19, 192), (ts("2027-09-22T00:00Z"), 0.08, 192), (ts("2027-09-28T00:00Z"), 0.03, 192)]
    emit_analog(f"{stem}.RAW.TPH.PV", tt, np.maximum(tph, 0.01), ok, deadband=0.01, maxgap=12, extras=tph_x)
    turb = pl(tt, [(ts("2027-09-06T00:00Z"), 17.0), (ts("2027-09-08T12:00Z"), 46.0), (ts("2027-09-13T12:00Z"), 58.0), (ts("2027-09-14T18:00Z"), 240.0),
                   (ts("2027-09-17T00:00Z"), 310.0), (ts("2027-09-24T00:00Z"), 120.0), (ts("2027-10-09T00:00Z"), 34.0), (ts("2027-10-25T00:00Z"), 19.0)])
    turb = turb * (1 + noise("rawturb", 0.07, 12))
    emit_analog(f"{stem}.RAW.TURB.PV", tt, turb, ok, deadband=2.0, maxgap=24, dec=1)
    bstr_low = (tt >= T["bstr_sp"]) & (tt < T["bstr_restore"])
    emit_analog(f"{stem}.RAW.FLOW.PV", tt, (q_plant * 1.02 + 1.0 - np.where(bstr_low, 3.5, 0.0)) * (1 + noise("rawq", 0.006, 3)), ok, deadband=1.1, maxgap=12)
    fin = 0.055 + 0.0005 * (turb - 17.0) + np.abs(noise("finturb", 0.006, 6))
    emit_analog(f"{stem}.FIN.TURB.PV", tt, fin, ok, deadband=0.012, maxgap=24)
    res = 2.3 + 0.45 * (dose_sp - 2.2) + noise("cl2res", 0.05, 6)
    emit_analog(f"{stem}.FIN.CL2RES.PV", tt, res, ok, deadband=0.12, maxgap=24)
    cw = 17.1 - 6.4 * (1 - lag(r_all, 36)) - 0.7 * (d / 62.0 - 1.0) + noise("clearwell", 0.08, 6)
    emit_analog(f"{stem}.CLEARWELL.LEVEL.PV", tt, cw, ok, deadband=0.18, maxgap=12)
    # power feeds
    for letter, dead, back, events in (
            ("A", fa, T["feed_a_back"], [(pf, 2), (pf + 1500, 0), (T["feed_a_back"] - 30, 1)]),
            ("B", fb, T["feed_b_back"], [(pf, 2), (pf + 1500, 0), (T["feed_b_back"] - 25, 1), (T["sub3_cmd"] + 1, 2),
                                          (T["sub3_cmd"] + 3600, 0), (T["sub3_close"] + 40, 1)])):
        v = np.where(dead == 1, 0.0, (12.62 + noise(f"feed{letter}", 0.04, 4)) * M.storm_sag_pu(1 if letter == "A" else 3, tt))
        vx = [(pf, 0.0, 192)] + ([(T["sub3_cmd"] + 1, 0.0, 192)] if letter == "B" else [])
        emit_analog(f"{stem}.FEED{letter}.VOLT.PV", tt, v, ok, deadband=0.06, maxgap=6, extras=vx)
        emit_discrete(f"{stem}.FEED{letter}.BKR.STATUS.STS", tt, step_fn(tt, events, 1), ok, extras=change_rows(events))
    # standby generator
    grun = M.plant_gen_running(tt).astype(int)
    gx = [(pf + 27, 1, 192), (T["feed_a_back"] + 1140, 0, 192)]
    emit_discrete(f"{stem}.GEN.RUN.STS", tt, grun, ok, extras=gx)
    emit_analog(f"{stem}.GEN.FUEL.PV", tt, M.plant_gen_fuel_pct(), ok, deadband=0.6, maxgap=72)
    for name, st, on_t, off_t in (("TP1", tp1, T["tp1_on"], T["tp1_off"]), ("TP2", tp2, T["tp2_on"], T["tp2_off"])):
        emit_discrete(f"{stem}.{name}.RUN.STS", tt, st, ok, extras=[(on_t, 1, 192), (off_t, 0, 192)])
        emit_analog(f"{stem}.{name}.FLOW.PV", tt, np.where(st == 1, 3.0 + noise(name, 0.08, 3), 0.0), ok, deadband=0.25, maxgap=24)


# =========================================================================== distribution zones and tanks
def gen_distribution():
    site = "DIST"
    set_site(site)
    tt = GRID + site_offset(site)
    ok = M.comms_ok(site, tt)
    d, r_all, r_gen = M.supply_ratios(tt)
    z4 = M.zone4_pressure(tt)
    manip = (tt >= T["p3_sp"] - 600) & (tt < T["z4_cross20"] + 1800)
    for z in (1, 2, 3, 4, 5):
        if z == 4:
            p = z4 + np.where(manip, 0.0, noise("z4", 0.16, 3))
            ex = [(T["z4_cross20"], 19.99, 192), (T["manual_query"], 16.4, 192)]
            delivered = d * M.ZONE_SHARE[4] * np.minimum(r_gen, 0.35 + 0.65 * z4 / 45.0)
        else:
            p = M.zone_pressure_general(tt, z) + noise(f"z{z}", 0.35, 3)
            ex = []
            delivered = d * M.ZONE_SHARE[z] * r_gen
        emit_analog(f"GW.DIST.ZONE{z}.PRESS.PV", tt, p, ok, deadband=0.8, maxgap=3, extras=ex)
        emit_analog(f"GW.DIST.ZONE{z}.DEMAND.PV", tt, delivered * (1 + noise(f"zd{z}", 0.01, 6)), ok, deadband=0.5, maxgap=12)


TANK_ZONE = {1: 1, 2: 1, 3: 4, 4: 2, 5: 2, 6: 5, 7: 1, 8: 4, 9: 3}


def gen_tanks():
    d, r_all, r_gen = M.supply_ratios(GRID)
    hl = M.local_hour(GRID)
    diur = (0.93 + 0.20 * np.exp(-((hl - 7.2) / 2.3) ** 2) + 0.22 * np.exp(-((hl - 19.6) / 2.6) ** 2) - 0.27 * np.exp(-((hl - 3.0) / 2.6) ** 2))
    season = d / np.maximum(62.0 * diur, 1)
    assets = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"]}
    for k in range(1, 10):
        site = "TK%02d" % k
        set_site(site)
        stem = f"GW.{site}"
        tt = GRID + site_offset(site)
        ok = M.comms_ok(site, tt)
        z = TANK_ZONE[k]
        pz = M.zone4_pressure(GRID) if z == 4 else M.zone_pressure_general(GRID, z)
        nominal = M.ZONE_NOMINAL[z]
        g = rng("scada", "tank", k)
        cap_mg = float(assets.get(f"GW-FAC-TK-0{k}", {}).get("capacity_mg") or 4.0)
        gal_per_ft = cap_mg * 1e6 / 20.0
        base_out = float(g.uniform(380, 620)) * cap_mg / 4.0
        max_in = min(1450.0, 1400.0 * cap_mg / 4.0)
        open_at, close_at = float(g.uniform(12.8, 14.6)), float(g.uniform(18.8, 19.5))
        avail = np.clip((pz - 22.0) / (nominal - 22.0), 0, 1) ** 0.7
        want_out = base_out * diur * np.clip(season, 0.6, 1.5) * (1 + 1.3 * (1 - r_gen)) * (1 + smooth_noise(("tank-out", k), N, 0.04, 6))
        level = np.empty(N); inflow = np.empty(N); outflow = np.empty(N); valve = np.empty(N)
        lv, vopen = float(g.uniform(14.5, 18.5)), bool(g.integers(0, 2))
        al, wl = avail.tolist(), want_out.tolist()
        for i in range(N):
            if lv < open_at:
                vopen = True
            elif lv > close_at:
                vopen = False
            fin = max_in * al[i] if vopen else 0.0
            fout = wl[i]
            if lv <= 1.2:
                fout = min(fout, fin)
            lv = min(20.4, max(0.8, lv + (fin - fout) * 5.0 / gal_per_ft))
            level[i], inflow[i], outflow[i], valve[i] = lv, fin, fout, 100.0 if vopen else 0.0
        manual = []
        if k in (3, 7):
            for a, b in M.COMMS_GAPS[site]:
                tm = a + 6 * 3600
                while tm < b:
                    i = int((tm - GRID[0]) // STEP)
                    manual.append((int(tm) + 240, float(level[i])))
                    tm += 11 * 3600
        emit_analog(f"{stem}.LEVEL.PV", tt, level, ok, deadband=0.16, maxgap=12, manual=manual)
        emit_analog(f"{stem}.LEVEL_PCT.PV", tt, level / 20.0 * 100.0, ok, deadband=0.8, maxgap=12)
        emit_analog(f"{stem}.INFLOW.PV", tt, inflow * (1 + smooth_noise(("tank-in", k), N, 0.01, 3)), ok, deadband=45.0, maxgap=12)
        emit_analog(f"{stem}.OUTFLOW.PV", tt, outflow, ok, deadband=38.0, maxgap=12)
        emit_discrete(f"{stem}.FILL_VALVE.SP", tt, valve, ok, heartbeat=36)


# =========================================================================== SCADA, historian and gateway health
def ops02_sessions():
    """Logged-out intervals of the operator console GW-WS-OPS-02."""
    g = rng("scada", "ops02")
    out = []
    t = ts("2027-08-14T23:00Z")
    while t < GRID[-1] + DAY:
        out.append((t - int(g.integers(60, 400)), t + int(g.integers(240, 780))))            # shift handover
        for _ in range(int(g.integers(1, 3))):
            a = t + int(g.integers(3600, 11 * 3600))
            out.append((a, a + int(g.integers(700, 2700))))
        t += 12 * 3600
    forced = [(T["sub2_cmd"] - 1380, T["sub2_cmd"] + 1440), (T["sub3_cmd"] - 1400, T["sub3_cmd"] + 1320)]
    keep = []
    for a, b in out:
        if any(a < fb + 900 and b > fa - 900 for fa, fb in forced):
            continue
        keep.append((a, b))
    keep += forced
    keep.sort()
    merged = []
    for a, b in keep:
        if merged and a <= merged[-1][1] + 60:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def gen_system():
    set_site(None)
    tt = GRID + site_offset("MASTER")
    g = rng("scada", "system")
    hl = M.local_hour(tt)
    wkend = M.is_weekend(tt)
    business = (hl >= 7) & (hl < 18) & ~wkend
    put_ok = None
    emit_discrete("GW.SCADA.SERVER.COMMS.STS", tt, np.ones(N), put_ok)
    emit_discrete("GW.HST.SERVER.COMMS.STS", tt, np.ones(N), put_ok)
    # alarm suppression list
    legit_before, legit_after = [], []
    t = GRID[0]
    cnt = 12
    freeze_a, freeze_b = ts("2027-09-08T00:00Z"), T["isolate"] + 4 * 3600
    change_times = []
    while t < GRID[-1]:
        t += int(g.integers(2 * DAY, 6 * DAY))
        tl = t - (t % DAY) + int(g.integers(13 * 3600, 21 * 3600))
        if freeze_a <= tl <= freeze_b + 5 * DAY or tl >= GRID[-1]:
            continue
        cnt = int(np.clip(cnt + g.choice([-2, -1, 1, 1, 2]), 9, 15))
        (legit_before if tl < freeze_a else legit_after).append((tl, cnt))
        change_times.append(tl)
    if legit_before:
        legit_before[-1] = (legit_before[-1][0], 12)
    steps = list(legit_before)
    rebuilt = T["isolate"] + 4 * 3600 + 1140
    steps += M.SUPPRESSION_STEPS + [(rebuilt, 9)] + [(a, b) for a, b in legit_after if a > rebuilt + DAY]
    steps.sort()
    change_times = [a for a, _ in steps]
    supp = step_fn(tt, steps, 12)
    emit_analog("GW.SCADA.ALARM_SUPR_CNT.PV", tt, supp, None, deadband=0.5, maxgap=72, extras=[(int(a), b, 192) for a, b in steps])
    chg = np.zeros(N)
    cx = []
    for a in change_times:
        day0 = a - (a % DAY)
        m = (tt >= a) & (tt < day0 + DAY)
        chg = chg + m
        n_today = sum(1 for b in change_times if day0 <= b <= a)
        cx.append((int(a), n_today, 192))
    emit_analog("GW.SCADA.ALARM_SUPR_CHG.PV", tt, chg, None, deadband=0.5, maxgap=72, extras=cx)
    # active alarms
    lf = T["landfall"]
    storm_alarms = pl(tt, [(lf - 8 * 3600, 0), (lf + 2 * 3600, 235), (lf + 10 * 3600, 405), (lf + 2 * DAY, 255), (lf + 5 * DAY, 118),
                           (lf + 10 * DAY, 52), (T["isolate"], 26), (T["isolate"] + DAY, 61), (T["all_restored"], 28),
                           (T["all_restored"] + 4 * DAY, 9), (T["all_restored"] + 10 * DAY, 0)])
    alarms = np.rint(6.5 + np.abs(noise("alarms", 3.0, 4)) + storm_alarms * (1 + noise("alarms2", 0.05, 6)))
    emit_analog("GW.SCADA.ACTIVE_ALARMS.PV", tt, alarms, None, deadband=3.0, maxgap=12)
    # setpoint writes per hour
    hours = np.arange(GRID[0] - GRID[0] % 3600, GRID[-1] + 3600, 3600)
    hlh = M.local_hour(hours)
    lam = np.where((hlh >= 7) & (hlh < 18), 4.2, np.where((hlh >= 18) & (hlh < 23), 1.3, 0.35))
    lam = lam * np.where((hours > lf) & (hours < lf + 12 * DAY), 2.2, 1.0)
    writes = g.poisson(lam).astype(float)
    for tw, k in ((T["uv_thr_sub1"], 2), (T["cfg_sub2"], 1), (T["sub2_cmd"], 1), (T["p3_sp"], 2), (T["sub3_cmd"], 1), (T["p3_restore"], 3)):
        writes[int((tw - hours[0]) // 3600)] += k
    w5 = writes[np.clip(((tt - hours[0]) // 3600).astype(int), 0, len(writes) - 1)]
    emit_analog("GW.SCADA.SETPOINT_WRITES.PV", tt, w5, None, deadband=0.5, maxgap=12)
    # operator console session
    out_iv = ops02_sessions()
    sess = np.ones(N)
    sx = []
    for a, b in out_iv:
        sess = np.where((tt >= a) & (tt < b), 0, sess)
        sx += [(int(a), 0, 192), (int(b), 1, 192)]
    emit_discrete("GW.SCADA.OPS02.SESSION.STS", tt, sess, None, extras=sx)
    iso_ev = [(T["isolate"], 1), (T["reconnect"], 0)]
    emit_discrete("GW.SCADA.EXT_ISOLATED.STS", tt, step_fn(tt, iso_ev, 0), None, extras=change_rows(iso_ev))
    # historian
    down = np.zeros(N)
    sites = ["SUB1", "SUB2", "SUB3", "SUB4", "SUB5", "DSS1", "UTL1", "DIST", "GEN1", "TK01", "TK03", "TK05", "TK07", "TK09"]
    for s in sites:
        down += ~M.comms_ok(s, tt)
    wr = 318.0 * (1 - 0.72 * down / len(sites)) + noise("hstwr", 9.0, 3)
    emit_analog("GW.HST.WRITE_RATE.PV", tt, wr, None, deadband=14.0, maxgap=12)
    isolated = (tt >= T["isolate"]) & (tt < T["reconnect"])
    hs = np.where(business, 4.0 + np.rint(np.abs(noise("hstsess", 1.6, 6))), 1.0 + (noise("hstsess2", 0.8, 12) > 0.6))
    remote = np.zeros(N)
    for a, dur in M.KNOWN_REMOTE_SESSIONS:
        remote = np.where((tt >= a) & (tt < a + dur), 1, remote)
    hs = np.where(isolated, np.minimum(hs, 2), hs + remote)
    emit_analog("GW.HST.SESSION_CNT.PV", tt, hs, None, deadband=0.5, maxgap=12)
    after = np.zeros(N)
    ax = []
    ah = []
    tday = GRID[0]
    while tday < GRID[-1]:
        if g.random() < 0.3:
            ah.append(tday + int(g.integers(0 * 3600, 5 * 3600)))            # evening local = early UTC next day
        tday += DAY
    for a, dur in M.KNOWN_REMOTE_SESSIONS:
        h = float(M.local_hour(np.array([a]))[0])
        if h < 7 or h >= 18:
            ah.append(a)
    for a in sorted(ah):
        off = -5 * 3600 if a < 1825570800 else -6 * 3600
        local_midnight_next = ((a + off) // DAY + 1) * DAY - off
        after = after + ((tt >= a) & (tt < local_midnight_next))
        ax.append(int(a))
    emit_analog("GW.HST.AFTER_HRS_ACCESS.PV", tt, after, None, deadband=0.5, maxgap=72)
    # remote-access gateway
    jst = step_fn(tt, [(T["isolate"], 0), (T["reconnect"], 1)], 1)
    emit_discrete("GW.JMP.SERVER.COMMS.STS", tt, jst, None, extras=change_rows([(T["isolate"], 0), (T["reconnect"], 1)]))
    legit = np.where(business, np.rint(np.clip(0.9 + noise("jmpsess", 1.0, 5), 0, 3)), 0.0)
    legit = np.where((tt > lf - 2 * DAY) & (tt < lf + 2 * DAY), np.minimum(legit, 1), legit)
    js = np.where(jst == 1, legit + remote, 0.0)
    emit_analog("GW.JMP.ACTIVE_SESSIONS.PV", tt, js, None, deadband=0.5, maxgap=12)
    geo_legit = np.where(legit > 0, 3.0 + np.abs(noise("jmpgeo", 2.5, 5)), 0.0)
    geo = np.where(remote > 0, 74.0 + 14.0 * np.abs(np.sin(tt / 977.0)), geo_legit)
    geo = np.where(jst == 1, geo, 0.0)
    emit_analog("GW.JMP.SRC_IP_GEO.PV", tt, geo, None, deadband=1.5, maxgap=12)
    hours_l = np.where(business[np.clip(((hours - GRID[0]) // STEP).astype(int), 0, N - 1)], 0.7, 0.12)
    fails = g.poisson(hours_l).astype(float)
    f5 = fails[np.clip(((tt - hours[0]) // 3600).astype(int), 0, len(fails) - 1)]
    emit_analog("GW.JMP.AUTH_FAILURES.PV", tt, np.where(jst == 1, f5, 0.0), None, deadband=0.5, maxgap=72)


# =========================================================================== main
PARTS = {  # part name -> (functions, file groups it owns). Parts let the generator run in short steps.
    "e1": ([lambda: gen_substations((1, 2, 3))], ["SUB01", "SUB02", "SUB03"]),
    "e2": ([lambda: gen_substations((4, 5)), gen_dss, gen_generation], ["SUB04", "SUB05", "DSS01", "GEN01"]),
    "w1": ([gen_boosters, gen_plant], ["BOOSTERS", "WTP"]),
    "w2": ([gen_distribution, gen_tanks], ["DIST", "TANKS"]),
    "sys": ([gen_system], ["SYSTEM"]),
}


def main(parts=None):
    """python3 gen_ot_scada.py            everything
       python3 gen_ot_scada.py e1 e2 ...  only those parts (e1, e2, w1, w2, sys)"""
    parts = parts or list(PARTS)
    # legacy files (old naming) are moved out once; this generator's own previous output is simply replaced
    current = re.compile(r"^historian_([A-Z0-9]+)_\d{6}\.csv$")
    tel = os.path.join(ROOT, OUT_DIR)
    os.makedirs(tel, exist_ok=True)
    legacy = [os.path.relpath(os.path.join(dp, f), ROOT) for dp, _, fs in os.walk(tel) for f in fs
              if f.startswith("historian") and not current.match(f)]
    retire(legacy)
    cons = os.path.join(tel, "_consolidated")
    if os.path.isdir(cons) and not os.listdir(cons):
        os.rmdir(cons)
    owned = {g for p in parts for g in PARTS[p][1]}
    for f in os.listdir(tel):
        m = current.match(f)
        if m and m.group(1) in owned:
            os.remove(os.path.join(tel, f))
    for p in parts:
        for fn in PARTS[p][0]:
            fn()
    total, size = 0, 0
    for (g, ym), rows in sorted(ROWS.items()):
        fp = out_path(f"{OUT_DIR}/historian_{g}_{ym}.csv")
        with open(fp, "w", encoding="utf-8", newline="") as fh:
            fh.write("Tagname,Timestamp,Value,Quality\n")
            fh.write("\n".join(rows))
            fh.write("\n")
        total += len(rows)
        size += os.path.getsize(fp)
    print(f"scada_historian [{' '.join(parts)}]: {total:,} rows, {len(ROWS)} files, {size / 1e6:.1f} MB, {len(COUNT)} tags")
    if len(parts) == len(PARTS):
        missing = [t["tagname"] for t in TAGS if COUNT[t["tagname"]] == 0]
        if missing:
            print("  TAGS WITH NO ROWS:", missing)


if __name__ == "__main__":
    import sys
    main(sys.argv[1:] or None)
