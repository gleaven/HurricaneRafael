"""Core objects for the port simulation: clock constants, vessels, itinerary segments and
the conversion of itineraries into position reports.

A vessel's life is a list of segments in time order:
    Stay  the vessel is at one place (moored, at anchor, holding station, drifting)
    Move  the vessel follows a verified Path with a piecewise-linear distance/time schedule
Gaps between segments mean the vessel is outside the feed's coverage or not transmitting.
Every stream in the maritime family is derived from these segments, so the streams agree.
"""
import math
import zlib

import numpy as np

import geo
import maritime_geom as mg
from common import (D0_EPOCH, LANDFALL, SPAN_END, SPAN_START, iso, local_ts, rng, storm_wind_kt, ts)

KN = 0.514444  # m/s per knot

# ------------------------------------------------------------------ canon clock (UTC epochs)
T0, T_END = SPAN_START, SPAN_END
T_WARM = T0 - 14 * 86400                      # simulation warm-up; nothing before T0 is written
XRAY = ts("2027-09-11T05:00Z")                # Port Condition X-Ray
YANKEE = ts("2027-09-12T12:00Z")              # Yankee: closed to inbound
ZULU = ts("2027-09-13T17:00Z")                # Zulu: closed to all (noon local, D-1)
ANCH_CLEAR = ts("2027-09-13T23:00Z")          # anchorage empty by 18:00 local
RETURN_D3_A, RETURN_D3_B = ts("2027-09-17T10:30Z"), ts("2027-09-17T23:30Z")   # storm riders back at the anchorage on D+3
REOPEN1 = ts("2027-10-14T16:00Z")             # partial reopening (D+30)
INNER_E_PERMITS = ts("2027-10-15T14:00Z")     # first permitted transits into the Main Turning Basin
BLAST = ts("2027-10-28T06:10Z")               # D+44 01:10 local
RESTRICTION_LIFTED = ts("2027-10-28T05:00Z")  # inner-channel restriction lifted at 00:00 local D+44
REOPEN2 = ts("2027-11-11T14:00Z")             # channel reopens after the sweep (D+58, 08:00 local)
DARK_START, DARK_END = ts("2027-10-15T02:00Z"), ts("2027-10-15T16:00Z")
LAST_IN_PRESTORM = ts("2027-09-11T13:00Z")    # last inbound pilot boarding before the storm
LAST_OUT_PRESTORM = ts("2027-09-13T08:30Z")   # last outbound departure from a berth before Zulu
BLACKOUT_FROM = ts("2027-10-28T01:30Z")       # no new ship movements start after this before the blast (one scripted departure excepted)

SEA = (27.79312, -96.96336)                   # sea buoy, seaward end of the sea bar channel
BOARD = (27.77575, -96.93124)                 # pilot boarding area
OFFING = (27.576, -96.56185)
RX = (27.8397, -97.0725)                      # shore AIS station, Port Aransas
RX_RANGE_NM = 45.0
LON_JETTY = -97.0450                          # jetty line (VTS checkpoint, jetty camera)
LON_FERRY = -97.0690                          # ferry crossing
LON_BRIDGE = -97.3957                         # Harbor Bridge
INTERVAL = {0: 60.0, 1: 300.0, 2: 1800.0, 3: 3600.0}


class Stay:
    kind = "stay"
    __slots__ = ("t0", "t1", "pos", "mode", "heading", "place", "ais", "status", "draft", "dest", "radius")

    def __init__(self, t0, t1, pos, mode, heading=None, place="", ais=True, status=None, draft=None, dest="", radius=0.0):
        self.t0, self.t1, self.pos, self.mode = float(t0), float(t1), (float(pos[0]), float(pos[1])), mode
        self.heading, self.place, self.ais, self.status, self.draft, self.dest, self.radius = heading, place, ais, status, draft, dest, radius


