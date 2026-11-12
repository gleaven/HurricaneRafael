"""Build the map viewer's data from the delivered logs.

    python3 scripts/build_map.py --resume [--budget=140]   run pending steps until the time budget is used; repeat until COMPLETE
    python3 scripts/build_map.py status                     list steps and what is done
    python3 scripts/build_map.py step tracks:ais:2027-09    run one step
    python3 scripts/build_map.py --force ...                ignore the cache

A step is redone by itself when any file it reads has changed since its cache entry was written
(size or modification time), or when its logic version in CODE is bumped; nothing needs deleting
by hand. `status` shows which steps are up to date, stale or never run.

The viewer never has tracks of its own: every position it shows comes from a stream file in
05_other_sources/. Steps (each well under the 150 s shell limit, cached in viewer/_build_cache):

  tracks:ais|adsb|drone|det|radar:<month>, tracks:avl:<file>   logged fixes -> simplified parts
  points:911:<month>      incidents
  sensors:gauge|field|outage                                    readings on fixed time slots
  index                   registries, static layers, events, alerts, storm track, reference outlines
  assemble:<month>        writes viewer/map_data/day_<n>.js for each UTC day of the month
  summary                 per-day activity for the timeline strip

Simplification never moves an asset off its real path: see scripts/map_tracks.py. Vessel
segments are re-checked against land; vehicle paths between fixes are matched to the road
network when a straight line between two fixes would cut a corner.
"""
import csv
import datetime as dt
import glob
import json
import math
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "streams"))
import geo            # noqa: E402
import map_tracks as mt  # noqa: E402

SRC = os.path.join(ROOT, "05_other_sources")
VIEW = os.path.join(ROOT, "09_shared_state_timeline", "viewer")
OUT = os.path.join(VIEW, "map_data")
CACHE = os.path.join(VIEW, "_build_cache")
D0 = 1820880000
DAY = 86400
FIRST_DAY, LAST_DAY = -30, 120                       # UTC day indices covered by the streams
MONTHS = ["2027-08", "2027-09", "2027-10", "2027-11", "2027-12", "2028-01"]
UTC = dt.timezone.utc

_G = {}


def G():
    if "g" not in _G:
        _G["g"] = geo.Geo()
    return _G["g"]


def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return json.load(fh)


_dates = {}


def ptime(s):
    """Epoch from 'YYYY-MM-DD[T ]HH:MM[:SS][Z]' (UTC)."""
    d = s[:10]
    if d not in _dates:
        _dates[d] = int(dt.datetime(int(d[:4]), int(d[5:7]), int(d[8:10]), tzinfo=UTC).timestamp())
    sec = int(s[17:19]) if len(s) >= 19 and s[16] == ":" else 0
    return _dates[d] + int(s[11:13]) * 3600 + int(s[14:16]) * 60 + sec


def utc_offset(t):
    return -5 if t < 1825570800 else -6


def local_to_epoch(s):
    """Epoch from a local wall-clock string 'YYYY-MM-DD HH:MM[:SS]'."""
    naive = ptime(s if len(s) > 10 else s + " 00:00")
    return naive - utc_offset(naive + 6 * 3600) * 3600


def e5(v):
    return int(round(float(v) * 1e5))


def cache_path(step):
    return os.path.join(CACHE, step.replace(":", "__").replace("/", "_") + ".json")


def save_cache(step, obj):
    os.makedirs(CACHE, exist_ok=True)
    tmp = cache_path(step) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    os.replace(tmp, cache_path(step))


def read_cache(step):
    with open(cache_path(step), encoding="utf-8") as fh:
        return json.load(fh)


def month_of(t):
    d = dt.datetime.fromtimestamp(t, UTC)
    return f"{d.year}-{d.month:02d}"


# ======================================================================================
# track steps
# ======================================================================================
def _finish_parts(t, la, lo, parts_idx, tol_perp, tol_sed, check=None, z=None, tol_z=None, zi=None, force=None):
    """Simplify each part; return list of flat int lists [t, lat_e5, lon_e5(, z)]."""
    x, y = mt.to_xy(la, lo)
    out, kept = [], 0
    for a, b in parts_idx:
        if b == a:
            keep = np.array([True])
        else:
            keep = mt.simplify(t[a:b + 1], x[a:b + 1], y[a:b + 1], tol_perp, tol_sed, None if z is None else z[a:b + 1], tol_z)
            if force is not None:
                keep |= force[a:b + 1]
            if check is not None:
                keep = mt.enforce(keep, lambda i, j: check(la[a + i], lo[a + i], la[a + j], lo[a + j]))
        idx = np.where(keep)[0] + a
        flat = []
        for k in idx:
            flat += [int(t[k]), e5(la[k]), e5(lo[k])]
            if zi is not None:
                flat.append(int(zi[k]))
        out.append(flat)
        kept += len(idx)
    return out, kept


