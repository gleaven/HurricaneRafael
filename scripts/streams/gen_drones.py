"""Small-unmanned-aircraft streams.

    python3 scripts/streams/gen_drones.py          (run after gen_aviation.py: it reads the ADS-B files)

Writes
  05_other_sources/drone_video/drone_telemetry_*.csv     authorised flights, one row per second (DJI SRT normalised)
  05_other_sources/drone_video/logs/flight_log.csv        one row per flight (airframe, sensor, tile sets, authorisation)
  05_other_sources/drone_video/logs/thermal_survey_readings.csv
  05_other_sources/drone_detections/sensor_sites.csv      the detection sensors and where they are
  05_other_sources/drone_detections/sensor_status_YYYY-MM.csv   hourly health rows
  05_other_sources/drone_detections/detections_YYYY-MM.csv      radar plots and RF contacts
  05_other_sources/drone_detections/laanc_authorizations.csv
  05_other_sources/drone_detections/sighting_reports.csv

Unauthorised aircraft never appear in the telemetry or the authorisations; they exist only as
what the sensors and witnesses would have recorded. See scripts/streams/README.md.
"""
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict


def _mmdd(day):
    """Calendar month-day of a scenario day, for mission names (no scenario-day numbers in data)."""
    import datetime as _dt
    return (_dt.date(2027, 9, 14) + _dt.timedelta(days=int(day))).strftime("%m%d")

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *            # noqa: F401,F403
from aviation_lib import xy, ll, hdg, unit, angdiff, KT, FT, NM

G = None
OPS = {o["operator_id"]: o for o in reg("drone_operators")["authorized_operators"]}
SITES = {s["site_id"]: s for s in reg("drone_operators")["launch_sites"]}
AREAS = {a["area_id"]: a for a in reg("areas")["areas"]}
INFRA = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"] if a.get("latitude") is not None}
AC = {(a.get("callsign_voice") or a["callsign"]): a for a in reg("aircraft_registry")["aircraft"]}
T_TFR = local_ts(-2, "00:01")

PT = {
    "sub01": (27.80951, -97.45564), "sub02": (27.8021, -97.45287), "sub03": (27.7706, -97.41624), "sub04": (27.74299, -97.42308),
    "sub05": (27.70022, -97.33461), "wtp": (27.86056, -97.62139), "depot": (27.69948, -97.27681), "nas": (27.69242, -97.27931),
    "harbor_bridge": (27.81097, -97.39678), "causeway": (27.85231, -97.35869), "jfk": (27.63508, -97.24076),
    "term01": (27.81447, -97.40133), "north_beach": (27.82976, -97.38457), "flour_bluff": (27.67054, -97.30216),
    "calallen": (27.86746, -97.62514), "downtown": (27.79501, -97.39805), "hillcrest": (27.80637, -97.41326),
    "molina": (27.7674, -97.4455), "port_aransas": (27.83392, -97.06111), "rockport": (28.02058, -97.05444),
    "portland": (27.87725, -97.32389), "ingleside": (27.87781, -97.21166), "aransas_pass": (27.90947, -97.15),
    "nueces_bay_shore": (27.8405, -97.4050), "portland_shore": (27.8700, -97.3170), "indian_point": (27.8520, -97.3530),
    "marina": (27.84593, -97.22564), "southside": (27.70169, -97.38393), "padre": (27.61492, -97.22138),
    "annaville": (27.83864, -97.58306), "tuloso": (27.82922, -97.57544), "oak_park": (27.79629, -97.43723),
}
PX = {k: xy(*v) for k, v in PT.items()}
INNER_HARBOR_BOX = (-97.53, 27.803, -97.393, 27.850)
JAMMER = xy(INFRA["TANK-0390"]["latitude"], INFRA["TANK-0390"]["longitude"])
JAM_WINDOWS = [(local_ts(d, "08:10") + (d * 437) % 1500, local_ts(d, "22:40") + (d * 911) % 1800) for d in range(38, 44)]   # same windows as the ADS-B stream

TEL_HEADER = ["flight_id", "frame_number", "timestamp_utc", "srt_time", "latitude", "longitude", "rel_alt_m", "abs_alt_m", "iso", "shutter",
              "fnum", "focal_len_mm", "ev", "color_temp_k", "gimbal_pitch_deg", "gimbal_yaw_deg", "gimbal_roll_deg", "course_deg",
              "operator_id", "drone_model", "mission_name", "video_filename"]
LOG_HEADER = ["flight_id", "operator_id", "airframe_id", "drone_model", "mission_name", "authorization_id", "launch_latitude", "launch_longitude",
              "takeoff_utc", "landing_utc", "duration_s", "track_km", "max_alt_m_agl", "sensor", "spectral_band", "ground_resolution_m",
              "tile_set_id", "tiles", "acquisition_start_utc", "acquisition_end_utc", "notes"]
MODEL_SPEC = {  # cruise m/s, climb m/s, fixed wing, sensor, focal mm, fnum
    "Argus Mk-7 fixed-wing survey aircraft": (28.0, 4.0, True, "42 MP nadir mapping camera", 35.0, 5.6),
    "Autel EVO II Pro": (9.0, 3.0, False, "1-inch 20 MP camera", 28.6, 2.8),
    "DJI Mavic 3 Enterprise": (10.0, 3.5, False, "4/3 CMOS 20 MP wide camera", 24.0, 2.8),
    "DJI Mini 4 Pro": (8.0, 3.0, False, "1/1.3-inch 48 MP camera", 24.0, 1.7),
    "DJI Mini 3 Pro": (8.0, 3.0, False, "1/1.3-inch 48 MP camera", 24.0, 1.7),
    "FLIR-equipped multirotor": (9.0, 3.0, False, "radiometric thermal imager 640x512", 13.0, 1.0),
    "DJI Matrice 30T": (11.0, 4.0, False, "wide + zoom + thermal payload", 24.0, 2.8),
    "Skydio X10": (11.0, 4.0, False, "VT300-L visual and thermal payload", 20.0, 2.2),
    "DJI Matrice 350 RTK": (12.0, 4.0, False, "P1 45 MP mapping camera", 35.0, 5.6),
    "WingtraOne Gen II": (16.0, 4.0, True, "RX1R II 42 MP mapping camera", 35.0, 5.6),
    "Skydio X2D": (9.0, 3.0, False, "12 MP colour and thermal camera", 20.0, 2.4),
    "DJI Phantom 4 Multispectral": (8.0, 3.0, False, "6-band multispectral array", 5.7, 2.2),
    "DJI Mavic 3 Thermal": (10.0, 3.5, False, "48 MP wide and 640x512 thermal", 24.0, 2.8),
}


def P(n):
    return PX[n]


def field_launch(target_xy, r, dist=(250, 700)):
    """A point on land near a target where a crew would park and launch: a roadside spot if there is
    a road close by, otherwise dry ground; never water."""
    spare = None
    for k in range(60):
        ang = r.uniform(0, 2 * math.pi)
        d = r.uniform(*dist) * (1.0 + k / 20.0)                  # widen the search if nothing is found nearby
        la, lo = ll(target_xy[0] + d * math.sin(ang), target_xy[1] + d * math.cos(ang))
        dd, sla, slo, name, cls = G.roads.nearest(la, lo)
        if dd < 400 and G.is_land(sla, slo) and G.shore_distance_m(sla, slo) >= 25:
            return xy(sla, slo)
        if spare is None and G.is_land(la, lo) and G.shore_distance_m(la, lo) >= 40:
            spare = xy(la, lo)
    if spare:
        return spare
    la, lo = ll(*target_xy)
    dd, sla, slo, name, cls = G.roads.nearest(la, lo)
    return xy(sla, slo)


def lawn(cx, cy, w, h, spacing, vertical=False):
    n = max(2, int(round((h if not vertical else w) / spacing)) + 1)
    pts = []
    for i in range(n):
        f = i / (n - 1)
        if vertical:
            x = cx - w / 2 + w * f
            pts += [(x, cy - h / 2), (x, cy + h / 2)] if i % 2 == 0 else [(x, cy + h / 2), (x, cy - h / 2)]
        else:
            y = cy - h / 2 + h * f
            pts += [(cx - w / 2, y), (cx + w / 2, y)] if i % 2 == 0 else [(cx + w / 2, y), (cx - w / 2, y)]
    return pts


def orbit(cx, cy, rad, turns=1.0, n=24, start=0.0):
    return [(cx + rad * math.sin(start + 2 * math.pi * turns * i / n), cy + rad * math.cos(start + 2 * math.pi * turns * i / n)) for i in range(n + 1)]


def path_xy(pts, v, t_total=None):
    """Positions every second along a polyline at speed v (m/s). Returns x, y arrays."""
    pts = np.asarray(pts, float)
    seg = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = s[-1]
    n = max(2, int(total / v) + 1)
    d = np.minimum(np.arange(n) * v, total)
    x = np.interp(d, s, pts[:, 0]); y = np.interp(d, s, pts[:, 1])
    return x, y, total


