"""Shared helpers for every stream generator in scripts/streams/.

Generators are deterministic: same inputs, same bytes. They read only
  00_scenario/canon_timeline.json      what happened and when (the truth)
  06_data_streams/*.json               entity registries (ids, names, positions)
  06_data_streams/_internal/*.json     internal notes and old-id maps (never copied into output)
  06_data_streams/stream_catalog.json  where each stream lives, its columns and span
  99_reference/geo via scripts/geo.py  real geography
and write only their own stream's files under 05_other_sources/.

    from common import *        # clock helpers, loaders, rng, storm model, writers
"""
import csv
import datetime as dt
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

D0_EPOCH = 1820880000                       # 2027-09-14T00:00:00Z
LANDFALL = D0_EPOCH + 6 * 3600              # 2027-09-14T06:00Z = 01:00 CDT
DST_END = 1825570800                        # 2027-11-07T07:00Z; CDT before, CST after
SPAN_START = D0_EPOCH - 30 * 86400          # 2027-08-15T00:00Z (D-30)
SPAN_END = D0_EPOCH + 120 * 86400 + 6 * 3600  # 2028-01-12T06:00Z (end of local D+119)
UTC = dt.timezone.utc


# ---------------------------------------------------------------- clock
def utc_offset(ts):
    return -5 if ts < DST_END else -6


def ts(iso):
    """Epoch seconds from an ISO string ('2027-09-14T06:00Z', with or without seconds/offset)."""
    s = iso.strip().replace("Z", "+00:00")
    if len(s) == 16:
        s += "+00:00"
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return int(d.timestamp())


def iso(t, sep="T", z=True, seconds=True):
    d = dt.datetime.fromtimestamp(int(t), UTC)
    s = d.strftime(f"%Y-%m-%d{sep}%H:%M:%S" if seconds else f"%Y-%m-%d{sep}%H:%M")
    return s + ("Z" if z else "")


def local_dt(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone(dt.timedelta(hours=utc_offset(t))))


def local_iso(t, sep=" "):
    return local_dt(t).strftime(f"%Y-%m-%d{sep}%H:%M:%S")


def day_of(t):
    """Scenario day (local calendar days from landfall day) of an epoch."""
    return (local_dt(t).date() - dt.date(2027, 9, 14)).days


def local_ts(day, hhmm="00:00"):
    """Epoch of a local wall-clock time on a scenario day: local_ts(12, '17:30')."""
    d = dt.date(2027, 9, 14) + dt.timedelta(days=day)
    h, m = map(int, hhmm.split(":"))
    naive = dt.datetime(d.year, d.month, d.day, h, m, tzinfo=UTC).timestamp()
    off = utc_offset(naive + 6 * 3600)
    return int(naive - off * 3600)


def d_label(t):
    l = local_dt(t)
    n = day_of(t)
    return f"D{'+' if n >= 0 else '-'}{abs(n)} {l:%H:%M}"


# ---------------------------------------------------------------- loaders
_cache = {}


def load_json(rel):
    if rel not in _cache:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            _cache[rel] = json.load(fh)
    return _cache[rel]


def canon():
    return load_json("00_scenario/canon_timeline.json")


def reg(name):
    """Participant-facing registry, e.g. reg('vessels')['vessels']."""
    return load_json(f"06_data_streams/{name}.json")


def internal(name):
    """Internal notes for a registry (truth, id_migration). Never copy text from here into output."""
    return load_json(f"06_data_streams/_internal/{name}_truth.json")


def catalog(stream_id):
    for s in load_json("06_data_streams/stream_catalog.json")["streams"]:
        if s["stream_id"] == stream_id:
            return s
    raise KeyError(stream_id)


def expected(stream_id):
    """Expected observations (event id, what, start_utc, end_utc) this stream must contain."""
    return [e for e in canon()["expected_observations"]["items"] if e["stream"] == stream_id]


