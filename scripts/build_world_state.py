"""Build the shared state timeline (the hour-by-hour world state every data generator reads).

Time is an integer hour t relative to D0 00:00Z (landfall is t = 6, 06:00Z on Sept. 14, 2027).
Range: day -60 00:00Z to day 119 23:00Z (4,320 hours).

Outputs in 09_shared_state_timeline/data/:
  variables.json      catalog: id, label, group, kind, unit, visibility, lanes, threads, states/colors, source, assumption
  segments.json       categorical and flag variables as [start_t, end_t) intervals
  series_hourly.json  numeric variables as hourly arrays (also series_hourly.csv)
  events.json         ground-truth events (MSEL) and public facts, timed to the hour
  storm_track.json    6-hourly storm positions and intensity
  state_daily.csv     every variable at 18:00Z (about 1 p.m. local) each day, for quick lookup
Deterministic: same inputs, same outputs (fixed seed).
Usage: python scripts/build_world_state.py
"""
import sys, os, json, math, random, csv, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, path

T0, T1 = -60 * 24, 119 * 24 + 23          # inclusive hour range
N = T1 - T0 + 1
OUT = "09_shared_state_timeline/data"
rng = random.Random(20270914)

def H(day, hh=0, mm=0):
    return day * 24 + hh + mm / 60.0

def idx(t):
    return int(round(t)) - T0

# ---------------------------------------------------------------- helpers
def keyframes(points, base=None):
    """Piecewise-linear series from [(t, value)], flat before first and after last."""
    pts = sorted(points)
    arr = []
    for i in range(N):
        t = T0 + i
        if t <= pts[0][0]:
            v = pts[0][1]
        elif t >= pts[-1][0]:
            v = pts[-1][1]
        else:
            for (ta, va), (tb, vb) in zip(pts, pts[1:]):
                if ta <= t <= tb:
                    v = va + (vb - va) * (t - ta) / (tb - ta) if tb > ta else vb
                    break
        arr.append(v)
    return arr

def noise(arr, amp, smooth=12, seed=0):
    r = random.Random(seed)
    raw = [r.uniform(-1, 1) for _ in range(N + smooth)]
    sm = [sum(raw[i:i + smooth]) / smooth for i in range(N)]
    return [a + amp * s * 2.2 for a, s in zip(arr, sm)]

def clamp(arr, lo=None, hi=None):
    return [min(hi, v) if hi is not None else v for v in [max(lo, v) if lo is not None else v for v in arr]]

def segs(changes):
    """[(t, value, note)] change points -> [[start, end, value, note]] covering the full range."""
    ch = sorted(changes, key=lambda c: c[0])
    out = []
    for i, c in enumerate(ch):
        start = max(T0, int(round(c[0])))
        end = int(round(ch[i + 1][0])) if i + 1 < len(ch) else T1 + 1
        if end > start:
            out.append([start, end, c[1], c[2] if len(c) > 2 else ""])
    return out

VARS, SEGS, SERIES = [], {}, {}

def var(**kw):
    kw.setdefault("lanes", ["C", "D", "I"]); kw.setdefault("threads", []); kw.setdefault("assumption", False)
    kw.setdefault("visibility", "public"); kw.setdefault("unit", ""); kw.setdefault("description", "")
    VARS.append(kw)
    return kw["id"]

def state(vid, changes, **kw):
    var(id=vid, kind="state", **kw); SEGS[vid] = segs(changes)

def number(vid, arr, **kw):
    var(id=vid, kind="number", **kw); SERIES[vid] = [round(v, 2) for v in arr]

C = {  # semantic palette (light, dark handled in viewer)
    "ok": "#3f8f6b", "calm": "#7a8a99", "watch": "#d9a227", "warn": "#e07a1f", "severe": "#c8402f",
    "closed": "#8f1d2c", "partial": "#e8a33d", "restore": "#2a9d8f", "info": "#4a78c2", "hidden": "#7b5ea7",
    "hidden2": "#a35a9b", "dark": "#3a3f4b", "none": "#c9cfd6", "good": "#5aa469", "public": "#2f6fb0"}

# ---------------------------------------------------------------- storm
track = [  # (t, lat, lon, wind_kt, stage)
    (H(-12), 14.8, 79.0, 25, "Tropical wave"), (H(-11), 15.9, 80.8, 30, "Tropical wave"),
    (H(-10, 6), 17.0, 82.5, 40, "Tropical storm"), (H(-9), 18.0, 84.5, 50, "Tropical storm"),
    (H(-8), 19.3, 86.5, 60, "Tropical storm"), (H(-7, 12), 20.3, 88.5, 45, "Tropical storm"),
    (H(-6, 12), 21.3, 91.0, 70, "Hurricane Cat 1"), (H(-5), 22.0, 92.3, 75, "Hurricane Cat 1"),
    (H(-4), 23.2, 93.6, 85, "Hurricane Cat 1"), (H(-3), 24.3, 94.8, 90, "Hurricane Cat 2"),
    (H(-2), 25.4, 95.7, 95, "Hurricane Cat 2"), (H(-1), 26.4, 96.4, 100, "Hurricane Cat 3"),
    (H(-1, 12), 27.0, 96.75, 105, "Hurricane Cat 3"), (H(0, 6), 27.75, 97.13, 110, "Hurricane Cat 3"),
    (H(0, 18), 28.2, 97.9, 60, "Tropical storm"), (H(1, 6), 28.8, 98.7, 30, "Tropical depression"),
    (H(1, 18), 29.5, 99.4, 20, "Remnant low")]
def stage_for(w):
    return "Hurricane Cat 3" if w >= 96 else "Hurricane Cat 2" if w >= 83 else "Hurricane Cat 1" if w >= 64 else "Tropical storm" if w >= 34 else "Tropical depression" if w >= 25 else "Remnant low"
track6 = []
t = H(-12)
while t <= H(1, 18):
    for (ta, la, lo, wa, sa), (tb, lb, lob, wb, sb) in zip(track, track[1:]):
        if ta <= t <= tb:
            f = (t - ta) / (tb - ta)
            w = wa + (wb - wa) * f
            track6.append({"t": int(t), "lat": round(la + (lb - la) * f, 2), "lon": round(lo + (lob - lo) * f, 2),
                           "wind_kt": round(w), "stage": stage_for(w) if t > H(-10, 5) else "Tropical wave"})
            break
    t += 6