class Flights:
    def __init__(self):
        self.tel = defaultdict(list)       # file key -> list of row strings
        self.log = []
        self.auth = []
        self.tracks = []                   # (flight dict, t array, x, y, alt) for the detection sensors
        self.seq = defaultdict(int)
        self.auth_n = 0
        self.vid = defaultdict(lambda: 100)

    def add(self, op_id, airframe_i, mission, t0, launch, pts, alt, purpose="survey", gimbal=-90.0, speed=None, hold=None, sensor=None,
            band="visible", gsd=None, tile_set=None, tiles=None, acq=None, notes="", file_key=None, thermal=False, auth_type=None):
        """One authorised flight: take off at `launch` (xy), fly `pts` at `alt` m above ground, come back and land."""
        op = OPS[op_id]
        af = op["airframes"][airframe_i % len(op["airframes"])]
        model = af["model"]
        v, climb, fixed, sens, focal, fnum = MODEL_SPEC[model]
        v = speed or v
        r = rng("drone-flight", op_id, mission, int(t0))
        alt = float(alt) * float(r.uniform(0.9, 1.0)) if alt >= 110 else float(alt) * float(r.uniform(0.92, 1.08))   # crews fly near, not at, the planned height
        day_local = local_dt(t0).strftime("%Y%m%d")
        self.seq[(op_id, day_local)] += 1
        fid = f"FLT-{op_id}-{day_local}-{self.seq[(op_id, day_local)]:02d}"
        full = [launch] + list(pts) + [launch]
        x, y, total = path_xy(full, v)
        if fixed and len(x) > 30:                              # round the corners of a fixed-wing track
            k = np.ones(9) / 9.0
            xs = np.convolve(np.concatenate([np.full(4, x[0]), x, np.full(4, x[-1])]), k, "valid")
            ys = np.convolve(np.concatenate([np.full(4, y[0]), y, np.full(4, y[-1])]), k, "valid")
            x, y = xs, ys
        n_cl = max(3, int(alt / climb))
        n_cr = len(x)
        n = n_cl + n_cr + n_cl
        X = np.concatenate([np.full(n_cl, x[0]), x, np.full(n_cl, x[-1])]) + r.normal(0, 0.25, n)
        Y = np.concatenate([np.full(n_cl, y[0]), y, np.full(n_cl, y[-1])]) + r.normal(0, 0.25, n)
        A = np.concatenate([np.linspace(0.3, alt, n_cl), np.full(n_cr, alt), np.linspace(alt, 0.3, n_cl)]) + r.normal(0, 0.15, n)
        if hold:                                                # (index fraction, seconds) pauses, e.g. to hover over a find
            pass
        Tt = int(t0) + np.arange(n)
        jam_note = ""
        if any(a <= t0 <= b for a, b in JAM_WINDOWS):           # satellite-navigation interference near the port, as the aircraft's own log shows it
            dj = math.hypot(float(X.mean()) - JAMMER[0], float(Y.mean()) - JAMMER[1]) / 1000.0
            if dj < 16.0:
                amp = 4.0 + 34.0 * (1.0 - dj / 16.0)
                wx = np.cumsum(r.normal(0, 1.0, n)); wy = np.cumsum(r.normal(0, 1.0, n))
                wx -= np.linspace(wx[0], wx[-1], n); wy -= np.linspace(wy[0], wy[-1], n)
                sc = amp / max(1.0, float(np.abs(np.concatenate([wx, wy])).max()))
                X = X + wx * sc + r.normal(0, amp / 6.0, n); Y = Y + wy * sc + r.normal(0, amp / 6.0, n)
                jam_note = "GNSS position warnings in flight; flown on visual reference"
        dx = np.gradient(X); dy = np.gradient(Y)
        course = (np.degrees(np.arctan2(dx, dy)) + 360.0) % 360.0
        course[:n_cl] = course[n_cl] if n_cr > 1 else 0.0
        course[-n_cl:] = course[-n_cl - 1]
        lat = 27.75 + Y / 110950.0
        lon = -97.40 + X / (111320.0 * math.cos(math.radians(27.75)))
        hour = local_dt(t0).hour + local_dt(t0).minute / 60.0
        night = hour < 6.6 or hour > 19.6
        if thermal or ("thermal" in sens.lower() and night):
            cam_iso, shutter, ct, ev = "", "", "", ""
        else:
            cam_iso = 100 if 8.5 < hour < 17.5 else (400 if not night else 3200)
            shutter = "1/1000" if cam_iso == 100 else ("1/320" if cam_iso == 400 else "1/30")
            ct = int(5500 + r.normal(0, 150)) if not night else 4200
            ev = round(float(r.choice([0.0, 0.0, -0.3, 0.3])), 1)
        self.vid[op_id] += 1
        vname = (f"DJI_{self.vid[op_id]:04d}.MP4" if "DJI" in model else f"{mission.replace('/', '-')}_{day_local}.{'tiles' if fixed else 'MP4'}")
        gp = np.full(n, gimbal) + r.normal(0, 0.3, n)
        gy = (course + r.normal(0, 0.8, n)) % 360.0
        fk = file_key or iso_month(t0)
        rows = self.tel[fk]
        drop = np.zeros(n, bool)                                # recorder dropouts: most flights lose a few frames, a few lose a run of them
        if r.random() < 0.8:
            for _ in range(int(r.poisson(1.6)) + (1 if r.random() < 0.1 else 0)):
                i0 = int(r.integers(5, max(6, n - 5)))
                drop[i0:i0 + int(r.choice([1, 1, 1, 2, 3, 8, 20], p=[0.4, 0.2, 0.1, 0.12, 0.08, 0.07, 0.03]))] = True
        for i in range(n):
            if drop[i]:
                continue
            tt = int(Tt[i])
            ss = i
            rows.append(f"{fid},{i + 1},{iso(tt)},{ss // 3600:02d}:{ss % 3600 // 60:02d}:{ss % 60:02d}.000,{lat[i]:.6f},{lon[i]:.6f},{A[i]:.1f},{A[i] + 3.5:.1f},"
                        f"{cam_iso},{shutter},{fnum},{focal},{ev},{ct},{gp[i]:.1f},{gy[i]:.1f},{r.normal(0, 0.1):.1f},{course[i]:.1f},{op_id},{model},{mission},{vname}")
        self.auth_n += 1
        tfr = t0 >= T_TFR and t0 < local_ts(21, "00:00")
        atype = auth_type or ("Special Governmental Interest waiver" if tfr else ("LAANC" if op["org_type"].startswith(("Contractor", "News", "University")) else "Certificate of Authorization"))
        aid = f"{'SGI' if atype.startswith('Special') else ('COA' if atype.startswith('Cert') else 'LAANC')}-{local_dt(t0):%y%m%d}-{self.auth_n:05d}"
        cx, cy = float(np.mean(X)), float(np.mean(Y))
        rad = float(np.hypot(X - cx, Y - cy).max()) + 150.0
        clat, clon = ll(cx, cy)
        lla = ll(*launch)
        self.auth.append([aid, atype, op_id, af["airframe_id"], iso(int(t0) - int(r.uniform(1800, 86400))), iso(int(t0) - 300), iso(int(Tt[-1]) + 600),
                          round(clat, 5), round(clon, 5), int(round(rad, -1)), int(math.ceil(alt / FT / 50.0) * 50), "approved"])
        tkm = float(np.hypot(np.diff(X), np.diff(Y)).sum()) / 1000.0
        self.log.append([fid, op_id, af["airframe_id"], model, mission, aid, round(lla[0], 5), round(lla[1], 5), iso(int(Tt[0])), iso(int(Tt[-1])), n,
                         round(tkm, 1), round(float(A.max()), 0), sensor or sens, band, gsd if gsd is not None else "", tile_set or "", tiles if tiles is not None else "",
                         acq[0] if acq else "", acq[1] if acq else "", "; ".join(q for q in (notes, jam_note) if q)])
        self.tracks.append(({"fid": fid, "op": op_id, "aid": aid, "rid": af.get("faa_registration", ""), "remote_id": af.get("remote_id", True), "model": model},
                            Tt, X, Y, A))
        return fid, int(Tt[-1]), tkm


def iso_month(t):
    return iso(t)[:7]


# ============================================================================ authorised flights
def near_restricted(t, cxy):
    """Canon: no authorisation exists for the Riverside / Up River Road corridor or the Inner Harbor
    between D-12 and D-3, and nothing authorised flies near the air station on the nights of D+1 to D+10."""
    lat, lon = ll(*cxy)
    if local_ts(-12, "00:00") <= t <= T_TFR:
        b = INNER_HARBOR_BOX
        if (b[0] <= lon <= b[2] and b[1] <= lat <= b[3]) or math.hypot(cxy[0] - P("sub01")[0], cxy[1] - P("sub01")[1]) < 3500:
            return True
    if local_ts(1, "00:00") <= t <= local_ts(11, "12:00"):
        h = local_dt(t).hour
        if (h >= 19 or h < 7) and math.hypot(cxy[0] - P("nas")[0], cxy[1] - P("nas")[1]) < 6000:
            return True
    return False


