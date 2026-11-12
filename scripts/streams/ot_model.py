"""Shared physical model for the utility / operational-technology stream family.

One model, read by gen_ot_scada.py (historian), gen_ot_records.py (outage map, work orders,
base status, fuel) and gen_ot_vessel.py (tanker cargo control), so the streams agree with each
other: customers out on a feeder is the same number that scales that feeder's current, the
generator that burns fuel in the historian is the one a delivery ticket refills, and so on.

Everything here comes from 00_scenario/canon_timeline.json (power, utility_cyber, water, spill,
relief, military_aviation, fraud_and_contracts, dark_vessel) and the registries. Nothing in this
module is written to disk.

Shared event-time rule (also used by the IT/security log family): where the timeline gives a time
to the minute, the second is 00 plus  int(sha256(event_id).hexdigest(), 16) % 50.
"""
import hashlib
import math

import numpy as np

from common import D0_EPOCH, LANDFALL, SPAN_END, SPAN_START, load_json, rng, ts, utc_offset

STEP = 300                                   # model grid, seconds
GRID = np.arange(SPAN_START, SPAN_END + 1, STEP, dtype=np.int64)
N = len(GRID)
DAY = 86400


def ev_sec(event_id):
    return int(hashlib.sha256(event_id.encode()).hexdigest(), 16) % 50


def E(iso_minute, event_id=None):
    return ts(iso_minute) + (ev_sec(event_id) if event_id else 0)


# ------------------------------------------------------------------ canon event times (UTC epochs)
T = {
    # hidden utility manipulations (times are the ones the expected observations state)
    "uv_thr_sub1": E("2027-09-11T17:04Z", "GW-EVT-003"),       # 27-UV 0.88 -> 0.94 pu at SUB-01
    "supp_list_d3": E("2027-09-11T17:09Z", "GW-EVT-003"),      # alarm suppression list extended
    "cfg_sub2": E("2027-09-11T22:11Z", "GW-EVT-103"),          # SUB-02 relay configuration written
    "cfg_rtu4": E("2027-09-11T22:11Z", "GW-EVT-010"),          # file timestamp later found on SUB-04 RTU
    "sub1_trip": E("2027-09-14T07:12Z", "GW-EVT-004"),
    "sub2_cmd": E("2027-09-21T14:28Z", "GW-EVT-005"),          # breaker-open command, CB-7
    "p3_sp": E("2027-09-23T02:04Z", "GW-EVT-006"),             # P-3 discharge setpoint 85 -> 68 psi
    "bstr_sp": E("2027-09-23T02:08Z", "GW-EVT-013"),           # booster station setpoint 72 -> 54 psi
    "supp_peak": E("2027-09-23T02:10Z", "GW-EVT-105"),         # suppression list reaches 94
    "z4_cross20": ts("2027-09-23T05:51Z") + ev_sec("GW-EVT-006"),
    "sub3_cmd": E("2027-09-24T19:43Z", "GW-EVT-007"),          # breaker-open command, CB-12
    "manual_query": ts("2027-09-26T15:52Z") + ev_sec("GW-EVT-008"),
    "isolate": E("2027-10-12T12:00Z", "GW-EVT-014"),
    "p3_restore": E("2027-10-12T12:14Z", "GW-EVT-014"),
    "bstr_restore": E("2027-10-12T12:26Z", "GW-EVT-014"),
    "relay_reset_sub1": E("2027-10-19T16:12Z", "GW-EVT-015"),
    "relay_reset_sub2": E("2027-10-19T16:47Z", "GW-EVT-015"),
    "sub2_close": E("2027-10-19T19:40Z", "GW-EVT-015"),
    "sub3_close": E("2027-10-19T19:52Z", "GW-EVT-015"),
    "all_restored": ts("2027-10-19T20:00Z"),
    "reconnect": ts("2027-10-19T18:00Z"),
    "rtu4_found": E("2027-09-30T18:00Z", "GW-EVT-010"),
    # storm
    "landfall": LANDFALL,
    "dss_trip": E("2027-09-14T06:17Z", "EVT-1602"),            # McKinley feeder to SRMC lost
    "srmc_restored": E("2027-09-22T14:14Z", "EVT-1605"),
    "plant_feeds": E("2027-09-14T09:00Z", "EVT-0302"),         # both plant feeds lose voltage
    "sub1_back": ts("2027-09-15T12:00Z"),
    "feed_a_back": ts("2027-09-16T14:02Z"),
    "feed_b_back": ts("2027-09-19T10:31Z"),
    "p3_restart": ts("2027-09-15T18:00Z"),
    "p4_restart": ts("2027-09-19T10:42Z"),
    "p4_tempgen": ts("2027-10-12T13:31Z"),
    "tp1_on": ts("2027-09-17T16:10Z"), "tp1_off": ts("2027-10-24T15:00Z"),
    "tp2_on": ts("2027-09-19T15:20Z"), "tp2_off": ts("2027-10-22T20:00Z"),
    "p2_back": ts("2027-10-22T15:40Z"),                        # D+38
    "p3_full": ts("2027-10-23T16:00Z"),
    # tankers
    "valves_open": E("2027-09-14T04:00Z", "EVT-0313"),
    "valves_closed": ts("2027-09-14T05:30Z"),
}