track6 = [p for p in track6 if p["t"] != int(H(0, 6))]
track6.append({"t": int(H(0, 6)), "lat": 27.75, "lon": 97.13, "wind_kt": 110, "stage": "Hurricane Cat 3", "landfall": True})
track6.sort(key=lambda p: p["t"])
for p in track6:
    if p["lon"] > 0: p["lon"] = -p["lon"]

wind = [0.0] * N
for i in range(N):
    t = T0 + i
    if H(-12) <= t <= H(1, 18):
        for (ta, la, lo, wa, sa), (tb, lb, lob, wb, sb) in zip(track, track[1:]):
            if ta <= t <= tb:
                wind[i] = wa + (wb - wa) * (t - ta) / (tb - ta); break
number("storm_max_wind_kt", wind, label="Storm maximum wind", group="Storm & weather", unit="kt", source="Scenario track (EVT-0202, EVT-0301)", fmt="0",
       scale=[0, 120], description="Maximum sustained wind of Rafael along its track; 0 when no system exists.")
stage_changes = [(T0, "No system"), (H(-12), "Tropical wave"), (H(-10, 6), "Tropical storm"), (H(-6, 12), "Hurricane Cat 1"),
                 (H(-3), "Hurricane Cat 2"), (H(-1), "Hurricane Cat 3"), (H(0, 12), "Tropical storm"), (H(1, 4), "Tropical depression"),
                 (H(1, 18), "Remnant low"), (H(2, 12), "No system")]
state("storm_stage", stage_changes, label="Storm stage", group="Storm & weather", source="EVT-0202, EVT-0301; PUB-015, PUB-017, PUB-022",
      states={"No system": C["none"], "Tropical wave": "#9fb7c9", "Tropical storm": C["watch"], "Hurricane Cat 1": C["warn"],
              "Hurricane Cat 2": "#d4552a", "Hurricane Cat 3": C["severe"], "Tropical depression": "#c9b458", "Remnant low": "#b8c2cc"})
state("nws_advisory", [(T0, "None"), (H(-21, 15), "Active-season outlook"), (H(-10, 15), "Storm forms (Caribbean)"), (H(-5, 15), "Cone covers Corpus Christi"),
                       (H(-3, 17), "Hurricane watch"), (H(-2, 20), "Hurricane warning"), (H(0, 21), "Warnings lifted"), (H(2), "None")],
      label="NWS advisories (local)", group="Storm & weather", source="PUB-013, PUB-015, PUB-018, PUB-101, PUB-102, PUB-022",
      states={"None": C["none"], "Active-season outlook": "#b9c6d3", "Storm forms (Caribbean)": "#9fb7c9", "Cone covers Corpus Christi": C["watch"],
              "Hurricane watch": C["warn"], "Hurricane warning": C["severe"], "Warnings lifted": C["restore"]})
# distance to Corpus Christi
CC = (27.80, -97.40)
def hav(a, b):
    r = 6371; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    return 2 * r * math.asin(math.sqrt(math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2))
dist = []
for i in range(N):
    t = T0 + i
    if H(-12) <= t <= H(1, 18):
        for (ta, la, lo, wa, sa), (tb, lb, lob, wb, sb) in zip(track, track[1:]):
            if ta <= t <= tb:
                f = (t - ta) / (tb - ta); pos = (la + (lb - la) * f, -(lo + (lob - lo) * f) if lo > 0 else lo + (lob - lo) * f)
                dist.append(hav(pos, CC)); break
    else:
        dist.append(2500.0)
number("storm_distance_km", [min(d, 2500) for d in dist], label="Distance from Corpus Christi", group="Storm & weather", unit="km", fmt="0",
       scale=[0, 2500], invert=True, source="Derived from track", description="Great-circle distance from the storm center to downtown Corpus Christi (capped at 2,500 km).")
tide = [0.6 * math.sin(2 * math.pi * (T0 + i) / 24.8) + 0.25 * math.sin(2 * math.pi * (T0 + i) / 12.4) + 1.0 for i in range(N)]
surge = keyframes([(H(-2), 0), (H(-1, 12), 1.5), (H(-1, 22), 4.0), (H(0, 4), 9.5), (H(0, 7), 11.0), (H(0, 10), 8.0), (H(0, 20), 3.5), (H(1, 12), 1.2), (H(2, 12), 0.2), (H(3), 0)])
number("bay_water_level_ft", [a + b for a, b in zip(tide, surge)], label="Bay water level (tide gauge)", group="Storm & weather", unit="ft", fmt="0.0",
       scale=[0, 12], source="EVT-0301 (3.4 m surge); PUB-023", lanes=["C", "D", "I"], description="Water level above datum at the NOAA tide gauge on Corpus Christi Bay (GAUGE-14). The gauge goes offline from landfall to D+5 in the rendering rules, but the true level is kept here.")
rain = [0.0] * N
for i in range(N):
    t = T0 + i
    if rng.random() < 0.004 and t < H(-12): rain[i] = rng.uniform(0.1, 0.8)
rain_k = keyframes([(H(-8), 0), (H(-7, 6), 0.35), (H(-6, 12), 0.25), (H(-5, 12), 0), (H(-1, 6), 0), (H(-1, 18), 0.6), (H(0, 4), 1.8), (H(0, 10), 1.2), (H(0, 22), 0.3), (H(1, 12), 0)])
number("rain_rate_in_hr", [max(a, b) for a, b in zip(rain, rain_k)], label="Rain rate (Corpus Christi)", group="Storm & weather", unit="in/hr", fmt="0.00",
       scale=[0, 2], source="EVT-0203 (moisture plume), EVT-0301; PUB-016", assumption=True)
river = keyframes([(T0, 3.0), (H(-8), 3.0), (H(-7, 12), 5.5), (H(-6), 8.6), (H(-4), 7.0), (H(-1), 6.0), (H(0, 12), 11.0), (H(2), 14.0), (H(5), 10.5), (H(12), 5.0), (H(25), 3.2)])
number("nueces_river_stage_ft", noise(river, 0.15, seed=3), label="Nueces River stage at Calallen", group="Storm & weather", unit="ft", fmt="0.0",
       scale=[0, 15], source="EVT-0203; PUB-016", assumption=True, lanes=["C"])

