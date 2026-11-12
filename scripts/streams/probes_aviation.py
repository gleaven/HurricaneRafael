"""Stream descriptions and probes for the aviation and remote-sensing family:
adsb, drone_detections, drone_telemetry, satellite. Used by scripts/check_streams.py.

Every probe reads the files on disk and returns (ok, detail)."""
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict
from functools import lru_cache

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import ROOT, ts, iso, reg, local_ts, local_dt, day_of, D0_EPOCH, geo_handle   # noqa: E402

M_LAT = 110950.0


def dist_m(la1, lo1, la2, lo2):
    return math.hypot((la1 - la2) * M_LAT, (lo1 - lo2) * 111320.0 * math.cos(math.radians((la1 + la2) / 2)))


def brg(la1, lo1, la2, lo2):
    return (math.degrees(math.atan2((lo2 - lo1) * math.cos(math.radians(la1)), la2 - la1)) + 360) % 360


AC = {(a.get("callsign_voice") or a["callsign"]): a for a in reg("aircraft_registry")["aircraft"]}
ICAO = {k: v["icao24"] for k, v in AC.items()}
INFRA = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"] if a.get("latitude") is not None}
AREAS = {a["area_id"]: a for a in reg("areas")["areas"]}
NGP = (27.6927, -97.29038)
AUS = (30.19453, -97.66988)
NFW = (32.76919, -97.44153)
MARINA = (27.84593, -97.22564)
BERTH = (27.81447, -97.40133)


# ============================================================================ ADS-B
@lru_cache(maxsize=None)
def adsb():
    """All ADS-B rows by aircraft: {icao: array[t, lat, lon, geo_alt, gnd, v, track, nic, nacp]}"""
    out = defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "adsb", "*.csv"))):
        with open(fp, encoding="utf-8") as fh:
            rd = csv.reader(fh)
            h = next(rd)
            ix = {c: i for i, c in enumerate(h)}
            for r in rd:
                out[r[0]].append((int(r[ix["time_position"]]), float(r[ix["latitude"]]), float(r[ix["longitude"]]), float(r[ix["geo_altitude"]] or 0),
                                  1.0 if r[ix["on_ground"]] == "True" else 0.0, float(r[ix["velocity"]]), float(r[ix["true_track"]]), float(r[ix["nic"]]), float(r[ix["nac_p"]])))
    return {k: np.array(v) for k, v in out.items()}


def rows(call, t0, t1):
    a = adsb().get(ICAO[call])
    if a is None:
        return np.zeros((0, 9))
    return a[(a[:, 0] >= t0) & (a[:, 0] <= t1)]


def sorties(a, base=NGP, radius=3500):
    """Split rows into flights: airborne runs separated by ground rows or gaps over 20 minutes."""
    out, cur = [], []
    for r in a:
        if r[4] == 1.0:
            if cur:
                out.append(np.array(cur)); cur = []
            continue
        if cur and r[0] - cur[-1][0] > 1200:
            out.append(np.array(cur)); cur = []
        cur.append(r)
    if cur:
        out.append(np.array(cur))
    return [s for s in out if len(s) > 5]


def hovers(s, max_v=4.0, max_alt=70.0, min_s=120):
    """Hover segments (slow, low, at least min_s long) in a sortie: list of (t0, t1, lat, lon)."""
    out, cur = [], []
    for r in s:
        if r[5] <= max_v and r[3] <= max_alt:
            cur.append(r)
        else:
            if cur and cur[-1][0] - cur[0][0] >= min_s:
                out.append((cur[0][0], cur[-1][0], float(np.mean([q[1] for q in cur])), float(np.mean([q[2] for q in cur]))))
            cur = []
    if cur and cur[-1][0] - cur[0][0] >= min_s:
        out.append((cur[0][0], cur[-1][0], float(np.mean([q[1] for q in cur])), float(np.mean([q[2] for q in cur]))))
    return out


def in_bbox(lat, lon, area_id, pad=0.004):
    b = AREAS[area_id]["bbox"]
    return b[0] - pad <= lon <= b[2] + pad and b[1] - pad <= lat <= b[3] + pad


def p_navy_evacuation():
    t0, t1 = ts("2027-09-10T05:00Z"), ts("2027-09-11T05:00Z")
    back = local_ts(6, "00:00")
    calls = [c for c, a in AC.items() if "Training Air Wing" in a["operator"]]
    dep_times, bad = [], []
    for c in calls:
        a = rows(c, t0, t1)
        air = a[a[:, 4] == 0]
        if len(air) < 5:
            bad.append(c + " did not fly"); continue
        last = air[-1]
        want = brg(last[1], last[2], *NFW)
        if last[1] < 28.6 or abs((last[6] - want + 180) % 360 - 180) > 20:
            bad.append(f"{c} last seen at {last[1]:.2f}N heading {last[6]:.0f}")
        if len(rows(c, t1, back)):
            bad.append(c + " seen again before D+6")
        dep_times.append(air[0][0])
    if bad:
        return False, "; ".join(bad[:4])
    dep_times.sort()
    waves = 1 + sum(1 for a, b in zip(dep_times, dep_times[1:]) if b - a > 1800)
    returned = sum(1 for c in calls if len(rows(c, back, local_ts(9, "23:59"))))
    ok = waves >= 3 and returned == len(calls)
    return ok, f"{len(calls)} Navy trainers leave NAS Corpus Christi and NAS Kingsville northbound for Fort Worth in {waves} waves between {iso(int(dep_times[0]))[11:16]}Z and {iso(int(dep_times[-1]))[11:16]}Z; none seen again before D+6; {returned} back by D+9"


def p_first_rescue():
    a = rows("C6033", ts("2027-09-14T06:00Z"), ts("2027-09-14T08:00Z"))
    air = a[a[:, 4] == 0]
    if not len(air):
        return False, "CG-6033 not airborne"
    lift = air[0][0]
    hv = [h for h in hovers(air, min_s=180) if in_bbox(h[2], h[3], "AREA-NBH-FLOURBLUFF", 0.01)]
    on_scene = air[(air[:, 0] >= ts("2027-09-14T06:43Z")) & (air[:, 0] <= ts("2027-09-14T06:46Z"))]
    over_fb = len(on_scene) and all(in_bbox(r[1], r[2], "AREA-NBH-FLOURBLUFF", 0.02) for r in on_scene)
    first = min((h[0] for h in hv), default=0)
    ok = abs(lift - ts("2027-09-14T06:22Z")) <= 60 and dist_m(air[0][1], air[0][2], *NGP) < 3000 and over_fb and abs(first - ts("2027-09-14T06:51Z")) <= 90
    return ok, (f"CG-6033 lifts from NAS Corpus Christi {iso(int(lift))[11:19]}Z, searching over Flour Bluff by 06:44Z, {len(hv)} hoist hovers there "
                f"(the first from {iso(int(first))[11:19]}Z)")


