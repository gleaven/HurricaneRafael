"""Scripted canon events and the everyday life of locally based craft.

Scripted (from 00_scenario/canon_timeline.json): the dark tanker and the borrowed fishing-vessel
identity, the fuel barge, the yacht at Ingleside, the tug at the jetties, the Navy and Coast
Guard search, the spill response. Everyday: ferries, fishing and charter boats, tours, patrols,
surveys, dredging, offshore supply runs and Intracoastal tows, all standing down for the
hurricane and returning only when the canon channel windows allow.
"""
import math

import numpy as np

import geo
import maritime_geom as mg
from common import local_ts, rng, utc_offset
from maritime_base import DAY, H, PORT_NAMES, Call
from maritime_core import (BLACKOUT_FROM, BLAST, BOARD, DARK_END, DARK_START, KN, LON_BRIDGE, LON_JETTY, OFFING, REOPEN1, REOPEN2,
                           SEA, T0, T_END, T_WARM, XRAY, YANKEE, ZULU, Move, Stay, Vessel, follow, make_move, swing, ts)

STORM_STOP = ts("2027-09-11T17:00Z")          # leisure, fishing and charter boats tie up
QUIET_FROM, QUIET_TO = ZULU, ts("2027-09-15T12:00Z")   # nothing moves under AIS in the port
WAYPOINTS = {
    "jetty_tips": (27.8338, -97.0290), "anch_w": (27.832, -96.950), "anch_e": (27.835, -96.885), "anch_s": (27.790, -96.915),
    "lydia": (27.875, -97.045), "aransas_bay": (27.980, -97.000), "aransas_n": (28.050, -96.970), "aransas_e": (27.955, -96.975),
    "copano": (28.100, -97.070), "copano_e": (28.110, -97.030), "redfish": (27.905, -97.100),
    "cc_mid": (27.770, -97.250), "cc_w": (27.780, -97.360), "cc_n": (27.822, -97.300), "cc_e": (27.760, -97.190), "cc_s": (27.725, -97.300),
    "north_beach": (27.835, -97.375), "portland": (27.865, -97.320), "nueces": (27.850, -97.420), "nueces_e": (27.855, -97.385),
    "nueces_w": (27.853, -97.455), "indian_pt": (27.852, -97.352),
}


def local_hour(t):
    return ((t + utc_offset(t) * 3600) % 86400) / 3600.0


def local_day(t):
    """Scenario day number (local calendar)."""
    return int(math.floor((t + utc_offset(t) * 3600 - (ts("2027-09-14T00:00Z"))) / 86400.0))


def weekday(t):
    """0 = Monday ... 6 = Sunday (local). 2027-09-14 is a Tuesday."""
    return (local_day(t) + 1) % 7