# ---------------------------------------------------------------- port and maritime
state("port_condition", [(T0, "Normal"), (H(-3, 16), "X-Ray"), (H(-2, 17), "Yankee"), (H(-1, 12), "Zulu"), (H(1), "Post-storm closure"),
                         (H(30, 15), "Partial reopening"), (H(44, 6, 10), "Security closure"), (H(58, 15), "Open")],
      label="Coast Guard port condition", group="Port & maritime", source="PUB-020, PUB-107, PUB-108, PUB-058, PUB-067, PUB-079",
      states={"Normal": C["ok"], "X-Ray": C["watch"], "Yankee": C["warn"], "Zulu": C["severe"], "Post-storm closure": C["closed"],
              "Partial reopening": C["partial"], "Security closure": "#6d1222", "Open": C["restore"]})
state("channel_status", [(T0, "Open"), (H(-2, 17), "Closed to inbound"), (H(-1, 12), "Closed to all"), (H(30, 15), "Open (inner channel restricted)"),
                         (H(44, 4), "Open"), (H(44, 6, 10), "Closed (explosive device)"), (H(58, 15), "Open")],
      label="Ship channel", group="Port & maritime", source="PUB-107, PUB-108, PUB-058, PUB-066, PUB-067, PUB-079",
      states={"Open": C["ok"], "Closed to inbound": C["warn"], "Closed to all": C["closed"], "Open (inner channel restricted)": C["partial"],
              "Closed (explosive device)": "#6d1222"})
anch = keyframes([(T0, 9), (H(-3, 12), 10), (H(-2, 17), 12), (H(-2, 23), 14), (H(-1, 12), 14), (H(-1, 20), 0), (H(3, 10), 0), (H(3, 22), 14),
                  (H(15), 20), (H(29), 26), (H(30, 15), 26), (H(38), 16), (H(44), 12), (H(44, 12), 15), (H(52), 21), (H(58, 15), 22), (H(66), 12), (H(80), 10), (H(119, 23), 10)])
anch = [round(v) for v in noise(anch, 0.6, smooth=24, seed=5)]
for a, b, v in [(H(-2, 22), H(-1, 12), 14), (H(-1, 20), H(3, 10), 0)]:
    for i in range(idx(a), idx(b) + 1): anch[i] = v
number("vessels_at_anchorage", anch, label="Vessels at offshore anchorage", group="Port & maritime", unit="ships", fmt="0", scale=[0, 30],
       source="PUB-107 (14 on Sept. 12), PUB-108 (to sea), PUB-109 (return), PUB-058", description="Ships waiting at the anchorage east of Port Aransas. Exactly 14 from the Yankee closure until Zulu sends them to sea; back from Sept. 17.")
state("crude_exports", [(T0, "Normal"), (H(-3, 16), "Winding down"), (H(-2, 17), "Halted"), (H(30, 15), "Limited"), (H(44, 6, 10), "Halted"),
                        (H(58, 15), "Resuming"), (H(70), "Normal")],
      label="Crude exports", group="Port & maritime", source="PUB-020, PUB-107, PUB-073, PUB-079",
      states={"Normal": C["ok"], "Winding down": C["watch"], "Halted": C["closed"], "Limited": C["partial"], "Resuming": C["restore"]})
exp = keyframes([(T0, 100), (H(-3, 16), 100), (H(-2, 17), 15), (H(-2, 22), 0), (H(30, 15), 0), (H(34), 35), (H(43), 55), (H(44, 6), 55), (H(44, 7), 0),
                 (H(58, 15), 0), (H(62), 70), (H(70), 95), (H(119, 23), 100)])
number("export_activity_pct", clamp(noise(exp, 2, seed=7), 0, 110), label="Export loading activity", group="Port & maritime", unit="% of normal", fmt="0",
       scale=[0, 110], assumption=True, source="Derived from channel status", description="Scenario index of tanker loading at the port (100 = normal). Not a published number.")
state("relief_ship_gulf_provider", [(T0, "Not yet booked"), (H(-5, 15), "Booked, inbound"), (H(-2, 22), "Waiting at anchorage"), (H(-1, 14), "At sea (riding out storm)"),
                                   (H(3, 18), "Waiting at anchorage"), (H(33, 14), "Berthed, unloading"), (H(35, 18), "Departed")],
      label="MV Gulf Provider (40 relief containers)", group="Port & maritime", source="EVT-0204, EVT-0401; PUB-018, PUB-059",
      states={"Not yet booked": C["none"], "Booked, inbound": C["info"], "Waiting at anchorage": C["watch"], "At sea (riding out storm)": C["warn"],
              "Berthed, unloading": C["restore"], "Departed": C["calm"]}, lanes=["C", "D"])
state("brigade_outload", [(T0, "Not scheduled"), (H(-48, 15), "Planned (late summer)"), (H(-3, 16), "Postponed (storm)"), (H(44, 6, 10), "Delayed again (channel closed)"),
                          (H(59, 14), "Loading"), (H(60, 18), "Sailing"), (H(64, 20), "Departed")],
      label="Fort Hood brigade outload", group="Port & maritime", source="PUB-007, PUB-020, PUB-068, PUB-080; EVT-0409",
      states={"Not scheduled": C["none"], "Planned (late summer)": C["info"], "Postponed (storm)": C["watch"], "Delayed again (channel closed)": C["warn"],
              "Loading": C["partial"], "Sailing": C["restore"], "Departed": C["calm"]}, lanes=["D", "I"])

# ---------------------------------------------------------------- water and power
state("onstevens_power_feeds", [(T0, "Both feeds up"), (H(0, 9), "Both feeds down"), (H(3, 14), "One feed restored"), (H(12, 16), "Both feeds up")],
      label="O.N. Stevens power feeds", group="Water & power", source="EVT-0302; PUB-025", assumption=True, lanes=["C"],
      states={"Both feeds up": C["ok"], "Both feeds down": C["closed"], "One feed restored": C["partial"]},
      description="Restoration times are builder assumptions (not in the public record).")
cap = keyframes([(T0, 100), (H(0, 9), 100), (H(0, 10), 0), (H(1, 6), 35), (H(3, 14), 50), (H(10), 62), (H(36, 18), 62), (H(38, 16), 100)])
number("water_capacity_pct", noise(cap, 0.8, seed=11), label="Water plant pumping capacity", group="Water & power", unit="%", fmt="0", scale=[0, 100],
       source="EVT-0302, EVT-0406", assumption=True, lanes=["C"])
