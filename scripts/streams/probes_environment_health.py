"""Descriptions and probes for the environment and health streams (see scripts/check_streams.py).

Every probe reads the delivered files on disk and tests what the canon timeline says a participant
should be able to find: the entity, the time and the value or pattern. Nothing here looks at the
generators.
"""
import csv
import datetime as dt
import glob
import json
import math
import os
from collections import Counter, defaultdict
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "05_other_sources")
D0 = dt.date(2027, 9, 14)
UTC = dt.timezone.utc


def E(iso):
    s = iso.replace("Z", "+00:00").replace(" ", "T")
    if len(s) <= 16:
        s += ":00+00:00" if len(s) == 16 else "T00:00:00+00:00"
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return d.timestamp()


def day(datestr):
    return (dt.date.fromisoformat(datestr[:10]) - D0).days


@lru_cache(maxsize=None)
def rows(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def files(pattern):
    return sorted(os.path.relpath(p, SRC) for p in glob.glob(os.path.join(SRC, pattern)))


@lru_cache(maxsize=None)
def reg(name):
    with open(os.path.join(ROOT, "06_data_streams", name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def f(x, default=float("nan")):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else float("nan")


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def span_of(pattern, col, fmt=None, end_of_day=False):
    lo, hi = float("inf"), float("-inf")
    for rel in files(pattern):
        r = rows(rel)
        if not r:
            continue
        vals = [x[col] if not callable(col) else col(x) for x in (r[0], r[-1])]
        for v in vals:
            t = E(v)
            lo, hi = min(lo, t), max(hi, t + (30 * 3600 if end_of_day else 0))
        if end_of_day or callable(col):
            ts = [E(x[col] if not callable(col) else col(x)) for x in r]
            lo, hi = min(lo, min(ts)), max(hi, max(ts) + (30 * 3600 if end_of_day else 0))
    return lo, hi


def header(pattern):
    cols = []
    for rel in files(pattern):
        with open(os.path.join(SRC, rel), encoding="utf-8", newline="") as fh:
            cols += next(csv.reader(fh))
    return sorted(set(cols))


def ids_in(pattern, col):
    out = set()
    for rel in files(pattern):
        out |= {x[col] for x in rows(rel)}
    return out


def sensor_ids(*keys):
    S = reg("sensor_registry")
    return {x.get("sensor_id") or x.get("site_id") for k in keys for x in S[k]}


# ======================================================================================
# weather
# ======================================================================================
def wx(sid):
    return rows(f"weather/{sid}_ASOS_observations.csv")


def buoy(sid):
    return rows(f"weather/BUOY{sid}_observations.csv")


def p_weather_soak():
    out = []
    for sid in ("KCRP", "KNGP"):
        r = [x for x in wx(sid) if "2027-09-07T05" <= x["ObsDateTime"] < "2027-09-12T05" and x["ReportType"] == "FM-15"]
        wet = [x for x in r if f(x["Precip1hr_mm"]) >= 2.5]
        days = {x["ObsDateTime"][:10] for x in wet}
        tot = sum(f(x["Precip1hr_mm"]) for x in r)
        out.append((sid, len(wet), len(days), round(tot)))
        if len(wet) < 12 or len(days) < 4 or tot < 100:
            return False, f"{sid}: only {len(wet)} hours of moderate-to-heavy rain on {len(days)} days, {tot:.0f} mm"
    return True, "; ".join(f"{s}: {n} hours >= 2.5 mm/h on {d} days, {t} mm" for s, n, d, t in out)


def p_weather_buoy():
    b = buoy("42020")
    seg = lambda a, z, c: [f(x[c]) for x in b if a <= x["ObsDateTime"] < z]
    dpd0, dpd1 = mean(seg("2027-09-03", "2027-09-07", "DPD_s")), mean(seg("2027-09-09", "2027-09-12", "DPD_s"))
    h0, h8, h11 = mean(seg("2027-09-03", "2027-09-07", "WVHT_m")), mean(seg("2027-09-08T05", "2027-09-09T05", "WVHT_m")), mean(seg("2027-09-11T05", "2027-09-12T05", "WVHT_m"))
    p8, p11 = mean(seg("2027-09-08T05", "2027-09-09T05", "PRES_mb")), mean(seg("2027-09-11T05", "2027-09-12T05", "PRES_mb"))
    ok = dpd1 >= dpd0 + 3 and h11 > h8 > h0 and p8 - p11 >= 1.0
    return ok, (f"buoy 42020: dominant period {dpd0:.1f} s -> {dpd1:.1f} s, wave height {h0:.2f} -> {h8:.2f} -> {h11:.2f} m, "
                f"pressure {p8:.1f} -> {p11:.1f} mb between D-6 and D-3")


def p_weather_landfall():
    notes, gaps = [], 0
    for sid in ("KNGP", "KCRP", "KRAS"):
        r = wx(sid)
        pm = min(r, key=lambda x: f(x["SeaLevelPressure_mb"]))
        pg = max(r, key=lambda x: f(x["WindGust_mps"], 0))
        if not ("2027-09-14T02" <= pm["ObsDateTime"] < "2027-09-14T12"):
            return False, f"{sid}: record-low pressure is at {pm['ObsDateTime']}, outside 02:00Z-12:00Z D0"
        if not ("2027-09-14T02" <= pg["ObsDateTime"] < "2027-09-14T12") or f(pg["WindGust_mps"]) < 33:
            return False, f"{sid}: peak gust {pg['WindGust_mps']} m/s at {pg['ObsDateTime']}"
        ts = [E(x["ObsDateTime"]) for x in r]
        d0a, d0b = E("2027-09-14T02:00Z"), E("2027-09-15T00:00Z")
        gap = max([(b - a) for a, b in zip(ts, ts[1:]) if d0a <= a < d0b] or [0]) / 3600      # longest silence that begins on D0
        if gap >= 3:
            gaps += 1
        dirs = [f(x["WindDir_deg"]) for x in r if "2027-09-14T02" <= x["ObsDateTime"] < "2027-09-14T12"]
        swing = max(min(abs(a - b), 360 - abs(a - b)) for a in dirs for b in dirs)
        notes.append(f"{sid} min {f(pm['SeaLevelPressure_mb']):.0f} mb at {pm['ObsDateTime'][11:16]}Z, gust {f(pg['WindGust_mps']) / 0.5144:.0f} kt at "
                     f"{pg['ObsDateTime'][11:16]}Z, wind swings {swing:.0f} deg, longest gap {gap:.0f} h")
        if sid == "KRAS" and swing < 60:
            return False, "KRAS: no wind shift with the eye"
    if gaps < 2:
        return False, "fewer than two of the three stations drop out for hours: " + "; ".join(notes)
    return True, "; ".join(notes)


# ======================================================================================
# advisories
# ======================================================================================
@lru_cache(maxsize=None)
def advisories():
    with open(os.path.join(SRC, "weather", "nhc_advisories.json"), encoding="utf-8") as fh:
        return json.load(fh)


def p_adv_formation():
    a = advisories()["advisories"]
    named = [x for x in a if x["storm_name"] == "RAFAEL" and x["classification"] == "Tropical Storm"]
    if not named:
        return False, "no tropical storm advisory"
    first = named[0]
    if not (E("2027-09-04T05:00Z") <= E(first["issued_utc"]) < E("2027-09-05T05:00Z")):
        return False, f"first Tropical Storm Rafael advisory issued {first['issued_utc']}, not on D-10"
    if not (15 <= first["center"]["lat"] <= 20 and -87 <= first["center"]["lon"] <= -80):
        return False, f"first named position {first['center']} is not in the northwestern Caribbean"
    gulf = [x for x in a if x["center"]["lat"] > 20.5 and x["center"]["lon"] < -88 and x["classification"] == "Hurricane"]
    cone = [x for x in a if x["corpus_christi_in_forecast_cone"] and E(x["issued_utc"]) < E("2027-09-10T05:00Z")]
    if not gulf or not cone:
        return False, "no advisory in the Gulf as a hurricane, or cone never covers Corpus Christi by D-5"
    return True, (f"advisory {first['advisory_number']} names Rafael at {first['issued_utc']} near {first['center']['lat']}N {abs(first['center']['lon'])}W; "
                  f"hurricane in the Gulf from {gulf[0]['issued_utc']}; Corpus Christi inside the forecast cone from {cone[0]['issued_utc']}")


def p_adv_landfall():
    for x in advisories()["advisories"]:
        lf = x.get("landfall")
        if lf and E("2027-09-14T03:00Z") <= E(x["issued_utc"]) <= E("2027-09-14T09:00Z"):
            ok = lf["category"] == 3 and "Mustang Island" in lf["location"] and "Port Aransas" in lf["location"] and lf["time_utc"].startswith("2027-09-14T06:00")
            return ok, f"advisory {x['advisory_number']} issued {x['issued_utc']}: {x['headline']}"
    return False, "no landfall advisory between 03:00Z and 09:00Z on D0"


# ======================================================================================
# gauges
# ======================================================================================
def gauge(sid):
    return rows(f"env_sensors/gauge_{sid}.csv")


def p_gauge_river():
    d = defaultdict(list)
    for x in gauge("GAUGE-12"):
        if "2027-09-06" <= x["ObsDateTime"][:10] <= "2027-09-13":
            d[x["ObsDateTime"][:10]].append(f(x["Stage_ft"]))
    m = [mean(d[k]) for k in sorted(d)]
    ok = all(b > a for a, b in zip(m[1:], m[2:])) and m[-1] - m[0] >= 3.0
    return ok, "GAUGE-12 daily mean stage, Sept 6 to 13: " + ", ".join(f"{v:.2f}" for v in m) + " ft"


def p_gauge_surge():
    best = None
    for sid in ("TG-8775237", "TG-8775241", "TG-8774770"):
        r = [x for x in gauge(sid) if "2027-09-14T04" <= x["ObsDateTime"] < "2027-09-14T12"]
        if r:
            m = max(r, key=lambda x: f(x["Residual_ft"]))
            if best is None or f(m["Residual_ft"]) > f(best["Residual_ft"]):
                best = m
    peak_m = f(best["Residual_ft"]) / 3.28084
    g14 = gauge("GAUGE-14")
    hole = [x for x in g14 if "2027-09-14T05" <= x["ObsDateTime"] < "2027-09-19T12"]
    before = [x for x in g14 if "2027-09-14T00" <= x["ObsDateTime"] < "2027-09-14T05"]
    after = [x for x in g14 if x["ObsDateTime"] >= "2027-09-19T12"]
    ok = 3.2 <= peak_m <= 3.6 and not hole and before and after
    return ok, (f"{best['SensorID']} residual peaks {f(best['Residual_ft']):.2f} ft ({peak_m:.2f} m) at {best['ObsDateTime'][11:16]}Z; "
                f"GAUGE-14 last reports {before[-1]['ObsDateTime'][11:16]}Z D0 at {f(before[-1]['Residual_ft']):.1f} ft above prediction and is silent until {after[0]['ObsDateTime'][:10]}"
                if before and after else "GAUGE-14 outage not as expected")


# ======================================================================================
# water quality
# ======================================================================================
def wq(sid):
    return rows(f"env_sensors/water_quality_{sid}.csv")


SONDES = ["WQ-01", "WQ-02", "WQ-03", "WQ-04", "WQ-05", "WQ-06"]


def pre_median(sid):
    return median([f(x["TotalHydrocarbons_ppb"]) for x in wq(sid) if x["ObsDateTime"] < "2027-09-13"])


def first_over(sid, level, after="2027-09-13"):
    for x in wq(sid):
        if x["ObsDateTime"] >= after and f(x["TotalHydrocarbons_ppb"]) > level:
            return x["ObsDateTime"]
    return None


def nearest_sonde_to_berth():
    T = reg("terminal_registry")
    b = next(x for x in T["berths"] if x["terminal_id"] == "TERM-01")
    S = reg("sensor_registry")["water_quality_sondes"]
    d = lambda s: math.hypot((s["latitude"] - b["latitude"]) * 110.95, (s["longitude"] - b["longitude"]) * 98.5)
    s = min(S, key=d)
    return s["sensor_id"], d(s)


def p_wq_nearest():
    sid, km = nearest_sonde_to_berth()
    base = pre_median(sid)
    r = [x for x in wq(sid) if "2027-09-14T04:00" <= x["ObsDateTime"] <= "2027-09-14T05:00"]
    hit = next((x for x in r if f(x["TotalHydrocarbons_ppb"]) > 5 * base), None)
    quiet = [f(x["TotalHydrocarbons_ppb"]) for x in wq(sid) if "2027-09-13T20:00" <= x["ObsDateTime"] < "2027-09-14T04:00"]
    ok = hit is not None and quiet and max(quiet) < 2.5 * base
    return ok, (f"{sid} ({km:.1f} km from the TERM-01 berth): {f(hit['TotalHydrocarbons_ppb']):.0f} ppb at {hit['ObsDateTime'][11:16]}Z against a "
                f"{base:.0f} ppb baseline; no rise in the eight hours before 04:00Z" if hit else f"{sid}: no rise within the hour")


def p_wq_wq01():
    base = pre_median("WQ-01")
    r = [x for x in wq("WQ-01") if "2027-09-14T04:00" <= x["ObsDateTime"] <= "2027-09-14T05:00"]
    hit = next((x for x in r if f(x["TotalHydrocarbons_ppb"]) > 3 * base), None)
    return hit is not None, (f"WQ-01 leaves its {base:.0f} ppb baseline at {hit['ObsDateTime'][11:16]}Z ({f(hit['TotalHydrocarbons_ppb']):.0f} ppb)" if hit
                             else "WQ-01 still at baseline at 05:00Z")


def p_wq_sequence():
    first = {s: first_over(s, 100.0) for s in SONDES}
    if any(v is None for v in first.values()):
        return False, f"not every sonde crosses 100 ppb: {first}"
    harbor = [first[s] for s in SONDES if "Inner Harbor" in next(x for x in reg("sensor_registry")["water_quality_sondes"] if x["sensor_id"] == s)["water_body"]]
    bays = [first[s] for s in SONDES if first[s] not in harbor]
    ok = max(harbor) < min(bays) and max(harbor) < "2027-09-14T12" and max(first.values()) < "2027-09-17T05"
    return ok, "first reading above 100 ppb: " + ", ".join(f"{s} {first[s][5:16]}Z" for s in sorted(first, key=first.get))


def p_wq_network():
    bases = [pre_median(s) for s in SONDES]
    allmax = max(((f(x["TotalHydrocarbons_ppb"]), x["ObsDateTime"], s) for s in SONDES for x in wq(s)), key=lambda z: z[0])
    first = {s: first_over(s, 100.0) for s in SONDES}
    d0 = [s for s in SONDES if first[s] and first[s][:10] == "2027-09-14"]
    later = [s for s in SONDES if first[s] and "2027-09-15" <= first[s][:10] <= "2027-09-16"]
    ok = all(15 <= b <= 25 for b in bases) and abs(allmax[0] - 3400) <= 50 and allmax[1][:10] == "2027-09-17" and len(d0) >= 2 and len(d0) + len(later) == 6
    return ok, (f"baselines {min(bases):.0f}-{max(bases):.0f} ppb (0.02 mg/L); network peak {allmax[0]:.0f} ppb (3.4 mg/L) at {allmax[2]} on {allmax[1][:16]}Z; "
                f"0.10 mg/L crossed on D0 at {', '.join(d0)}, on D+1/D+2 at {', '.join(later)}. The agency alert queue is not part of the sonde stream.")


def p_wq_nueces():
    r = wq("WQ-03")
    x = next((x for x in r if x["ObsDateTime"].startswith("2027-09-18T16:30")), None)
    mx = max(r, key=lambda z: f(z["TotalHydrocarbons_ppb"]))
    ok = x is not None and 2050 <= f(x["TotalHydrocarbons_ppb"]) <= 2150 and f(mx["TotalHydrocarbons_ppb"]) <= f(x["TotalHydrocarbons_ppb"]) + 1
    return ok, f"WQ-03 (Nueces Bay): {x['TotalHydrocarbons_ppb'] if x else 'missing'} ppb at 16:30Z on D+4, its record high"


def p_wq_d20():
    v = [f(x["TotalHydrocarbons_ppb"]) for s in SONDES for x in wq(s) if "2027-10-04T17:00" <= x["ObsDateTime"] <= "2027-10-04T22:00"]
    m = mean(v)
    return 340 <= m <= 460, (f"network average {m:.0f} ppb ({m / 1000:.2f} mg/L) between 17:00Z and 22:00Z on D+20. The plant raw-water intake reading "
                             "(FAC-UTL-01-RAW-TPH-MGL) is a plant tag carried by the historian stream, not a sonde.")


def p_wq_d60():
    v = [f(x["TotalHydrocarbons_ppb"]) for s in ("WQ-03", "WQ-04", "WQ-06") for x in wq(s) if "2027-11-08T06:00" <= x["ObsDateTime"] < "2027-11-14T06:00"]
    m = mean(v)
    return 20 <= m <= 40, f"bay sondes average {m:.0f} ppb ({m / 1000:.3f} mg/L) over D+55 to D+61"


# ======================================================================================
# air quality
# ======================================================================================
def aq(sid):
    return rows(f"env_sensors/aqs_air_quality_{sid}.csv")


def aqt(x):
    return x["Date_GMT"] + "T" + x["Time_GMT"]


def p_aq_channel():
    notes = []
    for sid in ("AQS-480-005", "AQS-480-001", "AQS-480-016"):
        r = aq(sid)
        b0 = median([f(x["Benzene_ppb"]) for x in r if x["Date_GMT"] < "2027-09-12"])
        h0 = median([f(x["TNMHC_ppbC"]) for x in r if x["Date_GMT"] < "2027-09-12"])
        w = [x for x in r if "2027-09-14T05:00" <= aqt(x) < "2027-09-20T05:00"]
        if not w:
            return False, f"{sid}: no readings in the window"
        bm, hm = max(f(x["Benzene_ppb"]) for x in w), max(f(x["TNMHC_ppbC"]) for x in w)
        if bm < 4 * b0 or hm < 4 * h0:
            return False, f"{sid}: benzene max {bm} vs baseline {b0}"
        notes.append(f"{sid} benzene {b0:.2f} -> {bm:.1f} ppb, hydrocarbons {h0:.0f} -> {hm:.0f} ppbC")
    return True, "; ".join(notes)


def p_aq_hillcrest():
    r = aq("AQS-480-005")
    b0 = median([f(x["Benzene_ppb"]) for x in r if x["Date_GMT"] < "2027-09-12"])
    at = lambda k: next((f(x["Benzene_ppb"]) for x in r if aqt(x) == k), None)
    v1, v2 = at("2027-09-16T14:00"), at("2027-09-17T02:00")
    mx = max(r, key=lambda x: f(x["Benzene_ppb"]))
    late = max(f(x["Benzene_ppb"]) for x in r if aqt(x) >= "2027-09-19T18:00")
    ok = (0.2 <= b0 <= 0.45 and v1 is not None and abs(v1 - 4.8) <= 0.05 and v2 is not None and abs(v2 - 7.2) <= 0.05
          and aqt(mx) == "2027-09-17T02:00" and late < 3.0)
    return ok, f"Hillcrest monitor AQS-480-005: baseline {b0:.2f} ppb, {v1} at 14:00Z D+2, peak {v2} at 02:00Z D+3, highest reading from 18:00Z D+5 on {late:.2f}"


# ======================================================================================
# health
# ======================================================================================
D34 = {"78405", "78416", "78417", "78401", "78407", "78408"}
SHORE_TRACTS = {"480101", "480201", "480301", "480401", "480501", "481301"}


@lru_cache(maxsize=None)
def visits():
    out = []
    for rel in files("public_health/ed_visits_*.csv"):
        for x in rows(rel):
            x["_d"] = day(x["Visit_Date"])
            x["_f"] = x["Facility_ID"].split("-")[1]
            out.append(x)
    return out


def rate(cond, lo, hi):
    return sum(1 for x in visits() if lo <= x["_d"] <= hi and cond(x)) / (hi - lo + 1)


def plc010():
    with open(os.path.join(ROOT, "06_data_streams", "_internal", "areas_truth.json"), encoding="utf-8") as fh:
        return {t.split("-")[-1] for t in json.load(fh)["truth"]["PLC-010"]["members"]}


def p_ed_baseline():
    c = Counter(x["_d"] for x in visits() if x["Facility_County"] == "Nueces" and -30 <= x["_d"] <= -5)
    m = mean(c.values())
    return 495 <= m <= 545, f"{m:.0f} visits a day at the six Nueces County emergency departments, Aug. 15 to Sept. 9"


def p_ed_srmc_d0():
    s = [x for x in visits() if x["_f"] == "SRMC" and x["_d"] == 0]
    by18 = [x for x in s if x["Arrive_Date_Time"] < "2027-09-14T23:00:00Z"]
    crush = sum(x["Chief_Complaint_Text"].startswith(("crush", "pinned")) for x in by18)
    drown = sum(x["Chief_Complaint_Text"].startswith(("near drowning", "submersion")) for x in by18)
    adm = sum(x["Disposition"] == "Admitted" for x in by18)
    ems_s = sum(x["Arrival_Mode"] == "EMS" for x in s)
    ems_b = sum(x["Arrival_Mode"] == "EMS" for x in visits() if x["_f"] == "BCMC" and x["_d"] == 0)
    esi1 = sum(x["Triage_Acuity_ESI"] == "1" for x in s)
    ok = len(by18) == 118 and crush == 4 and drown == 2 and adm == 37 and ems_s == 44 and ems_b == 28 and esi1 == 6
    return ok, (f"SRMC D0: {len(by18)} arrivals by 18:00 local ({crush} crush, {drown} near-drowning), {adm} admitted ({100 * adm / max(1, len(by18)):.0f}%), "
                f"{esi1} triaged ESI 1; ambulance arrivals {ems_s} at SRMC and {ems_b} at BCMC")


def p_ed_shoreline():
    shore = lambda x: (x["Patient_Tract"] in SHORE_TRACTS) and x["CC_Category"] in ("RESP", "SKIN")
    other = lambda x: (x["Patient_Tract"] not in SHORE_TRACTS) and x["CC_Category"] in ("RESP", "SKIN")
    a, b = rate(shore, 3, 21) / rate(shore, -30, -5), rate(other, 3, 21) / rate(other, -30, -5)
    return 1.4 <= a <= 1.85 and b < 1.25, f"respiratory and skin visits, D+3 to D+21 against Aug. 15 to Sept. 9: shoreline tracts x{a:.2f}, everywhere else x{b:.2f}"


def p_ed_gi_wave():
    gi = lambda x: x["CC_Category"] == "GI"
    base, peak = rate(gi, -30, -5), rate(gi, 6, 13)
    return 2.4 <= peak / base <= 3.2, f"gastrointestinal visits: {base:.1f} a day at baseline, {peak:.1f} a day D+6 to D+13 ({100 * (peak / base - 1):.0f}% above)"


def gi_count(fac, d):
    return sum(1 for x in visits() if x["_f"] == fac and x["_d"] == d and x["CC_Category"] == "GI")


def p_ed_cluster_peak():
    lab = [x for x in visits() if x["Discharge_Diagnosis_ICD10"] in ("A07.2", "A07.1")]
    first = min(x["_d"] for x in lab) if lab else None
    s = [gi_count("SRMC", d) for d in range(18, 23)]
    b = [gi_count("BCMC", d) for d in range(18, 23)]
    cl = [x for x in visits() if x["_f"] in ("SRMC", "BCMC") and 18 <= x["_d"] <= 22 and x["CC_Category"] == "GI"]
    share = sum(x["Patient_ZIP"] in D34 for x in cl) / max(1, len(cl))
    ok = first == 18 and all(200 <= v <= 235 for v in s) and all(110 <= v <= 135 for v in b) and share >= 0.88
    return ok, (f"Cryptosporidium/Giardia codes (A07.2, A07.1) first appear on D+{first} ({len(lab)} visits in all); GI visits D+18 to D+22: SRMC {s}, BCMC {b}; "
                f"{100 * share:.0f}% from the Districts 3 and 4 ZIP codes")


def p_ed_cluster_start():
    a, z = "2027-09-28T17:00:00Z", "2027-09-29T17:00:00Z"
    s = [x for x in visits() if x["_f"] == "SRMC" and x["CC_Category"] == "GI" and a <= x["Arrive_Date_Time"] < z]
    b = [x for x in visits() if x["_f"] == "BCMC" and x["CC_Category"] == "GI" and a <= x["Arrive_Date_Time"] < z]
    base = rate(lambda x: x["_f"] == "SRMC" and x["CC_Category"] == "GI", -30, -5)
    b34 = sum(x["Patient_ZIP"] in D34 for x in b)
    es = sum(x["Preferred_Language"] == "Spanish" for x in s + b)
    ok = len(s) == 14 and len(b) == 8 and b34 == 6
    return ok, (f"noon D+14 to noon D+15 local: SRMC {len(s)} GI presentations (baseline {base:.1f} a day), BCMC {len(b)} with {b34} from Districts 3-4; "
                f"{es} of the {len(s) + len(b)} prefer Spanish")


def p_ed_cluster_decline():
    s25, both28 = gi_count("SRMC", 25), gi_count("SRMC", 28) + gi_count("BCMC", 28)
    peak = mean(gi_count("SRMC", d) for d in range(18, 23))
    return 90 <= s25 <= 98 and 14 <= both28 <= 22, f"SRMC GI visits: {peak:.0f} a day D+18 to D+22, {s25} on D+25; {both28} across both hospitals on D+28"


def p_ed_equity():
    P = plc010()
    low = lambda x: x["Patient_Tract"] in P
    rest = lambda x: x["Patient_Tract"] not in P
    a, b = rate(low, 42, 48) / rate(low, -30, -5), rate(rest, 42, 48) / rate(rest, -30, -5)
    return 1.25 <= a <= 1.6 and 0.92 <= b <= 1.12, f"visits around D+45 against the pre-storm baseline: low-income surge-zone tracts x{a:.2f}, all other areas x{b:.2f}"


# ---- hospital capacity
@lru_cache(maxsize=None)
def cap():
    return {(x["Facility_ID"].split("-")[1], day(x["Report_Date"])): x for x in rows("public_health/hospital_capacity.csv")}


def p_cap_prestorm():
    x = cap()[("SRMC", -2)]
    ok = (x["Licensed_Beds"] == "500" and x["Staffed_Beds_Available"] == "487" and x["Census_Target"] == "440" and x["Elective_Procedures_Postponed"] == "47"
          and x["Diesel_Tank_A_gal"] == "12000" and x["Diesel_Tank_B_gal"] == "11850" and x["Generator_Test"] == "PASS" and x["Est_Runtime_Days_At_Storm_Load"] == "9.2")
    return ok, (f"SRMC D-2: {x['Licensed_Beds']} licensed, {x['Staffed_Beds_Available']} available, target {x['Census_Target']}, {x['Elective_Procedures_Postponed']} electives postponed, "
                f"tanks {x['Diesel_Tank_A_gal']} / {x['Diesel_Tank_B_gal']} gal, generator test {x['Generator_Test']}, {x['Est_Runtime_Days_At_Storm_Load']} days at storm load")


def p_cap_generator_start():
    x = cap()[("SRMC", 0)]
    ok = x["Commercial_Power_Lost_UTC"] == "2027-09-14T06:17:03Z" and x["Generator_Start_UTC"] == "2027-09-14T06:17:26Z" and x["Power_Source"] == "GENERATOR"
    return ok, f"SRMC D0: commercial power lost {x['Commercial_Power_Lost_UTC']}, generator start {x['Generator_Start_UTC']} (23 seconds)"


def p_cap_surge():
    s, b = cap()[("SRMC", 2)], cap()[("BCMC", 2)]
    ok = (s["Inpatient_Census"] == "700" and f(s["Pct_Licensed_Occupancy"]) == 140.0 and s["ICU_Occupied"] == "48" and s["Hallway_Patients"] == "89"
          and s["Triage_Tent_Patients"] == "62" and b["Inpatient_Census"] == "331" and b["ED_Boarding"] == "44" and "GETAC" in s["Mutual_Aid"])
    return ok, (f"D+2: SRMC census {s['Inpatient_Census']} ({s['Pct_Licensed_Occupancy']}%), ICU {s['ICU_Occupied']}/{s['ICU_Beds']}, hallway {s['Hallway_Patients']}, "
                f"tent {s['Triage_Tent_Patients']}; BCMC {b['Inpatient_Census']} ({b['Pct_Licensed_Occupancy']}%), boarding {b['ED_Boarding']}; mutual aid: {s['Mutual_Aid'][:40]}")


def p_cap_fuel():
    c = cap()
    gen = all(c[("SRMC", d)]["Power_Source"] == "GENERATOR" for d in range(0, 8))
    hrs = [f(c[("SRMC", d)]["Fuel_Hours_Remaining"]) for d in range(0, 6)]
    ok = gen and all(h >= 24 for h in hrs[:5]) and hrs[5] < 24
    return ok, f"SRMC on generator D0 to D+7; fuel-hours remaining at noon: {', '.join(f'{h:.0f}' for h in hrs[:5])}, then {hrs[5]:.1f} on D+5 (tank A {c[('SRMC', 5)]['Diesel_Tank_A_gal']}, tank B {c[('SRMC', 5)]['Diesel_Tank_B_gal']} gal)"


def p_cap_restored():
    s, b = cap()[("SRMC", 8)], cap()[("BCMC", 8)]
    ok = (s["Commercial_Power_Restored_UTC"] == "2027-09-22T14:14:33Z" and s["Power_Source"] == "COMMERCIAL" and s["Inpatient_Census"] == "540"
          and b["Inpatient_Census"] == "298" and abs(f(s["Generator_Hours_Cumulative"]) - 195.05) < 0.1)
    return ok, (f"SRMC D+8: commercial power restored {s['Commercial_Power_Restored_UTC']} (09:14 CDT), generator run-hours {s['Generator_Hours_Cumulative']}, "
                f"census {s['Inpatient_Census']} ({s['Pct_Licensed_Occupancy']}%); BCMC {b['Inpatient_Census']}")


def p_cap_below():
    c = cap()
    over = all(int(c[("SRMC", d)]["Inpatient_Census"]) >= 500 for d in range(0, 28))
    x = c[("SRMC", 28)]
    ok = over and x["Inpatient_Census"] == "475" and f(x["Pct_Licensed_Occupancy"]) == 95.0
    return ok, f"SRMC census at or above 500 every day D0 to D+27, then {x['Inpatient_Census']} ({x['Pct_Licensed_Occupancy']}%) on D+28; BCMC {c[('BCMC', 28)]['Inpatient_Census']}"


# ---- syndromic
@lru_cache(maxsize=None)
def syn():
    out = []
    for x in rows("public_health/syndrome_summary.csv"):
        x["_d"] = day(x["Report_Date"])
        x["_n"] = int(x["Visit_Count"])
        out.append(x)
    return out


def srate(cond, lo, hi):
    return sum(x["_n"] for x in syn() if lo <= x["_d"] <= hi and cond(x)) / (hi - lo + 1)


def matches_line_list():
    a = Counter()
    for x in visits():
        a[(x["Visit_Date"], x["Facility_ID"], "AREA-ZIP-" + x["Patient_ZIP"], x["CC_Category"])] += 1
    b = {(x["Report_Date"], x["Facility_ID"], x["Area_ID"], x["CC_Category"]): x["_n"] for x in syn()}
    return dict(a) == b


def p_syn_irritant():
    ir = lambda x: x["CC_Category"] == "IRRITANT"
    base = srate(ir, -30, -5)
    tot = sum(x["_n"] for x in syn() if 2 <= x["_d"] <= 5 and ir(x))
    near = sum(x["_n"] for x in syn() if 2 <= x["_d"] <= 5 and ir(x) and x["Area_ID"] in ("AREA-ZIP-78407", "AREA-ZIP-78408", "AREA-ZIP-78402", "AREA-ZIP-78401"))
    ok = base <= 2 and tot >= 30 and near / tot >= 0.75 and matches_line_list()
    return ok, f"odour and irritation complaints: {base:.1f} a day at baseline, {tot} over D+2 to D+5, {100 * near / max(1, tot):.0f}% from the ZIP codes beside the channel; summary equals the line list"


def p_syn_shoreline():
    zips = {"AREA-ZIP-78402", "AREA-ZIP-78401", "AREA-ZIP-78407", "AREA-ZIP-78408", "AREA-ZIP-78374"}
    c = lambda x: x["Area_ID"] in zips and x["CC_Category"] in ("RESP", "SKIN")
    o = lambda x: x["Area_ID"] not in zips and x["CC_Category"] in ("RESP", "SKIN")
    a, b = srate(c, 3, 21) / srate(c, -30, -5), srate(o, 3, 21) / srate(o, -30, -5)
    return a >= 1.3 and a > b + 0.15, f"respiratory and skin counts D+3 to D+21: shoreline ZIP areas x{a:.2f} of baseline, other areas x{b:.2f}"


def p_syn_gi_wave():
    allgi = lambda x: x["CC_Category"] == "GI"
    others = lambda x: x["CC_Category"] == "GI" and x["Facility_ID"] not in ("FAC-SRMC-001", "FAC-BCMC-002")
    base, peak = srate(allgi, -30, -5), srate(allgi, 6, 13)
    o_base, o_peak, o_late = srate(others, -30, -5), srate(others, 6, 13), srate(others, 21, 27)
    ok = peak / base >= 2.4 and o_peak >= 2.0 * o_base and o_late <= 0.6 * o_peak and matches_line_list()
    return ok, (f"GI counts: {base:.1f} a day at baseline, {peak:.1f} a day D+6 to D+13; at the five hospitals outside the later Districts 3-4 cluster "
                f"{o_base:.1f} -> {o_peak:.1f} -> {o_late:.1f} a day by D+21 to D+27; summary equals the line list")


def both_gi(d):
    return sum(x["_n"] for x in syn() if x["_d"] == d and x["CC_Category"] == "GI" and x["Facility_ID"] in ("FAC-SRMC-001", "FAC-BCMC-002"))


def p_syn_cluster_peak():
    v = [both_gi(d) for d in range(18, 23)]
    return all(320 <= x <= 360 for x in v), f"GI cases a day at SRMC and BCMC, D+18 to D+22: {v}"


def p_syn_curve():
    v = {d: both_gi(d) for d in range(14, 30)}
    ok = v[15] < v[16] < v[17] < v[18] and min(v[d] for d in range(18, 23)) > v[17] and v[23] > v[24] > v[25] > v[26] > v[27] > v[28]
    return ok, "GI cases a day at both hospitals by visit date, D+14 to D+29: " + ", ".join(str(v[d]) for d in range(14, 30)) + " (onset dates are in the line list)"


def p_ww():
    r = [x for x in rows("public_health/wastewater_surveillance.csv") if x["target"].startswith("Norovirus")]
    pre = median([f(x["concentration_gc_per_L"]) for x in r if day(x["sample_date"]) < -1])
    early = [f(x["concentration_gc_per_L"]) for x in r if 0 <= day(x["sample_date"]) <= 4]
    wave = median([f(x["concentration_gc_per_L"]) for x in r if 5 <= day(x["sample_date"]) <= 14])
    late = median([f(x["concentration_gc_per_L"]) for x in r if 30 <= day(x["sample_date"]) <= 50])
    ok = wave >= 3 * pre and (not early or max(early) < 2.5 * pre) and late < 1.6 * pre
    return ok, f"norovirus GII median: {pre:,.0f} gc/L before the storm, {wave:,.0f} over D+5 to D+14 (x{wave / pre:.1f}), {late:,.0f} by D+30 to D+50"


# ======================================================================================
def _text_health():
    seen = set()
    for x in visits():
        if x["Chief_Complaint_Text"] not in seen:
            seen.add(x["Chief_Complaint_Text"])
            yield x["Chief_Complaint_Text"]
    for x in rows("public_health/hospital_capacity.csv"):
        yield " ".join([x["Facility_Name"], x["Mutual_Aid"], x["Diversion_Status"]])


def _text_names(pattern, cols):
    def gen():
        seen = set()
        for rel in files(pattern):
            r = rows(rel)
            if r:
                s = " ".join(str(r[0].get(c, "")) for c in cols)
                if s not in seen:
                    seen.add(s)
                    yield s
    return gen


def _adv_text():
    for x in advisories()["advisories"]:
        yield x["headline"] + " " + " ".join(x["watches_and_warnings"])


FAC_IDS = lambda: {x["facility_id"] for x in reg("facility_registry")["facilities"]}
AREA_IDS = lambda: {x["area_id"] for x in reg("areas")["areas"]}

STREAMS = {
    "weather": {
        "time_range": lambda: span_of("weather/*_observations.csv", "ObsDateTime"),
        "ids": lambda: ids_in("weather/*_observations.csv", "StationID"),
        "registry_ids": lambda: sensor_ids("weather_stations", "buoys"),
        "public_voice": False, "text": _text_names("weather/*_observations.csv", ["StationName"]),
        "columns": lambda: header("weather/*_observations.csv"),
    },
    "storm_advisories": {
        "time_range": lambda: (min(E(x["issued_utc"]) for x in advisories()["advisories"]), max(E(x["issued_utc"]) for x in advisories()["advisories"])),
        "public_voice": True, "text": _adv_text,
        "columns": lambda: sorted(advisories()["advisories"][0].keys()),
    },
    "tide_river_gauges": {
        "time_range": lambda: span_of("env_sensors/gauge_*.csv", "ObsDateTime"),
        "ids": lambda: ids_in("env_sensors/gauge_*.csv", "SensorID"),
        "registry_ids": lambda: sensor_ids("tide_gauges", "stream_gauges"),
        "public_voice": False, "text": _text_names("env_sensors/gauge_*.csv", ["SensorName"]),
        "columns": lambda: header("env_sensors/gauge_*.csv"),
    },
    "water_quality": {
        "time_range": lambda: span_of("env_sensors/water_quality_*.csv", "ObsDateTime"),
        "ids": lambda: ids_in("env_sensors/water_quality_*.csv", "SensorID"),
        "registry_ids": lambda: sensor_ids("water_quality_sondes"),
        "public_voice": False, "text": _text_names("env_sensors/water_quality_*.csv", ["SensorName"]),
        "columns": lambda: header("env_sensors/water_quality_*.csv"),
    },
    "air_quality": {
        "time_range": lambda: span_of("env_sensors/aqs_*.csv", aqt),
        "ids": lambda: ids_in("env_sensors/aqs_*.csv", "SensorID"),
        "registry_ids": lambda: sensor_ids("air_monitors"),
        "public_voice": False, "text": _text_names("env_sensors/aqs_*.csv", ["Site_Name"]),
        "columns": lambda: header("env_sensors/aqs_*.csv"),
    },
    "wastewater": {
        "time_range": lambda: span_of("public_health/wastewater_surveillance.csv", "sample_date", end_of_day=True),
        "ids": lambda: ids_in("public_health/wastewater_surveillance.csv", "sewershed_id"),
        "registry_ids": lambda: {x["asset_id"] for x in reg("infrastructure_assets")["assets"]},
        "public_voice": False, "text": _text_names("public_health/wastewater_surveillance.csv", ["site_name"]),
        "columns": lambda: header("public_health/wastewater_surveillance.csv"),
    },
    "ed_visits": {
        "time_range": lambda: (min(E(x["Arrive_Date_Time"]) for x in visits()), max(E(x["Arrive_Date_Time"]) for x in visits())),
        "ids": lambda: {x["Facility_ID"] for x in visits()} | {"AREA-ZIP-" + x["Patient_ZIP"] for x in visits()} | {"AREA-TRACT-" + x["Patient_Tract"] for x in visits() if x["Patient_Tract"]},
        "registry_ids": lambda: FAC_IDS() | AREA_IDS(),
        "public_voice": True, "text": _text_health,
        "columns": lambda: header("public_health/ed_visits_*.csv"),
    },
    "hospital_capacity": {
        "time_range": lambda: span_of("public_health/hospital_capacity.csv", "Report_Date", end_of_day=True),
        "ids": lambda: ids_in("public_health/hospital_capacity.csv", "Facility_ID"),
        "registry_ids": FAC_IDS,
        "public_voice": True, "text": _text_health,
        "columns": lambda: header("public_health/hospital_capacity.csv"),
    },
    "syndromic": {
        "time_range": lambda: span_of("public_health/syndrome_summary.csv", "Report_Date", end_of_day=True),
        "ids": lambda: ids_in("public_health/syndrome_summary.csv", "Facility_ID") | ids_in("public_health/syndrome_summary.csv", "Area_ID"),
        "registry_ids": lambda: FAC_IDS() | AREA_IDS(),
        "public_voice": False,
        "columns": lambda: header("public_health/syndrome_summary.csv"),
    },
}

PROBES = {
    ("EVT-0203", "weather"): p_weather_soak,
    ("EVT-0202", "weather"): p_weather_buoy,
    ("EVT-0301", "weather"): p_weather_landfall,
    ("EVT-0202", "storm_advisories"): p_adv_formation,
    ("EVT-0301", "storm_advisories"): p_adv_landfall,
    ("EVT-0203", "tide_river_gauges"): p_gauge_river,
    ("EVT-0301", "tide_river_gauges"): p_gauge_surge,
    ("EVT-0313", "water_quality"): p_wq_nearest,
    ("EVT-2001", "water_quality"): p_wq_wq01,
    ("EVT-0314", "water_quality"): p_wq_sequence,
    ("EVT-2002", "water_quality"): p_wq_network,
    ("EVT-2006", "water_quality"): p_wq_nueces,
    ("EVT-2008", "water_quality"): p_wq_d20,
    ("EVT-2009", "water_quality"): p_wq_d60,
    ("EVT-0314", "air_quality"): p_aq_channel,
    ("EVT-2004", "air_quality"): p_aq_hillcrest,
    ("EVT-0310", "wastewater"): p_ww,
    ("EVT-0101", "ed_visits"): p_ed_baseline,
    ("EVT-1602", "ed_visits"): p_ed_srmc_d0,
    ("EVT-0317", "ed_visits"): p_ed_shoreline,
    ("EVT-0310", "ed_visits"): p_ed_gi_wave,
    ("EVT-1607", "ed_visits"): p_ed_cluster_peak,
    ("EVT-1606", "ed_visits"): p_ed_cluster_start,
    ("EVT-1609", "ed_visits"): p_ed_cluster_decline,
    ("EVT-0408", "ed_visits"): p_ed_equity,
    ("EVT-1601", "hospital_capacity"): p_cap_prestorm,
    ("EVT-1602", "hospital_capacity"): p_cap_generator_start,
    ("EVT-1603", "hospital_capacity"): p_cap_surge,
    ("EVT-1604", "hospital_capacity"): p_cap_fuel,
    ("EVT-1605", "hospital_capacity"): p_cap_restored,
    ("EVT-1609", "hospital_capacity"): p_cap_below,
    ("EVT-2004", "syndromic"): p_syn_irritant,
    ("EVT-0317", "syndromic"): p_syn_shoreline,
    ("EVT-0310", "syndromic"): p_syn_gi_wave,
    ("EVT-1607", "syndromic"): p_syn_cluster_peak,
    ("EVT-1608", "syndromic"): p_syn_curve,
}
