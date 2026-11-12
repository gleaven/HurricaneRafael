"""Ocean-going traffic: agents that cycle between sea, anchorage and berth, constrained by the
canon channel windows, plus the pilot boats and harbour tugs that every ship movement needs."""
import math
import re

import numpy as np

import geo
import maritime_geom as mg
from common import iso
from maritime_base import DAY, H, PORT_NAMES, Call
from maritime_core import (BLACKOUT_FROM, BLAST, BOARD, INNER_E_PERMITS, KN, LAST_IN_PRESTORM, LAST_OUT_PRESTORM, LON_BRIDGE,
                           LON_FERRY, LON_JETTY, OFFING, REOPEN1, REOPEN2, RETURN_D3_A, RETURN_D3_B, SEA, T0, T_END, T_WARM,
                           XRAY, YANKEE, ZULU, Move, Stay, follow, make_move, ts)

LON_TIPS = -97.0335        # seaward end of the jetties
TUG_IDS = ["VSL-0077", "VSL-0271", "VSL-0272", "VSL-0273", "VSL-0274", "VSL-0275", "VSL-0276", "VSL-0277"]
PILOT_IDS = ["VSL-0301", "VSL-0302", "VSL-0303"]
CARGO_WORDS = {"crude": ["crude oil"], "product": ["gasoline", "diesel", "jet fuel", "naphtha", "condensate"], "lng": ["LNG"],
               "cargo": ["general cargo", "containers", "steel", "wind components"], "roro": ["ro-ro", "general cargo"]}


class Agent:
    def __init__(self, v):
        self.v = v
        r = v.rec
        tp = r.get("typical_pattern", "")
        m = re.search(r"every (\d+) to (\d+) days", tp)
        m2 = re.search(r"about every (\d+) days", tp)
        self.cycle = (int(m.group(1)) + int(m.group(2))) / 2 if m else (int(m2.group(1)) if m2 else 30)
        if v.cls == "tanker":
            self.kind = "crude" if v.draft_max >= 14 else "product"
        else:
            self.kind = v.cls
        self.gate = (r.get("sea_gates") or ["GATE-OFFING"])[0]
        self.last_port = (r.get("usual_previous_ports") or ["(not reported)"])[0]
        self.next_port = (r.get("usual_next_ports") or ["(not reported)"])[0]
        light, full = v.draft_light, v.draft_max
        part = round(light + 0.7 * (full - light), 1)
        export_bulk = any(w in tp for w in ("sorghum", "wheat", "petroleum coke", "corn"))
        if self.kind in ("crude", "lng") or (self.kind == "bulk" and export_bulk):
            self.in_draft, self.out_draft, self.direction = light, full, "EXPORT"
        elif self.kind == "bulk":
            self.in_draft, self.out_draft, self.direction = full, light, "IMPORT"
        elif self.kind == "product":
            self.in_draft, self.out_draft, self.direction = part, round(light + 0.55 * (full - light), 1), "IMPORT"
        else:
            self.in_draft, self.out_draft, self.direction = part, round(light + 0.35 * (full - light), 1), "IMPORT"
        self.state = "away"
        self.next_eta = None
        self.call = None
        self.anch = None
        self.anch_since = None
        self.berth = None
        self.berth_since = None
        self.ready_at = None
        self.min_wait_until = 0.0
        self.not_before = 0.0
        self.forced_berth = None
        self.yankee = False
        self.storm_eta = None
        self.hold_after = None      # time after which a berthed ship may sail (closure holds)
        self.no_return = False
        self.scripted = False
        self.fixed_stay = None

    def berth_hours(self, rs):
        lo, hi = {"crude": (30, 42), "product": (20, 30), "lng": (22, 28), "bulk": (60, 108), "cargo": (36, 72),
                  "roro": (20, 30)}.get(self.kind, (30, 50))
        return float(rs.uniform(lo, hi))