vib = keyframes([(T0, 2.4), (H(-55), 2.5), (H(0, 8), 4.3), (H(0, 9), 9.8), (H(0, 10), 0), (H(38, 15), 0), (H(38, 16), 1.8), (H(119, 23), 1.9)])
number("pump_p2_vibration_mm_s", clamp(noise(vib, 0.08, seed=13), 0), label="Pump P-2 vibration (EQP-1102)", group="Water & power", unit="mm/s", fmt="0.0",
       scale=[0, 10], visibility="internal", source="EVT-0102, EVT-0302, EVT-0406", lanes=["C"], description="Equipment telemetry ground truth. 0 while the pump is failed.")
state("boil_water_notice", [(T0, "No notice"), (H(4, 15), "Boil-water notice"), (H(39, 18), "No notice")],
      label="Citywide boil-water notice", group="Water & power", source="EVT-0310, EVT-0406; PUB-039, PUB-063",
      states={"No notice": C["ok"], "Boil-water notice": C["severe"]})
state("water_pressure", [(T0, "Normal"), (H(0, 9), "Low citywide"), (H(38, 16), "Normal")], label="Water pressure", group="Water & power",
      source="PUB-025", states={"Normal": C["ok"], "Low citywide": C["warn"]}, lanes=["C"])
out = keyframes([(T0, 0), (H(-1, 20), 0), (H(0, 3), 20), (H(0, 7), 74), (H(2), 52), (H(5), 26), (H(10), 11), (H(20), 3), (H(30), 0)])
number("power_outage_pct", clamp(noise(out, 0.6, seed=17), 0, 100), label="Customers without power (Coastal Bend)", group="Water & power", unit="%", fmt="0",
       scale=[0, 80], assumption=True, source="Scenario assumption (no public figure)", lanes=["C", "D"])
state("bridges", [(T0, "Open"), (H(-1, 23), "Closed (wind)"), (H(3, 18), "Open")], label="Harbor Bridge and Nueces Bay Causeway", group="Water & power",
      source="EVT-0304; PUB-027, PUB-036", states={"Open": C["ok"], "Closed (wind)": C["closed"]})

# ---------------------------------------------------------------- spill and environment
oil = keyframes([(H(0, 4), 0), (H(0, 5, 30), 9000)])
number("oil_released_bbl", oil, label="Oil released (cumulative)", group="Spill & environment", unit="bbl", fmt="0", scale=[0, 9000],
       source="EVT-0313; PUB-029", threads=["T6"], description="Valves opened 04:00Z (11 p.m. Monday local), closed by 05:30Z.")
slick = keyframes([(H(0, 4), 0), (H(0, 6), 2), (H(0, 18), 40), (H(1, 12), 70), (H(2, 12), 85), (H(10), 62), (H(20), 30), (H(30), 12), (H(44), 3), (H(60), 0.5), (H(75), 0)])
number("oil_slick_km2", clamp(noise(slick, 0.8, seed=19), 0), label="Oil slick extent", group="Spill & environment", unit="km²", fmt="0", scale=[0, 90],
       source="EVT-0314; PUB-030 (about 33 sq mi)", threads=["T6"])
hc = keyframes([(T0, 2), (H(0, 4), 2), (H(0, 8), 88), (H(2), 70), (H(10), 40), (H(30), 12), (H(60), 4), (H(119, 23), 3)])
number("water_hydrocarbon_index", clamp(noise(hc, 1.2, seed=23), 0, 100), label="Hydrocarbon reading (sondes WQ-01 to 06)", group="Spill & environment", unit="index",
       fmt="0", scale=[0, 100], visibility="internal", source="EVT-0314; rendering rules", threads=["T6"], lanes=["C"])
state("spill_response", [(T0, "None"), (H(0, 7), "Spill reported"), (H(1, 15), "Unified Command (on hold, wind)"), (H(2, 14), "Active cleanup"),
                         (H(44, 15), "Monitoring")], label="Spill response", group="Spill & environment", source="PUB-024, PUB-029, PUB-031, PUB-066",
      threads=["T6"], states={"None": C["none"], "Spill reported": C["severe"], "Unified Command (on hold, wind)": C["warn"], "Active cleanup": C["partial"], "Monitoring": C["restore"]})
state("fishing_closure", [(T0, "Open"), (H(4, 16), "Closed (Parks and Wildlife)"), (H(115, 15), "Partly reopened")], label="Bay fishing", group="Spill & environment",
      source="PUB-040, PUB-099", threads=["T6"], lanes=["C"], states={"Open": C["ok"], "Closed (Parks and Wildlife)": C["closed"], "Partly reopened": C["partial"]})
state("shellfish_closure", [(T0, "Open"), (H(4, 16), "Closed (State Health Services)")], label="Shellfish harvesting", group="Spill & environment",
      source="PUB-040", threads=["T6"], lanes=["C"], states={"Open": C["ok"], "Closed (State Health Services)": C["closed"]})
state("spill_claims_process", [(T0, "None"), (H(12, 15), "Property claims open"), (H(63, 15), "Lost-income claims open")], label="Spill claims center",
      group="Spill & environment", source="PUB-106, PUB-082", threads=["T6"], lanes=["C"],
      states={"None": C["none"], "Property claims open": C["info"], "Lost-income claims open": C["public"]})
sc = keyframes([(H(12, 15), 0), (H(20), 600), (H(63), 1500), (H(80), 3000), (H(115), 4200), (H(119, 23), 4350)])
number("spill_claims_cumulative", [round(v) for v in sc], label="Spill damage claims (cumulative)", group="Spill & environment", unit="claims", fmt="0",
       scale=[0, 4500], source="EVT-0508; PUB-099 (about 4,200)", threads=["T6"], lanes=["C"])

# ---------------------------------------------------------------- health and emergency
dow = [1.0, 0.97, 0.98, 1.0, 1.06, 1.12, 1.05]
base911 = []
for i in range(N):
    t = T0 + i; d = math.floor(t / 24)
    wd = (datetime.date(2027, 9, 14) + datetime.timedelta(days=d)).weekday()
    base911.append(310 * dow[wd])