# alarm suppression list: (time, active count). Baseline 12; seven changes since D-5 add 82.
SUPPRESSION_STEPS = [
    (E("2027-09-09T03:12Z", "GW-EVT-105"), 18),
    (T["supp_list_d3"], 29),
    (E("2027-09-13T04:41Z", "GW-EVT-105"), 38),
    (E("2027-09-16T08:22Z", "GW-EVT-105"), 52),
    (E("2027-09-19T05:37Z", "GW-EVT-105"), 64),
    (E("2027-09-21T14:25Z", "GW-EVT-005"), 74),
    (T["supp_peak"], 94),
]

# out-of-hours remote sessions whose times canon states (start, seconds)
KNOWN_REMOTE_SESSIONS = [
    (E("2027-09-07T02:44Z", "GW-EVT-102"), 862),
    (ts("2027-09-08T23:40Z"), 1500),
    (T["uv_thr_sub1"] - 240, 900),
    (T["cfg_sub2"] - 420, 780),
    (ts("2027-09-14T08:31Z"), 600),
    (T["sub2_cmd"] - 200, 420),
    (T["p3_sp"] - 260, 760),
    (T["sub3_cmd"] - 180, 360),
    (ts("2027-10-02T14:33Z"), 1260),
    # the remaining five of the fourteen sessions (long late-night sessions before the storm);
    # the gateway's own session log is in the host_audit_logs stream and uses this same list
    (ts("2027-09-07T05:10Z") + 17, 5400),
    (ts("2027-09-08T03:05Z") + 41, 6600),
    (ts("2027-09-09T02:20Z") + 8, 7200),
    (ts("2027-09-09T23:55Z") + 29, 7800),
    (ts("2027-09-10T03:40Z") + 3, 6598),
]
KNOWN_REMOTE_SESSIONS.sort()


# ------------------------------------------------------------------ small helpers
def local_hour(t):
    t = np.asarray(t, dtype=np.float64)
    off = np.where(t < 1825570800, -5, -6)
    return ((t + off * 3600) % DAY) / 3600.0


def day_frac(t):
    return (np.asarray(t, dtype=np.float64) - D0_EPOCH) / DAY


def step_fn(t, events, initial):
    """Value of a step function at times t. events: [(epoch, value)] sorted by time."""
    times = np.array([e[0] for e in events], dtype=np.float64)
    vals = np.array([initial] + [e[1] for e in events], dtype=np.float64)
    return vals[np.searchsorted(times, np.asarray(t, dtype=np.float64), side="right")]


def pl(t, points):
    """Piecewise-linear through [(epoch, value)]."""
    x = np.array([p[0] for p in points], dtype=np.float64)
    y = np.array([p[1] for p in points], dtype=np.float64)
    return np.interp(np.asarray(t, dtype=np.float64), x, y)


def smooth_noise(key, n, sigma, corr_steps):
    """Deterministic correlated noise of length n."""
    g = rng("ot", key)
    m = n // corr_steps + 3
    knots = g.normal(0, sigma, m)
    x = np.arange(n) / corr_steps
    return np.interp(x, np.arange(m), knots)


