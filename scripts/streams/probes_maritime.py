"""Stream descriptions and probes for the maritime family:
ais, port_surveillance, port_conditions, port_arrivals, cargo_manifests. Used by scripts/check_streams.py.

Every probe reads the files on disk and returns (ok, detail). Nothing here looks at the generator."""
import calendar
import csv
import glob
import math
import os
import sys
from collections import defaultdict
from functools import lru_cache

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from common import ROOT, ts, iso, reg   # noqa: E402

AIS_GLOB = os.path.join(ROOT, "05_other_sources", "ais", "ais_*.csv")
SAIS_GLOB = os.path.join(ROOT, "05_other_sources", "ais", "satellite", "sais_*.csv")
SURV = os.path.join(ROOT, "05_other_sources", "port_surveillance")
SUP = os.path.join(ROOT, "05_other_sources", "supply")
H = 3600.0
M_LAT = 110950.0

VES = reg("vessels")["vessels"]
BY_ID = {v["vessel_id"]: v for v in VES}
BY_MMSI = {str(v["mmsi"]): v for v in VES if v.get("mmsi")}
TR = reg("terminal_registry")
BERTH = {b["berth_id"]: (b["latitude"], b["longitude"]) for b in TR["berths"]}
SLIP = {s["slip_id"]: (s["latitude"], s["longitude"]) for s in TR["slips"]}
ANCH = np.array([(a["latitude"], a["longitude"]) for a in TR["anchorage_positions"]])
SEA_BUOY = (TR["sea_buoy"]["latitude"], TR["sea_buoy"]["longitude"])


def M(vid):
    return str(BY_ID[vid]["mmsi"])


HD, GP, PR = M("VSL-0031"), M("VSL-0012"), M("VSL-0457")
KS, OB, CB, SEALIFT, NARWHAL = M("VSL-0041"), M("VSL-0042"), M("VSL-0077"), M("VSL-0019"), M("VSL-0481")
DEEP = {str(v["mmsi"]) for v in VES if v.get("mmsi") and v.get("deep_draft")}
CLASS = {str(v["mmsi"]): v["class"] for v in VES if v.get("mmsi")}
NAME = {str(v["mmsi"]): v["vessel_name"] for v in VES if v.get("mmsi")}

LON_JETTY = -97.045            # the jetty channel at Port Aransas
LON_BRIDGE = -97.3957          # Harbor Bridge, entrance to the Inner Harbor
LON_RESTRICT = -97.416         # west limit of the Main Turning Basin: the inner-channel restriction line
ZULU, YANKEE = ts("2027-09-13T17:00Z"), ts("2027-09-12T12:00Z")
REOPEN1, BLAST, REOPEN2 = ts("2027-10-14T16:00Z"), ts("2027-10-28T06:10Z"), ts("2027-11-11T14:00Z")
DARK0, DARK1 = ts("2027-10-15T02:00Z"), ts("2027-10-15T16:00Z")


def dist_m(la1, lo1, la2, lo2):
    return np.hypot((np.asarray(la1) - la2) * M_LAT, (np.asarray(lo1) - lo2) * 111320.0 * math.cos(math.radians(27.8)))


def epoch(s):
    """'2027-09-14T06:32:00' or with a trailing Z -> epoch seconds (UTC)."""
    return calendar.timegm((int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19]) if len(s) >= 19 else 0))


def z(t):
    return iso(t)


# ============================================================================ loaders
def _load_ais(pattern):
    """{mmsi: array[t, lat, lon, sog, status, draft, length]} sorted by time, and {mmsi: [(t, destination)]} for non-blank destinations."""
    rows, dests, names = defaultdict(list), defaultdict(list), {}
    for fp in sorted(glob.glob(pattern)):
        with open(fp, encoding="utf-8", newline="") as fh:
            rd = csv.reader(fh)
            h = next(rd)
            ix = {c: i for i, c in enumerate(h)}
            im, it, ila, ilo, isg, ist, idr, iln, ids, inm = (ix[c] for c in ("MMSI", "BaseDateTime", "LAT", "LON", "SOG", "Status", "Draft", "Length", "Destination", "VesselName"))
            for r in rd:
                t = epoch(r[it])
                rows[r[im]].append((t, float(r[ila]), float(r[ilo]), float(r[isg]), float(r[ist]), float(r[idr] or 0), float(r[iln] or 0)))
                if r[ids]:
                    dests[r[im]].append((t, r[ids]))
                names.setdefault(r[im], set()).add(r[inm])
    out = {}
    for k, v in rows.items():
        a = np.array(v)
        out[k] = a[np.argsort(a[:, 0], kind="stable")]
    return out, dests, names


@lru_cache(maxsize=None)
def ais():
    return _load_ais(AIS_GLOB)


@lru_cache(maxsize=None)
def sais():
    return _load_ais(SAIS_GLOB)


def A(mmsi, t0=None, t1=None, feed=ais):
    a = feed()[0].get(mmsi)
    if a is None:
        return np.zeros((0, 7))
    if t0 is not None:
        a = a[(a[:, 0] >= t0) & (a[:, 0] <= t1)]
    return a


def in_anchorage(a):
    """Mask: within 1.2 km of a charted anchorage position."""
    if len(a) == 0:
        return np.zeros(0, bool)
    d = np.hypot((a[:, 1][:, None] - ANCH[:, 0][None, :]) * M_LAT, (a[:, 2][:, None] - ANCH[:, 1][None, :]) * 98500.0)
    return d.min(axis=1) <= 1200.0


def anchored_set(t0, t1):
    """MMSIs with at least one 'at anchor' report inside the anchorage in the window."""
    out = set()
    for m, a in ais()[0].items():
        w = a[(a[:, 0] >= t0) & (a[:, 0] <= t1)]
        if len(w) and ((w[:, 4] == 1) & in_anchorage(w)).any():
            out.add(m)
    return out


def crossings(lon_line, t0, t1, who=None, lat_lo=27.78, lat_hi=27.90):
    """Passages of a meridian by consecutive reports less than 30 minutes apart: [(t, mmsi, 'IN'|'OUT')]."""
    out = []
    for m, a in ais()[0].items():
        if who is not None and m not in who:
            continue
        w = a[(a[:, 0] >= t0 - 1800) & (a[:, 0] <= t1 + 1800)]
        if len(w) < 2:
            continue
        s = w[:, 2] - lon_line
        idx = np.nonzero((s[:-1] * s[1:] < 0) & (np.diff(w[:, 0]) <= 1800) & (w[1:, 1] > lat_lo) & (w[1:, 1] < lat_hi))[0]
        for i in idx:
            t = w[i + 1, 0]
            if t0 <= t <= t1:
                out.append((t, m, "IN" if s[i + 1] < 0 else "OUT"))
    return sorted(out)


def max_gap(a):
    return float(np.diff(a[:, 0]).max()) if len(a) > 1 else float("inf")