surge911 = keyframes([(H(-3), 1.0), (H(-2), 1.15), (H(-1), 1.4), (H(0), 9.35), (H(1), 8.3), (H(2), 5.8), (H(4), 3.2), (H(7), 1.95), (H(14), 1.3), (H(30), 1.06), (H(44), 1.06), (H(45), 1.15), (H(48), 1.04), (H(60), 1.0)])
calls = [b * s for b, s in zip(base911, surge911)]
number("calls_911_per_day", noise(calls, 6, smooth=24, seed=29), label="911 calls (daily rate)", group="Health & emergency", unit="calls/day", fmt="0",
       scale=[0, 3000], source="EVT-0101, EVT-0303; PUB-026 (2,900 peak)", lanes=["C"], description="Daily call rate expressed at hourly resolution. Peak about 2,900 on landfall day; baseline about 310.")
gi = keyframes([(T0, 1.0), (H(5), 1.0), (H(6), 1.6), (H(8), 2.8), (H(11), 2.8), (H(14), 2.0), (H(20), 1.3), (H(30), 1.05), (H(40), 1.0)])
number("er_stomach_illness_x", noise(gi, 0.03, seed=31), label="ER stomach-illness visits (x normal)", group="Health & emergency", unit="x", fmt="0.00",
       scale=[0, 3], source="EVT-0310; PUB-046 (+180%)", lanes=["C"])
resp = keyframes([(T0, 1.0), (H(2, 12), 1.0), (H(3, 12), 1.45), (H(5), 1.6), (H(14), 1.45), (H(21), 1.12), (H(30), 1.0)])
number("er_respiratory_x", noise(resp, 0.02, seed=37), label="ER respiratory/skin near shorelines (x normal)", group="Health & emergency", unit="x", fmt="0.00",
       scale=[0, 2], source="EVT-0317; PUB-038", threads=["T6"], lanes=["C"])
low = keyframes([(T0, 1.0), (H(0), 1.0), (H(2), 1.7), (H(14), 1.6), (H(30), 1.45), (H(45), 1.4), (H(60), 1.28), (H(90), 1.12), (H(119, 23), 1.06)])
number("er_low_income_tracts_x", noise(low, 0.02, seed=41), label="ER visits, low-income surge-zone tracts (x normal)", group="Health & emergency", unit="x",
       fmt="0.00", scale=[0, 2], source="EVT-0408; PUB-069 (+40% on Oct. 29)", threads=["T5"], lanes=["C"])
ww = keyframes([(T0, 1.0), (H(4), 1.0), (H(5), 3.0), (H(9), 8.0), (H(14), 5.0), (H(30), 1.8), (H(45), 1.0)])
number("wastewater_norovirus_x", noise(ww, 0.1, seed=43), label="Wastewater norovirus signal (x baseline)", group="Health & emergency", unit="x", fmt="0.0",
       scale=[0, 9], source="EVT-0310; PUB-044", lanes=["C"])
sh = keyframes([(H(-3), 0), (H(-2, 14), 6), (H(0), 9), (H(7), 4), (H(21), 1), (H(35), 0)])
number("shelters_open", [round(v) for v in sh], label="Shelters open", group="Health & emergency", unit="shelters", fmt="0", scale=[0, 10],
       assumption=True, source="PUB-021 (shelters open inland); counts assumed", lanes=["C"])

# ---------------------------------------------------------------- military
state("nas_cc_aircraft", [(T0, "Home station"), (H(-4, 14), "Evacuated to NAS JRB Fort Worth"), (H(6, 14), "Returning"), (H(8, 20), "Home station")],
      label="NAS Corpus Christi aircraft", group="Military", source="EVT-0205; PUB-019, PUB-045", lanes=["D", "C"],
      states={"Home station": C["ok"], "Evacuated to NAS JRB Fort Worth": C["info"], "Returning": C["restore"]})
state("army_depot", [(T0, "Normal production"), (H(-4, 15), "Work halted, aircraft secured"), (H(0, 6), "Storm damage, stand-by"), (H(12), "Partial work"),
                     (H(47, 15), "Full production")], label="Corpus Christi Army Depot", group="Military", source="EVT-0206, EVT-0307, EVT-0409; PUB-035, PUB-075",
      lanes=["D"], states={"Normal production": C["ok"], "Work halted, aircraft secured": C["watch"], "Storm damage, stand-by": C["closed"], "Partial work": C["partial"], "Full production": C["restore"]})
fl = [0.0] * N
for d in range(34, 44):          # 40 landings: 26 military C-17 + 14 civil charters, 4 a day for 10 days
    for hh in (13, 15, 18, 21):
        fl[idx(H(d, hh))] = 1
fl_total = sum(fl)
number("relief_flights", fl, label="Relief flights landing (per hour)", group="Military", unit="flights", fmt="0", scale=[0, 1],
       source="EVT-0405; PUB-060 (26 military + 14 civil)", lanes=["D", "C"], description="One mark per landing; 40 between Oct. 18 and Oct. 27.")
rd = keyframes([(T0, 92), (H(-4, 14), 92), (H(-4, 16), 74), (H(8, 20), 84), (H(40, 12), 84), (H(40, 14), 61), (H(72), 63), (H(85), 74), (H(110), 85), (H(119, 23), 86)])
number("nas_readiness_pct", rd, label="NAS Corpus Christi readiness", group="Military", unit="%", fmt="0", scale=[50, 100], visibility="internal",
       source="EVT-0103, EVT-0407, EVT-0602 (92 -> 61 -> 85)", lanes=["D"], threads=["T2"], description="DoD-internal; never public.")
state("base_generator", [(T0, "Healthy (regular supplier)"), (H(12, 15), "Emergency fuel contract (Quellmar)"), (H(33), "Running on Quellmar fuel"),
                         (H(40, 12), "Failed (fouled injectors)"), (H(72, 15), "Overhaul parts ordered"), (H(85), "Overhauled")],
      label="NAS backup generator EQP-2201", group="Military", visibility="internal", source="EVT-0103, EVT-0312, EVT-0404, EVT-0407, EVT-0506", lanes=["D"], threads=["T2", "T3"],
      states={"Healthy (regular supplier)": C["ok"], "Emergency fuel contract (Quellmar)": C["info"], "Running on Quellmar fuel": C["hidden2"], "Failed (fouled injectors)": C["severe"],
              "Overhaul parts ordered": C["partial"], "Overhauled": C["restore"]})
drone_ch = [(T0, "No activity")]
for d in (1, 2, 4, 5, 7, 9):
    drone_ch += [(H(d, 3), "Overflight"), (H(d, 8), "No activity")]