# ------------------------------------------------------------------ weather and load
def ambient_c(t):
    """Outdoor temperature (deg C) used for load, demand and equipment temperatures."""
    d = day_frac(t)
    x = np.clip((d + 45.0) / 175.0, 0, 1)
    mean = 14.5 + 8.0 * (1 + np.cos(np.pi * x))
    idx = np.clip(((np.asarray(t) - SPAN_START) // STEP).astype(int), 0, N - 1)
    wx = _WX[idx]
    hl = local_hour(t)
    amp = 4.6
    storm = np.clip(1 - np.abs(d - 0.2) / 1.6, 0, 1)
    mean = mean * (1 - storm) + 25.5 * storm
    return mean + wx * (1 - 0.7 * storm) + amp * (1 - 0.7 * storm) * np.cos(2 * np.pi * (hl - 15.5) / 24)


_WX = smooth_noise("weather", N, 2.3, 288 * 2)      # multi-day weather wander
_FRONT = np.clip(smooth_noise("fronts", N, 3.5, 288 * 5), -9, 2) * np.clip((day_frac(GRID) - 35) / 30, 0, 1)
_WX = _WX + _FRONT


def is_weekend(t):
    dow = ((np.asarray(t, dtype=np.float64) + utc_offset_arr(t) * 3600) // DAY + 4) % 7     # 0 = Sunday
    return (dow == 0) | (dow == 6)


def utc_offset_arr(t):
    return np.where(np.asarray(t, dtype=np.float64) < 1825570800, -5, -6)


def evac_factor(t):
    """Share of normal population/activity present (evacuation and return)."""
    return pl(t, [(ts("2027-09-12T18:00Z"), 1.0), (ts("2027-09-13T20:00Z"), 0.72), (ts("2027-09-16T12:00Z"), 0.74),
                  (ts("2027-09-18T12:00Z"), 0.90), (ts("2027-09-24T12:00Z"), 1.0)])


def load_factor(t):
    """Electrical load as a fraction of system peak (0.27 .. 1.0)."""
    a = ambient_c(t)
    hl = local_hour(t)
    cooling = np.clip((a - 18.0) / 14.0, 0, 1.1)
    heating = np.clip((11.0 - a) / 10.0, 0, 0.6)
    shape = 0.66 + 0.19 * np.cos(2 * np.pi * (hl - 17.0) / 24) + 0.045 * np.cos(4 * np.pi * (hl - 8.5) / 24)
    lf = shape * (0.60 + 0.42 * cooling + 0.28 * heating)
    lf = np.where(is_weekend(t), lf * 0.94, lf)
    return np.clip(lf * (0.55 + 0.45 * evac_factor(t)), 0.2, 1.0)


def water_demand_mgd(t):
    """What customers and leaks would draw if pressure were normal."""
    a = ambient_c(t)
    hl = local_hour(t)
    season = 0.80 + 0.27 * np.clip((a - 12.0) / 18.0, 0, 1.05)
    diur = (0.93 + 0.20 * np.exp(-((hl - 7.2) / 2.3) ** 2) + 0.22 * np.exp(-((hl - 19.6) / 2.6) ** 2)
            - 0.27 * np.exp(-((hl - 3.0) / 2.6) ** 2) - 0.27 * np.exp(-((hl - 27.0) / 2.6) ** 2))
    wk = np.where(is_weekend(t), 1.03, 1.0)
    leaks = pl(t, [(T["plant_feeds"] - 7200, 0.0), (T["plant_feeds"], 0.24), (ts("2027-10-19T12:00Z"), 0.05),
                   (ts("2027-11-03T12:00Z"), 0.0)])
    return 62.0 * season * diur * wk * evac_factor(t) * (1 + leaks)


# ------------------------------------------------------------------ plant pumps
PUMP_MGD = 18.75
TP_MGD = 3.0


def pump_state(t):
    """Run status (1 running, 0 stopped, 2 fault) of the four high-service pumps and temporary pumps."""
    pf = T["plant_feeds"]
    p1 = step_fn(t, [(pf, 2), (pf + 205, 1)], 1)
    p2 = step_fn(t, [(pf, 2), (T["p2_back"], 1)], 1)
    p3 = step_fn(t, [(pf + 385, 2), (T["p3_restart"], 1)], 1)
    p4 = step_fn(t, [(pf, 2), (pf + 1260, 0), (T["p4_restart"], 1), (T["sub3_cmd"] + 2, 2),
                     (T["sub3_cmd"] + 1500, 0), (T["p4_tempgen"], 1)], 1)
    tp1 = step_fn(t, [(T["tp1_on"], 1), (T["tp1_off"], 0)], 0)
    tp2 = step_fn(t, [(T["tp2_on"], 1), (T["tp2_off"], 0)], 0)
    return p1, p2, p3, p4, tp1, tp2


def feed_dead(t):
    a = step_fn(t, [(T["plant_feeds"], 1), (T["feed_a_back"], 0)], 0)
    b = step_fn(t, [(T["plant_feeds"], 1), (T["feed_b_back"], 0), (T["sub3_cmd"] + 1, 1), (T["sub3_close"], 0)], 0)
    return a, b


def p3_derate(t):
    # on the standby generator at low voltage until it overheats and trips; damaged afterwards
    return step_fn(t, [(T["plant_feeds"], 0.45), (T["plant_feeds"] + 385, 0.55), (T["p3_full"], 1.0)], 1.0)


def p3_lowered(t):
    return step_fn(t, [(T["p3_sp"], 1), (T["p3_restore"], 0)], 0)


def plant_capacity(t):
    """(all, general) deliverable capacity in MGD. 'general' is what the zones other than Zone 4
    feel: P-3 and P-4 discharge into the Zone 4 transmission main, so losing them mostly hurts Zone 4."""
    p1, p2, p3, p4, tp1, tp2 = pump_state(t)
    fa, fb = feed_dead(t)
    k1 = np.where(fa == 1, 0.70, 1.0)                    # P-1 on the standby generator
    d3 = p3_derate(t)
    low = p3_lowered(t)
    k3_all = d3 * np.where(low == 1, 0.35, 1.0)
    k3_gen = d3 * np.where(low == 1, 1 - 0.3 * 0.65, 1.0)
    p4_lost_later = (np.asarray(t) > T["sub3_cmd"]) & (np.asarray(t) < T["p4_tempgen"])
    p4_gen = np.where(p4 == 1, 1.0, np.where(p4_lost_later, 0.70, 0.0))
    base = PUMP_MGD * k1 * (p1 == 1) + PUMP_MGD * (p2 == 1) + TP_MGD * tp1 + TP_MGD * tp2
    cap_all = base + PUMP_MGD * k3_all * (p3 == 1) + PUMP_MGD * (p4 == 1)
    cap_gen = base + PUMP_MGD * k3_gen * (p3 == 1) + PUMP_MGD * p4_gen
    return cap_all, cap_gen


ZONE_NOMINAL = {1: 62.0, 2: 58.0, 3: 60.0, 4: 60.0, 5: 56.0}
ZONE_SHARE = {1: 0.20, 2: 0.24, 3: 0.14, 4: 0.26, 5: 0.16}


def supply_ratios(t):
    d = water_demand_mgd(t)
    cap_all, cap_gen = plant_capacity(t)
    r_all = np.clip(0.97 * cap_all / d, 0, 1)
    r_gen = np.clip(0.97 * cap_gen / d, 0, 1)
    return d, r_all, r_gen


def zone_pressure_general(t, zone):
    d, r_all, r_gen = supply_ratios(t)
    hl = local_hour(t)
    dip = 2.4 * (np.exp(-((hl - 7.2) / 2.3) ** 2) + np.exp(-((hl - 19.6) / 2.6) ** 2)) - 1.2 * np.exp(-((hl - 3.0) / 2.6) ** 2)
    return np.maximum(ZONE_NOMINAL[zone] - 75.0 * (1 - r_gen) - dip, 6.0)


def zone4_pressure(t):
    """Zone 4 distribution pressure (psi): the general system until the P-3 setpoint is lowered,
    then the canon curve (19 psi four hours later, crossing 20 at 05:51Z; 14 after P-4 loses its
    supply; 14-17 until the setpoint is restored on D+28; 32 eight hours later; 40 by D+30)."""
    t = np.asarray(t, dtype=np.float64)
    gen = zone_pressure_general(t, 4)
    t0, tc = T["p3_sp"], T["z4_cross20"]
    v0 = float(zone_pressure_general(np.array([t0]), 4)[0])
    floor_a = 17.8
    tau = (tc - t0) / math.log((v0 - floor_a) / (20.0 - floor_a))
    seg_a = floor_a + (v0 - floor_a) * np.exp(-np.clip((t - t0) / tau, -5, 60))
    seg_a = seg_a + 0.25 * np.clip((t - tc - 3600) / 7200, 0, 1) * np.sin(2 * np.pi * (t % DAY) / DAY)
    tb = T["sub3_cmd"]
    vb0 = floor_a + (v0 - floor_a) * math.exp(-(tb - t0) / tau)
    seg_b = 14.2 + (vb0 - 14.2) * np.exp(-np.clip((t - tb) / 2400.0, -5, 60))
    hz = (t % DAY) / 3600.0
    seg_c = 15.55 + 0.87 * np.sin(2 * np.pi * (hz - 10.47) / 24)
    w = np.clip((t - tb - 3 * 3600) / (6 * 3600), 0, 1)
    seg_bc = seg_b * (1 - w) + seg_c * w
    tr = T["p3_restore"]
    vr = float((15.55 + 0.87 * math.sin(2 * math.pi * (((tr % DAY) / 3600.0) - 10.47) / 24)))
    seg_d = np.where(t < tr + 8 * 3600, vr + (32.0 - vr) * (1 - np.exp(-np.clip((t - tr) / 9000.0, -5, 60))) / (1 - math.exp(-8 * 3600 / 9000.0)),
                     np.interp(t, [tr + 8 * 3600, ts("2027-10-14T12:00Z")], [32.0, 40.0]))
    blend_end = ts("2027-10-17T12:00Z")
    wb = np.clip((t - ts("2027-10-14T12:00Z")) / (blend_end - ts("2027-10-14T12:00Z")), 0, 1)
    seg_e = 40.0 * (1 - wb) + np.maximum(gen, 40.0) * wb
    out = np.where(t < t0, gen,
          np.where(t < tb, seg_a,
          np.where(t < tr, seg_bc,
          np.where(t < ts("2027-10-14T12:00Z"), seg_d,
          np.where(t < blend_end, seg_e, gen)))))
    return out


# ------------------------------------------------------------------ feeders and customers out
FEEDERS = [  # feeder id (equipment id), substation, breaker tag stem, customers served, area id
    ("GW-SUB01-CB-2", "GW-FAC-SUB-01", "GW.SUB1.CB2", 9500, "AREA-NBH-CALALLEN"),
    ("GW-SUB01-CB-3", "GW-FAC-SUB-01", "GW.SUB1.CB3", 8000, "AREA-NBH-ANNAVILLE"),
    ("GW-SUB01-CB-4", "GW-FAC-SUB-01", "GW.SUB1.CB4", 6500, "AREA-NBH-TULOSO"),
    ("GW-SUB02-CB-5", "GW-FAC-SUB-02", "GW.SUB2.CB5", 6300, "AREA-NBH-HILLCREST"),
    ("GW-SUB02-CB-6", "GW-FAC-SUB-02", "GW.SUB2.CB6", 8400, "AREA-NBH-OAKPARK"),
    ("GW-SUB02-CB-8", "GW-FAC-SUB-02", "GW.SUB2.CB8", 6300, "AREA-NBH-INNERHARBOR"),
    ("GW-SUB03-CB-9", "GW-FAC-SUB-03", "GW.SUB3.CB9", 4300, "AREA-NBH-LEOPARD"),
    ("GW-SUB03-CB-10", "GW-FAC-SUB-03", "GW.SUB3.CB10", 6800, "AREA-NBH-WESTSIDE"),
    ("GW-SUB03-CB-11", "GW-FAC-SUB-03", "GW.SUB3.CB11", 3900, "AREA-NBH-MOLINA"),
    ("GW-SUB04-CB-14", "GW-FAC-SUB-04", "GW.SUB4.CB14", 7000, "AREA-NBH-SOUTHSIDE"),
    ("GW-SUB04-CB-15", "GW-FAC-SUB-04", "GW.SUB4.CB15", 6000, "AREA-ZIP-78415"),
    ("GW-SUB04-CB-16", "GW-FAC-SUB-04", "GW.SUB4.CB16", 5000, "AREA-NBH-GREENWOOD"),
    ("GW-SUB05-CB-18", "GW-FAC-SUB-05", "GW.SUB5.CB18", 6000, "AREA-NBH-FLOURBLUFF"),
    ("GW-SUB05-CB-19", "GW-FAC-SUB-05", "GW.SUB5.CB19", 4500, "AREA-NBH-PADREISLAND"),
    ("GW-SUB05-CB-20", "GW-FAC-SUB-05", "GW.SUB5.CB20", 5500, "AREA-ZIP-78412"),
    ("GW-DSS01-FDR-11", "GW-FAC-DSS-01", "GW.DSS1.FDR11", 5200, "AREA-NBH-DOWNTOWN"),
    ("GW-DSS01-FDR-12", "GW-FAC-DSS-01", "GW.DSS1.FDR12", 3800, "AREA-NBH-DELMAR"),
]
FEEDER_IDS = [f[0] for f in FEEDERS]
SERVED = {f[0]: f[3] for f in FEEDERS}
OUT_STEP = 900
OUT_START = ts("2027-09-10T05:00Z")
OUT_END = ts("2027-10-27T05:00Z")
OUT_GRID = np.arange(OUT_START, OUT_END + 1, OUT_STEP, dtype=np.int64)


def _fixed_curves(t):
    """Feeders whose outage is set directly by canon events."""
    lf = T["landfall"]
    d = {}
    d["GW-SUB02-CB-5"] = pl(t, [(lf, 0), (lf + 9000, 6300), (T["isolate"], 6300), (T["all_restored"] - 1, 1900), (T["all_restored"], 0)])
    d["GW-SUB02-CB-8"] = pl(t, [(lf + 1800, 0), (lf + 10800, 6300), (T["isolate"], 6300), (ts("2027-10-18T12:00Z"), 0)])
    d["GW-SUB02-CB-6"] = pl(t, [(lf + 3600, 0), (lf + 14400, 6400), (ts("2027-09-20T22:00Z"), 6400), (ts("2027-09-21T03:00Z"), 0),
                                 (ts("2027-09-21T14:30Z") - 1, 0), (ts("2027-09-21T14:30Z"), 8400), (T["isolate"], 8400),
                                 (ts("2027-10-17T06:00Z"), 0)])
    d["GW-SUB03-CB-9"] = pl(t, [(lf, 0), (lf + 10800, 4300), (T["isolate"], 4300), (T["all_restored"] - 1, 1300), (T["all_restored"], 0)])
    d["GW-SUB03-CB-11"] = pl(t, [(lf + 2700, 0), (lf + 12600, 3900), (T["isolate"], 3900), (ts("2027-10-17T18:00Z"), 0)])
    d["GW-SUB03-CB-10"] = pl(t, [(lf + 3600, 0), (lf + 14400, 4300), (ts("2027-09-19T10:00Z"), 4300), (ts("2027-09-20T00:00Z"), 0),
                                  (ts("2027-09-24T19:45Z") - 1, 0), (ts("2027-09-24T19:45Z"), 6800), (T["isolate"], 6800),
                                  (ts("2027-10-16T12:00Z"), 0)])
    d["GW-DSS01-FDR-11"] = step_fn(t, [(T["dss_trip"], 5200), (T["srmc_restored"], 0)], 0)
    return d


def _fixed_total_late(t):
    """D+28 to D+35: SUB-02 and SUB-03 circuits go from 36,000 to 3,200 by manual switching."""
    return pl(t, [(T["isolate"], 36000), (T["all_restored"] - 1, 3200), (T["all_restored"], 0)])


def _flex_total(t):
    """Customers out on all other feeders (storm damage being repaired)."""
    lf = T["landfall"]
    tr = T["sub1_trip"]
    return pl(t, [(lf, 0), (lf + 3600, 6200), (tr - 1, 8100), (tr, 29220), (lf + 7200, 30400), (lf + 10800, 33000),
                  (lf + 14400, 35300), (ts("2027-09-21T14:30Z"), 22000), (ts("2027-09-24T19:45Z"), 8000),
                  (ts("2027-09-28T12:00Z"), 0)])


_FLEX = ["GW-SUB01-CB-2", "GW-SUB01-CB-3", "GW-SUB01-CB-4", "GW-SUB04-CB-14", "GW-SUB04-CB-15", "GW-SUB04-CB-16",
         "GW-SUB05-CB-18", "GW-SUB05-CB-19", "GW-SUB05-CB-20", "GW-DSS01-FDR-12"]
# how stubborn each flexible feeder's damage is: (weight at peak, days until its share has halved)
# The barrier-island and bayfront feeders (Flour Bluff, Padre Island) take the surge and the strongest wind and are the
# slowest to rebuild; inland feeders lose laterals to wind and trees and come back sooner.
_FLEX_SHAPE = {"GW-SUB01-CB-2": (0.80, 4.2), "GW-SUB01-CB-3": (0.74, 3.4), "GW-SUB01-CB-4": (0.66, 2.6),
               "GW-SUB04-CB-14": (0.05, 2.5), "GW-SUB04-CB-15": (0.06, 3.0), "GW-SUB04-CB-16": (0.08, 3.4),
               "GW-SUB05-CB-18": (1.00, 6.5), "GW-SUB05-CB-19": (1.00, 7.5), "GW-SUB05-CB-20": (0.12, 3.0),
               "GW-DSS01-FDR-12": (0.12, 1.8)}


def _anchor_times():
    """Instants where the map must show the canon figure exactly (peak, the two breaker events and the
    quarter-hour before each, the end of storm repairs, isolation, the last switching)."""
    a = [T["landfall"] + 14400, ts("2027-09-21T14:15Z"), ts("2027-09-21T14:30Z"), ts("2027-09-24T19:30Z"), ts("2027-09-24T19:45Z"),
         ts("2027-09-28T12:00Z"), T["isolate"] - T["isolate"] % OUT_STEP, T["all_restored"] - OUT_STEP, T["all_restored"]]
    return {int((x - OUT_START) // OUT_STEP) for x in a}


def _stairs(fid, t, c, served, anchors):
    """Customers out as an outage map shows them: the smooth damage/repair curve c turned into steps.
    Outages are reported in lumps; customers come back a lateral or a line section at a time when a crew
    closes a switch, almost only between about 06:30 and 20:30 local; now and then a section that was
    just restored trips again and is out for a few hours. At the anchor instants the value is c exactly."""
    g = rng("ot", "outage-stairs", fid)
    hr = local_hour(t)
    out = np.empty(len(c))
    cur = float(c[0])
    lump = lambda: served * float(g.uniform(0.012, 0.055))
    thr_up, thr_dn = lump() * 0.6, lump()
    extra, extra_until = 0.0, -1
    for i in range(len(c)):
        ci = float(c[i])
        jump = i > 0 and abs(ci - float(c[i - 1])) > 0.15 * served
        if ci <= 0.5 or ci >= served - 0.5 or i in anchors or jump:
            cur, extra = ci, 0.0
        elif ci > cur:                                   # more customers reported out
            if ci - cur >= thr_up:
                cur, thr_up = ci, lump() * 0.6
        else:                                            # repairs
            crews = 6.5 <= hr[i] < 20.5 or g.random() < 0.02
            if crews and cur - ci >= thr_dn:
                cur = max(ci, cur - thr_dn * float(g.uniform(0.9, 1.7)))
                thr_dn = lump()
                if g.random() < 0.07 and extra == 0.0:   # a restored section trips again
                    extra, extra_until = served * float(g.uniform(0.008, 0.035)), i + int(g.integers(5, 22))
        if extra and i >= extra_until:
            extra = 0.0
        out[i] = min(served, cur + extra)
    return out


def outage_table():
    """Customers out per feeder on OUT_GRID (15 min). Returns {feeder_id: int array}. Totals follow
    power.customers_out_series in the canon timeline: 72,000 at 10:00Z on D0; 48,000 just before the
    SUB-02 breaker opens on D+7 and 56,400 after; +6,800 at 19:45Z on D+10; about 36,000 from D+14 to
    D+28; 3,200 before the final switching at 20:00Z on D+35; then none."""
    if "out" in _CACHE:
        return _CACHE["out"]
    t = OUT_GRID.astype(np.float64)
    out = {f: np.zeros(len(t)) for f in FEEDER_IDS}
    fixed = _fixed_curves(t)
    for f, v in fixed.items():
        out[f] = v
    # late phase: scale the six SUB-02/SUB-03 feeders to the canon total
    six = ["GW-SUB02-CB-5", "GW-SUB02-CB-6", "GW-SUB02-CB-8", "GW-SUB03-CB-9", "GW-SUB03-CB-10", "GW-SUB03-CB-11"]
    late = t >= T["isolate"]
    s = sum(out[f] for f in six)
    target = _fixed_total_late(t)
    scale = np.where(late & (s > 0), target / np.maximum(s, 1), 1.0)
    for f in six:
        out[f] = np.where(late, out[f] * scale, out[f])
    # flexible feeders
    flex = _flex_total(t)
    tr = T["sub1_trip"]
    sub1_dead = (t >= tr) & (t < T["sub1_back"])
    days = np.maximum(t - (T["landfall"] + 14400), 0) / DAY
    w = {}
    for f in _FLEX:
        w0, half = _FLEX_SHAPE[f]
        w[f] = SERVED[f] * w0 * 0.5 ** (days / half)
    sub1 = ["GW-SUB01-CB-2", "GW-SUB01-CB-3", "GW-SUB01-CB-4"]
    rest = [f for f in _FLEX if f not in sub1]
    forced = np.where(sub1_dead, 24000.0, 0.0)
    for f in sub1:
        out[f] = np.where(sub1_dead, SERVED[f], 0.0)
    remaining = np.maximum(flex - forced, 0)
    pool = [f for f in _FLEX]
    wsum_all = sum(w[f] for f in pool)
    wsum_rest = sum(w[f] for f in rest)
    for f in pool:
        share_all = remaining * w[f] / np.maximum(wsum_all, 1e-9)
        share_rest = remaining * w[f] / np.maximum(wsum_rest, 1e-9) if f in rest else 0.0
        val = np.where(sub1_dead, share_rest if f in rest else SERVED[f], share_all)
        out[f] = np.minimum(val, SERVED[f])
    # anything clipped goes to the feeders with room, in order
    short = flex - sum(out[f] for f in pool)
    for f in ["GW-SUB05-CB-18", "GW-SUB05-CB-19", "GW-SUB04-CB-16", "GW-SUB04-CB-15", "GW-SUB04-CB-14", "GW-SUB05-CB-20"]:
        room = SERVED[f] - out[f]
        add = np.clip(short, 0, room)
        out[f] += add
        short -= add
    # what the map shows: steps, daylight restoration, setbacks
    anchors = _anchor_times()
    for f in FEEDER_IDS:
        out[f] = _stairs(f, t, out[f], SERVED[f], anchors)
    # small everyday outages (a fuse, a tree limb, a car into a pole). Outside the storm they are all there is; during
    # the long tail of the restoration they keep happening on the feeders that are back in service.
    g = rng("ot", "outage-background")
    quiet = (t < ts("2027-09-13T12:00Z")) | (t > ts("2027-10-20T12:00Z"))
    tail = (t > ts("2027-09-25T12:00Z")) & (t <= ts("2027-10-20T12:00Z"))
    held = set(six)                                      # the SUB-02 and SUB-03 circuits are governed by canon in the tail
    k = 0
    while k < len(t):
        gap = int(g.integers(60, 260))
        k += max(5, gap // 7) if tail[min(k, len(t) - 1)] else gap     # more of them while 100,000 customers' worth of line is freshly repaired
        if k >= len(t):
            break
        f = FEEDER_IDS[int(g.integers(0, len(FEEDER_IDS)))]
        n = int(g.integers(4, 14))
        size = int(g.choice([12, 25, 40, 64, 110, 180, 260, 390]))
        if not quiet[k] and not (tail[k] and f not in held):
            continue
        if any(i in anchors for i in range(k - 1, k + n + 1)):
            continue
        out[f][k:k + n] += size
    # outer rain bands: scattered wind outages in the hours before landfall, growing into the landfall ramp
    gp = rng("ot", "outage-prelandfall")
    i0 = int((ts("2027-09-14T06:15Z") - OUT_START) // OUT_STEP)
    i_first = int((ts("2027-09-13T21:45Z") - OUT_START) // OUT_STEP)
    for f in FEEDER_IDS:
        val = out[f][i0] * float(gp.uniform(0.5, 0.85))
        k = i0 - 1
        while k >= i_first and val >= 6:
            out[f][k] = max(out[f][k], val)
            if gp.random() < 0.4:
                val *= float(gp.uniform(0.3, 0.8))
            k -= 1
    # 24 Oct: a transmission-side fault drops the Flour Bluff circuit (the air station's commercial feed) for 52 minutes
    a = int((ts("2027-10-24T19:30Z") - OUT_START) // OUT_STEP)
    out["GW-SUB05-CB-18"][a:a + 3] = SERVED["GW-SUB05-CB-18"]
    # ordinary circuit lockouts of the same kind (a pole hit, a failed lightning arrester): whole feeder out for under two hours
    for when, f, n in (("2027-10-21T13:15Z", "GW-SUB05-CB-20", 3), ("2027-10-26T02:00Z", "GW-DSS01-FDR-12", 5), ("2027-09-10T16:45Z", "GW-SUB04-CB-16", 2)):
        a = int((ts(when) - OUT_START) // OUT_STEP)
        out[f][a:a + n] = SERVED[f]
    res = {}
    for f in FEEDER_IDS:
        res[f] = np.clip(np.rint(out[f]), 0, SERVED[f]).astype(np.int64)
    # exact canon totals at the anchor instants (rounding drift goes to the largest flexible feeder)
    _CACHE["out"] = res
    return res


_CACHE = {}


def energized_fraction(feeder_id, t):
    """Share of a feeder's customers with power at times t (1.0 outside the outage-map window)."""
    tab = outage_table()[feeder_id]
    idx = np.clip(((np.asarray(t, dtype=np.float64) - OUT_START) // OUT_STEP).astype(int), 0, len(tab) - 1)
    inside = (np.asarray(t) >= OUT_START) & (np.asarray(t) <= OUT_END)
    return np.where(inside, 1.0 - tab[idx] / SERVED[feeder_id], 1.0)


# ------------------------------------------------------------------ substation state
SUBS = {  # n: (asset id, tag stem, peak MW, main breaker label, feeders)
    1: ("GW-FAC-SUB-01", "GW.SUB1", 150.0, "CB-1", ["GW-SUB01-CB-2", "GW-SUB01-CB-3", "GW-SUB01-CB-4"]),
    2: ("GW-FAC-SUB-02", "GW.SUB2", 120.0, "CB-7", ["GW-SUB02-CB-5", "GW-SUB02-CB-6", "GW-SUB02-CB-8"]),
    3: ("GW-FAC-SUB-03", "GW.SUB3", 90.0, "CB-12", ["GW-SUB03-CB-9", "GW-SUB03-CB-10", "GW-SUB03-CB-11"]),
    4: ("GW-FAC-SUB-04", "GW.SUB4", 110.0, "CB-13", ["GW-SUB04-CB-14", "GW-SUB04-CB-15", "GW-SUB04-CB-16"]),
    5: ("GW-FAC-SUB-05", "GW.SUB5", 100.0, "CB-17", ["GW-SUB05-CB-18", "GW-SUB05-CB-19", "GW-SUB05-CB-20"]),
}


def main_breaker(n, t):
    """Main breaker position: 1 closed, 0 open (commanded), 2 tripped by protection."""
    if n == 1:
        return step_fn(t, [(T["sub1_trip"], 2), (T["sub1_back"], 1)], 1)
    if n == 2:
        return step_fn(t, [(T["sub2_cmd"] + 2, 0), (T["sub2_close"] + 3, 1)], 1)
    if n == 3:
        return step_fn(t, [(T["sub3_cmd"] + 2, 0), (T["sub3_close"] + 3, 1)], 1)
    return np.ones(len(np.atleast_1d(t)))


def storm_sag_pu(n, t):
    """Per-unit bus voltage multiplier through the landfall. SUB-01 reaches 0.939 pu at 07:12Z;
    the others sag as far or further without tripping at their 0.88 pu setting."""
    lf = T["landfall"]
    tr = T["sub1_trip"]
    if n == 1:
        pts = [(lf - 5 * 3600, 1.0), (lf - 3600, 0.972), (lf + 1800, 0.953), (lf + 3600, 0.9447), (tr - 440, 0.9432),
               (tr - 150, 0.9412), (tr - 2, 0.9390), (tr + 3 * 3600, 0.955), (lf + 10 * 3600, 0.985), (lf + 30 * 3600, 1.0)]
    else:
        low = {2: 0.931, 3: 0.934, 4: 0.929, 5: 0.927}[n]
        pts = [(lf - 5 * 3600, 1.0), (lf - 3600, 0.970), (lf + 1800, 0.950), (lf + 3600, low + 0.008), (lf + 5400, low),
               (lf + 6900, low + 0.003), (lf + 3 * 3600, 0.952), (lf + 10 * 3600, 0.985), (lf + 30 * 3600, 1.0)]
    return pl(t, pts)


COMMS_GAPS = {  # site key -> [(start, end)] when the master station gets no data from the site
    "SUB1": [(T["sub1_trip"] + 1740, ts("2027-09-15T11:38Z"))],
    "SUB2": [(ts("2027-09-14T06:36Z"), ts("2027-09-16T15:04Z"))],
    "SUB3": [(ts("2027-09-14T07:26Z"), ts("2027-09-15T20:11Z"))],
    "SUB4": [(ts("2027-09-14T07:07Z"), ts("2027-09-17T02:02Z"))],
    "SUB5": [(ts("2027-09-14T08:12Z"), ts("2027-09-15T09:17Z"))],
    "DSS1": [(T["dss_trip"] + 200, ts("2027-09-17T04:05Z"))],
    "UTL1": [(T["plant_feeds"] + 1560, ts("2027-09-14T23:10Z")), (ts("2027-09-15T03:12Z"), ts("2027-09-15T07:44Z")),
             (ts("2027-09-15T15:21Z"), ts("2027-09-15T17:02Z")), (ts("2027-09-16T01:33Z"), ts("2027-09-16T04:09Z"))],
    "GEN1": [(ts("2027-09-14T07:21Z"), ts("2027-09-14T19:30Z"))],
    "DIST": [(ts("2027-09-14T08:22Z"), ts("2027-09-15T14:06Z")), (ts("2027-09-16T02:10Z"), ts("2027-09-16T05:30Z"))],
    "WTR1": [(ts("2027-09-14T10:05Z"), ts("2027-09-14T15:40Z"))],
    "WTR2": [(ts("2027-09-14T09:12Z"), ts("2027-09-14T21:18Z"))],
    "WTR3": [(ts("2027-09-14T11:31Z"), ts("2027-09-14T13:02Z"))],
}
for _i, (_a, _b) in enumerate([("06:58", "09-16T10:20"), ("07:31", "09-15T18:44"), ("08:02", "09-16T22:09"), ("06:44", "09-17T01:15"),
                              ("07:15", "09-16T03:37"), ("07:50", "09-15T12:26"), ("06:31", "09-16T16:48"), ("07:22", "09-17T05:02"),
                              ("08:09", "09-15T23:51")]):
    COMMS_GAPS["TK%02d" % (_i + 1)] = [(ts("2027-09-14T%sZ" % _a), ts("2027-%sZ" % _b))]


def comms_ok(site, t):
    t = np.asarray(t, dtype=np.float64)
    ok = np.ones(len(t), dtype=bool)
    for a, b in COMMS_GAPS.get(site, []):
        ok &= ~((t >= a) & (t < b))
    return ok


# ------------------------------------------------------------------ generators and fuel (shared with fuel_deliveries)
def plant_gen_running(t):
    """O.N. Stevens standby generator (EQP-1140): storm run plus the weekly test (Wednesday 15:00Z, 30 min)."""
    t = np.asarray(t, dtype=np.float64)
    storm = (t >= T["plant_feeds"] + 27) & (t < T["feed_a_back"] + 1140)
    dow = (t // DAY + 4) % 7                 # 0 = Sunday (UTC)
    sod = t % DAY
    test = (dow == 3) & (sod >= 15 * 3600) & (sod < 15 * 3600 + 1800) & ~((t > T["landfall"] - 3 * DAY) & (t < T["feed_a_back"] + 5 * DAY))
    return storm | test


PLANT_GEN_DELIVERIES = [  # (epoch, percent of tank added, gallons) -> also written as delivery tickets
    (ts("2027-08-26T14:20Z"), 6.0, 480), (ts("2027-09-11T15:05Z"), 7.0, 560),
    (ts("2027-09-15T20:34Z"), 34.0, 2720), (ts("2027-09-16T11:48Z"), 22.0, 1760),
    (ts("2027-09-20T16:12Z"), 37.0, 2960), (ts("2027-10-27T15:30Z"), 5.0, 400), (ts("2027-12-08T16:05Z"), 6.0, 480),
]
PLANT_GEN_TANK_GAL = 8000


def plant_gen_fuel_pct():
    """Fuel level (% of 8,000 gal) of the plant standby generator on GRID."""
    if "pgf" in _CACHE:
        return _CACHE["pgf"]
    run = plant_gen_running(GRID)
    level = np.empty(N)
    cur = 93.0
    deliveries = sorted(PLANT_GEN_DELIVERIES)
    di = 0
    for i in range(N):
        if run[i]:
            cur -= 1.32 * STEP / 3600.0
        while di < len(deliveries) and deliveries[di][0] <= GRID[i]:
            cur = min(99.0, cur + deliveries[di][1])
            di += 1
        level[i] = cur
    _CACHE["pgf"] = level
    return level