def p_noaa42():
    a = rows("NOAA42", ts("2027-09-14T07:30Z"), ts("2027-09-14T09:30Z"))
    if not len(a):
        return False, "NOAA42 not present"
    k = int(np.argmin(np.abs(a[:, 0] - ts("2027-09-14T08:30Z"))))
    over_bay = 27.6 <= a[k, 1] <= 27.95 and -97.5 <= a[k, 2] <= -97.1 and abs(a[k, 0] - ts("2027-09-14T08:30Z")) <= 120
    others = set()
    for call, ac in AC.items():
        if call == "NOAA42":
            continue
        b = rows(call, ts("2027-09-12T05:01Z"), ts("2027-09-14T14:00Z"))
        b = b[b[:, 4] == 0]
        if len(b) and any(dist_m(r[1], r[2], 27.78, -97.40) < 110000 for r in b[:: max(1, len(b) // 50)]):
            others.add(ac["operator"].split(",")[0] if "Coast Guard" not in ac["operator"] else "Coast Guard")
    ok = over_bay and others <= {"Coast Guard"}
    return ok, f"NOAA42 at {a[k, 1]:.3f}N {abs(a[k, 2]):.3f}W, {a[k, 3]:.0f} m at {iso(int(a[k, 0]))[11:19]}Z; other aircraft airborne near Corpus Christi between the flight restriction and 14:00Z: {sorted(others) or 'none'}"


def p_arng():
    t0, t1 = ts("2027-09-15T05:00Z"), ts("2027-09-16T05:00Z")
    total, det = 0.0, []
    for c in ("GUNSMOKE01", "GUNSMOKE02", "GUNSMOKE03"):
        a = rows(c, t0, t1)
        if not len(a):
            return False, c + " not present"
        air = a[a[:, 4] == 0]
        gnd = a[a[:, 4] == 1]
        if not len(gnd) or dist_m(gnd[0][1], gnd[0][2], *NGP) > 4000:
            return False, c + " did not land at NAS Corpus Christi"
        first = air[0]
        if first[1] < 28.3:
            return False, f"{c} first seen at {first[1]:.2f}N, not arriving from the north"
        est_dep = first[0] - dist_m(first[1], first[2], *AUS) / (AC[c]["cruise_speed_kt"] * 0.514444)
        hrs = (gnd[0][0] - est_dep) / 3600.0
        total += hrs
        low = air[(air[:, 1] < 27.92) & (air[:, 3] < 500)]
        det.append(f"{c} {hrs:.2f} h ({len(low)} low-level fixes over the city)")
    b = rows("GUNSMOKE02", ts("2027-09-15T17:42Z"), ts("2027-09-15T17:46Z"))
    s2 = INFRA["GW-FAC-SUB-02"]
    near = len(b) and min(dist_m(r[1], r[2], s2["latitude"], s2["longitude"]) for r in b) < 1200
    ok = abs(total - 6.2) <= 0.4 and near
    return ok, f"three UH-60 sorties from the direction of Austin-Bergstrom, {total:.1f} flight hours in all ({'; '.join(det)}); one passes Harbor View substation at 17:44Z"


def missions(a, gap=500):
    """Engine start to shutdown: rows (airborne or on a pad with rotors turning) with no silence longer than gap seconds."""
    out, cur = [], []
    for r in a:
        if cur and r[0] - cur[-1][0] > gap:
            out.append(np.array(cur)); cur = []
        cur.append(r)
    if cur:
        out.append(np.array(cur))
    return [m for m in out if (m[:, 4] == 0).sum() > 5]


def p_rescue_d1():
    t0, t1 = ts("2027-09-15T05:00Z"), ts("2027-09-16T05:00Z")
    res, ok = [], True
    want = {"C6033": (7, 7), "C6041": (6, 6), "DPS110": (3, 6), "CAMCC-11": (3, 6)}
    areas = ("AREA-NBH-FLOURBLUFF", "AREA-NBH-NORTHBEACH")     # the two communities the public record names for air rescues
    seen_areas = set()
    for c, (lo, hi) in want.items():
        ss = missions(rows(c, t0, t1))
        hv = [h for m in ss for h in hovers(m[m[:, 4] == 0], min_s=90)]
        for h in hv:
            for ar in areas:
                if in_bbox(h[2], h[3], ar, 0.008):
                    seen_areas.add(ar)
        hrs = sum(m[-1][0] - m[0][0] for m in ss) / 3600.0
        res.append(f"{c}: {len(ss)} sorties, {hrs:.1f} h, {len(hv)} hover points")
        if not (lo <= len(ss) <= hi) or len(hv) < len(ss):
            ok = False
    ok = ok and len(seen_areas) == 2
    return ok, "; ".join(res) + f"; low hovers in {len(seen_areas)} of 2 communities (Flour Bluff, North Beach)"


def p_sheen_survey():
    best = None
    for c in ("C2306", "C2311"):
        a = rows(c, ts("2027-09-18T15:30Z"), ts("2027-09-18T17:00Z"))
        a = a[(a[:, 4] == 0) & (a[:, 1] > 27.70) & (a[:, 1] < 27.90) & (a[:, 2] > -97.52) & (a[:, 2] < -97.15) & (a[:, 3] < 900)]
        if len(a) < 20:
            continue
        east = np.sin(np.radians(a[:, 6])) > 0.5
        west = np.sin(np.radians(a[:, 6])) < -0.5
        seq = [1 if e else (-1 if w else 0) for e, w in zip(east, west)]
        seq = [s for s in seq if s]
        rev = sum(1 for x, y in zip(seq, seq[1:]) if x != y)
        if best is None or rev > best[1]:
            best = (c, rev, a)
    if not best:
        return False, "no Coast Guard fixed-wing aircraft low over the bays at 16:00Z"
    c, rev, a = best
    return rev >= 4, f"{c} flies {rev + 1} east-west lines over Nueces and Corpus Christi bays at {np.median(a[:, 3]):.0f} m between {iso(int(a[0, 0]))[11:16]}Z and {iso(int(a[-1, 0]))[11:16]}Z"


def arrivals(call, t0, t1, field=NGP):
    a = rows(call, t0 - 3600, t1 + 3600)
    n, times = 0, []
    prev_air = False
    for r in a:
        if r[4] == 1.0 and prev_air and dist_m(r[1], r[2], *field) < 4000 and t0 <= r[0] <= t1:
            n += 1; times.append(r[0])
        prev_air = r[4] == 0.0
    return n, times


def p_relief():
    t0, t1 = ts("2027-10-18T05:00Z"), ts("2027-10-28T05:00Z")
    mil = sum(arrivals(c, t0, t1)[0] for c, a in AC.items() if a["type_designator"] == "C17")
    civ = sum(arrivals(c, t0, t1)[0] for c, a in AC.items() if "charter" in a["role"].lower())
    days = set()
    for c, a in AC.items():
        if a["type_designator"] == "C17" or "charter" in a["role"].lower():
            for t in arrivals(c, t0, t1)[1]:
                days.add(day_of(t))
    return mil == 26 and civ == 14, f"{mil} C-17 arrivals and {civ} civil charter arrivals at NAS Corpus Christi on {len(days)} days (D+{min(days)} to D+{max(days)})" if days else "no arrivals"


def p_gps():
    j = INFRA["TANK-0390"]
    t0, t1 = ts("2027-10-22T05:00Z"), ts("2027-10-28T05:00Z")
    inside = [0, 0]; before = [0, 0]; far = [0, 0]; jumps = 0
    for icao, a in adsb().items():
        w = a[(a[:, 0] >= t0) & (a[:, 0] <= t1) & (a[:, 4] == 0)]
        if len(w):
            d = np.hypot((w[:, 1] - j["latitude"]) * M_LAT, (w[:, 2] - j["longitude"]) * 98500.0)
            near = w[d < 60000]
            inside[0] += len(near); inside[1] += int((near[:, 7] < 7).sum())
            fr = w[d > 80000]
            far[0] += len(fr); far[1] += int((fr[:, 7] < 7).sum())
            if len(near) > 2:
                dt = np.diff(near[:, 0])
                dd = np.hypot(np.diff(near[:, 1]) * M_LAT, np.diff(near[:, 2]) * 98500.0)
                jumps += int(((dt > 0) & (dt <= 60) & (dd / np.maximum(dt, 1) > 350)).sum())
        b = a[(a[:, 0] >= t0 - 6 * 86400) & (a[:, 0] < t0) & (a[:, 4] == 0)]
        if len(b):
            d = np.hypot((b[:, 1] - j["latitude"]) * M_LAT, (b[:, 2] - j["longitude"]) * 98500.0)
            nb = b[d < 60000]
            before[0] += len(nb); before[1] += int((nb[:, 7] < 7).sum())
    f_in = inside[1] / max(1, inside[0]); f_before = before[1] / max(1, before[0]); f_far = far[1] / max(1, far[0])
    ok = f_in > 0.25 and f_before < 0.01 and f_far < 0.01 and jumps >= 20
    return ok, (f"{f_in:.0%} of airborne reports within 60 km of the Quellmar terminal carry nic below 7 during the window ({inside[1]} of {inside[0]}), "
                f"{f_before:.1%} in the six days before and {f_far:.1%} beyond 80 km; {jumps} position jumps")


# ============================================================================ drone detections
DD = os.path.join(ROOT, "05_other_sources", "drone_detections")


@lru_cache(maxsize=None)
def detections():
    out = []
    for fp in sorted(glob.glob(os.path.join(DD, "detections_*.csv"))):
        with open(fp, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_t"] = ts(r["time_utc"])
                out.append(r)
    return out


@lru_cache(maxsize=None)
def status_rows():
    out = []
    for fp in sorted(glob.glob(os.path.join(DD, "sensor_status_*.csv"))):
        with open(fp, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_t"] = ts(r["time_utc"])
                out.append(r)
    return out


@lru_cache(maxsize=None)
def table(name):
    with open(os.path.join(DD, name), encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def tracks(sensor, t0, t1, kind="radar_plot"):
    g = defaultdict(list)
    for r in detections():
        if r["sensor_id"] == sensor and t0 <= r["_t"] <= t1 and r["detection_type"] == kind:
            g[r["track_id"]].append(r)
    return g


def longest(sensor, t0, t1, cls="unknown"):
    g = tracks(sensor, t0, t1)
    g = {k: v for k, v in g.items() if v[0]["classification"] == cls}
    if not g:
        return None
    k = max(g, key=lambda q: g[q][-1]["_t"] - g[q][0]["_t"])
    return g[k]


def track_stats(tr):
    rcs = np.median([float(r["rcs_m2"]) for r in tr])
    alt = np.median([float(r["altitude_m"]) for r in tr])
    la = np.array([float(r["latitude"]) for r in tr]); lo = np.array([float(r["longitude"]) for r in tr]); tt = np.array([r["_t"] for r in tr])
    dist = np.hypot(np.diff(la) * M_LAT, np.diff(lo) * 98500.0)
    sp = float(np.median([float(r["speed_mps"]) for r in tr]))
    return float(rcs), float(alt), sp, tt[0], tt[-1], la, lo


def p_1901():
    s1 = INFRA["GW-FAC-SUB-01"]
    t0, t1 = ts("2027-09-03T05:00Z"), ts("2027-09-12T05:01Z")
    hits = []
    for a in table("laanc_authorizations.csv"):
        if ts(a["end_utc"]) < t0 or ts(a["start_utc"]) > t1:
            continue
        la, lo = float(a["center_latitude"]), float(a["center_longitude"])
        if dist_m(la, lo, s1["latitude"], s1["longitude"]) < 3500 or (27.803 <= la <= 27.85 and -97.53 <= lo <= -97.393):
            hits.append(a["authorization_id"])
    w0, w1 = ts("2027-09-04T03:00Z"), ts("2027-09-04T06:00Z")
    st = [r for r in status_rows() if r["sensor_id"] == "USCG-RDR-R14" and w0 <= r["_t"] <= w1]
    online = len(st) >= 3 and all(r["status"] == "online" for r in st)
    trk = [r for r in detections() if r["sensor_id"] == "USCG-RDR-R14" and w0 <= r["_t"] <= w1]
    ok = not hits and online and not trk
    return ok, f"{len(hits)} authorisations for the Riverside / Up River Road corridor or the Inner Harbor between 3 and 12 September; buoy R-14 online 03:00Z-06:00Z on 4 September with {len(trk)} plots"


def esm_contact():
    t = ts("2027-09-05T06:47Z")
    return [r for r in detections() if r["sensor_id"] == "ESM-CAMCC04" and abs(r["_t"] - t) <= 5]


def p_1902():
    c = esm_contact()
    a = [r for r in c if abs(float(r["rf_center_mhz"]) - 902.4) < 0.05]
    b = [r for r in c if abs(float(r["rf_center_mhz"]) - 2437.0) < 0.5]
    if not a or not b:
        return False, "no 902.4 MHz / 2.437 GHz contact pair at 06:47Z on 5 September"
    same = abs(float(a[0]["bearing_deg_true"]) - float(b[0]["bearing_deg_true"])) <= 1.0
    pos = rows("CAMCC-04", ts("2027-09-05T06:45Z"), ts("2027-09-05T06:49Z"))
    flying = len(pos) and min(dist_m(r[1], r[2], float(a[0]["latitude"]), float(a[0]["longitude"])) for r in pos) < 9000 and pos[0][4] == 0
    radar = [r for r in detections() if r["detection_type"] == "radar_plot" and r["classification"] == "unknown" and abs(r["_t"] - ts("2027-09-05T06:47Z")) < 1800
             and r["authorization_id"] == "" and float(r["rcs_m2"]) < 0.02 and 100 < float(r["altitude_m"]) < 200]
    ok = same and abs(float(a[0]["duration_s"]) - 4.1) < 0.05 and bool(flying)
    return ok, (f"CAMCC-04 logs a {a[0]['duration_s']} s contact at 902.4 MHz on bearing {a[0]['bearing_deg_true']} true and a 2.437 GHz contact on the same bearing at 06:47Z from "
                f"{a[0]['latitude']}N {a[0]['longitude']}; the aircraft is airborne there in ADS-B; no authorisation and no matching radar track")


def p_1903():
    tr = longest("USCG-RDR-R18", ts("2027-09-06T04:00Z"), ts("2027-09-06T05:00Z"))
    if not tr:
        return False, "no unknown track on R-18"
    rcs, alt, sp, a, b, la, lo = track_stats(tr)
    s1 = INFRA["GW-FAC-SUB-01"]
    over = min(dist_m(x, y, s1["latitude"], s1["longitude"]) for x, y in zip(la, lo))
    ok = abs(a - ts("2027-09-06T04:15Z")) <= 90 and abs(b - ts("2027-09-06T04:33Z")) <= 90 and abs(rcs - 0.012) < 0.003 and abs(alt - 482 * 0.3048) < 12 and abs(sp - 12.4) < 1.0 \
        and over < 400 and all(r["alert"] == "false" for r in tr) and all(r["authorization_id"] == "" for r in tr)
    return ok, f"R-18 raw track {iso(int(a))[11:19]}Z-{iso(int(b))[11:19]}Z, RCS {rcs:.3f} m2, {alt / 0.3048:.0f} ft, {sp:.1f} m/s, passes {over:.0f} m from Riverside Switching Station, below the alert threshold, no authorisation"


def port_track(day, t_a, t_b):
    tr = longest("USCG-RDR-R22", ts(day + "T04:30Z"), ts(day + "T05:30Z"))
    if not tr:
        return None
    return track_stats(tr) + (tr,)


def p_1904():
    q = port_track("2027-09-09", "04:58", "05:17")
    if not q:
        return False, "no unknown track on R-22 on 9 September"
    rcs, alt, sp, a, b, la, lo, tr = q
    d = np.array([dist_m(x, y, *BERTH) for x, y in zip(la, lo)])
    close = d < 150
    passes = int(((~close[:-1]) & close[1:]).sum()) + int(close[0])
    ok = abs(a - ts("2027-09-09T04:58Z")) <= 90 and abs(b - ts("2027-09-09T05:17Z")) <= 90 and abs(rcs - 0.014) < 0.003 and abs(alt - 411 * 0.3048) < 12 and abs(sp - 10.8) < 1.0 and passes >= 2 \
        and all(r["authorization_id"] == "" for r in tr)
    return ok, f"R-22 raw track {iso(int(a))[11:19]}Z-{iso(int(b))[11:19]}Z, RCS {rcs:.3f} m2, {alt / 0.3048:.0f} ft, {sp:.1f} m/s, {passes} passes over the Rendal berth, no authorisation"


def p_1905():
    q5 = port_track("2027-09-11", "04:45", "05:08")
    q4 = port_track("2027-09-09", "04:58", "05:17")
    if not q5 or not q4:
        return False, "port tracks missing on R-22"
    rcs, alt, sp, a, b, la, lo, tr = q5
    la4, lo4 = q4[5], q4[6]
    dmin = np.array([np.min(np.hypot((la4 - x) * M_LAT, (lo4 - y) * 98500.0)) for x, y in zip(la, lo)])
    frac = float((dmin <= 80).mean())
    ok = abs(a - ts("2027-09-11T04:45Z")) <= 90 and abs(b - ts("2027-09-11T05:08Z")) <= 90 and abs(rcs - 0.015) < 0.003 and abs(alt - 491 * 0.3048) < 12 and abs(sp - 11.1) < 1.0 and frac > 0.95
    return ok, f"R-22 raw track {iso(int(a))[11:19]}Z-{iso(int(b))[11:19]}Z, RCS {rcs:.3f} m2, {alt / 0.3048:.0f} ft, {sp:.1f} m/s; {frac:.0%} of plots within 80 m of the 9 September track"


def p_0318():
    t0, t1 = ts("2027-09-15T05:00Z"), ts("2027-09-25T12:00Z")      # the ten nights, D+1 to D+10 (local), to the morning after
    st = [r for r in status_rows() if r["sensor_id"] in ("NASCC-PS-01", "NASCC-PS-02", "NASCC-PS-03", "NASCC-PS-04") and t0 <= r["_t"] <= t1]
    offline = len(st) > 500 and all(r["status"] == "offline" for r in st)
    radar = [r for r in detections() if r["sensor_id"].startswith("NASCC-PS-0") and r["detection_type"] == "radar_plot" and t0 <= r["_t"] <= t1]
    rf = [r for r in detections() if r["sensor_id"].startswith("NASCC") and r["detection_type"] == "rf_contact" and t0 <= r["_t"] <= t1]
    nights, times = set(), []
    for r in table("sighting_reports.csv"):
        t = ts(r["time_utc"])
        night = local_dt(t).hour >= 19 or local_dt(t).hour < 7
        if t0 <= t <= t1 and night and not r["disposition"].startswith("resolved"):
            if dist_m(float(r["observer_latitude"]), float(r["observer_longitude"]), *NGP) < 9000:
                nights.add(day_of(t - 6 * 3600))
                times.append(t)
    auth = 0
    for a in table("laanc_authorizations.csv"):
        s, e = ts(a["start_utc"]), ts(a["end_utc"])
        if e < t0 or s > t1 or dist_m(float(a["center_latitude"]), float(a["center_longitude"]), *NGP) > 8000:
            continue
        if any(s - 3600 <= t <= e + 3600 for t in times):       # an authorised flight near the base around a sighting
            auth += 1
    portable_only = all(r["sensor_id"] == "NASCC-PS-05" for r in rf)   # bearing-only hits from the portable detector set up on 21 September; no tracks
    ok = offline and not radar and len(nights) == 6 and auth == 0 and portable_only and len(rf) <= 20
    return ok, f"air-station perimeter sensors offline throughout; {len(radar)} radar plots and {len(rf)} brief RF contacts; unexplained night sighting reports near the base on {len(nights)} nights (D+{sorted(nights)}); {auth} authorised flights near the base within an hour of any of them"


def intersect(p1, b1, p2, b2):
    """Intersection of two bearing lines (lat, lon, bearing true) on a local plane."""
    x1, y1 = (p1[1] + 97.4) * 98500.0, (p1[0] - 27.75) * M_LAT
    x2, y2 = (p2[1] + 97.4) * 98500.0, (p2[0] - 27.75) * M_LAT
    d1 = (math.sin(math.radians(b1)), math.cos(math.radians(b1)))
    d2 = (math.sin(math.radians(b2)), math.cos(math.radians(b2)))
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    s = ((x2 - x1) * d2[1] - (y2 - y1) * d2[0]) / den
    x, y = x1 + d1[0] * s, y1 + d1[1] * s
    return (27.75 + y / M_LAT, -97.4 + x / 98500.0)


def p_1906():
    c = [r for r in esm_contact() if abs(float(r["rf_center_mhz"]) - 902.4) < 0.05]
    tr = longest("USCG-RDR-R18", ts("2027-09-06T04:00Z"), ts("2027-09-06T05:00Z"))
    if not c or not tr:
        return False, "bearing or track missing"
    n = max(8, int(150 / 4))                                   # first two and a half minutes of the track: the inbound leg
    la = np.array([float(r["latitude"]) for r in tr[:n]]); lo = np.array([float(r["longitude"]) for r in tr[:n]])
    x = (lo + 97.4) * 98500.0; y = (la - 27.75) * M_LAT
    A = np.vstack([x - x.mean(), y - y.mean()]).T
    _, _, vt = np.linalg.svd(A, full_matrices=False)
    dx, dy = vt[0]
    if dx * (x[-1] - x[0]) + dy * (y[-1] - y[0]) < 0:
        dx, dy = -dx, -dy
    back = (math.degrees(math.atan2(-dx, -dy)) + 360) % 360     # where the track came from
    p = intersect((float(c[0]["latitude"]), float(c[0]["longitude"])), float(c[0]["bearing_deg_true"]), (float(la.mean()), float(lo.mean())), back)
    if not p:
        return False, "lines are parallel"
    err = dist_m(p[0], p[1], *MARINA)
    return err < 450, f"the CAMCC-04 bearing ({c[0]['bearing_deg_true']} true) and the back-projected R-18 inbound track ({back:.1f} true) cross {err:.0f} m from Ingleside Marina Berth 7"


def p_1908():
    t0, t1 = ts("2027-10-16T05:00Z"), ts("2027-10-25T05:00Z")
    first = {}
    for r in status_rows():
        if r["sensor_id"] not in first or r["_t"] < first[r["sensor_id"]]:
            first[r["sensor_id"]] = r["_t"]
    new = sorted(s for s, t in first.items() if t0 <= t <= t1)
    sites = {s["sensor_id"]: s for s in table("sensor_sites.csv")}
    port = sum(1 for s in new if "Port" in sites[s]["name"] or "Bridge" in sites[s]["name"])
    util = sum(1 for s in new if "CBPWA" in sites[s]["name"])
    return len(new) >= 5 and port >= 3 and util >= 1, f"{len(new)} new fixed sensors start reporting between 16 and 23 October ({port} at port sites, {util} at utility sites); none reported before"


# ============================================================================ drone telemetry
DV = os.path.join(ROOT, "05_other_sources", "drone_video")


@lru_cache(maxsize=None)
def flights():
    """Per-flight summary from the telemetry on disk: {flight_id: dict(op, mission, t0, t1, lat[], lon[], t[])}, subsampled every 5 s."""
    out = {}
    for fp in sorted(glob.glob(os.path.join(DV, "drone_telemetry_*.csv"))):
        with open(fp, encoding="utf-8") as fh:
            rd = csv.reader(fh)
            h = next(rd)
            ix = {c: i for i, c in enumerate(h)}
            for r in rd:
                f = out.get(r[0])
                if f is None:
                    f = out[r[0]] = {"op": r[ix["operator_id"]], "mission": r[ix["mission_name"]], "t": [], "lat": [], "lon": [], "n": 0, "model": r[ix["drone_model"]]}
                f["n"] += 1
                if f["n"] % 5 == 1:
                    f["t"].append(ts(r[ix["timestamp_utc"]])); f["lat"].append(float(r[ix["latitude"]])); f["lon"].append(float(r[ix["longitude"]]))
    for f in out.values():
        f["t"] = np.array(f["t"]); f["lat"] = np.array(f["lat"]); f["lon"] = np.array(f["lon"])
        f["km"] = float(np.hypot(np.diff(f["lat"]) * M_LAT, np.diff(f["lon"]) * 98500.0).sum()) / 1000.0
    return out


def near_flights(lat, lon, radius, t0, t1, ops=None):
    res = []
    for fid, f in flights().items():
        if f["t"][-1] < t0 or f["t"][0] > t1 or (ops and f["op"] not in ops):
            continue
        d = np.hypot((f["lat"] - lat) * M_LAT, (f["lon"] - lon) * 98500.0)
        m = (d < radius) & (f["t"] >= t0) & (f["t"] <= t1)
        if m.any():
            res.append((fid, f, f["t"][m][0], f["t"][m][-1]))
    return res


def p_bridges():
    hb = INFRA["FAC-INF-01A"]; cw = INFRA["FAC-INF-01B"]
    days = {}
    for d in (1, 3):
        t0, t1 = local_ts(d, "00:00"), local_ts(d + 1, "00:00")
        a = near_flights(hb["latitude"], hb["longitude"], 700, t0, t1, {"DRN-OP-002"})
        b = near_flights(cw["latitude"], cw["longitude"], 1500, t0, t1, {"DRN-OP-002"})
        days[d] = (len(a), len(b))
    ok = all(v[0] >= 1 and v[1] >= 1 for v in days.values())
    return ok, f"TxDOT inspection flights over the Harbor Bridge and the Nueces Bay Causeway: D+1 {days[1]}, D+3 {days[3]} (bridge, causeway)"


def p_oil_shore():
    t0, t1 = ts("2027-09-15T05:00Z"), ts("2027-09-17T05:00Z")
    nb = near_flights(27.832, -97.383, 1500, t0, t1, {"DRN-OP-010", "DRN-OP-011"})
    ny = near_flights(27.8405, -97.4105, 1800, t0, t1, {"DRN-OP-010", "DRN-OP-011"})
    days = {day_of(q[2]) for q in nb + ny}
    return days >= {1, 2} and nb and ny, f"{len(nb)} survey flights along North Beach and {len(ny)} along the Nueces Bay shore on D+{sorted(days)} (NOAA and Coast Guard aircraft)"


def p_sar_uas():
    t0, t1 = ts("2027-09-15T05:00Z"), ts("2027-09-16T05:00Z")
    fl = [f for f in flights().values() if f["op"] == "DRN-OP-005" and t0 <= f["t"][0] <= t1]
    th = [f for f in fl if "TIR" in f["mission"]]
    return len(th) >= 4, f"{len(th)} thermal-imaging flights by the search contractor on D+1 over {sorted({f['mission'].split('-SAR-')[1].rsplit('-', 1)[0] for f in th})}"


def p_depot():
    t0, t1 = local_ts(2, "00:00"), local_ts(3, "00:00")
    fl = near_flights(27.69948, -97.27681, 500, t0, t1)
    return len(fl) >= 1, f"{len(fl)} survey flight over the Army depot hangars on D+2 ({fl[0][1]['mission']}, {iso(int(fl[0][2]))[11:16]}Z-{iso(int(fl[0][3]))[11:16]}Z)" if fl else "no flight over the depot on D+2"


def p_grid():
    t0, t1 = ts("2027-09-17T12:00Z"), ts("2027-09-17T14:00Z")
    fl = {f["mission"]: f for f in flights().values() if f["mission"].startswith("FEMA-UAV-0917-GRID")}
    names = sorted(fl)
    km = sum(f["km"] for f in fl.values())
    inside = all(t0 <= f["t"][0] and f["t"][-1] <= t1 + 300 for f in fl.values())
    ok = names == ["FEMA-UAV-0917-GRID%02d" % i for i in range(1, 9)] and abs(km - 1440) / 1440 < 0.03 and inside
    return ok, f"{len(names)} swarm flights {names[0] if names else ''} to {names[-1] if names else ''}, {km:.0f} km of track between {iso(int(min(f['t'][0] for f in fl.values())))[11:16]}Z and {iso(int(max(f['t'][-1] for f in fl.values())))[11:16]}Z" if fl else "no grid flights"


def p_utility_passes():
    t0, t1 = ts("2027-09-22T09:30Z"), ts("2027-09-22T13:00Z")
    res, ok = [], True
    for aid in ("GW-FAC-SUB-01", "GW-FAC-SUB-02", "GW-FAC-SUB-03", "GW-FAC-SUB-04", "GW-FAC-SUB-05", "GW-FAC-UTL-01"):
        a = INFRA[aid]
        want = "FEMA-UAV-0922-UTL-0%s" % ("6" if aid.endswith("UTL-01") else aid[-1])
        fl = [q for q in near_flights(a["latitude"], a["longitude"], 1000, t0, t1, {"DRN-OP-001"}) if q[1]["mission"] == want]
        if not fl:
            ok = False; res.append(aid + ": none"); continue
        res.append(f"{aid.split('-')[-2] + '-' + aid.split('-')[-1]} {iso(int(fl[0][2]))[11:16]}-{iso(int(fl[0][3]))[11:16]}Z")
        if aid == "GW-FAC-SUB-02":
            ok = ok and abs(fl[0][2] - ts("2027-09-22T10:34Z")) <= 120 and abs(fl[0][3] - ts("2027-09-22T10:51Z")) <= 120
    return ok, "survey passes over the five substations and the water plant on D+8: " + ", ".join(res)


def p_thermal():
    lp = os.path.join(DV, "logs", "flight_log.csv")
    rp = os.path.join(DV, "logs", "thermal_survey_readings.csv")
    if not (os.path.exists(lp) and os.path.exists(rp)):
        return False, "flight log or thermal readings missing"
    log = [r for r in csv.DictReader(open(lp, encoding="utf-8")) if r["flight_id"] == "CBAS-TIR-0925"]
    rd = {(r["asset_id"], r["component"].split()[-1]): float(r["surface_temp_c"]) for r in csv.DictReader(open(rp, encoding="utf-8"))}
    if not log:
        return False, "CBAS-TIR-0925 not in the flight log"
    l = log[0]
    dur = int(l["duration_s"])
    a = rows("CBAS208", ts("2027-09-25T09:00Z"), ts("2027-09-25T12:00Z"))
    air = a[a[:, 4] == 0]
    alt_ok = len(air) and abs(np.median(air[:, 3][air[:, 3] > 400]) - 610) < 60
    ok = abs(dur - 134 * 60) <= 240 and "SAFIRE 380" in l["sensor"] and "7.5-13.5" in l["spectral_band"] and float(l["ground_resolution_m"]) == 0.4 and alt_ok \
        and rd.get(("GW-FAC-SUB-02", "B2-A")) == 24.3 and rd.get(("GW-FAC-SUB-02", "B2-C")) == 24.1 and rd.get(("GW-FAC-SUB-03", "B3-B")) == 24.0 \
        and abs(air[0][0] - ts("2027-09-25T09:15Z")) < 600
    return ok, f"CBAS-TIR-0925 logged {dur // 3600} h {dur % 3600 // 60} min, {l['sensor']}, {l['spectral_band']}, {l['ground_resolution_m']} m; aircraft in ADS-B at about 2,000 ft; readings B2-A 24.3, B2-C 24.1, B3-B 24.0 C"


def p_debris():
    t0, t1 = ts("2027-09-28T05:00Z"), ts("2027-11-24T06:00Z")
    fl = [f for f in flights().values() if "DEBRIS" in f["mission"] and t0 <= f["t"][0] <= t1]
    sites = {f["mission"].split("-VOLUME")[0] for f in fl}
    weeks = {int((f["t"][0] - t0) // (7 * 86400)) for f in fl}
    return len(fl) >= 12 and len(sites) >= 3 and len(weeks) >= 6, f"{len(fl)} pile-volume survey flights at {len(sites)} debris staging sites in {len(weeks)} different weeks"


def p_cleanup():
    t0, t1 = ts("2027-10-14T05:00Z"), ts("2027-10-29T05:00Z")
    fl = [f for f in flights().values() if t0 <= f["t"][0] <= t1 and ("CLEANUP-SURVEY" in f["mission"])]
    return len(fl) >= 4, f"{len(fl)} shoreline cleanup survey flights between 14 and 28 October ({sorted({f['mission'] for f in fl})[:3]})"


# ============================================================================ satellite
SAT = os.path.join(ROOT, "05_other_sources", "satellite")


@lru_cache(maxsize=None)
def scenes():
    out = []
    for fp in sorted(glob.glob(os.path.join(SAT, "*.json"))):
        d = json.load(open(fp, encoding="utf-8"))
        if d.get("type") == "Feature":
            d["_t"] = ts(d["properties"]["datetime"])
            out.append(d)
    return sorted(out, key=lambda d: d["_t"])


def sc(t0, t1, pred=lambda d: True):
    return [d for d in scenes() if t0 <= d["_t"] <= t1 and pred(d)]


def is_sar(d):
    return "sar:frequency_band" in d["properties"]


def covers(d, lat, lon):
    w, s, e, n = d["bbox"]
    return w <= lon <= e and s <= lat <= n


@lru_cache(maxsize=None)
def ais_picture_fn():
    sys.path.insert(0, HERE)
    import gen_satellite
    return gen_satellite.Ais()


def p_s0104():
    ss = sc(ts("2027-08-15T05:00Z"), ts("2027-09-12T05:00Z"), lambda d: covers(d, 27.84, -96.92) and "detections" in d["properties"] and d["properties"]["detections"].get("vessels"))
    if len(ss) < 5:
        return False, f"only {len(ss)} pre-storm scenes carry vessel counts"
    ais = ais_picture_fn()
    G = geo_handle()
    worst, n = 0, 0
    for d in ss:
        p = ais.picture(d["_t"], G)
        if p is None:
            continue
        n += 1
        worst = max(worst, abs(p["offshore_anchorage"] - d["properties"]["detections"]["vessels"]["offshore_anchorage"]))
    if n == 0:
        return False, "no AIS on disk for the pre-storm scene times"
    return worst <= 1, f"{len(ss)} pre-storm scenes carry hull counts for the offshore anchorage; against the AIS on disk the largest difference is {worst} (re-run gen_satellite.py after AIS changes)"


def p_s0207():
    ss = sc(ts("2027-09-12T05:00Z"), ts("2027-09-13T05:00Z"), lambda d: is_sar(d) and covers(d, 27.84, -96.92))
    ok = any(d["properties"].get("detections", {}).get("vessels", {}).get("offshore_anchorage") == 14 for d in ss)
    return ok, f"radar scene {ss[0]['id'] if ss else ''} at {ss[0]['properties']['datetime'] if ss else ''}: 14 hulls queued at the offshore anchorage"


def p_s0208():
    ss = sc(ts("2027-09-12T05:00Z"), ts("2027-09-13T05:00Z"), lambda d: is_sar(d) and "reference" in d["properties"]["title"].lower())
    pts = {"Nueces": (27.80, -97.40), "San Patricio": (28.0, -97.5), "Aransas": (28.1, -97.0), "Kleberg": (27.45, -97.8)}
    cov = [k for k, (la, lo) in pts.items() if any(covers(d, la, lo) for d in ss)]
    return len(ss) >= 4 and len(cov) == 4, f"{len(ss)} pre-storm radar reference scenes covering {', '.join(cov)} counties"


def p_s1101():
    ss = sc(ts("2027-09-12T14:00Z"), ts("2027-09-12T16:00Z"))
    got = {}
    for d in ss:
        for o in d["properties"].get("observations", []):
            if o["state"] == "closed":
                got[o["asset_id"]] = d["properties"]["datetime"]
    ok = got.get("GW-FAC-SUB-02", "")[11:16] == "14:17" and got.get("GW-FAC-SUB-03", "")[11:16] == "14:31"
    return ok, f"baseline images of utility yards: feeder breakers closed at SUB-02 ({got.get('GW-FAC-SUB-02', '?')[11:16]}Z) and SUB-03 ({got.get('GW-FAC-SUB-03', '?')[11:16]}Z); {len(got)} yards imaged"


def p_s0301():
    ss = sc(ts("2027-09-14T05:00Z"), ts("2027-09-15T05:00Z"), lambda d: is_sar(d) and covers(d, 27.80, -97.30))
    return len(ss) >= 2, f"{len(ss)} radar passes over the bays on landfall day ({', '.join(d['properties']['datetime'][11:16] + 'Z' for d in ss)})"


def p_s0314():
    ss = sc(ts("2027-09-14T05:00Z"), ts("2027-09-17T05:00Z"))
    oil = [d for d in ss if d["properties"].get("detections", {}).get("oil_on_water", {}).get("present")]
    a85 = [d for d in oil if d["properties"]["detections"]["oil_on_water"].get("area_km2") == 85]
    kinds = {"radar" if is_sar(d) else "optical" for d in oil}
    ok = len(oil) >= 3 and a85 and day_of(a85[0]["_t"]) == 2 and kinds == {"radar", "optical"}
    return ok, f"{len(oil)} radar and optical scenes show the slick spreading; {a85[0]['id'] if a85 else '?'} on D+2 measures about 85 square km"


def p_s1206():
    d0 = sc(ts("2027-09-14T08:25Z"), ts("2027-09-14T08:35Z"), is_sar)
    d2 = sc(ts("2027-09-16T05:00Z"), ts("2027-09-17T05:00Z"), lambda d: not is_sar(d))
    a = d0 and d0[0]["properties"]["detections"]["oil_on_water"]["present"] and "Inner Harbor" in d0[0]["properties"]["detections"]["oil_on_water"]["where"]
    b = any(d["properties"].get("detections", {}).get("oil_on_water", {}).get("area_km2") == 85 and "North Beach" in d["properties"]["description"] for d in d2)
    return bool(a and b), "radar pass at 08:30Z on D0 shows oil on water in the Inner Harbor around the berth; optical scene on D+2 shows about 85 square km of sheen and oil on North Beach"


def p_s1102():
    d0 = sc(ts("2027-09-14T08:30Z"), ts("2027-09-14T10:30Z"), is_sar)
    if not d0:
        return False, "no radar pass at 08:30Z"
    p = d0[0]["properties"]
    v = p["detections"]["vessels"]
    ok = p["gsd"] == 5 and v.get("main_turning_basin_crude_berth") == 2 and v.get("ship_channel_under_way") == 0 and p["detections"]["inundation_depth_m"] == [2.1, 3.4] \
        and p["detections"]["oil_on_water"]["present"] and covers(d0[0], 27.81, -97.40)
    return ok, f"{d0[0]['id']}: 5 m radar, two large hulls at the Inner Harbor berth, none under way, inundation 2.1 to 3.4 m, oil-on-water signature near the berth"


def p_s0305():
    ss = sc(ts("2027-09-15T05:00Z"), ts("2027-09-16T05:00Z"), is_sar)
    ok = any(d["properties"].get("detections", {}).get("flood_extent_km2") == 112 for d in ss)
    return ok, f"radar flood-extent scene {ss[0]['id'] if ss else '?'}: about 112 square km inundated across three counties"


def p_s0505():
    ss = sc(ts("2027-09-28T05:00Z"), ts("2027-11-24T06:00Z"), lambda d: "Debris staging site" in d["properties"]["title"] and not is_sar(d))
    dates = {d["properties"]["datetime"][:10] for d in ss}
    return len(ss) >= 10 and len(dates) >= 4, f"{len(ss)} optical scenes of debris staging sites on {len(dates)} dates"


def p_s0411():
    ss = sc(ts("2027-10-15T04:20Z"), ts("2027-10-15T04:25Z"), is_sar)
    ok = bool(ss) and any("2 nautical miles off the entrance channel" in u["description"] and u["ais_match"] is False for u in ss[0]["properties"]["detections"]["vessels"].get("uncorrelated", []))
    return ok, f"radar pass {ss[0]['properties']['datetime'][11:16] if ss else '?'}Z: one hull about 2 nautical miles off the entrance channel that no AIS message matches"


def p_s0403():
    ss = sc(ts("2027-10-15T09:30Z"), ts("2027-10-15T09:35Z"), is_sar)
    ok = bool(ss) and "side by side" in ss[0]["properties"]["description"] and any(u["ais_match"] is False for u in ss[0]["properties"]["detections"]["vessels"].get("uncorrelated", []))
    return ok, f"radar scene {ss[0]['properties']['datetime'][11:16] if ss else '?'}Z: two hulls side by side at the anchorage, one with no AIS match"


def p_s1108():
    ss = sc(ts("2027-10-29T17:00Z"), ts("2027-10-29T19:00Z"), lambda d: d["properties"].get("archive", {}).get("receipt_id") == "NGA-2027-10-29-FEMA-CC")
    ok = bool(ss) and ss[0]["properties"]["archive"]["native_gsd_m"] == 0.03 and "FEMA-TIR-0925-UTL" in ss[0]["properties"]["archive"]["referenced_reports"]
    return ok, "archive receipt NGA-2027-10-29-FEMA-CC for the 3 cm archive, with a chain-of-custody note referring to FEMA-TIR-0925-UTL"


# ============================================================================ stream descriptions
def _adsb_range():
    lo, hi = 1e18, 0
    for a in adsb().values():
        lo = min(lo, a[0, 0]); hi = max(hi, a[-1, 0])
    return int(lo), int(hi)


def _header(fp):
    with open(fp, encoding="utf-8") as fh:
        return next(csv.reader(fh))


def _dd_sensor_registry():
    r = reg("sensor_registry")
    ids = {s["sensor_id"] for k, v in r.items() if isinstance(v, list) for s in v if isinstance(s, dict) and s.get("sensor_id")}
    extra = os.path.join(ROOT, "06_data_streams", "_internal", "registry_additions_aviation.json")
    if "drone_detection_sensors" not in r and os.path.exists(extra):       # proposed additions, until the registry pass merges them
        ids |= {s["sensor_id"] for s in json.load(open(extra, encoding="utf-8"))["drone_detection_sensors"]}
    ids |= {o["operator_id"] for o in reg("drone_operators")["authorized_operators"]}
    return ids


def _dd_ids():
    ids = {r["sensor_id"] for r in status_rows()} | {r["sensor_id"] for r in detections()} | {a["operator_id"] for a in table("laanc_authorizations.csv")}
    return ids


def _dd_columns():
    cols = set()
    for fp in glob.glob(os.path.join(DD, "*.csv")):
        cols |= set(_header(fp))
    return sorted(cols)


def _dd_text():
    for r in table("sighting_reports.csv"):
        yield r["description"] + " " + r["disposition"]
    for s in table("sensor_sites.csv"):
        yield s["name"]


def _dd_range():
    t = [r["_t"] for r in status_rows()]
    return int(min(t)), int(max(t))


def _dv_range():
    lo = min(f["t"][0] for f in flights().values()); hi = max(f["t"][-1] for f in flights().values())
    return int(lo), int(hi)


def _dv_ids():
    ids = {f["op"] for f in flights().values()}
    lp = os.path.join(DV, "logs", "flight_log.csv")
    if os.path.exists(lp):
        ids |= {r["operator_id"] for r in csv.DictReader(open(lp, encoding="utf-8"))}
    return ids


def _dv_registry():
    return {o["operator_id"] for o in reg("drone_operators")["authorized_operators"]} | {a["aircraft_id"] for a in reg("aircraft_registry")["aircraft"]}


def _dv_text():
    for f in flights().values():
        yield f["mission"]


def _sat_range():
    return int(scenes()[0]["_t"]), int(scenes()[-1]["_t"])


def _sat_text():
    for d in scenes():
        yield d["properties"]["title"] + " " + d["properties"]["description"]


STREAMS = {
    "adsb": {"time_range": _adsb_range, "ids": lambda: set(adsb().keys()), "registry_ids": lambda: {a["icao24"] for a in AC.values()},
             "public_voice": False, "columns": lambda: _header(sorted(glob.glob(os.path.join(ROOT, "05_other_sources", "adsb", "*.csv")))[0])},
    "drone_detections": {"time_range": _dd_range, "ids": _dd_ids, "registry_ids": _dd_sensor_registry, "public_voice": True, "text": _dd_text, "columns": _dd_columns},
    "drone_telemetry": {"time_range": _dv_range, "ids": _dv_ids, "registry_ids": _dv_registry, "public_voice": False, "text": _dv_text,
                        "columns": lambda: _header(sorted(glob.glob(os.path.join(DV, "*.csv")))[0])},
    "satellite": {"time_range": _sat_range, "public_voice": True, "text": _sat_text},
}

PROBES = {
    ("EVT-0205", "adsb"): p_navy_evacuation,
    ("EVT-1702", "adsb"): p_first_rescue,
    ("EVT-1102", "adsb"): p_noaa42,
    ("EVT-1103", "adsb"): p_arng,
    ("EVT-1703", "adsb"): p_rescue_d1,
    ("EVT-2006", "adsb"): p_sheen_survey,
    ("EVT-0405", "adsb"): p_relief,
    ("EVT-0412", "adsb"): p_gps,
    ("EVT-1901", "drone_detections"): p_1901,
    ("EVT-1902", "drone_detections"): p_1902,
    ("EVT-1903", "drone_detections"): p_1903,
    ("EVT-1904", "drone_detections"): p_1904,
    ("EVT-1905", "drone_detections"): p_1905,
    ("EVT-0318", "drone_detections"): p_0318,
    ("EVT-1906", "drone_detections"): p_1906,
    ("EVT-1908", "drone_detections"): p_1908,
    ("EVT-0304", "drone_telemetry"): p_bridges,
    ("EVT-0314", "drone_telemetry"): p_oil_shore,
    ("EVT-1703", "drone_telemetry"): p_sar_uas,
    ("EVT-0307", "drone_telemetry"): p_depot,
    ("EVT-1104", "drone_telemetry"): p_grid,
    ("EVT-1105", "drone_telemetry"): p_utility_passes,
    ("EVT-1106", "drone_telemetry"): p_thermal,
    ("EVT-0505", "drone_telemetry"): p_debris,
    ("EVT-0410", "drone_telemetry"): p_cleanup,
    ("EVT-0104", "satellite"): p_s0104,
    ("EVT-0207", "satellite"): p_s0207,
    ("EVT-0208", "satellite"): p_s0208,
    ("EVT-1101", "satellite"): p_s1101,
    ("EVT-0301", "satellite"): p_s0301,
    ("EVT-0314", "satellite"): p_s0314,
    ("EVT-1206", "satellite"): p_s1206,
    ("EVT-1102", "satellite"): p_s1102,
    ("EVT-0305", "satellite"): p_s0305,
    ("EVT-0505", "satellite"): p_s0505,
    ("EVT-0411", "satellite"): p_s0411,
    ("EVT-0403", "satellite"): p_s0403,
    ("EVT-1108", "satellite"): p_s1108,
}

if __name__ == "__main__":
    for (ev, st), fn in PROBES.items():
        try:
            ok, det = fn()
        except Exception as e:      # noqa: BLE001
            ok, det = False, "probe raised " + repr(e)
        print(("ok  " if ok else "FAIL"), ev, st, "-", det)