state("drone_overflights", drone_ch, label="Drone overflights at NAS (truth)", group="Military", visibility="hidden", source="EVT-0318", lanes=["D", "I"], threads=["T7"],
      states={"No activity": C["none"], "Overflight": C["hidden"]})
state("perimeter_sensors", [(T0, "Normal"), (H(0, 6), "Degraded (storm damage)"), (H(12, 18), "Restored")], label="NAS perimeter sensors", group="Military",
      visibility="internal", source="EVT-0318 (sensors down)", assumption=True, lanes=["D"], threads=["T7"],
      states={"Normal": C["ok"], "Degraded (storm damage)": C["warn"], "Restored": C["restore"]})
state("gps_interference", [(T0, "None"), (H(38, 13), "Active (JAM-01 near TANK-0390)"), (H(43, 23), "None")], label="GPS interference (truth)", group="Military",
      visibility="hidden", source="EVT-0412", lanes=["D", "I", "C"], threads=["T7", "T3"], states={"None": C["none"], "Active (JAM-01 near TANK-0390)": C["hidden"]})

# ---------------------------------------------------------------- hidden maritime threads
state("halcyon_drift", [(T0, "Out of area"), (H(-45), "Loitering offshore (true MMSI)"), (H(-3, 18), "At anchorage"), (H(-1, 14), "At sea (storm)"),
                        (H(3, 20), "At anchorage"), (H(31, 2), "AIS dark"), (H(31, 4), "Laying devices off entrance"), (H(31, 4, 40), "AIS dark"),
                        (H(31, 9), "Ship-to-ship transfer to Barge 44"), (H(31, 11), "AIS dark"), (H(31, 16), "At anchorage (AIS on)"), (H(34), "Departed area (assumed)")],
      label="MV Halcyon Drift (truth)", group="Hidden threads", visibility="hidden", source="EVT-0104, EVT-0207, EVT-0402, EVT-0403, EVT-0411", lanes=["I"], threads=["T2", "T7"],
      states={"Out of area": C["none"], "Loitering offshore (true MMSI)": "#9b87c4", "At anchorage": C["hidden"], "At sea (storm)": "#8c7ab8", "AIS dark": "#2b2140",
              "Laying devices off entrance": "#c8402f", "Ship-to-ship transfer to Barge 44": "#e07a1f", "At anchorage (AIS on)": C["hidden"], "Departed area (assumed)": C["none"]})
state("spoofed_identity", [(T0, "Inactive"), (H(31, 2), "Broadcasting MMSI-SYN-0457"), (H(31, 16), "Inactive")], label="Spoofed AIS identity (truth)",
      group="Hidden threads", visibility="hidden", source="EVT-0402", lanes=["I"], threads=["T2"], states={"Inactive": C["none"], "Broadcasting MMSI-SYN-0457": C["hidden"]})
dev = keyframes([(H(31, 4), 0), (H(31, 4, 30), 2), (H(44, 6), 2), (H(44, 6, 10), 1), (H(52, 17), 1), (H(52, 18), 0)])
number("devices_in_channel", [round(v) for v in dev], label="Explosive devices in channel (truth)", group="Hidden threads", unit="devices", fmt="0",
       scale=[0, 2], visibility="hidden", source="EVT-0411, EVT-0413, EVT-0414", lanes=["D", "I"], threads=["T7"])
fuel = keyframes([(H(32, 10), 0), (H(32, 16), 380), (H(33), 380), (H(40), 120), (H(75), 60)])
number("contaminated_fuel_m3", fuel, label="Transferred fuel in Quellmar tanks (truth)", group="Hidden threads", unit="m³", fmt="0", scale=[0, 400],
       visibility="hidden", source="EVT-0404; drawdown assumed", assumption=True, lanes=["D", "I"], threads=["T2", "T3"])

# ---------------------------------------------------------------- cyber and information
state("kestrel_activity", [(T0, "Dormant"), (H(-35, 14), "Reconnaissance scans"), (H(-33, 15), "Vendor phishing (Brightwake)"), (H(-32), "Dormant"),
                           (H(-20, 15), "Inside tanker networks"), (H(0, 4), "Valve commands sent"), (H(0, 5, 30), "Inside tanker networks"),
                           (H(1, 13), "Phishing wave (city, NAS)"), (H(3, 23), "Inside tanker networks"), (H(5, 18), "Dormant"),
                           (H(62, 2), "Credential stuffing (aid portal)"), (H(70, 23), "Dormant")],
      label="KESTREL activity (truth)", group="Cyber & information", visibility="hidden", source="EVT-0106, EVT-0107, EVT-0209, EVT-0313, EVT-0306, EVT-0502",
      lanes=["I", "C", "D"], threads=["T4", "T6"],
      states={"Dormant": C["none"], "Reconnaissance scans": "#b8a6d9", "Vendor phishing (Brightwake)": "#9b87c4", "Inside tanker networks": C["hidden"],
              "Valve commands sent": "#c8402f", "Phishing wave (city, NAS)": C["hidden2"], "Credential stuffing (aid portal)": "#8f2d6e"})
posts = keyframes([(H(2), 0), (H(2, 12), 1800), (H(4), 2600), (H(8), 1100), (H(14), 600), (H(20), 250), (H(21), 0), (H(75), 0), (H(76), 900), (H(79), 1300), (H(85), 300), (H(86), 0)])
number("rumor_posts_per_day", clamp(noise(posts, 25, smooth=24, seed=47), 0), label="Coordinated rumor posts (daily rate)", group="Cyber & information", unit="posts/day",
       fmt="0", scale=[0, 2700], source="EVT-0309, EVT-0507 (18,000 posts, 40 accounts)", lanes=["C", "I"], threads=["T4"])
ato = keyframes([(H(62, 2), 0), (H(70, 23), 410)])
number("accounts_taken_over", [round(v) for v in ato], label="Aid accounts taken over (cumulative)", group="Cyber & information", unit="accounts", fmt="0",
       scale=[0, 420], visibility="internal", source="EVT-0502; public from PUB-085 (day 71)", lanes=["C", "I"], threads=["T4"])