class LocalMixin:
    # ------------------------------------------------------------------ helpers
    def wp(self, name):
        if not hasattr(self, "_wp"):
            self._wp = {}
        if name not in self._wp:
            p = WAYPOINTS[name]
            if self.G.is_land(*p) or self.G.land_clearance_m(*p) < 170:
                q = self.GM.water_point_near(p, 180.0, 1500.0)
                if q is None:
                    raise ValueError(f"no water near waypoint {name}")
                p = q
            self._wp[name] = p
        return self._wp[name]

    def gulf_ok(self, q):
        """Open Gulf east and south of the pass, well clear of the barrier islands (the fishing grounds)."""
        lat, lon = q
        if not (27.42 <= lat <= 27.99 and -96.975 <= lon <= -96.45):
            return False
        if lat > 27.80 + (lon + 96.975) * 0.95:        # stay seaward of San Jose and Matagorda islands
            return False
        if self.G.in_box(lat, lon):
            return self.G.land_clearance_m(lat, lon) >= 2500
        return True

    def idle(self, v, t0, t1):
        return all(s.t1 <= t0 or s.t0 >= t1 for s in v.itin)

    def uses_ship_channel(self, path):
        key = ("cc", id(path))
        if key not in self._paths:
            la, lo = self.GM.sample(path.pts, 150.0)
            self._paths[key] = any((self.G.channel_at(float(a), float(b), 0) or "").startswith("CESWG_CC") for a, b in zip(la, lo))
        return self._paths[key]

    def go(self, v, path, t, speed, rev=False, slow_start=True, slow_end=True, **kw):
        L = path.length

        def vf(lat, lon, s):
            if (slow_start and (s < 220 if not rev else s > L - 220)) or (slow_end and (s > L - 220 if not rev else s < 220)):
                return min(speed, 5.0)
            return speed
        m = make_move(path, t, vfun=vf, s0=(L if rev else 0.0), s1=(0.0 if rev else L), **kw)
        v.add(m)
        return m.t1

    def hold(self, v, t, secs, pos, mode="hold", **kw):
        v.add(Stay(t, t + secs, pos, mode, **kw))
        return t + secs

    def small_window(self, t, kind):
        """May a boat of this kind be under way at time t (start of a trip)?"""
        if QUIET_FROM <= t < QUIET_TO:
            return False
        if kind in ("response", "cg", "survey", "navy"):
            return True
        if kind == "bay":                      # bays away from the ship channel
            return t < STORM_STOP or t >= ts("2027-09-26T10:00Z")
        if kind == "leisure":
            return t < STORM_STOP or t >= ts("2027-11-20T00:00Z")
        # anything that uses the ship channel or the entrance
        if t < (STORM_STOP if kind in ("gulf", "charter", "tour") else YANKEE - 6 * H):
            return True
        if kind == "charter":
            return ts("2027-10-19T10:00Z") <= t < BLAST - 16 * H or t >= REOPEN2 + 20 * H
        if kind == "tour":
            return t >= REOPEN2 + 3 * DAY
        return REOPEN1 + 4 * H <= t < BLAST - 14 * H or t >= REOPEN2 + 2 * H

    def fill_home(self, v, ais_moored=True, status=5, t_stop=None):
        """Fill the gaps in a local craft's day with the time spent at her mooring. A gap is only
        filled when the vessel was at the mooring on both sides of it; time away at sea stays empty."""
        hp = self.home_position(v)
        if hp is None:
            return
        pos, hdg, hid = hp

        def end_pos(s):
            if s.kind == "stay":
                return s.pos
            la, lo, _ = s.path.at(float(s.ks[-1]))
            return (la, lo)

        def start_pos(s):
            if s.kind == "stay":
                return s.pos
            la, lo, _ = s.path.at(float(s.ks[0]))
            return (la, lo)
        v.itin.sort(key=lambda s: s.t0)
        gaps, t, prev = [], T_WARM, None
        for s in v.itin:
            if s.t0 - t > 120:
                at_home = (prev is None or geo.dist_m(end_pos(prev), pos) < 250) and geo.dist_m(start_pos(s), pos) < 250
                if at_home:
                    gaps.append((t, s.t0))
            if s.t1 >= t:
                t, prev = s.t1, s
        end = T_END + 2 * H if t_stop is None else t_stop
        if end - t > 120 and (prev is None or geo.dist_m(end_pos(prev), pos) < 250):
            gaps.append((t, end))
        for a, b in gaps:
            if t_stop is not None and a >= t_stop:
                continue
            if ais_moored:
                v.add(Stay(a, b, pos, "moored", heading=hdg, place=hid, status=status))
            else:
                pre = min(9 * 60, (b - a) / 3)
                if a > T_WARM:
                    v.add(Stay(a, a + pre, pos, "moored", heading=hdg, place=hid, status=status))
                v.add(Stay(a + pre if a > T_WARM else a, b - pre, pos, "moored", heading=hdg, place=hid, ais=False, status=status))
                v.add(Stay(b - pre, b, pos, "moored", heading=hdg, place=hid, status=status))

    def out_and_back(self, v, t_dep, names, speed, hold_secs=0, status=0, kind="cg", holds=None):
        """Home -> waypoint(s) -> home on verified water routes. Returns the end time (or None)."""
        pos, hdg, hid = self.home_position(v)
        pts = [pos] + [self.wp(n) for n in names] + [pos]
        keys = [hid] + list(names) + [hid]
        paths = []
        for i in range(len(pts) - 1):
            a, b = keys[i], keys[i + 1]
            fwd = ("w", a, b) in self._paths
            rev = ("w", b, a) in self._paths
            if fwd or not rev:
                paths.append((self.water(pts[i], pts[i + 1], 150.0, key=(a, b)), False))
            else:
                paths.append((self.water(pts[i + 1], pts[i], 150.0, key=(b, a)), True))
        if kind not in ("response", "cg", "survey", "navy") and any(self.uses_ship_channel(p) for p, _ in paths):
            if not self.small_window(t_dep, "gulf"):
                return None
        t = t_dep
        for i, (p, rev) in enumerate(paths):
            t = self.go(v, p, t, speed, rev=rev, slow_start=(i == 0), slow_end=(i == len(paths) - 1), status=status)
            if i < len(paths) - 1:
                secs = (holds[i] if holds else hold_secs)
                if secs:
                    t = self.hold(v, t, secs, pts[i + 1], "drift", radius=60.0, status=status)
        return t

    # ------------------------------------------------------------------ ferries
    def run_ferries(self):
        lanes = {"VSL-0313": ("SLIP-FRY-03", "SLIP-FRY-07", 0.0), "VSL-0314": ("SLIP-FRY-04", "SLIP-FRY-08", 0.5),
                 "VSL-0311": ("SLIP-FRY-01", "SLIP-FRY-05", 0.25), "VSL-0315": ("SLIP-FRY-05", "SLIP-FRY-01", 0.25),
                 "VSL-0312": ("SLIP-FRY-02", "SLIP-FRY-06", 0.75), "VSL-0316": ("SLIP-FRY-06", "SLIP-FRY-02", 0.75)}
        order = ["VSL-0313", "VSL-0314", "VSL-0311", "VSL-0315", "VSL-0312", "VSL-0316"]
        stop1, start1 = local_ts(-1, "09:00"), local_ts(10, "06:00")
        stop2, start2 = BLAST, REOPEN2
        passes = sorted(t for t, _ in self.ship_passes)
        pa = np.array(passes) if passes else np.array([0.0])

        def level(t):
            if stop1 <= t < start1 or stop2 <= t < start2:
                return 0
            h, wd, d = local_hour(t), weekday(t), local_day(t)
            if t < stop1:
                peak = wd >= 5 or d in (-8, -7)          # weekends and Labor Day weekend
                if h < 5.5:
                    return 1
                if h < 8 or h >= 20:
                    return 2
                return 6 if (peak and 9 <= h < 19) else 4
            if t < REOPEN1:
                return 2 if 6 <= h < 22 else 0
            if h < 5.5:
                return 1
            if h < 7 or h >= 19:
                return 2
            return 4 if (wd >= 5 or t < stop2) else 2
        cycle = 22 * 60.0
        for vid in order:
            v = self.vessels[vid]
            a_id, b_id, ph = lanes[vid]
            k = order.index(vid)
            lane_key = tuple(sorted((a_id, b_id)))
            P = self.water(self.spos(lane_key[0]), self.spos(lane_key[1]), 150.0, key=("ferry",) + lane_key)
            rs = rng("ferry", lane_key)                 # boats sharing a lane keep step with each other
            cur = a_id
            t_arr = T_WARM
            t = T_WARM + ph * cycle
            self.home[vid] = (self.spos(a_id), None, a_id)
            while t < T_END:
                if not (k < level(t)):
                    t += 10 * 60
                    continue
                t_go = t + float(rs.uniform(6.5, 9.5)) * 60
                i = int(np.searchsorted(pa, t_go - 240))       # hold for a ship passing the crossing
                while i < len(pa) and pa[i] <= t_go + 420:
                    t_go = max(t_go, pa[i] + 200.0)
                    i += 1
                if level(t_go) == 0 or t_go >= T_END:
                    t = t_go + 60
                    continue
                rev = (cur == lane_key[1])
                m = make_move(P, t_go, speed=5.6 * v.spd, s0=(P.length if rev else 0.0), s1=(0.0 if rev else P.length), status=0)
                v.add(Stay(t_arr, t_go, self.spos(cur), "moored", heading=None, place=cur, status=5))
                v.add(m)
                cur = b_id if cur == a_id else a_id
                t_arr = t = m.t1
            v.add(Stay(t_arr, T_END + 2 * H, self.spos(cur), "moored", heading=None, place=cur, status=5))

    # ------------------------------------------------------------------ the dark tanker and the borrowed identity
    def script_halcyon(self):
        v = self.vessels["VSL-0031"]
        A10, A16 = self.anch["ANCH-10"], self.anch["ANCH-16"]
        dr, rad = 8.6, 250.0
        p_shift = self.open_path(A10, A16, seg=3000.0)

        def vs(lat, lon, s):
            return 2.0 if (s < 250 or s > p_shift.length - 250) else 4.6
        t = T_WARM

        def shift(t_from, st, dwell_h):
            # the anchor watch keeps reporting 'at anchor' while the cable is hove in
            v.add(Stay(t_from, st + 14 * 60, A10, "anchored", place="ANCH-10", status=1, draft=dr, dest="", radius=rad))
            m = make_move(p_shift, st + 14 * 60, vfun=vs, status=0, draft=dr, dest="")
            v.add(m)
            v.add(Stay(m.t1, m.t1 + dwell_h * H + 12 * 60, A16, "anchored", place="ANCH-16", status=1, draft=dr, dest="", radius=rad))
            m2 = make_move(p_shift, m.t1 + dwell_h * H + 12 * 60, vfun=vs, s0=p_shift.length, s1=0.0, status=0, draft=dr, dest="")
            v.add(m2)
            return m2.t1
        for st, dw in ((ts("2027-08-19T14:20Z"), 11.5), (ts("2027-08-27T09:40Z"), 19.0), (ts("2027-08-29T16:10Z"), 9.0), (ts("2027-09-08T22:30Z"), 13.0)):
            t = shift(t, st, dw)
        t_leave, t_back, k = self.halcyon_slot
        v.add(Stay(t, t_leave, A10, "anchored", place="ANCH-10", status=1, draft=dr, dest="", radius=rad))
        t = self.storm_sortie(v, "ANCH-10", t_leave, t_back, dr, k, dest="")
        for st, dw in ((ts("2027-09-24T15:40Z"), 10.0), (ts("2027-10-02T10:10Z"), 16.0), (ts("2027-10-09T19:20Z"), 12.0)):
            t = shift(t, st, dw)
        # --- the night of D+30/31
        v.add(Stay(t, DARK_START, A10, "anchored", place="ANCH-10", status=1, draft=dr, dest="", radius=rad))
        t_go = ts("2027-10-15T03:31Z")
        v.add(Stay(DARK_START, t_go, A10, "anchored", place="ANCH-10", ais=False, status=1, draft=dr, radius=rad))
        Q = mg.dest_point(BOARD, 40.0, 320.0)
        p_q = self.open_path(A10, Q, seg=2000.0)

        def vq(lat, lon, s):
            return 2.5 if (s < 300 or s > p_q.length - 300) else 6.3
        m = make_move(p_q, t_go, vfun=vq, ais=False, status=0, draft=dr)
        v.add(m)
        t_l0, t_l1 = m.t1, ts("2027-10-15T04:43Z")
        v.add(Stay(t_l0, t_l1, Q, "drift", ais=False, radius=140.0, place="off entrance channel", draft=dr))
        m2 = make_move(p_q, t_l1, vfun=vq, s0=p_q.length, s1=0.0, ais=False, status=0, draft=dr)
        v.add(m2)
        H0, hdg0 = swing(m2.t1, A10, rad, v.phase / 3600.0)
        p_h = self.open_path(A10, H0, seg=3000.0) if geo.dist_m(A10, H0) > 5 else None
        t = m2.t1
        if p_h is not None:
            mh = make_move(p_h, t, speed=1.5, ais=False, draft=dr)
            v.add(mh)
            t = mh.t1
        v.add(Stay(t, DARK_END, H0, "hold", heading=hdg0, ais=False, status=1, draft=dr, place="ANCH-10"))
        t_sail = ts("2027-10-18T03:10Z")
        v.add(Stay(DARK_END, t_sail, A10, "anchored", place="ANCH-10", status=1, draft=8.2, dest="", radius=rad))
        self.depart_legs(v, A10, "GATE-YUCATAN", t_sail + 15 * 60, 8.2, "")
        self.dark = dict(H0=H0, hdg=hdg0, Q=Q, t_go=t_go, loiter=(t_l0, t_l1), back=m2.t1, p_q=p_q, m_out=m, m_back=m2)
        # --- the transponder using FV Pelican Ridge's identity: positions a few hundred metres off the hull
        real = self.vessels["VSL-0457"]
        sp = Vessel(dict(real.rec))
        sp.id = "SPOOF-0457"
        sp.radar = False
        sp.phase = 0.0
        off = lambda p: mg.dest_point(p, 205.0, 430.0)
        A10s, Qs = off(A10), off(Q)
        sp.add(Stay(DARK_START + 40, t_go + 120, A10s, "hold", status=7, place=""))
        ps = self.open_path(A10s, Qs, seg=2000.0)
        sp.add(Move(ps, m.kt + 120, m.ks * (ps.length / p_q.length), status=7))
        sp.add(Stay(t_l0 + 120, t_l1 + 120, Qs, "drift", radius=90.0, status=7))
        sp.add(Move(ps, m2.kt + 120, m2.ks * (ps.length / p_q.length), status=7))
        sp.add(Stay(m2.t1 + 120, DARK_END - 30, A10s, "hold", status=7, place=""))
        self.vessels["SPOOF-0457"] = sp

    def script_pelican(self):
        """The real FV Pelican Ridge: working the northeastern Gulf about 600 nm away (satellite feed)."""
        v = self.vessels["VSL-0457"]
        rs = rng("pelican")
        base = self.gates["GATE-CAPE-SAN-BLAS"]
        t = ts("2027-08-11T12:00Z")
        while t < T_END:
            trip = float(rs.uniform(14, 20)) * DAY
            if t <= DARK_START <= t + trip + 4 * DAY and not (t + DAY < DARK_START < t + trip - DAY):
                trip = DARK_START - t + 5 * DAY
            end = min(t + trip, T_END + H)
            p = mg.dest_point(base, float(rs.uniform(0, 360)), float(rs.uniform(2000, 15000)))
            tt = t
            while tt < end:
                q = mg.dest_point(base, float(rs.uniform(150, 290)), float(rs.uniform(4000, 46000)))
                if self.G.is_land(*q) or geo.gc_nm(q, SEA) < 560 or geo.gc_nm(q, SEA) > 640:
                    continue
                path = self.GM.open_leg(p, q, max_seg_m=14000.0)
                m = make_move(path, tt, speed=float(rs.uniform(2.5, 3.2)), status=7, draft=2.1, dest="")
                v.add(m)
                tt, p = m.t1, q
                if rs.random() < 0.25:
                    v.add(Stay(tt, tt + float(rs.uniform(3, 7)) * H, p, "drift", radius=300.0, status=7, draft=2.1))
                    tt = v.itin[-1].t1
            t = tt + float(rs.uniform(3, 5)) * DAY

    def script_narwhal(self):
        v = self.vessels["VSL-0481"]
        slip = self.spos("SLIP-ING-07")
        P = self.water(slip, SEA, 150.0, key=("SLIP-ING-07", "SEA"))
        t_arr = ts("2027-09-02T21:05Z")
        probe = make_move(P, 0.0, speed=11.0)
        t_sea = t_arr - probe.t1
        self.arrive_legs(v, "GATE-FLORIDA-STRAITS", SEA, t_sea, 1.7, dest_txt="INGLESIDE")
        self.go(v, P, t_sea, 11.0, rev=True, draft=1.7, dest="INGLESIDE")
        last = ts("2027-09-07T00:14Z")
        v.add(Stay(v.busy_until, last + 20, slip, "moored", heading=118.0, place="SLIP-ING-07", status=5, draft=1.7, dest="INGLESIDE"))
        v.last_fix = last
        v.phase = last % 3600.0
        v.nojit = True
        t_out = ts("2027-09-07T03:32Z")
        v.add(Stay(last + 20, t_out, slip, "moored", heading=118.0, place="SLIP-ING-07", ais=False, status=5, draft=1.7))
        t = self.go(v, P, t_out, 9.5, ais=False, draft=1.7)
        self.depart_legs(v, SEA, "GATE-FLORIDA-STRAITS", t, 1.7, "")
        for s in v.itin:
            if s.t0 >= t - 1:
                s.ais = False

    # ------------------------------------------------------------------ the fuel barge
    def tow(self, tug, barge, P, t, speed, rev=False, lead=38.0, **kw):
        """Towboat pushing a barge along P; the barge's bow leads by `lead` metres."""
        L = P.length

        def vf(lat, lon, s):
            edge = (s < 250 or s > L - 250)
            return 2.2 if edge else min(speed, self.channel_speed(lat, lon) * 0.62 if lon < -97.3957 else speed)
        mb = make_move(P, t, vfun=vf, s0=(L if rev else 0.0), s1=(0.0 if rev else L), status=0, **kw)
        ks = np.clip(mb.ks - (lead if not rev else -lead), 0.0, L)
        tug.add(Move(P, mb.kt, ks, status=0, **kw))
        if barge is not None:
            barge.add(mb)
        la, lo, _ = P.at(float(ks[-1]))
        return mb.t1, (la, lo)

    def tow_duration(self, P, speed, rev=False):
        L = P.length

        def vf(lat, lon, s):
            edge = (s < 250 or s > L - 250)
            return 2.2 if edge else min(speed, self.channel_speed(lat, lon) * 0.62 if lon < -97.3957 else speed)
        return make_move(P, 0.0, vfun=vf, s0=(L if rev else 0.0), s1=(0.0 if rev else L)).t1

    def script_tow44(self):
        tug, brg = self.vessels["VSL-0294"], self.vessels["BRG-0044"]
        d = self.dark
        fleet = self.bpos("TERM-19-B01")
        self.home["BRG-0044"] = (fleet, 106.0, "TERM-19-B01")
        thome, thdg, thid = self.home_position(tug)
        side = mg.dest_point(d["H0"], d["hdg"] + 90.0, 55.0)
        P1 = mg.join(self.ship_path("TERM-19-B01").reversed(), self.open_path(SEA, side, seg=3000.0))
        t_arr = ts("2027-10-15T09:14Z")
        # make up the tow
        A = self.nav(thome, fleet, 0.0, start_at=thome, end_at=fleet, key=("tow44", "a"))
        t_dep = t_arr - self.tow_duration(P1, 6.3)
        t0 = self.go(tug, A, t_dep - 42 * 60, 4.0)
        tug.add(Stay(t0, t_dep, fleet, "hold", place="TERM-19-B01"))
        t1, tpos = self.tow(tug, brg, P1, t_dep, 6.3, dest="")
        t_off = ts("2027-10-15T12:47Z")
        tug.add(Stay(t1, t_off, tpos, "hold", place="alongside"))
        brg.add(Stay(t1, t_off, side, "hold", place="alongside"))
        # back in through the jetties to the Redfish Bay fleet for the night
        P2 = mg.join(self.open_path(side, SEA, seg=3000.0), self.ship_path("TERM-26-B01"))
        t2, tpos2 = self.tow(tug, brg, P2, t_off, 6.3, dest="")
        t_next = ts("2027-10-16T13:06Z")
        f26 = self.bpos("TERM-26-B01")
        tug.add(Stay(t2, t_next, tpos2, "moored", heading=47.0, place="TERM-26-B01", status=5))
        brg.add(Stay(t2, t_next, f26, "moored", heading=47.0, place="TERM-26-B01", status=5))
        # D+32: up the ship channel to the fuel terminal
        q = self.bpos("TERM-02-B01")
        P3 = self.nav(f26, q, 0.0, start_at=f26, end_at=q, key=("tow44", "c"))
        t3, tpos3 = self.tow(tug, brg, P3, t_next, 6.3, dest="CORPUS CHRISTI")
        t_done = ts("2027-10-17T14:10Z")
        tug.add(Stay(t3, t_done, tpos3, "moored", heading=105.0, place="TERM-02-B01", status=5))
        brg.add(Stay(t3, t_done, q, "moored", heading=105.0, place="TERM-02-B01", status=5))
        P4 = self.nav(q, fleet, 0.0, start_at=q, end_at=fleet, key=("tow44", "d"))
        t4, tpos4 = self.tow(tug, brg, P4, t_done, 3.5, dest="")
        B = self.nav(tpos4, thome, 0.0, start_at=tpos4, end_at=thome, key=("tow44", "e"))
        tug.add(Stay(t4, t4 + 15 * 60, tpos4, "hold", place="TERM-19-B01"))
        self.go(tug, B, t4 + 15 * 60, 4.0)
        self.tow44 = dict(alongside=(t1, t_off), deliver=(t_next, t3), side=side)

    def run_bunker_barges(self):
        """Routine fuel-barge runs inside the port by the same towboat (Barge 42 mostly)."""
        tug = self.vessels["VSL-0294"]
        rs = rng("bunker")
        fleet = self.bpos("TERM-19-B01")
        thome, _, _ = self.home_position(tug)
        self.home["BRG-0042"] = (mg.dest_point(fleet, 106.0, 70.0) if self.GM.point_ok(mg.dest_point(fleet, 106.0, 70.0)) else fleet, 106.0, "TERM-19-B01")
        if "BRG-0044" not in self.home:
            self.home["BRG-0044"] = (fleet, 106.0, "TERM-19-B01")
        t = T_WARM + 1.3 * DAY
        targets = ["TERM-17-B02", "TERM-07-B03", "TERM-13-B02", "TERM-18-B01", "TERM-04-B02", "TERM-15-B02", "TERM-11-B01", "TERM-12-B01"]
        while t < T_END - DAY:
            t += float(rs.uniform(1.6, 3.4)) * DAY
            h = local_hour(t)
            t += ((13 - h) % 24) * H * 0.5
            ok = (t < YANKEE - 30 * H) or (REOPEN1 + DAY <= t < BLAST - DAY) or (t >= REOPEN2 + DAY)
            if not ok:
                continue
            bid = targets[int(rs.integers(0, len(targets)))]
            if self.berths[bid]["zone"] == "inner_w" and REOPEN1 <= t < REOPEN2 and False:
                continue
            barge = self.vessels["BRG-0042" if rs.random() < 0.8 else "BRG-0044"]
            bhome = self.home[barge.id][0]
            q = self.bpos(bid)
            # barge lies outboard of whatever ship is at the berth: stop 60 m short on the channel side
            P = self.nav(bhome, q, 0.0, start_at=bhome, end_at=q, key=("bunk", barge.id, bid))
            probe = make_move(P, 0.0, speed=3.6)
            dur = probe.t1 * 2 + 5.5 * H
            if not (self.idle(tug, t - H, t + dur + H) and self.idle(barge, t - H, t + dur + H)):
                continue
            A = self.nav(thome, bhome, 0.0, start_at=thome, end_at=bhome, key=("bunk", "a", barge.id))
            t0 = self.go(tug, A, t - 30 * 60, 4.0)
            tug.add(Stay(t0, t, bhome, "hold", place="TERM-19-B01"))
            t1, tp = self.tow_short(tug, barge, P, t, 3.6, stop_short=70.0)
            stay = float(rs.uniform(3.0, 5.0)) * H
            la, lo, _ = P.at(P.length - 70.0)
            tug.add(Stay(t1, t1 + stay, tp, "hold", place=bid))
            barge.add(Stay(t1, t1 + stay, (la, lo), "hold", place=bid))
            t2, tp2 = self.tow_short(tug, barge, P, t1 + stay, 3.6, rev=True, stop_short=70.0)
            B = self.nav(tp2, thome, 0.0, start_at=tp2, end_at=thome, key=("bunk", "b", barge.id))
            tug.add(Stay(t2, t2 + 12 * 60, tp2, "hold", place="TERM-19-B01"))
            self.go(tug, B, t2 + 12 * 60, 4.0)
            t = t2 + H

    def tow_short(self, tug, barge, P, t, speed, rev=False, stop_short=0.0, lead=38.0):
        L = P.length
        lo_s, hi_s = 0.0, L - stop_short
        mb = make_move(P, t, speed=speed, s0=(hi_s if rev else lo_s), s1=(lo_s if rev else hi_s), status=0)
        ks = np.clip(mb.ks - lead, 0.0, L)
        tug.add(Move(P, mb.kt, ks, status=0))
        barge.add(mb)
        la, lo, _ = P.at(float(ks[-1]))
        return mb.t1, (la, lo)

    # ------------------------------------------------------------------ the tug at the jetties (D+44)
    def script_blast(self):
        cb = self.vessels["VSL-0077"]
        plan = self.escort_plan
        escort, res = plan["escort"]
        a0, b1, end_pt, B, bmove = res
        cb.itin.remove(bmove)
        # the tug turns back in from the jetty tips and is half-way along the jetty channel at 06:10Z
        t_turn = bmove.t0 + 150
        m = make_move(B, t_turn, speed=7.4)
        s_blast = m.s_at(BLAST)
        la, lo, brg = B.at(s_blast)
        self.blast_point = (la, lo)
        kt = [t_turn] + [float(k) for k in m.kt if t_turn < k < BLAST] + [BLAST]
        cb.add(Stay(bmove.t0 - 90, t_turn, end_pt, "hold", status=0, place="jetty channel"))     # turning round off the jetty tips
        cb.add(Move(B, kt, [m.s_at(k) for k in kt], status=0))
        t_tow = ts("2027-10-28T09:40Z")
        cb.add(Stay(BLAST, t_tow, self.blast_point, "hold", heading=brg, status=2, place="jetty channel"))
        yard = self.bpos("TERM-20-B01")
        Ptow = self.nav(self.blast_point, yard, 0.0, start_at=self.blast_point, end_at=yard, key=("blast", "tow"))
        lq = self.vessels["VSL-0271"]
        mt = make_move(Ptow, t_tow, speed=4.6, status=2)
        cb.add(mt)
        cb.add(Stay(mt.t1, T_END + 2 * H, yard, "moored", heading=92.0, place="TERM-20-B01", status=5))
        self.free_at["VSL-0077"] = 1e18
        # Laguna Queen comes out for her, tows her to the yard, and goes home
        lhome, _, _ = self.home_position(lq)
        A = self.nav(lhome, self.blast_point, 0.0, start_at=lhome, end_at=self.blast_point, key=("blast", "lq"))
        probe = make_move(A, 0.0, vfun=self.tug_vfun(A, lq))
        ta = t_tow - 20 * 60 - probe.t1
        if self.idle(lq, ta - 60, mt.t1 + 3 * H):
            L = A.length
            ma = make_move(A, ta, vfun=self.tug_vfun(A, lq), s0=0.0, s1=L - 60.0)
            lq.add(ma)
            la2, lo2, _ = A.at(L - 60.0)
            lq.add(Stay(ma.t1, t_tow, (la2, lo2), "hold", place="jetty channel"))
            ks = np.clip(mt.ks + 45.0, 0.0, Ptow.length - 60.0)
            lq.add(Move(Ptow, mt.kt, ks, status=0))
            la3, lo3, _ = Ptow.at(float(ks[-1]))
            Bq = self.nav((la3, lo3), lhome, 0.0, start_at=(la3, lo3), end_at=lhome, key=("blast", "lqhome"))
            lq.add(Stay(mt.t1, mt.t1 + 25 * 60, (la3, lo3), "hold", place="TERM-20-B01"))
            self.go(lq, Bq, mt.t1 + 25 * 60, 4.5)
        # Coast Guard boats from Station Port Aransas converge within minutes; a patrol boat follows
        for vid, t_go, off in (("VSL-0325", BLAST + 4.5 * 60, (20.0, 70.0)), ("VSL-0326", BLAST + 7 * 60, (200.0, 90.0)), ("VSL-0323", BLAST + 16 * 60, (110.0, 260.0))):
            b = self.vessels[vid]
            hp, _, hid = self.home_position(b)
            tgt = mg.dest_point(self.blast_point, off[0], off[1])
            if self.G.is_land(*tgt) or not self.GM.clear(self.blast_point, tgt, 4.0):
                tgt = self.blast_point
            Pc = self.water(hp, tgt, 150.0, key=("blast", vid))
            t1 = self.go(b, Pc, t_go, 24.0 if vid != "VSL-0323" else 17.0, status=0)
            t_rel = t_tow + (20 + 25 * (vid == "VSL-0326")) * 60 if vid != "VSL-0323" else ts("2027-10-28T15:00Z")
            b.add(Stay(t1, t_rel, tgt, "hold", status=0, place="jetty channel"))
            self.go(b, Pc, t_rel, 14.0, rev=True)

    # ------------------------------------------------------------------ Navy and Coast Guard search (D+46 to D+58)
    def script_search(self):
        usns = self.vessels["VSL-0341"]
        # spill support earlier in the scenario: alongside the cargo docks D+4 to D+22
        berth = self.bpos("TERM-07-B04")
        Pin = self.ship_path("TERM-07-B04")
        t_arr = ts("2027-09-18T19:00Z")
        probe = make_move(Pin, 0.0, vfun=self.ship_vfun(Pin, 1.0))
        self.arrive_legs(usns, "GATE-SWPASS", SEA, t_arr - probe.t1, 5.5, dest_txt="CORPUS CHRISTI")
        m = make_move(Pin, t_arr - probe.t1, vfun=self.ship_vfun(Pin, 1.0), status=0, draft=5.5, dest="CORPUS CHRISTI")
        usns.add(m)
        t_dep = ts("2027-10-06T14:00Z")
        usns.add(Stay(m.t1, t_dep, berth, "moored", heading=89.0, place="TERM-07-B04", status=5, draft=5.5))
        Pout = Pin.reversed()
        m2 = make_move(Pout, t_dep, vfun=self.ship_vfun(Pout, 1.0), status=0, draft=5.5, dest="NORFOLK")
        usns.add(m2)
        self.depart_legs(usns, SEA, "GATE-SWPASS", m2.t1, 5.5, "NORFOLK")
        # back for the channel search: anchors close to the sea buoy as the dive support platform
        A1 = self.anch["ANCH-01"]
        t_on = ts("2027-10-29T23:30Z")
        self.arrive_legs(usns, "GATE-SWPASS", A1, t_on, 5.5, dest_txt="CORPUS CHRISTI")
        t_off = REOPEN2 + 3 * H
        usns.add(Stay(t_on, t_off, A1, "anchored", place="ANCH-01", status=1, draft=5.5, radius=180.0))
        self.anch_busy["ANCH-01"].append((t_on - H, t_off + H, usns.id))
        self.depart_legs(usns, A1, "GATE-SWPASS", t_off + 12 * 60, 5.5, "NORFOLK")
        # search lanes: the sea bar and jetty channels, in parallel lines either side of the centerline
        inner = (27.8425, -97.0545)
        base = self.nav(inner, SEA, 0.0, key=("search", "base"))
        lanes = [base] + [self.offset_path(("search",), base, d) for d in (45.0, -45.0, 80.0, -80.0)]
        lanes = [l for i, l in enumerate(lanes) if i == 0 or l.pts != base.pts]
        find_pt = mg.dest_point((27.8105, -96.9960), 200.0, 380.0)
        boats = [self.vessels[i] for i in ("VSL-0342", "VSL-0343", "VSL-0344")]
        rs = rng("search")
        for b in boats:
            hp, _, hid = self.home_position(b)
            join_pt = base.pts[0]
            Pa = self.water(hp, join_pt, 150.0, key=("search", b.id))
            t_first = ts("2027-10-29T21:00Z")
            b.add(Stay(t_first, local_ts(46, "07:10"), hp, "moored", heading=None, place=hid, status=5))
            for day in range(46, 58):
                t = local_ts(day, "07:20") + boats.index(b) * 9 * 60 + float(rs.uniform(0, 8)) * 60
                t = self.go(b, Pa, t, 14.0, status=3)
                n = 0
                t_stop = local_ts(day, "16:40")
                while t < t_stop:
                    lane = lanes[int(rs.integers(0, len(lanes)))]
                    if day == 52 and local_ts(52, "09:20") <= t < local_ts(52, "15:30"):
                        # the second device: boats close on the find and hold there
                        cur = lane.pts[-1] if n % 2 else lane.pts[0]
                        Pf = self.GM.water_path(cur, find_pt, 150.0)
                        t = self.go(b, Pf, t, 9.0, status=3, slow_start=False)
                        t = self.hold(b, t, local_ts(52, "15:40") - t, mg.dest_point(find_pt, 120.0 * boats.index(b), 60.0 + 40.0 * boats.index(b)), "drift",
                                      radius=35.0, status=3, place="near entrance channel")
                        back_to = lane.pts[0]
                        Pb = self.GM.water_path(find_pt, back_to, 150.0)
                        t = self.go(b, Pb, t, 9.0, status=3, slow_end=False)
                        n = 0
                        continue
                    L = lane.length
                    m = make_move(lane, t, speed=float(rs.uniform(4.2, 5.4)), s0=(L if n % 2 else 0.0), s1=(0.0 if n % 2 else L), status=3)
                    b.add(m)
                    t = m.t1 + 120
                    n += 1
                # finish at the inner end
                if n % 2:
                    L = lanes[0].length
                    m = make_move(lanes[0], t, speed=8.0, s0=L, s1=0.0, status=3)
                    b.add(m)
                    t = m.t1
                t = self.go(b, Pa, t + 60, 12.0, rev=True, status=0)
                nxt = local_ts(day + 1, "07:10") if day < 57 else REOPEN2 + 26 * H
                b.add(Stay(t, nxt, hp, "moored", heading=None, place=hid, status=5))
        # Coast Guard security zone: one response boat on station off the jetty tips in six-hour watches
        cg = [self.vessels[i] for i in ("VSL-0325", "VSL-0326", "VSL-0327")]
        post = self.wp("jetty_tips")
        t = ts("2027-10-28T18:00Z")
        i = 0
        while t < REOPEN2 - 2 * H:
            b = cg[i % 3]
            hp, _, hid = self.home_position(b)
            Pc = self.water(hp, post, 150.0, key=(hid, "jetty_tips"))
            if self.idle(b, t - 600, t + 6.6 * H):
                t1 = self.go(b, Pc, t, 20.0)
                b.add(Stay(t1, t + 6.1 * H, post, "drift", radius=120.0, place="security zone"))
                self.go(b, Pc, t + 6.1 * H, 18.0, rev=True)
            t += 6 * H
            i += 1

    # ------------------------------------------------------------------ spill response
    def run_response(self):
        rs = rng("response")
        base_id = "TERM-24-B01"
        big = self.vessels["VSL-0351"]
        sk = [self.vessels[i] for i in ("VSL-0352", "VSL-0353", "VSL-0354", "VSL-0355")]
        berth = self.bpos("TERM-01-B07")
        # working points on the Inner Harbor centerline near the berth, and just outside the Harbor Bridge
        n0, _ = self.G.nav.nearest(berth)
        work = self.G.nav.nodes[n0]
        e0 = self.G.nav.nodes[self.G.nav.nearest((27.8108, -97.3835))[0]]
        mtb_w = self.G.nav.nodes[self.G.nav.nearest((27.8137, -97.4110))[0]]
        mtb_e = self.G.nav.nodes[self.G.nav.nearest((27.8133, -97.3990))[0]]
        sweep = self.nav(mtb_w, mtb_e, 0.0, key=("resp", "sweep"))
        shore = {"north_beach": self.wp("north_beach"), "indian_pt": self.wp("indian_pt"), "portland": self.wp("portland"),
                 "nueces_e": self.wp("nueces_e"), "nueces": self.wp("nueces"), "nueces_w": self.wp("nueces_w")}

        def sortie_inner(v, day, start, hours):
            hp, _, _ = self.home_position(v)
            A = self.nav(hp, mtb_w, 0.0, start_at=hp, key=("resp", "in", v.id))
            t = local_ts(day, start) + float(rs.uniform(0, 25)) * 60
            if not self.idle(v, t - 600, t + (hours + 2.5) * H):
                return
            t = self.go(v, A, t, 6.5, status=3)
            t_stop = t + hours * H
            n = 0
            L = sweep.length
            lanes = [sweep]
            while t < t_stop:
                m = make_move(sweep, t, speed=float(rs.uniform(1.2, 2.2)), s0=(L if n % 2 else 0.0), s1=(0.0 if n % 2 else L), status=3)
                v.add(m)
                t = m.t1 + float(rs.uniform(2, 9)) * 60
                n += 1
            if n % 2:
                m = make_move(sweep, t, speed=4.0, s0=L, s1=0.0, status=3)
                v.add(m)
                t = m.t1
            self.go(v, A, t + 60, 6.5, rev=True, status=0)

        def sortie_shore(v, day, start, hours, names):
            hp, _, _ = self.home_position(v)
            A = self.nav(hp, e0, 0.0, start_at=hp, key=("resp", "out", v.id))
            t = local_ts(day, start) + float(rs.uniform(0, 25)) * 60
            if not self.idle(v, t - 600, t + (hours + 4.0) * H):
                return
            t = self.go(v, A, t, 6.5, status=0)
            cur, ckey = e0, "resp_e0"
            t_stop = t + hours * H
            k = 0
            while t < t_stop:
                nm = names[k % len(names)]
                P = self.water(cur, shore[nm], 150.0, key=(ckey, nm))
                t = self.go(v, P, t, 7.0 if k == 0 else 2.4, status=3, slow_start=False, slow_end=False)
                t = self.hold(v, t, float(rs.uniform(20, 55)) * 60, shore[nm], "drift", radius=45.0, status=3, place="shoreline")
                cur, ckey = shore[nm], nm
                k += 1
            P = self.water(cur, e0, 150.0, key=(ckey, "resp_e0"))
            t = self.go(v, P, t, 7.0, status=0, slow_start=False, slow_end=False)
            self.go(v, A, t + 30, 6.5, rev=True, status=0)

        # a monthly drill before the storm
        for v in (sk[0], sk[2]):
            sortie_inner(v, -20, "09:00", 2.5)
        sortie_shore(sk[3], -20, "09:10", 2.0, ["north_beach", "indian_pt"])
        for day in range(2, 61):
            if day >= 44 and day % 3 != 0:
                continue                                   # monitoring only
            first = (day == 2)
            st = "10:05" if first else "07:15"
            if day < 21:
                sortie_inner(sk[0], day, st, 8.0 if not first else 6.0)
                sortie_inner(sk[1], day, st, 8.0 if not first else 6.0)
                sortie_shore(sk[2], day, st, 6.5 if not first else 5.0, ["north_beach", "indian_pt", "portland"] if day % 2 == 0 else ["nueces_e", "nueces", "nueces_w"])
                sortie_shore(sk[3], day, st, 6.0 if not first else 5.0, ["nueces_e", "nueces"] if day % 2 == 0 else ["portland", "indian_pt", "north_beach"])
            elif day < 44:
                sortie_inner(sk[day % 2], day, st, 5.0)
                sortie_shore(sk[2 + day % 2], day, st, 5.0, ["north_beach", "portland"] if day % 2 else ["nueces_e", "nueces", "nueces_w"])
            else:
                sortie_shore(sk[2], day, "08:00", 4.0, ["north_beach", "nueces_e", "portland"])
        # the response vessel lies off the berth as the on-scene platform D+2 to D+20, home each evening
        hp, _, _ = self.home_position(big)
        A = self.nav(hp, work, 0.0, start_at=hp, key=("resp", "big"))
        la, lo, _ = A.at(A.length - 40.0)
        for day in range(2, 21):
            t = local_ts(day, "10:20" if day == 2 else "06:50")
            probe = make_move(A, 0.0, speed=5.0, s1=A.length - 40.0)
            m = make_move(A, t, speed=5.0, s1=A.length - 40.0, status=3)
            big.add(m)
            t_back = local_ts(day, "18:30")
            big.add(Stay(m.t1, t_back, (la, lo), "hold", status=3, place="Inner Harbor"))
            big.add(make_move(A, t_back, speed=5.0, s0=A.length - 40.0, s1=0.0, status=0))

    # ------------------------------------------------------------------ everyday craft
    def run_patrols(self):
        rs = rng("patrol")
        V = self.vessels
        # Coast Guard small boats from Station Port Aransas
        routes = [["jetty_tips", "anch_w"], ["jetty_tips", "anch_s", "anch_e"], ["lydia"], ["lydia", "aransas_bay"], ["jetty_tips"],
                  ["redfish"], ["cc_e"], ["anch_w", "anch_e"]]
        for vid, per_day in (("VSL-0325", 1.3), ("VSL-0326", 1.0), ("VSL-0327", 0.8), ("VSL-0328", 0.5), ("VSL-0329", 0.35)):
            b = V[vid]
            t = T_WARM + float(rs.uniform(0, 1)) * DAY
            while t < T_END - 6 * H:
                t += float(rs.exponential(1.0 / per_day)) * DAY
                h = local_hour(t)
                if not (6 <= h <= 21) and rs.random() < 0.8:
                    t += ((8 - h) % 24) * H
                if not self.small_window(t, "cg") or BLAST - 2 * H <= t < REOPEN2:
                    continue
                r = routes[int(rs.integers(0, len(routes)))]
                if vid == "VSL-0329":
                    r = [["redfish"], ["lydia", "aransas_bay"], ["cc_e"], ["aransas_e"]][int(rs.integers(0, 4))]
                if local_day(t) in (1, 2, 3, 4, 5) and vid != "VSL-0329":
                    r = [["cc_e", "cc_mid"], ["redfish"], ["lydia", "aransas_bay"], ["cc_e", "cc_n"]][int(rs.integers(0, 4))]   # search and rescue in the bays
                sp = 22.0 if vid != "VSL-0329" else 16.0
                est = 3.5 * H
                if not self.idle(b, t - 900, t + est + 3 * H):
                    continue
                self.out_and_back(b, t, r, sp * b.spd, hold_secs=float(rs.uniform(8, 30)) * 60, kind="cg")
        # the 87-ft patrol boat: longer daily patrols of the bays, the channel and the anchorage
        b = V["VSL-0323"]
        t = T_WARM + 0.4 * DAY
        longr = [["jetty_tips", "anch_w", "anch_e", "anch_s"], ["lydia", "aransas_bay", "aransas_n"], ["cc_e", "cc_mid", "cc_n"], ["jetty_tips", "anch_s"]]
        while t < T_END - 10 * H:
            t += float(rs.uniform(0.8, 1.7)) * DAY
            if not self.small_window(t, "cg") or BLAST - 3 * H <= t < BLAST + 12 * H:
                continue
            r = longr[int(rs.integers(0, len(longr)))]
            if self.idle(b, t - 900, t + 9 * H):
                self.out_and_back(b, t, r, 15.0 * b.spd, hold_secs=float(rs.uniform(15, 50)) * 60, kind="cg")
        # port police in the Inner Harbor and La Quinta; fireboat and game warden occasionally
        pp = V["VSL-0492"]
        hp, _, hid = self.home_position(pp)
        ends = [self.bpos("TERM-05-B02"), self.bpos("TERM-11-B01"), self.bpos("TERM-17-B01"), self.bpos("TERM-03-B01")]
        t = T_WARM + 0.2 * DAY
        while t < T_END - 5 * H:
            t += float(rs.uniform(0.45, 1.1)) * DAY
            if QUIET_FROM <= t < QUIET_TO:
                continue
            k = int(rs.integers(0, len(ends)))
            tgt = self.G.nav.nodes[self.G.nav.nearest(ends[k])[0]]
            P = self.nav(hp, tgt, 0.0, start_at=hp, key=("pp", k))
            probe = make_move(P, 0.0, speed=9.0)
            if not self.idle(pp, t - 600, t + probe.t1 * 2 + 40 * 60):
                continue
            t1 = self.go(pp, P, t, 9.0 if k < 3 else 16.0)
            t1 = self.hold(pp, t1, float(rs.uniform(5, 20)) * 60, tgt, "hold")
            self.go(pp, P, t1, 9.0 if k < 3 else 16.0, rev=True)
        for vid, names, gap, kind in (("VSL-0493", [["cc_w"], ["north_beach"], ["cc_w", "cc_mid"]], (5, 11), "cg"),
                                      ("VSL-0491", [["aransas_n"], ["copano", "copano_e"], ["aransas_bay", "aransas_e"], ["aransas_n", "copano_e"]], (1.2, 3.0), "cg")):
            b = V[vid]
            t = T_WARM + 0.5 * DAY
            while t < T_END - 6 * H:
                t += float(rs.uniform(*gap)) * DAY
                h = local_hour(t)
                t += ((9 - h) % 24) * H * (1.0 if not 7 <= h <= 15 else 0.0)
                if not self.small_window(t, "cg") or (vid == "VSL-0491" and STORM_STOP <= t < ts("2027-09-19T12:00Z")):
                    continue
                r = names[int(rs.integers(0, len(names)))]
                if self.idle(b, t - 600, t + 7 * H):
                    self.out_and_back(b, t, r, 19.0 * b.spd, hold_secs=float(rs.uniform(10, 40)) * 60, kind=kind)

    def run_cutters(self):
        rs = rng("cutters")
        V = self.vessels
        storm_lo, storm_hi = YANKEE - 40 * H, QUIET_TO
        blast_lo, blast_hi = BLAST - 6 * H, BLAST + 8 * H
        for vid, away_d, in_d, spd in (("VSL-0321", (16, 22), (5, 8), 13.0), ("VSL-0322", (3, 5), (1.5, 3.5), 18.0)):
            v = V[vid]
            hp, hdg, hid = self.home_position(v)
            Pout = self.nav(hp, SEA, 0.0, start_at=hp, key=("cut", vid))
            Pgo = self.open_path(OFFING, SEA, seg=6000.0)
            fac = min(1.25, spd / 11.0)
            dur = make_move(Pout, 0.0, vfun=self.ship_vfun(Pout, fac)).t1
            t_in = T_WARM                                   # time the cutter last arrived alongside
            t = T_WARM + float(rs.uniform(1, 4)) * DAY      # next departure
            while t < T_END - DAY:
                away = float(rs.uniform(*away_d)) * DAY
                if storm_lo <= t < storm_hi:                # in port as the storm approaches: put to sea before Yankee
                    if t_in <= YANKEE - 18 * H:
                        t = max(t_in + 4 * H, YANKEE - float(rs.uniform(10, 16)) * H)
                        away = (ts("2027-09-15T16:00Z") if vid == "VSL-0322" else ts("2027-09-16T13:00Z")) - t
                    else:
                        t = storm_hi + 6 * H
                if blast_lo <= t < blast_hi:
                    t = blast_hi + float(rs.uniform(1, 5)) * H
                t_ret = t + away                            # time back alongside
                if QUIET_FROM - 4 * H <= t_ret < QUIET_TO + 4 * H:
                    t_ret = QUIET_TO + float(rs.uniform(4, 9)) * H
                if blast_lo <= t_ret - dur < blast_hi + dur:
                    t_ret = blast_hi + dur + float(rs.uniform(1, 4)) * H
                m = make_move(Pout, t, vfun=self.ship_vfun(Pout, fac), status=0, draft=v.draft_max)
                v.add(m)
                t_gate = self.depart_legs(v, SEA, "GATE-OFFING", m.t1, v.draft_max, "")
                t_sea = t_ret - dur
                t_off = t_sea - Pgo.length / (spd * KN)
                if t_off < t_gate + 2 * H:
                    t_off = t_gate + 2 * H
                    t_sea = t_off + Pgo.length / (spd * KN)
                v.add(make_move(Pgo, t_off, speed=spd, draft=v.draft_max))
                m2 = make_move(Pout, t_sea, vfun=self.ship_vfun(Pout, fac), s0=Pout.length, s1=0.0, status=0, draft=v.draft_max)
                v.add(m2)
                t_in = m2.t1
                t = t_in + float(rs.uniform(*in_d)) * DAY
        # buoy tender: day trips along the channel, standing off aids for a while; channel aids verified after the storm
        v = V["VSL-0324"]
        hp, hdg, hid = self.home_position(v)
        Pch = self.nav(hp, SEA, 0.0, start_at=hp, key=("cut", "tender"))
        t = T_WARM + 2 * DAY
        while t < T_END - DAY:
            d = local_day(t)
            gap = float(rs.uniform(4, 9)) if not (1 <= d <= 12) else float(rs.uniform(0.9, 1.3))
            t += gap * DAY
            h = local_hour(t)
            t += ((7.5 - h) % 24) * H
            if QUIET_FROM - 30 * H <= t < QUIET_TO or BLAST - 20 * H <= t < BLAST + 30 * H:
                continue
            L = Pch.length
            far = float(rs.uniform(0.35, 1.0)) * L
            tt = t
            s = 0.0
            stops = sorted(float(x) for x in rs.uniform(0.1 * far, far, int(rs.integers(3, 7))))
            if not self.idle(v, t - 600, t + 14 * H):
                continue
            for st in stops + [None]:
                tgt = st if st is not None else far
                m = make_move(Pch, tt, vfun=lambda la, lo, s_: min(9.5, self.channel_speed(la, lo)), s0=s, s1=tgt, status=3, draft=v.draft_max)
                v.add(m)
                tt, s = m.t1, tgt
                if st is not None:
                    la, lo, _ = Pch.at(s)
                    tt = self.hold(v, tt, float(rs.uniform(25, 70)) * 60, (la, lo), "hold", status=3, draft=v.draft_max)
            m = make_move(Pch, tt + 300, vfun=lambda la, lo, s_: min(10.5, self.channel_speed(la, lo)), s0=s, s1=0.0, status=0, draft=v.draft_max)
            v.add(m)
            t = m.t1

    def run_survey_dredge_research(self):
        rs = rng("survey")
        V = self.vessels
        sv = V["VSL-0362"]
        hp, _, hid = self.home_position(sv)
        inner = (27.8425, -97.0545)
        a_in = self.water(hp, inner, 150.0, key=(hid, "survey_in"))
        reaches = [((27.8425, -97.0545), SEA), ((27.8425, -97.0545), (27.8250, -97.1700)), ((27.8250, -97.1700), (27.8105, -97.2800)),
                   ((27.8105, -97.2800), (27.8103, -97.3800))]
        t = T_WARM + DAY
        while t < T_END - DAY:
            d = local_day(t)
            busy = (1 <= d <= 29) or (44 <= d <= 58)
            t += (float(rs.uniform(0.95, 1.3)) if busy else float(rs.uniform(5, 9))) * DAY
            h = local_hour(t)
            t += ((7.2 - h) % 24) * H
            if QUIET_FROM - 40 * H <= t < QUIET_TO or BLAST <= t < BLAST + 30 * H:
                continue
            k = int(rs.integers(0, len(reaches))) if not (44 <= local_day(t) <= 58) else 0
            a, b = reaches[k]
            base = self.nav(a, b, 0.0, key=("survey", k))
            lines = [base] + [x for x in (self.offset_path(("survey", k), base, d_) for d_ in (30.0, -30.0, 60.0, -60.0)) if x.pts != base.pts]
            if not self.idle(sv, t - 600, t + 11 * H):
                continue
            tt = self.go(sv, a_in, t, 13.0, status=0)
            if k > 0:
                link = self.nav(inner, a, 0.0, key=("survey", "link", k))
                tt = self.go(sv, link, tt, 12.0, status=0, slow_start=False, slow_end=False)
            n = 0
            for ln in lines[:max(1, min(len(lines), int(rs.integers(3, 6))))]:
                m = make_move(ln, tt, speed=float(rs.uniform(5.5, 6.5)), s0=(ln.length if n % 2 else 0.0), s1=(0.0 if n % 2 else ln.length), status=3)
                sv.add(m)
                tt = m.t1 + 90
                n += 1
            if n % 2:
                m = make_move(base, tt, speed=11.0, s0=base.length, s1=0.0, status=0)
                sv.add(m)
                tt = m.t1
            if k > 0:
                tt = self.go(sv, link, tt, 12.0, rev=True, status=0, slow_start=False, slow_end=False)
            t = self.go(sv, a_in, tt, 13.0, rev=True, status=0)
        # dredge: a few hundred metres a day along the barge lane beside the bay reach; laid up for the storm until mid-November
        dr = V["VSL-0361"]
        a, b = (27.8112, -97.3050), (27.8108, -97.3600)
        base = self.nav(a, b, 0.0, key=("dredge", "base"))
        lane = self.offset_path(("dredge",), base, 95.0)
        if lane.pts == base.pts:
            lane = self.offset_path(("dredge",), base, 70.0)
        yard = self.bpos("TERM-20-B01")
        ypos = mg.dest_point(yard, 92.0, 120.0)
        if not (self.GM.point_ok(ypos) and self.G.channel_at(ypos[0], ypos[1], 120)):
            ypos = mg.dest_point(yard, 272.0, 120.0)
        s = 300.0
        t = T_WARM
        t_layup = ts("2027-09-10T14:00Z")
        t_resume = ts("2027-11-16T15:00Z")

        way = [1.0]                      # the dredge works along the lane and back again, one cut at a time

        def work(t0, t1, s):
            t = t0
            while t < t1:
                dur = float(rs.uniform(3.5, 6.5)) * H
                la, lo, _ = lane.at(s)
                dr.add(Stay(t, min(t + dur, t1), (la, lo), "work", heading=268.0, status=3, draft=2.6, place="dredging"))
                s += way[0] * float(rs.uniform(45, 95))
                if s > lane.length - 200 or s < 300.0:
                    way[0] = -way[0]
                    s = min(max(s, 300.0), lane.length - 200)
                t += dur
            return s
        s = work(t, t_layup, s)
        la, lo, _ = lane.at(s)
        Pm = self.nav((la, lo), ypos, 0.0, start_at=(la, lo), end_at=ypos, key=("dredge", "in"))
        m = make_move(Pm, t_layup, speed=4.0, status=0, draft=2.6)
        dr.add(m)
        probe = make_move(Pm, 0.0, speed=4.0)
        dr.add(Stay(m.t1, t_resume - probe.t1, ypos, "moored", heading=92.0, place="TERM-20-B01", status=5, draft=2.6))
        dr.add(make_move(Pm, t_resume - probe.t1, speed=4.0, s0=Pm.length, s1=0.0, status=0, draft=2.6))
        work(t_resume, T_END + 2 * H, s)
        # research vessel: day trips to bay and nearshore stations two or three times a week; sampling after the spill
        rv = V["VSL-0461"]
        t = T_WARM + 0.7 * DAY
        opts = [["cc_e", "cc_mid"], ["lydia", "aransas_bay"], ["jetty_tips", "anch_s"], ["cc_e", "cc_n", "cc_mid"], ["redfish"]]
        while t < T_END - 10 * H:
            d = local_day(t)
            t += float(rs.uniform(1.6, 3.6) if not (3 <= d <= 25) else rs.uniform(1.0, 1.8)) * DAY
            h = local_hour(t)
            t += ((7.5 - h) % 24) * H
            if (STORM_STOP <= t < ts("2027-09-17T10:00Z")) or BLAST - 12 * H <= t < REOPEN2:
                continue
            r = opts[int(rs.integers(0, len(opts)))]
            if 3 <= local_day(t) <= 30:
                r = [["cc_e", "cc_mid", "cc_n"], ["cc_e", "cc_mid"], ["lydia", "aransas_bay"]][int(rs.integers(0, 3))]
            if self.idle(rv, t - 600, t + 10 * H):
                self.out_and_back(rv, t, r, 10.0 * rv.spd, hold_secs=float(rs.uniform(25, 60)) * 60, status=3, kind="survey")

    def run_osv_and_tows(self):
        rs = rng("osv")
        V = self.vessels
        for vid in ("VSL-0261", "VSL-0262", "VSL-0263"):
            v = V[vid]
            hp, hdg, hid = self.home_position(v)
            Pout = self.nav(hp, SEA, 0.0, start_at=hp, key=("osv", vid))
            t = T_WARM + float(rs.uniform(0, 3)) * DAY
            while t < T_END - 2 * DAY:
                t += float(rs.uniform(1.4, 3.2)) * DAY
                away = float(rs.uniform(16, 40)) * H
                if not self.small_window(t, "osv") or not self.small_window(t + away, "osv"):
                    continue
                if not self.idle(v, t - 600, t + away + 6 * H):
                    continue
                m = make_move(Pout, t, vfun=lambda la, lo, s_: min(10.5, self.channel_speed(la, lo) * 1.1), status=0, draft=4.2, dest="OFFSHORE")
                v.add(m)
                self.depart_legs(v, SEA, "GATE-OFFING", m.t1, 4.2, "OFFSHORE")
                Pgo = self.open_path(OFFING, SEA, seg=6000.0)
                t_off = t + away
                v.add(make_move(Pgo, t_off, speed=11.5, draft=3.8, dest="HARBOR ISLAND"))
                m2 = make_move(Pout, t_off + Pgo.length / (11.5 * KN), vfun=lambda la, lo, s_: min(10.5, self.channel_speed(la, lo) * 1.1), s0=Pout.length, s1=0.0,
                               status=0, draft=3.8, dest="HARBOR ISLAND")
                v.add(m2)
                t = m2.t1
        # Intracoastal Waterway line-haul tows: Houston side <-> Corpus Christi (and through to the south)
        nav = self.G.nav
        gi = [i for i, r in enumerate(nav.reach) if r.startswith("CESWG_GI")]
        north = nav.nodes[max(gi, key=lambda i: nav.nodes[i][0])]
        south = nav.nodes[min(gi, key=lambda i: nav.nodes[i][0])]
        fleet = self.bpos("TERM-19-B02")
        f26 = self.bpos("TERM-26-B01")
        P_in = self.nav(north, fleet, 0.0, end_at=fleet, key=("giww", "north_fleet"))
        P_26 = self.nav(north, f26, 0.0, end_at=f26, key=("giww", "north_26"))
        P_thru = self.nav(north, south, 0.0, key=("giww", "thru"))
        P_s19 = self.nav(south, fleet, 0.0, end_at=fleet, key=("giww", "south_fleet"))
        for vid in ("VSL-0291", "VSL-0292", "VSL-0293"):
            v = V[vid]
            t = T_WARM + float(rs.uniform(0, 6)) * DAY
            while t < T_END - 2 * DAY:
                t += float(rs.uniform(4.5, 9.0)) * DAY
                sp = float(rs.uniform(5.4, 6.4))
                kind = rs.random()
                if kind < 0.55:
                    P, stay = P_in, float(rs.uniform(18, 50)) * H
                elif kind < 0.8:
                    P, stay = P_26, float(rs.uniform(8, 30)) * H
                else:
                    P, stay = P_thru, None
                uses_cc = P is not P_26
                dur = P.length / (sp * KN)
                t_end = t + dur * (2 if stay is not None else 1) + (stay or 0) + 4 * H
                if uses_cc:
                    if not (self.small_window(t, "tow") and self.small_window(t_end, "tow")):
                        continue
                elif not ((t < YANKEE - 12 * H and t_end < YANKEE - 6 * H) or (t >= ts("2027-09-28T12:00Z"))):
                    continue
                if BLAST - dur - 2 * H <= t < BLAST + 6 * H:
                    continue
                if not self.idle(v, t - 600, t_end + H):
                    continue
                rev_first = (P is P_thru and rs.random() < 0.5)
                L = P.length

                def vt(lat, lon, s_):
                    return min(sp, self.channel_speed(lat, lon) * 0.62) if lon < -97.3957 else sp
                m = make_move(P, t, vfun=vt, s0=(L if rev_first else 0.0), s1=(0.0 if rev_first else L - (40.0 if stay is not None else 0.0)),
                              status=0, draft=2.9, dest="CORPUS CHRISTI" if stay is not None else ("BROWNSVILLE" if not rev_first else "HOUSTON"))
                v.add(m)
                if stay is not None:
                    la, lo, _ = P.at(L - 40.0)
                    v.add(Stay(m.t1, m.t1 + stay, (la, lo), "moored", heading=None, place="TERM-19-B02" if P is P_in else "TERM-26-B01", status=5, draft=2.9))
                    t2 = m.t1 + stay
                    if not (self.small_window(t2, "tow") if uses_cc else True):
                        # caught by a closure: stay until the channel reopens
                        t3 = REOPEN1 + 6 * H if t2 < REOPEN1 else REOPEN2 + 5 * H
                        v.itin[-1].t1 = t3
                        t2 = t3
                    m2 = make_move(P, t2, vfun=vt, s0=L - 40.0, s1=0.0, status=0, draft=2.9, dest="HOUSTON")
                    v.add(m2)
                    t = m2.t1
                else:
                    t = m.t1

    def run_fishing_and_leisure(self):
        rs = rng("fishing")
        V = self.vessels
        lost_after_storm = {"VSL-0403", "VSL-0406", "VSL-0433", "VSL-0435", "VSL-0413"}     # boats that do not come back after Rafael

        def gulf_trip(v, t, hours, speed, work_speed, status, kind):
            hp, _, hid = self.home_position(v)
            P = self.water(hp, SEA, 150.0, key=(hid, "SEA"))
            tt = self.go(v, P, t, speed, status=0)
            p = SEA
            t_stop = t + hours * H - P.length / (speed * KN)
            first = True
            while tt < t_stop:
                q = mg.dest_point(SEA, float(rs.uniform(35, 175)), float(rs.uniform(7000, 38000)))
                if first:
                    spd = speed
                else:
                    q = mg.dest_point(p, float(rs.uniform(0, 360)), float(rs.uniform(2500, 7500)))
                    spd = work_speed
                if not self.gulf_ok(q) or not self.gulf_ok(mg.interp(p, q, 0.33)) or not self.gulf_ok(mg.interp(p, q, 0.67)):
                    continue
                path = mg.Path(self.GM.densify([p, q], 2500.0))
                m = make_move(path, tt, speed=spd, status=(0 if first else status))
                v.add(m)
                tt, p, first = m.t1, q, False
                if rs.random() < 0.3:
                    tt = self.hold(v, tt, float(rs.uniform(15, 50)) * 60, p, "drift", radius=80.0, status=status)
            path = mg.Path(self.GM.densify([p, SEA], 2500.0))
            m = make_move(path, tt, speed=speed, status=0)
            v.add(m)
            return self.go(v, P, m.t1, speed, rev=True, status=0)

        def bay_trip(v, t, names, hours, speed, work_speed, status, kind):
            hp, _, hid = self.home_position(v)
            first = self.water(hp, self.wp(names[0]), 150.0, key=(hid, names[0]))
            if kind != "bay_any" and self.uses_ship_channel(first) and not self.small_window(t, "gulf"):
                return None
            tt = self.go(v, first, t, speed, status=0)
            cur = names[0]
            t_stop = t + hours * H
            while tt < t_stop:
                nxt = names[int(rs.integers(0, len(names)))]
                if nxt == cur:
                    tt = self.hold(v, tt, float(rs.uniform(15, 45)) * 60, self.wp(cur), "drift", radius=70.0, status=status)
                    continue
                a, b = sorted((cur, nxt))
                P = self.water(self.wp(a), self.wp(b), 150.0, key=(a, b))
                tt = self.go(v, P, tt, work_speed, rev=(cur != a), slow_start=False, slow_end=False, status=status)
                cur = nxt
            back = self.water(hp, self.wp(cur), 150.0, key=(hid, cur))
            return self.go(v, back, tt, speed, rev=True, status=0)

        # --- Conn Brown Harbor shrimpers
        for vid in ("VSL-0401", "VSL-0402", "VSL-0403", "VSL-0404", "VSL-0405", "VSL-0406", "VSL-0407"):
            v = V[vid]
            t = T_WARM + float(rs.uniform(0, 2)) * DAY
            while t < T_END - DAY:
                t += float(rs.uniform(0.9, 2.2)) * DAY
                h = local_hour(t)
                t += ((4.8 + float(rs.uniform(0, 1.2)) - h) % 24) * H
                if t > STORM_STOP and vid in lost_after_storm:
                    break
                if t > ts("2027-11-25T00:00Z") and rs.random() < 0.45:
                    continue                                   # season winds down
                gulf_ok = self.small_window(t, "gulf") and self.small_window(t + 15 * H, "gulf") and not (BLAST - 40 * H < t < BLAST)
                if gulf_ok and rs.random() < 0.65:
                    hours = float(rs.uniform(10, 15)) if rs.random() < 0.7 else float(rs.uniform(30, 52))
                    if not self.small_window(t + hours * H + 3 * H, "gulf") or (t < BLAST < t + (hours + 4) * H):
                        hours = 11.0
                    if self.idle(v, t - 600, t + (hours + 4) * H):
                        t = gulf_trip(v, t, hours, 8.5 * v.spd, 2.8, 7, "gulf")
                elif self.small_window(t, "bay") and not (STORM_STOP <= t < ts("2027-09-28T10:00Z")):
                    if self.idle(v, t - 600, t + 13 * H):
                        r = bay_trip(v, t, ["aransas_bay", "aransas_e", "aransas_n"], float(rs.uniform(8, 11)), 8.5 * v.spd, 2.8, 7, "bay")
                        t = r if r else t
        # --- Rockport bay boats, the weekend sportfisher and the game of charters
        for vid in ("VSL-0411", "VSL-0412", "VSL-0413"):
            v = V[vid]
            t = T_WARM + float(rs.uniform(0, 2)) * DAY
            while t < T_END - DAY:
                t += float(rs.uniform(0.9, 2.0)) * DAY
                h = local_hour(t)
                t += ((5.5 + float(rs.uniform(0, 1.0)) - h) % 24) * H
                if t > STORM_STOP and vid in lost_after_storm:
                    break
                if not self.small_window(t, "bay"):
                    continue
                if self.idle(v, t - 600, t + 11 * H):
                    names = ["aransas_n", "copano", "copano_e"] if rs.random() < 0.6 else ["aransas_bay", "aransas_e", "aransas_n"]
                    r = bay_trip(v, t, names, float(rs.uniform(6, 9)), 9.0 * v.spd, 2.6, 7, "bay_any")
                    t = r if r else t
        for vid in ("VSL-0431", "VSL-0432", "VSL-0433", "VSL-0434", "VSL-0435"):
            v = V[vid]
            t = T_WARM + float(rs.uniform(0, 1)) * DAY
            while t < T_END - DAY:
                pre = t < STORM_STOP
                t += float(rs.uniform(0.7, 1.6) if pre else rs.uniform(1.5, 4.5)) * DAY
                h = local_hour(t)
                start = 5.8 if rs.random() < 0.7 else 12.5
                t += ((start + float(rs.uniform(0, 0.8)) - h) % 24) * H
                if t > STORM_STOP and vid in lost_after_storm:
                    break
                if not self.small_window(t, "charter") or not self.small_window(t + 9 * H, "charter"):
                    continue
                if not pre and weekday(t) < 4 and rs.random() < 0.6:
                    continue
                hours = float(rs.uniform(4.5, 6)) if start > 10 or rs.random() < 0.4 else float(rs.uniform(8, 10))
                if self.idle(v, t - 600, t + (hours + 2) * H):
                    if rs.random() < 0.75:
                        t = gulf_trip(v, t, hours, 21.0 * v.spd, 6.0, 0, "charter")
                    else:
                        r = bay_trip(v, t, ["lydia", "aransas_bay", "aransas_e"], hours - 1.5, 20.0 * v.spd, 4.0, 0, "charter")
                        t = r if r else t
        # --- weekend sportfisher out of Rockport, the cruising yacht, the sailors on Corpus Christi Bay
        v = V["VSL-0484"]
        t = T_WARM
        while t < T_END - DAY:
            t += DAY
            if weekday(t) < 5 or rs.random() < 0.45:
                continue
            tt = local_ts(local_day(t), "06:00") + float(rs.uniform(0, 50)) * 60
            if self.small_window(tt, "gulf") and self.small_window(tt + 11 * H, "gulf") and (tt < STORM_STOP or tt > ts("2027-11-18T00:00Z")) and self.idle(v, tt - 600, tt + 13 * H):
                gulf_trip(v, tt, float(rs.uniform(8, 10.5)), 22.0 * v.spd, 6.5, 0, "gulf")
        v = V["VSL-0485"]
        for day, names in ((-24, ["lydia", "aransas_bay", "aransas_n"]), (-16, ["jetty_tips"]), (-9, ["lydia", "aransas_bay"]), (82, ["lydia", "aransas_bay"]), (103, ["jetty_tips"])):
            tt = local_ts(day, "09:30")
            if self.idle(v, tt - 600, tt + 9 * H):
                self.out_and_back(v, tt, names, 12.0, hold_secs=50 * 60, kind="leisure")
        for vid, wed in (("VSL-0482", False), ("VSL-0483", True)):
            v = V[vid]
            hp, _, hid = self.home_position(v)
            for day in range(-44, 120):
                tt0 = local_ts(day, "00:00")
                wd = weekday(tt0)
                go = (wd >= 5 and rs.random() < 0.6) or (wed and wd == 2 and rs.random() < 0.85)
                if not go:
                    continue
                tt = local_ts(day, "17:40" if (wed and wd == 2) else "10:30") + float(rs.uniform(0, 40)) * 60
                if not self.small_window(tt, "leisure") or (day > 60 and rs.random() < 0.5):
                    continue
                if self.idle(v, tt - 600, tt + 6 * H):
                    names = [["cc_w", "cc_mid"], ["cc_w", "cc_s"], ["cc_w", "cc_n"], ["cc_w"]][int(rs.integers(0, 4))]
                    if wed and wd == 2:
                        names = ["cc_w", "cc_s", "cc_w"]
                    self.out_and_back(v, tt, names, float(rs.uniform(4.6, 6.2)), hold_secs=0, kind="leisure")
        # --- tour boat and the San Jose Island launch out of Port Aransas
        tb = V["VSL-0471"]
        sj = V["VSL-0472"]
        hp, _, hid = self.home_position(sj)
        land = self.GM.water_point_near((27.8432, -97.0480), 45.0, 500.0)
        Psj = self.water(hp, land, 60.0, key=(hid, "stjo"))
        for day in range(-44, 120):
            wd = weekday(local_ts(day, "12:00"))
            base_t = local_ts(day, "08:00")
            if self.small_window(base_t, "tour") and self.small_window(base_t + 12 * H, "tour"):
                pre = base_t < STORM_STOP
                if pre or wd >= 5:
                    for hh in ((9.0, 11.5, 14.0, 18.2) if pre else (10.0, 14.0)):
                        if rs.random() < (0.85 if pre else 0.6):
                            tt = local_ts(day, "00:00") + hh * H + float(rs.uniform(0, 12)) * 60
                            if self.idle(tb, tt - 600, tt + 2.2 * H):
                                self.out_and_back(tb, tt, ["lydia"], 8.0, hold_secs=float(rs.uniform(25, 40)) * 60, kind="tour")
                if pre or (wd >= 5 and rs.random() < 0.7):
                    for hh in range(8, 18):
                        tt = local_ts(day, "00:00") + hh * H + float(rs.uniform(0, 6)) * 60
                        if rs.random() < 0.85 and self.idle(sj, tt - 60, tt + 40 * 60):
                            t1 = self.go(sj, Psj, tt, 14.0)
                            sj.add(Stay(t1, t1 + 9 * 60, land, "hold", place="San Jose Island"))
                            self.go(sj, Psj, t1 + 9 * 60, 14.0, rev=True)