class ShipsMixin:
    # ------------------------------------------------------------------ setup
    def setup_agents(self):
        ex = {"VSL-0031"}
        self.agents = {}
        for v in self.vessels.values():
            if v.cls in ("tanker", "lng", "bulk", "cargo", "roro") and v.id not in ex:
                self.agents[v.id] = Agent(v)
        y = [x for x in self.sets["yankee_queue_14"]["vessels"] if x not in ("VSL-0031",)]
        # storm arrivals for the Yankee queue, spread from D-5 evening to an hour before Yankee
        slots = np.linspace(ts("2027-09-09T21:00Z"), YANKEE - 1.4 * H, len(y))
        order = sorted(y, key=lambda i: (i == "VSL-0012", self.vessels[i].rs.random()))   # Gulf Provider last (ETA D-2)
        for vid, t in zip(order, slots):
            ag = self.agents[vid]
            ag.yankee = True
            ag.storm_eta = float(t + ag.v.rs.uniform(-1.2 * H, 1.2 * H)) if vid != "VSL-0012" else float(YANKEE - 2.6 * H)
        for vid, ag in self.agents.items():
            rs = ag.v.rs
            if vid in ("VSL-0041", "VSL-0042"):
                ag.next_eta = ts("2027-09-10T08:10Z") if vid == "VSL-0041" else ts("2027-09-10T15:20Z")
                ag.no_return = ag.scripted = True
                continue
            if vid == "VSL-0019":             # sealift ship: arrives for the planned D+45 restart, loads D+59 to D+64
                ag.next_eta = ts("2027-10-28T21:40Z")
                ag.no_return = ag.scripted = True
                ag.not_before = ts("2027-11-12T14:10Z")
                ag.forced_berth = "TERM-07-B01"
                ag.fixed_stay = ts("2027-11-17T15:20Z")
                ag.in_draft, ag.out_draft, ag.direction = 7.4, 9.4, "EXPORT"
                ag.last_port, ag.next_port = "Beaumont", "(not announced)"
                ag.gate = "GATE-SABINE"
                continue
            if ag.yankee:
                eta = ag.storm_eta
                while eta - ag.cycle * DAY > T_WARM + 2 * DAY:
                    eta -= ag.cycle * DAY * float(rs.uniform(0.95, 1.05))
                ag.next_eta = eta if eta < ag.storm_eta - 12 * DAY else ag.storm_eta
            else:
                ag.next_eta = T_WARM + float(rs.uniform(0.05, 1.0)) * ag.cycle * DAY
        self.tug_roster = [self.vessels[i] for i in TUG_IDS]
        self.pilot_roster = [self.vessels[i] for i in PILOT_IDS]
        for v in self.tug_roster + self.pilot_roster:
            self.free_at[v.id] = T_WARM
        self.blast_point = None
        self.escort_done = False

    # ------------------------------------------------------------------ canon windows
    @staticmethod
    def inbound_allowed(t, zone):
        if t < LAST_IN_PRESTORM:
            return True
        if t < REOPEN1:
            return False
        if t < BLACKOUT_FROM:
            if zone == "laq":
                return True
            if zone == "inner_e":
                return t >= INNER_E_PERMITS
            return False
        return t >= REOPEN2

    def in_ok(self, ag, t, zone):
        # the two tankers with a berth booked at TERM-01 are the last ships brought in under X-Ray
        if ag.v.id in ("VSL-0041", "VSL-0042") and t < ts("2027-09-11T21:00Z"):
            return True
        return self.inbound_allowed(t, zone)

    @staticmethod
    def outbound_allowed(t):
        return t < LAST_OUT_PRESTORM or REOPEN1 <= t < BLACKOUT_FROM - 1.5 * H or t >= REOPEN2

    def berth_candidates(self, ag, t):
        v = ag.v
        need = max(ag.in_draft, ag.out_draft)
        out = []
        terms = list(v.rec.get("usual_berths") or [])
        if ag.forced_berth:
            return [ag.forced_berth]
        words = CARGO_WORDS.get(ag.kind, [])
        for b in self.berths.values():
            if b["berth_type"] != "berth" or b["max_loa_m"] < v.loa or b["max_draft_m"] < need:
                continue
            usual = b["terminal_id"] in terms
            alt = any(w in b.get("cargo_types", []) for w in words)
            if not (usual or alt):
                continue
            if b["terminal_id"] == "TERM-01" and v.id not in ("VSL-0041", "VSL-0042") and t > ts("2027-09-09T00:00Z"):
                continue
            if b["berth_id"] in ("TERM-13-B01", "TERM-15-B01") and t > REOPEN1:
                continue                      # kept free for the two tankers' shift on D+62
            if b["berth_id"] == "TERM-07-B02" and v.id != "VSL-0012" and REOPEN1 - DAY < t < ts("2027-10-17T16:00Z"):
                continue                      # relief cargo berth held for MV Gulf Provider
            if b["berth_id"] == "TERM-07-B01" and v.id != "VSL-0019" and ts("2027-11-08T00:00Z") < t < ts("2027-11-18T00:00Z"):
                continue                      # military outload berth
            out.append((0 if usual else 1, b["berth_id"]))
        return [b for _, b in sorted(out)]

    # ------------------------------------------------------------------ service craft
    def pick_free(self, roster, t_need, n=1):
        ok = [v for v in roster if self.free_at[v.id] <= t_need and not (v.id == "VSL-0077" and t_need > BLAST - 1.6 * DAY)]
        ok.sort(key=lambda v: (self.free_at[v.id], v.id))
        return ok[:n] if len(ok) >= n else None

    def boat_vfun(self, path, fast, slow=6.0):
        L = path.length

        def f(lat, lon, s):
            return slow if (s < 260 or s > L - 260) else fast
        return f

    def pilot_run(self, boat, t_board, order):
        """Pilot boat out to the boarding area and back for one ship movement."""
        home, hdg, hid = self.home_position(boat)
        P = self.water(home, BOARD, 150.0, key=("pil", boat.id))
        fast = 18.5 * boat.spd
        probe = make_move(P, 0.0, vfun=self.boat_vfun(P, fast))
        t_out = t_board - 5 * 60 - probe.t1
        out = make_move(P, t_out, vfun=self.boat_vfun(P, fast), dest="", place=order)
        boat.add(out)
        boat.add(Stay(out.t1, t_board + 4 * 60, BOARD, "drift", radius=70.0, place="PILOT-BOARDING"))
        back = make_move(P, t_board + 4 * 60, vfun=self.boat_vfun(P, fast), s0=P.length, s1=0.0, place=order)
        boat.add(back)
        self.free_at[boat.id] = back.t1 + 12 * 60
        return out.t0, back.t1

    def tug_job(self, tug, P, ship_move, inbound, s_meet, s_hold, t_hold_until, escort_to=None):
        """One harbour tug working one ship movement on the ship's own track P.
        inbound: meet at s_meet, follow to s_hold, stand by, return to base.
        outbound: stand by at s_hold, follow to s_meet (or escort_to), return to base."""
        home, hdg, hid = self.home_position(tug)
        la, lo, _ = P.at(s_hold)
        hold_pt = (la, lo)
        la, lo, _ = P.at(s_meet)
        meet_pt = (la, lo)
        gap = 70.0
        if inbound:
            t_meet = ship_move.t_at_s(s_meet + gap)
            A = self.nav(home, meet_pt, 0.0, start_at=home, end_at=meet_pt, key=("tugA", tug.id, round(meet_pt[0], 5), round(meet_pt[1], 5)))
            probe = make_move(A, 0.0, vfun=self.tug_vfun(A, tug))
            a = make_move(A, t_meet - probe.t1 - 240, vfun=self.tug_vfun(A, tug))
            tug.add(a)
            tug.add(Stay(a.t1, t_meet, meet_pt, "hold", heading=None, place="standby"))
            t_end = ship_move.t_at_s(s_hold + gap)
            kt = [t_meet] + [float(k) for k in ship_move.kt if t_meet < k < t_end] + [t_end]
            ks = [min(max(ship_move.s_at(k) - gap, s_meet), s_hold) for k in kt]
            tug.add(Move(P, kt, ks, place="assist"))
            tug.add(Stay(t_end, t_hold_until, hold_pt, "hold", place="assist"))
            B = self.nav(hold_pt, home, 0.0, start_at=hold_pt, end_at=home, key=("tugB", tug.id, round(hold_pt[0], 5), round(hold_pt[1], 5)))
            b = make_move(B, t_hold_until, vfun=self.tug_vfun(B, tug))
            tug.add(b)
            self.free_at[tug.id] = b.t1 + 20 * 60
            return a.t0, b.t1
        # outbound: P is the outbound track (berth -> sea); s_hold < s_meet
        t_go = ship_move.t_at_s(s_hold + gap)                 # ship is just past the tug
        A = self.nav(home, hold_pt, 0.0, start_at=home, end_at=hold_pt, key=("tugA", tug.id, round(hold_pt[0], 5), round(hold_pt[1], 5)))
        probe = make_move(A, 0.0, vfun=self.tug_vfun(A, tug))
        t_arr = ship_move.t0 - 14 * 60
        a = make_move(A, t_arr - probe.t1, vfun=self.tug_vfun(A, tug))
        tug.add(a)
        tug.add(Stay(a.t1, t_go, hold_pt, "hold", place="assist"))
        s_end = escort_to if escort_to is not None else s_meet
        t_end = ship_move.t_at_s(min(s_end + gap, P.length))
        kt = [t_go] + [float(k) for k in ship_move.kt if t_go < k < t_end] + [t_end]
        ks = [min(max(ship_move.s_at(k) - gap, s_hold), s_end) for k in kt]
        tug.add(Move(P, kt, ks, place="assist"))
        la, lo, _ = P.at(s_end)
        end_pt = (la, lo)
        B = self.nav(end_pt, home, 0.0, start_at=end_pt, end_at=home, key=("tugB", tug.id, round(end_pt[0], 5), round(end_pt[1], 5)))
        b = make_move(B, t_end + 90, vfun=self.tug_vfun(B, tug))
        tug.add(b)
        self.free_at[tug.id] = b.t1 + 20 * 60
        return a.t0, b.t1, end_pt, B, b

    def tug_vfun(self, path, tug):
        L, head, tail = path.length, path.head, path.tail

        def f(lat, lon, s):
            if s < head + 30 or s > L - tail - 30:
                return 2.5
            return min(10.0, self.channel_speed(lat, lon) * 1.05) * tug.spd
        return f

    # ------------------------------------------------------------------ ship movement building
    def in_track(self, bid):
        key = ("intrack", bid)
        if key not in self._paths:
            lane = self.lane(bid, True, deep=True)
            self._paths[key] = mg.join(self.open_path(BOARD, SEA, deep=True, seg=4000.0), lane)
        return self._paths[key]

    def out_track(self, bid):
        key = ("outtrack", bid)
        if key not in self._paths:
            lane = self.lane(bid, False, deep=True).reversed()
            self._paths[key] = mg.join(lane, self.open_path(SEA, BOARD, deep=True, seg=4000.0))
        return self._paths[key]

    def s_at_lon(self, P, lon):
        for i in range(len(P.pts) - 1):
            a, b = P.pts[i][1], P.pts[i + 1][1]
            if (a - lon) * (b - lon) <= 0 and a != b:
                return float(P.cum[i] + (P.cum[i + 1] - P.cum[i]) * (lon - a) / (b - a))
        return None

    def slot_ok(self, t_buoy, direction, zone, t_in0, t_in1):
        for tr in self.transits:
            if abs(tr["t_buoy"] - t_buoy) < 40 * 60:
                return False
            if tr["zone"] == zone and tr["dir"] != direction and not (t_in1 + 600 <= tr["t_in0"] or t_in0 >= tr["t_in1"] + 600):
                return False
            if tr["zone"] == zone and tr["dir"] == direction and abs(tr["t_in0"] - t_in0) < 35 * 60:
                return False
        return True

    def plan_inbound(self, ag, t, bid, from_anch=True):
        v = ag.v
        P = self.in_track(bid)
        zone = self.berths[bid]["zone"]
        if from_anch:
            a = self.anch[ag.anch]
            p1 = self.open_path(a, BOARD, deep=True, seg=3000.0)
            L1 = p1.length

            def v1(lat, lon, s):
                return 2.0 if s < 250 else (6.2 if s > L1 - 900 else 8.0 * v.spd)
            m1 = make_move(p1, t + 18 * 60, vfun=v1, status=0, draft=ag.in_draft, dest="CORPUS CHRISTI")
            t_board = m1.t1
        else:
            m1, t_board = None, t
        m2 = make_move(P, t_board, vfun=self.ship_vfun(P, v.spd), status=0, draft=ag.in_draft, dest="CORPUS CHRISTI")
        s_buoy = self.open_path(BOARD, SEA, deep=True, seg=4000.0).length
        t_buoy = m2.t_at_s(s_buoy)
        s_br = self.s_at_lon(P, LON_BRIDGE)
        s_meet = (s_br - 150.0) if (zone != "laq" and s_br is not None) else P.length - P.tail - 2500.0
        s_meet = min(s_meet, P.length - P.tail - 60.0 - 750.0)
        t_in0 = m2.t_at_s(s_meet)
        return dict(v=v, ag=ag, dir="IN", berth=bid, zone=zone, m1=m1, m2=m2, P=P, t_start=t, t_board=t_board, t_buoy=t_buoy,
                    t_jetty=m2.t_at_lon(LON_JETTY), t_ferry=m2.t_at_lon(LON_FERRY), t_bridge=m2.t_at_s(s_br) if (s_br and zone != "laq") else None,
                    t_end=m2.t1, t_in0=t_in0, t_in1=m2.t1, s_meet=s_meet, s_hold=P.length - P.tail - 60.0)

    def plan_outbound(self, ag, t, bid):
        v = ag.v
        P = self.out_track(bid)
        zone = self.berths[bid]["zone"]
        dest = PORT_NAMES.get(ag.next_port, ag.next_port.upper())[:20]
        m = make_move(P, t, vfun=self.ship_vfun(P, v.spd), status=0, draft=ag.out_draft, dest=dest)
        s_buoy = P.length - self.open_path(SEA, BOARD, deep=True, seg=4000.0).length
        s_br = self.s_at_lon(P, LON_BRIDGE)
        s_meet = (s_br + 150.0) if (zone != "laq" and s_br is not None) else P.head + 2500.0
        s_meet = max(s_meet, P.head + 60.0 + 750.0)
        return dict(v=v, ag=ag, dir="OUT", berth=bid, zone=zone, m1=None, m2=m, P=P, t_start=t, t_board=m.t1, t_buoy=m.t_at_s(s_buoy),
                    t_jetty=m.t_at_lon(LON_JETTY), t_ferry=m.t_at_lon(LON_FERRY), t_bridge=m.t_at_s(s_br) if (s_br and zone != "laq") else None,
                    t_end=m.t1, t_in0=t, t_in1=m.t_at_s(s_meet), s_meet=s_meet, s_hold=P.head + 60.0)

    def services_for(self, plan, escort=None):
        """Reserve a pilot boat and two tugs for a planned movement; None if not available."""
        t_board = plan["t_board"]
        boats = self.pick_free(self.pilot_roster, t_board - 50 * 60)
        if plan["dir"] == "IN":
            t_need = plan["t_in0"] - (3.4 * H if plan["zone"] == "laq" else 2.3 * H)
        else:
            t_need = plan["t_start"] - (3.4 * H if plan["zone"] == "laq" else 2.3 * H)
        roster = [x for x in self.tug_roster if not (escort and x.id == escort.id)]
        tugs = self.pick_free(roster, t_need, 2)
        if escort is not None and self.free_at[escort.id] > t_need:
            return None
        if not boats or not tugs:
            return None
        return boats[0], tugs

    def commit(self, plan, boat, tugs, escort=None):
        v, ag = plan["v"], plan["ag"]
        self._order = getattr(self, "_order", 4000) + 1
        order = f"PO-{self._order:05d}"
        plan["order"] = order
        if plan["m1"] is not None:
            v.add(plan["m1"])
        v.add(plan["m2"])
        self.pilot_run(boat, plan["t_board"], order)
        P, m = plan["P"], plan["m2"]
        names = []
        if plan["dir"] == "IN":
            hold_until = plan["t_end"] + 22 * 60
            for k, tug in enumerate(tugs):
                self.tug_job(tug, P, m, True, plan["s_meet"] + 140.0 * k, plan["s_hold"] - 90.0 * k, hold_until + 240 * k)
                names.append(tug.name)
        else:
            for k, tug in enumerate(tugs):
                self.tug_job(tug, P, m, False, plan["s_meet"] - 140.0 * k, plan["s_hold"] + 90.0 * k, None)
                names.append(tug.name)
            if escort is not None:
                s_tip = self.s_at_lon(P, LON_TIPS)
                res = self.tug_job(escort, P, m, False, plan["s_meet"], plan["s_hold"] + 200.0, None, escort_to=s_tip)
                names.append(escort.name)
                plan["escort"] = (escort, res)
        plan["tugs"] = names
        plan["pilot_boat"] = boat.name
        self.transits.append(plan)
        if plan["t_ferry"] is not None:
            self.ship_passes.append((plan["t_ferry"], v.id))
        return plan

    # ------------------------------------------------------------------ offshore legs
    def sea_speed(self, v):
        return (13.5 if v.cls in ("lng", "roro", "cargo") else 12.5) * v.spd

    def arrive_legs(self, v, gate, dest, t_arr, draft, dest_txt="CORPUS CHRISTI", deep=False):
        """Sea gate -> OFFING -> dest, timed to end at t_arr. Returns the start time."""
        g = self.gate_path(gate)
        sp = self.sea_speed(v)
        p2 = self.open_path(OFFING, dest, deep=False, seg=6000.0)
        L2 = p2.length

        def v2(lat, lon, s):
            return 5.5 if s > L2 - 1200 else (9.0 if s > L2 - 5000 else sp)
        probe2 = make_move(p2, 0.0, vfun=v2)
        t_off = t_arr - probe2.t1
        m2 = make_move(p2, t_off, vfun=v2, draft=draft, dest=dest_txt)
        dur1 = g.length / (sp * KN)
        m1 = make_move(g, t_off - dur1, speed=sp, s0=g.length, s1=0.0, draft=draft, dest=dest_txt)
        v.add(m1); v.add(m2)
        return m1.t0

    def depart_legs(self, v, start, gate, t, draft, dest_txt):
        """start (BOARD or an anchorage position) -> OFFING -> sea gate. Returns the time at the gate."""
        sp = self.sea_speed(v)
        p1 = self.open_path(start, OFFING, deep=False, seg=6000.0)

        def v1(lat, lon, s):
            return 7.0 if s < 800 else (10.0 if s < 4000 else sp)
        m1 = make_move(p1, t, vfun=v1, draft=draft, dest=dest_txt)
        v.add(m1)
        if gate == "GATE-OFFING":
            return m1.t1
        g = self.gate_path(gate)
        m2 = make_move(g, m1.t1, speed=sp, draft=draft, dest=dest_txt)
        v.add(m2)
        return m2.t1

    # ------------------------------------------------------------------ anchorage
    def take_anchor(self, t, prefer=None, exclude=("ANCH-10", "ANCH-16")):
        ids = [a for a in self.anch if a not in exclude and self.free(self.anch_busy[a], t, t + 400 * DAY)]
        if prefer and prefer in ids:
            return prefer
        ids.sort(key=lambda a: geo.gc_nm(self.anch[a], SEA) + 0.8 * rng_hash(a, t))
        return ids[0] if ids else None

    def anchored_count(self, t):
        return sum(1 for ag in self.agents.values() if ag.state == "anchored")

    # ------------------------------------------------------------------ agent transitions
    def new_call(self, ag, eta):
        c = Call(ag.v, eta, ag.last_port, ag.next_port, ag.kind, ag.direction)
        c.draft_arr = ag.in_draft
        ag.call = c
        self.calls.append(c)
        return c

    def do_arrive(self, ag, t):
        v = ag.v
        c = self.new_call(ag, ag.next_eta + float(v.rs.uniform(-3, 3)) * H)
        storm = ag.yankee and ag.storm_eta is not None and abs(ag.next_eta - ag.storm_eta) < 1
        if v.id == "VSL-0019":
            c.eta = ts("2027-10-29T13:00Z")
            c.noa_time = ts("2027-10-22T15:00Z")
        if storm:
            ag.not_before = REOPEN1
            if v.id == "VSL-0012":
                c.noa_time = ts("2027-09-09T14:20Z")            # booked D-5 with a pre-storm ETA
                c.eta = ts("2027-09-12T11:00Z")
        pos_id = self.take_anchor(t)
        direct = (not storm) and not ag.scripted and v.rs.random() < (0.06 if ag.kind == "crude" else 0.25)
        if direct:
            # straight to the pilot station if a berth and a slot are open on arrival
            for bid in self.berth_candidates(ag, t):
                zone = self.berths[bid]["zone"]
                if not self.in_ok(ag, t, zone) or t < ag.not_before:
                    continue
                plan = self.plan_inbound(ag, t, bid, from_anch=False)
                stay = ag.berth_hours(v.rs) * H
                if not self.free(self.berth_busy[bid], plan["t_end"] - 30 * 60, plan["t_end"] + stay + 5 * H):
                    continue
                if not self.slot_ok(plan["t_buoy"], "IN", zone, plan["t_in0"], plan["t_in1"]):
                    continue
                sv = self.services_for(plan)
                if not sv:
                    continue
                self.arrive_legs(v, ag.gate, BOARD, t, ag.in_draft)
                self.commit(plan, sv[0], sv[1])
                self.berth_in(ag, bid, plan, stay)
                return
        if pos_id is None:
            c.status = "CANCELLED"
            c.hold.append((t, "no anchorage position available; diverted"))
            self.schedule_next(ag, t, cancelled=True)
            return
        self.arrive_legs(v, ag.gate, self.anch[pos_id], t, ag.in_draft, deep=False)
        ag.state, ag.anch, ag.anch_since = "anchored", pos_id, t
        self.anch_busy[pos_id].append((t, 1e18, v.id))
        c.ata_anch, c.anch = t, pos_id
        c.status = "AT ANCHORAGE"
        lo, hi = (30, 110) if ag.kind == "crude" else (4, 30)
        ag.min_wait_until = t + float(v.rs.uniform(lo, hi)) * H
        if v.id == "VSL-0041":
            ag.min_wait_until = ts("2027-09-11T10:30Z"); ag.forced_berth = "TERM-01-B07"
        if v.id == "VSL-0042":
            ag.min_wait_until = ts("2027-09-11T11:40Z"); ag.forced_berth = "TERM-01-B08"

    def release_anchor(self, ag, t):
        pid = ag.anch
        self.anch_busy[pid] = [(a, (t if vid == ag.v.id and b > 1e17 else b), vid) for a, b, vid in self.anch_busy[pid]]

    def berth_in(self, ag, bid, plan, stay):
        ag.state, ag.berth, ag.berth_since = "berthed", bid, plan["t_end"]
        ag.ready_at = plan["t_end"] + stay
        self.berth_busy[bid].append((plan["t_end"] - 30 * 60, 1e18, ag.v.id))
        c = ag.call
        c.ata, c.berth, c.status = plan["t_end"], bid, "IN PORT"
        if ag.v.id in ("VSL-0041", "VSL-0042"):
            ag.ready_at = 1e18
        if ag.fixed_stay:
            ag.ready_at = ag.fixed_stay

    def try_inbound(self, ag, t):
        if t < ag.min_wait_until or t < ag.not_before:
            return False
        v = ag.v
        for bid in self.berth_candidates(ag, t):
            zone = self.berths[bid]["zone"]
            if not self.in_ok(ag, t + 18 * 60, zone):
                continue
            if not self.free(self.berth_busy[bid], t + 2.8 * H, t + 4.6 * H):
                continue                      # berth plainly occupied when the ship would arrive
            plan = self.plan_inbound(ag, t, bid)
            stay = ag.berth_hours(v.rs) * H
            if not self.in_ok(ag, plan["t_board"], zone):
                continue
            if t < BLAST and plan["t_end"] > BLAST - 25 * 60:
                continue
            if not self.free(self.berth_busy[bid], plan["t_end"] - 30 * 60, plan["t_end"] + stay + 5 * H):
                continue
            if not self.slot_ok(plan["t_buoy"], "IN", zone, plan["t_in0"], plan["t_in1"]):
                continue
            sv = self.services_for(plan)
            if not sv:
                continue
            a = self.anch[ag.anch]
            v.add(Stay(ag.anch_since, t + 18 * 60, a, "anchored", place=ag.anch, status=1, draft=ag.in_draft,
                       dest="CORPUS CHRISTI", radius=float(v.rs.uniform(190, 300))))
            self.release_anchor(ag, t + 18 * 60)
            ag.call.atd_anch = t + 18 * 60
            self.commit(plan, sv[0], sv[1])
            self.berth_in(ag, bid, plan, stay)
            return True
        return False

    def berth_stay(self, ag, t_end):
        """Write the moored period for a ship leaving its berth at t_end (draft changes as cargo is worked)."""
        v, bid = ag.v, ag.berth
        b = self.berths[bid]
        t0 = ag.berth_since
        mid = t0 + 0.72 * (min(t_end, ag.ready_at) - t0)
        hdg = b.get("heading_deg", 0.0)
        v.add(Stay(t0, mid, self.bpos(bid), "moored", heading=hdg, place=bid, status=5, draft=ag.in_draft, dest="CORPUS CHRISTI"))
        dest = PORT_NAMES.get(ag.next_port, ag.next_port.upper())[:20]
        v.add(Stay(mid, t_end, self.bpos(bid), "moored", heading=hdg, place=bid, status=5, draft=ag.out_draft, dest=dest))

    def try_outbound(self, ag, t, escort=None, force=False):
        v, bid = ag.v, ag.berth
        if not force and (t < ag.ready_at or not self.outbound_allowed(t) or (ag.hold_after and t < ag.hold_after)):
            return False
        plan = self.plan_outbound(ag, t, bid)
        if not force and not self.slot_ok(plan["t_buoy"], "OUT", plan["zone"], plan["t_in0"], plan["t_in1"]):
            return False
        laden_crude = ag.kind == "crude" and escort is None and v.rs.random() < 0.55
        if laden_crude:
            cands = self.pick_free(self.tug_roster, plan["t_start"] - 2.3 * H, 3)
            escort = cands[2] if cands else None
        sv = self.services_for(plan, escort)
        if not sv:
            if force:
                raise RuntimeError("no service craft for forced departure")
            return False
        self.berth_stay(ag, t)
        self.berth_busy[bid] = [(a, (t + 40 * 60 if vid == v.id and b > 1e17 else b), vid) for a, b, vid in self.berth_busy[bid]]
        self.commit(plan, sv[0], sv[1], escort)
        dest = PORT_NAMES.get(ag.next_port, ag.next_port.upper())[:20]
        t_gate = self.depart_legs(v, BOARD, ag.gate, plan["m2"].t1, ag.out_draft, dest)
        c = ag.call
        c.atd, c.atd_port, c.status = t, plan["t_buoy"], "DEPARTED"
        ag.state, ag.berth = "away", None
        self.schedule_next(ag, t_gate)
        return plan

    def shift_ship(self, ag, new_bid, t, draft):
        """Move a ship from her berth to another berth inside the port with two tugs (dead slow)."""
        v, old = ag.v, ag.berth
        P = self.GM.nav_path(self.bpos(old), self.bpos(new_bid), 40, deep=True, start_at=self.bpos(old), end_at=self.bpos(new_bid))

        def vf(lat, lon, s):
            return 1.2 if (s < P.head + 30 or s > P.length - P.tail - 30) else 2.6
        m = make_move(P, t, vfun=vf, status=0, draft=draft, dest="CORPUS CHRISTI")
        tugs = self.pick_free(self.tug_roster, t - 2.3 * H, 2)
        if not tugs:
            raise RuntimeError("no tugs for the shift")
        v.add(m)
        for k, tug in enumerate(tugs):
            self.tug_job(tug, P, m, False, P.length - P.tail - 40.0 - 80.0 * k, P.head + 40.0 + 60.0 * k, None)
        self.berth_busy[old] = [(a, (t + 30 * 60 if vid == v.id and b > 1e17 else b), vid) for a, b, vid in self.berth_busy[old]]
        self.berth_busy[new_bid].append((t, 1e18, v.id))
        ag.berth = new_bid
        ag.call.shift = (m.t1, new_bid)
        self._order = getattr(self, "_order", 4000) + 1
        self.transits.append(dict(v=v, ag=ag, dir="SHIFT", berth=new_bid, zone="inner_w", m1=None, m2=m, P=P, t_start=t, t_board=t,
                                  t_buoy=-1e18, t_jetty=None, t_ferry=None, t_bridge=None, t_end=m.t1, t_in0=t, t_in1=m.t1,
                                  order=f"PO-{self._order:05d}", tugs=[x.name for x in tugs], pilot_boat="", from_berth=old))
        return m

    def leave_anchorage(self, ag, t, reason, status="CANCELLED"):
        """A waiting ship gives up and sails for another port."""
        v = ag.v
        a = self.anch[ag.anch]
        v.add(Stay(ag.anch_since, t, a, "anchored", place=ag.anch, status=1, draft=ag.in_draft, dest="CORPUS CHRISTI",
                   radius=float(v.rs.uniform(190, 300))))
        self.release_anchor(ag, t)
        dest = PORT_NAMES.get(ag.last_port if ag.direction == "IMPORT" else ag.next_port, "FOR ORDERS")[:20]
        t_gate = self.depart_legs(v, a, ag.gate, t, ag.in_draft, "FOR ORDERS" if v.rs.random() < 0.5 else dest)
        c = ag.call
        c.atd_anch, c.status = t, status
        c.hold.append((t, reason))
        ag.state, ag.anch = "away", None
        self.schedule_next(ag, t_gate, cancelled=True)

    def schedule_next(self, ag, t_free, cancelled=False):
        v = ag.v
        ag.last_free = t_free
        if ag.no_return:
            ag.next_eta = None
            return
        if ag.yankee and ag.storm_eta and t_free < ag.storm_eta - 5 * DAY:
            ag.next_eta = ag.storm_eta
            return
        away = max(ag.cycle * float(v.rs.uniform(0.9, 1.12)) - 2.5, 9.0) * DAY
        if cancelled:
            away = max(away * 0.6, 8 * DAY)
        ag.next_eta = t_free + away

    # ------------------------------------------------------------------ closures: what happens to an ETA
    def eta_policy(self, ag, t):
        """'arrive', or ('cancel', reason, next_eta) for an ETA that falls in a closure."""
        if ag.yankee and ag.storm_eta and abs(t - ag.storm_eta) < 1:
            return "arrive"
        if ag.scripted:
            return "arrive"
        if getattr(ag, "surge", False) and t < ts("2027-09-10T12:00Z"):
            return "arrive"
        if ts("2027-09-09T03:00Z") <= t < REOPEN1 - 2 * DAY:
            if t > ts("2027-09-19T00:00Z") and ag.v.rs.random() < 0.34 and self.anchored_count(t) < 23:
                return "arrive"
            return ("cancel", "Port Condition X-Ray/Yankee/Zulu; port closed" if t < ts("2027-09-15T00:00Z") else "ship channel closed")
        if BLAST <= t < REOPEN2 - 0.5 * DAY:
            if self.anchored_count(t) < 24 and ag.v.rs.random() < 0.7:
                return "arrive"
            return ("cancel", "ship channel closed")
        return "arrive"