def geo_handle(build_roads=True):
    import geo
    if "geo" not in _cache:
        _cache["geo"] = geo.Geo(build_roads=build_roads)
    return _cache["geo"]


# ---------------------------------------------------------------- randomness
def rng(*keys):
    """Deterministic generator for a stream and any sub-keys: rng('ais', mmsi)."""
    h = hashlib.sha256("|".join(str(k) for k in keys).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


# ---------------------------------------------------------------- storm model
def _track():
    if "track" not in _cache:
        pts = load_json("09_shared_state_timeline/data/storm_track.json")
        _cache["track"] = sorted(pts, key=lambda p: p["t"])
    return _cache["track"]


def storm_center(t):
    """(lat, lon, vmax_kt) of Rafael at epoch t, or None outside the track. Track hours are
    relative to D0 00:00Z; landfall is forced to 06:00Z at the canon landfall point."""
    pts = _track()
    h = (t - D0_EPOCH) / 3600.0
    if h < pts[0]["t"] or h > pts[-1]["t"]:
        return None
    for a, b in zip(pts, pts[1:]):
        if a["t"] <= h <= b["t"]:
            f = (h - a["t"]) / (b["t"] - a["t"]) if b["t"] > a["t"] else 0
            return (a["lat"] + (b["lat"] - a["lat"]) * f, a["lon"] + (b["lon"] - a["lon"]) * f,
                    a["wind_kt"] + (b["wind_kt"] - a["wind_kt"]) * f)
    return None


def storm_wind_kt(t, lat, lon, rmw_nm=18.0, background=None):
    """Sustained wind (kt) and direction-from (deg) at a point from a simple vortex around the
    track, blended with a calm-weather background. Good for keeping streams consistent with
    each other (who is flying, sailing, reporting gusts); not a meteorological model."""
    c = storm_center(t)
    hour = (t % 86400) / 3600.0
    base = background if background is not None else 9.0 + 4.0 * math.sin((hour - 15) / 24 * 2 * math.pi)
    if c is None:
        return base, 140.0
    clat, clon, vmax = c
    dy = (lat - clat) * 60.0
    dx = (lon - clon) * 60.0 * math.cos(math.radians(lat))
    r = max(1.0, math.hypot(dx, dy))
    v = vmax * (r / rmw_nm) if r < rmw_nm else vmax * (rmw_nm / r) ** 0.62
    # weaker on the left of the track, weaker over land after landfall
    brg = math.degrees(math.atan2(dx, dy)) % 360
    v *= 0.85 + 0.15 * math.cos(math.radians(brg - 60))
    direction = (brg + 100) % 360           # cyclonic flow with inflow
    return max(base, v), direction if v > base else 140.0


def surge_m(t, exposure=1.0):
    """Storm surge above normal tide (m) for an open-coast/bay site; peak about 3.4 m at landfall."""
    h = (t - LANDFALL) / 3600.0
    return max(0.0, exposure * 3.4 * math.exp(-(h / 5.5) ** 2 if h < 0 else -(h / 9.0) ** 2))


# ---------------------------------------------------------------- output
def out_path(rel):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def write_csv(rel, header, rows):
    """Write rows (iterable of lists) with a header; returns the row count."""
    n = 0
    with open(out_path(rel), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
            n += 1
    return n


def write_jsonl(rel, objs):
    n = 0
    with open(out_path(rel), "w", encoding="utf-8") as fh:
        for o in objs:
            fh.write(json.dumps(o, ensure_ascii=False) + "\n")
            n += 1
    return n


def retire(rel_paths, tag="streams_pre_regen_20261109"):
    """Move superseded stream files out of the delivered tree into _versions/<tag>/ (same relative
    path) so stale data cannot be mistaken for current data."""
    import shutil
    moved = 0
    for rel in rel_paths:
        src = os.path.join(ROOT, rel)
        if os.path.exists(src):
            dst = os.path.join(ROOT, "_versions", tag, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            moved += 1
    return moved