@lru_cache(maxsize=None)
def radar():
    """Radar plots as a dict of numpy arrays."""
    cols = defaultdict(list)
    for fp in sorted(glob.glob(os.path.join(SURV, "radar_tracks_*.csv"))):
        with open(fp, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                cols["t"].append(epoch(r["time_utc"])); cols["ne"].append(r["sensor_id"] == "RADAR-BUOY-NE"); cols["track"].append(r["track_id"])
                cols["lat"].append(float(r["latitude"])); cols["lon"].append(float(r["longitude"])); cols["spd"].append(float(r["speed_kn"]))
                cols["len"].append(float(r["est_length_m"])); cols["ship"].append(r["size_class"] == "ship"); cols["corr"].append(r["ais_correlated"] == "Y")
                cols["mmsi"].append(r["correlated_mmsi"]); cols["ingest"].append(epoch(r["ingest_utc"]))
    return {k: np.array(v) for k, v in cols.items()}


def R(t0, t1, **flt):
    d = radar()
    m = (d["t"] >= t0) & (d["t"] <= t1)
    for k, v in flt.items():
        m &= (d[k] == v)
    return {k: v[m] for k, v in d.items()}


@lru_cache(maxsize=None)
def table(name):
    with open(os.path.join(SURV if name in ("camera_events", "vessel_traffic_log", "sensor_status", "sensors") else SUP, name + ".csv"), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def rows_between(name, col, t0, t1):
    return [r for r in table(name) if r[col] and t0 <= epoch(r[col]) <= t1]


def status_at(t):
    """Latest logged status of each sensor at time t."""
    out = {}
    for r in table("sensor_status"):
        if epoch(r["time_utc"]) <= t and r["status"] in ("ONLINE", "OFFLINE", "NO UPLINK"):
            out[r["sensor_id"]] = r["status"]
    return out


def ship_names_in_view(text):
    """'KALVORA STAR (TERM-01-B07); OSTREL BAY (TERM-01-B08)' -> [('KALVORA STAR', 'TERM-01-B07'), ...]"""
    out = []
    for part in text.split(";"):
        part = part.strip()
        if part and part != "none" and "(" in part:
            out.append((part[:part.rfind("(")].strip(), part[part.rfind("(") + 1:].rstrip(")")))
    return out


DEEP_NAMES = {n.upper().split(" ", 1)[1] if n.upper().split(" ", 1)[0] in ("MT", "MV", "FV", "LNG") else n.upper() for m, n in NAME.items() if m in DEEP}


# ============================================================================ AIS probes
def p_0104_ais():
    a = A(HD, ts("2027-08-15T05:00Z"), ts("2027-09-12T05:00Z"))
    if len(a) < 1000:
        return False, f"only {len(a)} reports for {HD} in the window"
    inside = in_anchorage(a).mean()
    anch = (a[:, 4] == 1).mean()
    gap = max_gap(a)
    dest = [d for t, d in ais()[1].get(HD, []) if t <= ts("2027-09-12T05:00Z")]
    under = a[:, 4] == 0
    shifts = int(((~under[:-1]) & under[1:]).sum())
    back = a[-1, 4] == 1
    ok = inside == 1.0 and anch >= 0.97 and set(np.unique(a[:, 4])) <= {0.0, 1.0} and gap <= 480 and not dest and shifts >= 1 and back
    return ok, (f"{len(a)} reports under MMSI {HD}, all inside the anchorage={inside == 1.0}, at anchor {anch:.1%}, {shifts} short shift(s) under way and back at anchor, "
                f"longest gap {gap / 60:.1f} min, destinations entered: {sorted(set(dest)) or 'none'}")


def p_1201_ais():
    a = A(HD, ts("2027-08-31T05:00Z"), ts("2027-09-07T23:00Z"))
    if len(a) < 500:
        return False, f"only {len(a)} reports"
    gap = max_gap(a)
    dest = [d for t, d in ais()[1].get(HD, []) if ts("2027-08-31T05:00Z") <= t <= ts("2027-09-07T23:00Z")]
    all_anchor = bool((a[:, 4] == 1).all())
    both = np.concatenate([A(HD, ts("2027-08-15T00:00Z"), DARK0 - 1), A(HD, ts("2027-08-15T00:00Z"), DARK0 - 1, feed=sais)])
    worst = max_gap(both[np.argsort(both[:, 0])])
    ok = all_anchor and gap <= 480 and not dest and in_anchorage(a).all() and worst <= 4500
    return ok, (f"{len(a)} reports 31 Aug-7 Sep, every one 'at anchor'={all_anchor}, longest gap {gap / 60:.1f} min, no destination={not dest}; "
                f"longest gap anywhere before 15 Oct 02:00Z, shore and satellite feeds together, {worst / 60:.0f} min (at sea, on the satellite feed)")


def p_1202_ais():
    t0, t1 = ts("2027-09-11T04:30Z"), ts("2027-09-11T06:30Z")
    at = anchored_set(t0, t1)
    r = R(t0, t1, ne=True, ship=True)
    if not len(r["t"]):
        return False, "no ship-sized Buoy-NE plots in the window"
    unmatched = int((~r["corr"]).sum())
    worst, no_ais = 0.0, []
    for m in set(r["mmsi"]):
        a = A(m, t0 - 1800, t1 + 1800)
        if not len(a):
            no_ais.append(m)
            continue
        est = r["len"][r["mmsi"] == m]
        worst = max(worst, float(np.abs(est / a[0, 6] - 1).max()))
    base = R(ts("2027-09-07T05:00Z"), ts("2027-09-14T05:00Z"), ship=True)
    frac = float(base["corr"].mean()) if len(base["t"]) else 0.0
    hd_len = r["len"][r["mmsi"] == HD]
    ok = HD in at and len(at) >= 3 and unmatched == 0 and not no_ais and worst <= 0.10 and frac == 1.0 and len(hd_len) > 0
    return ok, (f"{len(at)} ships at anchor on AIS incl. Halcyon Drift={HD in at}; {len(set(r['mmsi']))} ship-sized radar tracks, unmatched {unmatched}; radar length within "
                f"{worst:.1%} of AIS length; share of ship-sized plots with an AIS match 7-13 Sep {frac:.1%} of {len(base['t'])}")


def p_0207_ais():
    out_d3 = [c for c in crossings(LON_JETTY, ts("2027-09-11T05:00Z"), ts("2027-09-12T05:00Z"), DEEP) if c[2] == "OUT"]
    out_d2 = [c for c in crossings(LON_JETTY, ts("2027-09-12T05:00Z"), ts("2027-09-13T05:00Z"), DEEP) if c[2] == "OUT"]
    inbound_after = [c for c in crossings(LON_JETTY, YANKEE, ts("2027-09-15T05:00Z"), DEEP) if c[2] == "IN"]
    held = anchored_set(ts("2027-09-13T12:00Z"), ZULU)
    after = anchored_set(ts("2027-09-13T23:00Z"), ts("2027-09-15T05:00Z"))
    moving = 0
    for m, a in ais()[0].items():
        w = a[(a[:, 0] >= ZULU + 2 * H) & (a[:, 0] <= ts("2027-09-15T05:00Z"))]
        moving += int(((w[:, 3] > 1.0) & (w[:, 2] < -97.03) & (w[:, 2] > -97.60) & (w[:, 1] > 27.6) & (w[:, 1] < 28.1)).sum())
    put_to_sea = sum(1 for m in held if len(A(m, ZULU, ts("2027-09-14T03:00Z"))) and (A(m, ZULU, ts("2027-09-14T03:00Z"))[:, 3] > 5).any())
    ok = len(out_d3) >= 1 and len(out_d2) >= 1 and not inbound_after and len(held) == 14 and GP in held and HD in held and not after and moving == 0 and put_to_sea == 14
    return ok, (f"deep-draft sailings past the jetties: {len(out_d3)} on 11 Sep, {len(out_d2)} on 12 Sep; inbound after Yankee: {len(inbound_after)}; at anchor before Zulu: {len(held)} "
                f"(Gulf Provider={GP in held}, Halcyon Drift={HD in held}); under way to sea after Zulu: {put_to_sea}; at anchor after 23:00Z: {len(after)}; "
                f"reports under way inside the port from 19:00Z 13 Sep to 05:00Z 15 Sep: {moving}")


def p_0210_ais():
    t1 = ts("2027-09-17T05:00Z")
    det = []
    ok = True
    for m, b in ((KS, "TERM-01-B07"), (OB, "TERM-01-B08")):
        day = A(m, ts("2027-09-11T05:00Z"), t1)
        fast = day[(day[:, 4] == 5) & (dist_m(day[:, 1], day[:, 2], *BERTH[b]) < 150)]
        if len(fast) < 100:
            return False, f"{NAME[m]}: only {len(fast)} moored reports at {b}"
        a = day[day[:, 0] >= fast[0, 0]]
        d = dist_m(a[:, 1], a[:, 2], *BERTH[b]).max()
        good = bool((a[:, 4] == 5).all() and (a[:, 3] <= 0.2).all() and d <= 150 and max_gap(a) <= 4800 and fast[0, 0] <= ts("2027-09-11T18:00Z"))
        ok &= good
        det.append(f"{NAME[m]}: moored at {b} from {z(fast[0, 0])}; {len(a)} reports to 05:00Z 17 Sep, all moored and stopped={good}, within {d:.0f} m of the berth, longest gap {max_gap(a) / 60:.0f} min")
    return ok, "; ".join(det)


def p_1906_ais():
    a = A(NARWHAL)
    s = A(NARWHAL, feed=sais)
    if not len(a):
        return False, "no reports for Narwhal Dream"
    last = max(a[-1, 0], s[-1, 0] if len(s) else 0)
    w = A(NARWHAL, ts("2027-09-03T05:00Z"), ts("2027-09-07T00:15Z"))
    d = dist_m(w[:, 1], w[:, 2], *SLIP["SLIP-ING-07"]).max() if len(w) else 1e9
    first_moored = a[(a[:, 4] == 5) & (dist_m(a[:, 1], a[:, 2], *SLIP["SLIP-ING-07"]) < 80)]
    ok = (iso(last)[:16] == "2027-09-07T00:14" and len(w) > 50 and d < 80 and bool((w[:, 4] == 5).all()) and len(first_moored) > 0
          and first_moored[0, 0] <= ts("2027-09-03T05:00Z"))
    return ok, (f"moored at SLIP-ING-07 (Ingleside marina berth 7) from {z(first_moored[0, 0]) if len(first_moored) else '?'}; {len(w)} reports 3-7 Sep within {d:.0f} m of the slip; "
                f"last report in either feed {z(last)}; reports after that: 0")


def p_0401_ais():
    closed = crossings(LON_JETTY, ZULU, REOPEN1 - 1, DEEP)
    first = crossings(LON_JETTY, REOPEN1, ts("2027-10-15T05:00Z"), DEEP)
    inner = 0
    for m in DEEP:
        w = A(m, REOPEN1, ts("2027-10-15T14:00Z"))
        inner += int(((w[:, 3] > 1.0) & (w[:, 2] < LON_BRIDGE)).sum())
    g = A(GP, ts("2027-10-14T05:00Z"), ts("2027-10-18T05:00Z"))
    at_anchor = g[(g[:, 4] == 1) & in_anchorage(g)]
    moored = g[(g[:, 4] == 5) & (dist_m(g[:, 1], g[:, 2], *BERTH["TERM-07-B02"]) < 150)]
    berthed = z(moored[0, 0]) if len(moored) else None
    ok = (not closed and len(first) >= 1 and inner == 0 and len(at_anchor) > 100 and at_anchor[-1, 0] >= ts("2027-10-17T05:00Z") and len(moored) > 0
          and ts("2027-10-17T05:00Z") <= moored[0, 0] < ts("2027-10-18T05:00Z"))
    return ok, (f"deep-draft passages of the jetties 13 Sep 17:00Z to 14 Oct 16:00Z: {len(closed)}; first after reopening {z(first[0][0]) if first else None} "
                f"({len(first)} by 05:00Z 15 Oct); deep-draft reports under way west of the Harbor Bridge before 14:00Z 15 Oct: {inner}; "
                f"Gulf Provider at anchor until {z(at_anchor[-1, 0]) if len(at_anchor) else None}, moored at TERM-07-B02 from {berthed}")


def p_0410_ais():
    t0, t1 = ts("2027-10-14T05:00Z"), ts("2027-10-28T05:00Z")
    days, boats = set(), set()
    for m, c in CLASS.items():
        if c != "spill_response":
            continue
        w = A(m, t0, t1)
        w = w[(w[:, 3] > 0.5) & (w[:, 2] < -97.03)]
        if len(w):
            boats.add(m)
            days |= set(((w[:, 0] - t0) // 86400).astype(int).tolist())
    west = 0
    for m in DEEP:
        w = A(m, t0, t1)
        west += int(((w[:, 3] > 0.5) & (w[:, 2] < LON_RESTRICT)).sum())
    ok = len(days) >= 12 and len(boats) >= 2 and west == 0
    return ok, f"{len(boats)} response vessels under way inside the port on {len(days)} of 14 days; deep-draft reports under way west of the restriction line ({LON_RESTRICT}): {west}"


def p_1208_ais():
    before = crossings(LON_JETTY, ZULU, REOPEN1 - 1, DEEP)
    c = crossings(LON_JETTY, REOPEN1, ts("2027-10-16T05:00Z"), DEEP)
    ok = not before and len(c) >= 2
    return ok, (f"no deep-draft passage of the jetties for {(REOPEN1 - ZULU) / 86400:.0f} days, then {len(c)} between 16:00Z 14 Oct and 05:00Z 16 Oct; first: "
                + ", ".join(f"{NAME[m]} {d} {z(t)}" for t, m, d in c[:3]))


def p_0402_ais():
    a = A(HD, ts("2027-10-14T16:00Z"), ts("2027-10-16T05:00Z"))
    s = A(HD, ts("2027-10-14T16:00Z"), ts("2027-10-16T05:00Z"), feed=sais)
    inside = a[(a[:, 0] > DARK0 + 600) & (a[:, 0] < DARK1 - 600)]
    before, after = a[a[:, 0] <= DARK0 + 600], a[a[:, 0] >= DARK1 - 600]
    if not len(before) or not len(after):
        return False, "Halcyon Drift has no reports either side of the window"
    gap = after[0, 0] - before[-1, 0]
    sp = A(PR, DARK0, DARK1)
    near = sp[dist_m(sp[:, 1], sp[:, 2], *SEA_BUOY) < 9 * 1852] if len(sp) else sp
    far = A(PR, DARK0, DARK1, feed=sais)
    far_nm = dist_m(far[:, 1], far[:, 2], *SEA_BUOY) / 1852 if len(far) else np.array([0.0])
    outside = A(PR, DARK0 - 10 * 86400, DARK0 - 1)
    outside2 = A(PR, DARK1 + 1, DARK1 + 10 * 86400)
    ok = (len(inside) == 0 and len(s) == 0 and 13.4 * H <= gap <= 14.6 * H and len(near) >= 20 and in_anchorage(near).mean() > 0.5 and len(far) >= 5
          and 520 <= far_nm.min() and far_nm.max() <= 680 and len(outside) == 0 and len(outside2) == 0)
    return ok, (f"Halcyon Drift: last report {z(before[-1, 0])}, next {z(after[0, 0])} ({gap / H:.1f} h silent); MMSI {PR} (Pelican Ridge) in the shore feed "
                f"{len(near)} times {z(near[0, 0]) if len(near) else ''}-{z(near[-1, 0]) if len(near) else ''} at the anchorage, and in the satellite feed {len(far)} times in the same hours "
                f"{far_nm.min():.0f}-{far_nm.max():.0f} nm away; shore-feed reports under that MMSI in the ten days before or after: {len(outside) + len(outside2)}")


def p_0404_ais():
    t0, t1 = ts("2027-10-16T05:00Z"), ts("2027-10-17T05:00Z")
    hits = []
    for m, c in CLASS.items():
        if c != "tug":
            continue
        w = A(m, t0, t1)
        if not len(w):
            continue
        at = w[(dist_m(w[:, 1], w[:, 2], *BERTH["TERM-02-B01"]) < 250) & (w[:, 3] < 0.5)]
        cr = [x for x in crossings(LON_BRIDGE, t0, t1, {m}, 27.80, 27.83) if x[2] == "IN"]
        if len(at) and cr and cr[0][0] < at[0, 0]:
            hits.append((m, cr[0][0], at[0, 0], at[-1, 0]))
    ok = len(hits) >= 1
    return ok, "; ".join(f"tug {NAME[m]} ({m}) inbound under the Harbor Bridge {z(a)}, stopped at TERM-02-B01 (Quellmar barge dock) {z(b)} to {z(c)}" for m, a, b, c in hits) or "no tug reached TERM-02-B01 from the bay on 16 Oct"


def p_0414_ais():
    days, boats = set(), set()
    for m, c in CLASS.items():
        if c not in ("navy", "coast_guard"):
            continue
        w = A(m, BLAST, REOPEN2)
        w = w[(w[:, 2] > -97.06) & (w[:, 2] < -96.93) & (w[:, 1] > 27.76) & (w[:, 1] < 27.86) & (w[:, 3] > 1.0) & (w[:, 3] < 9.0)]
        if len(w) >= 20:
            boats.add(m)
            days |= set(((w[:, 0] - ts("2027-10-28T05:00Z")) // 86400).astype(int).tolist())
    commercial = crossings(LON_JETTY, BLAST + 1800, REOPEN2 - 1, DEEP)
    q0, q1 = anchored_set(ts("2027-10-27T12:00Z"), ts("2027-10-27T18:00Z")), anchored_set(ts("2027-11-10T12:00Z"), ts("2027-11-10T18:00Z"))
    # second find: a Navy craft stopped on one spot in the approach for an hour or more on 5 Nov (local)
    hold = None
    for m, c in CLASS.items():
        if c != "navy":
            continue
        w = A(m, ts("2027-11-05T05:00Z"), ts("2027-11-06T06:00Z"))
        w = w[(w[:, 2] > -97.06) & (w[:, 2] < -96.90) & (w[:, 1] > 27.74) & (w[:, 1] < 27.86)]
        i = 0
        while i < len(w):
            j = i
            while j + 1 < len(w) and w[j + 1, 3] < 0.7 and dist_m(w[j + 1, 1], w[j + 1, 2], w[i, 1], w[i, 2]) < 200 and w[j + 1, 0] - w[j, 0] < 2400:
                j += 1
            if w[i, 3] < 0.7 and w[j, 0] - w[i, 0] >= 3600 and (hold is None or w[j, 0] - w[i, 0] > hold[2] - hold[1]):
                hold = (m, w[i, 0], w[j, 0], w[i, 1], w[i, 2])
            i = j + 1
    first_after = crossings(LON_JETTY, REOPEN2, REOPEN2 + 86400, DEEP)
    ok = len(days) >= 11 and len(boats) >= 3 and not commercial and len(q1) > len(q0) and len(q1) >= 8 and hold is not None and len(first_after) >= 1
    return ok, (f"{len(boats)} Navy and Coast Guard vessels working the entrance at search speed on {len(days)} days; deep-draft passages of the jetties 28 Oct 06:40Z to 11 Nov 14:00Z: "
                f"{len(commercial)}; ships at anchor {len(q0)} on 27 Oct -> {len(q1)} on 10 Nov; "
                + (f"{NAME[hold[0]]} held position {z(hold[1])}-{z(hold[2])} at {hold[3]:.4f},{hold[4]:.4f}" if hold else "no Navy craft held position on 5 Nov")
                + f"; first passage after reopening {z(first_after[0][0]) if first_after else None}")


def p_0413_ais():
    a = A(CB, ts("2027-10-28T05:30Z"), ts("2027-10-28T08:00Z"))
    if len(a) < 10:
        return False, f"only {len(a)} reports for Corrin Bay"
    run = a[(a[:, 0] >= ts("2027-10-28T06:04:30Z")) & (a[:, 0] <= ts("2027-10-28T06:10:15Z"))]
    stopped = a[(a[:, 0] >= ts("2027-10-28T06:09Z")) & (a[:, 3] < 0.5)]
    if not len(stopped) or not len(run):
        return False, "no stop found after 06:09Z"
    t_stop, p = stopped[0, 0], (stopped[0, 1], stopped[0, 2])
    still = a[(a[:, 0] >= t_stop) & (a[:, 0] <= t_stop + 1500)]
    others = set()
    for m, o in ais()[0].items():
        if m == CB:
            continue
        w = o[(o[:, 0] >= t_stop) & (o[:, 0] <= ts("2027-10-28T08:00Z"))]
        if len(w) and (dist_m(w[:, 1], w[:, 2], *p) < 600).any():
            others.add(m)
    later = crossings(LON_JETTY, ts("2027-10-28T08:00Z"), ts("2027-10-29T08:00Z"), DEEP)
    ok = (run[:, 3].min() > 4 and ts("2027-10-28T06:09:30Z") <= t_stop <= ts("2027-10-28T06:11:30Z") and bool((still[:, 3] < 1.0).all()) and -97.06 < p[1] < -97.02
          and len(others) >= 2 and not later)
    return ok, (f"Corrin Bay making {run[:, 3].min():.1f}-{run[:, 3].max():.1f} kn in the jetty channel 06:04-06:10Z, stopped at {z(t_stop)} at {p[0]:.5f},{p[1]:.5f} in the jetty channel and stayed stopped; "
                f"{len(others)} other vessels within 600 m by 08:00Z ({', '.join(sorted(NAME[m] for m in others)[:5])}); deep-draft passages in the next 24 h: {len(later)}")


def p_0409_ais():
    a = A(SEALIFT, ts("2027-10-28T00:00Z"), ts("2027-11-19T00:00Z"))
    if not len(a):
        return False, "no reports for the sealift ship"
    moored = a[(a[:, 4] == 5) & (dist_m(a[:, 1], a[:, 2], *BERTH["TERM-07-B01"]) < 150)]
    out = [c for c in crossings(LON_JETTY, ts("2027-11-12T06:00Z"), ts("2027-11-18T06:00Z"), {SEALIFT}) if c[2] == "OUT"]
    waited = a[(a[:, 4] == 1) & in_anchorage(a)]
    ok = (len(moored) > 50 and ts("2027-11-12T06:00Z") <= moored[0, 0] < ts("2027-11-13T06:00Z") and len(out) == 1 and ts("2027-11-17T06:00Z") <= out[0][0] < ts("2027-11-18T06:00Z")
          and moored[-1, 0] < out[0][0] and len(waited) > 0)
    return ok, (f"{NAME[SEALIFT]}: at anchor offshore {z(waited[0, 0]) if len(waited) else None} to {z(waited[-1, 0]) if len(waited) else None}; moored at TERM-07-B01 "
                f"{z(moored[0, 0]) if len(moored) else None} to {z(moored[-1, 0]) if len(moored) else None}; outbound past the jetties {z(out[0][0]) if out else None}")


# ============================================================================ port surveillance probes
def p_1201_ps():
    t1 = ts("2027-09-07T23:00Z")
    vts = [r for r in table("vessel_traffic_log") if r["mmsi"] == HD or "HALCYON DRIFT" in r["vessel_name"].upper()]
    cam = [r for r in table("camera_events") if r["mmsi"] == HD]
    r = R(ts("2027-08-31T05:00Z"), t1, ne=True, ship=True)
    seen = int((r["mmsi"] == HD).sum())
    ok = not vts and not cam and seen > 100
    return ok, (f"vessel traffic log entries for MMSI {HD} at any time: {len(vts)} (no checkpoint passage, pilot order or tug assignment); radar holds the hull at the anchorage "
                f"({seen} correlated plots 31 Aug-7 Sep)")


def p_1202_ps():
    t0, t1 = ts("2027-09-11T04:30Z"), ts("2027-09-11T06:30Z")
    r = R(t0, t1, ne=True, ship=True)
    m = (np.hypot((r["lat"][:, None] - ANCH[:, 0][None, :]) * M_LAT, (r["lon"][:, None] - ANCH[:, 1][None, :]) * 98500.0).min(axis=1) <= 1300) if len(r["t"]) else np.zeros(0, bool)
    ids = set(r["mmsi"][m])
    st = status_at(t0)
    ok = len(ids) >= 3 and HD in ids and bool(r["corr"].all()) and st.get("RADAR-BUOY-NE") == "ONLINE"
    return ok, f"Buoy-NE online; {len(set(r['track'][m]))} ship-sized tracks at the anchorage in the window, all matched to AIS={bool(r['corr'].all()) if len(r['t']) else None}, Halcyon Drift among them={HD in ids}"


def _anch_ships(t0, t1):
    r = R(t0, t1, ne=True, ship=True)
    if not len(r["t"]):
        return set(), r
    m = np.hypot((r["lat"][:, None] - ANCH[:, 0][None, :]) * M_LAT, (r["lon"][:, None] - ANCH[:, 1][None, :]) * 98500.0).min(axis=1) <= 1300
    return set(r["track"][m & (r["spd"] < 1.0)]), r


def p_1203_ps():
    n0, _ = _anch_ships(ts("2027-09-13T16:00Z"), ts("2027-09-13T17:00Z"))
    n1, _ = _anch_ships(ts("2027-09-13T23:00Z"), ts("2027-09-14T05:00Z"))
    r = R(ts("2027-09-13T17:00Z"), ts("2027-09-13T23:00Z"), ne=True, ship=True)
    unmatched = int((~r["corr"]).sum())
    leaving = len(set(r["track"][r["spd"] > 3]))
    frames = [f for f in rows_between("camera_events", "time_utc", ts("2027-09-13T21:00Z"), ts("2027-09-13T23:00Z")) if f["event_type"] == "FRAME"]
    cam1 = [f for f in frames if f["sensor_id"] == "CAM-01"]
    both = bool(cam1) and all("KALVORA STAR" in f["vessels_in_view"] and "OSTREL BAY" in f["vessels_in_view"] for f in cam1)
    others = sorted({n for f in frames if f["sensor_id"] != "CAM-01" for n, b in ship_names_in_view(f["vessels_in_view"]) if n in DEEP_NAMES})
    cams = {f["sensor_id"] for f in frames}
    ok = len(n0) >= 12 and not n1 and unmatched == 0 and leaving >= 12 and both and not others and len(cams) >= 12
    return ok, (f"Buoy-NE: {len(n0)} ships at anchor in the hour before Zulu, {leaving} tracks under way 17:00-23:00Z, all matched to AIS (unmatched {unmatched}), "
                f"{len(n1)} at anchor after 23:00Z; camera frames 21:00-23:00Z from {len(cams)} cameras: CAM-01 shows Kalvora Star and Ostrel Bay={both}, "
                f"deep-draft vessels at any other berth: {others or 'none'}")


def p_1204_ps():
    cam1 = [r for r in table("camera_events") if r["sensor_id"] == "CAM-01" and epoch(r["time_utc"]) < ts("2027-09-15T00:00Z")]
    last = cam1[-1]
    dark = rows_between("camera_events", "time_utc", ts("2027-09-14T02:30Z"), ts("2027-09-15T14:09Z"))
    st = [r for r in rows_between("sensor_status", "time_utc", ts("2027-09-14T02:15Z"), ts("2027-09-14T06:00Z"))]
    cams_off = {r["sensor_id"] for r in st if r["sensor_id"].startswith("CAM") and r["status"] == "OFFLINE" and r["time_utc"].startswith("2027-09-14T02:30")}
    sw = [r for r in st if r["sensor_id"] == "RADAR-BUOY-SW" and r["status"] != "ONLINE"]
    ne_off = [r for r in st if r["sensor_id"] == "RADAR-BUOY-NE" and r["status"] == "OFFLINE"]
    ne_plots = R(ts("2027-09-14T03:38Z"), ts("2027-09-14T05:10Z"), ne=True)
    ne_after = R(ts("2027-09-14T05:10:01Z"), ts("2027-09-16T19:00Z"), ne=True)
    sw_live = R(ts("2027-09-14T03:38Z"), ts("2027-09-15T11:00Z"), ne=False)
    live_late = bool(len(sw_live["t"])) and bool((sw_live["ingest"] >= ts("2027-09-15T16:00Z")).all())
    ok = (last["time_utc"].startswith("2027-09-14T02:29") and "mooring lines intact" in last["note"] and "no visible sheen" in last["note"]
          and "KALVORA STAR" in last["vessels_in_view"] and "OSTREL BAY" in last["vessels_in_view"] and not dark and len(cams_off) == 14
          and bool(sw) and sw[0]["time_utc"].startswith("2027-09-14T03:38") and bool(ne_off) and ne_off[0]["time_utc"].startswith("2027-09-14T05:10")
          and len(ne_plots["t"]) > 0 and len(ne_after["t"]) == 0 and live_late)
    return ok, (f"last CAM-01 frame {last['time_utc']}: {last['vessels_in_view']}; '{last['note']}'; {len(cams_off)} cameras logged OFFLINE at 02:30Z and no camera row until 15 Sep 14:10Z; "
                f"Buoy-SW '{sw[0]['status'] if sw else None}' at {sw[0]['time_utc'] if sw else None} ({sw[0]['detail'] if sw else ''}), its plots after that reached the archive only from 15 Sep 16:00Z={live_late}; "
                f"Buoy-NE plots until {z(ne_plots['t'].max()) if len(ne_plots['t']) else None}, OFFLINE at {ne_off[0]['time_utc'] if ne_off else None}")


def p_1205_ps():
    rec = [r for r in rows_between("sensor_status", "time_utc", ts("2027-09-15T16:00Z"), ts("2027-09-15T18:00Z")) if "BUOY-SW-REC-20270915" in r["detail"]]
    buf = R(ts("2027-09-14T03:38Z"), ts("2027-09-15T11:00Z"), ne=False)
    moving = int((buf["ship"] & (buf["spd"] > 1.0)).sum()) if len(buf["t"]) else -1
    span = (buf["t"].min(), buf["t"].max()) if len(buf["t"]) else (0, 0)
    gap = float(np.diff(np.unique(buf["t"])).max()) if len(buf["t"]) > 1 else 1e9
    vts = rows_between("vessel_traffic_log", "time_utc", ts("2027-09-13T23:00Z"), ts("2027-09-15T12:00Z"))
    hourly = [r for r in rows_between("sensor_status", "time_utc", ts("2027-09-14T03:38Z"), ts("2027-09-15T11:00Z")) if r["sensor_id"] == "RADAR-BUOY-SW" and r["status"] == "NO UPLINK"]
    after = [r for r in table("camera_events") if epoch(r["time_utc"]) >= ts("2027-09-14T02:30Z")]
    first = after[0] if after else None
    ok = (bool(rec) and len(buf["t"]) > 20 and moving == 0 and span[0] <= ts("2027-09-14T04:15Z") and span[1] >= ts("2027-09-15T10:00Z") and not vts and len(hourly) >= 30
          and first is not None and first["time_utc"].startswith("2027-09-15T14:10") and first["sensor_id"] == "CAM-01" and "KALVORA STAR" in first["vessels_in_view"]
          and "OSTREL BAY" in first["vessels_in_view"] and first["water_surface"] == "heavy sheen" and "boom" in first["note"])
    return ok, (f"{rec[0]['time_utc'] if rec else None} {rec[0]['status'] if rec else ''}: {rec[0]['detail'] if rec else 'no recovery row'}; {len(buf['t'])} buffered Buoy-SW plots "
                f"{z(span[0])} to {z(span[1])} (all small drifting contacts; {len(hourly)} hourly 'recording to onboard buffer' status rows), ship-sized plots under way: {moving}; traffic-log entries 13 Sep 23:00Z to 15 Sep 12:00Z: {len(vts)}; first camera row after the storm "
                f"{first['time_utc'] if first else None} {first['sensor_id'] if first else ''}: {first['vessels_in_view'] if first else ''}, {first['water_surface'] if first else ''}, '{first['note'] if first else ''}'")


def p_1207_ps():
    rec = [r for r in rows_between("sensor_status", "time_utc", ts("2027-09-19T08:00Z"), ts("2027-09-19T10:00Z")) if r["status"] == "ARCHIVE EXPORT"]
    ok = bool(rec) and "2027-09-11" in rec[0]["detail"] and "2027-09-19" in rec[0]["detail"]
    return ok, f"{rec[0]['time_utc']} {rec[0]['sensor_id']} {rec[0]['status']}: {rec[0]['detail']}" if rec else "no archive export row on 19 Sep"


def p_1208_ps():
    st = status_at(ts("2027-10-14T17:00Z"))
    cams = sorted(k for k, v in st.items() if k.startswith("CAM") and v == "ONLINE")
    buoys = [k for k in ("RADAR-BUOY-NE", "RADAR-BUOY-SW") if st.get(k) == "ONLINE"]
    base = R(ts("2027-09-16T19:30Z"), DARK0 - 1, ship=True)
    night = R(DARK0, DARK1, ship=True)
    pre = R(ts("2027-08-15T00:00Z"), ts("2027-09-14T06:00Z"), ship=True)
    f0 = float(base["corr"].mean()) if len(base["t"]) else 0
    f1 = float(night["corr"].mean()) if len(night["t"]) else 1
    fp = float(pre["corr"].mean()) if len(pre["t"]) else 0
    first_un = z(night["t"][~night["corr"]].min()) if len(night["t"]) and (~night["corr"]).any() else None
    ok = len(cams) == 8 and len(buoys) == 2 and f0 == 1.0 and fp == 1.0 and f1 < 1.0
    return ok, (f"14 Oct 17:00Z: {len(cams)} of 14 cameras online ({', '.join(cams)}), {len(buoys)} of 2 radar buoys; ship-sized plots matched to AIS: {fp:.1%} before the storm, "
                f"{f0:.1%} from 16 Sep to 15 Oct 02:00Z ({len(base['t'])} plots), {f1:.1%} from 02:00Z to 16:00Z 15 Oct; first unmatched plot {first_un}")


def _dark_track():
    """Unmatched ship-sized Buoy-NE plots during the AIS silence, and Halcyon Drift's last AIS position before it."""
    a = A(HD, DARK0 - 2 * H, DARK0 + 600)
    last = (a[-1, 1], a[-1, 2]) if len(a) else None
    r = R(DARK0, DARK1, ne=True, ship=True)
    m = ~r["corr"]
    return last, {k: v[m] for k, v in r.items()}


def p_0402_ps():
    last, r = _dark_track()
    if last is None or not len(r["t"]):
        return False, "no unmatched ship-sized contact during the silence"
    d = dist_m(r["lat"], r["lon"], *last)
    at = d < 500
    hours = len(set((r["t"][at] // 3600).astype(int).tolist()))
    before = R(DARK0 - 2 * H, DARK0 - 1, ne=True, ship=True)
    same_track = set(r["track"][at]) & set(before["track"][before["mmsi"] == HD])
    ok = at.sum() >= 100 and hours >= 11 and r["t"][at].min() <= DARK0 + 900 and r["t"][at].max() >= DARK1 - 900 and abs(float(np.median(r["len"][at])) / BY_ID["VSL-0031"]["length_m"] - 1) < 0.1
    return ok, (f"unmatched ship-sized contact within 500 m of Halcyon Drift's last AIS position ({last[0]:.5f},{last[1]:.5f}): {int(at.sum())} plots in {hours} of 14 hours, "
                f"{z(r['t'][at].min())} to {z(r['t'][at].max())}, echo length about {np.median(r['len'][at]):.0f} m; same radar track as before the silence={bool(same_track)}")


def p_0411_ps():
    last, r = _dark_track()
    w = (r["t"] >= ts("2027-10-15T03:30Z")) & (r["t"] <= ts("2027-10-15T05:30Z")) & (r["spd"] < 1.5)
    if last is None or not w.any():
        return False, "no slow unmatched contact off the entrance 03:30-05:30Z"
    off = dist_m(r["lat"][w], r["lon"][w], *last) > 2000
    if not off.any():
        return False, "the unmatched contact never left its anchorage position"
    t, la, lo = r["t"][w][off], r["lat"][w][off], r["lon"][w][off]
    dur = (t.max() - t.min()) / 60
    spread = float(dist_m(la, lo, la.mean(), lo.mean()).max())
    d_buoy = float(dist_m(la.mean(), lo.mean(), *SEA_BUOY)) / 1852
    ok = 30 <= dur <= 50 and spread < 400 and 1.2 <= d_buoy <= 3.0 and t.min() <= ts("2027-10-15T04:20Z") <= t.max()
    return ok, (f"unmatched ship-sized track nearly stopped {z(t.min())} to {z(t.max())} ({dur:.0f} min) at {la.mean():.4f},{lo.mean():.4f}, {d_buoy:.1f} nm seaward of the sea buoy on the "
                f"approach, {len(t)} plots within {spread:.0f} m")


def p_0403_ps():
    last, r = _dark_track()
    c = R(ts("2027-10-15T07:00Z"), ts("2027-10-15T14:00Z"), ne=True)
    best = None
    for tr in set(c["track"][c["corr"]]):
        m = c["track"] == tr
        t, la, lo = c["t"][m], c["lat"][m], c["lon"][m]
        close = dist_m(la, lo, *last) < 200
        if close.sum() >= 20:
            dur = t[close].max() - t[close].min()
            if best is None or dur > best[1]:
                best = (tr, dur, t[close].min(), t[close].max(), c["mmsi"][m][0], int(close.sum()))
    if best is None:
        return False, "no second contact alongside the unmatched one"
    hull = r["t"][(r["t"] >= best[2]) & (r["t"] <= best[3]) & (dist_m(r["lat"], r["lon"], *last) < 500)]
    ok = best[1] >= 3 * H and best[2] <= ts("2027-10-15T09:30Z") <= best[3] and len(hull) >= 20
    return ok, (f"track {best[0]} ({NAME.get(best[4], best[4])}, MMSI {best[4]}) within 200 m of the unmatched ship-sized contact from {z(best[2])} to {z(best[3])} "
                f"({best[1] / H:.1f} h, {best[5]} plots), the unmatched contact plotted {len(hull)} times beside it")


def p_0413_ps():
    cam = [r for r in rows_between("camera_events", "time_utc", ts("2027-10-28T06:05Z"), ts("2027-10-28T06:30Z")) if r["sensor_id"] == "CAM-13" and r["event_type"] == "INCIDENT"]
    r = R(ts("2027-10-28T05:50Z"), ts("2027-10-28T06:40Z"), ne=True)
    m = r["mmsi"] == CB
    t, spd = r["t"][m], r["spd"][m]
    fast = spd[t < ts("2027-10-28T06:10Z")]
    slow = spd[t >= ts("2027-10-28T06:11Z")]
    ok = bool(cam) and cam[0]["mmsi"] == CB and len(fast) >= 2 and fast.max() > 4 and len(slow) >= 5 and slow.max() < 1.0
    return ok, ((f"{cam[0]['time_utc']} {cam[0]['sensor_id']} {cam[0]['event_type']}: '{cam[0]['note']}'; " if cam else "no camera incident row; ")
                + f"Buoy-NE track of Corrin Bay: {fast.max() if len(fast) else 0:.1f} kn before 06:10Z, {slow.max() if len(slow) else -1:.1f} kn or less in {len(slow)} plots after 06:11Z")


# ============================================================================ port conditions probes
def cond(t0, t1, col="effective_utc"):
    return rows_between("port_conditions", col, t0, t1)


def seg_status(t):
    out = {}
    for r in sorted(table("port_conditions"), key=lambda r: (epoch(r["effective_utc"]), epoch(r["issued_utc"]))):
        if r["segment_id"] and epoch(r["effective_utc"]) <= t and r["order_type"] in ("PORT CONDITION", "CHANNEL STATUS", "SAFETY ZONE", "SECURITY ZONE"):
            out[r["segment_id"]] = r["status"]
    return out


def p_0207_pc():
    x = [r for r in cond(ts("2027-09-11T05:00Z"), ts("2027-09-12T05:00Z")) if r["port_condition"] == "X-RAY" and r["order_type"] == "PORT CONDITION"]
    y = [r for r in cond(ts("2027-09-12T05:00Z"), ts("2027-09-13T05:00Z")) if r["port_condition"] == "YANKEE"]
    zz = [r for r in cond(ZULU, ZULU) if r["port_condition"] == "ZULU"]
    sy, sz = seg_status(YANKEE + 60), seg_status(ZULU + 60)
    ok = (bool(x) and all(r["status"] == "OPEN" for r in x) and bool(y) and sy.get("SEG-ENT") == "CLOSED TO INBOUND" and bool(zz)
          and all(sz.get(s) == "CLOSED" for s in ("SEG-ENT", "SEG-BAY", "SEG-LAQ", "SEG-INNER-E", "SEG-INNER-W")))
    return ok, (f"X-Ray {x[0]['order_id'] if x else None} effective {x[0]['effective_utc'] if x else None} (port open); Yankee {y[0]['order_id'] if y else None} effective "
                f"{y[0]['effective_utc'] if y else None} ({sy.get('SEG-ENT')}); Zulu {zz[0]['order_id'] if zz else None} effective {zz[0]['effective_utc'] if zz else None} (every channel segment CLOSED)")


def p_0210_pc():
    rows = [r for r in cond(ts("2027-09-11T05:00Z"), ts("2027-09-14T05:00Z")) if r["order_type"] == "VESSEL ORDER" and r["terminal_id"] == "TERM-01"]
    got = {r["vessel_mmsi"] for r in rows if "remain moored" in r["text"] and "Zulu" in r["text"]}
    ok = got == {KS, OB}
    return ok, "; ".join(f"{r['order_id']} {r['effective_utc']}: {r['text']}" for r in rows) or "no order for the two tankers"


def p_1203_pc():
    rows = [r for r in cond(ZULU, ZULU) if r["order_id"] == "COTP ORDER 27-2027"]
    ok = bool(rows) and all(r["status"] == "CLOSED" for r in rows) and "directed to sea" in rows[0]["text"] and "agents" in rows[0]["text"] and ts("2027-09-13T15:00Z") <= epoch(rows[0]["issued_utc"]) <= ZULU
    return ok, f"{rows[0]['order_id']} issued {rows[0]['issued_utc']}, effective {rows[0]['effective_utc']}, {len(rows)} segments CLOSED: {rows[0]['text']}" if rows else "COTP Order 27-2027 not found"


def p_1204_pc():
    rows = [r for r in cond(ts("2027-09-14T02:15Z"), ts("2027-09-14T04:15Z")) if r["authority"].startswith("Port of Corpus Christi")]
    ok = bool(rows) and rows[0]["effective_utc"].startswith("2027-09-14T02:40") and "Channel clear of traffic" in rows[0]["text"] and "cameras dark" in rows[0]["text"]
    return ok, f"{rows[0]['order_id']} {rows[0]['effective_utc']}: '{rows[0]['text']}'" if rows else "no port authority log entry at 02:40Z"


def p_1206_pc():
    sz = [r for r in cond(ts("2027-09-14T05:00Z"), ts("2027-09-17T05:00Z")) if r["order_type"] == "SAFETY ZONE"]
    st = seg_status(ts("2027-09-17T05:00Z"))
    opened = [r for r in cond(ts("2027-09-14T05:00Z"), ts("2027-09-17T05:00Z")) if r["status"] == "OPEN"]
    ok = bool(sz) and {r["segment_id"] for r in sz} == {"SEG-INNER-E", "SEG-INNER-W"} and "Inner Harbor" in sz[0]["text"] and all(v == "CLOSED" for v in st.values()) and not opened
    return ok, f"{sz[0]['order_id']} effective {sz[0]['effective_utc']}: {sz[0]['text'][:150]}; every segment still CLOSED on 17 Sep" if sz else "no safety zone order"


def p_0401_pc():
    rows = cond(ts("2027-10-14T05:00Z"), ts("2027-10-15T05:00Z"))
    st = seg_status(REOPEN1 + 60)
    before = seg_status(REOPEN1 - 60)
    ok = (bool(rows) and st.get("SEG-ENT") == "OPEN" and st.get("SEG-BAY") == "OPEN" and st.get("SEG-INNER-E") == "RESTRICTED" and st.get("SEG-INNER-W") == "CLOSED TO DEEP-DRAFT"
          and before.get("SEG-ENT") == "CLOSED" and before.get("SEG-BAY") == "CLOSED")
    return ok, f"{rows[0]['order_id'] if rows else None} effective {rows[0]['effective_utc'] if rows else None}: " + ", ".join(f"{k} {v}" for k, v in sorted(st.items()))


def p_0410_pc():
    mid = seg_status(ts("2027-10-21T12:00Z"))
    end = seg_status(ts("2027-10-28T05:00:30Z"))
    lift = [r for r in cond(ts("2027-10-28T05:00Z"), ts("2027-10-28T05:00Z")) if "lifted" in r["text"]]
    dec = [r for r in cond(REOPEN1, REOPEN1) if "decontamination" in r["text"]]
    ok = mid.get("SEG-INNER-E") == "RESTRICTED" and mid.get("SEG-INNER-W") == "CLOSED TO DEEP-DRAFT" and end.get("SEG-INNER-E") == "OPEN" and end.get("SEG-INNER-W") == "OPEN" and bool(lift) and bool(dec)
    return ok, (f"inner channel on 21 Oct: SEG-INNER-E {mid.get('SEG-INNER-E')}, SEG-INNER-W {mid.get('SEG-INNER-W')} (decontamination wording={bool(dec)}); "
                f"{lift[0]['order_id'] if lift else None} effective {lift[0]['effective_utc'] if lift else None}: {lift[0]['text'] if lift else ''}")


def p_1208_pc():
    rows = cond(ts("2027-10-14T16:00Z"), ts("2027-10-14T18:00Z"))
    ok = bool(rows) and "outer and bay reaches cleared for deep-draft traffic" in rows[0]["text"] and "Inner channel restricted" in rows[0]["text"] and rows[0]["effective_utc"].startswith("2027-10-14T16:00")
    return ok, f"{rows[0]['order_id']} issued {rows[0]['issued_utc']}, effective {rows[0]['effective_utc']}: {rows[0]['text']}" if rows else "no order effective 16:00-18:00Z 14 Oct"


def p_0414_pc():
    close = [r for r in cond(BLAST, BLAST + 3600) if r["status"] == "CLOSED"]
    during = seg_status(ts("2027-11-05T00:00Z"))
    reopen = [r for r in cond(ts("2027-11-11T05:00Z"), ts("2027-11-12T06:00Z")) if r["status"] == "OPEN"]
    second = [r for r in cond(ts("2027-11-05T05:00Z"), ts("2027-11-06T06:00Z")) if "second" in r["text"].lower()]
    opened_early = [r for r in cond(BLAST + 3601, ts("2027-11-11T04:59Z")) if r["status"] == "OPEN"]
    ok = (len({r["segment_id"] for r in close}) == 7 and all(v == "CLOSED" for v in during.values()) and len({r["segment_id"] for r in reopen}) == 7 and "sweep" in reopen[0]["text"]
          and bool(second) and not opened_early)
    return ok, (f"{close[0]['order_id'] if close else None} effective {close[0]['effective_utc'] if close else None}: all 7 segments CLOSED; {second[0]['order_id'] if second else None} "
                f"{second[0]['effective_utc'] if second else None} second object; {reopen[0]['order_id'] if reopen else None} effective {reopen[0]['effective_utc'] if reopen else None}: "
                f"{reopen[0]['text'] if reopen else ''}")


# ============================================================================ arrivals probes
def arr():
    return table("vessel_arrivals")


def p_0104_pa():
    rows = [r for r in arr() if r["mmsi"] == HD or "HALCYON DRIFT" in r["vessel_name"].upper()]
    man = [r for r in table("cargo_manifest") if r["mmsi"] == HD]
    return (not rows and not man), f"port calls on file for MMSI {HD}: {len(rows)}; manifest lines: {len(man)} (of {len(arr())} port calls in the file)"


def p_0204_pa():
    rows = [r for r in arr() if r["mmsi"] == GP and ts("2027-09-09T05:00Z") <= epoch(r["noa_submitted_datetime"]) <= ts("2027-09-12T05:00Z")]
    ok = len(rows) == 1 and epoch(rows[0]["eta_datetime"]) < ZULU
    return ok, (f"{rows[0]['arrival_id']} filed {rows[0]['noa_submitted_datetime']} for {rows[0]['vessel_name']}, ETA {rows[0]['eta_datetime']} at {rows[0]['terminal_id']}" if rows
                else "no notice of arrival filed 9-11 Sep")


def p_0207_pa():
    rows = [r for r in arr() if ts("2027-09-12T05:00Z") <= epoch(r["eta_datetime"]) <= ts("2027-10-14T05:00Z")]
    held = [r for r in arr() if "Yankee" in r["hold_log"] and r["ata_datetime"] and epoch(r["ata_datetime"]) >= REOPEN1 and epoch(r["ata_anchorage_datetime"]) < ZULU]
    canc = [r for r in rows if r["noa_status"] == "CANCELLED"]
    berthed_closed = [r for r in arr() if r["ata_datetime"] and ZULU - 29 * H <= epoch(r["ata_datetime"]) < REOPEN1 and r["mmsi"] not in (KS, OB)]
    sl = [r for r in arr() if r["mmsi"] == SEALIFT and "postponed" in r["hold_log"] and "2027-09-11" in r["hold_log"]]
    ok = len(held) >= 5 and len(canc) >= 5 and not berthed_closed and len(sl) == 1 and not sl[0]["ata_datetime"]
    return ok, (f"{len(held)} port calls held at the anchorage from Yankee and berthed only after the reopening; port calls with an ETA between 12 Sep and 14 Oct: {len(rows)}, of which {len(canc)} cancelled; "
                f"berthings while closed to inbound: {len(berthed_closed)}; sealift call {sl[0]['arrival_id'] if sl else None}: {sl[0]['hold_log'] if sl else 'not found'}")


def p_0210_pa():
    det, ok = [], True
    for m, b in ((KS, "TERM-01-B07"), (OB, "TERM-01-B08")):
        rows = [r for r in arr() if r["mmsi"] == m and r["berth_id"] == b]
        good = len(rows) == 1 and rows[0]["atd_datetime"] == "" and rows[0]["noa_status"] == "REMAINING IN PORT" and ts("2027-09-11T05:00Z") <= epoch(rows[0]["ata_datetime"]) <= ts("2027-09-12T05:00Z")
        ok &= good
        if rows:
            det.append(f"{rows[0]['arrival_id']} {rows[0]['vessel_name']} berthed {b} {rows[0]['ata_datetime']}, departure '{rows[0]['atd_datetime']}', status {rows[0]['noa_status']}")
    return ok, "; ".join(det) or "no port calls for the two tankers"


def p_0401_pa():
    rows = [r for r in arr() if r["ata_datetime"] and REOPEN1 <= epoch(r["ata_datetime"]) <= ts("2027-10-18T05:00Z")]
    backlog = [r for r in rows if r["ata_anchorage_datetime"] and epoch(r["ata_anchorage_datetime"]) < REOPEN1 - 86400]
    g = [r for r in rows if r["mmsi"] == GP]
    first = min((epoch(r["ata_datetime"]) for r in rows), default=None)
    ok = len(backlog) >= 5 and len(g) == 1 and g[0]["ata_datetime"].startswith(("2027-10-17T", "2027-10-18T0")) and ts("2027-10-17T05:00Z") <= epoch(g[0]["ata_datetime"]) < ts("2027-10-18T05:00Z") \
        and epoch(g[0]["eta_datetime"]) < ZULU
    return ok, (f"{len(rows)} berthings 14-18 Oct, first {z(first) if first else None}, {len(backlog)} of them ships that had waited offshore since before the reopening; "
                f"Gulf Provider {g[0]['arrival_id'] if g else None}: ETA {g[0]['eta_datetime'] if g else None}, berthed {g[0]['berth_id'] if g else None} {g[0]['ata_datetime'] if g else None}")


def p_0414_pa():
    rows = [r for r in arr() if BLAST <= epoch(r["eta_datetime"]) <= REOPEN2]
    held = [r for r in arr() if r["hold_log"] and "2027-10-2" in r["hold_log"] + "" and r["ata_datetime"] and epoch(r["ata_datetime"]) >= REOPEN2 and "ship channel closed" in r["hold_log"]]
    held += [r for r in rows if r not in held and r["hold_log"] and r["ata_datetime"] and epoch(r["ata_datetime"]) >= REOPEN2]
    canc = [r for r in rows if r["noa_status"] == "CANCELLED"]
    berthed = [r for r in arr() if r["ata_datetime"] and BLAST + 1800 <= epoch(r["ata_datetime"]) < REOPEN2]
    crude_sailed = [r for r in arr() if r["atd_datetime"] and BLAST + 1800 <= epoch(r["atd_datetime"]) < REOPEN2]
    ok = len(held) >= 5 and len(canc) >= 2 and not berthed and not crude_sailed
    return ok, (f"port calls with an ETA during the closure: {len(rows)}; held offshore and berthed after 11 Nov: {len(held)}; cancelled: {len(canc)}; berthings during the closure: {len(berthed)}; "
                f"sailings (loaded tankers included) during the closure: {len(crude_sailed)}")


def p_0409_pa():
    rows = [r for r in arr() if r["mmsi"] == SEALIFT and r["ata_datetime"]]
    if len(rows) != 1:
        return False, f"{len(rows)} completed sealift calls"
    r = rows[0]
    late = (epoch(r["ata_datetime"]) - epoch(r["eta_datetime"])) / 86400
    ok = (r["berth_id"] == "TERM-07-B01" and ts("2027-11-12T06:00Z") <= epoch(r["ata_datetime"]) < ts("2027-11-13T06:00Z") and ts("2027-11-17T06:00Z") <= epoch(r["atd_datetime"]) < ts("2027-11-18T06:00Z")
          and r["eta_datetime"].startswith("2027-10-29") and 13.5 <= late <= 14.6)
    return ok, f"{r['arrival_id']} {r['vessel_name']}: planned {r['eta_datetime']}, berthed {r['berth_id']} {r['ata_datetime']} ({late:.1f} days later), sailed {r['atd_datetime']}; '{r['hold_log']}'"


# ============================================================================ manifest probes
def man():
    return table("cargo_manifest")


def p_0204_cm():
    rows = [r for r in man() if r["booking_date"] == "2027-09-09" and r["consignee_id"] == "VND-0006" and r["mmsi"] == GP and r["unit_of_measure"].startswith("CONTAINER")]
    n = sum(int(float(r["quantity"])) for r in rows)
    boxes = sum(len(r["container_numbers"].split()) for r in rows)
    ok = n == 40 and boxes == 40 and all(r["planned_arrival_date"] < "2027-09-14" for r in rows) and all(r["consignee_name"] == "Gulf Relief Logistics" for r in rows)
    return ok, (f"{len(rows)} house bills booked 2027-09-09 on Gulf Provider for Gulf Relief Logistics (VND-0006): {n} forty-foot containers ({boxes} container numbers), planned arrival "
                f"{sorted({r['planned_arrival_date'] for r in rows})}, actual arrival {sorted({r['arrival_date'] for r in rows})}")


def _parts():
    return [r for r in man() if "PUMP REBUILD PARTS" in r["cargo_description"]]


def p_0308_cm():
    rows = _parts()
    if len(rows) != 1:
        return False, f"{len(rows)} pump-parts consignments"
    r = rows[0]
    late = (epoch(r["arrival_date"] + "T00:00:00") - epoch(r["planned_arrival_date"] + "T00:00:00")) / 86400
    ok = r["arrival_date"] == "2027-10-20" and late == 25 and not r["port_of_lading"].endswith(", TX") and "2027-09-16" <= r["booking_date"] <= "2027-09-17"
    return ok, f"{r['manifest_id']} {r['cargo_description']} from {r['shipper_name']}, {r['port_of_lading']}: booked {r['booking_date']}, promised {r['planned_arrival_date']}, arrived {r['arrival_date']} ({late:.0f} days late)"


def p_0405_cm():
    rows = [r for r in man() if r["mode"] == "AIR" and "NAS Corpus Christi" in r["port_of_discharge"] and "2027-10-18" <= r["arrival_date"] <= "2027-10-27"]
    days = sorted({r["arrival_date"] for r in rows})
    mil = sum(1 for r in rows if "C-17" in r["carrier"])
    ok = len(rows) == 40 and len(days) >= 8 and all(r["release_date"] >= r["arrival_date"] for r in rows) and mil == 26
    return ok, f"{len(rows)} air consignments received at NAS Corpus Christi on {len(days)} days {days[0] if days else ''} to {days[-1] if days else ''}: {mil} military airlift, {len(rows) - mil} civil charter"


def p_0406_cm():
    rows = _parts()
    ok = len(rows) == 1 and rows[0]["arrival_date"] == "2027-10-20" and rows[0]["release_date"] == "2027-10-20" and rows[0]["supplier_id"] == "VND-0005" and "Water" in rows[0]["consignee_name"]
    return ok, (f"{rows[0]['manifest_id']} {rows[0]['cargo_description']}: delivered {rows[0]['release_date']} to {rows[0]['consignee_name']} (supplier {rows[0]['supplier_id']})" if rows else "no pump-parts consignment")


def p_0409_cm():
    rows = [r for r in man() if r["mmsi"] == SEALIFT]
    heli = [r for r in rows if "ROTARY-WING" in r["cargo_description"]]
    calls = {r["arrival_id"] for r in rows}
    call = [a for a in arr() if a["arrival_id"] in calls]
    ok = (len(rows) >= 2 and len(heli) == 1 and all(r["direction"] == "EXPORT" for r in rows) and all("2027-11-12" <= r["arrival_date"] <= "2027-11-13" for r in rows)
          and all(r["release_date"] == "2027-11-17" for r in rows) and len(call) == 1 and call[0]["berth_id"] == "TERM-07-B01")
    return ok, f"{len(rows)} export lines on {NAME[SEALIFT]} ({', '.join(sorted(calls))}): " + "; ".join(r["cargo_description"] for r in rows) + f"; alongside {rows[0]['arrival_date'] if rows else ''}, sailed {rows[0]['release_date'] if rows else ''}"


# ============================================================================ stream descriptions
def _span_ais():
    lo = min(a[0, 0] for a in ais()[0].values())
    hi = max(a[-1, 0] for a in ais()[0].values())
    return float(lo), float(hi)


def _span_surv():
    d = radar()
    st = table("sensor_status")
    return float(min(d["t"].min(), epoch(st[0]["time_utc"]))), float(max(d["t"].max(), epoch(st[-1]["time_utc"])))


def _ids_surv():
    out = set(radar()["mmsi"]) - {""}
    out |= {r["mmsi"] for r in table("camera_events") if r["mmsi"]} | {r["mmsi"] for r in table("vessel_traffic_log") if r["mmsi"]}
    for name in ("camera_events", "sensor_status"):
        out |= {r["sensor_id"] for r in table(name)}
    out |= {"RADAR-BUOY-NE" if x else "RADAR-BUOY-SW" for x in set(radar()["ne"].tolist())}
    out |= {r["berth_id"] for r in table("camera_events") if r["berth_id"]}
    return out


def _text(name, cols):
    for r in table(name):
        yield " | ".join(r[c] for c in cols)


def _header(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return next(csv.reader(fh))


def _surv_columns():
    out = []
    for fp in sorted(glob.glob(os.path.join(SURV, "*.csv"))):
        out += _header(fp)
    return sorted(set(out))


ALL_MMSI = set(BY_MMSI)
TERMINAL_IDS = {t["terminal_id"] for t in TR["terminals"]} | set(BERTH) | {a["position_id"] for a in TR["anchorage_positions"]}
SEGMENTS = {"SEG-ENT", "SEG-BAY", "SEG-LAQ", "SEG-INNER-E", "SEG-INNER-W", "SEG-GIWW", "SEG-ANCH"}


def _entity_ids():
    out = set()
    for k, v in reg("entity_registry").items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict):
                    out |= {str(val) for key, val in x.items() if key.endswith("_id") and isinstance(val, str)}
    return out


STREAMS = {
    "ais": {
        "time_range": _span_ais,
        "ids": lambda: set(ais()[0]) | set(sais()[0]),
        "registry_ids": lambda: ALL_MMSI,
        "public_voice": False,
        "text": lambda: (" ".join(sorted(n)) for n in list(ais()[2].values()) + [{d for _, d in v} for v in ais()[1].values()]),
        "columns": lambda: _header(sorted(glob.glob(AIS_GLOB))[0]),
    },
    "port_surveillance": {
        "time_range": _span_surv,
        "ids": _ids_surv,
        "registry_ids": lambda: ALL_MMSI | {r["sensor_id"] for r in table("sensors")} | set(BERTH),
        "public_voice": False,
        "text": lambda: list(_text("camera_events", ("vessel_name", "vessels_in_view", "water_surface", "note"))) + list(_text("sensor_status", ("status", "detail")))
        + list(_text("vessel_traffic_log", ("vessel_name", "pilot_boat", "tugs", "from_place", "to_place"))) + list(_text("sensors", ("name",))),
        "columns": _surv_columns,
    },
    "port_conditions": {
        "time_range": lambda: (min(epoch(r["effective_utc"]) for r in table("port_conditions")), ts("2028-01-12T06:00Z")),   # an order stands until the next one: the last row is the state to the end of the span
        "ids": lambda: {r["vessel_mmsi"] for r in table("port_conditions") if r["vessel_mmsi"]} | {r["terminal_id"] for r in table("port_conditions") if r["terminal_id"]}
        | {r["segment_id"] for r in table("port_conditions") if r["segment_id"]},
        "registry_ids": lambda: ALL_MMSI | TERMINAL_IDS | SEGMENTS,
        "public_voice": True,
        "text": lambda: _text("port_conditions", ("order_id", "authority", "segment_name", "status", "text")),
        "columns": lambda: _header(os.path.join(SUP, "port_conditions.csv")),
    },
    "port_arrivals": {
        "time_range": lambda: (min(epoch(r["eta_datetime"]) for r in arr()), max(epoch(r[c]) for r in arr() for c in ("eta_datetime", "ata_datetime", "atd_datetime") if r[c])),
        "ids": lambda: {r["mmsi"] for r in arr()} | {r[c] for r in arr() for c in ("terminal_id", "berth_id", "anchorage_position_id", "shift_berth_id") if r[c]},
        "registry_ids": lambda: ALL_MMSI | TERMINAL_IDS,
        "public_voice": False,
        "text": lambda: _text("vessel_arrivals", ("vessel_name", "terminal", "agent", "hold_log")),
        "columns": lambda: _header(os.path.join(SUP, "vessel_arrivals.csv")),
    },
    "cargo_manifests": {
        "time_range": lambda: (min(epoch(r["booking_date"] + "T00:00:00") for r in man()), max(epoch((r["release_date"] or r["arrival_date"] or r["booking_date"]) + "T00:00:00") for r in man()) + 86399),
        "ids": lambda: {r["mmsi"] for r in man() if r["mmsi"]} | {r[c] for r in man() for c in ("supplier_id", "consignee_id") if r[c]} | {r["arrival_id"] for r in man() if r["arrival_id"]},
        "registry_ids": lambda: ALL_MMSI | _entity_ids() | {r["arrival_id"] for r in arr()},
        "public_voice": False,
        "text": lambda: _text("cargo_manifest", ("vessel_name", "carrier", "cargo_description", "shipper_name", "consignee_name", "port_of_lading", "port_of_discharge")),
        "columns": lambda: _header(os.path.join(SUP, "cargo_manifest.csv")),
    },
}

PROBES = {
    ("EVT-0104", "ais"): p_0104_ais, ("EVT-1201", "ais"): p_1201_ais, ("EVT-1202", "ais"): p_1202_ais, ("EVT-0207", "ais"): p_0207_ais,
    ("EVT-0210", "ais"): p_0210_ais, ("EVT-1906", "ais"): p_1906_ais, ("EVT-0401", "ais"): p_0401_ais, ("EVT-0410", "ais"): p_0410_ais,
    ("EVT-1208", "ais"): p_1208_ais, ("EVT-0402", "ais"): p_0402_ais, ("EVT-0404", "ais"): p_0404_ais, ("EVT-0414", "ais"): p_0414_ais,
    ("EVT-0413", "ais"): p_0413_ais, ("EVT-0409", "ais"): p_0409_ais,
    ("EVT-1201", "port_surveillance"): p_1201_ps, ("EVT-1202", "port_surveillance"): p_1202_ps, ("EVT-1203", "port_surveillance"): p_1203_ps,
    ("EVT-1204", "port_surveillance"): p_1204_ps, ("EVT-1205", "port_surveillance"): p_1205_ps, ("EVT-1207", "port_surveillance"): p_1207_ps,
    ("EVT-1208", "port_surveillance"): p_1208_ps, ("EVT-0402", "port_surveillance"): p_0402_ps, ("EVT-0411", "port_surveillance"): p_0411_ps,
    ("EVT-0403", "port_surveillance"): p_0403_ps, ("EVT-0413", "port_surveillance"): p_0413_ps,
    ("EVT-0207", "port_conditions"): p_0207_pc, ("EVT-0210", "port_conditions"): p_0210_pc, ("EVT-1203", "port_conditions"): p_1203_pc,
    ("EVT-1204", "port_conditions"): p_1204_pc, ("EVT-1206", "port_conditions"): p_1206_pc, ("EVT-0401", "port_conditions"): p_0401_pc,
    ("EVT-0410", "port_conditions"): p_0410_pc, ("EVT-1208", "port_conditions"): p_1208_pc, ("EVT-0414", "port_conditions"): p_0414_pc,
    ("EVT-0104", "port_arrivals"): p_0104_pa, ("EVT-0204", "port_arrivals"): p_0204_pa, ("EVT-0207", "port_arrivals"): p_0207_pa,
    ("EVT-0210", "port_arrivals"): p_0210_pa, ("EVT-0401", "port_arrivals"): p_0401_pa, ("EVT-0414", "port_arrivals"): p_0414_pa,
    ("EVT-0409", "port_arrivals"): p_0409_pa,
    ("EVT-0204", "cargo_manifests"): p_0204_cm, ("EVT-0308", "cargo_manifests"): p_0308_cm, ("EVT-0405", "cargo_manifests"): p_0405_cm,
    ("EVT-0406", "cargo_manifests"): p_0406_cm, ("EVT-0409", "cargo_manifests"): p_0409_cm,
}


if __name__ == "__main__":
    import time
    t0 = time.time()
    bad = 0
    for (ev, st), fn in PROBES.items():
        if len(sys.argv) > 1 and sys.argv[1] not in (ev, st):
            continue
        try:
            ok, detail = fn()
        except Exception as e:      # noqa: BLE001
            import traceback
            ok, detail = False, "raised: " + traceback.format_exc(limit=3)
        bad += not ok
        print(("ok   " if ok else "FAIL "), ev, st, "-", detail)
    print(f"{bad} failing, {time.time() - t0:.0f} s")