class Move:
    kind = "move"
    __slots__ = ("t0", "t1", "path", "kt", "ks", "ais", "status", "draft", "dest", "place")

    def __init__(self, path, kt, ks, ais=True, status=0, draft=None, dest="", place=""):
        self.path, self.kt, self.ks = path, np.asarray(kt, float), np.asarray(ks, float)
        self.t0, self.t1 = float(self.kt[0]), float(self.kt[-1])
        self.ais, self.status, self.draft, self.dest, self.place = ais, status, draft, dest, place

    def s_at(self, t):
        return float(np.interp(t, self.kt, self.ks))

    def pos(self, t):
        return self.path.at(self.s_at(t))

    def speed_kn(self, t):
        i = int(np.searchsorted(self.kt, t, side="right")) - 1
        i = min(max(i, 0), len(self.kt) - 2)
        dt = self.kt[i + 1] - self.kt[i]
        return abs(self.ks[i + 1] - self.ks[i]) / dt / KN if dt > 0 else 0.0

    def t_at_s(self, s):
        """Time at which the vessel reaches s metres along the path (ks is monotone)."""
        ks = self.ks
        if ks[-1] >= ks[0]:
            return float(np.interp(s, ks, self.kt))
        return float(np.interp(-s, -ks, self.kt))

    def t_at_lon(self, lon):
        """Time the vessel crosses a meridian while on this move, or None."""
        pts = self.path.pts
        lo, hi = sorted((self.ks[0], self.ks[-1]))
        for i in range(len(pts) - 1):
            a, b = pts[i][1], pts[i + 1][1]
            if (a - lon) * (b - lon) <= 0 and a != b:
                s = self.path.cum[i] + (self.path.cum[i + 1] - self.path.cum[i]) * (lon - a) / (b - a)
                if lo - 1 <= s <= hi + 1:
                    return self.t_at_s(s)
        return None