state("spill_cause_public", [(T0, "No spill"), (H(0, 7), "Cause unknown"), (H(6, 16), "Possible unauthorized remote access"), (H(8, 16), "Vendor credentials misused"),
                             (H(112, 15), "Attributed to a foreign government")], label="Public knowledge: spill cause", group="Public knowledge",
      source="PUB-024, PUB-042, PUB-047, PUB-097", threads=["T6"],
      states={"No spill": C["none"], "Cause unknown": C["calm"], "Possible unauthorized remote access": C["info"], "Vendor credentials misused": C["public"], "Attributed to a foreign government": "#1d4f86"})
state("blast_cause_public", [(T0, "No incident"), (H(44, 7), "Cause unknown"), (H(46, 15), "Explosive device confirmed"), (H(52, 16), "Second device found"),
                             (H(112, 15), "Attributed to a foreign government")], label="Public knowledge: channel blast", group="Public knowledge",
      source="PUB-067, PUB-070, PUB-078, PUB-097", threads=["T7"],
      states={"No incident": C["none"], "Cause unknown": C["calm"], "Explosive device confirmed": C["info"], "Second device found": C["public"], "Attributed to a foreign government": "#1d4f86"})
state("drones_public", [(T0, "Nothing reported"), (H(2, 15), "Residents' videos"), (H(6, 15), "NAS aware"), (H(9, 15), "FBI investigating"), (H(11, 15), "Sightings stopped"),
                        (H(96, 15), "Navy security review")], label="Public knowledge: drones", group="Public knowledge", source="PUB-032, PUB-043, PUB-048, PUB-051, PUB-093",
      threads=["T7"], states={"Nothing reported": C["none"], "Residents' videos": C["calm"], "NAS aware": C["info"], "FBI investigating": C["public"], "Sightings stopped": "#8fb3d9", "Navy security review": "#1d4f86"})
state("gps_public", [(T0, "Nothing reported"), (H(39, 15), "FAA notice: interference"), (H(44, 6), "Interference stopped"), (H(47, 15), "Transmitter found (parked vehicle)")],
      label="Public knowledge: GPS interference", group="Public knowledge", source="PUB-064, PUB-067, PUB-074", threads=["T7"],
      states={"Nothing reported": C["none"], "FAA notice: interference": C["info"], "Interference stopped": "#8fb3d9", "Transmitter found (parked vehicle)": C["public"]})
state("ais_anomaly_public", [(T0, "Nothing reported"), (H(38, 15), "Identity in two places reported"), (H(48, 15), "Analysts note timing vs blast")],
      label="Public knowledge: AIS anomaly", group="Public knowledge", source="PUB-062, PUB-076", threads=["T2", "T7"],
      states={"Nothing reported": C["none"], "Identity in two places reported": C["info"], "Analysts note timing vs blast": C["public"]})

# ---------------------------------------------------------------- aid and money
state("fema_status", [(T0, "No declaration"), (H(4, 16), "Declaration (public assistance only)"), (H(25, 15), "State requests household aid"),
                      (H(57, 16), "Household aid approved"), (H(60, 13), "Registration open"), (H(92, 15), "Door-to-door registration")],
      label="FEMA aid status", group="Aid & money", source="PUB-103, PUB-104, PUB-105, PUB-081, PUB-092", threads=["T5"], lanes=["C"],
      states={"No declaration": C["none"], "Declaration (public assistance only)": C["info"], "State requests household aid": C["watch"], "Household aid approved": C["partial"],
              "Registration open": C["restore"], "Door-to-door registration": C["ok"]})
ia = []
for i in range(N):
    t = T0 + i
    if t < H(60, 13): ia.append(0)
    else:
        x = (t - H(60, 13)) / 24.0
        ia.append(48000 / (1 + math.exp(-(x - 12) / 4.5)) * (1 if x < 29 else 1) + (max(0, x - 29) * 100))
scale_ia = 48000 / ia[idx(H(89, 23))]
number("aid_registrations_cumulative", [round(v * scale_ia) for v in ia], label="FEMA aid registrations (cumulative)", group="Aid & money", unit="claims", fmt="0",
       scale=[0, 52000], source="EVT-0501 (48,000 in 30 days)", threads=["T5"], lanes=["C"])
state("debris_contract_vantorra", [(T0, "None"), (H(10, 15), "Awarded $14.2M (sole-source)"), (H(78, 15), "Overbilling records reported"), (H(80, 15), "Payments paused"),
                                   (H(84, 15), "Inspector general review"), (H(104, 14), "FBI search warrants"), (H(114, 15), "Forfeiture filing (Brannoch)")],
      label="Debris contract: Vantorra", group="Aid & money", source="PUB-049, PUB-088, PUB-089, PUB-090, PUB-094, PUB-098", threads=["T3"], lanes=["C", "I"],
      states={"None": C["none"], "Awarded $14.2M (sole-source)": C["info"], "Overbilling records reported": C["watch"], "Payments paused": C["warn"],
              "Inspector general review": "#d4552a", "FBI search warrants": C["severe"], "Forfeiture filing (Brannoch)": C["closed"]})
state("fuel_contract_quellmar", [(T0, "None"), (H(12, 15), "Awarded $2.1M (emergency)"), (H(33), "Delivering transferred fuel (truth)"), (H(75, 15), "Suspended by Navy"),
                                 (H(104, 14), "FBI search warrants"), (H(114, 15), "Forfeiture filing (Brannoch)")],
      label="Fuel contract: Quellmar", group="Aid & money", source="EVT-0312, EVT-0404; PUB-056, PUB-087, PUB-094, PUB-098", threads=["T2", "T3"], lanes=["D", "C", "I"],
      states={"None": C["none"], "Awarded $2.1M (emergency)": C["info"], "Delivering transferred fuel (truth)": C["hidden2"], "Suspended by Navy": C["warn"],
              "FBI search warrants": C["severe"], "Forfeiture filing (Brannoch)": C["closed"]})
div = keyframes([(H(64), 0), (H(70), 0.9), (H(76), 2.8), (H(80), 3.9)])
number("diverted_aid_musd", div, label="Diverted disaster aid (truth, cumulative)", group="Aid & money", unit="$M", fmt="0.0", scale=[0, 4], visibility="hidden",
       source="EVT-0503 ($3.9M); public only from PUB-098 (day 114)", threads=["T3", "T4"], lanes=["C", "I"])