def step_ais(month):
    W = mt.WaterCheck(G())
    rows = {}
    with open(os.path.join(SRC, "ais", f"ais_{month}.csv"), encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        h = next(rd)
        ix = {k: h.index(k) for k in ("MMSI", "BaseDateTime", "LAT", "LON", "SOG", "Heading", "Status", "VesselName")}
        for r in rd:
            v = rows.setdefault(r[ix["MMSI"]], ([], [], [], [], [], [], [r[ix["VesselName"]]]))
            v[0].append(ptime(r[ix["BaseDateTime"]])); v[1].append(float(r[ix["LAT"]])); v[2].append(float(r[ix["LON"]]))
            v[3].append(float(r[ix["SOG"]] or 0)); v[4].append(r[ix["Heading"]]); v[5].append(r[ix["Status"]])
    assets, n_in, n_out = {}, 0, 0
    for mmsi, (t, la, lo, sog, hd, stt, nm) in rows.items():
        t = np.array(t); la = np.array(la); lo = np.array(lo)
        o = np.argsort(t, kind="stable")
        t, la, lo = t[o], la[o], lo[o]
        sog = [sog[i] for i in o]; hd = [hd[i] for i in o]; stt = [stt[i] for i in o]
        x, y = mt.to_xy(la, lo)
        parts = mt.split_parts(t, x, y, 35 * 60)
        flat, kept = _finish_parts(t, la, lo, parts, 12.0, 60.0, W.clear)
        st, last = [], None
        for ti, s in zip(t, stt):
            if s != last:
                st += [int(ti), int(s) if s.isdigit() else -1]
                last = s
        hh, lasth = [], None
        for ti, sg, hv in zip(t, sog, hd):
            if sg < 0.3 and hv not in ("", "511"):
                hv = int(float(hv))
                if lasth is None or abs(((hv - lasth + 180) % 360) - 180) > 6:
                    hh += [int(ti), hv]
                    lasth = hv
        assets[mmsi] = {"p": flat, "st": st, "hd": hh, "nm": nm[0]}
        n_in += len(t); n_out += kept
    save_cache(f"tracks:ais:{month}", {"assets": assets})
    return f"{len(assets)} vessels, {n_in:,} fixes -> {n_out:,} vertices"


def step_adsb(month):
    rows = {}
    with open(os.path.join(SRC, "adsb", f"adsb_{month}.csv"), encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        h = next(rd)
        ix = {k: h.index(k) for k in ("icao24", "callsign", "time_position", "longitude", "latitude", "baro_altitude", "on_ground", "nic")}
        for r in rd:
            v = rows.setdefault(r[ix["icao24"]], ([], [], [], [], [], [r[ix["callsign"]].strip()]))
            v[0].append(int(float(r[ix["time_position"]]))); v[1].append(float(r[ix["latitude"]])); v[2].append(float(r[ix["longitude"]]))
            g = r[ix["on_ground"]] in ("True", "true", "1")
            # altitude: -1 means on the ground; airborne values are kept at 1 m or more (barometric altitude can
            # read below zero in a low hover, which must not be mistaken for "on the ground")
            v[3].append(-1.0 if g else max(1.0, float(r[ix["baro_altitude"]] or 0)))
            v[4].append(int(r[ix["nic"]] or 8) if r[ix["nic"]].strip().isdigit() else 8)
    assets, n_in, n_out = {}, 0, 0
    for icao, (t, la, lo, alt, nic, cs) in rows.items():
        t = np.array(t); la = np.array(la); lo = np.array(lo); alt = np.array(alt); nic = np.array(nic)
        o = np.argsort(t, kind="stable")
        t, la, lo, alt, nic = t[o], la[o], lo[o], alt[o], nic[o]
        x, y = mt.to_xy(la, lo)
        parts = mt.split_parts(t, x, y, 5 * 60, still_m=60)
        # keep every fix where the aircraft leaves or touches the ground, and every distinct position on the ground,
        # so nothing is ever drawn "on the ground" away from where the log has it on the ground
        gnd = alt < 0
        force = np.zeros(len(t), bool)
        force[1:] |= gnd[1:] != gnd[:-1]
        force[:-1] |= gnd[1:] != gnd[:-1]
        mv = np.ones(len(t), bool)
        mv[1:] = np.hypot(np.diff(x), np.diff(y)) > 2.0
        force |= gnd & mv
        flat, kept = _finish_parts(t, la, lo, parts, 60.0, 400.0, None, alt, 40.0, np.round(alt), force)
        # navigation-integrity drops (receiver-reported), as [start, end] pairs
        low = nic < 6
        iv, a = [], None
        for ti, f in zip(t, low):
            if f and a is None:
                a = int(ti)
            if not f and a is not None:
                iv += [a, int(ti)]; a = None
        if a is not None:
            iv += [a, int(t[-1])]
        assets[icao] = {"p": flat, "cs": cs[0], "ni": iv}
        n_in += len(t); n_out += kept
    save_cache(f"tracks:adsb:{month}", {"assets": assets})
    return f"{len(assets)} aircraft, {n_in:,} fixes -> {n_out:,} vertices"


_M = {}


def matcher():
    if "m" not in _M:
        _M["m"] = mt.RoadMatcher(G())
    return _M["m"]


def _tick_in(lo, hi):
    """First multiple of 900 s in the half-open interval [lo, hi), or None."""
    k = math.ceil(lo / 900.0) * 900.0
    return k if k < hi else None


def match_gap(M, a, b, ta, tb):
    """Vertices (epoch, lat, lon) that take a vehicle from fix a (at ta) to fix b (at tb) along the
    street network, excluding the two fixes themselves, plus how the gap was resolved:
      "road"  a street path that could be driven in the time available
      "fast"  a street path exists but is a long way round; it is still followed when it could
              have been driven in the time
      "bridged"  the long way round could not have been driven in the time: streets from both ends,
              joined by one hop of at most 60 m (divided roads, crossings the street file leaves open)
      None    no street connection: the caller keeps the two fixes and nothing in between
    Time is shared out by distance along the streets. A fix that sits off the centreline (a station
    yard, a hospital apron, a driveway) is joined to the street by a short hop driven at about
    20 m/s; hops are timed so that the vehicle is on the street, not mid-yard, at each 15-minute
    tick, because the yard has no geometry to follow."""
    gap = tb - ta
    d_st = geo.dist_m(a, b)
    r = M.path(a, b, max(6.0 * d_st + 1500.0, 2500.0))
    if r is None:
        return None, None
    pts, metres, sa, sb = r
    kind = "road" if (metres <= max(3.0 * d_st + 300.0, 400.0) and (gap <= 0 or metres <= 45.0 * gap + 200.0)) else "fast"
    if kind == "fast" and gap > 0 and metres > 35.0 * gap + 100.0:
        # the only street path is too long to have been driven in the time: follow the streets from both
        # ends and cross the short break between them, rather than racing round or jumping
        r2 = M.bridged(a, b, max(1.5 * d_st + 200.0, 400.0))
        if r2 is not None and r2[1] <= 35.0 * gap + 100.0:
            pts, metres, sa, sb = r2
            kind = "bridged"
    out = []
    ta, tb = int(ta), int(tb)
    gap = tb - ta
    t0, t1 = ta, tb
    if sa > 25.0 and gap >= 2:                       # leave the yard
        ha = max(1, min(int(math.ceil(sa / 20.0)), gap // 3))
        if ta % 900 == 0 and gap >= 6:               # a tick falls on the moment of departure: hold one second
            out.append((ta + 1, a)); t0 = ta + 1
        tk = _tick_in(t0 + 1, t0 + ha)
        if tk is not None:
            ha = int(tk) - t0
        t0 += ha
    if sb > 25.0 and gap >= 2:                       # enter the yard
        hb = max(1, min(int(math.ceil(sb / 20.0)), gap // 3))
        tk = _tick_in(t1 - hb + 1, t1)
        if tk is not None:
            hb = t1 - int(tk)
        t1 -= hb
    if t1 < t0:
        t0 = t1 = (ta + tb) // 2
    seg = [geo.dist_m(p, q) for p, q in zip(pts, pts[1:])]
    tot = sum(seg)
    on_a = sa <= 25.0 and geo.dist_m(a, pts[0]) <= 6.0
    on_b = sb <= 25.0 and geo.dist_m(b, pts[-1]) <= 6.0
    acc = 0.0
    if not on_a:
        out.append((t0, pts[0]))
    for i, (p, s_) in enumerate(zip(pts[1:], seg)):
        acc += s_
        last = i == len(seg) - 1
        if last and on_b:
            break
        out.append((int(round(t0 + (t1 - t0) * (acc / tot if tot > 0 else 1.0))), p))
    return out, kind


def step_avl(fname):
    Gx = G()
    R = mt.RoadCheck(Gx, 30.0)
    M = matcher()
    rows = {}
    with open(os.path.join(SRC, "avl", fname), encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        h = next(rd)
        ix = {k: h.index(k) for k in ("time_utc", "unit_id", "latitude", "longitude", "status", "incident_number")}
        for r in rd:
            v = rows.setdefault(r[ix["unit_id"]], ([], [], [], [], []))
            v[0].append(ptime(r[ix["time_utc"]])); v[1].append(float(r[ix["latitude"]])); v[2].append(float(r[ix["longitude"]]))
            v[3].append(r[ix["status"]]); v[4].append(r[ix["incident_number"]])
    assets, n_in, n_out = {}, 0, 0
    stats = {"moving": 0, "straight": 0, "road": 0, "fast": 0, "bridged": 0, "unmatched": 0}
    for unit, (t, la, lo, stt, inc) in rows.items():
        o = np.argsort(np.array(t), kind="stable")
        t = [t[i] for i in o]; la = [la[i] for i in o]; lo = [lo[i] for i in o]; stt = [stt[i] for i in o]; inc = [inc[i] for i in o]
        n_in += len(t)
        T, LA, LO = [float(t[0])], [la[0]], [lo[0]]
        protect = [False]                           # vertices the simplifier must keep (street geometry)
        for k in range(1, len(t)):
            a, b = (la[k - 1], lo[k - 1]), (la[k], lo[k])
            gap = t[k] - t[k - 1]
            d = geo.dist_m(a, b)
            if d >= 12 and gap <= 8 * 60:
                stats["moving"] += 1
                if R.clear(a[0], a[1], b[0], b[1]):
                    stats["straight"] += 1          # the straight line between the fixes is itself on the street
                else:
                    verts, kind = match_gap(M, a, b, t[k - 1], t[k])
                    if verts is None:
                        # no street connects the two fixes: stay at the earlier one until the next report
                        stats["unmatched"] += 1
                        T.append(t[k] - (1 if gap >= 2 else 0)); LA.append(la[k - 1]); LO.append(lo[k - 1]); protect.append(True)
                    else:
                        stats[kind] += 1
                        last_t = T[-1]
                        for tt, p in verts:
                            tv = min(max(tt, last_t), float(t[k]))
                            T.append(tv); LA.append(p[0]); LO.append(p[1]); protect.append(True)
                            last_t = tv
            T.append(float(t[k])); LA.append(la[k]); LO.append(lo[k]); protect.append(False)
        T = np.array(T); LA = np.array(LA); LO = np.array(LO)
        x, y = mt.to_xy(LA, LO)
        parts = mt.split_parts(T, x, y, 8 * 60, still_m=40)
        flat, kept = _finish_parts(T, LA, LO, parts, 10.0, 200.0, R.clear)
        st, last = [], None
        for ti, s, n in zip(t, stt, inc):
            if (s, n) != last:
                st.append([int(ti), s, n])
                last = (s, n)
        assets[unit] = {"p": flat, "st": st}
        n_out += kept
    save_cache(f"tracks:avl:{fname}", {"assets": assets, "match": stats, "unfilled": stats["unmatched"]})
    mv = max(1, stats["moving"])
    return (f"{len(assets)} units, {n_in:,} fixes -> {n_out:,} vertices; moving gaps {stats['moving']:,}: straight on street {stats['straight']:,}, "
            f"routed {stats['road']:,}, routed the long way round {stats['fast']:,}, joined across a short break {stats['bridged']:,}, no street path {stats['unmatched']:,} ({100 * stats['unmatched'] / mv:.2f}%)")


def step_drone(month):
    flights = {}
    for fp in sorted(glob.glob(os.path.join(SRC, "drone_video", f"drone_telemetry_{month}*.csv"))):
        with open(fp, encoding="utf-8", newline="") as fh:
            rd = csv.reader(fh)
            h = next(rd)
            ix = {k: h.index(k) for k in ("flight_id", "timestamp_utc", "latitude", "longitude", "rel_alt_m", "operator_id", "drone_model", "mission_name")}
            for r in rd:
                v = flights.setdefault(r[ix["flight_id"]], ([], [], [], [], [r[ix["operator_id"]], r[ix["drone_model"]], r[ix["mission_name"]]]))
                v[0].append(ptime(r[ix["timestamp_utc"]])); v[1].append(float(r[ix["latitude"]])); v[2].append(float(r[ix["longitude"]])); v[3].append(float(r[ix["rel_alt_m"]] or 0))
    out, n_in, n_out = [], 0, 0
    for fid, (t, la, lo, alt, meta) in flights.items():
        t = np.array(t); la = np.array(la); lo = np.array(lo); alt = np.array(alt)
        flat, kept = _finish_parts(t, la, lo, [(0, len(t) - 1)], 8.0, 40.0, None, alt, 8.0, np.round(alt))
        out.append({"id": fid, "op": meta[0], "md": meta[1], "ms": meta[2], "p": flat[0]})
        n_in += len(t); n_out += kept
    save_cache(f"tracks:drone:{month}", {"flights": out})
    return f"{len(out)} flights, {n_in:,} frames -> {n_out:,} vertices"


def step_det(month):
    tracks = {}
    with open(os.path.join(SRC, "drone_detections", f"detections_{month}.csv"), encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if not r["latitude"]:
                continue
            v = tracks.setdefault(r["track_id"] or (r["sensor_id"] + r["time_utc"]), {"t": [], "la": [], "lo": [], "alt": [], "s": r["sensor_id"], "k": r["detection_type"], "c": {}, "al": 0, "rid": r["remote_id"], "auth": r["authorization_id"]})
            v["t"].append(ptime(r["time_utc"])); v["la"].append(float(r["latitude"])); v["lo"].append(float(r["longitude"])); v["alt"].append(float(r["altitude_m"] or 0))
            v["c"][r["classification"]] = v["c"].get(r["classification"], 0) + 1
            v["al"] |= r["alert"] == "true"
    out, n_in, n_out = [], 0, 0
    for tid, v in tracks.items():
        t = np.array(v["t"]); la = np.array(v["la"]); lo = np.array(v["lo"]); alt = np.array(v["alt"])
        o = np.argsort(t, kind="stable")
        t, la, lo, alt = t[o], la[o], lo[o], alt[o]
        cls = max(v["c"], key=v["c"].get)
        loose = cls in ("bird", "clutter")
        flat, kept = _finish_parts(t, la, lo, [(0, len(t) - 1)], 120.0 if loose else 15.0, 400.0 if loose else 60.0, None, alt, 60.0, np.round(alt))
        out.append({"id": tid, "s": v["s"], "k": v["k"], "c": cls, "al": int(v["al"]), "au": 1 if v["auth"] else 0, "p": flat[0]})
        n_in += len(t); n_out += kept
    save_cache(f"tracks:det:{month}", {"tracks": out})
    return f"{len(out)} detection tracks, {n_in:,} plots -> {n_out:,} vertices"


def step_radar(month):
    W = mt.WaterCheck(G())
    tracks = {}
    with open(os.path.join(SRC, "port_surveillance", f"radar_tracks_{month}.csv"), encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        for r in rd:
            if r["ais_correlated"] == "Y":
                continue
            v = tracks.setdefault(r["sensor_id"] + "|" + r["track_id"], {"t": [], "la": [], "lo": [], "s": r["sensor_id"], "sz": r["size_class"], "len": r["est_length_m"]})
            v["t"].append(ptime(r["time_utc"])); v["la"].append(float(r["latitude"])); v["lo"].append(float(r["longitude"]))
    out, n_in, n_out = [], 0, 0
    for tid, v in tracks.items():
        t = np.array(v["t"]); la = np.array(v["la"]); lo = np.array(v["lo"])
        o = np.argsort(t, kind="stable")
        t, la, lo = t[o], la[o], lo[o]
        x, y = mt.to_xy(la, lo)
        parts = mt.split_parts(t, x, y, 20 * 60, still_m=60)
        flat, kept = _finish_parts(t, la, lo, parts, 20.0, 120.0, W.clear)
        out.append({"id": tid.split("|")[1], "s": v["s"], "sz": v["sz"], "len": v["len"], "p": flat})
        n_in += len(t); n_out += kept
    save_cache(f"tracks:radar:{month}", {"tracks": out})
    return f"{len(out)} radar tracks without AIS, {n_in:,} plots -> {n_out:,} vertices"


def step_911(month):
    days = {}
    n = 0
    with open(os.path.join(SRC, "911", f"cad_incidents_{month}.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                t0 = local_to_epoch(r["call_received_dttm"])
                t1 = local_to_epoch(r["cleared_dttm"]) if r["cleared_dttm"] else t0 + 1800
                la, lo = e5(r["latitude"]), e5(r["longitude"])
            except (ValueError, IndexError):
                continue
            days.setdefault(str((t0 - D0) // DAY), []).append([t0, t1, la, lo, r["nature_code"], r["priority"], r["agency"], r["incident_number"], r["unit_id"]])
            n += 1
    save_cache(f"points:911:{month}", {"days": days})
    return f"{n:,} incidents"


def _slot_series(files, tcol, cols, slot_s, parse=ptime, key=None, combine_date=None):
    """{sensor: {day: [[v...] per slot or None]}} taking the last observation in each slot."""
    out = {}
    for fp in files:
        with open(fp, encoding="utf-8", newline="") as fh:
            rd = csv.DictReader(fh)
            for r in rd:
                try:
                    t = parse(r[combine_date[0]] + "T" + r[combine_date[1]]) if combine_date else parse(r[tcol])
                except (ValueError, KeyError, IndexError):
                    continue
                sid = r[key]
                d = (t - D0) // DAY
                if d < FIRST_DAY or d > LAST_DAY:
                    continue
                slot = int((t - D0 - d * DAY) // slot_s)
                vals = []
                for c in cols:
                    v = r.get(c, "")
                    try:
                        vals.append(round(float(v), 2))
                    except (TypeError, ValueError):
                        vals.append(None)
                out.setdefault(sid, {}).setdefault(str(d), [None] * (DAY // slot_s))[slot] = vals
    return out


def step_gauge():
    s = _slot_series(sorted(glob.glob(os.path.join(SRC, "env_sensors", "gauge_*.csv"))), "ObsDateTime", ["WaterLevel_ft_MLLW", "Residual_ft"], 900, key="SensorID")
    save_cache("sensors:gauge", {"gauge": s})
    return f"{len(s)} gauges"


def step_field():
    wq = _slot_series(sorted(glob.glob(os.path.join(SRC, "env_sensors", "water_quality_*.csv"))), "ObsDateTime", ["TotalHydrocarbons_ppb", "Salinity_psu", "Turbidity_NTU"], 1800, key="SensorID")
    aq = _slot_series(sorted(glob.glob(os.path.join(SRC, "env_sensors", "aqs_air_quality_*.csv"))), None, ["PM25_ugm3", "H2S_ppb", "Benzene_ppb", "TNMHC_ppbC"], 3600, key="SensorID", combine_date=("Date_GMT", "Time_GMT"))
    wx = _slot_series(sorted(glob.glob(os.path.join(SRC, "weather", "K*_ASOS_observations.csv"))), "ObsDateTime", ["DryBulbTemp_C", "WindDir_deg", "WindSpeed_mps", "WindGust_mps", "SeaLevelPressure_mb", "Precip1hr_mm"], 3600, key="StationID")
    by = _slot_series(sorted(glob.glob(os.path.join(SRC, "weather", "BUOY*_observations.csv"))), "ObsDateTime", ["ATMP_C", "WDIR_degT", "WSPD_mps", "GST_mps", "PRES_mb", "WVHT_m"], 3600, key="StationID")
    save_cache("sensors:field", {"wq": wq, "aq": aq, "wx": wx, "buoy": by})
    return f"{len(wq)} sondes, {len(aq)} air monitors, {len(wx)} weather stations, {len(by)} buoys"


def step_outage():
    areas = {}
    with open(os.path.join(SRC, "telemetry", "outage_map.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            t = ptime(r["timestamp_utc"])
            a = areas.setdefault(r["area_id"], {})
            k = t - (t % 3600)
            cur = a.setdefault(k, [0, 0])
            if t % 3600 == 0 or cur == [0, 0]:
                a[k] = [int(r["customers_out"] or 0), int(r["customers_served"] or 0)]
    out = {}
    for area, series in areas.items():
        for k, v in series.items():
            d = (k - D0) // DAY
            out.setdefault(area, {}).setdefault(str(d), [None] * 24)[int((k - D0 - d * DAY) // 3600)] = v
    save_cache("sensors:outage", {"outage": out})
    return f"{len(out)} areas"


# ======================================================================================
# index
# ======================================================================================
def _dp_line(pts, tol_m):
    a = np.array(pts, float)
    x, y = mt.to_xy(a[:, 1], a[:, 0])
    keep = mt.simplify(np.arange(len(a), dtype=float), x, y, tol_m, 1e12)
    return [[e5(p[1]), e5(p[0])] for p, k in zip(pts, keep) if k]     # stored as [lat_e5, lon_e5]; input is lon, lat


def step_index():
    Gx = G()
    idx = {"d0": D0, "first_day": FIRST_DAY, "last_day": LAST_DAY, "built": dt.datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ")}
    terms = load("02_public_record/restricted_terms.json")["terms"]
    never = [t["pattern"] for t in terms if t["public_from_day"] is None]
    never_rx = re.compile("|".join(f"(?:{p})" for p in never), re.I)
    idx["never_public"] = never

    def truth(name):
        try:
            d = load(f"06_data_streams/_internal/{name}_truth.json")
        except FileNotFoundError:
            return {}
        t = d.get("truth") or d.get("hosts") or {}
        return t if isinstance(t, dict) else {}

    # ---- vessels
    vt = truth("vessels")
    ves = {}
    for v in load("06_data_streams/vessels.json")["vessels"]:
        if not v.get("mmsi"):
            continue
        tr = vt.get(v.get("vessel_id"), {})
        role = tr.get("role") if isinstance(tr, dict) else (tr if isinstance(tr, str) else None)
        nm = v.get("vessel_name") or ""
        e = {"n": nm, "c": v.get("class") or "cargo", "sc": v.get("sub_class") or v.get("vessel_type_desc") or "", "len": v.get("length_m") or 0,
             "bm": v.get("beam_m") or 0, "dr": v.get("draft_m") or 0, "fl": v.get("flag") or "", "op": v.get("operator") or "", "id": v.get("vessel_id"),
             "deep": 1 if v.get("deep_draft") else 0, "hp": v.get("home_port") or ""}
        if never_rx.search(nm):
            e["np"] = 1
        if role:
            e["tr"] = role
        ves[str(v["mmsi"])] = e
    idx["vessels"] = ves
    # ---- aircraft
    at = truth("aircraft_registry")
    air = {}
    for a in load("06_data_streams/aircraft_registry.json")["aircraft"]:
        if not a.get("icao24"):
            continue
        td, model = (a.get("type_designator") or ""), (a.get("model") or "")
        role = (a.get("role") or "").lower()
        kind = "heli" if td.startswith("H") or re.search(r"helicopter|jayhawk|black hawk|chinook|lakota|bell|airbus h|ec\d|seahawk|dolphin|uh-|mh-|ch-|as350", model, re.I) else \
            ("uav" if "unmanned" in role or re.search(r"mq-|uav|unmanned", model, re.I) else
             ("heavy" if re.search(r"airlift|cargo|hurricane recon", role) or re.search(r"c-17|c-130|737|a320|757|767|p-3|wp-3", model, re.I) else
              ("airliner" if "passenger" in role else ("trainer" if "training" in role else "light"))))
        tr = at.get(a.get("aircraft_id"), {})
        e = {"cs": a.get("callsign") or "", "reg": a.get("registration") or "", "md": model, "op": a.get("operator") or "", "rl": a.get("role") or "", "k": kind,
             "mil": 1 if a.get("military") else 0, "hb": a.get("home_base") or "", "id": a.get("aircraft_id")}
        r = tr.get("role") if isinstance(tr, dict) else (tr if isinstance(tr, str) else None)
        if r:
            e["tr"] = r
        air[a["icao24"].lower()] = e
    idx["aircraft"] = air
    # ---- response units, stations
    cu = load("06_data_streams/cad_units.json")
    def ukind(t):
        t = t or ""
        if "ambulance" in t or "als" in t or "bls" in t or "medical" in t or "mci" in t: return "ambulance"
        if "bus" in t: return "bus"
        if "boat" in t or "marine" in t or "swiftwater" in t: return "boat"
        if "high_water" in t or "usar" in t: return "highwater"
        if any(k in t for k in ("patrol", "supervisor", "traffic", "detective", "swat", "k9", "lieutenant", "command", "public_info", "evacuation")) and "fire" not in t: return "patrol"
        if any(k in t for k in ("engine", "ladder", "truck", "rescue", "tender", "hazmat", "foam", "battalion", "fire", "welfare")): return "engine"
        return "truck"
    idx["units"] = {u["unit_id"]: {"a": u.get("agency"), "t": u.get("type"), "k": ukind(u.get("type")), "d": u.get("description") or "", "hs": u.get("home_station") or ""} for u in cu["units"]}
    idx["agencies"] = {k: (v.get("name") if isinstance(v, dict) else str(v)) for k, v in cu["agencies"].items()} if isinstance(cu["agencies"], dict) else {}
    idx["natures"] = {n.get("code") or n.get("nature_code"): (n.get("description") or n.get("nature_description") or "") for n in cu["nature_codes"]}
    idx["stations"] = [{"id": s["station_id"], "a": s.get("agency"), "n": s.get("name"), "la": s["latitude"], "lo": s["longitude"]} for s in cu["stations"] if isinstance(s.get("latitude"), (int, float))]
    # ---- drone operators
    dr = load("06_data_streams/drone_operators.json")
    idx["drone_ops"] = {o["operator_id"]: {"n": o.get("org_name"), "t": o.get("org_type")} for o in dr["authorized_operators"]}
    # ---- fixed things
    ft = truth("facility_registry")
    fac = []
    for f in load("06_data_streams/facility_registry.json")["facilities"]:
        if isinstance(f.get("latitude"), (int, float)):
            e = {"id": f["facility_id"], "n": f.get("facility_name"), "t": f.get("facility_type_code") or "", "tt": f.get("facility_type") or "", "la": f["latitude"], "lo": f["longitude"]}
            fac.append(e)
    idx["facilities"] = fac
    it = truth("infrastructure_assets")
    inf = []
    for a in load("06_data_streams/infrastructure_assets.json")["assets"]:
        if isinstance(a.get("latitude"), (int, float)):
            e = {"id": a["asset_id"], "n": a.get("name"), "t": a.get("asset_type") or "", "la": a["latitude"], "lo": a["longitude"], "al": a.get("aliases") or []}
            tr = it.get(a["asset_id"])
            if tr:
                e["tr"] = tr.get("role") if isinstance(tr, dict) else str(tr)
            inf.append(e)
    idx["infrastructure"] = inf
    sr = load("06_data_streams/sensor_registry.json")
    sens = []
    for grp, kind in (("water_quality_sondes", "wq"), ("air_monitors", "aq"), ("tide_gauges", "gauge"), ("stream_gauges", "gauge"), ("weather_stations", "wx"), ("buoys", "buoy"), ("bridge_wind_sensors", "wind")):
        for s in sr.get(grp, []):
            if isinstance(s.get("latitude"), (int, float)):
                sens.append({"id": s.get("sensor_id"), "n": s.get("sensor_name") or s.get("name"), "k": kind, "la": s["latitude"], "lo": s["longitude"], "op": s.get("operator") or "",
                             "st": s.get("station_number") or s.get("station_id") or ""})
    idx["sensors"] = sens
    for fn, key in (("drone_detections/sensor_sites.csv", "det_sensors"), ("port_surveillance/sensors.csv", "port_sensors")):
        rows = []
        with open(os.path.join(SRC, fn), encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["latitude"] and r["longitude"]:
                    rows.append({"id": r["sensor_id"], "n": r["name"], "t": r["sensor_type"], "la": float(r["latitude"]), "lo": float(r["longitude"])})
        idx[key] = rows
    sg = []
    fp = os.path.join(SRC, "drone_detections", "sighting_reports.csv")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["observer_latitude"] and r["observer_longitude"]:
                    sg.append({"id": r["report_id"], "t": ptime(r["time_utc"]), "la": float(r["observer_latitude"]), "lo": float(r["observer_longitude"]),
                               "dir": float(r["direction_deg"]) if r["direction_deg"] else None, "n": r["objects_seen"], "dur": float(r["duration_min"] or 5),
                               "x": r["description"], "by": r["received_by"], "who": r["reporter_type"], "dp": r["disposition"]})
    idx["sightings"] = sorted(sg, key=lambda a: a["t"])
    tr = load("06_data_streams/terminal_registry.json")
    idx["terminals"] = [{"id": t["terminal_id"], "n": t.get("terminal_name"), "t": t.get("terminal_type") or "", "la": t["latitude"], "lo": t["longitude"]} for t in tr["terminals"] if isinstance(t.get("latitude"), (int, float))]
    idx["berths"] = [{"id": b["berth_id"], "la": b["latitude"], "lo": b["longitude"], "h": b.get("heading_deg") or 0} for b in tr["berths"]]
    idx["anchorage"] = [{"id": p.get("position_id"), "la": p["latitude"], "lo": p["longitude"]} for p in tr.get("anchorage_positions", [])]
    idx["airfields"] = [{"id": a.get("airfield_id") or a.get("id") or a.get("lid"), "n": a.get("name"), "la": a.get("latitude"), "lo": a.get("longitude")}
                        for a in load("06_data_streams/aircraft_registry.json").get("airfields", []) if isinstance(a.get("latitude"), (int, float))]
    # ---- areas (reference points and boxes) for outages and event placement
    areas = load("06_data_streams/areas.json")["areas"]
    A = {}
    for a in areas:
        rp = a.get("reference_point") or {}
        if isinstance(rp.get("latitude"), (int, float)):
            A[a["area_id"]] = {"n": a.get("name"), "t": a.get("area_type"), "la": rp["latitude"], "lo": rp["longitude"], "bb": a.get("bbox")}
    idx["areas"] = {k: v for k, v in A.items() if v["t"] in ("neighbourhood", "water_district", "water_district_group", "evacuation_zone", "county", "city", "pressure_zone")}
    # ---- shelters
    sh = {}
    with open(os.path.join(SRC, "shelters", "shelter_daily_census.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            d = (dt.date.fromisoformat(r["date_local"]) - dt.date(2027, 9, 14)).days
            sh.setdefault(r["facility_id"], {"n": r["facility_name"], "cap": int(r["capacity"] or 0), "d": {}})["d"][str(d)] = [int(r["occupancy"] or 0), r["status"], int(r["spanish_speaking_pct"] or 0)]
    facpos = {f["id"]: f for f in fac}
    for k, v in sh.items():
        if k in facpos:
            v["la"], v["lo"] = facpos[k]["la"], facpos[k]["lo"]
    idx["shelters"] = {k: v for k, v in sh.items() if "la" in v}
    # ---- alerts, port conditions
    al = []
    with open(os.path.join(SRC, "public_health", "eas_broadcasts.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["AlertType"] == "RequiredWeeklyTest":
                continue
            al.append({"id": r["AlertID"], "ty": r["AlertType"], "t": ptime(r["IssuedAt_UTC"]), "en": ptime(r["ReleasedAt_EN"]) if r["ReleasedAt_EN"] else None,
                       "es": ptime(r["ReleasedAt_ES"]) if r["ReleasedAt_ES"] else None, "x": ptime(r["ExpiresAt_UTC"]) if r["ExpiresAt_UTC"] else None,
                       "h": r["Headline_EN"], "hs": r["Headline_ES"], "ar": r["GeographicArea"], "pr": r["Priority"]})
    idx["alerts"] = sorted(al, key=lambda a: a["t"])
    pc = []
    with open(os.path.join(SRC, "supply", "port_conditions.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            pc.append({"t": ptime(r["effective_utc"]), "seg": r["segment_id"], "sn": r["segment_name"], "st": r["status"], "pc": r["port_condition"], "o": r["order_id"], "tx": r["text"][:220]})
    idx["port"] = sorted(pc, key=lambda a: a["t"])
    # ---- SAR missions, damage
    sar = []
    with open(os.path.join(SRC, "sar", "sar_missions.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            sar.append([ptime(r["launch_utc"]), ptime(r["on_scene_utc"]), ptime(r["recovery_utc"]), e5(r["latitude"]), e5(r["longitude"]), r["asset_id"], r["asset_type"], r["method"],
                        int(r["persons"] or 0), r["outcome"], r["agency"]])
    idx["sar"] = sorted(sar)
    dmg, lv = [], ["AFF", "MIN", "MAJ", "DES", "INA", "NVD"]
    with open(os.path.join(SRC, "infrastructure", "damage_assessment.csv"), encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            try:
                t = local_to_epoch(r["ASMT_DATE"])
            except Exception:
                continue
            if r["DMG_LEVEL"] not in lv:
                lv.append(r["DMG_LEVEL"])
            dmg += [t, e5(r["LATITUDE"]), e5(r["LONGITUDE"]), lv.index(r["DMG_LEVEL"])]
    order = np.argsort(np.array(dmg[0::4]), kind="stable")
    idx["damage"] = [x for i in order for x in dmg[i * 4:i * 4 + 4]]
    idx["damage_levels"] = lv
    # ---- storm
    try:
        import envmodel
        env = envmodel.Env()
        idx["storm_track"] = [[round(a, 2), round(b, 3), round(c, 3), round(d, 1), round(p, 1)] for a, b, c, d, p in env.trk]
    except Exception as ex:                                   # fall back to the track file without pressures
        idx["storm_track"] = [[p["t"], p["lat"], p["lon"], p["wind_kt"], 1008.0] for p in sorted(load("09_shared_state_timeline/data/storm_track.json"), key=lambda p: p["t"])]
        idx["storm_note"] = f"pressures unavailable ({ex})"
    idx["landfall"] = D0 + 6 * 3600
    # ---- events
    canon = load("00_scenario/canon_timeline.json")
    obs_t = {}
    for o in canon.get("expected_observations", {}).get("items", []):
        try:
            t = ptime(o["start_utc"])
        except Exception:
            continue
        obs_t[o["event_id"]] = min(t, obs_t.get(o["event_id"], t))
    place = {}
    for k, v in A.items():
        place[k] = (v["la"], v["lo"], v["n"], v["t"])
    for f in fac:
        place[f["id"]] = (f["la"], f["lo"], f["n"], "facility")
    for a in inf:
        place[a["id"]] = (a["la"], a["lo"], a["n"], "infrastructure")
        for alias in a["al"]:
            place.setdefault(alias, (a["la"], a["lo"], a["n"], "infrastructure"))
    for f in load("06_data_streams/facility_registry.json")["facilities"]:
        for alias in f.get("aliases") or []:
            if isinstance(f.get("latitude"), (int, float)):
                place.setdefault(alias, (f["latitude"], f["longitude"], f.get("facility_name"), "facility"))
    for f in load("06_data_streams/facility_registry.json").get("out_of_area", []):
        if isinstance(f.get("latitude"), (int, float)):
            place[f.get("facility_id")] = (f["latitude"], f["longitude"], f.get("facility_name"), "facility")
            for alias in f.get("aliases") or []:
                place.setdefault(alias, (f["latitude"], f["longitude"], f.get("facility_name"), "facility"))
    for t in idx["terminals"]:
        place[t["id"]] = (t["la"], t["lo"], t["n"], "terminal")
    for s in sens:
        place[s["id"]] = (s["la"], s["lo"], s["n"], "sensor")
    anc = idx["anchorage"]
    if anc:
        place["ANC-OFF"] = (sum(p["la"] for p in anc) / len(anc), sum(p["lo"] for p in anc) / len(anc), "Offshore anchorage", "anchorage")
    jet = next((it for it in Gx.channels.items if it["props"]["reach_id"].startswith("CESWG_CC_02")), None)
    if jet is not None:
        c = jet["xy"][:-1].mean(axis=0)
        place["ENT-01"] = (float(c[1]), float(c[0]), "Aransas Pass entrance channel", "channel")
    mtb = next((it for it in Gx.channels.items if it["props"]["reach_id"].startswith("CESWG_CC_08")), None)
    if mtb is not None:
        c = mtb["xy"][:-1].mean(axis=0)
        place["PORT-07"] = (float(c[1]), float(c[0]), "Port of Corpus Christi, Inner Harbor", "port")
    lf = (canon.get("storm", {}).get("landfall", {}).get("track_point") or {})
    if isinstance(lf.get("lat"), (int, float)):
        place["LF-01"] = (lf["lat"], lf["lon"], "Landfall, Mustang Island", "landfall")
    for alias, target in (("FAC-HOS-xx", "FAC-SRMC-001"), ("WQ-01 to WQ-06", "WQ-01"), ("HOST-VSL-01", "TERM-01")):
        if target in place:
            place.setdefault(alias, place[target])
    ww = next((a for a in inf if a["t"] == "wastewater_treatment_plant"), None)
    if ww:
        place.setdefault("WW-xx", (ww["la"], ww["lo"], ww["n"], "infrastructure"))
    ops = next((a for a in inf if a["t"] == "operations_center"), None)
    # gazetteer for descriptions (longest names first)
    gaz = sorted([(v[2], k) for k, v in place.items() if v[2] and len(v[2]) >= 7 and v[3] not in ("county", "city")], key=lambda x: -len(x[0]))
    wide = {"county", "city", "water_district_group", "evacuation_zone"}

    def locate(place_ids, text):
        specific = [p for p in place_ids if p in place and place[p][3] not in wide]
        if specific:
            return specific[0], False
        low = text.lower()
        for name, pid in gaz:
            if name.lower() in low:
                return pid, False
        if ops and re.search(r"GW-(SYS|WS|SRV|ENG)|SIEM|historian|SCADA", text):
            place["_ops"] = (ops["la"], ops["lo"], ops["n"], "infrastructure")
            return "_ops", False
        for p in place_ids:
            if p in place:
                return p, True
        return None, True

    events = []
    msel = load("00_scenario/msel.json")
    msel = msel if isinstance(msel, list) else msel.get("events", [])
    try:
        gm = load("scenarios/gridwater/00_scenario/msel.json")
        gm = gm if isinstance(gm, list) else gm.get("events", [])
    except FileNotFoundError:
        gm = []
    seen = set()
    for e in list(msel) + list(gm):
        if e["event_id"] in seen:
            continue
        seen.add(e["event_id"])
        t = obs_t.get(e["event_id"])
        if t is None:
            if e.get("time_utc") and re.match(r"\d\d:\d\d", str(e["time_utc"])):
                hh, mm = int(e["time_utc"][:2]), int(e["time_utc"][3:5])
                t = D0 + e["day"] * DAY + hh * 3600 + mm * 60
                if hh < 5:
                    t += 0                                   # early-UTC times already belong to the stated day in the MSEL
            else:
                t = D0 + e["day"] * DAY + 17 * 3600          # local noon
        t1 = D0 + (e.get("day_end") or e["day"]) * DAY + 29 * 3600 if e.get("day_end") else None
        pid, area_wide = locate(e.get("place_ids") or [], e.get("description") or "")
        lanes = [str(x)[:1].upper() for x in (e.get("lanes") or [])]
        ev = {"id": e["event_id"], "k": "m", "t": int(t), "d": e["day"], "th": e.get("threads") or [], "ln": lanes, "x": e.get("description") or "", "ob": 1 if e.get("observable", True) else 0}
        if t1:
            ev["t1"] = int(t1)
        if pid:
            ev.update(la=round(place[pid][0], 5), lo=round(place[pid][1], 5), pn=place[pid][2], aw=1 if area_wide else 0)
        events.append(ev)
    facts = load("02_public_record/public_record.json")["facts"]
    try:
        facts = facts + load("scenarios/gridwater/02_public_record/public_record.json").get("facts", [])
    except Exception:
        pass
    seen = set()
    for f in facts:
        if f["id"] in seen:
            continue
        seen.add(f["id"])
        hm = f.get("time_local") if re.match(r"\d\d:\d\d", str(f.get("time_local") or "")) else "09:00"
        day = dt.date(2027, 9, 14) + dt.timedelta(days=f["day"])
        t = local_to_epoch(f"{day.isoformat()} {hm}")
        pid, area_wide = locate((f.get("places") or []) + (f.get("public_places") or []), f.get("statement") or "")
        ev = {"id": f["id"], "k": "f", "t": int(t), "d": f["day"], "th": f.get("threads") or [], "ty": f.get("type") or "", "x": (f.get("statement") or "")[:600], "ev": f.get("events") or []}
        if pid:
            ev.update(la=round(place[pid][0], 5), lo=round(place[pid][1], 5), pn=place[pid][2], aw=1 if area_wide else 0)
        events.append(ev)
    events.sort(key=lambda e: e["t"])
    idx["events"] = events
    thr = load("00_scenario/threads.json")
    idx["threads"] = {t["thread_id"]: t["name"] for t in thr}
    try:
        ms = load("10_news_sites/newsroom/data/milestones.json")
        idx["milestones"] = [{"t": m["ts"], "l": m["label"]} for m in ms]
    except Exception:
        idx["milestones"] = []
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index.js"), "w", encoding="utf-8") as fh:
        fh.write("window.RAFAEL_MAP=window.RAFAEL_MAP||{days:{}};window.RAFAEL_MAP.index=")
        json.dump(idx, fh, separators=(",", ":"), ensure_ascii=False)
        fh.write(";\n")
    # ---- reference outlines for the offline basemap
    ref = {"land": [], "channels": [], "anchorages": [], "roads": [], "box": list(geo.BOX)}
    for it in Gx.land.items:
        xy = it["xy"]
        if len(xy) < 4:
            continue
        w = (xy[:, 0].max() - xy[:, 0].min()) * geo.M_PER_DEG_LON; hgt = (xy[:, 1].max() - xy[:, 1].min()) * geo.M_PER_DEG_LAT
        if max(w, hgt) < 120:
            continue
        ring = _dp_line([(float(p[0]), float(p[1])) for p in xy], 25.0)
        if len(ring) >= 4:
            ref["land"].append(ring)
    ref["water"] = [_dp_line([(float(p[0]), float(p[1])) for p in it["xy"]], 25.0) for it in Gx.water_override.items]
    for it in Gx.channels.items:
        ref["channels"].append({"id": it["props"]["reach_id"], "n": it["props"].get("description") or "", "d": it["props"].get("depth_ft") or 0,
                                "r": [[e5(p[1]), e5(p[0])] for p in it["xy"]]})
    for it in Gx.anchorages.items:
        ref["anchorages"].append([[e5(p[1]), e5(p[0])] for p in it["xy"]])
    for name, cls, pts in Gx.roads.features:
        if cls in ("primary", "secondary", "arterial"):
            line = _dp_line([(p[1], p[0]) for p in pts], 12.0)
            if len(line) >= 2:
                ref["roads"].append({"c": cls[0], "n": name, "l": line})
        else:
            # every local street, so that a vehicle on a side street is on a drawn street in the offline chart
            line = _dp_line([(p[1], p[0]) for p in pts], 6.0)
            if len(line) >= 2:
                ref["roads"].append({"c": "l", "l": line})
    coarse = []
    for it in Gx.land_coarse.items:
        if len(it["xy"]) >= 4:
            coarse.append([[e5(p[1]), e5(p[0])] for p in it["xy"][::2]] if len(it["xy"]) > 400 else [[e5(p[1]), e5(p[0])] for p in it["xy"]])
    ref["coarse"] = coarse
    with open(os.path.join(OUT, "reference.js"), "w", encoding="utf-8") as fh:
        fh.write("window.RAFAEL_MAP=window.RAFAEL_MAP||{days:{}};window.RAFAEL_MAP.ref=")
        json.dump(ref, fh, separators=(",", ":"), ensure_ascii=False)
        fh.write(";\n")
    return (f"index.js {os.path.getsize(os.path.join(OUT, 'index.js')) / 1e6:.1f} MB ({len(ves)} vessels, {len(air)} aircraft, {len(idx['units'])} units, {len(events)} events, "
            f"{sum(1 for e in events if 'la' in e)} placed); reference.js {os.path.getsize(os.path.join(OUT, 'reference.js')) / 1e6:.1f} MB")


# ======================================================================================
# assemble
# ======================================================================================
def _all(prefix, key, names=MONTHS):
    out = []
    for m in names:
        p = cache_path(f"{prefix}:{m}")
        if os.path.exists(p):
            out.append(read_cache(f"{prefix}:{m}")[key])
    return out


def _merge_assets(month_dicts, width, join_gap, checker=None, hold=False):
    """{asset: {"parts": [np.array(n, width)], ...}} across months, joining parts over a month boundary."""
    out = {}
    for md in month_dicts:
        for aid, a in md.items():
            o = out.setdefault(aid, {"parts": [], "st": [], "hd": [], "meta": {k: v for k, v in a.items() if k not in ("p", "st", "hd")}})
            parts = [np.array(p, dtype=np.int64).reshape(-1, width) for p in a["p"] if p]
            if parts and o["parts"]:
                last, first = o["parts"][-1], parts[0]
                gap = first[0, 0] - last[-1, 0]
                moved = abs(first[0, 1] - last[-1, 1]) + abs(first[0, 2] - last[-1, 2]) > 40
                ok = gap >= 0 and (not moved or (gap <= join_gap and (checker is None or checker(last[-1, 1] / 1e5, last[-1, 2] / 1e5, first[0, 1] / 1e5, first[0, 2] / 1e5))))
                if ok:
                    o["parts"][-1] = np.vstack([last, first])
                    parts = parts[1:]
                elif hold and 0 <= gap <= join_gap:
                    # same unit a few minutes later somewhere else, and no clear road line between the two fixes:
                    # hold at the earlier fix and step to the next one
                    mid = None
                    if width == 3 and gap >= 1:
                        # the files are cut at local midnight on the first of the month: route across the cut like any other gap
                        vs, _kind = match_gap(matcher(), (last[-1, 1] / 1e5, last[-1, 2] / 1e5), (first[0, 1] / 1e5, first[0, 2] / 1e5), int(last[-1, 0]), int(first[0, 0]))
                        if vs is not None:
                            tp = int(last[-1, 0]); rows_ = []
                            for tv, (la_, lo_) in vs:
                                tp = min(max(int(tv), tp), int(first[0, 0]))
                                rows_.append((tp, e5(la_), e5(lo_)))
                            mid = np.array(rows_, dtype=np.int64).reshape(-1, 3)
                    if mid is None:
                        mid = last[-1].copy()[None, :]; mid[0, 0] = first[0, 0] - 1
                    o["parts"][-1] = np.vstack([last, mid, first])
                    parts = parts[1:]
            o["parts"] += parts
            if "st" in a:
                o["st"] += a["st"]
            if "hd" in a:
                o["hd"] += a["hd"]
    return out


def _day_parts(parts, ds, de):
    out = []
    for p in parts:
        if p[-1, 0] < ds or p[0, 0] >= de:
            continue
        t = p[:, 0]
        i0 = max(0, int(np.searchsorted(t, ds, side="right")) - 1)
        i1 = min(len(t) - 1, int(np.searchsorted(t, de, side="left")))
        seg = p[i0:i1 + 1].copy()
        seg[:, 0] -= ds
        out.append(_delta(seg))
    return out


def _delta(seg):
    """First vertex absolute, the rest as differences (the viewer and check_map undo this)."""
    d = seg.copy()
    d[1:] = seg[1:] - seg[:-1]
    return d.ravel().tolist()


def _day_changes(flat, ds, de, width=2):
    """Changes list [t, v, ...] -> state at day start plus changes inside the day (t relative)."""
    if not flat:
        return []
    n = len(flat) // width
    ts_ = flat[0::width]
    i = int(np.searchsorted(ts_, ds, side="right")) - 1
    out = []
    if i >= 0:
        out += [0] + flat[i * width + 1:(i + 1) * width]
    j = i + 1
    while j < n and ts_[j] < de:
        out += [ts_[j] - ds] + flat[j * width + 1:(j + 1) * width]
        j += 1
    return out


def step_assemble(month):
    W = mt.WaterCheck(G())
    RC = mt.RoadCheck(G(), 30.0)
    ves = _merge_assets([d for d in _all("tracks:ais", "assets")], 3, 35 * 60, W.clear)
    air = _merge_assets([d for d in _all("tracks:adsb", "assets")], 4, 5 * 60)
    avl_files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SRC, "avl", "avl_*.csv")))
    by_unit = {}
    for f in avl_files:
        p = cache_path(f"tracks:avl:{f}")
        if os.path.exists(p):
            by_unit.setdefault(f.split("_")[2], []).append(read_cache(f"tracks:avl:{f}")["assets"])
    veh = {}
    for agency, lst in by_unit.items():
        for a in lst:
            for u in a.values():
                u["st2"] = u.pop("st")
        m = _merge_assets(lst, 3, 8 * 60, RC.clear, hold=True)
        for a in lst:
            for uid, u in a.items():
                m[uid].setdefault("stc", []).extend(u["st2"])
        veh.update(m)
    drones = [f for lst in _all("tracks:drone", "flights") for f in lst]
    dets = [f for lst in _all("tracks:det", "tracks") for f in lst]
    radar = [f for lst in _all("tracks:radar", "tracks") for f in lst]
    inc = {}
    for dd in _all("points:911", "days"):
        for k, v in dd.items():
            inc.setdefault(int(k), []).extend(v)
    gauge = read_cache("sensors:gauge")["gauge"] if os.path.exists(cache_path("sensors:gauge")) else {}
    field = read_cache("sensors:field") if os.path.exists(cache_path("sensors:field")) else {}
    outage = read_cache("sensors:outage")["outage"] if os.path.exists(cache_path("sensors:outage")) else {}
    y, mth = int(month[:4]), int(month[5:7])
    stats = {}
    os.makedirs(OUT, exist_ok=True)
    for d in range(FIRST_DAY, LAST_DAY + 1):
        ds = D0 + d * DAY
        when = dt.datetime.fromtimestamp(ds, UTC)
        if (when.year, when.month) != (y, mth):
            continue
        de = ds + DAY
        day = {"n": d, "v": {}, "vs": {}, "vh": {}, "a": {}, "an": {}, "c": {}, "cs": {}, "d": [], "x": [], "r": [], "i": [], "s": {}, "o": {}}
        nv = 0
        for aid, a in ves.items():
            p = _day_parts(a["parts"], ds, de)
            if p:
                day["v"][aid] = p
                nv += sum(len(x) for x in p) // 3
                st = _day_changes(a["st"], ds, de)
                if st:
                    day["vs"][aid] = st
                hd = _day_changes(a["hd"], ds, de)
                if hd:
                    day["vh"][aid] = hd
        na = 0
        for aid, a in air.items():
            p = _day_parts(a["parts"], ds, de)
            if p:
                day["a"][aid] = p
                na += sum(len(x) for x in p) // 4
                ni = a["meta"].get("ni") or []
                iv = [x - ds for k in range(0, len(ni), 2) if ni[k + 1] >= ds and ni[k] < de for x in (ni[k], ni[k + 1])]
                if iv:
                    day["an"][aid] = iv
        nc = 0
        for uid, a in veh.items():
            p = _day_parts(a["parts"], ds, de)
            if p:
                day["c"][uid] = p
                nc += sum(len(x) for x in p) // 3
                sc = sorted(a.get("stc", []), key=lambda r: r[0])
                tt = [r[0] for r in sc]
                i = int(np.searchsorted(tt, ds, side="right")) - 1
                cs = []
                if i >= 0:
                    cs += [0, sc[i][1], sc[i][2]]
                j = i + 1
                while j < len(sc) and sc[j][0] < de:
                    cs += [sc[j][0] - ds, sc[j][1], sc[j][2]]
                    j += 1
                day["cs"][uid] = cs
        for f in drones:
            p = np.array(f["p"], dtype=np.int64).reshape(-1, 4)
            if p[-1, 0] >= ds and p[0, 0] < de:
                q = p.copy(); q[:, 0] -= ds
                day["d"].append({"id": f["id"], "op": f["op"], "md": f["md"], "ms": f["ms"], "p": _delta(q)})
        for f in dets:
            p = np.array(f["p"], dtype=np.int64).reshape(-1, 4)
            if p[0, 0] >= ds and p[0, 0] < de:
                q = p.copy(); q[:, 0] -= ds
                day["x"].append({"id": f["id"], "s": f["s"], "k": f["k"], "c": f["c"], "al": f["al"], "au": f["au"], "p": _delta(q)})
        for f in radar:
            parts = [np.array(p, dtype=np.int64).reshape(-1, 3) for p in f["p"] if p]
            pp = _day_parts(parts, ds, de)
            if pp:
                day["r"].append({"id": f["id"], "s": f["s"], "sz": f["sz"], "len": f["len"], "p": pp})
        rows = sorted(inc.get(d, []), key=lambda r: r[0])
        # incidents received earlier but still open at the start of the day
        carry = [r for r in inc.get(d - 1, []) if r[1] > ds]
        day["i"] = [[r[0] - ds, r[1] - ds] + r[2:] for r in carry + rows]
        day["s"] = {"gauge": {k: v[str(d)] for k, v in gauge.items() if str(d) in v}}
        for grp in ("wq", "aq", "wx", "buoy"):
            day["s"][grp] = {k: v[str(d)] for k, v in field.get(grp, {}).items() if str(d) in v}
        day["o"] = {k: v[str(d)] for k, v in outage.items() if str(d) in v}
        name = f"day_{'m' if d < 0 else 'p'}{abs(d):03d}.js"
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(f"window.RAFAEL_MAP=window.RAFAEL_MAP||{{days:{{}}}};window.RAFAEL_MAP.days[{d}]=")
            json.dump(day, fh, separators=(",", ":"), ensure_ascii=False)
            fh.write(f";window.RAFAEL_MAP.onDay&&window.RAFAEL_MAP.onDay({d});\n")
        stats[str(d)] = {"v": len(day["v"]), "a": len(day["a"]), "c": len(day["c"]), "i": len(rows), "d": len(day["d"]), "x": len(day["x"]),
                         "vx": nv + na + nc, "kb": os.path.getsize(os.path.join(OUT, name)) // 1024}
    save_cache(f"assemble:{month}", {"stats": stats})
    kb = sum(s["kb"] for s in stats.values())
    return f"{len(stats)} day files, {kb / 1024:.1f} MB"


def step_summary():
    stats = {}
    for m in MONTHS:
        stats.update(read_cache(f"assemble:{m}")["stats"])
    with open(os.path.join(OUT, "summary.js"), "w", encoding="utf-8") as fh:
        fh.write("window.RAFAEL_MAP=window.RAFAEL_MAP||{days:{}};window.RAFAEL_MAP.summary=")
        json.dump(stats, fh, separators=(",", ":"))
        fh.write(";\n")
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, "*.js")))
    return f"{len(stats)} days; map_data is {total / 1e6:.1f} MB"


# ======================================================================================
def steps():
    out = []
    for m in MONTHS:
        out += [(f"tracks:ais:{m}", lambda m=m: step_ais(m)), (f"tracks:adsb:{m}", lambda m=m: step_adsb(m)), (f"tracks:drone:{m}", lambda m=m: step_drone(m)),
                (f"tracks:det:{m}", lambda m=m: step_det(m)), (f"tracks:radar:{m}", lambda m=m: step_radar(m)), (f"points:911:{m}", lambda m=m: step_911(m))]
    for f in sorted(os.path.basename(p) for p in glob.glob(os.path.join(SRC, "avl", "avl_*.csv"))):
        out.append((f"tracks:avl:{f}", lambda f=f: step_avl(f)))
    out += [("sensors:gauge", step_gauge), ("sensors:field", step_field), ("sensors:outage", step_outage), ("index", step_index)]
    out += [(f"assemble:{m}", lambda m=m: step_assemble(m)) for m in MONTHS]
    out.append(("summary", step_summary))
    return out


# ---------------------------------------------------------------- stale-input detection
GEO = os.path.join(ROOT, "99_reference", "geo")
CODE = {"ais": 1, "adsb": 1, "avl": 4, "drone": 1, "det": 1, "radar": 1, "911": 1, "gauge": 1, "field": 1, "outage": 1, "index": 2, "assemble": 3, "summary": 1}
# bump a number above when that step's logic changes; the step is then redone on the next run


def step_inputs(name):
    """Every file a step reads. A step is redone when one of them changes (size or modification
    time), when its entry in CODE changes, or when its cache is missing."""
    g = lambda *parts: sorted(glob.glob(os.path.join(*parts)))
    kind = name.split(":")
    land = [os.path.join(GEO, f) for f in ("land_local.geojson", "water_overrides_local.geojson", "land_gulf_coarse.geojson")]
    roads = g(GEO, "roads_*.geojson")
    if name.startswith("tracks:ais:"):
        return [os.path.join(SRC, "ais", f"ais_{kind[2]}.csv")] + land
    if name.startswith("tracks:adsb:"):
        return [os.path.join(SRC, "adsb", f"adsb_{kind[2]}.csv")]
    if name.startswith("tracks:avl:"):
        return [os.path.join(SRC, "avl", name.split(":", 2)[2])] + roads
    if name.startswith("tracks:drone:"):
        return g(SRC, "drone_video", f"drone_telemetry_{kind[2]}*.csv")
    if name.startswith("tracks:det:"):
        return [os.path.join(SRC, "drone_detections", f"detections_{kind[2]}.csv")]
    if name.startswith("tracks:radar:"):
        return [os.path.join(SRC, "port_surveillance", f"radar_tracks_{kind[2]}.csv")]
    if name.startswith("points:911:"):
        return [os.path.join(SRC, "911", f"cad_incidents_{kind[2]}.csv")]
    if name == "sensors:gauge":
        return g(SRC, "env_sensors", "gauge_*.csv")
    if name == "sensors:field":
        return g(SRC, "env_sensors", "water_quality_*.csv") + g(SRC, "env_sensors", "aqs_air_quality_*.csv") + g(SRC, "weather", "K*_ASOS_observations.csv") + g(SRC, "weather", "BUOY*_observations.csv")
    if name == "sensors:outage":
        return [os.path.join(SRC, "telemetry", "outage_map.csv")]
    if name == "index":
        return (g(ROOT, "06_data_streams", "*.json") + g(ROOT, "06_data_streams", "_internal", "*_truth.json") + g(GEO, "*.geojson")
                + [os.path.join(ROOT, r) for r in ("02_public_record/restricted_terms.json", "02_public_record/public_record.json", "00_scenario/canon_timeline.json",
                                                   "00_scenario/msel.json", "00_scenario/threads.json", "scenarios/gridwater/00_scenario/msel.json",
                                                   "scenarios/gridwater/02_public_record/public_record.json", "09_shared_state_timeline/data/storm_track.json",
                                                   "10_news_sites/newsroom/data/milestones.json")]
                + [os.path.join(SRC, r) for r in ("shelters/shelter_daily_census.csv", "public_health/eas_broadcasts.csv", "supply/port_conditions.csv", "sar/sar_missions.csv",
                                                  "infrastructure/damage_assessment.csv", "drone_detections/sighting_reports.csv")]
                + g(SRC, "port_surveillance", "sensors*.csv") + g(SRC, "drone_detections", "sensor*.csv"))
    if name.startswith("assemble:"):
        return g(CACHE, "tracks__*.json") + g(CACHE, "points__*.json") + g(CACHE, "sensors__*.json") + [os.path.join(CACHE, "index.done")]
    if name == "summary":
        return g(CACHE, "assemble__*.json")
    return []


def signature(name):
    import hashlib
    kind = name.split(":")[1] if name.split(":")[0] in ("tracks", "points", "sensors") else name.split(":")[0]
    h = hashlib.sha1(f"code={CODE.get(kind, 0)}".encode())
    for fp in step_inputs(name):
        if os.path.exists(fp):
            st = os.stat(fp)
            h.update(f"|{os.path.relpath(fp, ROOT)}:{st.st_size}:{int(st.st_mtime)}".encode())
        else:
            h.update(f"|{os.path.relpath(fp, ROOT)}:missing".encode())
    return h.hexdigest()


def sig_path(name):
    return os.path.join(CACHE, name.replace(":", "__").replace("/", "_") + ".sig")


def is_done(name):
    have = os.path.exists(cache_path(name)) or (name in ("index", "summary") and os.path.exists(os.path.join(CACHE, name + ".done")))
    if not have or not os.path.exists(sig_path(name)):
        return False
    return open(sig_path(name)).read().strip() == signature(name)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    budget = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--budget=")), 140.0)
    all_steps = steps()
    names = [n for n, _ in all_steps]
    if args[:1] == ["status"]:
        for n in names:
            print(("done  " if is_done(n) else ("STALE " if os.path.exists(cache_path(n)) or os.path.exists(os.path.join(CACHE, n + ".done")) else "TODO  ")) + n)
        return
    if args[:1] == ["step"]:
        todo = [(n, f) for n, f in all_steps if n in args[1:] or any(n.startswith(a) for a in args[1:])]
    else:
        todo = [(n, f) for n, f in all_steps]
    t0 = time.time()
    ran = 0
    for n, f in todo:
        # checked just before running, because earlier steps in this run change the inputs of later ones
        if args[:1] != ["step"] and not force and is_done(n):
            continue
        if time.time() - t0 > budget:
            print(f"INCOMPLETE: {sum(1 for x in names if not is_done(x))} steps left; run again with --resume")
            sys.exit(2)
        t1 = time.time()
        sig = signature(n)
        msg = f()
        if n in ("index", "summary"):
            os.makedirs(CACHE, exist_ok=True)
            open(os.path.join(CACHE, n + ".done"), "w").write(msg)
        if n == "index":
            sig = signature(n)
        open(sig_path(n), "w").write(sig)
        ran += 1
        print(f"{n:<40} {time.time() - t1:5.1f}s  {msg}", flush=True)
    left = [x for x in names if not is_done(x)]
    print(("COMPLETE" + ("" if ran else " (nothing to do: every step is up to date)")) if not left else f"INCOMPLETE: {len(left)} steps left")


if __name__ == "__main__":
    main()
