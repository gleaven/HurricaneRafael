"""Flight kinematics shared by the aviation generators (ADS-B and drones).

A flight is built as a list of knots (time, x, y, altitude, on-ground flag, phase tag) in a local
metric projection; airborne runs are resampled every 5 s and smoothed so that turns are rounded,
then rows are emitted at the stream's cadence. Geometry (runways, pads, parking positions) comes
from 06_data_streams/aircraft_registry.json, which was built from the real airfield data in
99_reference/geo/. See scripts/streams/README.md for the generator contract.
"""
import math

import numpy as np

from common import reg, storm_wind_kt

LAT0, LON0 = 27.75, -97.40
MLAT = 110950.0
MLON = 111320.0 * math.cos(math.radians(LAT0))
KT, FT, NM = 0.514444, 0.3048, 1852.0


def xy(lat, lon):
    return ((lon - LON0) * MLON, (lat - LAT0) * MLAT)


def ll(x, y):
    return (LAT0 + y / MLAT, LON0 + x / MLON)


def hdg(dx, dy):
    return (math.degrees(math.atan2(dx, dy)) + 360.0) % 360.0


def unit(h):
    r = math.radians(h)
    return (math.sin(r), math.cos(r))


def angdiff(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------- performance
# vr lift-off, vcl initial climb, vapp approach (m/s); roc/rod (m/s); roll (m); min runway (m)
PERF = {
    "TEX2": dict(small=True, vr=46, vcl=72, vapp=54, roc=14, rod=8, roll=550, minrw=1200, alt=(2400, 4600), win=30),
    "BE9L": dict(vr=50, vcl=72, vapp=55, roc=9, rod=6, roll=700, minrw=1200, alt=(1800, 3700), win=30),
    "T45": dict(vr=64, vcl=125, vapp=66, roc=28, rod=14, roll=1100, minrw=2000, alt=(4600, 7600), win=40),
    "C17": dict(vr=66, vcl=125, vapp=62, roc=11, rod=9, roll=1300, minrw=2200, alt=(9400, 10700), win=60),
    "E75L": dict(vr=70, vcl=128, vapp=67, roc=13, rod=9, roll=1400, minrw=1800, alt=(9800, 11000), win=60),
    "CRJ7": dict(vr=70, vcl=128, vapp=68, roc=13, rod=9, roll=1400, minrw=1800, alt=(9800, 10700), win=60),
    "B734": dict(vr=72, vcl=128, vapp=70, roc=12, rod=9, roll=1500, minrw=2000, alt=(9800, 10700), win=60),
    "B752": dict(vr=72, vcl=128, vapp=68, roc=13, rod=9, roll=1500, minrw=2000, alt=(9800, 11000), win=60),
    "AT72": dict(vr=57, vcl=85, vapp=58, roc=7, rod=6, roll=1000, minrw=1300, alt=(4900, 6400), win=40),
    "CN35": dict(vr=55, vcl=80, vapp=58, roc=8, rod=6, roll=800, minrw=1200, alt=(450, 2700), win=30),
    "DH8B": dict(vr=56, vcl=85, vapp=58, roc=8, rod=6, roll=900, minrw=1200, alt=(900, 3700), win=30),
    "PC12": dict(vr=45, vcl=75, vapp=50, roc=9, rod=6, roll=600, minrw=900, alt=(4000, 7300), win=30),
    "B350": dict(vr=55, vcl=85, vapp=56, roc=11, rod=7, roll=800, minrw=1100, alt=(1500, 7600), win=30),
    "BE20": dict(vr=52, vcl=80, vapp=54, roc=10, rod=7, roll=750, minrw=1000, alt=(4000, 7000), win=30),
    "P3": dict(vr=65, vcl=110, vapp=68, roc=8, rod=7, roll=1400, minrw=2000, alt=(2400, 3100), win=50),
    "Q9": dict(vr=45, vcl=62, vapp=48, roc=5, rod=5, roll=900, minrw=1500, alt=(5800, 5800), win=40),
    "C172": dict(small=True, vr=28, vcl=38, vapp=33, roc=3.5, rod=3, roll=300, minrw=600, alt=(750, 1700), win=25),
    "P28A": dict(small=True, vr=30, vcl=40, vapp=34, roc=3.5, rod=3, roll=320, minrw=600, alt=(750, 1700), win=25),
    "C182": dict(small=True, vr=30, vcl=45, vapp=36, roc=4.5, rod=3.5, roll=300, minrw=600, alt=(450, 2100), win=25),
    "C206": dict(small=True, vr=31, vcl=45, vapp=37, roc=4.5, rod=3.5, roll=350, minrw=600, alt=(300, 900), win=25),
    "C208": dict(vr=36, vcl=55, vapp=42, roc=5, rod=4, roll=450, minrw=700, alt=(600, 3000), win=25),
    "SR22": dict(vr=37, vcl=55, vapp=41, roc=6, rod=4, roll=400, minrw=700, alt=(1500, 3000), win=25),
    "BE36": dict(vr=37, vcl=55, vapp=41, roc=5.5, rod=4, roll=400, minrw=700, alt=(1500, 3000), win=25),
    # helicopters
    "H60": dict(helo=True, roc=7, rod=5, alt=(150, 450), win=20),
    "AS50": dict(helo=True, roc=7, rod=5, alt=(150, 400), win=20),
    "B06": dict(helo=True, roc=6, rod=4, alt=(250, 450), win=20),
    "B429": dict(helo=True, roc=7, rod=5, alt=(300, 600), win=20),
    "EC35": dict(helo=True, roc=7, rod=5, alt=(300, 600), win=20),
    "H47": dict(helo=True, roc=7, rod=5, alt=(300, 600), win=20),
    "H64": dict(helo=True, roc=8, rod=6, alt=(150, 450), win=20),
}

# ADS-B receivers feeding the archive (lat, lon); a row exists only when one is in line of sight
RECEIVERS = [(27.7722, -97.5024), (27.6927, -97.2904), (27.8118, -97.0888), (28.0862, -97.0437), (27.5045, -97.8083)]
RX = np.array([xy(*r) for r in RECEIVERS])
COVERAGE_NM = 150.0


def visible(x, y, alt_m, gnd):
    d = float(np.hypot(RX[:, 0] - x, RX[:, 1] - y).min()) / NM
    if gnd:
        return d <= 9.0
    h = max(0.0, alt_m) / FT
    return d <= min(COVERAGE_NM, 1.23 * (math.sqrt(h) + 9.0))


# ---------------------------------------------------------------------------- airfields
class Fields:
    def __init__(self):
        r = reg("aircraft_registry")
        self.af = {a["airfield_id"]: a for a in r["airfields"]}
        self.park = {p["position_id"]: p for p in r["parking_positions"]}
        self.ac = {a["aircraft_id"]: a for a in r["aircraft"]}
        self.by_call = {(a.get("callsign_voice") or a["callsign"]): a for a in r["aircraft"]}
        self.pads = {p["position_id"]: p for p in r["parking_positions"] if not p.get("airfield_id")}

    def pt(self, afid):
        a = self.af[afid]
        return xy(a["latitude"], a["longitude"])

    def local(self, afid):
        return bool(self.af[afid].get("runways"))

    def park_xy(self, pid):
        p = self.park[pid]
        return xy(p["latitude"], p["longitude"])

    def runway(self, afid, t, perf):
        """Pick the runway direction into the wind: returns (threshold_xy, far_end_xy, heading, length)."""
        a = self.af[afid]
        _, wdir = storm_wind_kt(t, a["latitude"], a["longitude"])
        best = None
        for rw in a["runways"]:
            e1, e2 = xy(*rw["end_1"]), xy(*rw["end_2"])
            L = math.hypot(e2[0] - e1[0], e2[1] - e1[1])
            for s, e in ((e1, e2), (e2, e1)):
                h = hdg(e[0] - s[0], e[1] - s[1])
                score = math.cos(math.radians(angdiff(h, wdir))) + (0.15 if L >= perf.get("minrw", 0) else -2.0) + L / 20000.0
                if best is None or score > best[0]:
                    best = (score, s, e, h, L)
        return best[1], best[2], best[3], best[4]


# ---------------------------------------------------------------------------- track builder
class Trk:
    """Knots: (t, x, y, alt_m, gnd, tag). Tags: p parked, g ground moving, t terminal (10 s rows),
    e en route (60 s), l low-level work (30 s), h hover (10 s)."""

    def __init__(self, t0, x, y, alt=0.0, gnd=True, tag="p"):
        self.k = [(float(t0), float(x), float(y), float(alt), gnd, tag)]
        self.v = 0.0
        self.h = None

    @property
    def t(self):
        return self.k[-1][0]

    @property
    def p(self):
        return self.k[-1][1], self.k[-1][2]

    @property
    def alt(self):
        return self.k[-1][3]

    def wait(self, dur, tag="p", gnd=True):
        t, x, y, a, _, _ = self.k[-1]
        self.k.append((t + dur, x, y, a, gnd, tag))
        self.v = 0.0

    def go(self, x, y, alt, v, tag, gnd=False, roc=None, rod=None):
        """Leg to (x, y), reaching speed v at the end. On the ground speed changes steadily along
        the leg. In the air the aircraft first turns onto the new course along an arc sized for
        its speed, then flies straight; altitude changes at roc/rod (climbs at the start of the
        leg, descents at the end; whatever does not fit is left for the next leg)."""
        t, x0, y0, a0, _, _ = self.k[-1]
        L = math.hypot(x - x0, y - y0)
        if gnd:
            v0 = self.v
            if L > 1.0:
                self.h = hdg(x - x0, y - y0)
            n = 5 if abs(v - v0) > 8 and L > 50 else 1
            T = L / max(1.5, (v0 + v) / 2.0)
            for i in range(1, n + 1):
                f = i / n                                        # fraction of time; constant acceleration
                d = (v0 * f * T + 0.5 * (v - v0) * f * f * T) / L if L > 0 else 1.0
                self.k.append((t + T * f, x0 + (x - x0) * d, y0 + (y - y0) * d, 0.0, True, tag))
            self.v = v
            return
        if L < 1.0:
            self.k.append((t + 1.0, x, y, alt, False, tag))
            self.v = v
            return
        # turn onto course
        vt = max(self.v, 8.0)
        want = hdg(x - x0, y - y0)
        turn = angdiff(want, self.h) if self.h is not None else 0.0
        if abs(turn) > 25.0 and vt > 14.0:
            R = max(250.0, vt * vt / (9.81 * math.tan(math.radians(25.0))))
            if L > 2.2 * R:
                sgn = 1.0 if turn > 0 else -1.0
                ux, uy = unit(self.h)
                cx, cy = x0 + uy * sgn * R, y0 - ux * sgn * R     # centre of the turn, to the right for +
                ang0 = math.atan2(x0 - cx, y0 - cy)
                h = self.h
                px, py = x0, y0
                done = 0.0
                while done < 350.0:
                    stepd = 15.0
                    done += stepd
                    ang = ang0 + sgn * math.radians(done)
                    nx, ny = cx + R * math.sin(ang), cy + R * math.cos(ang)
                    h = (self.h + sgn * done) % 360.0
                    dt_ = R * math.radians(stepd) / vt
                    da = 0.0
                    if roc and alt > a0 + 1:
                        da = min(alt - a0, roc * dt_)
                    elif rod and alt < a0 - 1:
                        da = -min(a0 - alt, rod * dt_ * 0.5)
                    a0 += da
                    t += dt_
                    self.k.append((t, nx, ny, a0, False, tag))
                    px, py = nx, ny
                    if abs(angdiff(hdg(x - px, y - py), h)) < 9.0:
                        break
                x0, y0 = px, py
                L = math.hypot(x - x0, y - y0)
        self.h = hdg(x - x0, y - y0)
        vavg = max(1.5, (self.v + v) / 2.0)
        T = L / vavg
        d = alt - a0
        rate = roc if d > 0 else rod
        if rate and abs(d) > 1:
            need = abs(d) / rate
            if need < T * 0.92:
                f = need / T
                if d > 0:
                    self.k.append((t + need, x0 + (x - x0) * f, y0 + (y - y0) * f, alt, False, tag))
                else:
                    self.k.append((t + T - need, x0 + (x - x0) * (1 - f), y0 + (y - y0) * (1 - f), a0, False, tag))
                self.k.append((t + T, x, y, alt, False, tag))
            else:
                self.k.append((t + T, x, y, a0 + math.copysign(rate * T, d), False, tag))
        else:
            self.k.append((t + T, x, y, alt, False, tag))
        self.v = v

    def hover(self, dur, rng, drift=12.0, alt=None, tag="h"):
        t, x, y, a, _, _ = self.k[-1]
        a = a if alt is None else alt
        n = max(1, int(dur // 30))
        for i in range(1, n + 1):
            self.k.append((t + dur * i / n, x + rng.normal(0, drift), y + rng.normal(0, drift), a + rng.normal(0, 2.0), False, tag))
        self.v = 0.0
        self.h = None


CADENCE = {"g": 10, "t": 10, "e": 60, "l": 30, "h": 10}


def sample(trk, win_s=30):
    """Turn knots into state rows (t, x, y, alt, gnd, speed, track, vrate). Airborne runs are
    resampled at 5 s and smoothed with a moving average, which rounds corners and leaves straight
    segments (runway centrelines, final approach) where they are."""
    k = trk.k
    rows = []
    i = 0
    n = len(k)
    last_trk = 0.0
    while i < n - 1:
        gnd = k[i + 1][4]
        j = i
        while j < n - 1 and k[j + 1][4] == gnd:
            j += 1
        seg = k[i:j + 1]
        if gnd:
            for a, b in zip(seg, seg[1:]):
                dt = b[0] - a[0]
                L = math.hypot(b[1] - a[1], b[2] - a[2])
                if b[5] == "p" or L < 0.5:
                    if not rows or rows[-1][0] < a[0]:
                        rows.append((a[0], a[1], a[2], 0.0, True, 0.0, last_trk, 0.0))
                    rows.append((b[0], b[1], b[2], 0.0, True, 0.0, last_trk, 0.0))
                    continue
                last_trk = hdg(b[1] - a[1], b[2] - a[2])
                t = a[0] if (not rows or rows[-1][0] < a[0]) else a[0] + CADENCE["g"]
                while t < b[0]:
                    f = (t - a[0]) / dt
                    rows.append((t, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, 0.0, True, L / dt, last_trk, 0.0))
                    t += CADENCE["g"]
        else:
            ts = np.array([q[0] for q in seg])
            keep = np.concatenate([[True], np.diff(ts) > 1e-6])
            segk = [q for q, m in zip(seg, keep) if m]
            ts = np.array([q[0] for q in segk])
            T = np.arange(ts[0], ts[-1] + 1e-6, 5.0)
            if len(T) < 2:
                T = np.array([ts[0], ts[-1]])
            X = np.interp(T, ts, [q[1] for q in segk]); Y = np.interp(T, ts, [q[2] for q in segk]); A = np.interp(T, ts, [q[3] for q in segk])
            tagidx = np.searchsorted(ts, T, side="left").clip(1, len(segk) - 1)
            tags = [segk[m][5] for m in tagidx]
            w = max(1, int(win_s // 5) // 2)
            if len(T) > 2 * w + 2:
                hov = np.array([tg == "h" for tg in tags])
                Xs, Ys = X.copy(), Y.copy()
                for _ in range(2):
                    Xp = np.concatenate([np.full(w, Xs[0]), Xs, np.full(w, Xs[-1])])
                    Yp = np.concatenate([np.full(w, Ys[0]), Ys, np.full(w, Ys[-1])])
                    ker = np.ones(2 * w + 1) / (2 * w + 1)
                    Xn, Yn = np.convolve(Xp, ker, "valid"), np.convolve(Yp, ker, "valid")
                    # pin ends so the run starts and ends exactly where the knots say
                    ramp = np.minimum(1.0, np.minimum(np.arange(len(T)), np.arange(len(T))[::-1]) / (2.0 * w))
                    Xs = np.where(hov, Xs, X + (Xn - X) * ramp)
                    Ys = np.where(hov, Ys, Y + (Yn - Y) * ramp)
                X, Y = Xs, Ys
            VX = np.gradient(X, T); VY = np.gradient(Y, T); VZ = np.gradient(A, T)
            tn = T[0] if (not rows or rows[-1][0] < T[0]) else T[0] + 5.0
            for m in range(len(T)):
                if T[m] + 1e-6 < tn:
                    continue
                sp = math.hypot(VX[m], VY[m])
                if sp > 1.0:
                    last_trk = hdg(VX[m], VY[m])
                rows.append((float(T[m]), float(X[m]), float(Y[m]), float(A[m]), False, sp, last_trk, float(VZ[m])))
                tn = T[m] + CADENCE.get(tags[m], 10)
            if rows and rows[-1][0] < T[-1] - 1e-6:
                rows.append((float(T[-1]), float(X[-1]), float(Y[-1]), float(A[-1]), False, math.hypot(VX[-1], VY[-1]), last_trk, float(VZ[-1])))
        i = j
    return rows


# ---------------------------------------------------------------------------- fixed-wing pieces
def fw_takeoff(trk, F, afid, perf, vc, rng):
    """Taxi from the current (parked) position to the runway, roll, lift off and climb straight
    ahead to about 150 m. Returns runway heading."""
    thr, far, h, L = F.runway(afid, trk.t, perf)
    ux, uy = unit(h)
    start = (thr[0] + ux * 40, thr[1] + uy * 40)
    trk.v = 7.0
    trk.go(start[0], start[1], 0, 7.0, "g", gnd=True)
    trk.v = 0.0
    roll = min(perf["roll"] * rng.uniform(0.9, 1.15), L * 0.62)
    trk.wait(rng.uniform(15, 50), tag="g")
    trk.v = 0.0
    lo = (start[0] + ux * roll, start[1] + uy * roll)
    trk.go(lo[0], lo[1], 0, perf["vr"], "g", gnd=True)
    trk.h = h
    d1 = max(L - roll, 600) + 1500
    trk.go(lo[0] + ux * d1, lo[1] + uy * d1, 150, perf["vcl"], "t", roc=perf["roc"])
    return h


def fw_land(trk, F, afid, perf, park_xy, rng, low_approach=False, vc=None):
    """From wherever the aircraft is: join the final for the runway in use, land (or fly a low
    approach), roll out and taxi to the parking position."""
    thr, far, h, L = F.runway(afid, trk.t + 600, perf)
    ux, uy = unit(h)
    x0, y0 = trk.p
    faf_d = 9000.0 if not perf.get("small") else 3600.0
    faf = (thr[0] - ux * faf_d, thr[1] - uy * faf_d)
    # which side are we arriving from? if from ahead of the runway, fly a downwind first
    rel = angdiff(hdg(faf[0] - x0, faf[1] - y0), h)
    vapp = perf["vapp"]
    vmid = max(vapp * 1.25, min(trk.v, vapp * 1.7))
    if abs(rel) > 75:
        side = 1.0 if ((x0 - thr[0]) * uy - (y0 - thr[1]) * ux) > 0 else -1.0   # right of runway heading = +1
        px, py = uy * side, -ux * side
        off = 4500.0 if not perf.get("small") else 1800.0
        dw1 = (thr[0] + ux * 1500 + px * off, thr[1] + uy * 1500 + py * off)
        dw2 = (faf[0] - ux * 1500 + px * off, faf[1] - uy * 1500 + py * off)
        pa = 750 if not perf.get("small") else 330
        trk.go(dw1[0], dw1[1], pa, vmid, "t", roc=perf["roc"], rod=perf["rod"])
        trk.go(dw2[0], dw2[1], pa * 0.8, vmid, "t", roc=perf["roc"], rod=perf["rod"])
        trk.go(faf[0], faf[1], 470 if not perf.get("small") else 200, vapp * 1.15, "t", rod=perf["rod"])
    else:
        d = math.hypot(faf[0] - x0, faf[1] - y0)
        if d > 30000:
            f = (d - 25000) / d
            trk.go(x0 + (faf[0] - x0) * f, y0 + (faf[1] - y0) * f, max(1500.0, min(trk.alt, 3000.0)), max(vmid, 0.75 * trk.v), "e" if d > 60000 else "t", roc=perf["roc"], rod=perf["rod"])
        trk.go(faf[0], faf[1], 470 if not perf.get("small") else 200, vapp * 1.15, "t", roc=perf["roc"], rod=perf["rod"])
    if low_approach:
        trk.go(thr[0] + ux * 200, thr[1] + uy * 200, 20, vapp, "t", rod=4.0)
        trk.go(thr[0] + ux * (L + 2500), thr[1] + uy * (L + 2500), 250, perf["vcl"], "t", roc=perf["roc"])
        trk.h = h
        return h
    td = (thr[0] + ux * 320, thr[1] + uy * 320)
    trk.k.append((trk.t + faf_d / vapp, td[0], td[1], 0.0, False, "t"))
    trk.v = vapp
    trk.h = h
    stop_d = min(L * 0.72, 320 + perf["roll"] * 1.2)
    ex = (thr[0] + ux * stop_d, thr[1] + uy * stop_d)
    trk.go(ex[0], ex[1], 0, 9.0, "g", gnd=True)
    trk.v = 7.0
    trk.go(park_xy[0], park_xy[1], 0, 7.0, "g", gnd=True)
    trk.wait(20, tag="p")
    return h


def far_point(F, afid, origin_xy, dist_nm=175.0):
    """A point dist_nm from origin on the bearing to a distant airfield (flights are only seen
    inside coverage, so the track simply heads that way and leaves)."""
    fx, fy = F.pt(afid)
    b = hdg(fx - origin_xy[0], fy - origin_xy[1])
    D = math.hypot(fx - origin_xy[0], fy - origin_xy[1])
    d = min(D, dist_nm * NM)
    ux, uy = unit(b)
    return (origin_xy[0] + ux * d, origin_xy[1] + uy * d), b, D


# ---------------------------------------------------------------------------- helicopters
def helo_lift(trk, alt, v, hd, perf):
    x, y = trk.p
    trk.k.append((trk.t + 12, x, y, 12.0, False, "t"))
    ux, uy = unit(hd)
    trk.v = 5.0
    trk.h = hd
    trk.go(x + ux * 600, y + uy * 600, min(alt, 90.0), min(v, 35.0), "t", roc=perf["roc"])


def helo_goto(trk, x, y, alt, v, perf, tag="l", stop=False, cruise=None):
    """Fly to a point; with stop=True decelerate into a hover over it at the given altitude.
    Legs longer than 4 km are flown at the cruise altitude, short hops stay low."""
    x0, y0 = trk.p
    d = math.hypot(x - x0, y - y0)
    en = max(alt, cruise) if (cruise and d > 4000) else max(alt, min(trk.alt, alt + 60))
    if stop and d > 900:
        f = (d - 700) / d
        trk.go(x0 + (x - x0) * f, y0 + (y - y0) * f, en, v, tag if d > 5000 else "t", roc=perf["roc"], rod=perf["rod"])
        trk.go(x, y, alt, 3.0, "t", rod=perf["rod"], roc=perf["roc"])
    elif stop:                                                    # short hop between hover points: speed up, then slow into the hover
        vm = min(v, 7.0 + d / 45.0)
        trk.go((x0 + x) / 2, (y0 + y) / 2, max(alt, min(trk.alt, alt + 25)), vm, "t", roc=perf["roc"], rod=perf["rod"])
        trk.go(x, y, alt, 3.0, "t", rod=perf["rod"], roc=perf["roc"])
    else:
        trk.go(x, y, alt, v, tag if d > 5000 else "t", roc=perf["roc"], rod=perf["rod"])


def helo_land(trk, x, y, perf, v=55.0, cruise=None):
    helo_goto(trk, x, y, 25.0, v, perf, stop=True, cruise=cruise)
    trk.k.append((trk.t + 25, x, y, 0.0, False, "t"))
    trk.k.append((trk.t + 5, x, y, 0.0, True, "p"))
    trk.v = 0.0
