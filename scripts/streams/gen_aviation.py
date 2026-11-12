"""ADS-B stream generator (05_other_sources/adsb/adsb_YYYY-MM.csv).

    python3 scripts/streams/gen_aviation.py

OpenSky state-vector CSV plus nic / nac_p. Every flight has a purpose and a type-appropriate
profile, flies between real runways, pads and places, and follows the canon timeline: ordinary
traffic before the storm, the Navy training aircraft leaving on D-4, the flight restriction from
D-2, the hurricane hunter and the first rescue helicopter on landfall night, the rescue surge,
the survey and relief flights, the GPS interference of D+38 to D+43, the channel search and the
sealift. Covert drones never appear here. See scripts/streams/README.md.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sar_plan import HELICOPTER_SORTIES
from common import *            # noqa: F401,F403
from aviation_lib import *      # noqa: F401,F403
import aviation_lib as AL

F = Fields()
G = None
AREAS = {a["area_id"]: a for a in reg("areas")["areas"]}
INFRA = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"] if a.get("latitude") is not None}
FAC = {f["facility_id"]: f for f in reg("facility_registry")["facilities"]}
TERM = reg("terminal_registry")

HEADER = ["icao24", "callsign", "origin_country", "time_position", "last_contact", "longitude", "latitude", "baro_altitude",
          "on_ground", "velocity", "true_track", "vertical_rate", "sensors", "geo_altitude", "squawk", "spi", "position_source",
          "category", "nic", "nac_p"]

T_TFR = local_ts(-2, "00:01")
JAMMER = xy(INFRA["TANK-0390"]["latitude"], INFRA["TANK-0390"]["longitude"])
# interference: on daily from mid-morning to late evening local, D+38 to D+43 (hidden schedule of the transmitter)
JAM_WINDOWS = [(local_ts(d, "08:10") + (d * 437) % 1500, local_ts(d, "22:40") + (d * 911) % 1800) for d in range(38, 44)]

PADS = {
    "SRMC": xy(27.77783, -97.39437), "BCMC": xy(27.69227, -97.34572), "SCMH": xy(27.68514, -97.37745),
    "GCCH": xy(27.7487, -97.3849), "ABCH": xy(27.91332, -97.15935), "DPS": xy(27.74114, -97.43499),
    "AIRMED": xy(27.71838, -97.55239),
}
PLACES = {  # story and survey locations (lat, lon), all from the registries
    "north_beach": (27.82976, -97.38457), "flour_bluff": (27.67054, -97.30216), "calallen": (27.86746, -97.62514),
    "downtown": (27.79501, -97.39805), "hillcrest": (27.80637, -97.41326), "molina": (27.7674, -97.4455),
    "port_aransas": (27.83392, -97.06111), "rockport": (28.02058, -97.05444), "portland": (27.87725, -97.32389),
    "ingleside": (27.87781, -97.21166), "aransas_pass": (27.90947, -97.15), "inner_harbor": (27.81447, -97.40133),
    "nueces_bay": (27.852, -97.445), "wtp": (27.86056, -97.62139), "nas": (27.69242, -97.27931),
    "jetties": (27.8366, -97.0391), "harbor_bridge": (27.81097, -97.39678), "causeway": (27.85231, -97.35869),
    "sub01": (27.80951, -97.45564), "sub02": (27.8021, -97.45287), "sub03": (27.7706, -97.41624),
    "sub04": (27.74299, -97.42308), "sub05": (27.70022, -97.33461), "padre": (27.61492, -97.22138),
    "bay_mid": (27.77, -97.25), "sea_buoy": (27.79312, -96.96336), "anchorage": (27.84, -96.92),
    "viola": (27.8408, -97.5139), "cc_bay_west": (27.79, -97.34), "robstown": (27.79031, -97.66889),
}
PX = {k: xy(*v) for k, v in PLACES.items()}


def P(name):
    return PX[name]


def bbox_pts(area_id, rng, n, classes=("local", "arterial")):
    b = AREAS[area_id]["bbox"]
    out = []
    for _ in range(n * 6):
        r = G.roads.random_point(rng, box=tuple(b), classes=classes)
        if r and G.is_land(r[0], r[1]):
            out.append(xy(r[0], r[1]))
        if len(out) >= n:
            break
    return out


# ============================================================================ simulator
class Sim:
    def __init__(self):
        self.rows = defaultdict(list)
        self.busy = {}                      # aircraft_id -> time free
        self.loc = {}                       # aircraft_id -> where it is parked ("CRP", "NGP", pad name, "away")
        self.spot = {}                      # aircraft_id -> parking xy (when visiting)
        self.log = []
        for a in F.ac.values():
            self.busy[a["aircraft_id"]] = SPAN_START - 86400
            hb = a.get("home_base")
            self.loc[a["aircraft_id"]] = hb if (hb and F.local(hb)) else ("away" if hb else "pad")
        self.tr = 0                         # transient ramp counter

    # ---- helpers
    def ac(self, call):
        return F.by_call[call]

    def perf(self, a):
        p = dict(PERF[a["type_designator"]])
        p["vc"] = a["cruise_speed_kt"] * KT
        return p

    def home_xy(self, a):
        return F.park_xy(a["parking_position_id"])

    def here_xy(self, a):
        return self.spot.get(a["aircraft_id"], self.home_xy(a))

    def transient(self, afid):
        ids = ([p for p in F.park if p.startswith("PARK-%s-T" % afid)] or [p for p in F.park if p.startswith("PARK-%s-A1" % afid)]
               or [p for p in F.park if p.startswith("PARK-%s-" % afid)])
        self.tr += 1
        return F.park_xy(sorted(ids)[self.tr % len(ids)])

    def free(self, a, t):
        return self.busy[a["aircraft_id"]] <= t

    def squawk(self, a, kind, key):
        if kind == "vfr":
            return "1200"
        if kind == "sar":
            return "1277"
        r = rng("adsb-squawk", a["icao24"], key)
        while True:
            s = "".join(str(int(r.integers(0, 8))) for _ in range(4))
            if s not in ("7500", "7600", "7700", "1200", "1277", "0000") and s[0] != "7":
                return s

    # ---- emission
    def emit(self, a, trk, squawk, purpose, dest_loc=None, spot=None):
        perf = PERF[a["type_designator"]]
        rows = sample(trk, perf.get("win", 30))
        icao = a["icao24"]
        call = call8(a["callsign"])
        cat = a["adsb_emitter_category"]
        r = rng("adsb-noise", icao, int(trk.k[0][0]))
        base_nic = 8 if (a.get("military") or cat >= 3) else int(r.choice([7, 8, 8]))
        base_nac = 10 if base_nic == 8 and cat >= 3 else 9
        n = 0
        t_first = t_last = None
        for (t, x, y, alt, gnd, sp, trkdeg, vr) in rows:
            if not visible(x, y, alt, gnd):
                continue
            t = int(round(t))
            nic, nac, src = base_nic, base_nac, 0
            if not gnd:
                j = jam(t, x, y, alt, icao)
                if j:
                    nic, nac, dx, dy, src = j
                    x, y = x + dx, y + dy
                elif r.random() < 0.003:
                    nic, nac = base_nic - 1, base_nac - 1
            lat, lon = ll(x, y)
            if gnd:
                baro = geo_alt = ""
                geo_alt = round(4.0 + r.normal(0, 0.8), 1)
                vrs = 0.0
            else:
                dp = pressure_deficit(t, lat, lon)
                geo_alt = round(alt + r.normal(0, 3.0), 1)
                baro = round(alt + 8.3 * dp + r.normal(0, 2.0), 1)
                vrs = round(vr, 2)
            row = [icao, call, "United States", t, t + int(r.integers(0, 2)), round(lon, 5), round(lat, 5), baro,
                   "True" if gnd else "False", round(sp, 1), round(trkdeg, 1), vrs, "", geo_alt, squawk, "False", src, cat, nic, nac]
            self.rows[iso(t)[:7]].append(row)
            n += 1
            t_first = t if t_first is None else t_first
            t_last = t
        self.busy[a["aircraft_id"]] = trk.t + 300
        if dest_loc is not None:
            self.loc[a["aircraft_id"]] = dest_loc
        if spot is not None:
            self.spot[a["aircraft_id"]] = spot
        elif dest_loc is not None and dest_loc == a.get("home_base"):
            self.spot.pop(a["aircraft_id"], None)
        self.log.append((a["callsign"], purpose, iso(trk.k[0][0]), iso(trk.t), n))
        return trk.t

    # ---- fixed wing ---------------------------------------------------------------------
    def fw(self, call, t0, origin, dest, via=(), cruise=None, purpose="", squawk="ifr", low_tag="e", dest_spot=None):
        """Fixed-wing flight. origin/dest: local airfield id, or ("far", airfield id) to enter or
        leave coverage on the bearing of a distant field. via items:
           (x, y, alt_m, v, tag) waypoint | ("LA", airfield) low approach | ("ORB", cx, cy, r, turns, alt, v, tag)
        t0 is the off-blocks time for local origins, or the time the aircraft enters coverage."""
        a = self.ac(call)
        perf = self.perf(a)
        vc = perf["vc"]
        r = rng("adsb-fw", call, int(t0))
        cruise = cruise if cruise is not None else float(r.uniform(*perf["alt"]))
        if isinstance(origin, tuple):
            dest_xy = F.pt(dest) if not isinstance(dest, tuple) else (0, 0)
            start, b, D = far_point(F, origin[1], dest_xy)
            alt0 = min(cruise, perf["alt"][1])
            if D < 170 * NM:                                   # the field itself is inside coverage range: climb out of it
                trk = Trk(t0, start[0], start[1], 60.0, False, "t")
                trk.v = perf["vcl"]
                tgt = (via[0][0], via[0][1]) if (via and not isinstance(via[0][0], str)) else dest_xy
                trk.go(start[0] + (tgt[0] - start[0]) * 0.4, start[1] + (tgt[1] - start[1]) * 0.4, alt0, vc, "e", roc=perf["roc"])
            else:
                trk = Trk(t0, start[0], start[1], alt0, False, "e")
                trk.v = vc
        else:
            trk = Trk(t0 - 150, *self.here_xy(a))
            trk.wait(150, tag="p")
            fw_takeoff(trk, F, origin, perf, vc, r)
        for w in via:
            if w[0] == "LA":
                fw_land(trk, F, w[1], perf, None, r, low_approach=True)
            elif w[0] == "ORB":
                _, cx, cy, rad, turns, alt, v, tag = w
                x0, y0 = trk.p
                a0 = math.atan2(x0 - cx, y0 - cy)
                steps = max(8, int(16 * turns))
                for i in range(1, steps + 1):
                    ang = a0 + 2 * math.pi * turns * i / steps
                    trk.go(cx + rad * math.sin(ang), cy + rad * math.cos(ang), alt, v or vc * 0.8, tag, roc=perf["roc"], rod=perf["rod"])
            else:
                x, y, alt, v, tag = w
                trk.go(x, y, alt, v or vc, tag, roc=perf["roc"], rod=perf["rod"])
        if isinstance(dest, tuple):
            end, b, D = far_point(F, dest[1], trk.p)
            x0, y0 = trk.p
            # climb out on the way
            d = math.hypot(end[0] - x0, end[1] - y0)
            f = min(0.5, 30000.0 / max(d, 1.0))
            trk.go(x0 + (end[0] - x0) * f, y0 + (end[1] - y0) * f, min(cruise, trk.alt + perf["roc"] * 30000.0 / max(perf["vcl"], 40)), (perf["vcl"] + vc) / 2, "t" if trk.alt < 900 else "e", roc=perf["roc"])
            if D < 170 * NM:                                   # lands at a field we can still partly see: descend into it
                x1, y1 = trk.p
                trk.go(x1 + (end[0] - x1) * 0.55, y1 + (end[1] - y1) * 0.55, cruise, vc, "e", roc=perf["roc"] * 0.8)
                trk.go(end[0], end[1], 60.0, perf["vapp"] * 1.2, "e", rod=perf["rod"])
            else:
                trk.go(end[0], end[1], cruise, vc, "e", roc=perf["roc"] * 0.8)
            self.emit(a, trk, self.squawk(a, squawk, int(t0)), purpose, dest_loc="away")
        else:
            spot = dest_spot or (self.home_xy(a) if dest == a.get("home_base") else self.transient(dest))
            fw_land(trk, F, dest, perf, spot, r)
            self.emit(a, trk, self.squawk(a, squawk, int(t0)), purpose, dest_loc=dest, spot=None if dest == a.get("home_base") else spot)
        return trk.t

    # ---- helicopters ----------------------------------------------------------------------
    def helo(self, call, t0, legs, start=None, end=None, purpose="", squawk="vfr", end_loc=None, enter_from=None, exit_to=None):
        """Helicopter flight from where the aircraft is parked (or entering coverage from a distant
        field). legs: ("go", x, y, alt, v) | ("hover", x, y, alt, seconds) | ("pad", x, y, seconds_on_ground)
        | ("orbit", cx, cy, r, turns, alt, v) | ("lines", [(x, y), ...], alt, v)."""
        a = self.ac(call)
        perf = self.perf(a)
        vc = perf["vc"]
        r = rng("adsb-helo", call, int(t0))
        calt = float(r.uniform(*perf["alt"]))
        if enter_from:
            first = legs[0]
            tgt = (first[1], first[2]) if first[0] in ("go", "hover", "pad") else P("downtown")
            startp, b, D = far_point(F, enter_from, tgt, dist_nm=95.0)
            trk = Trk(t0, startp[0], startp[1], max(calt, 600.0), False, "e")
            trk.v = vc
        else:
            sx, sy = start or self.here_xy(a)
            trk = Trk(t0 - 120, sx, sy)
            trk.wait(120, tag="p")
            first = legs[0]
            tx, ty = (first[1], first[2]) if first[0] in ("go", "hover", "pad", "orbit") else first[1][0]
            helo_lift(trk, calt, vc, hdg(tx - sx, ty - sy), perf)
        for leg in legs:
            k = leg[0]
            if k == "go":
                _, x, y, alt, v = leg
                helo_goto(trk, x, y, alt or calt, v or vc, perf)
            elif k == "hover":
                _, x, y, alt, dur = leg
                helo_goto(trk, x, y, alt, vc, perf, stop=True, cruise=calt)
                trk.hover(dur, r, drift=10.0, alt=alt)
            elif k == "pad":
                _, x, y, dur = leg
                helo_land(trk, x, y, perf, v=vc * 0.8, cruise=calt)
                trk.wait(dur, tag="p")
                helo_lift(trk, calt, vc, float(r.uniform(0, 360)), perf)
            elif k == "orbit":
                _, cx, cy, rad, turns, alt, v = leg
                x0, y0 = trk.p
                a0 = math.atan2(x0 - cx, y0 - cy)
                helo_goto(trk, cx + rad * math.sin(a0), cy + rad * math.cos(a0), alt, vc, perf)
                steps = max(8, int(12 * turns))
                for i in range(1, steps + 1):
                    ang = a0 + 2 * math.pi * turns * i / steps
                    trk.go(cx + rad * math.sin(ang), cy + rad * math.cos(ang), alt, v, "t")
            elif k == "lines":
                _, pts, alt, v = leg
                for (x, y) in pts:
                    trk.go(x, y, alt, v, "l", roc=perf["roc"], rod=perf["rod"])
        if exit_to:
            endp, b, D = far_point(F, exit_to, trk.p, dist_nm=95.0)
            trk.go(endp[0], endp[1], max(calt, 600.0), vc, "e", roc=perf["roc"])
            self.emit(a, trk, self.squawk(a, squawk, int(t0)), purpose, dest_loc="away")
        else:
            ex, ey = end or self.here_xy(a)
            helo_land(trk, ex, ey, perf, v=vc * 0.8, cruise=calt)
            trk.wait(15, tag="p")
            if end_loc:
                dl = end_loc
            elif end is None:
                dl = a["home_base"] if (a.get("home_base") and F.local(a["home_base"])) else "pad"
                if self.spot.get(a["aircraft_id"]) is not None:
                    dl = self.loc[a["aircraft_id"]] if self.loc[a["aircraft_id"]] != "away" else dl
            else:
                dl = self.loc[a["aircraft_id"]]
            self.emit(a, trk, self.squawk(a, squawk, int(t0)), purpose, dest_loc=dl, spot=(ex, ey) if end else self.spot.get(a["aircraft_id"]))
        return trk.t


def call8(cs):
    """Transponder call signs are at most 8 characters: longer registry call signs keep their
    first six characters and their two-digit number (GUNSMOKE02 -> GUNSMO02)."""
    if len(cs) > 8:
        cs = cs[:6] + cs[-2:]
    return cs.ljust(8)


def pressure_deficit(t, lat, lon):
    """hPa below standard at a point (storm low plus slow synoptic wobble); drives baro vs GNSS altitude."""
    c = storm_center(t)
    syn = -2.0 + 3.5 * math.sin(t / 86400.0 / 5.3) + 2.0 * math.sin(t / 86400.0 / 1.9)
    if c is None:
        return syn
    dy = (lat - c[0]) * 60.0
    dx = (lon - c[1]) * 60.0 * math.cos(math.radians(lat))
    rr = math.hypot(dx, dy)
    depth = max(0.0, (c[2] - 30.0) / 80.0) * 70.0
    return syn + depth * math.exp(-rr / 45.0)


def jam(t, x, y, alt, icao):
    """GPS interference as a receiver would report it: (nic, nac_p, dx, dy, position_source) or None."""
    if t < JAM_WINDOWS[0][0] or t > JAM_WINDOWS[-1][1]:
        return None
    if not any(a <= t <= b for a, b in JAM_WINDOWS):
        return None
    d = math.hypot(x - JAMMER[0], y - JAMMER[1]) / 1000.0
    if d > 60.0:
        return None
    if d > 5.0 and alt < ((d - 5.0) / 3.57) ** 2:      # below the transmitter's radio horizon
        return None
    r = rng("adsb-jam", icao, t)
    s = 1.0 - d / 60.0
    if r.random() > 0.55 + 0.45 * s:                   # some messages still carry good fixes, more often far out
        return (int(r.choice([6, 7])), int(r.choice([7, 8])), 0.0, 0.0, 0)
    nic = int(r.choice([0, 0, 0, 1, 2, 3, 4, 5]) if s > 0.5 else r.choice([0, 2, 3, 4, 5, 6, 6]))
    nac = int(r.choice([0, 0, 1, 2, 4, 5]) if s > 0.5 else r.choice([0, 3, 4, 5, 6, 7]))
    if r.random() < 0.18:                              # multilateration fix: good position, no integrity
        return (0, 0, r.normal(0, 60.0), r.normal(0, 60.0), 2)
    sig = 250.0 + 1400.0 * s
    dx, dy = r.normal(0, sig), r.normal(0, sig)
    if r.random() < 0.10:                              # position jump
        ang = r.uniform(0, 2 * math.pi)
        mag = r.uniform(3000, 9000)
        dx, dy = dx + mag * math.sin(ang), dy + mag * math.cos(ang)
    return (nic, nac, dx, dy, 0)


# ============================================================================ schedule
def weekday(day):
    return (1 + day) % 7          # Monday = 0; D0 is a Tuesday


def readiness(day):
    pts = [(-50, 92), (40, 61), (110, 85)]
    if day <= pts[0][0]:
        return pts[0][1] / 92.0
    for (d0, p0), (d1, p1) in zip(pts, pts[1:]):
        if d0 <= day <= d1:
            return (p0 + (p1 - p0) * (day - d0) / (d1 - d0)) / 92.0
    return pts[-1][1] / 92.0


HOLIDAYS = {72, 73, 101, 102, 103, 109}      # Thanksgiving Thu/Fri, Dec 24-26, Jan 1


def lawnmower(x0, y0, x1, y1, n, vertical=False):
    pts = []
    for i in range(n):
        f = i / max(1, n - 1)
        if vertical:
            x = x0 + (x1 - x0) * f
            pts += [(x, y0), (x, y1)] if i % 2 == 0 else [(x, y1), (x, y0)]
        else:
            y = y0 + (y1 - y0) * f
            pts += [(x0, y), (x1, y)] if i % 2 == 0 else [(x1, y), (x0, y)]
    return pts


def build(sim):
    S = sim
    ngp, crp = F.pt("NGP"), F.pt("CRP")
    MOA = {"south": xy(27.25, -97.05), "west": xy(27.95, -98.15), "north": xy(28.45, -97.75), "gulf": xy(27.45, -96.55)}

    # ---------------------------------------------------------------- airlines
    AIR = [("CPA2231", "DFW", "07:35", "14:20"), ("CPA2245", "IAH", "08:50", "16:05"), ("CPA2262", "DFW", "10:40", "18:15"),
           ("LMA614", "HOU", "09:25", "17:10"), ("LMA628", "DAL", "11:55", "19:20")]

    def airline_day(day):
        if -3 < day < 5:
            return
        r = rng("adsb-airline", day)
        for call, hub, am, pm in AIR:
            slots = [am, pm]
            if day == -3:
                slots = [am] if pm > "16:30" else [am, pm]
            elif 5 <= day <= 7:
                slots = [am] if call in ("CPA2231", "LMA614", "CPA2245") else []
            for sl in slots:
                if r.random() < 0.035:
                    continue                                   # cancelled rotation
                t_in = local_ts(day, sl) + int(r.normal(0, 420))
                t_land = S.fw(call, t_in, ("far", hub), "CRP", purpose="scheduled arrival from " + hub)
                S.fw(call, t_land + int(r.uniform(33, 52) * 60), "CRP", ("far", hub), purpose="scheduled departure to " + hub)

    # ---------------------------------------------------------------- Navy training
    T6 = ["MARLIN1%d" % i for i in range(1, 9)]
    T44 = ["PELICAN2%d" % i for i in range(1, 5)]
    T45 = ["JAVELINA3%d" % i for i in range(1, 7)]

    def t6_sortie(call, t0):
        r = rng("adsb-t6", call, t0)
        a = S.ac(call)
        vc = a["cruise_speed_kt"] * KT
        area = MOA[str(r.choice(["south", "gulf", "west"]))]
        alt = float(r.uniform(2400, 4600))
        via = [(area[0] + r.normal(0, 4000), area[1] + r.normal(0, 4000), alt, vc, "e")]
        for _ in range(int(r.integers(3, 6))):
            via.append((area[0] + r.normal(0, 9000), area[1] + r.normal(0, 9000), alt + r.normal(0, 500), vc * r.uniform(0.75, 1.0), "e"))
        olf = str(r.choice(["NGW", "NWL"]))
        via += [("LA", olf)] * int(r.integers(1, 4))
        S.fw(call, t0, "NGP", "NGP", via=via, cruise=alt, purpose="training sortie")

    def t44_sortie(call, t0):
        r = rng("adsb-t44", call, t0)
        a = S.ac(call)
        vc = a["cruise_speed_kt"] * KT
        if r.random() < 0.25:
            far = str(r.choice(["SAT", "VCT", "BRO", "MFE"]))
            S.fw(call, t0, "NGP", ("far", far), purpose="instrument cross-country out")
            back = t0 + int(r.uniform(2.3, 3.4) * 3600)
            S.fw(call, back, ("far", far), "NGP", purpose="instrument cross-country return")
            return
        via = [(MOA["north"][0] * 0.35 + r.normal(0, 5000), MOA["north"][1] * 0.35 + r.normal(0, 5000), 1800, vc, "e"),
               ("LA", "RKP"), ("LA", "CRP")]
        if r.random() < 0.5:
            via.append(("LA", "NGW"))
        S.fw(call, t0, "NGP", "NGP", via=via, cruise=1800, purpose="instrument training")

    def t45_sortie(call, t0):
        r = rng("adsb-t45", call, t0)
        a = S.ac(call)
        vc = a["cruise_speed_kt"] * KT
        area = xy(27.15 + r.normal(0, 0.08), -98.25 + r.normal(0, 0.1)) if r.random() < 0.6 else xy(27.0 + r.normal(0, 0.06), -97.2 + r.normal(0, 0.08))
        alt = float(r.uniform(4600, 7600))
        via = [(area[0], area[1], alt, vc, "e")]
        for _ in range(int(r.integers(3, 6))):
            via.append((area[0] + r.normal(0, 14000), area[1] + r.normal(0, 14000), alt + r.normal(0, 700), vc * r.uniform(0.8, 1.05), "e"))
        if r.random() < 0.5:
            via.append(("LA", "NQI"))
        S.fw(call, t0, "NQI", "NQI", via=via, cruise=alt, purpose="jet training sortie")

    def navy_day(day):
        r = rng("adsb-navy", day)
        if day == -4:                                         # hurricane evacuation to Fort Worth, in waves
            waves = [("13:20", T6[:4]), ("14:40", T6[4:]), ("15:50", T44), ("16:50", T45[:3]), ("18:10", T45[3:])]
            for hh, calls in waves:
                for i, c in enumerate(calls):
                    S.fw(c, local_ts(day, hh) + i * 170 + int(r.uniform(0, 40)), "NQI" if c.startswith("JAV") else "NGP", ("far", "NFW"),
                         purpose="hurricane evacuation to NAS JRB Fort Worth")
            return
        if -4 < day < 6:
            return
        if 6 <= day <= 8:                                     # return, a few each day
            back = {6: T6[:4] + T44[:2], 7: T6[4:] + T44[2:], 8: T45}[day]
            for i, c in enumerate(back):
                S.fw(c, local_ts(day, "10:30") + i * 1500 + int(r.uniform(0, 600)), ("far", "NFW"), "NQI" if c.startswith("JAV") else "NGP",
                     purpose="return from NAS JRB Fort Worth")
            return
        wd = weekday(day)
        scale = readiness(day)
        if day in HOLIDAYS:
            return
        if 97 <= day <= 110:
            scale *= 0.2
        if wd >= 5:
            scale *= 0.06
        if day == 9 or day == 10:
            scale *= 0.5
        for calls, fn, slots, p in ((T6, t6_sortie, ("08:10", "13:30"), 0.80), (T44, t44_sortie, ("08:40", "14:00"), 0.62),
                                    (T45, t45_sortie, ("08:20", "13:10"), 0.72)):
            for c in calls:
                if 6 <= day < 9 and c in T45:
                    continue
                for sl in slots:
                    if r.random() < p * scale:
                        t0 = local_ts(day, sl) + int(r.uniform(0, 5400))
                        if t0 + 3 * 3600 < T_TFR or day > 0:
                            if S.free(S.ac(c), t0) and S.loc[S.ac(c)["aircraft_id"]] != "away":
                                fn(c, t0)

    # ---------------------------------------------------------------- Coast Guard
    CGH = ["C6033", "C6041", "C6017", "C6028"]

    def cg_helo_routine(call, t0, r):
        kind = r.choice(["patrol", "hoist", "bay"])
        calt = float(r.uniform(150, 350))
        if kind == "patrol":
            legs = [("go", *P("port_aransas"), calt, None), ("go", *xy(27.70, -97.10), calt, None), ("go", *xy(27.60, -97.18), calt, None),
                    ("go", *P("padre"), calt, None)]
        elif kind == "hoist":
            c = xy(27.74 + r.normal(0, 0.02), -97.27 + r.normal(0, 0.03))
            legs = [("go", c[0], c[1], 120, None)] + [("hover", c[0] + r.normal(0, 400), c[1] + r.normal(0, 400), 25, int(r.uniform(180, 420))) for _ in range(int(r.integers(2, 5)))]
        else:
            legs = [("go", *P("bay_mid"), calt, None), ("go", *P("ingleside"), calt, None), ("go", *P("north_beach"), calt, None)]
        S.helo(call, t0, legs, purpose="routine " + str(kind), squawk="vfr")

    def hc144(call, t0, kind, r):
        a = S.ac(call)
        vc = a["cruise_speed_kt"] * KT
        base = S.loc[a["aircraft_id"]]
        if kind == "offshore":
            b = math.radians(r.uniform(95, 150))
            d = r.uniform(110, 190) * 1000
            p1 = (crp[0] + d * math.sin(b), crp[1] + d * math.cos(b))
            p2 = (p1[0] + r.normal(0, 30000), p1[1] - abs(r.normal(40000, 10000)))
            via = [(p1[0], p1[1], 900, vc, "e"), (p2[0], p2[1], 600, vc * 0.85, "e"), (P("padre")[0] + 20000, P("padre")[1], 600, vc, "e")]
        elif kind == "bays":                                   # sheen mapping over Nueces and Corpus Christi bays
            pts = lawnmower(xy(27.86, -97.50)[0], xy(27.72, -97.5)[1], xy(27.86, -97.17)[0], xy(27.875, -97.5)[1], 7)
            via = [(x, y, 450, vc * 0.75, "l") for x, y in pts]
        else:                                                  # entrance channel and anchorage patrol
            via = [(P("jetties")[0], P("jetties")[1], 450, vc * 0.8, "l"), (P("sea_buoy")[0], P("sea_buoy")[1], 450, vc * 0.8, "l"),
                   ("ORB", P("anchorage")[0], P("anchorage")[1], 9000, 1.5, 450, vc * 0.8, "l"), (P("port_aransas")[0], P("port_aransas")[1] - 6000, 450, vc * 0.8, "l")]
        S.fw(call, t0, base, base, via=via, cruise=900, purpose="Coast Guard " + kind, squawk="ifr")

    def sar_sortie(call, t0, area_ids, n_hoists, r, drop=None, base=None, first_point=None, slow=False, hover_s=(210, 420)):
        """Rescue sortie from NAS Corpus Christi: hover at hoist points in the named neighbourhoods,
        optionally deliver to a hospital pad, return."""
        a = S.ac(call)
        legs = []
        pts = []
        for i in range(n_hoists):
            aid = area_ids[i % len(area_ids)] if i >= len(area_ids) or r.random() < 0.8 else str(r.choice(area_ids))
            pts += bbox_pts(aid, r, 1)
        if first_point:
            pts = [first_point] + pts[1:]
        # visit in a sensible order: nearest neighbour from the base
        cur = base or S.here_xy(a)
        order = []
        rest = list(pts)
        while rest:
            j = min(range(len(rest)), key=lambda q: math.hypot(rest[q][0] - cur[0], rest[q][1] - cur[1]))
            cur = rest.pop(j)
            order.append(cur)
        v = 21.0 if slow else None
        for i, (x, y) in enumerate(order):
            if i == 0 and slow:                                # battering into the wind along the shore
                legs.append(("go", x - 900, y + 1500, 60, 18.0))
            legs.append(("hover", x, y, float(r.uniform(18, 32)), int(r.uniform(*hover_s))))
        if drop:
            legs.append(("pad", PADS[drop][0], PADS[drop][1], int(r.uniform(240, 480))))
        return S.helo(call, t0, legs, purpose="rescue sortie", squawk="sar")

    plan_base = {}
    for q in HELICOPTER_SORTIES:
        plan_base.setdefault(q["callsign"], xy(q["base"]["lat"], q["base"]["lon"]))

    def plan_sortie(q):
        """One helicopter sortie from the shared rescue plan, flown stop by stop on the plan's clock: hover over each hoist,
        a skid-height hover at each street pick-up, wheels down at drop-off pads and ramps, parked at base between sorties."""
        a = S.ac(q["callsign"])
        perf = S.perf(a)
        vc = perf["vc"]
        r = rng("adsb-sarplan", q["sortie_id"])
        bx, by = xy(q["base"]["lat"], q["base"]["lon"])
        t0 = ts(q["takeoff_utc"])
        calt = float(r.uniform(*perf["alt"]))
        trk = Trk(t0 - 100 - int(r.integers(0, 80)), bx, by)
        trk.wait(t0 - trk.t, tag="p")

        def warp(i0, t_arr):
            tA, tB = trk.k[i0 - 1][0], trk.k[-1][0]
            if tB - tA < 1.0 or t_arr - tA < 1.0:
                return
            f = (t_arr - tA) / (tB - tA)
            for j in range(i0, len(trk.k)):
                kk = trk.k[j]
                trk.k[j] = (tA + (kk[0] - tA) * f,) + kk[1:]

        stops = q["stops"]
        on_ground = True
        for n_st, st in enumerate(stops):
            x, y = xy(st["lat"], st["lon"])
            ta, td = ts(st["arrive_utc"]), ts(st["depart_utc"])
            i0 = len(trk.k)
            if on_ground:
                px, py = trk.p
                helo_lift(trk, calt, vc, hdg(x - px, y - py) if math.hypot(x - px, y - py) > 5 else float(r.uniform(0, 360)), perf)
                on_ground = False
            kind = st["kind"]
            if kind == "search":
                alt = float(r.uniform(90, 150))
                rad, v = float(r.uniform(350, 600)), float(r.uniform(22, 30))
                a0 = math.atan2(trk.p[0] - x, trk.p[1] - y)
                helo_goto(trk, x + rad * math.sin(a0), y + rad * math.cos(a0), alt, vc * 0.8, perf, cruise=calt)
                warp(i0, ta)
                i1 = len(trk.k)
                turns = max(0.5, (td - ta) * v / (2 * math.pi * rad))
                steps = max(8, int(12 * turns))
                for i in range(1, steps + 1):
                    ang = a0 + 2 * math.pi * turns * i / steps
                    trk.go(x + rad * math.sin(ang), y + rad * math.cos(ang), alt, v, "t")
                warp(i1, td)
            elif kind == "pickup":
                hoist = st.get("method") == "HOIST"
                alt = float(r.uniform(13.0, 24.0)) if hoist else float(r.uniform(4.0, 6.0))       # 40-80 ft hoist hover; skids just clear of the street
                helo_goto(trk, x, y, alt, vc, perf, stop=True, cruise=calt)
                warp(i0, ta)
                if td - ta >= 20:
                    trk.hover(td - ta, r, drift=5.0 if hoist else 1.2, alt=alt)
                else:
                    trk.wait(max(1, td - ta), tag="h", gnd=False)
            else:                                          # dropoff at a ramp position or helipad, or the landing back at base
                helo_land(trk, x, y, perf, v=vc * 0.8, cruise=calt)
                warp(i0, ta)
                on_ground = True
                if n_st < len(stops) - 1:
                    trk.wait(max(20, td - ta), tag="p")
        if not on_ground:
            i0 = len(trk.k)
            helo_land(trk, bx, by, perf, v=vc * 0.8, cruise=calt)
            warp(i0, ts(q["landing_utc"]))
        trk.wait(15, tag="p")
        return S.emit(a, trk, "1277", "rescue sortie " + q["sortie_id"], dest_loc=q["base"]["airfield_id"] or "pad", spot=(bx, by))

    def storm_ops():
        """D-3 to D+6: everything canon says about who flew when."""
        r = rng("adsb-storm")
        # --- D-3: Coast Guard pre-positions two Jayhawks at the air station; the rest leave the coast
        t = local_ts(-3, "15:40")
        for i, c in enumerate(["C6033", "C6041"]):
            spot = plan_base.get(c) or S.transient("NGP")
            S.helo(c, t + i * 420, [("go", *P("bay_mid"), 300, None), ("go", ngp[0] + 2500, ngp[1] + 2500, 200, None)], end=spot,
                   end_loc="NGP", purpose="reposition to NAS Corpus Christi ahead of the storm")
        S.helo("C6017", local_ts(-3, "13:10"), [("go", *P("portland"), 450, None)], exit_to="EFD", purpose="hurricane evacuation")
        S.helo("C6028", local_ts(-3, "13:25"), [("go", *P("portland"), 450, None)], exit_to="EFD", purpose="hurricane evacuation")
        S.fw("C2306", local_ts(-3, "14:05"), "CRP", ("far", "EFD"), purpose="hurricane evacuation")
        S.fw("C2311", local_ts(-3, "14:30"), "CRP", ("far", "SKF"), purpose="hurricane evacuation")
        S.fw("CAMCC-04", local_ts(-3, "11:20"), "NGP", ("far", "SKF"), purpose="hurricane evacuation")
        S.fw("CAMCC-21", local_ts(-3, "12:05"), "NGP", ("far", "SKF"), purpose="hurricane evacuation")
        S.helo("CAMCC-11", local_ts(-3, "12:40"), [("go", *P("calallen"), 400, None)], exit_to="SAT", purpose="hurricane evacuation")
        S.helo("DPS110", local_ts(-3, "13:50"), [("go", *P("calallen"), 400, None)], exit_to="SAT", purpose="hurricane evacuation")
        S.fw("DPS201", local_ts(-3, "10:15"), "CRP", ("far", "AUS"), purpose="hurricane evacuation")
        S.helo("AIRMED1", local_ts(-3, "16:20"), [("go", *P("robstown"), 400, None)], exit_to="SAT", purpose="hurricane evacuation")
        S.helo("AIRMED2", local_ts(-3, "16:45"), [("go", *P("calallen"), 400, None)], exit_to="SAT", purpose="hurricane evacuation")
        S.helo("SKY6", local_ts(-3, "17:30"), [("go", *P("downtown"), 350, None), ("go", *P("calallen"), 400, None)], exit_to="SAT", purpose="hurricane evacuation")
        for i, c in enumerate(["CAP4216", "CBAS208", "EAGLE424", "N7312K", "N200KC"]):
            S.fw(c, local_ts(-3, "09:30") + i * 2400, "CRP", ("far", ["SAT", "AUS", "SAT", "AUS", "DFW"][i]), purpose="hurricane evacuation")
        S.fw("N922SR", local_ts(-3, "10:10"), "RKP", ("far", "AUS"), purpose="hurricane evacuation")
        S.fw("N58PA", local_ts(-3, "11:00"), "RAS", ("far", "SAT"), purpose="hurricane evacuation")
        S.fw("N8841Q", local_ts(-3, "12:20"), "RAS", ("far", "SAT"), purpose="hurricane evacuation")
        S.fw("N36BN", local_ts(-3, "09:50"), "TFP", ("far", "VCT"), purpose="hurricane evacuation")
        S.helo("CCAD31", local_ts(-4, "09:30"), [("go", ngp[0] - 3000, ngp[1] - 4000, 200, None)], purpose="pre-storm hangar reposition check")

        # --- D0 and D+1: the rescue sorties are the ones in the shared plan (sar_plan.SORTIES), flown stop by stop on its clock.
        # The state and CBP helicopters come back from San Antonio late on D0 to the positions their sorties start from.
        S.helo("DPS110", ts("2027-09-14T21:10Z"), [("go", *P("calallen"), 350, None), ("go", *P("molina"), 250, None)], enter_from="SAT",
               end=plan_base.get("DPS110") or PADS["DPS"], end_loc="pad", purpose="return for rescue operations", squawk="sar")
        S.helo("CAMCC-11", ts("2027-09-14T21:40Z"), [("go", *P("calallen"), 350, None), ("go", ngp[0] + 2000, ngp[1] + 2500, 200, None)], enter_from="SAT",
               end=plan_base.get("CAMCC-11") or S.transient("NGP"), end_loc="NGP", purpose="return for rescue operations", squawk="sar")
        for sortie in sorted(HELICOPTER_SORTIES, key=lambda q: q["takeoff_utc"]):
            plan_sortie(sortie)
        # --- D+1: three National Guard Black Hawks from Austin sweep the districts (EVT-1103); SUB-02 in view 17:44Z
        sweeps = {
            "GUNSMOKE01": (ts("2027-09-15T15:10Z"), ["calallen", "viola", "sub01", "hillcrest", "downtown", "north_beach", "causeway", "portland", "ingleside", "bay_mid"]),
            "GUNSMOKE02": (ts("2027-09-15T16:20Z"), ["robstown", "molina", "sub03", "sub01", "sub02", "inner_harbor", "north_beach", "downtown", "hillcrest", "sub04", "sub05", "flour_bluff"]),
            "GUNSMOKE03": (ts("2027-09-15T16:50Z"), ["calallen", "robstown", "molina", "sub04", "sub05", "flour_bluff", "padre", "port_aransas", "bay_mid"]),
        }
        aus = F.pt("AUS")
        for call, (t_dep, names) in sweeps.items():
            a = S.ac(call)
            vc = a["cruise_speed_kt"] * KT
            first = P(names[0])
            D = math.hypot(aus[0] - first[0], aus[1] - first[1])
            t_first = t_dep + D / vc                               # time over the first waypoint
            startp, _, _ = far_point(F, "AUS", first, dist_nm=95.0)
            d_in = math.hypot(startp[0] - first[0], startp[1] - first[1])
            trk = Trk(t_first - d_in / vc, startp[0], startp[1], 900.0, False, "e")
            trk.v = vc
            perf = S.perf(a)
            trk.go(first[0], first[1], 300.0, vc * 0.7, "l", rod=perf["rod"])
            tgt_end = t_dep + 124 * 60                             # 3 x 2 h 04 min = 6.2 flight hours
            pts = [P(nm) for nm in names[1:]]
            if call == "GUNSMOKE02":                               # be over Harbor View substation at 17:44Z
                i2 = names.index("sub02") - 1
                t_sub = ts("2027-09-15T17:44Z")
                dist_to = sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip([first] + pts[:i2], pts[:i2 + 1]))
                vs = dist_to / (t_sub - trk.t)
                for p in pts[:i2 + 1]:
                    trk.go(p[0], p[1], 240.0, vs, "l")
                    trk.v = vs
                pts = pts[i2 + 1:]
            spot = S.transient("NGP")
            remain = sum(math.hypot(b[0] - a_[0], b[1] - a_[1]) for a_, b in zip([trk.p] + pts, pts + [spot]))
            vs = max(14.0, min(vc, remain / max(60.0, (tgt_end - 90 - trk.t))))
            for p in pts:
                trk.go(p[0], p[1], 240.0, vs, "l")
                trk.v = vs
            helo_land(trk, spot[0], spot[1], perf, v=vs)
            trk.wait(15, tag="p")
            S.emit(a, trk, "1277", "reconnaissance sweep from Austin-Bergstrom", dest_loc="NGP", spot=spot)
        # --- D+1: Coast Guard fixed-wing back; coastal damage flight
        S.fw("C2306", ts("2027-09-15T13:30Z"), ("far", "EFD"), "CRP", via=[(P("rockport")[0], P("rockport")[1], 600, None, "l"), (P("port_aransas")[0], P("port_aransas")[1], 450, None, "l"),
             (P("padre")[0], P("padre")[1], 450, None, "l")], purpose="coastal damage survey on return")
        S.fw("FEMA01", ts("2027-09-15T20:40Z"), ("far", "SAT"), "CRP", purpose="FEMA team arrival")
        S.fw("DPS201", ts("2027-09-15T14:20Z"), ("far", "AUS"), "CRP", via=[("ORB", P("downtown")[0], P("downtown")[1], 9000, 1.2, 1500, None, "l")], purpose="state damage overview")
        # --- D+2: remaining Coast Guard aircraft return
        S.helo("C6017", ts("2027-09-16T10:50Z"), [("go", *P("portland"), 300, None), ("go", crp[0] + 1500, crp[1] + 1500, 200, None)], enter_from="EFD", end_loc="CRP", purpose="return to air station")
        S.helo("C6028", ts("2027-09-16T11:10Z"), [("go", *P("portland"), 300, None), ("go", crp[0] + 1500, crp[1] + 1500, 200, None)], enter_from="EFD", end_loc="CRP", purpose="return to air station")
        S.fw("C2311", ts("2027-09-16T14:10Z"), ("far", "SKF"), "CRP", purpose="return to air station")
        S.fw("CAMCC-21", ts("2027-09-16T15:00Z"), ("far", "SKF"), "NGP", purpose="return")
        S.fw("CAMCC-04", ts("2027-09-17T16:10Z"), ("far", "SKF"), "NGP", purpose="return")
        S.fw("CAP4216", ts("2027-09-16T13:40Z"), ("far", "AUS"), "CRP", purpose="return for damage photography")
        S.helo("SKY6", ts("2027-09-16T13:05Z"), [("go", *P("calallen"), 350, None), ("orbit", *P("north_beach"), 1200, 2, 300, 30.0), ("go", *P("downtown"), 300, None),
               ("go", crp[0] + 1200, crp[1] + 1000, 200, None)], enter_from="SAT", end_loc="CRP", purpose="return; oil on North Beach")
        S.helo("AIRMED1", ts("2027-09-16T15:30Z"), [("go", *P("robstown"), 350, None), ("go", PADS["AIRMED"][0] + 800, PADS["AIRMED"][1] + 800, 150, None)], enter_from="SAT", purpose="return to base")
        S.helo("AIRMED2", ts("2027-09-16T16:05Z"), [("go", *P("calallen"), 350, None), ("go", PADS["SCMH"][0] + 800, PADS["SCMH"][1] + 800, 150, None)], enter_from="SAT", purpose="return to base")
        # --- D+2 to D+5: no helicopter rescues are logged after D+1 (boats and trucks do the rest); the Jayhawks fly shoreline
        # and neighbourhood searches and inter-hospital transfers, the state and CBP helicopters damage reconnaissance
        for day in range(2, 6):
            n_cg = {2: 2, 3: 2, 4: 1, 5: 1}[day]
            for call in ("C6033", "C6041"):
                t = local_ts(day, "07:10") + (0 if call == "C6033" else 1500) + int(rng("adsb-sar-late", call, day).integers(0, 1500))
                for i in range(n_cg):
                    rr2 = rng("adsb-sar-late", call, day, i)
                    if rr2.random() < 0.35:
                        frm, to = [str(x) for x in rr2.choice(["BCMC", "SRMC", "SCMH", "GCCH"], size=2, replace=False)]
                        te = S.helo(call, t, [("pad", PADS[frm][0], PADS[frm][1], int(rr2.uniform(420, 900))), ("pad", PADS[to][0], PADS[to][1], int(rr2.uniform(300, 700)))],
                                    purpose="inter-hospital patient transfer", squawk="sar")
                    else:
                        names = [str(x) for x in rr2.choice(["flour_bluff", "padre", "port_aransas", "north_beach", "portland", "ingleside", "aransas_pass", "calallen"], size=3, replace=False)]
                        legs = []
                        for n_ in names:
                            legs.append(("go", *P(n_), float(rr2.uniform(120, 220)), None))
                            if rr2.random() < 0.6:
                                legs.append(("orbit", *P(n_), float(rr2.uniform(500, 1100)), float(rr2.uniform(1.0, 2.5)), float(rr2.uniform(90, 160)), 28.0))
                        te = S.helo(call, t, legs, purpose="search patrol, no survivors recovered", squawk="sar")
                    t = te + int(rr2.uniform(80, 170) * 60)
            for call in ("DPS110", "CAMCC-11"):
                rr2 = rng("adsb-sar-late", call, day, 0)
                t = local_ts(day, "08:20") + (900 if call == "DPS110" else 2700) + int(rr2.integers(0, 2400))
                names = [str(x) for x in rr2.choice(["calallen", "robstown", "molina", "hillcrest", "north_beach", "flour_bluff", "padre", "portland"], size=3, replace=False)]
                S.helo(call, t, [("go", *P(n_), float(rr2.uniform(150, 300)), None) for n_ in names], purpose="damage reconnaissance", squawk="sar")
            if day <= 4:
                for call in ("GUNSMOKE01", "GUNSMOKE02", "GUNSMOKE03"):
                    rr2 = rng("adsb-guard", call, day)
                    for i in range(2):
                        t = local_ts(day, "08:00" if i == 0 else "13:30") + int(rr2.uniform(0, 3000))
                        names = [str(x) for x in rr2.choice(["port_aransas", "rockport", "aransas_pass", "calallen", "robstown", "portland", "padre", "ingleside"], size=3, replace=False)]
                        S.helo(call, t, [("go", *P(n_), 300, None) for n_ in names], purpose="relief and reconnaissance support", squawk="sar")
        for i, call in enumerate(("GUNSMOKE01", "GUNSMOKE02", "GUNSMOKE03")):
            S.helo(call, local_ts(5, "09:20") + i * 600, [("go", *P("calallen"), 400, None)], exit_to="AUS", purpose="return to Austin-Bergstrom")
        # DPS and CBP helicopters go back to their own pads / ramp on D+6
        S.helo("DPS110", local_ts(6, "08:30"), [("go", *P("molina"), 250, None)], end=PADS["DPS"], end_loc="pad", purpose="return to base")
        S.helo("CAMCC-11", local_ts(6, "09:10"), [("go", *P("flour_bluff"), 200, None)], end=F.park_xy(S.ac("CAMCC-11")["parking_position_id"]), end_loc="NGP", purpose="reposition to home ramp")
        for i, c in enumerate(["C6033", "C6041"]):
            S.helo(c, local_ts(6, "10:00") + i * 500, [("go", *P("bay_mid"), 300, None), ("go", crp[0] + 1500, crp[1] + 1500, 200, None)],
                   end=F.park_xy(S.ac(c)["parking_position_id"]), end_loc="CRP", purpose="return to Coast Guard air station")
        # --- D+4: sheen mapping flight at about 16:00Z (EVT-2006)
        hc144("C2306", ts("2027-09-18T15:38Z"), "bays", rng("adsb-hc144-d4"))

    # ---------------------------------------------------------------- NOAA42 on landfall morning (EVT-1102)
    def noaa42():
        a = S.ac("NOAA42")
        vc = a["cruise_speed_kt"] * KT
        t_cross = ts("2027-09-14T08:30Z")
        p_cross = xy(27.812, -97.33)                              # over the bay reach of the ship channel
        b_in = 300.0                                              # heading while crossing (from the southeast)
        ux, uy = unit(b_in)
        d_in = 150 * NM
        start = (p_cross[0] - ux * d_in, p_cross[1] - uy * d_in)
        trk = Trk(t_cross - d_in / vc, start[0], start[1], 3000.0, False, "e")
        trk.v = vc
        trk.go(p_cross[0] - ux * 30000, p_cross[1] - uy * 30000, 3000.0, vc, "e")
        trk.go(p_cross[0], p_cross[1], 3000.0, vc, "t")
        trk.go(p_cross[0] + ux * 45000, p_cross[1] + uy * 45000, 3000.0, vc, "t")       # on toward the centre, inland
        nx, ny = unit(40.0)
        trk.go(trk.p[0] + nx * 60000, trk.p[1] + ny * 60000, 3000.0, vc, "e")
        ex, ey = unit(95.0)
        trk.go(trk.p[0] + ex * 330000, trk.p[1] + ey * 330000, 3000.0, vc, "e")
        S.emit(a, trk, S.squawk(a, "ifr", 42), "hurricane reconnaissance and radar pass", dest_loc="away")

    # ---------------------------------------------------------------- relief airlift D+34 to D+43 (EVT-0405)
    def relief():
        r = rng("adsb-relief")
        c17_per_day = [3, 3, 3, 2, 3, 3, 2, 3, 2, 2]              # 26
        civ_per_day = [2, 1, 2, 1, 2, 1, 1, 2, 1, 1]              # 14
        c17 = ["SYN41", "SYN42", "SYN43", "SYN44", "SYN45"]
        civ = ["GCX301", "GCX302", "BZA303"]
        ci = vi = 0
        for k, day in enumerate(range(34, 44)):
            times = sorted(r.uniform(6.5, 19.0, size=c17_per_day[k]))
            for j, hh in enumerate(times):
                call = c17[ci % 5]
                ci += 1
                home = S.ac(call)["home_base"]
                t_in = local_ts(day, "00:00") + int((hh + j * 0.9) * 3600)
                t_land = S.fw(call, t_in, ("far", home), "NGP", purpose="relief airlift arrival")
                S.fw(call, t_land + int(r.uniform(2.2, 3.6) * 3600), "NGP", ("far", home), purpose="relief airlift departure")
            times = sorted(r.uniform(7.0, 18.0, size=civ_per_day[k]))
            for j, hh in enumerate(times):
                call = civ[vi % 3]
                vi += 1
                home = S.ac(call)["home_base"]
                t_in = local_ts(day, "00:00") + int((hh + j * 1.3) * 3600)
                t_land = S.fw(call, t_in, ("far", home), "NGP", purpose="relief charter arrival")
                S.fw(call, t_land + int(r.uniform(1.6, 2.8) * 3600), "NGP", ("far", home), purpose="relief charter departure")

    # ---------------------------------------------------------------- everything else, day by day
    STORY = {2: "north_beach", 3: "harbor_bridge", 4: "nueces_bay", 5: "flour_bluff", 6: "nas", 7: "calallen", 8: "port_aransas", 9: "hillcrest",
             10: "inner_harbor", 12: "molina", 13: "hillcrest", 14: "calallen", 20: "nueces_bay", 30: "inner_harbor", 33: "inner_harbor",
             34: "nas", 39: "nas", 44: "jetties", 45: "jetties", 46: "jetties", 52: "jetties", 58: "inner_harbor", 59: "inner_harbor",
             60: "downtown", 61: "inner_harbor", 64: "inner_harbor"}

    def misc_day(day):
        r = rng("adsb-misc", day)
        wd = weekday(day)
        pre = day <= -4
        post = day >= 7
        closed = -3 <= day <= 6
        # Coast Guard routine
        if pre or post:
            for call in CGH:
                if r.random() < 0.34:
                    t0 = local_ts(day, "08:00") + int(r.uniform(0, 12) * 3600)
                    if r.random() < 0.12:
                        t0 = local_ts(day, "20:30") + int(r.uniform(0, 3600))
                    if S.free(S.ac(call), t0):
                        cg_helo_routine(call, t0, r)
            closure = 44 <= day <= 58
            for call in ("C2306", "C2311"):
                p = 0.42 if not closure else 0.75
                if r.random() < p:
                    t0 = local_ts(day, "07:30") + int(r.uniform(0, 9) * 3600)
                    kind = "channel" if closure else ("bays" if (7 <= day <= 20 and r.random() < 0.6) else "offshore")
                    if S.free(S.ac(call), t0):
                        hc144(call, t0, kind, r)
        if 2 <= day <= 6:
            for call in ("C2306", "C2311"):
                if day == 4 and call == "C2306":
                    continue
                if day >= 3 and r.random() < 0.7 and S.loc[S.ac(call)["aircraft_id"]] != "away":
                    hc144(call, local_ts(day, "09:00") + int(r.uniform(0, 5) * 3600) + (0 if call == "C2306" else 7000), "bays" if r.random() < 0.7 else "offshore", r)
        # CBP unmanned night patrol: every second night, always south of Ingleside (see drone detections)
        doy = (local_dt(local_ts(day, "12:00")).timetuple().tm_yday)
        if (pre or day >= 5) and doy % 2 == 0 and S.loc[S.ac("CAMCC-04")["aircraft_id"]] != "away":
            t0 = local_ts(day - 1, "20:40") + int(r.uniform(0, 1500))
            if t0 + 9 * 3600 < T_TFR or day > 0:
                a = S.ac("CAMCC-04")
                vc = a["cruise_speed_kt"] * KT
                circ = [xy(27.62, -97.10), xy(27.70, -96.90), xy(27.76, -97.05), xy(27.70, -97.28)]
                via = []
                laps = int(r.integers(22, 29))
                off = int(r.integers(0, 4))
                for i in range(laps * 4):
                    c = circ[(i + off) % 4]
                    via.append((c[0] + r.normal(0, 600), c[1] + r.normal(0, 600), 5800, vc, "e"))
                S.fw("CAMCC-04", t0, "NGP", "NGP", via=via, cruise=5800, purpose="maritime night patrol")
        if (pre or post) and wd in (0, 2, 4) and r.random() < 0.8:
            t0 = local_ts(day, "09:30") + int(r.uniform(0, 4) * 3600)
            legs = [("go", *P(str(n_)), 250, None) for n_ in r.choice(["port_aransas", "padre", "bay_mid", "ingleside", "jetties", "inner_harbor"], size=3, replace=False)]
            S.helo("CAMCC-11", t0, legs, purpose="law-enforcement patrol")
        if (pre or post) and ((wd in (1, 3) and r.random() < 0.7) or (44 <= day <= 58 and r.random() < 0.8)):
            a = S.ac("CAMCC-21")
            vc = a["cruise_speed_kt"] * KT
            if S.loc[a["aircraft_id"]] != "away":
                if 44 <= day <= 58:
                    via = [(P("sea_buoy")[0], P("sea_buoy")[1], 900, vc * 0.8, "l"), ("ORB", P("anchorage")[0] + 8000, P("anchorage")[1], 16000, 2.0, 900, vc * 0.8, "l")]
                else:
                    b = math.radians(r.uniform(100, 160))
                    d = r.uniform(120, 220) * 1000
                    via = [(ngp[0] + d * math.sin(b), ngp[1] + d * math.cos(b), 1500, vc, "e"), (ngp[0] + d * math.sin(b) - 60000, ngp[1] + d * math.cos(b) - 50000, 1200, vc, "e")]
                S.fw("CAMCC-21", local_ts(day, "10:10") + int(r.uniform(0, 3) * 3600), "NGP", "NGP", via=via, cruise=1500, purpose="maritime patrol")
        # state police helicopter and transport
        if (pre or post) and r.random() < 0.38:
            legs = [("go", *P(str(n_)), 250, None) for n_ in r.choice(["downtown", "molina", "calallen", "flour_bluff", "robstown", "hillcrest", "padre"], size=3, replace=False)]
            S.helo("DPS110", local_ts(day, "10:00") + int(r.uniform(0, 9) * 3600), legs, start=PADS["DPS"], end=PADS["DPS"], purpose="police patrol")
        if (pre or post) and r.random() < 0.18:
            t0 = local_ts(day, "08:00") + int(r.uniform(0, 3) * 3600)
            S.fw("DPS201", t0, "CRP", ("far", "AUS"), purpose="state transport")
            S.fw("DPS201", t0 + int(r.uniform(5, 8) * 3600), ("far", "AUS"), "CRP", purpose="state transport return")
        if 2 <= day <= 6 and S.loc[S.ac("DPS201")["aircraft_id"]] == "CRP":
            S.fw("DPS201", local_ts(day, "08:10") + int(r.uniform(0, 1800)), "CRP", "CRP", via=[("ORB", P(str(r.choice(["calallen", "port_aransas", "flour_bluff", "rockport"])))[0],
                 P("downtown")[1], 12000, 1.5, 1500, None, "l")], cruise=1500, purpose="damage overview")
        # air ambulance
        if pre or day >= 3:
            n = int(r.poisson(1.3 if not (3 <= day <= 20) else 2.4))
            for i in range(n):
                call = "AIRMED1" if r.random() < 0.55 else "AIRMED2"
                a = S.ac(call)
                t0 = local_ts(day, "00:00") + int(r.uniform(0, 24) * 3600)
                if not S.free(a, t0) or (t0 > T_TFR - 4 * 3600 and day < 0):
                    continue
                home = PADS["AIRMED"] if call == "AIRMED1" else PADS["SCMH"]
                src = str(r.choice(["ABCH", "SCMH", "BCMC", "scene", "scene", "RKP"]))
                dst = str(r.choice(["SRMC", "GCCH", "SRMC", "BCMC"]))
                legs = []
                if src == "scene":
                    pt = xy(27.75 + r.normal(0, 0.12), -97.55 + r.normal(0, 0.15))
                    legs.append(("go", pt[0], pt[1], 25, None))             # landing off-airport: lost below coverage
                    legs.append(("hover", pt[0], pt[1], 20, 60))
                elif src == "RKP":
                    legs.append(("go", *F.pt("RKP"), 300, None))
                elif PADS[src] != home:
                    legs.append(("pad", PADS[src][0], PADS[src][1], int(r.uniform(600, 1200))))
                if PADS[dst] != home:
                    legs.append(("pad", PADS[dst][0], PADS[dst][1], int(r.uniform(480, 900))))
                if legs:
                    S.helo(call, t0, legs, start=home, end=home, purpose="air ambulance", squawk="vfr")
        # news helicopter
        if S.loc[S.ac("SKY6")["aircraft_id"]] == "CRP":
            flights = []
            if pre and wd < 5:
                if r.random() < 0.55:
                    flights.append(("06:20", ["downtown", "harbor_bridge", "cc_bay_west"]))
                if r.random() < 0.5:
                    flights.append(("17:05", ["downtown", "molina", "flour_bluff"]))
            elif day >= 3:
                if day in STORY:
                    flights.append(("08:10" if day != 44 else "07:40", [STORY[day], "downtown"]))
                    if day <= 14 or day in (44, 46, 58):
                        flights.append(("16:20", [STORY[day]]))
                elif (day <= 20 and r.random() < 0.7) or (wd < 5 and r.random() < 0.4):
                    flights.append(("07:00", [str(x) for x in r.choice(["downtown", "harbor_bridge", "north_beach", "calallen", "flour_bluff", "inner_harbor"], size=2, replace=False)]))
            for hh, names in flights:
                legs = []
                for n_ in names:
                    legs.append(("orbit", *P(n_), 900, 2, 330, 28.0))
                S.helo("SKY6", local_ts(day, hh) + int(r.uniform(0, 1200)), legs, purpose="news gathering")
        # survey, pipeline patrol, Civil Air Patrol, FEMA
        if (pre and wd == 3) or (day >= 9 and wd == 3 and r.random() < 0.8):
            if S.loc[S.ac("CBAS208")["aircraft_id"]] == "CRP":
                c = P(str(r.choice(["nueces_bay", "padre", "calallen", "portland", "rockport"])))
                pts = lawnmower(c[0] - 7000, c[1] - 4000, c[0] + 7000, c[1] + 4000, 5)
                S.fw("CBAS208", local_ts(day, "09:15") + int(r.uniform(0, 3600)), "CRP", "CRP", via=[(x, y, 900, 62.0, "l") for x, y in pts], cruise=900, purpose="aerial survey", squawk="vfr")
        if (pre and wd == 1) or (day >= 9 and wd == 1):
            if S.loc[S.ac("EAGLE424")["aircraft_id"]] == "CRP":
                pts = [P("robstown"), P("calallen"), P("viola"), P("sub01"), P("portland"), P("ingleside"), P("aransas_pass")]
                S.fw("EAGLE424", local_ts(day, "08:30") + int(r.uniform(0, 3600)), "CRP", "CRP", via=[(x, y, 300, 55.0, "l") for x, y in pts], cruise=300, purpose="pipeline patrol", squawk="vfr")
        if 3 <= day <= 9 and S.loc[S.ac("CAP4216")["aircraft_id"]] == "CRP":
            c = P(str(r.choice(["flour_bluff", "north_beach", "port_aransas", "calallen", "padre", "portland"])))
            pts = lawnmower(c[0] - 4500, c[1] - 3000, c[0] + 4500, c[1] + 3000, 5)
            S.fw("CAP4216", local_ts(day, "09:00") + int(r.uniform(0, 5400)), "CRP", "CRP", via=[(x, y, 450, 52.0, "l") for x, y in pts], cruise=450, purpose="damage photography", squawk="vfr")
        if 2 <= day <= 6:
            c = P(str(r.choice(["rockport", "aransas_pass", "ingleside"])))
            t0 = local_ts(day, "10:30") + int(r.uniform(0, 3600))
            S.fw("CAP4227", t0, ("far", "VCT"), ("far", "VCT"), via=[("ORB", c[0], c[1], 5000, 3.0, 450, 52.0, "l")], cruise=900, purpose="damage photography", squawk="vfr")
        if S.loc[S.ac("FEMA01")["aircraft_id"]] == "CRP":
            if 2 <= day <= 4:
                c = P({2: "port_aransas", 3: "flour_bluff", 4: "calallen"}[day])
                pts = lawnmower(c[0] - 14000, c[1] - 6000, c[0] + 14000, c[1] + 6000, 4)
                S.fw("FEMA01", local_ts(day, "09:40"), "CRP", "CRP", via=[(x, y, 1500, 90.0, "l") for x, y in pts], cruise=1500, purpose="aerial assessment")
            elif day == 5 or (day > 5 and wd == 3):
                S.fw("FEMA01", local_ts(day, "15:30") + int(r.uniform(0, 2400)), "CRP", ("far", "SAT"), purpose="staff transport")
        elif day > 5 and day <= 75 and wd == 0 and S.loc[S.ac("FEMA01")["aircraft_id"]] == "away":
            S.fw("FEMA01", local_ts(day, "09:10") + int(r.uniform(0, 2400)), ("far", "SAT"), "CRP", purpose="staff transport")
        # depot test flights (halted D-4, hangars damaged, back to full production D+47)
        p_test = 0.35 if (day <= -5 or day >= 47) else (0.14 if day >= 25 else 0.0)
        if wd < 5 and day not in HOLIDAYS:
            for call in ("CCAD31", "CCAD44"):
                if r.random() < p_test:
                    hp = (ngp[0] + r.normal(0, 300), ngp[1] - 600 + r.normal(0, 300))
                    legs = [("hover", hp[0], hp[1], 15, int(r.uniform(240, 600))), ("go", ngp[0] - 6000 + r.normal(0, 1500), ngp[1] - 9000, 300, None),
                            ("go", ngp[0] + 5000, ngp[1] - 14000 + r.normal(0, 2000), 450, None), ("go", ngp[0] + 2500, ngp[1] - 3000, 200, None)]
                    S.helo(call, local_ts(day, "09:00") + int(r.uniform(0, 5) * 3600), legs, purpose="maintenance test flight")
        # general aviation
        if pre or day >= 11:
            ga_ok = lambda c: S.loc[S.ac(c)["aircraft_id"]] not in ("away",)
            if wd < 6 and ga_ok("N7312K") and day not in HOLIDAYS:
                for sl in ("09:00", "13:00", "16:00"):
                    if r.random() < 0.55:
                        t0 = local_ts(day, sl) + int(r.uniform(0, 5400))
                        if r.random() < 0.5:
                            via = [("LA", "CRP")] * int(r.integers(2, 6))
                        else:
                            c = xy(27.9 + r.normal(0, 0.05), -97.75 + r.normal(0, 0.06))
                            via = [(c[0], c[1], 1000, 50.0, "e"), (c[0] + 5000, c[1] - 4000, 1100, 45.0, "e"), (c[0] - 3000, c[1] - 6000, 900, 50.0, "e"), ("LA", "CRP")]
                        if t0 + 2 * 3600 < T_TFR or day > 0:
                            S.fw("N7312K", t0, "CRP", "CRP", via=via, cruise=1000, purpose="flight training", squawk="vfr")
            if wd >= 5 or r.random() < 0.12:
                for c, home, other in (("N58PA", "RAS", "RKP"), ("N8841Q", "RAS", "CRP"), ("N36BN", "TFP", "RAS")):
                    if (home == "RAS" and 0 <= day < 30) or not ga_ok(c):
                        continue
                    if r.random() < 0.45:
                        t0 = local_ts(day, "09:30") + int(r.uniform(0, 6) * 3600)
                        if t0 + 3 * 3600 < T_TFR or day > 0:
                            te = S.fw(c, t0, home, other, cruise=float(r.uniform(700, 1400)), purpose="personal flight", squawk="vfr")
                            S.fw(c, te + int(r.uniform(1, 3) * 3600), other, home, cruise=float(r.uniform(700, 1400)), purpose="personal flight", squawk="vfr")
            for c, home, p in (("N922SR", "RKP", 0.25), ("N200KC", "CRP", 0.3)):
                if wd < 5 and r.random() < p and ga_ok(c):
                    far = str(r.choice(["SAT", "HOU", "AUS", "DFW", "MFE"]))
                    t0 = local_ts(day, "07:30") + int(r.uniform(0, 3) * 3600)
                    if t0 + 12 * 3600 < T_TFR or day > 0:
                        S.fw(c, t0, home, ("far", far), purpose="business flight")
                        S.fw(c, t0 + int(r.uniform(6, 10) * 3600), ("far", far), home, purpose="business flight return")

    def returns_after_storm():
        """General aviation and survey aircraft come home once the airspace reopens."""
        back = [("CBAS208", 7, "SAT", "CRP"), ("EAGLE424", 8, "SAT", "CRP"), ("N7312K", 8, "AUS", "CRP"), ("N200KC", 7, "DFW", "CRP"),
                ("N922SR", 9, "AUS", "RKP"), ("N36BN", 10, "VCT", "TFP"), ("N58PA", 28, "SAT", "RAS"), ("N8841Q", 29, "SAT", "RAS")]
        for i, (c, day, far, home) in enumerate(back):
            S.fw(c, local_ts(day, "10:00") + i * 1100, ("far", far), home, purpose="return after the storm", squawk="vfr" if c.startswith("N") and c != "N200KC" else "ifr")

    def special_day(day):
        r = rng("adsb-specials", day)
        if day == 11:
            # D+11 thermal survey of the substation corridor (EVT-1106): 2 h 14 min at 2,000 ft AGL from 09:15Z
            t0 = ts("2027-09-25T09:15Z")
            order = ["sub05", "sub04", "sub03", "sub02", "sub01", "wtp", "sub01", "sub02", "sub03", "sub04", "sub05"]
            via = []
            for n_ in order:
                c = P(n_)
                for dx in (-2200, 2200):
                    via.append((c[0] + dx, c[1] + (700 if dx > 0 else -700), 610, None, "l"))
                for dx in (2200, -2200):
                    via.append((c[0] + dx, c[1] + (-700 if dx > 0 else 700), 610, None, "l"))
            dist = 0.0
            prev = crp
            for w in via:
                dist += math.hypot(w[0] - prev[0], w[1] - prev[1])
                prev = (w[0], w[1])
            dist += math.hypot(prev[0] - crp[0], prev[1] - crp[1])
            v = dist / (134 * 60 - 560)                            # airborne 2 h 14 min
            via = [(x, y, alt, v, tag) for (x, y, alt, _, tag) in via]
            S.fw("CBAS208", t0, "CRP", "CRP", via=via, cruise=610, purpose="thermal survey of substations", squawk="vfr")
        if day == 44:                                              # a Coast Guard helicopter goes to the jetties after the blast
            S.helo("C6017", ts("2027-10-28T06:31Z"), [("go", *P("port_aransas"), 200, None), ("orbit", *P("jetties"), 900, 4, 90, 25.0),
                   ("hover", P("jetties")[0] + 300, P("jetties")[1] + 100, 40, 420), ("orbit", *P("sea_buoy"), 1500, 1.5, 120, 30.0)],
                   purpose="response to incident at the jetties", squawk="sar")
        if day == 45:                                              # Navy mine-countermeasures helicopter detachment arrives
            S.helo("NAVYHK21", local_ts(45, "15:10"), [("go", *P("rockport"), 300, None), ("go", ngp[0] + 2500, ngp[1] + 2500, 200, None)], enter_from="MSY",
                   end=S.transient("NGP"), end_loc="NGP", purpose="detachment arrival")
        if 46 <= day <= 57:
            for hh in (["08:00", "13:20"] if r.random() < 0.6 else ["09:10"]):
                j = P("jetties")
                ax = unit(121.4)
                pts = []
                for i in range(int(r.integers(5, 9))):
                    off = (-900 + i * 300)
                    s0 = (j[0] + ax[0] * 1500 - ax[1] * off, j[1] + ax[1] * 1500 + ax[0] * off)
                    s1 = (j[0] + ax[0] * 9000 - ax[1] * off, j[1] + ax[1] * 9000 + ax[0] * off)
                    pts += [s0, s1] if i % 2 == 0 else [s1, s0]
                S.helo("NAVYHK21", local_ts(day, hh) + int(r.uniform(0, 1800)), [("go", *P("port_aransas"), 150, None), ("lines", pts, 45, 21.0)], purpose="channel search support")
        if day == 59:
            S.helo("NAVYHK21", local_ts(59, "09:30"), [("go", *P("rockport"), 300, None)], exit_to="MSY", purpose="detachment departure")
        if day == 57:                                              # an Army heavy-lift helicopter flies in to be loaded and does not fly out
            S.helo("RIDGELINE01", local_ts(57, "11:05"), [("go", *P("calallen"), 400, None), ("go", ngp[0] + 2500, ngp[1] + 2500, 200, None)], enter_from="GRK",
                   end=S.transient("NGP"), end_loc="NGP", purpose="self-deployment for sealift")
        if day == 58:
            S.helo("RIDGELINE01", local_ts(58, "14:20"), [("go", ngp[0] - 5000, ngp[1] - 6000, 250, None), ("go", ngp[0] + 4000, ngp[1] - 9000, 250, None)],
                   purpose="maintenance check flight before loading")

    # ---- run in time order where state matters
    for day in range(-30, -4):
        airline_day(day); navy_day(day); misc_day(day)
    navy_day(-4); airline_day(-4); misc_day(-4)
    airline_day(-3)
    storm_ops()
    noaa42()
    for day in range(2, 7):
        airline_day(day); navy_day(day); misc_day(day)
    returns_after_storm()
    for day in range(7, 120):
        if day == 34:
            relief()
        special_day(day)
        airline_day(day); navy_day(day); misc_day(day)


def main():
    global G
    G = geo_handle()
    sim = Sim()
    build(sim)
    retire(["05_other_sources/adsb/" + f for f in os.listdir(os.path.join(ROOT, "05_other_sources", "adsb"))
            if not f.startswith("adsb_20")] if os.path.isdir(os.path.join(ROOT, "05_other_sources", "adsb")) else [])
    total = 0
    for month in sorted(sim.rows):
        rows = sim.rows[month]
        rows.sort(key=lambda r: (r[3], r[0]))
        # one position per aircraft per second at most
        seen, out = set(), []
        for r in rows:
            k = (r[0], r[3])
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        n = write_csv(f"05_other_sources/adsb/adsb_{month}.csv", HEADER, out)
        total += n
        print(f"adsb_{month}.csv  {n:>8} rows")
    with open("/tmp/adsb_flight_log.tsv", "w") as fh:
        for l in sim.log:
            fh.write("\t".join(str(x) for x in l) + "\n")
    print(f"adsb total {total} rows, {len(sim.log)} flights")


if __name__ == "__main__":
    main()