# ---------------------------------------------------------------- phases
phases = load("00_scenario/config.json")["phases"]
state("phase", [(H(p["start_day"]), f"Phase {p['phase']}: {p['name']}") for p in phases], label="Scenario phase", group="Scenario",
      source="00_scenario/phases.json", states={f"Phase {p['phase']}: {p['name']}": c for p, c in zip(phases, ["#a9b8c6", "#d9b75b", "#c8402f", "#e08a3c", "#5aa0b8", "#6b8fc9"])})

# ---------------------------------------------------------------- scenario layers
# A layer scenario (registry kind "layer") may provide 00_scenario/state_layer.py with build(api, scenario).
# Its variables are stamped with the scenario id; check_scenarios.py enforces the id prefix.
import importlib.util
from common import load_registry, sroot
LAYERS = [s for s in load_registry() if s.get("kind") == "layer"]
for _s in LAYERS:
    _f = os.path.join(sroot(_s["id"]), "00_scenario", "state_layer.py")
    if os.path.exists(_f):
        _spec = importlib.util.spec_from_file_location("layer_" + _s["id"], _f); _mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _api = dict(state=lambda vid, ch, _sid=_s["id"], **kw: state(vid, ch, scenario=_sid, **kw),
                    number=lambda vid, arr, _sid=_s["id"], **kw: number(vid, arr, scenario=_sid, **kw),
                    H=H, idx=idx, keyframes=keyframes, noise=noise, clamp=clamp, segs=segs, C=C, N=N, T0=T0, T1=T1,
                    value=lambda vid, t: SERIES[vid][idx(t)] if vid in SERIES else next((v for a, b, v, _ in SEGS[vid] if a <= t < b), None))
        _mod.build(_api, _s)

# ---------------------------------------------------------------- events
msel = load("00_scenario/msel.json"); facts = load("02_public_record/public_record.json")["facts"]
def ev_time(e):
    if e.get("time_utc"):
        hh, mm = e["time_utc"].rstrip("Z").split(":")
        return H(e["day"], int(hh), int(mm))
    return H(e["day"], 15)
def _obs(e):
    """Stream ids for the viewer (observed_in entries are {stream, what, when} objects; older files hold plain labels)."""
    out = []
    for o in e.get("observed_in", []) or []:
        sid = o["stream"] if isinstance(o, dict) else o
        if sid not in out:
            out.append(sid)
    return out

events = []
for e in msel:
    events.append({"id": e["event_id"], "kind": "truth", "t": round(ev_time(e), 2), "t_end": round(H(e["day_end"], 23), 2) if e.get("day_end") else None,
                   "label": e["description"], "threads": e["threads"], "lanes": e["lanes"], "places": e["place_ids"], "observed_in": _obs(e)})
for f in facts:
    events.append({"id": f["id"], "kind": "public", "t": H(f["day"], 15), "label": f["statement"], "arcs": f["arcs"], "events": f["events"],
                   "threads": sorted({t for ev in msel if ev["event_id"] in f["events"] for t in ev["threads"]}), "lanes": ["C", "D", "I"]})
for _s in LAYERS:
    _r = sroot(_s["id"])
    _m = os.path.join(_r, "00_scenario", "msel.json"); _p = os.path.join(_r, "02_public_record", "public_record.json")
    _lm = json.load(open(_m, encoding="utf-8")) if os.path.exists(_m) else []
    for e in _lm:
        events.append({"id": e["event_id"], "kind": "truth", "t": round(ev_time(e), 2), "t_end": round(H(e["day_end"], 23), 2) if e.get("day_end") else None,
                       "label": e["description"], "threads": e["threads"], "lanes": e["lanes"], "places": e.get("place_ids", []),
                       "observed_in": _obs(e), "scenario": _s["id"]})
    for f in (json.load(open(_p, encoding="utf-8"))["facts"] if os.path.exists(_p) else []):
        events.append({"id": f["id"], "kind": "public", "t": H(f["day"], 15), "label": f["statement"], "arcs": f.get("arcs", []), "events": f.get("events", []),
                       "threads": sorted({t for ev in _lm if ev["event_id"] in f.get("events", []) for t in ev["threads"]}), "lanes": ["C", "D", "I"], "scenario": _s["id"]})
events.sort(key=lambda e: e["t"])

# ---------------------------------------------------------------- write
os.makedirs(path(OUT), exist_ok=True)
meta = {"scenario": "Hurricane Rafael", "t0_hour": T0, "t1_hour": T1, "hours": N, "d0_date": "2027-09-14", "landfall_t": 6,
        "time_note": "t = hours from D0 00:00Z (Sept. 14, 2027). Local time is UTC-5 (CDT) until Nov. 7, 2027 07:00Z (t = 1303), then UTC-6 (CST).",
        "dst_end_t": 54 * 24 + 7, "relief_flights_total": int(fl_total), "generated_by": "scripts/build_world_state.py"}
def dump(name, obj):
    with open(path(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":") if name == "series_hourly.json" else None, indent=None if name == "series_hourly.json" else 1)
groups = []
for v in VARS:
    if v["group"] not in groups: groups.append(v["group"])
dump("variables.json", {"meta": meta, "groups": groups, "variables": VARS})
dump("segments.json", SEGS)
dump("series_hourly.json", {"t0": T0, "series": SERIES})
dump("events.json", events)
dump("storm_track.json", track6)
d0 = datetime.datetime(2027, 9, 14, tzinfo=datetime.timezone.utc)
with open(path(OUT, "series_hourly.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); keys = list(SERIES)
    w.writerow(["t", "utc"] + keys)
    for i in range(N):
        w.writerow([T0 + i, (d0 + datetime.timedelta(hours=T0 + i)).strftime("%Y-%m-%dT%H:%MZ")] + [SERIES[k][i] for k in keys])
def value_at(vid, t):
    if vid in SERIES: return SERIES[vid][idx(t)]
    for s, e, v, _ in SEGS[vid]:
        if s <= t < e: return v
with open(path(OUT, "state_daily.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); keys = [v["id"] for v in VARS]
    w.writerow(["day", "utc"] + keys)
    for d in range(-60, 120):
        t = d * 24 + 18
        w.writerow([d, (d0 + datetime.timedelta(hours=t)).strftime("%Y-%m-%dT%H:%MZ")] + [value_at(k, t) for k in keys])
print(f"variables: {len(VARS)} ({len(SEGS)} state, {len(SERIES)} numeric); events: {len(events)}; track points: {len(track6)}; hours: {N}; relief flights: {int(fl_total)}")