def make_move(path, t0, speed=None, vfun=None, s0=0.0, s1=None, t1=None, **kw):
    """Schedule a run along path from s0 to s1 (either direction along the path).
    speed: constant knots; vfun(lat, lon, s) -> knots evaluated at the path vertices;
    t1: fit a constant speed to arrive at t1."""
    s1 = path.length if s1 is None else s1
    fwd = s1 >= s0
    lo, hi = (s0, s1) if fwd else (s1, s0)
    inner = [float(c) for c in path.cum if lo + 0.5 < c < hi - 0.5]
    # long straight runs get intermediate knots so speed changes are spread along them
    ss = [lo] + inner + [hi]
    dense = [ss[0]]
    for a, b in zip(ss, ss[1:]):
        n = int((b - a) // 4000)
        for k in range(1, n + 1):
            dense.append(a + (b - a) * k / (n + 1))
        dense.append(b)
    ss = dense if fwd else dense[::-1]
    if t1 is not None:
        total = abs(s1 - s0)
        kt = [t0 + (t1 - t0) * (abs(s - s0) / total if total > 0 else 0.0) for s in ss]
        return Move(path, kt, ss, **kw)
    if vfun is None:
        v = [max(0.3, speed)] * len(ss)
    else:
        v = []
        for s in ss:
            la, lo_, _ = path.at(s)
            v.append(max(0.3, float(vfun(la, lo_, s))))
    kt = [float(t0)]
    for i in range(1, len(ss)):
        ds = abs(ss[i] - ss[i - 1])
        kt.append(kt[-1] + ds / (0.5 * (v[i] + v[i - 1]) * KN))
    return Move(path, kt, ss, **kw)


def follow(move, dt=0.0, ds=0.0, s_min=None, s_max=None, **kw):
    """A second vessel on the same track, dt seconds behind and/or ds metres ahead."""
    ks = move.ks + ds
    lo = 0.0 if s_min is None else s_min
    hi = move.path.length if s_max is None else s_max
    ks = np.clip(ks, lo, hi)
    args = dict(ais=move.ais, status=move.status, draft=move.draft, dest=move.dest)
    args.update(kw)
    return Move(move.path, move.kt + dt, ks, **args)


def ais_name(name):
    for pre in ("MT ", "MV ", "FV ", "RV ", "SV ", "USCGC ", "USNS "):
        if name.startswith(pre) and pre.strip() in ("MT", "MV", "FV", "RV", "SV"):
            name = name[len(pre):]
    return name.upper()[:20]


class Vessel:
    def __init__(self, rec):
        self.rec = rec
        self.id = rec["vessel_id"]
        self.mmsi = rec.get("mmsi")
        self.name = rec["vessel_name"]
        self.cls = rec["class"]
        self.tc = rec.get("transceiver_class")
        self.loa = rec.get("length_m") or 10
        self.beam = rec.get("beam_m") or 4
        self.draft_max = rec.get("draft_m") or 1.0
        self.draft_light = rec.get("draft_ballast_m") or self.draft_max
        self.itin = []
        self.rs = rng("maritime", self.id)
        self.phase = float(self.rs.uniform(0, 3600))
        self.spd = float(self.rs.uniform(0.94, 1.06))

    def add(self, seg):
        if seg.t1 < seg.t0:
            raise ValueError(f"{self.id}: segment ends before it starts")
        self.itin.append(seg)
        return seg

    @property
    def busy_until(self):
        return max((s.t1 for s in self.itin), default=-1e18)

    def finalize(self):
        self.itin.sort(key=lambda s: (s.t0, s.t1))
        for a, b in zip(self.itin, self.itin[1:]):
            if b.t0 < a.t1 - 1.0:
                raise ValueError(f"{self.id} {self.name}: overlapping segments {iso(a.t0)}..{iso(a.t1)} ({a.kind} {getattr(a, 'place', '')}) "
                                 f"and {iso(b.t0)}..{iso(b.t1)} ({b.kind} {getattr(b, 'place', '')})")

    def segment_at(self, t):
        for s in self.itin:
            if s.t0 <= t <= s.t1:
                return s
        return None

    def position_at(self, t):
        s = self.segment_at(t)
        if s is None:
            return None
        if s.kind == "move":
            la, lo, _ = s.pos(t)
            return la, lo
        return s.pos


# ------------------------------------------------------------------ wind-driven swing at anchor
def swing(t, anchor, radius, seed):
    """Position and heading of a ship lying to her anchor: downwind of the anchor, yawing slowly."""
    w, wdir = storm_wind_kt(t, anchor[0], anchor[1])
    slow = 28.0 * math.sin(2 * math.pi * (t / 44700.0 + seed)) + 9.0 * math.sin(2 * math.pi * (t / 7300.0 + 3 * seed))
    brg_from = (wdir + slow) % 360
    scope = radius * (0.55 + 0.45 * min(1.0, w / 25.0))
    p = mg.dest_point(anchor, (brg_from + 180) % 360, scope)
    return p, brg_from


# ------------------------------------------------------------------ reports
class Emitter:
    """Turns itineraries into AIS reports (shore-station feed and satellite feed)."""

    def __init__(self, GM):
        self.GM, self.G = GM, GM.G
        self._ok = {}

    def feed(self, lat, lon):
        return "T" if geo.gc_nm((lat, lon), RX) <= RX_RANGE_NM else "S"

    def stay_fixes(self, v, seg, t_lo, t_hi):
        a, b = max(seg.t0, t_lo), min(seg.t1, t_hi)
        if b <= a or not seg.ais:
            return
        if seg.mode == "moored":
            step = 3600.0
        elif seg.mode == "anchored":
            step = 360.0
        elif seg.mode == "work":
            step = 900.0
        else:
            z = mg._zone_of_point(self.G, seg.pos[0], seg.pos[1])
            step = (120.0, 300.0, 900.0, 3600.0)[z]
        k0 = math.ceil((a - v.phase) / step)
        times = []
        t = v.phase + k0 * step
        while t <= b:
            times.append(t)
            t += step
        if seg.mode in ("moored", "anchored") and seg.t0 >= t_lo and (not times or times[0] - a > 240):
            times.insert(0, a + 20)             # report on arrival
        if seg.mode in ("hold", "drift") and not times:
            times = [0.5 * (a + b)]
        rs = rng("fix", v.id, int(seg.t0))
        for t in times:
            tj = min(max(t + (0.0 if getattr(v, "nojit", False) else float(rs.uniform(-25, 25))), a), b)
            if seg.mode == "anchored":
                p, hdg = swing(tj, seg.pos, seg.radius or 220.0, v.phase / 3600.0)
                sog = abs(float(rs.normal(0.1, 0.1)))
                cog = float(rs.uniform(0, 360))
            elif seg.mode == "drift":
                ang = (tj / 23.0 + v.phase) % 360
                p = mg.dest_point(seg.pos, ang, (seg.radius or 60.0) * (0.4 + 0.6 * abs(math.sin(tj / 700.0))))
                if self.G.is_land(*p):
                    p = seg.pos
                hdg = (ang + 90) % 360
                sog = abs(float(rs.normal(0.8, 0.3)))
                cog = hdg
            else:
                p = seg.pos
                hdg = seg.heading if seg.heading is not None else (zlib.crc32(f"{v.id}|{int(seg.t0)}".encode()) % 3600) / 10.0   # fixed for the stay, and the same however the run is split
                hdg = (hdg + float(rs.normal(0, 0.6))) % 360
                sog = 0.0 if rs.random() < 0.85 else 0.1
                cog = float(rs.uniform(0, 360)) if seg.mode == "moored" else hdg
            yield (tj, p[0], p[1], sog, cog, hdg, seg)

    def move_fixes(self, v, seg, t_lo, t_hi):
        if not seg.ais or seg.t1 <= t_lo or seg.t0 >= t_hi:
            return
        path = seg.path
        zs = mg.zones(self.G, path)
        nofix = path.nofix
        lo, hi = sorted((seg.ks[0], seg.ks[-1]))
        times = set()
        # every vertex passed is reported, so the reported track is the verified path itself
        for i, c in enumerate(path.cum):
            if lo - 0.5 <= c <= hi + 0.5:
                times.add(round(seg.t_at_s(float(c)), 1))
        times.add(round(seg.t0, 1)); times.add(round(seg.t1, 1))
        must = sorted(times)
        must_arr = np.array(must)
        rs = rng("fixm", v.id, int(seg.t0))
        t = seg.t0 + float(rs.uniform(5, 40))
        while t < seg.t1:
            s = seg.s_at(t)
            i = min(max(int(np.searchsorted(path.cum, s, side="right")) - 1, 0), len(zs) - 1)
            step = INTERVAL[zs[i]]
            if step > 300.0:
                la_, lo_, _ = seg.pos(t)
                if geo.gc_nm((la_, lo_), SEA) <= 9.0:      # the anchorage and the pilot station report like the approach
                    step = 300.0
            if not (nofix and nofix[i]):
                tt = round(t, 1)
                j = int(np.searchsorted(must_arr, tt))
                near = min(abs(must_arr[j - 1] - tt) if j > 0 else 1e9, abs(must_arr[j] - tt) if j < len(must_arr) else 1e9)
                if near >= 4.0:          # a report at a turn replaces the scheduled one beside it
                    times.add(tt)
            t += step * float(rs.uniform(0.92, 1.08))
        prev = None
        for t in sorted(times):
            if t < t_lo or t > t_hi:
                continue
            if prev is not None and t - prev < 0.95:
                continue
            prev = t
            la, lon, brg = seg.pos(t)
            fwd = seg.ks[-1] >= seg.ks[0]
            cog = brg if fwd else (brg + 180) % 360
            sog = max(0.0, seg.speed_kn(min(max(t, seg.t0 + 0.5), seg.t1 - 0.5)) + float(rs.normal(0, 0.12)))
            hdg = (cog + float(rs.normal(0, 1.2))) % 360
            yield (t, la, lon, sog, cog, hdg, seg)

    def fixes(self, v, t_lo=T0, t_hi=T_END):
        last = None
        for seg in v.itin:
            gen = self.stay_fixes(v, seg, t_lo, t_hi) if seg.kind == "stay" else self.move_fixes(v, seg, t_lo, t_hi)
            for f in gen:
                if last is not None and last[6] is not seg and f[0] - last[0] < 150.0:
                    # a ship lying to her anchor swings a cable's length from it: no report in the first
                    # minutes of weighing or letting go, so the track does not jump between the two
                    swung = (seg.kind == "stay" and seg.mode == "anchored") or (last[6].kind == "stay" and last[6].mode == "anchored")
                    if swung and geo.dist_m((last[1], last[2]), (f[1], f[2])) > 40.0:
                        continue
                last = f
                yield f