def rng_hash(a, t):
    import zlib
    return (zlib.crc32(f"{a}|{int(t // 3600)}".encode()) % 1000) / 1000.0


class ShipLoopMixin:
    """The time loop for ocean-going traffic and the storm, reopening and blast scripting."""

    def storm_sortie(self, v, anch_id, t_leave, t_back, draft, k, dest="FOR ORDERS"):
        """Put to sea ahead of the hurricane, slow-steam well east of the track, come back."""
        a = self.anch[anch_id]
        off = -0.33 + 0.05 * k
        W1 = (27.70 + 0.4 * off, -95.9)
        W2 = (28.10 + off, -93.7 + 0.03 * k)
        W3 = (27.92 + off, -93.0 + 0.03 * k)
        p_out = mg.join(self.open_path(a, W1, seg=6000.0), self.open_path(W1, W2, seg=14000.0))
        L = p_out.length
        sp = 13.0 * v.spd

        def vo(lat, lon, s):
            return 2.5 if s < 300 else (8.0 if s < 2500 else sp)
        m_out = make_move(p_out, t_leave, vfun=vo, draft=draft, dest=dest)
        v.add(m_out)
        p_back = p_out.reversed()
        sb = 12.0 * v.spd

        def vb(lat, lon, s):
            return 4.0 if s > L - 700 else (8.0 if s > L - 4000 else sb)
        probe = make_move(p_back, 0.0, vfun=vb)
        t_ret = t_back - probe.t1
        p_l = self.open_path(W2, W3, seg=14000.0)
        avail = t_ret - m_out.t1
        leg = p_l.length / (5.5 * KN)
        n = max(2, int(round(avail / leg / 2.0)) * 2)
        dt = avail / n
        tt = m_out.t1
        for i in range(n):
            v.add(make_move(p_l, tt, t1=tt + dt, s0=(0.0 if i % 2 == 0 else p_l.length), s1=(p_l.length if i % 2 == 0 else 0.0),
                            draft=draft, dest=dest))
            tt += dt
        v.add(make_move(p_back, t_ret, vfun=vb, draft=draft, dest=dest))
        return t_back

    def run_ships(self):
        self.setup_agents()
        A = self.agents
        gp = A["VSL-0012"]
        step = 600.0
        t = T_WARM
        flags = set()
        lock = None
        while t < T_END + 2 * H:
            # ---------------- arrivals
            due = sorted((ag for ag in A.values() if ag.state == "away" and ag.next_eta is not None and ag.next_eta <= t),
                         key=lambda g: g.next_eta)
            for ag in due:
                pol = self.eta_policy(ag, ag.next_eta)
                if pol == "arrive":
                    self.do_arrive(ag, ag.next_eta)
                else:
                    c = self.new_call(ag, ag.next_eta)
                    c.status = "CANCELLED"
                    c.hold.append((min(ag.next_eta - 20 * H, max(c.noa_time + 6 * H, XRAY if ag.next_eta < REOPEN1 else BLAST + 3 * H)), pol[1]))
                    ag.next_eta = ag.next_eta + ag.cycle * DAY * float(ag.v.rs.uniform(0.75, 1.05))
            # ---------------- the week before landfall: exporters bring loadings forward to get cargoes away ahead of the storm
            if "surge" not in flags and t >= ts("2027-09-03T00:00Z"):
                flags.add("surge")
                cand = sorted((g for g in A.values() if g.state == "away" and g.next_eta is not None and not g.yankee and not g.scripted and not g.no_return
                               and g.next_eta > ts("2027-09-08T18:00Z") and getattr(g, "last_free", 0.0) <= ts("2027-08-29T00:00Z")
                               and g.v.id not in ("VSL-0041", "VSL-0042", "VSL-0019", "VSL-0012")),
                              key=lambda g: (g.kind not in ("crude", "lng", "product"), g.next_eta))[:9]
                for i, g in enumerate(sorted(cand, key=lambda g: g.next_eta)):
                    g.next_eta = ts("2027-09-06T22:00Z") + i * 8.4 * H + float(g.v.rs.uniform(-2, 2)) * H
                    g.surge = True
            # ---------------- scripted: storm
            if "prestorm" not in flags and t >= LAST_IN_PRESTORM:
                flags.add("prestorm")
                berthed = sorted((g for g in A.values() if g.state == "berthed" and g.ready_at < 1e17), key=lambda g: g.ready_at)
                caps = np.linspace(ts("2027-09-11T20:00Z"), LAST_OUT_PRESTORM - 2.5 * H, max(len(berthed), 1))
                for g, cap in zip(berthed, caps):
                    g.ready_at = min(g.ready_at, float(cap))
                waiting = [g for g in A.values() if g.state == "anchored" and not (g.yankee and g.not_before >= REOPEN1)]
                for i, g in enumerate(sorted(waiting, key=lambda g: g.anch_since)):
                    g.leave_at = t + (1.0 + 2.2 * i) * H
                    g.leave_reason = "sailed ahead of Hurricane Rafael; call cancelled"
            if "zulu" not in flags and t >= ZULU:
                flags.add("zulu")
                riders = sorted((g for g in A.values() if g.state == "anchored"), key=lambda g: g.anch)
                self.notes.append(("anchored_at_zulu", [g.v.id for g in riders]))
                n = len(riders) + 1          # Halcyon Drift sails with them (scripted separately as slot k = n - 1)
                for k, g in enumerate(riders):
                    t_leave = ZULU + (9 + 17.5 * k) * 60
                    t_back = RETURN_D3_A + (RETURN_D3_B - RETURN_D3_A) * (k + 0.5) / n
                    a = self.anch[g.anch]
                    g.v.add(Stay(g.anch_since, t_leave, a, "anchored", place=g.anch, status=1, draft=g.in_draft,
                                 dest="CORPUS CHRISTI", radius=float(g.v.rs.uniform(190, 300))))
                    self.storm_sortie(g.v, g.anch, t_leave, t_back, g.in_draft, k)
                    g.anch_since = t_back
                    g.not_before = REOPEN1
                    if not any("Yankee" in h[1] for h in g.call.hold):
                        g.call.hold.append((max(YANKEE, g.anch_since_first if hasattr(g, "anch_since_first") else YANKEE), "Port Condition Yankee: port closed to inbound; holding at anchorage"))
                    g.call.hold.append((ZULU, "Port Condition Zulu: directed to sea"))
                    g.call.hold.append((t_back, "returned to anchorage; ship channel closed"))
                    g.storm_slot = (t_leave, t_back)
                self.halcyon_slot = (ZULU + (9 + 17.5 * (n - 1)) * 60, RETURN_D3_A + (RETURN_D3_B - RETURN_D3_A) * (n - 0.5) / n, n - 1)
            if "reopen1" not in flags and t >= REOPEN1:
                flags.add("reopen1")
                gp.forced_berth = "TERM-07-B02"
                gp.not_before = ts("2027-10-17T13:20Z")
                i = 0
                for g in sorted((g for g in A.values() if g.state == "anchored"), key=lambda g: g.anch_since):
                    zones = {self.berths[b]["zone"] for b in self.berth_candidates(g, t)}
                    if g is not gp and not (zones & {"laq", "inner_e"}):
                        g.leave_at = t + (5.0 + 7.0 * i) * H
                        g.leave_reason = "berth not available under the inner-channel restriction; diverted"
                        i += 1
                    if g.kind == "lng":
                        g.not_before = REOPEN1
                    elif g is not gp:
                        g.not_before = max(g.not_before, REOPEN1 + 20 * 60)
            # ---------------- scripted: the ship escorted by Corrin Bay on the night of the blast
            if "blastship" not in flags and t >= ts("2027-10-24T12:00Z"):
                # make sure a laden tanker is alongside in the Main Turning Basin on the night of D+43/44
                flags.add("blastship")
                pool = [g for g in A.values() if g.kind == "crude" and not g.scripted]

                def rank(g):
                    if g.state == "berthed" and self.berths[g.berth]["zone"] == "inner_e" and g.ready_at > BLAST - 30 * H:
                        return (0, g.ready_at)
                    if g.state == "anchored":
                        return (1, g.anch_since)
                    if g.state == "away" and g.next_eta is not None and g.v.busy_until < t - 4 * H:
                        return (2, g.next_eta)
                    return (9, 0)
                pool.sort(key=rank)
                bs = pool[0]
                if rank(bs)[0] == 9:
                    raise RuntimeError("no tanker can be alongside for the night of the blast")
                if bs.state == "away":
                    bs.next_eta = t + 72 * H if bs.v.busy_until > t - 70 * H else t + 5 * H
                    bs.next_eta = min(bs.next_eta, ts("2027-10-26T20:00Z"))
                bs.scripted = True
                self.blast_agent = bs
            bs = getattr(self, "blast_agent", None)
            if bs is not None and lock is None:
                if bs.state == "anchored":
                    bs.min_wait_until = min(bs.min_wait_until, t)
                elif bs.state == "berthed":
                    lock = bs
                    lock.ready_at = 1e18
            if lock is not None and "escort" not in flags and t >= BLAST - 4 * H:
                flags.add("escort")
                probe = self.plan_outbound(lock, 0.0, lock.berth)
                s_tip = self.s_at_lon(probe["P"], LON_TIPS)
                t_dep = ts("2027-10-28T06:00Z") - probe["m2"].t_at_s(s_tip)
                lock.ready_at = t_dep
                plan = self.try_outbound(lock, t_dep, escort=self.vessels["VSL-0077"], force=True)
                self.escort_plan = plan
            # ---------------- scripted: the two tankers shift to lay berths on D+62
            for vid, when, nb in (("VSL-0041", ts("2027-11-15T15:00Z"), "TERM-13-B01"), ("VSL-0042", ts("2027-11-15T19:00Z"), "TERM-15-B01")):
                if vid not in flags and t >= when:
                    flags.add(vid)
                    g = A[vid]
                    full = g.v.draft_max
                    g.v.add(Stay(g.berth_since, ts("2027-09-13T02:00Z"), self.bpos(g.berth), "moored", heading=self.berths[g.berth]["heading_deg"],
                                 place=g.berth, status=5, draft=g.in_draft, dest="CORPUS CHRISTI"))
                    g.v.add(Stay(ts("2027-09-13T02:00Z"), when, self.bpos(g.berth), "moored", heading=self.berths[g.berth]["heading_deg"],
                                 place=g.berth, status=5, draft=full, dest=PORT_NAMES.get(g.next_port, "")[:20]))
                    m = self.shift_ship(g, nb, when, full)
                    g.v.add(Stay(m.t1, T_END + 2 * H, self.bpos(nb), "moored", heading=self.berths[nb]["heading_deg"], place=nb, status=5,
                                 draft=full, dest=PORT_NAMES.get(g.next_port, "")[:20]))
                    g.call.status = "REMAINING IN PORT"
            # ---------------- ships that give up waiting
            for g in A.values():
                if g.state == "anchored" and getattr(g, "leave_at", None) and t >= g.leave_at:
                    self.leave_anchorage(g, g.leave_at, g.leave_reason)
                    g.leave_at = None
            # ---------------- departures, then berthing
            if not (BLACKOUT_FROM - 1.5 * H <= t < REOPEN2):
                for g in sorted((g for g in A.values() if g.state == "berthed" and g is not lock and g.ready_at < 1e17), key=lambda g: g.ready_at):
                    if g.ready_at <= t:
                        self.try_outbound(g, t)
            if t < LAST_IN_PRESTORM or REOPEN1 <= t < BLACKOUT_FROM or t >= REOPEN2:
                order = sorted((g for g in A.values() if g.state == "anchored"),
                               key=lambda g: (0 if (g.kind == "lng" and t >= REOPEN1) else 1, g.anch_since))
                started = 0
                for g in order:
                    if started:
                        break
                    if self.try_inbound(g, t):
                        started += 1
            t += step
        if lock is None or "escort" not in flags:
            raise RuntimeError("no ship was available for the escorted departure before the blast")
        # ---------------- close out at the end of the span
        for g in A.values():
            if g.state == "anchored":
                g.v.add(Stay(g.anch_since, T_END + 2 * H, self.anch[g.anch], "anchored", place=g.anch, status=1, draft=g.in_draft,
                             dest="CORPUS CHRISTI", radius=float(g.v.rs.uniform(190, 300))))
            elif g.state == "berthed" and g.v.id not in ("VSL-0041", "VSL-0042"):
                g.call.status = "IN PORT"
                self.berth_stay(g, T_END + 2 * H)
        self.log(f"  ships: {len(self.calls)} calls, {len(self.transits)} piloted movements")