def build_flights(F):
    def wind_ok(t, p):
        la, lo = ll(*p)
        return storm_wind_kt(t, la, lo)[0] < 22.0

    def can_fly(t, p):
        if T_TFR <= t < local_ts(1, "05:30"):
            return False
        return wind_ok(t, p) and not near_restricted(t, p)

    def weekday(day):
        return (1 + day) % 7

    def survey(op, i, mission, t0, target, size=(400, 300), alt=60, spacing=45, launch=None, dist=(250, 700), **kw):
        r = rng("drone-survey", op, mission, int(t0))
        tgt = target if isinstance(target, tuple) else P(target)
        if not can_fly(t0, tgt):
            return None
        la = launch or field_launch(tgt, r, dist)
        return F.add(op, i, mission, t0, la, lawn(tgt[0], tgt[1], size[0], size[1], spacing, vertical=bool(r.integers(0, 2))), alt, **kw)

    def circle(op, i, mission, t0, target, rad=120, alt=50, turns=2, launch=None, dist=(200, 500), **kw):
        r = rng("drone-orbit", op, mission, int(t0))
        tgt = target if isinstance(target, tuple) else P(target)
        if not can_fly(t0, tgt):
            return None
        la = launch or field_launch(tgt, r, dist)
        return F.add(op, i, mission, t0, la, orbit(tgt[0], tgt[1], rad, turns, start=float(r.uniform(0, 6.28))), alt, gimbal=-35.0, **kw)

    def line(op, i, mission, t0, a, b, alt=45, offset=30, launch=None, **kw):
        r = rng("drone-line", op, mission, int(t0))
        if not can_fly(t0, a):
            return None
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L * offset, dx / L * offset
        la = launch or field_launch(a, r, (150, 400))
        return F.add(op, i, mission, t0, la, [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)], alt, gimbal=-60.0, **kw)

    # ---- named places for routine work
    bridge_n, bridge_s = xy(27.8188, -97.3930), xy(27.8040, -97.3995)       # Harbor Bridge approaches (along US 181)
    cw_n, cw_s = xy(27.8700, -97.3440), xy(27.8370, -97.3740)               # Nueces Bay Causeway
    shore = {"north_beach": (xy(27.8200, -97.3870), xy(27.8440, -97.3790)), "portland": (xy(27.8690, -97.3250), xy(27.8800, -97.2990)),
             "nueces_bay": (xy(27.8370, -97.4250), xy(27.8440, -97.3960)), "indian_point": (xy(27.8490, -97.3580), xy(27.8560, -97.3450)),
             "flour_bluff": (xy(27.6600, -97.2760), xy(27.6790, -97.2720)), "ingleside": (xy(27.8230, -97.2100), xy(27.8330, -97.1900))}
    debris_sites = {}
    for name, (lat, lon) in {"DEBRIS-CAL": (27.8440, -97.6050), "DEBRIS-FB": (27.6640, -97.3040), "DEBRIS-PTL": (27.8890, -97.3120), "DEBRIS-RKP": (28.0380, -97.0680),
                             "DEBRIS-WEST": (27.7760, -97.4820)}.items():
        rr = rng("debris-site", name)
        d, sla, slo, rn, cls = G.roads.nearest(lat, lon)
        debris_sites[name] = xy(sla + 0.0012, slo + 0.0012) if G.is_land(sla + 0.0012, slo + 0.0012) else xy(sla, slo)

    for day in range(-30, 120):
        r = rng("drone-day", day)
        wd = weekday(day)
        d0 = local_ts(day, "00:00")
        H = lambda hhmm: local_ts(day, hhmm) + int(r.uniform(0, 1500))
        pre = day <= -3
        if day == -30:
            circle("DRN-OP-007", 0, "LEDGER-PHOTO", local_ts(-30, "08:40"), "downtown", rad=120, alt=70)
        if day == 118:
            circle("DRN-OP-004", 0, "H6-AERIALS", local_ts(118, "16:10"), "north_beach", rad=150, alt=80)
        if day == 119:
            circle("DRN-OP-007", 0, "LEDGER-PHOTO", local_ts(119, "10:20"), "downtown", rad=120, alt=70)
        # ---------------- routine programmes (before the storm, and again once things settle)
        if pre or day >= 20:
            if wd == 2:                                         # utility asset inspection, one site a week
                wk = (day + 30) // 7
                site = ["sub01", "sub04", "sub05", "wtp", "sub03", "sub02"][wk % 6]
                survey("DRN-OP-006", wk, f"CBPWA-INSPECT-{site.upper()}", H("09:10"), site, size=(260, 220), alt=45, spacing=40, band="visible and thermal")
            if wd in (1, 4) and (pre and day <= -13 or day >= 20):   # port police perimeter patrols (airframes grounded for service D-12 to the storm)
                a_, b_ = xy(27.8125, -97.4080), xy(27.8118, -97.3985)
                line("DRN-OP-008", day, "PORT-PERIMETER-PATROL", H("15:20" if wd == 1 else "06:50"), a_, b_, alt=40)
            if wd == 3:                                         # university coastal research
                k = ["flour_bluff", "portland", "indian_point"][((day + 30) // 7) % 3]
                a_, b_ = shore[k]
                line("DRN-OP-012", day, f"TAMUCC-SHORELINE-{k.upper().replace('_', '-')}", H("10:30"), a_, b_, alt=60, offset=45, band="multispectral")
            if wd == 0 and ((day + 30) // 7) % 2 == 0:          # parks and wildlife shoreline counts
                a_, b_ = shore["nueces_bay"] if pre else shore[str(r.choice(["nueces_bay", "indian_point", "north_beach"]))]
                line("DRN-OP-009", 0, "TPWD-ROOKERY-COUNT", H("08:00"), a_, b_, alt=75, offset=60)
            if wd == 1 and ((day + 30) // 28) != ((day + 23) // 28):   # monthly bridge inspection
                line("DRN-OP-002", 0, "TXDOT-HARBOR-BRIDGE-ROUTINE", H("09:40"), bridge_s, bridge_n, alt=55, launch=field_launch(bridge_s, r, (100, 300)))
            if r.random() < 0.10:
                circle("DRN-OP-004", 0, "H6-AERIALS", H("17:10"), str(r.choice(["downtown", "north_beach", "port_aransas", "flour_bluff"])), rad=150, alt=80)
            if r.random() < 0.07:
                circle("DRN-OP-007", 0, "LEDGER-PHOTO", H("11:20"), str(r.choice(["downtown", "hillcrest", "calallen", "portland"])), rad=120, alt=70)
            if wd == 5 and ((day + 30) // 7) % 4 == 1:
                survey("DRN-OP-013", 0, "NCSO-TRAINING", H("09:00"), "calallen", size=(300, 300), alt=50, launch=xy(SITES["UAS-SITE-CAL"]["latitude"], SITES["UAS-SITE-CAL"]["longitude"]))
                survey("DRN-OP-003", 0, "CCFD-TRAINING", H("09:30"), "flour_bluff", size=(300, 300), alt=50, launch=xy(SITES["UAS-SITE-FB"]["latitude"], SITES["UAS-SITE-FB"]["longitude"]))
        # ---------------- search and rescue support, D+1 to D+5 (EVT-1703)
        if 1 <= day <= 5:
            n_day = {1: 9, 2: 7, 3: 6, 4: 4, 5: 3}[day]
            for i in range(n_day):
                nb = ["calallen", "north_beach", "flour_bluff", "calallen", "flour_bluff", "north_beach"][i % 6]
                hh = ["06:40", "07:50", "09:10", "10:40", "12:20", "14:10", "16:00", "20:40", "22:10"][i]
                if int(hh[:2]) >= 19 and nb == "flour_bluff":
                    nb = "calallen"
                b = AREAS["AREA-NBH-" + nb.upper().replace("_", "")]["bbox"]
                c = xy(r.uniform(b[1] + 0.004, b[3] - 0.004), r.uniform(b[0] + 0.004, b[2] - 0.004))
                survey("DRN-OP-005", i, f"MERIDIAN-TIR-SAR-{nb.upper().replace('_', '-')}-{i + 1:02d}", H(hh), c, size=(520, 420), alt=70, spacing=55, thermal=True,
                       band="long-wave infrared", sensor="radiometric thermal imager 640x512")
            for i in range(3 if day <= 3 else 1):
                nb = ["flour_bluff", "north_beach", "flour_bluff"][i]
                b = AREAS["AREA-NBH-" + nb.upper().replace("_", "")]["bbox"]
                c = xy(r.uniform(b[1] + 0.004, b[3] - 0.004), r.uniform(b[0] + 0.004, b[2] - 0.004))
                survey("DRN-OP-003", i, f"CCFD-SAR-{nb.upper().replace('_', '-')}-{i + 1:02d}", H(["08:20", "11:30", "15:10"][i]), c, size=(380, 300), alt=55)
            for i in range(2 if day <= 3 else 1):
                b = AREAS["AREA-NBH-CALALLEN"]["bbox"]
                c = xy(r.uniform(b[1] + 0.004, b[3] - 0.004), r.uniform(b[0] + 0.004, b[2] - 0.004))
                survey("DRN-OP-013", i, f"NCSO-SAR-CALALLEN-{i + 1:02d}", H(["09:00", "13:40"][i]), c, size=(380, 300), alt=55, band="visible and thermal")
        if 6 <= day <= 12:                                       # Meridian moves to damage assessment (EVT-1706)
            for i in range(2):
                nb = str(r.choice(["flour_bluff", "north_beach", "calallen", "port_aransas", "portland"]))
                c = (P(nb)[0] + r.normal(0, 600), P(nb)[1] + r.normal(0, 600))
                survey("DRN-OP-005", i, f"MERIDIAN-DAMAGE-{nb.upper().replace('_', '-')}", H(["09:30", "14:00"][i]), c, size=(450, 380), alt=70, spacing=55, band="visible and thermal")
        # ---------------- bridges: inspections on D+1 and D+3 (EVT-0304), JFK causeway D+2
        if day in (1, 3):
            line("DRN-OP-002", 0, "TXDOT-HARBOR-BRIDGE-POST-STORM", H("08:30"), bridge_s, bridge_n, alt=55, launch=field_launch(bridge_s, r, (100, 300)))
            line("DRN-OP-002", 1, "TXDOT-NUECES-BAY-CAUSEWAY-POST-STORM", H("10:40"), cw_s, cw_n, alt=50, launch=field_launch(cw_s, r, (100, 300)), speed=12.0)
        if day == 2:
            line("DRN-OP-002", 0, "TXDOT-JFK-CAUSEWAY-POST-STORM", H("09:00"), xy(27.6352, -97.2500), xy(27.6348, -97.2310), alt=50)
        # ---------------- oil: shoreline surveys D+1 and D+2 (EVT-0314), mapping to D+20, cleanup surveys to D+44 (EVT-0410)
        if day in (1, 2):
            a_, b_ = shore["north_beach"]
            line("DRN-OP-010", 0, "NOAA-ORR-SHORELINE-NORTH-BEACH", H("13:10"), a_, b_, alt=110, offset=70)
            a_, b_ = shore["nueces_bay"]
            line("DRN-OP-010", 0, "NOAA-ORR-SHORELINE-NUECES-BAY", H("15:20"), a_, b_, alt=110, offset=70)
            a_, b_ = shore["portland"] if day == 2 else shore["indian_point"]
            line("DRN-OP-011", day, "USCG-SHORELINE-ASSESSMENT", H("11:00"), a_, b_, alt=60, offset=40)
        if 3 <= day <= 44:
            if day <= 20 or wd in (1, 4):
                k = ["north_beach", "nueces_bay", "portland", "indian_point"][day % 4]
                a_, b_ = shore[k]
                nm = "USCG-BOOM-INSPECTION-" if day < 30 else "USCG-CLEANUP-SURVEY-"
                line("DRN-OP-011", day, nm + k.upper().replace("_", "-"), H("09:20"), a_, b_, alt=55, offset=40)
            if (day <= 20 and day % 3 == 0) or (day > 20 and wd == 2):
                k = ["nueces_bay", "north_beach", "portland"][(day // 3) % 3]
                a_, b_ = shore[k]
                nm = "NOAA-ORR-OIL-MAPPING-" if day < 30 else "NOAA-ORR-CLEANUP-SURVEY-"
                line("DRN-OP-010", 0, nm + k.upper().replace("_", "-"), H("12:40"), a_, b_, alt=110, offset=80)
            if 4 <= day <= 20 and day % 2 == 0:
                a_, b_ = shore[str(r.choice(["nueces_bay", "indian_point"]))]
                line("DRN-OP-009", 0, "TPWD-OILED-WILDLIFE-SURVEY", H("07:40"), a_, b_, alt=70, offset=55)
        # ---------------- utility restoration patrols D+2 to D+35
        if 2 <= day <= 35 and (day <= 14 or wd < 5):
            site = ["sub04", "sub05", "sub03", "wtp", "sub01", "sub02"][day % 6]
            c = (P(site)[0] + r.normal(0, 900), P(site)[1] + r.normal(0, 900))
            a_ = c
            b_ = (c[0] + r.normal(0, 700), c[1] + r.normal(0, 700))
            line("DRN-OP-006", day, f"CBPWA-FEEDER-PATROL-{site.upper()}", H("08:40"), a_, b_, alt=45, band="visible and thermal")
        # ---------------- news
        if 1 <= day <= 10 or (day in (30, 33, 44, 46, 52, 58, 60)):
            st = {1: "flour_bluff", 2: "north_beach", 3: "harbor_bridge", 4: "nueces_bay_shore", 5: "flour_bluff", 6: "calallen", 7: "calallen", 8: "port_aransas",
                  9: "hillcrest", 10: "north_beach", 30: "north_beach", 33: "north_beach", 44: "port_aransas", 46: "port_aransas", 52: "port_aransas",
                  58: "north_beach", 60: "downtown"}[day]
            circle("DRN-OP-004", 0, "H6-STORM-COVERAGE" if day <= 10 else "H6-AERIALS", H("07:30"), st, rad=160, alt=90)
            if day % 2 == 0:
                circle("DRN-OP-007", 0, "LEDGER-PHOTO", H("10:10"), st, rad=130, alt=80)
        # ---------------- insurance imaging D+5 to D+75
        if 5 <= day <= 75 and wd < 6:
            for i in range(2 if day <= 40 else 1):
                nb = str(r.choice(["flour_bluff", "port_aransas", "rockport", "north_beach", "padre", "aransas_pass", "portland"]))
                c = (P(nb)[0] + r.normal(0, 900), P(nb)[1] + r.normal(0, 900))
                la, lo = ll(*c)
                if not G.is_land(la, lo):
                    continue
                survey("DRN-OP-014", i + day, f"LPC-CLAIMS-{nb.upper().replace('_', '-')}", H(["09:00", "13:30"][i]), c, size=(240, 200), alt=45, spacing=40)
        # ---------------- debris staging sites, weekly from D+14 to D+70 (EVT-0505)
        if 14 <= day <= 70 and wd == 2:
            for j, (name, c) in enumerate(debris_sites.items()):
                survey("DRN-OP-013", j, f"NCSO-{name}-VOLUME-SURVEY", H("08:00") + j * 3300, c, size=(320, 260), alt=60, spacing=35, gsd=0.02,
                       notes="photogrammetric pile-volume survey")
        # ---------------- FEMA contractor swarm
        argus_sites = {k: xy(SITES[k]["latitude"], SITES[k]["longitude"]) for k in ("UAS-SITE-CRP", "UAS-SITE-CAL", "UAS-SITE-FB")}
        if day == 2:                                             # depot hangars (EVT-0307)
            c = P("depot")
            if can_fly(H("10:00"), c):
                F.add("DRN-OP-001", 0, "FEMA-UAV-0916-CCAD-HANGARS", local_ts(2, "10:05"), argus_sites["UAS-SITE-FB"], lawn(c[0], c[1], 900, 700, 120), 122, gsd=0.03,
                      tile_set="FEMA-UAV-0916-CCAD", tiles=3120, file_key="2027-09_argus")
        if day in (3, 4):                                        # Phase 1 grid (EVT-1104): eight aircraft, 12:02Z to about 13:50Z
            grids3 = [("UAS-SITE-CRP", 27.810, -97.405, 7.0, 7.0), ("UAS-SITE-CRP", 27.770, -97.460, 7.6, 6.6), ("UAS-SITE-CRP", 27.712, -97.385, 7.6, 6.6),
                      ("UAS-SITE-CAL", 27.855, -97.612, 9.0, 7.0), ("UAS-SITE-CAL", 27.806, -97.545, 7.6, 7.0), ("UAS-SITE-FB", 27.668, -97.300, 6.0, 7.4),
                      ("UAS-SITE-FB", 27.617, -97.226, 6.4, 7.0), ("UAS-SITE-FB", 27.712, -97.318, 5.6, 7.0)]
            grids4 = [("UAS-SITE-CRP", 27.760, -97.395, 6.0, 6.0), ("UAS-SITE-CAL", 27.880, -97.320, 6.0, 5.0), ("UAS-SITE-CAL", 27.830, -97.660, 6.0, 6.0),
                      ("UAS-SITE-FB", 27.690, -97.170, 5.0, 9.0), ("UAS-SITE-FB", 27.650, -97.345, 6.0, 6.0), ("UAS-SITE-CRP", 27.730, -97.455, 7.0, 6.0),
                      ("UAS-SITE-CRP", 27.830, -97.480, 8.0, 4.0), ("UAS-SITE-FB", 27.745, -97.345, 6.0, 5.0)]
            total = 0.0
            for gi, (site, lat, lon, wkm, hkm) in enumerate(grids3 if day == 3 else grids4):
                c = xy(lat, lon)
                la = argus_sites[site]
                transit = 2 * math.hypot(c[0] - la[0], c[1] - la[1]) / 1000.0
                target_km = 183.0
                nlines = max(4, int(round((target_km - transit - hkm) / (wkm + (hkm / 1.0) * 0.0 + 0.001))))
                spacing = hkm * 1000.0 / max(1, nlines - 1)
                pts = lawn(c[0], c[1], wkm * 1000.0, hkm * 1000.0, spacing)
                # trim or extend the last line so the track comes to 180 km
                full = [la] + pts + [la]
                L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(full, full[1:])) / 1000.0
                while L > target_km + 1.0 and len(pts) > 4:
                    pts = pts[:-2]
                    full = [la] + pts + [la]
                    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(full, full[1:])) / 1000.0
                if L < target_km - 0.5:
                    extra = (target_km - L) * 1000.0 / 2.0
                    last = pts[-1]
                    pts = pts + [(last[0], last[1] + extra)]
                t0 = local_ts(day, "07:02") + gi * 95 + int(rng("argus-launch", day, gi).uniform(0, 240))
                fid, te, tkm = F.add("DRN-OP-001", gi, f"FEMA-UAV-{_mmdd(day)}-GRID{gi + 1:02d}", t0, la, pts, 122, gsd=0.03, tile_set=f"FEMA-UAV-{_mmdd(day)}-GRID{gi + 1:02d}",
                                     tiles=int(round(847000 / 8.0 + (gi - 3.5) * 900)) if day == 3 else int(98000 + gi * 1100), file_key="2027-09_argus",
                                     notes="nadir optical, lawnmower pattern at 400 ft above ground")
                total += tkm
            print(f"  Argus grid D+{day}: {total:.0f} km of track")
        if day == 8:                                             # Phase 2: utility yards (EVT-1105); SUB-02 imaged 10:34Z to 10:51Z
            plan = [("UTL-01", "sub01", "10:08", 14, 1210), ("UTL-02", "sub02", None, 17, 1247), ("UTL-03", "sub03", "11:02", 16, 1180),
                    ("UTL-04", "sub04", "11:26", 14, 1105), ("UTL-05", "sub05", "11:50", 14, 1090), ("UTL-06", "wtp", "11:10", 22, 2100)]
            for gi, (tile, site, hh, minutes, tiles) in enumerate(plan):
                c = P(site)
                la = argus_sites["UAS-SITE-CAL"] if site == "wtp" else (argus_sites["UAS-SITE-FB"] if site == "sub05" else argus_sites["UAS-SITE-CRP"])
                v = 28.0
                tr = math.hypot(c[0] - la[0], c[1] - la[1]) / v
                acq0 = ts("2027-09-22T10:34Z") if site == "sub02" else ts("2027-09-22T%sZ" % hh)
                t0 = acq0 - tr - 122 / 4.0 - 6
                # racetrack passes over the yard for the acquisition window
                turns = minutes * 60.0 * v / (2 * math.pi * 380.0 + 2 * 900.0)
                pts = []
                for k in range(int(math.ceil(turns))):
                    off = (k % 4 - 1.5) * 45.0
                    pts += [(c[0] - 450, c[1] + off), (c[0] + 450, c[1] + off)] + orbit(c[0] + 450, c[1] + off + 380, 380, 0.5, 8, start=math.pi)[1:] + \
                           [(c[0] + 450, c[1] + off + 760), (c[0] - 450, c[1] + off + 760)] + orbit(c[0] - 450, c[1] + off + 380, 380, 0.5, 8, start=0.0)[1:]
                # cut the pattern to the acquisition time
                need = minutes * 60.0 * v
                out, acc = [pts[0]], 0.0
                for a, b in zip(pts, pts[1:]):
                    d = math.hypot(b[0] - a[0], b[1] - a[1])
                    if acc + d >= need:
                        f = (need - acc) / d
                        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                        break
                    out.append(b)
                    acc += d
                F.add("DRN-OP-001", gi, f"FEMA-UAV-0922-{tile}", t0, la, out, 122, gsd=0.12, tile_set=f"FEMA-UAV-0922-{tile}", tiles=tiles, thermal=True,
                      sensor="nadir long-wave infrared mapping payload", band="7.5-13.5 um",
                      acq=(iso(int(acq0)), iso(int(acq0 + minutes * 60))), file_key="2027-09_argus", notes="pre-dawn thermal passes over utility yard")
        if day == 15:
            c = P("wtp")
            F.add("DRN-OP-001", 0, "FEMA-UAV-0929-UTL-06", local_ts(15, "08:10"), argus_sites["UAS-SITE-CAL"], lawn(c[0], c[1], 1100, 800, 90), 122, gsd=0.03,
                  tile_set="FEMA-UAV-0929-UTL-06", tiles=2100, file_key="2027-09_argus")
        if day in (22, 36, 45):                                  # Phases 3 and 4: recovery monitoring; final pass D+45
            n_ac = 8 if day == 45 else 4
            for gi in range(n_ac):
                site = ["UAS-SITE-CRP", "UAS-SITE-CAL", "UAS-SITE-FB"][gi % 3]
                la = argus_sites[site]
                rr = rng("argus-late", day, gi)
                c = (la[0] + rr.uniform(-9000, 9000), la[1] + rr.uniform(-7000, 7000))
                F.add("DRN-OP-001", gi, f"FEMA-UAV-{_mmdd(day)}-RM{gi + 1:02d}", local_ts(day, "08:05") + gi * 140 + int(rr.uniform(0, 300)), la, lawn(c[0], c[1], 5200, 4200, 420), 122, gsd=0.03,
                      tile_set=f"FEMA-UAV-{_mmdd(day)}-RM{gi + 1:02d}", tiles=int(41000 + gi * 700), file_key="2027-10_argus")


def write_flights(F):
    old = [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "05_other_sources", "drone_video", "*")) if not os.path.basename(p).startswith(("drone_telemetry_", "logs"))]
    retire(old)
    total = 0
    for key in sorted(F.tel):
        p = out_path(f"05_other_sources/drone_video/drone_telemetry_{key}.csv")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(",".join(TEL_HEADER) + "\n")
            fh.write("\n".join(F.tel[key]) + "\n")
        total += len(F.tel[key])
        print(f"drone_telemetry_{key}.csv  {len(F.tel[key]):>8} rows")
    # the manned thermal-survey sortie (canon EVT-1106) is logged alongside the unmanned flights
    a = AC["CBAS208"]
    t0, t1 = adsb_airborne(a["icao24"], ts("2027-09-25T09:00Z"), ts("2027-09-25T12:00Z"))
    log = sorted(F.log, key=lambda r: r[8])
    if t0:
        log.append(["CBAS-TIR-0925", a["aircraft_id"], a["registration"], a["model"], "CBAS-TIR-0925", "", 27.77137, -97.50334, iso(t0), iso(t1), t1 - t0,
                    "", 610, "FLIR SAFIRE 380", "7.5-13.5 um", 0.4, "FEMA-TIR-0925-UTL", "", iso(t0 + 900), iso(t1 - 600),
                    "manned thermal survey of substations and the water plant at 2,000 ft above ground; position track in ADS-B"])
        log.sort(key=lambda r: r[8])
    write_csv("05_other_sources/drone_video/logs/flight_log.csv", LOG_HEADER, log)
    amb = 23.2
    readings = [
        ("GW-FAC-SUB-01", "main feeder breaker B1-A", 31.6), ("GW-FAC-SUB-01", "main feeder breaker B1-B", 31.9), ("GW-FAC-SUB-01", "main feeder breaker B1-C", 30.8),
        ("GW-FAC-SUB-01", "main transformer T1", 41.5),
        ("GW-FAC-SUB-02", "main feeder breaker B2-A", 24.3), ("GW-FAC-SUB-02", "main feeder breaker B2-B", 30.9), ("GW-FAC-SUB-02", "main feeder breaker B2-C", 24.1),
        ("GW-FAC-SUB-02", "main transformer T1", 38.7),
        ("GW-FAC-SUB-03", "main feeder breaker B3-A", 31.2), ("GW-FAC-SUB-03", "main feeder breaker B3-B", 24.0), ("GW-FAC-SUB-03", "main feeder breaker B3-C", 31.5),
        ("GW-FAC-SUB-03", "main transformer T1", 40.2),
        ("GW-FAC-SUB-04", "main feeder breaker B4-A", 30.4), ("GW-FAC-SUB-04", "main feeder breaker B4-B", 31.1), ("GW-FAC-SUB-04", "main feeder breaker B4-C", 30.7),
        ("GW-FAC-SUB-04", "main transformer T1", 39.9),
        ("GW-FAC-SUB-05", "main feeder breaker B5-A", 30.9), ("GW-FAC-SUB-05", "main feeder breaker B5-B", 30.2), ("GW-FAC-SUB-05", "main feeder breaker B5-C", 31.4),
        ("GW-FAC-SUB-05", "main transformer T1", 40.8),
        ("GW-FAC-UTL-01", "high-service pump station roof", 24.9), ("GW-FAC-UTL-01", "standby generator enclosure", 36.4),
    ]
    rows = []
    for i, (asset, comp, temp) in enumerate(readings):
        rows.append(["CBAS-TIR-0925", "FEMA-TIR-0925-UTL", asset, comp, temp, amb if asset != "GW-FAC-UTL-01" else 23.0,
                     round(temp - (amb if asset != "GW-FAC-UTL-01" else 23.0), 1), "FLIR SAFIRE 380", "7.5-13.5 um", 0.4])
    write_csv("05_other_sources/drone_video/logs/thermal_survey_readings.csv",
              ["flight_id", "tile_set_id", "asset_id", "component", "surface_temp_c", "ambient_temp_c", "delta_c", "sensor", "spectral_band", "ground_resolution_m"], rows)
    print(f"drone telemetry total {total} rows, {len(F.log)} flights")


# ============================================================================ ADS-B lookups (files on disk)
_adsb_cache = {}


def adsb_rows(icao, t0, t1):
    out = []
    for month in sorted({iso(t0)[:7], iso(t1)[:7]}):
        fp = os.path.join(ROOT, "05_other_sources", "adsb", f"adsb_{month}.csv")
        if not os.path.exists(fp):
            continue
        if fp not in _adsb_cache:
            rows = defaultdict(list)
            with open(fp, encoding="utf-8") as fh:
                rd = csv.reader(fh)
                next(rd)
                for r in rd:
                    rows[r[0]].append((int(r[3]), float(r[6]), float(r[5]), r[8] == "True", float(r[13] or 0)))
            _adsb_cache[fp] = rows
        out += [r for r in _adsb_cache[fp].get(icao, []) if t0 <= r[0] <= t1]
    return out


def adsb_airborne(icao, t0, t1):
    rows = [r for r in adsb_rows(icao, t0, t1) if not r[3]]
    return (rows[0][0], rows[-1][0]) if rows else (None, None)


def adsb_pos(icao, t):
    rows = adsb_rows(icao, t - 180, t + 180)
    if not rows:
        return None
    b = [r for r in rows if r[0] <= t]
    a = [r for r in rows if r[0] >= t]
    if b and a:
        p, q = b[-1], a[0]
        f = 0.0 if q[0] == p[0] else (t - p[0]) / (q[0] - p[0])
        return (p[1] + (q[1] - p[1]) * f, p[2] + (q[2] - p[2]) * f, p[4] + (q[4] - p[4]) * f)
    p = (b or a)[-1 if b else 0]
    return (p[1], p[2], p[4])


# ============================================================================ detection sensors
def sensor_table():
    """Sensor sites. Radar buoys sit in water beside the ship channel; fixed sensors on land."""
    def land(lat, lon):
        d, sla, slo, n, c = G.roads.nearest(lat, lon)
        for la, lo in ((lat, lon), (sla + 0.0006, slo + 0.0006), (sla, slo)):
            if G.is_land(la, lo):
                return round(la, 5), round(lo, 5)
        return round(lat, 5), round(lon, 5)

    S = [
        dict(sensor_id="USCG-RDR-R14", name="Coast Guard radar buoy R-14, ship channel east of the Harbor Bridge", kind="X-band surface-search radar, raw plot archive",
             owner="U.S. Coast Guard Sector Corpus Christi", lat=27.8120, lon=-97.3840, range_m=2500, installed="2024-03-11T00:00:00Z", alert_rcs_m2=0.05),
        dict(sensor_id="USCG-RDR-R18", name="Coast Guard radar buoy R-18, Tule Lake Channel", kind="X-band surface-search radar, raw plot archive",
             owner="U.S. Coast Guard Sector Corpus Christi", lat=27.8165, lon=-97.4592, range_m=2500, installed="2024-03-12T00:00:00Z", alert_rcs_m2=0.05),
        dict(sensor_id="USCG-RDR-R22", name="Coast Guard radar buoy R-22, Main Turning Basin", kind="X-band surface-search radar, raw plot archive",
             owner="U.S. Coast Guard Sector Corpus Christi", lat=27.8132, lon=-97.4040, range_m=2500, installed="2024-03-12T00:00:00Z", alert_rcs_m2=0.05),
        dict(sensor_id="ESM-CAMCC04", name="Electronic support measures receiver aboard CBP aircraft CAMCC-04 (position is the aircraft's)", kind="airborne RF intercept and direction finding",
             owner="U.S. Customs and Border Protection, Air and Marine Operations", lat="", lon="", range_m=60000, installed="2026-01-15T00:00:00Z", alert_rcs_m2=""),
    ]
    for i, (lat, lon, nm) in enumerate([(27.7052, -97.2850, "north perimeter"), (27.6905, -97.3005, "west gate"), (27.6830, -97.2760, "south perimeter"),
                                         (27.6990, -97.2775, "Army depot hangar line")]):
        la, lo = land(lat, lon)
        S.append(dict(sensor_id=f"NASCC-PS-{i + 1:02d}", name=f"NAS Corpus Christi perimeter sensor, {nm}", kind="RF direction finder and short-range radar",
                      owner="Naval Air Station Corpus Christi security department", lat=la, lon=lo, range_m=1800, installed="2025-06-02T00:00:00Z", alert_rcs_m2=0.01))
    la, lo = land(27.6935, -97.2830)
    S.append(dict(sensor_id="NASCC-PS-05", name="NAS Corpus Christi portable RF detector, flight line", kind="portable RF detector (bearing only)",
                  owner="Naval Air Station Corpus Christi security department", lat=la, lon=lo, range_m=2500, installed="2027-09-21T22:00:00Z", alert_rcs_m2=""))
    new = [(27.8166, -97.4010, "Port of Corpus Christi, Main Turning Basin north shore"), (27.8118, -97.4075, "Port of Corpus Christi, cargo docks"),
           (27.8205, -97.4350, "Port of Corpus Christi, Avery Point"), (27.8235, -97.4830, "Port of Corpus Christi, Tule Lake"),
           (27.8098, -97.4553, "CBPWA Riverside Switching Station"), (27.8025, -97.4525, "CBPWA Harbor View Substation"), (27.8125, -97.3925, "Harbor Bridge south approach")]
    online = ["2027-10-16T15:00:00Z", "2027-10-16T18:30:00Z", "2027-10-18T16:00:00Z", "2027-10-19T20:15:00Z", "2027-10-20T15:40:00Z", "2027-10-22T17:05:00Z", "2027-10-23T19:20:00Z"]
    for i, ((lat, lon, nm), on) in enumerate(zip(new, online)):
        la, lo = land(lat, lon)
        S.append(dict(sensor_id=f"SENT-RF-{i + 1:02d}", name=f"Counter-UAS RF node, {nm}", kind="RF sensing and direction finding node",
                      owner="Port of Corpus Christi Authority / Coastal Bend Power and Water Authority (Sentinel Airspace Inc. network)", lat=la, lon=lo,
                      range_m=3000, installed=on, alert_rcs_m2=""))
    return S


def hostile_paths():
    """Flight paths of the unauthorised reconnaissance sorties (never written anywhere as such).
    Returns list of dict(n, t0, x, y, alt) sampled every second."""
    marina, sub01, berth = P("marina"), P("sub01"), P("term01")
    out = []

    def fly(n, pts_speed_alt, t_anchor, anchor_index):
        """pts_speed_alt: list of (x, y, speed, alt). t_anchor is the time at vertex anchor_index."""
        xs, ys, al, tt = [], [], [], []
        t = 0.0
        times = [0.0]
        for (a, b) in zip(pts_speed_alt, pts_speed_alt[1:]):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            times.append(times[-1] + d / b[2])
        t0 = t_anchor - times[anchor_index]
        T = np.arange(0, int(times[-1]) + 1)
        X = np.interp(T, times, [p[0] for p in pts_speed_alt]); Y = np.interp(T, times, [p[1] for p in pts_speed_alt]); A = np.interp(T, times, [p[3] for p in pts_speed_alt])
        out.append(dict(n=n, t0=t0, T=T + t0, x=X, y=Y, alt=A))

    # sorties 1 and 2: northern route over Nueces Bay, stand-off orbit north of the switching station (outside every buoy's reach)
    north = [xy(27.8600, -97.2600), xy(27.8780, -97.3300), xy(27.8640, -97.4000), xy(27.8440, -97.4420)]
    stand = xy(27.8440, -97.4500)
    for n, t_on, minutes in ((1, ts("2027-09-04T04:30Z"), 22), (2, ts("2027-09-05T06:40Z"), 16)):
        pts = [(marina[0], marina[1], 13.0, 5.0)] + [(p[0], p[1], 13.0, 175.0) for p in north]
        k_on = len(pts) - 1
        orb = orbit(stand[0], stand[1], 420, minutes * 60 * 9.0 / (2 * math.pi * 420), n=int(minutes * 4), start=0.4)
        pts += [(p[0], p[1], 9.0, 180.0) for p in orb]
        pts += [(p[0], p[1], 13.0, 175.0) for p in reversed(north)] + [(marina[0], marina[1], 13.0, 5.0)]
        fly(n, pts, t_on, k_on)
    # sortie 3: direct line from the marina to the switching station; overhead for about 11 minutes; R-18 holds it 04:15Z-04:33Z
    v3 = 12.4
    alt3 = 482 * FT
    ux, uy = unit(hdg(sub01[0] - marina[0], sub01[1] - marina[1]))
    r18 = xy(27.8165, -97.4592)
    # entry into R-18's 2.5 km circle along the inbound line
    a = 1.0
    bq = 2 * ((marina[0] - r18[0]) * ux + (marina[1] - r18[1]) * uy)
    cq = (marina[0] - r18[0]) ** 2 + (marina[1] - r18[1]) ** 2 - 2470.0 ** 2
    s_in = (-bq - math.sqrt(bq * bq - 4 * a * cq)) / 2
    entry = (marina[0] + ux * s_in, marina[1] + uy * s_in)
    d_to_sub = math.hypot(sub01[0] - entry[0], sub01[1] - entry[1])
    loiter_s = 18 * 60 - 2 * d_to_sub / v3
    orb = orbit(sub01[0], sub01[1], 160, loiter_s * v3 / (2 * math.pi * 160), n=60, start=math.atan2(entry[0] - sub01[0], entry[1] - sub01[1]))
    pts = [(marina[0], marina[1], v3, 5.0), (marina[0] + ux * 600, marina[1] + uy * 600, v3, alt3), (entry[0], entry[1], v3, alt3),
           (orb[0][0], orb[0][1], v3, alt3)] + [(p[0], p[1], v3, alt3) for p in orb[1:]] + [(entry[0], entry[1], v3, alt3),
           (marina[0] + ux * 600, marina[1] + uy * 600, v3, alt3), (marina[0], marina[1], v3, 5.0)]
    fly(3, pts, ts("2027-09-06T04:15Z"), 2)
    # sorties 4 and 5: ground station on the north shore of the Main Turning Basin; two-pass survey of the Rendal berth
    gs = xy(27.8195, -97.4030)
    def port_pattern(v, alt, minutes, jitter_key):
        rr = rng("hostile-port", jitter_key)
        w0, w1 = (berth[0] - 520, berth[1] + 10), (berth[0] + 520, berth[1] + 10)
        p0, p1 = (berth[0] + 520, berth[1] - 70), (berth[0] - 520, berth[1] - 70)
        lap = [w0, w1, p0, p1]
        pts = [(gs[0], gs[1], v, 3.0), (gs[0] - 40, gs[1] - 120, v, alt)]
        need = minutes * 60 * v - 2 * math.hypot(gs[0] - w0[0], gs[1] - w0[1])
        acc, k = 0.0, 0
        cur = w0
        pts.append((w0[0], w0[1], v, alt))
        while True:
            nxt = lap[(k + 1) % 4]
            d = math.hypot(nxt[0] - cur[0], nxt[1] - cur[1])
            if acc + d > need:
                break
            pts.append((nxt[0] + rr.normal(0, 6), nxt[1] + rr.normal(0, 6), v, alt))
            acc += d
            cur = nxt
            k += 1
        pts += [(gs[0] - 40, gs[1] - 120, v, alt), (gs[0], gs[1], v, 3.0)]
        return pts
    fly(4, port_pattern(10.8, 411 * FT, 19, "s4"), ts("2027-09-09T04:58Z"), 0)
    fly(5, port_pattern(11.1, 491 * FT, 23, "s5"), ts("2027-09-11T04:45Z"), 0)
    return out


def build_detections(F):
    S = sensor_table()
    by = {s["sensor_id"]: s for s in S}
    det = defaultdict(list)       # month -> rows
    status = defaultdict(list)
    DET_HEADER = ["time_utc", "sensor_id", "detection_type", "track_id", "latitude", "longitude", "altitude_m", "speed_mps", "course_deg", "rcs_m2",
                  "bearing_deg_true", "range_m", "rf_center_mhz", "rf_signature", "duration_s", "remote_id", "authorization_id", "classification", "confidence", "alert"]
    tid = defaultdict(int)
    first_seen = {}                                          # temporary key -> (sensor, first time); numbered in time order when written

    def track_id(sid, t):
        tid[sid] += 1
        key = f"@{sid}@{tid[sid]}"
        first_seen[key] = (sid, int(t))
        return key

    # ---- sensor availability
    off = {
        "USCG-RDR-R14": [(ts("2027-09-14T03:40Z"), ts("2027-09-20T16:10Z"), "no heartbeat")],
        "USCG-RDR-R18": [(ts("2027-09-14T05:00Z"), ts("2027-09-18T19:30Z"), "no heartbeat")],
        "USCG-RDR-R22": [(ts("2027-09-14T04:50Z"), ts("2027-09-22T15:00Z"), "no heartbeat")],
    }
    for i in range(1, 5):
        off[f"NASCC-PS-{i:02d}"] = [(ts("2027-09-14T05:20Z") + i * 700, ts("2027-09-26T15:00Z") + i * 5400, "no heartbeat")]
    rm = rng("drone-maint")
    for sid in ("USCG-RDR-R14", "USCG-RDR-R18", "USCG-RDR-R22", "NASCC-PS-01", "NASCC-PS-02", "NASCC-PS-03", "NASCC-PS-04"):
        for _ in range(7):                                   # short routine outages, never on the nights that matter
            t = SPAN_START + int(rm.uniform(0, SPAN_END - SPAN_START))
            d = day_of(t)
            if -13 <= d <= 12:
                continue
            off[sid].append((t, t + int(rm.uniform(1.5, 7) * 3600), "scheduled maintenance" if rm.random() < 0.6 else "degraded: low battery"))

    def is_on(sid, t):
        s = by[sid]
        if t < ts(s["installed"]):
            return False
        return not any(a <= t < b for a, b, _ in off.get(sid, []))

    def radar_sees(sid, x, y, alt):
        s = by[sid]
        sx, sy = xy(s["lat"], s["lon"])
        d = math.hypot(x - sx, y - sy)
        if d > s["range_m"] or d < 60:
            return None
        if sid == "USCG-RDR-R14" and ll(x, y)[1] < -97.3952:        # the Harbor Bridge shadows everything west of it
            return None
        return d

    def radar_track(sid, T, X, Y, A, rcs, cls, conf, r, auth="", rid="", every=4, sigma=6.0):
        """Write the part of a path that the radar holds. Returns number of plots."""
        s = by[sid]
        sx, sy = xy(s["lat"], s["lon"])
        cur, n = None, 0
        last_t = None
        for i in range(0, len(T), every):
            t = int(T[i])
            if not is_on(sid, t):
                cur = None
                continue
            d = radar_sees(sid, X[i], Y[i], A[i])
            if d is None:
                cur = None
                continue
            if cur is None or (last_t is not None and t - last_t > 40):
                cur = track_id(sid, t)
            last_t = t
            px, py = X[i] + r.normal(0, sigma), Y[i] + r.normal(0, sigma)
            la, lo = ll(px, py)
            j = min(len(T) - 1, i + every)
            sp = math.hypot(X[j] - X[i], Y[j] - Y[i]) / max(1, (T[j] - T[i])) + r.normal(0, 0.25)
            crs = hdg(X[j] - X[i], Y[j] - Y[i]) if j > i else 0.0
            rc = max(0.002, rcs * math.exp(r.normal(0, 0.12)))
            alert = "true" if (s["alert_rcs_m2"] != "" and rc >= s["alert_rcs_m2"]) else "false"
            det[iso(t)[:7]].append([iso(t), sid, "radar_plot", cur, round(la, 6), round(lo, 6), round(A[i] + r.normal(0, 4.0), 1), round(max(0.0, sp), 1), round(crs, 1),
                                    round(rc, 4), round(hdg(px - sx, py - sy), 1), int(math.hypot(px - sx, py - sy)), "", "", "", rid, auth, cls, round(conf + r.normal(0, 0.04), 2), alert])
            n += 1
        return n

    # ---- 1. unauthorised sorties as the buoys recorded them (raw archive, below the alert threshold)
    hp = hostile_paths()
    rh = rng("drone-hostile")
    for h in hp:
        rcs = {1: 0.012, 2: 0.012, 3: 0.012, 4: 0.014, 5: 0.015}[h["n"]]
        for sid in ("USCG-RDR-R14", "USCG-RDR-R18", "USCG-RDR-R22"):
            radar_track(sid, h["T"], h["x"], h["y"], h["alt"], rcs, "unknown", 0.38, rh)
    # ---- 2. CAMCC-04 electronic-support contacts on patrol nights, including 06:47Z on 5 September (EVT-1902)
    icao = AC["CAMCC-04"]["icao24"]
    marina = P("marina")
    emitters = [("marine radar", 9410.0, "pulsed, 9.4 GHz navigation radar", P("term01")), ("marine radar", 9410.0, "pulsed, 9.4 GHz navigation radar", xy(27.84, -96.92)),
                ("marine radar", 3050.0, "pulsed, S-band navigation radar", xy(27.83, -96.95)), ("VHF marine", 156.8, "narrowband FM voice", xy(27.8366, -97.0391)),
                ("ISM telemetry", 915.0, "LoRa-type chirp, low duty cycle", P("sub04")), ("ISM telemetry", 902.9, "frequency-hopping telemetry, low duty cycle", xy(27.8235, -97.4830)),
                ("ISM telemetry", 927.1, "frequency-hopping telemetry, low duty cycle", P("wtp")), ("wireless LAN", 2437.0, "OFDM, 20 MHz", P("downtown")),
                ("wireless LAN", 2462.0, "OFDM, 20 MHz", P("port_aransas")), ("cellular", 1960.0, "LTE downlink", P("flour_bluff")),
                ("marine radar", 9375.0, "pulsed, 9.4 GHz navigation radar", xy(27.812, -97.30)), ("AIS", 161.975, "GMSK burst", xy(27.80, -96.98)),
                # hobby and industrial emitters that sound like small unmanned aircraft links
                ("unknown emitter", 5785.0, "analog-style video downlink burst", P("southside")), ("unknown emitter", 5805.0, "analog-style video downlink burst", P("portland")),
                ("unknown emitter", 2437.0, "frequency-hopping, 2.4 GHz control link", P("padre")), ("unknown emitter", 2462.0, "frequency-hopping, 2.4 GHz control link", P("calallen")),
                ("ISM telemetry", 902.4, "frequency-hopping burst, data link", P("annaville")), ("unknown emitter", 915.6, "frequency-hopping burst, data link", P("ingleside")),
                ("unknown emitter", 2420.0, "frequency-hopping, 2.4 GHz control link", P("north_beach")), ("unknown emitter", 5745.0, "analog-style video downlink burst", P("rockport")),
                ("unknown emitter", 433.9, "narrowband telemetry burst", P("tuloso")), ("unknown emitter", 1280.0, "wideband FM video", P("aransas_pass"))]
    rp = rng("drone-esm")
    for night in range(-30, 120):
        base = local_ts(night, "00:00") - 2 * 3600
        rows = [q for q in adsb_rows(icao, base, base + 12 * 3600) if not q[3] and q[4] > 4000]
        if len(rows) < 50:
            continue
        t_a, t_b = rows[0][0], rows[-1][0]
        k = int(rp.integers(9, 22))
        for _ in range(k):
            t = int(rp.uniform(t_a, t_b))
            pos = adsb_pos(icao, t)
            if not pos:
                continue
            nm, mhz, sig, src = emitters[int(rp.integers(0, len(emitters)))]
            ax, ay = xy(pos[0], pos[1])
            brg = hdg(src[0] - ax + rp.normal(0, 400), src[1] - ay + rp.normal(0, 400))
            unk = nm == "unknown emitter" or rp.random() < 0.04
            det[iso(t)[:7]].append([iso(t), "ESM-CAMCC04", "rf_contact", track_id("ESM-CAMCC04", t), round(pos[0], 5), round(pos[1], 5), round(pos[2], 0), "", "", "",
                                    round(brg, 1), "", round(mhz + (float(rp.normal(0, 3.0)) if unk else 0.0), 1), sig, round(float(rp.uniform(0.4, 45.0)), 1), "", "",
                                    "unknown emitter" if unk else nm, round(float(rp.uniform(0.3, 0.6) if unk else rp.uniform(0.6, 0.98)), 2), "false"])
    t = ts("2027-09-05T06:47:00Z")
    pos = adsb_pos(icao, t)
    if pos:
        ax, ay = xy(pos[0], pos[1])
        brg = hdg(marina[0] - ax, marina[1] - ay)
        c = track_id("ESM-CAMCC04", t)
        det["2027-09"].append([iso(t), "ESM-CAMCC04", "rf_contact", c, round(pos[0], 5), round(pos[1], 5), round(pos[2], 0), "", "", "", round(brg, 1), "",
                               902.4, "frequency-hopping burst, data link", 4.1, "", "", "unknown emitter", 0.41, "false"])
        det["2027-09"].append([iso(t + 2), "ESM-CAMCC04", "rf_contact", c, round(pos[0], 5), round(pos[1], 5), round(pos[2], 0), "", "", "", round(brg + 0.2, 1), "",
                               2437.0, "frequency-hopping, 2.4 GHz control link", 3.6, "", "", "unknown emitter", 0.37, "false"])
    else:
        print("  WARNING: CAMCC-04 not airborne in ADS-B at 2027-09-05T06:47Z; run gen_aviation.py first")
    # ---- 3. portable RF detector at the air station: two short bearing-only hits late in the overflight period
    ps5 = by["NASCC-PS-05"]
    for tt, brg in ((ts("2027-09-23T03:41:10Z"), 148.0), (ts("2027-09-25T03:12:35Z"), 212.5)):   # nights of D+8 and D+10
        det["2027-09"].append([iso(tt), "NASCC-PS-05", "rf_contact", track_id("NASCC-PS-05", tt), "", "", "", "", "", "", brg, "", 5785.0, "analog-style video downlink burst",
                               round(float(rh.uniform(3, 11)), 1), "", "", "unknown emitter", 0.33, "false"])
    rq = rng("drone-ps05")
    t_inst = ts(ps5["installed"])
    for day in range(day_of(t_inst), 120):
        for _ in range(int(rq.poisson(1.7))):
            tt = local_ts(day, "00:00") + int(rq.uniform(0, 86400))
            if tt < t_inst + 1800 or tt >= SPAN_END:
                continue
            mhz, sig, cls = [(5785.0, "analog-style video downlink burst", "unknown emitter"), (5805.0, "video bridge, fixed link", "fixed link"), (2437.0, "OFDM, 20 MHz (wireless LAN)", "wireless LAN"),
                             (2462.0, "frequency-hopping, 2.4 GHz control link", "unknown emitter"), (5745.0, "analog-style video downlink burst", "unknown emitter"),
                             (915.0, "frequency-hopping burst, data link", "ISM telemetry"), (2412.0, "OFDM, 40 MHz (wireless LAN)", "wireless LAN")][int(rq.choice(7, p=[0.1, 0.2, 0.28, 0.1, 0.07, 0.1, 0.15]))]
            det[iso(tt)[:7]].append([iso(tt), "NASCC-PS-05", "rf_contact", track_id("NASCC-PS-05", tt), "", "", "", "", "", "", round(float(rq.uniform(0, 360)), 1), "", mhz, sig,
                                     round(float(rq.uniform(1, 90)), 1), "", "", cls, round(float(rq.uniform(0.3, 0.9)), 2), "false"])
    # ---- 4. authorised flights that pass a working sensor
    ra = rng("drone-auth-det")
    for meta, T, X, Y, A in F.tracks:
        t0 = int(T[0])
        for s in S:
            sid = s["sensor_id"]
            if sid.startswith("ESM") or sid == "NASCC-PS-05" or s["lat"] == "":
                continue
            sx, sy = xy(s["lat"], s["lon"])
            if math.hypot(float(X.mean()) - sx, float(Y.mean()) - sy) > s["range_m"] + 9000:
                continue
            if sid.startswith("SENT"):
                d = np.hypot(X - sx, Y - sy)
                m = d < s["range_m"]
                if m.any() and is_on(sid, t0):
                    i0 = int(np.argmax(m))
                    dur = int(m.sum())
                    tt = int(T[i0])
                    det[iso(tt)[:7]].append([iso(tt), sid, "rf_contact", track_id(sid, tt), "", "", "", "", "", "", round(hdg(X[i0] - sx, Y[i0] - sy), 1), "",
                                             2437.0 if "DJI" in meta["model"] else 5745.0, "Remote ID broadcast and control link", dur, meta["rid"] if meta["remote_id"] else "",
                                             meta["aid"], "uas", round(float(ra.uniform(0.85, 0.99)), 2), "false"])
            else:
                rcs = 0.02 if "fixed-wing" not in meta["model"] else 0.05
                radar_track(sid, T, X, Y, A, rcs * float(ra.uniform(0.7, 1.4)), "uas", 0.8, ra, auth=meta["aid"], rid=meta["rid"] if meta["remote_id"] else "", every=4)
    # ---- 5. birds, clutter and false alarms across the whole span
    rb = rng("drone-birds")
    quiet = [("USCG-RDR-R14", ts("2027-09-04T02:45Z"), ts("2027-09-04T06:15Z"))]
    for s in S:
        sid = s["sensor_id"]
        if sid.startswith(("ESM", "SENT")) or sid == "NASCC-PS-05":
            continue
        sx, sy = xy(s["lat"], s["lon"])
        buoy = sid.startswith("USCG")
        for day in range(-30, 120):
            n = int(rb.poisson(5.5 if buoy else 3.2))
            for _ in range(n):
                hour = float(rb.choice([rb.uniform(5.5, 9.0), rb.uniform(17.0, 20.5), rb.uniform(0, 24)], p=[0.4, 0.35, 0.25]))
                t0 = local_ts(day, "00:00") + int(hour * 3600)
                if not is_on(sid, t0) or any(q[0] == sid and q[1] <= t0 <= q[2] for q in quiet):
                    continue
                dur = int(rb.uniform(30, 190))
                ang = rb.uniform(0, 2 * math.pi)
                d0 = rb.uniform(200, s["range_m"] * 0.95)
                x0, y0 = sx + d0 * math.sin(ang), sy + d0 * math.cos(ang)
                crs = rb.uniform(0, 360)
                v = rb.uniform(7, 19)
                T = t0 + np.arange(dur)
                wob = np.cumsum(rb.normal(0, 2.5, dur))
                ux, uy = unit(crs)
                X = x0 + ux * v * np.arange(dur) - uy * wob
                Y = y0 + uy * v * np.arange(dur) + ux * wob
                kind = rb.random()
                if kind < 0.82:
                    A = np.clip(rb.uniform(3, 90) + np.cumsum(rb.normal(0, 0.6, dur)), 1, 200)
                    flock = rb.random() < 0.12
                    rcs = float(rb.uniform(0.06, 0.5)) if flock else float(np.exp(rb.normal(math.log(0.012), 0.6)))
                    radar_track(sid, T, X, Y, A, rcs, "bird" if rb.random() < 0.8 else "unknown", 0.7 if flock else 0.55, rb)
                elif kind < 0.93:
                    A = np.full(dur, rb.uniform(2, 12))
                    radar_track(sid, T, x0 + rb.normal(0, 8, dur), y0 + rb.normal(0, 8, dur), A, float(rb.uniform(0.01, 0.2)), "clutter", 0.45, rb)
                else:
                    A = np.full(dur, rb.uniform(250, 600))
                    radar_track(sid, T, x0 + ux * 55 * np.arange(dur), y0 + uy * 55 * np.arange(dur), A, float(rb.uniform(2, 30)), "aircraft", 0.9, rb)
    # RF nodes: ordinary false alarms
    for s in S:
        if not s["sensor_id"].startswith("SENT"):
            continue
        for day in range(32, 120):
            for _ in range(int(rb.poisson(2.0))):
                t0 = local_ts(day, "00:00") + int(rb.uniform(0, 86400))
                if t0 < ts(s["installed"]):
                    continue
                det[iso(t0)[:7]].append([iso(t0), s["sensor_id"], "rf_contact", track_id(s["sensor_id"], t0), "", "", "", "", "", "", round(float(rb.uniform(0, 360)), 1), "",
                                         float(rb.choice([2412.0, 2437.0, 2462.0, 5745.0, 5805.0])), str(rb.choice(["OFDM, 20 MHz (wireless LAN)", "video bridge, fixed link", "OFDM, 40 MHz (wireless LAN)", "analog-style video downlink burst",
                                                                                                   "frequency-hopping, 2.4 GHz control link", "frequency-hopping burst, data link"], p=[0.42, 0.2, 0.2, 0.06, 0.08, 0.04])),
                                         round(float(rb.uniform(1, 120)), 1), "", "", str(rb.choice(["wireless LAN", "fixed link", "unknown emitter"], p=[0.6, 0.3, 0.1])),
                                         round(float(rb.uniform(0.4, 0.9)), 2), "false"])
    # ---- status rows (hourly)
    cnt = defaultdict(int)
    for m, rows in det.items():
        for r in rows:
            cnt[(r[1], r[0][:13])] += 1
    for s in S:
        sid = s["sensor_id"]
        if sid.startswith("ESM"):
            continue
        t = max(SPAN_START, (ts(s["installed"]) // 3600 + 1) * 3600)
        while t < SPAN_END:
            st, note = "online", ""
            for a, b, why in off.get(sid, []):
                if a <= t < b:
                    st, note = ("offline", why) if "heartbeat" in why or "maintenance" in why else ("degraded", why)
            n = cnt.get((sid, iso(t)[:13]), 0)
            status[iso(t)[:7]].append([iso(t), sid, st, "" if st == "offline" else n, "" if st == "offline" else ("pass" if st == "online" else "warn"), note])
            t += 3600
    # ---- write
    for p in glob.glob(os.path.join(ROOT, "05_other_sources", "drone_detections", "*.csv")):   # this generator's own earlier output
        os.remove(p)
    # track numbers: one running counter per sensor, in order of first detection
    rn = rng("drone-track-numbers")
    start_no = {}
    final = {}
    for key, (sid, t0) in sorted(first_seen.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[0])):
        if sid not in start_no:
            start_no[sid] = 1 if ts(by[sid]["installed"]) > SPAN_START else int(rn.integers(2100, 9400))
        final[key] = f"{sid.split('-')[-1]}-{iso(t0)[2:10].replace('-', '')}-{start_no[sid] % 100000:05d}"
        start_no[sid] += 1
    for rows in det.values():
        for r in rows:
            r[3] = final.get(r[3], r[3])
    tot = 0
    for m in sorted(det):
        rows = sorted(det[m], key=lambda r: (r[0], r[1]))
        tot += write_csv(f"05_other_sources/drone_detections/detections_{m}.csv", DET_HEADER, rows)
    for m in sorted(status):
        write_csv(f"05_other_sources/drone_detections/sensor_status_{m}.csv", ["time_utc", "sensor_id", "status", "detections_last_hour", "self_test", "note"],
                  sorted(status[m], key=lambda r: (r[0], r[1])))
    write_csv("05_other_sources/drone_detections/sensor_sites.csv", ["sensor_id", "name", "sensor_type", "owner", "latitude", "longitude", "nominal_range_m", "reporting_since_utc", "alert_rcs_threshold_m2"],
              [[s["sensor_id"], s["name"], s["kind"], s["owner"], s["lat"], s["lon"], s["range_m"], s["installed"] if ts(s["installed"]) > SPAN_START else iso(SPAN_START), s["alert_rcs_m2"]] for s in S])
    write_csv("05_other_sources/drone_detections/laanc_authorizations.csv",
              ["authorization_id", "authorization_type", "operator_id", "airframe_id", "issued_utc", "start_utc", "end_utc", "center_latitude", "center_longitude", "radius_m",
               "max_altitude_ft_agl", "status"], sorted(F.auth, key=lambda r: r[5]))
    print(f"drone detections: {tot} detection rows, {sum(len(v) for v in status.values())} status rows, {len(F.auth)} authorisations")
    # registry proposal for the sensors this stream needs (the registry belongs to another pass)
    add = {"_about": "Drone-detection sensors used by 05_other_sources/drone_detections. Proposed for sensor_registry.json as key 'drone_detection_sensors'.",
           "drone_detection_sensors": [{"sensor_id": s["sensor_id"], "name": s["name"], "sensor_type": s["kind"], "owner": s["owner"], "latitude": s["lat"] if s["lat"] != "" else None,
                                        "longitude": s["lon"] if s["lon"] != "" else None, "nominal_range_m": s["range_m"], "reporting_since_utc": s["installed"]} for s in S]}
    with open(out_path("06_data_streams/_internal/registry_additions_aviation.json"), "w", encoding="utf-8") as fh:
        json.dump(add, fh, indent=1)
    return S


def build_sightings(S):
    """Logged visual reports. Six nights of lights over the air station and depot between D+1 and
    D+10 (the perimeter sensors were down), wrapped in the ordinary reports any city generates."""
    r = rng("drone-sightings")
    rows = []
    n = 0
    nights = [1, 2, 4, 6, 8, 10]                              # the same nights as the calls and posts about lights over the base

    def obs_point(c, spread):
        for _ in range(30):
            p = G.roads.random_point(r, box=(c[1] - spread, c[0] - spread, c[1] + spread, c[0] + spread), classes=("local", "arterial", "secondary"))
            if p and G.is_land(p[0], p[1]):
                return p
        return (c[0], c[1], "")

    desk = ["NAS Corpus Christi security desk", "Corpus Christi police non-emergency line", "FAA Flight Standards District Office report form", "Nueces County sheriff front desk",
            "Port of Corpus Christi police"]
    nas = PT["nas"]
    for d in nights:
        k = int(r.integers(3, 7))
        base = local_ts(d, "21:20") + int(r.uniform(0, 3.5 * 3600))
        for i in range(k):
            t = base + int(r.uniform(0, 5400))
            from_base = i < 2
            if from_base:
                la, lo, road = nas[0] + r.normal(0, 0.004), nas[1] + r.normal(0, 0.004), ""
                d_, la, lo, road, _c = G.roads.nearest(la, lo)
                who, recv = "security patrol", desk[0]
                txt = str(r.choice([
                    "Patrol reports two to three steady white lights moving slowly over the flight line, no engine noise heard over generators. Perimeter detection system still out of service.",
                    "Watch stander observed lights hovering near the hangar line then moving off to the south-east. No aircraft scheduled. Unable to confirm with sensors (offline).",
                    "Gate sentry reports a faint buzzing and one blinking light crossing the fence line toward the depot, lost sight after about four minutes.",
                    "Roving patrol saw a small light hold position over the ramp, then climb and depart over the water. No transponder traffic reported by the tower."]))
            else:
                la, lo, road = obs_point((27.672 + r.normal(0, 0.006), -97.297 + r.normal(0, 0.008)), 0.012)
                who, recv = "resident", str(r.choice(desk[1:4]))
                txt = str(r.choice([
                    "Caller in Flour Bluff says several lights were hovering over the Navy base for about ten minutes; took a phone video.",
                    "Resident reports lights in a line over the air station, not moving like helicopters, no sound.",
                    "Caller saw two lights above the base that stayed still, then moved quickly toward the Laguna Madre.",
                    "Neighbours watched three lights over the depot side of the base around the same time as last night.",
                    "Caller reports a drone-like buzzing and a red light over the base fence; power still out on the street so the sky is very dark."]))
            n += 1
            brg = hdg(*(np.array(xy(*nas)) - np.array(xy(la, lo))))
            rows.append(["", iso(t), recv, who, round(la, 5), round(lo, 5), road, round(brg + r.normal(0, 8), 0) % 360, int(r.integers(2, 4) if not from_base or r.random() < 0.6 else 1),
                         int(r.uniform(3, 14)), txt, "logged; no sensor confirmation" if d < 6 else "logged; forwarded to investigators"])
    # ordinary reports through the span: day and night, before and after the storm; most are explained, some never are
    day_txt = ["Caller reports a drone over the neighbourhood taking pictures of roofs.", "Resident asks whether the drone over the shoreline is allowed.",
               "Caller saw a small aircraft circling low for several minutes.", "Report of a drone near the bridge during the morning.",
               "Resident reports a drone over the debris site.", "Caller reports a drone hovering near a school field.", "Report of a drone following the power line right-of-way."]
    day_res = ["resolved: matched an authorised survey flight", "resolved: matched an authorised survey flight", "resolved: news or survey aircraft on ADS-B",
               "resolved: matched an authorised inspection flight", "resolved: matched an authorised survey flight", "resolved: hobby flier contacted, advised of rules",
               "resolved: matched an authorised inspection flight"]
    night_txt = ["Caller reports a bright light low in the western sky after sunset, not moving.", "Resident reports blinking lights moving slowly north to south, high up.",
                 "Caller says a light has been hovering over the bay for twenty minutes.", "Report of a buzzing sound and a small light over the neighbourhood after dark.",
                 "Caller reports two lights in a line over the water, no sound.", "Resident reports a steady light over the refinery area before dawn."]
    night_res = ["resolved: planet low on the horizon", "resolved: aircraft on ADS-B", "resolved: planet low on the horizon", "logged; no sensor confirmation",
                 "resolved: aircraft on ADS-B", "logged; no sensor confirmation", "logged; forwarded to investigators", "no further action"]
    for day in range(-30, 120):
        lam = 0.3 if day < 1 else (0.9 if 6 <= day <= 14 else (0.35 if day < 60 else 0.2))
        if -2 <= day <= 0:
            lam = 0.0
        for _ in range(int(r.poisson(lam))):
            night = r.random() < 0.35
            hour = float(r.choice([r.uniform(19.8, 24.0), r.uniform(0.0, 6.2)])) if night else float(r.uniform(7.2, 18.8))
            t = local_ts(day, "00:00") + int(hour * 3600)
            names = ["flour_bluff", "north_beach", "downtown", "calallen", "southside", "port_aransas", "portland", "molina", "hillcrest", "padre", "annaville", "rockport"]
            if night and 1 <= day <= 11:
                names = [q for q in names if q != "flour_bluff"]   # reports near the base on those nights are the ones above
            c = PT[str(r.choice(names))]
            la, lo, road = obs_point(c, 0.012)
            if night:
                txt = night_txt[int(r.integers(0, len(night_txt)))]
                res = night_res[int(r.choice(len(night_res), p=[0.24, 0.24, 0.1, 0.16, 0.1, 0.06, 0.04, 0.06]))]
            else:
                i = int(r.integers(0, len(day_txt)))
                txt, res = day_txt[i], (day_res[i] if r.random() < 0.85 else str(r.choice(["no further action", "logged; no sensor confirmation"])))
            rows.append(["", iso(t), str(r.choice(desk[1:])), "resident", round(la, 5), round(lo, 5), road, int(r.uniform(0, 360)), int(r.choice([1, 1, 1, 2, 3])),
                         int(r.uniform(1, 20)), txt, res])
    rows.sort(key=lambda q: q[1])
    for i, q in enumerate(rows):                              # report numbers are issued as reports come in
        q[0] = f"SR-{local_dt(ts(q[1])):%y%m%d}-{i + 1:04d}"
    write_csv("05_other_sources/drone_detections/sighting_reports.csv",
              ["report_id", "time_utc", "received_by", "reporter_type", "observer_latitude", "observer_longitude", "observer_street", "direction_deg", "objects_seen",
               "duration_min", "description", "disposition"], rows)
    print(f"sighting reports: {len(rows)}")


def main():
    global G
    G = geo_handle()
    F = Flights()
    build_flights(F)
    write_flights(F)
    S = build_detections(F)
    build_sightings(S)
    rules = {"sources": [
        {"name": "Drone telemetry launch and flight positions", "glob": "05_other_sources/drone_video/drone_telemetry_*.csv", "lat": "latitude", "lon": "longitude", "rule": "on_land_or_air", "id": "flight_id"},
        {"name": "Drone detection sensor sites (land)", "glob": "05_other_sources/drone_detections/sensor_sites.csv", "lat": "latitude", "lon": "longitude", "rule": "land_fixed",
         "id": "sensor_id", "allow_missing": True, "where": ["sensor_type", ["RF direction finder and short-range radar", "portable RF detector (bearing only)", "RF sensing and direction finding node"]]},
        {"name": "Drone detection radar buoys (water)", "glob": "05_other_sources/drone_detections/sensor_sites.csv", "lat": "latitude", "lon": "longitude", "rule": "water_fixed",
         "id": "sensor_id", "allow_missing": True, "where": ["sensor_type", "X-band surface-search radar, raw plot archive"]},
        {"name": "Drone sighting observers", "glob": "05_other_sources/drone_detections/sighting_reports.csv", "lat": "observer_latitude", "lon": "observer_longitude", "rule": "land_fixed", "id": "report_id"},
    ]}
    with open(out_path("99_reference/geo/position_rules.d/aviation.json"), "w", encoding="utf-8") as fh:
        json.dump(rules, fh, indent=1)


if __name__ == "__main__":
    main()
