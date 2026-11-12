"""Environment streams: weather, storm advisories, tide and river gauges, water quality, air quality.

    python3 scripts/streams/gen_environment.py            all five
    python3 scripts/streams/gen_environment.py weather    one (weather | advisories | gauges | water | air)

Everything is driven by scripts/streams/envmodel.py (one atmosphere, one hurricane) and by the
spill, storm and outage facts in 00_scenario/canon_timeline.json. Deterministic.
"""
import glob
import math
import os
import sys

import numpy as np

from common import (D0_EPOCH, LANDFALL, SPAN_END, SPAN_START, ROOT, canon, iso, local_dt, reg, retire, rng, ts,
                    write_csv, out_path)
from envmodel import Env, KT, H, _bearing

ENV = None


def env():
    global ENV
    if ENV is None:
        ENV = Env()
    return ENV


def rel_old(pattern):
    return [os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, pattern))]


def supersede(rel_paths, current_headers):
    """Clear a stream's files before writing. Files left by the previous generation of the corpus
    (different header) are moved to _versions once with common.retire; files this generator wrote
    on an earlier run are simply deleted, so re-running never overwrites the retired originals."""
    heads = [",".join(h) for h in current_headers]
    old = []
    for rel in rel_paths:
        fp = os.path.join(ROOT, rel)
        if not os.path.isfile(fp):
            continue
        with open(fp, encoding="utf-8", errors="replace") as fh:
            first = fh.readline().strip()
        if first in heads or (rel.endswith(".json") and '"best_track"' in open(fp, encoding="utf-8").read()[-4000000:]):
            os.remove(fp)
        else:
            old.append(rel)
    return retire(old)


def pwl(knots, t):
    """Piecewise-linear value through [(epoch, value), ...]; flat outside."""
    xs = [k[0] for k in knots]
    ys = [k[1] for k in knots]
    return float(np.interp(t, xs, ys))


def in_any(t, windows):
    return any(a <= t < b for a, b in windows)


# ======================================================================================
# weather stations and buoys
# ======================================================================================
# id: (USAF, WBAN, elevation m, land exposure, coastal factor, storm outage (first missing, first back))
STATIONS = {
    "KCRP": ("722510", "12924", 13, 0.80, 1.00, ("2027-09-14T10:40Z", "2027-09-14T16:40Z")),
    "KNGP": ("722515", "12926", 5, 0.88, 0.60, ("2027-09-14T07:55Z", "2027-09-15T15:40Z")),
    "KNGW": ("", "", 9, 0.80, 0.90, ("2027-09-14T08:40Z", "2027-09-16T02:40Z")),
    "KRAS": ("", "", 2, 0.90, 0.45, ("2027-09-14T06:40Z", "2027-09-19T16:40Z")),
    "KRKP": ("722524", "12972", 7, 0.86, 0.60, ("2027-09-14T07:40Z", "2027-09-16T13:40Z")),
    "KTFP": ("", "", 4, 0.85, 0.70, ("2027-09-14T06:20Z", "2027-09-17T14:40Z")),
    "KNQI": ("722516", "12928", 15, 0.76, 1.25, None),
}
WX_HEADER = ["USAF", "WBAN", "StationID", "StationName", "StnLat", "StnLon", "StnElev_m", "ObsDateTime", "ReportType",
             "SkyCondition", "CloudBaseAGL_ft", "Visibility_m", "PresentWx", "DryBulbTemp_C", "DewPoint_C",
             "RelativeHumidity_pct", "WindDir_deg", "WindSpeed_mps", "WindGust_mps", "StationPressure_mb",
             "SeaLevelPressure_mb", "Precip1hr_mm", "Remarks"]
BUOY_HEADER = ["StationID", "StationName", "StnLat", "StnLon", "ObsDateTime", "WDIR_degT", "WSPD_mps", "GST_mps",
               "WVHT_m", "DPD_s", "APD_s", "MWD_degT", "PRES_mb", "ATMP_C", "WTMP_C", "DEWP_C"]
STORM_SPECI = (ts("2027-09-13T18:00Z"), ts("2027-09-14T18:00Z"))


def rh(T, Td):
    es = lambda x: 6.112 * math.exp(17.67 * x / (x + 243.5))
    return max(5, min(100, round(100 * es(Td) / es(T))))


def station_obs(E, sid, st, t, g, rain1h):
    usaf, wban, elev, land, coastal, _ = STATIONS[sid]
    lat, lon = st["latitude"], st["longitude"]
    T, Td = E.temp(t, lat, lon, coastal)
    T += g.normal(0, 0.25)
    Td = min(Td + g.normal(0, 0.25), T - 0.2)
    spd, d, r = E.wind(t, lat, lon, land, coastal)
    storm = r is not None and spd > 14
    spd *= 1 + g.normal(0, 0.05 if storm else 0.12)
    spd = max(0.0, spd)
    d = (d + g.normal(0, 4 if storm else 9)) % 360
    gust = ""
    if storm:
        gust = spd * (1.24 + 0.12 * g.random())
    elif spd >= 6.5 and g.random() < 0.7:
        gust = spd * (1.32 + 0.22 * g.random())
    slp = E.slp(t, lat, lon) + g.normal(0, 0.12)
    stp = slp * math.exp(-elev / 8434.0)
    # sky, visibility, weather
    lh = E.local_hour(t)
    humid = Td > T - 2.0
    cool, dry, north, _, since, s = E._front_terms(t)
    wx, vis = "", 16093
    if rain1h >= 7.6:
        wx, vis = "+RA", int(max(600, 4200 - rain1h * 90 + g.normal(0, 200)))
    elif rain1h >= 2.5:
        wx, vis = "RA", int(max(2400, 9000 - rain1h * 550 + g.normal(0, 400)))
    elif rain1h > 0:
        wx, vis = "-RA", int(max(6000, 14000 - rain1h * 1500 + g.normal(0, 600)))
    if storm and spd > 25:
        vis = int(min(vis, max(400, 2400 - spd * 30)))
        wx = "+RA" if rain1h >= 4 else (wx or "RA")
    if wx and rain1h >= 6 and not storm and lh > 12 and T > 24 and g.random() < 0.45:
        wx = "TS" + wx.replace("-", "")
    if not wx and humid and spd < 2.6 and (lh < 8.5 or lh > 22.5) and g.random() < 0.55:
        v = int(max(300, g.gamma(2.0, 1800)))
        if v < 9000:
            vis, wx = v, ("FG" if v < 1000 else "BR")
    if rain1h > 0 or (storm and spd > 18):
        sky, base = "OVC", int(max(300, 2600 - rain1h * 110 - (spd * 25 if storm else 0) + g.normal(0, 200)))
    elif since < 14 and s > 0.3:
        sky, base = "BKN", int(1800 + g.normal(0, 300))
    elif since < 60 and dry > 3:
        sky, base = ("CLR", 0) if g.random() < 0.8 else ("FEW", 12000)
    elif wx in ("FG", "BR"):
        sky, base = ("OVC", 200) if wx == "FG" else ("BKN", 600)
    elif humid and 5 < lh < 10:
        sky, base = ("BKN" if g.random() < 0.6 else "SCT"), int(900 + g.normal(0, 200))
    else:
        c = g.random()
        sky = "CLR" if c < 0.22 else ("FEW" if c < 0.55 else ("SCT" if c < 0.85 else "BKN"))
        base = 0 if sky == "CLR" else int(max(1500, 3200 + 220 * (T - Td) + g.normal(0, 400)))
    base = int(round(base / 100.0) * 100)
    wd = int(round(d / 10.0) * 10) % 360 or 360
    if spd < 0.6:
        spd, wd = 0.0, 0
    rem = ""
    if storm and gust and gust / KT >= 64:
        rem = f"PK WND {wd:03d}{int(round(gust / KT)):03d}"
    return [usaf, wban, sid, st["sensor_name"], st["latitude"], st["longitude"], elev, None, None, sky, base, vis, wx,
            round(T, 1), round(Td, 1), rh(T, Td), wd, round(spd, 1), (round(gust, 1) if gust else ""), round(stp, 1),
            round(slp, 1), round(rain1h, 1), rem]


def gen_weather():
    E = env()
    S = reg("sensor_registry")
    supersede(rel_old("05_other_sources/weather/*_observations.csv") + rel_old("05_other_sources/weather/_consolidated/*"), [WX_HEADER, BUOY_HEADER])
    totals = {}
    for st in S["weather_stations"]:
        sid = st["sensor_id"]
        g = rng("weather", sid)
        out = STATIONS[sid][5]
        outages = [(ts(out[0]), ts(out[1]))] if out else []
        # routine short gaps (maintenance, comms): about three a season
        for _ in range(int(g.integers(2, 5))):
            a = SPAN_START + int(g.integers(5, 140)) * 86400 + int(g.integers(0, 24)) * H
            if abs(a - LANDFALL) > 12 * 86400:
                outages.append((a, a + int(g.integers(2, 7)) * H))
        rain = E.rain_series(sid, st["latitude"], st["longitude"])
        rows = []
        t = SPAN_START
        while t < SPAN_END:
            times = [(t + 53 * 60, "FM-15")]
            if STORM_SPECI[0] <= t < STORM_SPECI[1]:
                times = [(t + 13 * 60, "FM-16"), (t + 33 * 60, "FM-16"), (t + 53 * 60, "FM-15")]
            for tt, rt in times:
                if in_any(tt, outages):
                    continue
                i = int((tt - E.t0) // H)
                r1 = float(rain[i]) if rt == "FM-15" else float(rain[i]) * ((tt - t) / 3600.0)
                row = station_obs(E, sid, st, tt, g, r1)
                row[7], row[8] = iso(tt, z=False), rt
                rows.append(row)
            t += H
        totals[sid] = write_csv(f"05_other_sources/weather/{sid}_ASOS_observations.csv", WX_HEADER, rows)
    for st in S["buoys"]:
        sid = st["sensor_id"]
        g = rng("weather", "buoy", sid)
        lat, lon = st["latitude"], st["longitude"]
        rows = []
        swell_mem = 0.0
        t = SPAN_START
        while t < SPAN_END:
            tt = t + 50 * 60
            spd, d, r = E.wind(tt, lat, lon, 0.74, 0.3)
            spd = max(0.2, spd * (1 + g.normal(0, 0.07)))
            d = (d + g.normal(0, 7)) % 360
            gust = spd * (1.18 + 0.1 * g.random())
            T, Td = E.temp(tt, lat, lon, 0.25, water=True)
            sst = pwl([(ts("2027-08-15T00:00Z"), 30.3), (ts("2027-09-12T00:00Z"), 29.6), (ts("2027-10-15T00:00Z"), 27.2),
                       (ts("2027-11-15T00:00Z"), 23.6), (ts("2027-12-15T00:00Z"), 20.4), (ts("2028-01-12T00:00Z"), 18.6)], tt)
            storm = E.storm(tt)
            swell = 0.0
            per_sw = 0.0
            if storm and storm["vmax_kt"] >= 40 and storm["lat"] >= 20.9 and storm["lon"] < -88.0:     # in the Gulf
                dist, brg = _bearing(storm["lat"], storm["lon"], lat, lon)
                swell = 0.034 * storm["vmax_kt"] * (150.0 / (dist + 110.0))
                per_sw = min(14.5, 9.5 + dist / 110.0)
                mwd = (brg + 180) % 360
            # upwelling and mixing cool the water after the storm passes
            if tt > ts("2027-09-13T06:00Z"):
                dmin = 2.6 if sid == "42020" else 90.6
                sst -= (2.8 if dmin < 30 else 0.8) * math.exp(-(tt - ts("2027-09-14T00:00Z")) / (12 * 86400.0)) * min(1.0, (tt - ts("2027-09-13T06:00Z")) / (12 * H))
            swell_mem = max(swell, swell_mem * 0.985)                          # swell lingers after the source moves on
            sea = 0.22 + 0.0165 * spd ** 2 if spd < 15 else min(11.5, 0.245 * spd + 0.25)
            hs = math.sqrt(sea ** 2 + swell_mem ** 2) * (1 + g.normal(0, 0.05))
            if swell_mem > 0.55 * sea and per_sw:
                dpd, mw = per_sw + g.normal(0, 0.4), mwd
            else:
                dpd, mw = min(13.0, 3.6 + 0.62 * math.sqrt(max(sea, 0.1)) * 3.1 + g.normal(0, 0.3)), d
            apd = max(2.8, dpd * 0.72 + g.normal(0, 0.15))
            p = E.slp(tt, lat, lon) + g.normal(0, 0.12)
            rows.append([sid, st["sensor_name"], lat, lon, iso(tt, z=False), int(round(d)) % 360, round(spd, 1), round(gust, 1),
                         round(hs, 2), round(dpd, 1), round(apd, 1), int(round(mw)) % 360, round(p, 1),
                         round(min(T, sst + 2.5), 1), round(sst + g.normal(0, 0.05), 1), round(Td, 1)])
            t += H
        totals[sid] = write_csv(f"05_other_sources/weather/BUOY{sid}_observations.csv", BUOY_HEADER, rows)
    return totals


# ======================================================================================
# hurricane advisories
# ======================================================================================
def gen_advisories():
    import json
    E = env()
    supersede(["05_other_sources/weather/nhc_advisories.json"], [])
    name_at = ts("2027-09-04T09:00Z")          # named on the morning of D-10 (canon)
    cat3_at = ts("2027-09-13T09:00Z")          # upgraded to Category 3 on D-1 (canon)
    watch_at = ts("2027-09-11T15:00Z")         # hurricane watch, D-3
    warn_at = ts("2027-09-12T17:00Z")          # hurricane warning, 12:00 CDT D-2
    warn_end = ts("2027-09-14T18:00Z")
    issue_times = []
    t = ts("2027-09-02T15:00Z")
    while t <= ts("2027-09-15T15:00Z"):
        issue_times.append((t, False))
        if watch_at <= t < ts("2027-09-14T21:00Z"):
            issue_times.append((t + 3 * H, True))      # intermediate advisories while watches/warnings are up
        t += 6 * H
    issue_times.append((warn_at, "special"))
    issue_times.append((LANDFALL, "landfall"))
    issue_times.sort(key=lambda x: x[0])

    def op_wind(tt):
        st = E.storm(tt)
        v = st["vmax_kt"]
        if tt < name_at:
            v = min(v, 30)
        if tt < cat3_at:
            v = min(v, 95)
        return int(5 * round(v / 5.0)), st

    def cls(v, tt, st):
        if tt >= ts("2027-09-15T12:00Z"):
            return "Post-Tropical Cyclone"
        if v >= 64:
            return "Hurricane"
        return "Tropical Storm" if v >= 34 else "Tropical Depression"

    def cat(v):
        return 0 if v < 64 else 1 if v < 83 else 2 if v < 96 else 3 if v < 113 else 4

    out, num, last_full = [], 0, 0
    for tt, kind in issue_times:
        v, st = op_wind(tt)
        if kind is False:
            num += 1
            label = str(num)
        elif kind is True:
            label = f"{num}A"
        elif kind == "special":
            num += 1
            label = str(num)
        else:
            label = f"{num}B"
        c = cls(v, tt, st)
        named = tt >= name_at
        nm = "Rafael" if named else "Nine"
        lead_err = max(0.0, (ts("2027-09-12T00:00Z") - tt) / (10 * 86400.0))    # older forecasts were less certain
        fc = []
        for tau in (12, 24, 36, 48, 72, 96, 120):
            f = E.storm(tt + tau * H)
            if not f:
                continue
            g = rng("advisory", label, tau)
            fc.append({"tau_h": tau, "valid_utc": iso(tt + tau * H, seconds=False),
                       "lat": round(f["lat"] + lead_err * tau / 120.0 * float(g.normal(0, 0.6)), 1),
                       "lon": round(f["lon"] + lead_err * tau / 120.0 * float(g.normal(0, 0.8)), 1),
                       "max_wind_kt": int(5 * round(min(f["vmax_kt"], 115) / 5.0)),
                       "cone_radius_nm": {12: 26, 24: 41, 36: 55, 48: 69, 72: 102, 96: 151, 120: 198}[tau]})
        ww = []
        if watch_at <= tt < warn_at:
            ww = ["Hurricane Watch: Baffin Bay to Sargent, Texas, including Corpus Christi Bay",
                  "Storm Surge Watch: Baffin Bay to Sargent, Texas"]
        elif warn_at <= tt < warn_end:
            ww = ["Hurricane Warning: Baffin Bay to Port O'Connor, Texas, including Nueces County and Corpus Christi Bay",
                  "Storm Surge Warning: Baffin Bay to Port O'Connor, Texas",
                  "Tropical Storm Warning: Port Mansfield to Baffin Bay and Port O'Connor to Sargent, Texas"]
        dist_cc, _ = _bearing(st["lat"], st["lon"], 27.80, -97.40)
        if kind == "landfall":
            head = ("Hurricane Rafael makes landfall on Mustang Island near Port Aransas, Texas, as a Category 3 hurricane "
                    "at 0600 UTC (100 AM CDT)")
        elif kind == "special":
            head = "Hurricane Warning issued for the Texas Coastal Bend; Rafael expected near Port Aransas early Tuesday"
        elif not named:
            head = "Tropical Depression Nine moving west-northwest over the northwestern Caribbean Sea"
        elif tt == name_at:
            head = "Tropical Storm Rafael forms in the northwestern Caribbean Sea"
        elif tt < ts("2027-09-08T06:00Z"):
            head = "Rafael crossing the Yucatan Peninsula toward the southern Gulf" if ts("2027-09-06T12:00Z") <= tt else "Tropical Storm Rafael heading for the Yucatan Peninsula"
        elif tt < ts("2027-09-09T12:00Z"):
            head = "Rafael becomes a hurricane over the southern Gulf"
        elif tt < watch_at:
            head = "Hurricane Rafael strengthening over the Gulf; forecast cone now includes the Texas Coastal Bend"
        elif tt < warn_at:
            head = "Hurricane Watch in effect for the Texas Coastal Bend"
        elif tt < cat3_at:
            head = "Rafael moving slowly toward the Texas coast; preparations should be rushed to completion"
        elif tt < LANDFALL:
            head = "Rafael is now a Category 3 hurricane; life-threatening storm surge of 9 to 12 feet expected near Port Aransas"
        elif tt < ts("2027-09-14T18:00Z"):
            head = "Rafael weakening inland over South Texas; life-threatening flooding continues"
        elif tt < ts("2027-09-15T09:00Z"):
            head = "Rafael weakens to a tropical storm inland; all coastal warnings discontinued"
        else:
            head = "Rafael becomes a remnant low over south-central Texas; this is the last advisory"
        cone_points = [(f["lat"], f["lon"], f["cone_radius_nm"]) for f in fc]
        cc_in_cone = any(_bearing(a, b, 27.80, -97.40)[0] <= r for a, b, r in cone_points)
        l = local_dt(tt)
        out.append({"advisory_number": label, "atcf_id": "AL092027", "storm_name": nm.upper(),
                    "advisory_type": {False: "public", True: "intermediate", "special": "special", "landfall": "tropical cyclone update"}[kind],
                    "issued_utc": iso(tt), "issued_local": l.strftime("%I%M %p CDT %a %b %d %Y").lstrip("0").upper(),
                    "classification": c, "saffir_simpson_category": cat(v) if c == "Hurricane" else None,
                    "center": {"lat": round(st["lat"], 1), "lon": round(st["lon"], 1)},
                    "max_sustained_winds_kt": v, "max_sustained_winds_mph": int(5 * round(v * 1.15078 / 5.0)),
                    "min_central_pressure_mb": int(round(st["pc_mb"])) if tt >= name_at else int(max(1004, round(st["pc_mb"]))),
                    "movement": f"{['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'][int((st['heading_deg'] + 11.25) // 22.5) % 16]} at {max(2, int(round(st['speed_kt'])))} kt",
                    "distance_to_corpus_christi_nm": int(round(dist_cc)), "headline": head, "watches_and_warnings": ww,
                    "forecast": fc, "corpus_christi_in_forecast_cone": bool(cc_in_cone),
                    "landfall": ({"time_utc": "2027-09-14T06:00Z", "location": "Mustang Island near Port Aransas, Texas",
                                  "lat": 27.75, "lon": -97.13, "category": 3, "max_sustained_winds_kt": 110,
                                  "min_central_pressure_mb": 943} if kind == "landfall" else None)})
    best = [{"time_utc": iso(D0_EPOCH + int(h * H), seconds=False), "lat": la, "lon": lo, "max_wind_kt": w, "min_pressure_mb": int(p),
             "status": ("HU" if w >= 64 else "TS" if w >= 34 else "TD") if h <= 36 else "LO"} for h, la, lo, w, p in E.trk]
    doc = {"storm": "Rafael", "atcf_id": "AL092027", "basin": "Atlantic", "season": 2027,
           "source_format": "National Hurricane Center public advisories and HURDAT2-style best track",
           "times": "UTC; issued_local is US Central", "count": len(out), "advisories": out, "best_track": best}
    with open(out_path("05_other_sources/weather/nhc_advisories.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
    return {"advisories": len(out), "best_track": len(best)}


# ======================================================================================
# tide and river gauges
# ======================================================================================
FT = 3.28084
# id: K1, O1, M2, S2 amplitudes (m), mean above MLLW (m), bay factor for wind set-down, surge peak (m), peak time, rise h, fall h, outage
TIDE = {
    "TG-8775870": (0.140, 0.130, 0.080, 0.022, 0.30, 0.4, 2.10, "2027-09-14T03:40Z", 4.0, 3.5, ("2027-09-14T04:12Z", "2027-09-26T15:00Z")),
    "TG-8775241": (0.120, 0.112, 0.068, 0.018, 0.27, 0.5, 3.05, "2027-09-14T05:50Z", 4.2, 4.5, ("2027-09-14T06:06Z", "2027-09-23T15:00Z")),
    "TG-8775237": (0.095, 0.090, 0.055, 0.015, 0.23, 0.7, 3.42, "2027-09-14T06:10Z", 4.2, 5.0, None),
    "TG-8775792": (0.050, 0.045, 0.020, 0.006, 0.15, 1.0, 1.75, "2027-09-14T04:40Z", 4.5, 2.2, None),
    "GAUGE-14": (0.045, 0.040, 0.020, 0.006, 0.14, 1.0, 3.40, "2027-09-14T07:20Z", 4.6, 6.5, ("2027-09-14T04:48Z", "2027-09-19T14:00Z")),
    "TG-8774770": (0.035, 0.030, 0.012, 0.004, 0.12, 1.0, 2.55, "2027-09-14T07:40Z", 4.8, 7.0, ("2027-09-14T08:06Z", "2027-09-14T20:30Z")),
}
TIDE_HEADER = ["SensorID", "StationNumber", "SensorName", "Latitude", "Longitude", "ObsDateTime", "WaterLevel_ft_MLLW",
               "Predicted_ft_MLLW", "Residual_ft", "AirTemp_C", "WaterTemp_C", "WindSpeed_kt", "WindGust_kt",
               "BaroPressure_mb", "Sigma_ft", "Quality"]
STREAM_HEADER = ["SensorID", "SensorName", "Latitude", "Longitude", "ObsDateTime", "Stage_ft", "Discharge_cfs",
                 "WaterTemp_C", "SpecificConductance_uScm", "Quality"]


def predicted_tide_m(sid, t):
    k1, o1, m2, s2, mean, *_ = TIDE[sid]
    hrs = (t - D0_EPOCH) / 3600.0
    ph = {"TG-8775870": 0.0, "TG-8775241": 0.25, "TG-8775237": 0.5, "TG-8775792": 2.2, "GAUGE-14": 2.9, "TG-8774770": 3.6}[sid]
    seasonal = 0.11 * math.cos(2 * math.pi * (t - ts("2027-10-05T00:00Z")) / (365.25 * 86400))
    return (mean + seasonal
            + k1 * math.cos(2 * math.pi * (hrs - ph) / 23.934 - 0.6)
            + o1 * math.cos(2 * math.pi * (hrs - ph) / 25.819 - 2.1)
            + m2 * math.cos(2 * math.pi * (hrs - ph) / 12.421 - 1.2)
            + s2 * math.cos(2 * math.pi * (hrs - ph) / 12.0 - 0.3))


def surge_at(sid, t):
    """Storm surge residual (m) at a tide gauge."""
    *_, peak, tp, rise, fall, _ = TIDE[sid]
    tp = ts(tp)
    dh = (t - tp) / 3600.0
    fore = 0.38 / (1 + math.exp(-(t - ts("2027-09-13T10:00Z")) / (5 * 3600.0))) if dh < 0 else 0.0
    if dh < -60:
        return 0.0
    if dh < 0:
        return fore + (peak - 0.38) * math.exp(-((dh / rise) ** 2))
    if sid == "TG-8775792":                         # left of the track: offshore wind empties the lagoon after the peak
        return peak * math.exp(-dh / fall) - 0.55 * math.exp(-((dh - 5.0) / 3.5) ** 2) + 0.25 * math.exp(-dh / 40.0) * (1 - math.exp(-dh / 6.0))
    tail = 0.42 * math.exp(-dh / 38.0)
    return (peak - 0.42) * math.exp(-dh / fall) + tail


def bay_level_m(t, E):
    """Surge + weather residual used for harbour sondes (Inner Harbor follows the bay)."""
    return surge_at("GAUGE-14", t)


def gen_gauges():
    E = env()
    S = reg("sensor_registry")
    supersede(rel_old("05_other_sources/env_sensors/gauge_*.csv"), [TIDE_HEADER, STREAM_HEADER])
    totals = {}
    for st in S["tide_gauges"]:
        sid = st["sensor_id"]
        g = rng("gauges", sid)
        lat, lon = st["latitude"], st["longitude"]
        bay = TIDE[sid][5]
        out = TIDE[sid][10]
        outages = [(ts(out[0]), ts(out[1]))] if out else []
        for _ in range(int(g.integers(1, 4))):
            a = SPAN_START + int(g.integers(3, 145)) * 86400 + int(g.integers(0, 240)) * 360
            if abs(a - LANDFALL) > 14 * 86400:
                outages.append((a, a + int(g.integers(3, 30)) * 360))
        rows = []
        slow = 0.0
        t = SPAN_START
        wtemp_noise = 0.0
        while t < SPAN_END:
            if t % 3600 == 0:
                cool, dry, north, _, since, s = E._front_terms(t)
                slow += (-(0.030 * bay) * north + 0.035 * E._an(E.an_W, t) - slow) * 0.12     # hourly relaxation
                spd, d, r = E.wind(t, lat, lon, 0.85, 0.4)
                T, Td = E.temp(t, lat, lon, 0.45)
                p = E.slp(t, lat, lon)
                wtemp_noise = 0.9 * wtemp_noise + float(g.normal(0, 0.05))
            if not in_any(t, outages):
                pred = predicted_tide_m(sid, t)
                storm = surge_at(sid, t)
                chop = 0.012 + 0.0012 * spd ** 1.5
                resid = slow + storm + float(g.normal(0, 0.008))
                wl = pred + resid
                sst = pwl([(ts("2027-08-15T00:00Z"), 30.6), (ts("2027-09-13T00:00Z"), 29.4), (ts("2027-09-16T00:00Z"), 26.6),
                           (ts("2027-10-15T00:00Z"), 26.0), (ts("2027-11-15T00:00Z"), 21.0), (ts("2027-12-15T00:00Z"), 16.4),
                           (ts("2028-01-12T00:00Z"), 14.8)], t) - 0.5 * min(8.0, cool) * 0.6 + wtemp_noise
                kt = spd / KT
                rows.append([sid, st["station_number"], st["sensor_name"], lat, lon, iso(t, z=False),
                             round(wl * FT, 2), round(pred * FT, 2), round(resid * FT, 2), round(T, 1), round(sst, 1),
                             round(kt * (1 + float(g.normal(0, 0.04))), 1), round(kt * (1.22 + 0.1 * float(g.random())), 1),
                             round(p, 1), round(chop * FT * (1 + 0.3 * float(g.random())), 2), "p"])
            t += 360
        totals[sid] = write_csv(f"05_other_sources/env_sensors/gauge_{sid}.csv", TIDE_HEADER, rows)
    # ---- stream gauges
    rain = E.rain_series("KCRP", 27.77335, -97.51298)
    hourly_t = np.arange(E.n) * H + E.t0
    for st in S["stream_gauges"]:
        sid = st["sensor_id"]
        g = rng("gauges", sid)
        river = sid == "GAUGE-12"
        # unit response to rain: slow basin for the river, flashy for the creek
        k = np.exp(-np.arange(0, 400) / (70.0 if river else 9.0)) * (1 - np.exp(-np.arange(0, 400) / (22.0 if river else 2.0)))
        k /= k.sum()
        resp = np.convolve(rain, k)[:E.n] * (0.062 if river else 0.26)                 # ft per mm of rain (lumped)
        if river:
            # the canon soaking fills the basin: a steady rise from D-7 into landfall, then the flood crest
            steady = np.interp(hourly_t, [ts("2027-09-07T05:00Z"), ts("2027-09-14T05:00Z"), ts("2027-09-16T20:00Z"),
                                          ts("2027-09-24T00:00Z"), ts("2027-10-10T00:00Z"), ts("2027-11-10T00:00Z")],
                               [0.0, 4.9, 9.6, 3.4, 1.1, 0.2], left=0.0, right=0.0)
            base = np.interp(hourly_t, [SPAN_START, ts("2027-09-07T00:00Z"), ts("2027-12-01T00:00Z"), SPAN_END], [3.9, 3.7, 4.3, 4.5])
            stage_h = base + steady + np.minimum(resp, 1.6) * np.where(steady > 0.3, 0.25, 1.0)
        else:
            base = np.full(E.n, 1.25)
            stage_h = base + np.minimum(resp, 9.5)
        outages = [(ts("2027-09-14T07:15Z"), ts("2027-09-14T15:00Z"))] if river else [(ts("2027-09-14T05:45Z"), ts("2027-09-15T19:00Z"))]
        rows = []
        t = SPAN_START
        noise = 0.0
        while t < SPAN_END:
            if not in_any(t, outages):
                x = (t - E.t0) / H
                i = int(x)
                stg = stage_h[i] * (1 - (x - i)) + stage_h[i + 1] * (x - i)
                if not river:                              # tidal reach: the surge backs up Oso Creek
                    stg += 0.85 * FT * surge_at("TG-8775792", t) * 0.9
                noise = 0.8 * noise + float(g.normal(0, 0.006))
                stg = max(0.4, stg + noise)
                q = (38.0 * max(0.05, stg - 2.3) ** 2.25) if river else (9.0 * max(0.05, stg - 0.6) ** 2.1)
                T, _ = E.temp(t, st["latitude"], st["longitude"], 0.8, water=True)
                sc = (980 - 55 * min(10.0, max(0.0, stg - 4.0))) if river else 0
                rows.append([sid, st["sensor_name"], st["latitude"], st["longitude"], iso(t, z=False), round(stg, 2),
                             round(q, 0 if q > 100 else 1), round(T - 0.8, 1) if river else "",
                             int(sc + float(g.normal(0, 8))) if river else "", "A" if t < ts("2027-12-15T00:00Z") else "P"])
            t += 900
        totals[sid] = write_csv(f"05_other_sources/env_sensors/gauge_{sid}.csv", STREAM_HEADER, rows)
    return totals


# ======================================================================================
# water-quality sondes
# ======================================================================================
def T0(day, hhmm="00:00"):
    h, m = map(int, hhmm.split(":"))
    return D0_EPOCH + day * 86400 + h * 3600 + m * 60


BASE_TPH = 20.0          # ppb (0.02 mg/L), canon baseline
# hydrocarbon signal above baseline, ppb, by sonde: [(epoch UTC, value)]
OIL = {
    "WQ-02": [(T0(0, "04:22"), 0), (T0(0, "04:40"), 160), (T0(0, "05:30"), 1750), (T0(0, "08:00"), 2100), (T0(1), 1900),
              (T0(2), 2400), (T0(3, "15:00"), 3380), (T0(4), 2900), (T0(5), 2300), (T0(7), 1500), (T0(10), 950),
              (T0(15), 660), (T0(20, "20:00"), 500), (T0(30), 255), (T0(44), 92), (T0(60), 17), (T0(63), 14), (T0(90), 4), (T0(119), 1)],
    "WQ-01": [(T0(0, "04:38"), 0), (T0(0, "04:50"), 110), (T0(0, "05:45"), 1500), (T0(0, "09:00"), 2250), (T0(1), 2400),
              (T0(2), 2550), (T0(3, "12:00"), 2800), (T0(4), 2650), (T0(5), 2300), (T0(7), 1750), (T0(10), 1150),
              (T0(15), 800), (T0(20, "20:00"), 580), (T0(30), 310), (T0(44), 135), (T0(60), 22), (T0(63), 18), (T0(90), 6), (T0(119), 2)],
    "WQ-05": [(T0(0, "06:05"), 0), (T0(0, "07:00"), 420), (T0(0, "12:00"), 1500), (T0(1), 1900), (T0(2, "12:00"), 2200),
              (T0(3, "12:00"), 2100), (T0(5), 1600), (T0(7), 1200), (T0(10), 840), (T0(15), 610), (T0(20, "20:00"), 460),
              (T0(30), 240), (T0(44), 100), (T0(60), 15), (T0(63), 13), (T0(90), 4), (T0(119), 1)],
    "WQ-06": [(T0(1, "08:00"), 0), (T0(1, "14:00"), 260), (T0(2), 700), (T0(2, "18:00"), 1300), (T0(3, "10:00"), 1900),
              (T0(4), 1500), (T0(5), 1150), (T0(7), 800), (T0(10), 520), (T0(15), 370), (T0(20, "20:00"), 280),
              (T0(30), 140), (T0(44), 55), (T0(60), 8), (T0(63), 7), (T0(90), 2), (T0(119), 1)],
    "WQ-03": [(T0(1, "20:00"), 0), (T0(2, "04:00"), 320), (T0(2, "18:00"), 760), (T0(3, "12:00"), 1400), (T0(4, "10:00"), 1850),
              (T0(4, "16:30"), 2080), (T0(4, "21:30"), 2080), (T0(5, "06:00"), 1800), (T0(6), 1500), (T0(8), 1100), (T0(10), 800),
              (T0(15), 520), (T0(20, "20:00"), 360), (T0(30), 180), (T0(44), 75), (T0(60), 10), (T0(63), 9), (T0(90), 3), (T0(119), 1)],
    "WQ-04": [(T0(2, "06:00"), 0), (T0(2, "16:00"), 130), (T0(3, "12:00"), 340), (T0(4, "12:00"), 310), (T0(6), 230),
              (T0(10), 160), (T0(15), 125), (T0(20, "20:00"), 100), (T0(30), 55), (T0(44), 22), (T0(60), 5), (T0(63), 4), (T0(90), 1), (T0(119), 0)],
}
# exact readings canon states: (sonde, epoch, total ppb)
PINS = [("WQ-02", T0(3, "15:00"), 3400.0), ("WQ-03", T0(4, "16:30"), 2100.0), ("WQ-03", T0(4, "21:30"), 2100.0)]
SONDE_OUT = {
    "WQ-01": [(T0(0, "09:15"), T0(0, "15:30"))],
    "WQ-02": [(T0(0, "08:30"), T0(1, "03:00"))],
    "WQ-05": [(T0(0, "08:00"), T0(0, "21:00"))],
    "WQ-06": [(T0(0, "05:15"), T0(1, "07:30"))],
    "WQ-03": [(T0(0, "05:45"), T0(1, "14:00"))],
    "WQ-04": [(T0(0, "04:30"), T0(1, "22:00"))],
}
WQ_HEADER = ["SensorID", "SensorName", "Latitude", "Longitude", "ObsDateTime", "WaterTemp_C", "SpecificConductance_uScm",
             "Salinity_psu", "DissolvedOxygen_mgL", "pH", "Turbidity_NTU", "TotalHydrocarbons_ppb", "Depth_m", "Battery_V", "QC"]


def tph_ppb(sid, t, g, state):
    sig = pwl(OIL[sid], t) if OIL[sid][0][0] <= t else 0.0
    state["patch"] = 0.86 * state["patch"] + float(g.normal(0, 0.05))            # oil arrives in patches
    for psid, pt, pv in PINS:
        if psid == sid and abs(t - pt) <= 3 * 3600:
            w = 1.0 - abs(t - pt) / (3 * 3600.0)
            if abs(t - pt) < 450:
                return pv
            return min(pv - 12.0, (BASE_TPH + sig) * (1 + state["patch"] * (1 - w)))
    if sid == "WQ-03" and T0(4, "16:30") < t < T0(4, "21:30"):
        return 2100.0 - abs(float(g.normal(0, 22)))
    base = BASE_TPH * math.exp(float(g.normal(0, 0.14)))
    v = base + sig * max(0.35, 1 + state["patch"])
    cap = 3250.0 if sid != "WQ-03" else 2040.0
    if v > cap:                                   # stay below the readings canon gives as the maxima
        v = cap + 45.0 * math.tanh((v - cap) / 400.0)
    return v


def gen_water():
    E = env()
    S = reg("sensor_registry")
    supersede(rel_old("05_other_sources/env_sensors/water_quality_*.csv") + rel_old("05_other_sources/env_sensors/_consolidated/water_quality*"), [WQ_HEADER])
    rain = E.rain_series("KCRP", 27.77335, -97.51298)
    fresh_k = np.exp(-np.arange(0, 900) / 220.0)
    fresh = np.convolve(rain, fresh_k / fresh_k.sum())[:E.n] * 220.0 / 100.0         # runoff memory, arbitrary units
    totals = {}
    for st in S["water_quality_sondes"]:
        sid = st["sensor_id"]
        g = rng("water_quality", sid)
        lat, lon = st["latitude"], st["longitude"]
        piling = st.get("installation") == "piling mount"
        nueces = "Nueces" in st["water_body"]
        harbor = "Inner Harbor" in st["water_body"]
        sal0 = 31.5 if nueces else (33.5 if harbor else 35.2)
        fresh_gain = 2.6 if nueces else (1.0 if harbor else 0.55)
        outages = list(SONDE_OUT[sid])
        for _ in range(int(g.integers(2, 5))):                                    # fouling, service visits, telemetry gaps
            a = SPAN_START + int(g.integers(3, 146)) * 86400 + int(g.integers(0, 96)) * 900
            if abs(a - LANDFALL) > 25 * 86400:
                outages.append((a, a + int(g.integers(4, 40)) * 900))
        state = {"patch": 0.0}
        do_n = ph_n = tb_n = 0.0
        batt = 12.9
        rows = []
        t = SPAN_START
        while t < SPAN_END:
            tph = tph_ppb(sid, t, g, state)                                       # advance the patch process every step
            if in_any(t, outages):
                t += 900
                continue
            x = (t - E.t0) / H
            i = int(x)
            fr = fresh[i]
            spd, d, r = E.wind(t, lat, lon, 0.85, 0.5)
            _, _, _, _, _, _ = E._front_terms(t)
            lh = E.local_hour(t)
            wt = pwl([(ts("2027-08-15T00:00Z"), 30.8), (ts("2027-09-13T00:00Z"), 29.6), (ts("2027-09-15T12:00Z"), 26.4),
                      (ts("2027-10-15T00:00Z"), 25.8), (ts("2027-11-15T00:00Z"), 20.6), (ts("2027-12-15T00:00Z"), 16.0),
                      (ts("2028-01-12T00:00Z"), 14.4)], t)
            cool = E._front_terms(t)[0]
            wt += 0.45 * math.cos((lh - 16.5) / 24 * 2 * math.pi) - 0.35 * min(8.0, cool) + float(g.normal(0, 0.04))
            storm_h = (t - LANDFALL) / 3600.0
            sal = sal0 - fresh_gain * min(9.0, fr) + (1.2 * math.exp(-((storm_h - 1) / 6.0) ** 2) if harbor or nueces else 0.0)
            sal = max(2.0, sal + float(g.normal(0, 0.08)))
            sc = sal * 1500.0 * (1 + 0.019 * (wt - 25.0)) / (1 + 0.019 * (wt - 25.0)) + float(g.normal(0, 40))
            tb_n = 0.9 * tb_n + float(g.normal(0, 0.12))
            turb = (9 if not harbor else 14) * math.exp(tb_n) + 2.2 * max(0.0, spd - 6) ** 1.5 + 14 * min(8.0, fr)
            if -8 < storm_h < 60:
                turb += 520 * math.exp(-((storm_h - 2) / 9.0) ** 2) + 160 * math.exp(-max(0.0, storm_h) / 30.0) * (storm_h > 0)
            do_n = 0.95 * do_n + float(g.normal(0, 0.05))
            dosat = 14.6 - 0.39 * wt + 0.0046 * wt * wt - 0.035 * sal
            do = dosat * (0.86 + 0.07 * math.cos((lh - 16.0) / 24 * 2 * math.pi)) + do_n
            if 0 < storm_h < 24 * 16:                                           # oxygen sag after the storm
                do -= 2.6 * math.exp(-((storm_h / 24.0 - 3.5) / 3.2) ** 2)
            do = max(0.6, do - 0.0006 * min(tph, 3000))
            ph_n = 0.96 * ph_n + float(g.normal(0, 0.012))
            ph = 8.12 - 0.045 * min(9.0, fr) * (fresh_gain / 1.5) + 0.05 * math.cos((lh - 16.0) / 24 * 2 * math.pi) + ph_n
            if piling:
                depth = 1.6 + predicted_tide_m("GAUGE-14", t) + bay_level_m(t, E) + float(g.normal(0, 0.01))
            else:
                depth = 1.0 + float(g.normal(0, 0.01))
            batt = 12.9 - 0.5 * max(0.0, math.sin((lh - 2) / 24 * 2 * math.pi)) * 0.3 + float(g.normal(0, 0.02))
            if 0 < storm_h < 70:
                batt -= 0.8 * math.exp(-storm_h / 40.0)
            qc = "A"
            if turb > 600:
                qc = "S"                                                         # suspect: heavy sediment
            rows.append([sid, st["sensor_name"], lat, lon, iso(t, z=False), round(wt, 2), int(round(sc)), round(sal, 2),
                         round(do, 2), round(ph, 2), round(min(turb, 990.0), 1), round(tph, 1), round(depth, 2), round(batt, 2), qc])
            t += 900
        totals[sid] = write_csv(f"05_other_sources/env_sensors/water_quality_{sid}.csv", WQ_HEADER, rows)
    return totals


# ======================================================================================
# air-quality monitors
# ======================================================================================
AQ_HEADER = ["SensorID", "State_Code", "County_Code", "Site_Name", "Site_Type", "Latitude", "Longitude", "Date_GMT", "Time_GMT",
             "PM25_ugm3", "Ozone_ppb", "SO2_ppb", "H2S_ppb", "Benzene_ppb", "TNMHC_ppbC", "WindSpeed_mps", "WindDir_deg",
             "Temp_C", "QC"]
HILLCREST = "AQS-480-005"
REFINERY_ROW = "AQS-480-016"
# Hillcrest benzene above its 0.3 ppb baseline (canon: 4.8 at 14:00Z D+2, 7.2 at 02:00Z D+3, under 3 by 18:00Z D+5)
BENZ = [(T0(0, "04:10"), 0.0), (T0(0, "05:00"), 1.2), (T0(1, "12:00"), 2.1), (T0(2, "06:00"), 2.6), (T0(2, "14:00"), 4.5),
        (T0(2, "20:00"), 5.6), (T0(3, "02:00"), 6.9), (T0(3, "12:00"), 5.4), (T0(4), 4.9), (T0(4, "12:00"), 4.0),
        (T0(5, "06:00"), 3.2), (T0(5, "17:00"), 2.5), (T0(6, "12:00"), 1.6), (T0(8), 0.8), (T0(12), 0.2), (T0(20), 0.0)]
# how strongly each monitor sees the channel plume relative to Hillcrest
PLUME = {HILLCREST: 1.0, "AQS-480-001": 0.85, "AQS-MOB-001": 0.80, "AQS-480-004": 0.75, REFINERY_ROW: 0.70, "AQS-480-006": 0.55,
         "AQS-480-014": 0.40, "AQS-480-010": 0.28, "AQS-480-007": 0.18, "AQS-480-015": 0.08, "AQS-480-013": 0.06}
AQ_BACK = {HILLCREST: "2027-09-15T13:00Z", "AQS-480-001": "2027-09-15T18:00Z", REFINERY_ROW: "2027-09-16T10:00Z",
           "AQS-480-003": "2027-09-14T22:00Z", "AQS-480-004": "2027-09-18T15:00Z", "AQS-480-012": "2027-09-23T16:00Z",
           "AQS-480-009": "2027-09-17T14:00Z", "AQS-MOB-001": "2027-09-16T15:00Z", "AQS-480-006": "2027-09-16T19:00Z"}
SOURCE = (27.81447, -97.40133)        # the TERM-01 berth


def gen_air():
    E = env()
    S = reg("sensor_registry")
    supersede(rel_old("05_other_sources/env_sensors/aqs_*.csv") + rel_old("05_other_sources/env_sensors/_consolidated/aqs*"), [AQ_HEADER])
    gshared = rng("air_quality", "regional")
    n = E.n
    dust = np.zeros(n)                                  # Saharan dust and stagnation episodes raise PM2.5 regionally
    for a, hours, amp in (("2027-08-19T00:00Z", 60, 16), ("2027-08-29T06:00Z", 48, 11), ("2027-10-03T00:00Z", 40, 8),
                          ("2027-11-22T00:00Z", 36, 9), ("2027-12-27T00:00Z", 30, 10)):
        i0 = int((ts(a) - E.t0) // H)
        dust[i0:i0 + hours] += amp * np.hanning(hours)
    # industrial upsets and restart flaring: (start, hours, SO2 ppb, benzene ppb, TNMHC ppbC) at industrial monitors
    upsets = []
    for _ in range(9):
        a = SPAN_START + int(gshared.integers(2, 26)) * 86400 + int(gshared.integers(0, 24)) * H
        upsets.append((a, int(gshared.integers(2, 6)), float(gshared.uniform(12, 40)), float(gshared.uniform(0.6, 1.8)), float(gshared.uniform(300, 900))))
    for _ in range(16):
        a = ts("2027-09-23T00:00Z") + int(gshared.integers(0, 105)) * 86400 + int(gshared.integers(0, 24)) * H
        restart = a < ts("2027-10-15T00:00Z")
        upsets.append((a, int(gshared.integers(2, 8)), float(gshared.uniform(18, 62) if restart else gshared.uniform(10, 34)),
                       float(gshared.uniform(0.7, 2.2)), float(gshared.uniform(350, 1400))))
    totals = {}
    for st in S["air_monitors"]:
        sid = st["sensor_id"]
        g = rng("air_quality", sid)
        lat, lon = st["latitude"], st["longitude"]
        params = set(st.get("parameters") or [])
        stype = st["site_type"]
        ind = stype in ("industrial", "fenceline community", "mobile")
        plume = PLUME.get(sid, 0.0)
        dist_src, brg_src = _bearing(SOURCE[0], SOURCE[1], lat, lon)
        off = T0(0, "03:00") + int(g.integers(0, 12)) * 900 + (int(2.2 * H) if sid in (HILLCREST, "AQS-480-001") else 0)
        back = ts(AQ_BACK[sid]) if sid in AQ_BACK else T0(1) + int(g.integers(4, 130)) * H
        outages = [(off, back)]
        if stype == "mobile":
            outages = [(ts("2027-09-13T17:00Z"), back)]
        for _ in range(int(g.integers(2, 6))):
            a = SPAN_START + int(g.integers(2, 147)) * 86400 + int(g.integers(0, 24)) * H
            if abs(a - LANDFALL) > 14 * 86400:
                outages.append((a, a + int(g.integers(2, 14)) * H))
        b0 = {"industrial": 0.5, "fenceline community": 0.3, "mobile": 0.45}.get(stype, 0.14)
        if sid == HILLCREST:
            b0 = 0.3
        pm_n = so_n = h2_n = bz_n = hc_n = 0.0
        rows = []
        t = SPAN_START
        while t < SPAN_END:
            i = int((t - E.t0) // H)
            lh = E.local_hour(t)
            spd, d, r = E.wind(t, lat, lon, 0.8, 0.9)
            T, Td = E.temp(t, lat, lon, 0.9)
            pm_n = 0.85 * pm_n + float(g.normal(0, 0.11))
            so_n = 0.8 * so_n + float(g.normal(0, 0.22))
            h2_n = 0.8 * h2_n + float(g.normal(0, 0.2))
            bz_n = 0.8 * bz_n + float(g.normal(0, 0.11))
            hc_n = 0.8 * hc_n + float(g.normal(0, 0.16))
            if in_any(t, outages):
                t += H
                continue
            calm = max(0.0, 1.0 - spd / 4.0)
            dstorm = (t - LANDFALL) / 86400.0
            shut = 0.25 if -2.0 < dstorm < 9 else (0.6 if 9 <= dstorm < 21 else 1.0)       # plants down for the storm
            # ---------- PM2.5
            pm = (8.0 + (2.0 if ind else 0.0)) * math.exp(pm_n) + dust[i] + 5.0 * calm * (lh < 8 or lh > 20)
            if 1.5 < dstorm < 16:                                                    # generators, debris, dried silt
                pm += (9.0 if stype != "background" else 3.0) * math.exp(-max(0.0, dstorm - 4) / 6.0)
            if r is not None and spd > 14:
                pm = 4.0 + abs(float(g.normal(0, 1.5)))                              # rain and wind scrub the air
            # ---------- ozone
            sun = max(0.0, math.sin((lh - 6.5) / 13.0 * math.pi)) if 6.5 < lh < 19.5 else 0.0
            winter = min(1.0, max(0.0, (t - ts("2027-10-01T00:00Z")) / (70 * 86400)))
            oz = 16 + (30 - 12 * winter) * sun * (1.15 if spd < 4 else 0.9) + 6 * float(g.normal(0, 0.5))
            oz = max(2.0, oz - (8 if lh < 6 and calm > 0.4 else 0))
            # ---------- upsets
            so_up = bz_up = hc_up = 0.0
            if ind:
                for a, hours, so2, bz, hc in upsets:
                    if a <= t < a + hours * H:
                        k = math.sin((t - a + H / 2) / (hours * H) * math.pi)
                        so_up += so2 * k; bz_up += bz * k; hc_up += hc * k
            so2 = (3.2 if ind else 0.9) * shut * math.exp(so_n) + so_up * (0.6 + 0.4 * float(g.random()))
            h2s = (0.7 if ind else 0.2) * shut * math.exp(h2_n)
            benz = b0 * (0.55 + 0.45 * shut) * math.exp(bz_n) * (1.0 + 0.5 * calm) + bz_up
            hc = (150 if ind else 60) * (0.5 + 0.5 * shut) * math.exp(hc_n) * (1 + 0.6 * calm) + hc_up
            # ---------- the spill plume
            if plume > 0 and BENZ[0][0] <= t <= BENZ[-1][0]:
                envp = pwl(BENZ, t)
                if sid == HILLCREST:
                    benz = b0 + envp * (1.0 + 0.045 * float(g.normal(0, 1)))
                    if t == T0(2, "14:00"):
                        benz = 4.8
                    elif t == T0(3, "02:00"):
                        benz = 7.2
                    else:
                        benz = min(benz, 7.05)
                        if T0(2, "14:00") < t < T0(3, "02:00"):
                            benz = max(benz, 4.85)
                        if t < T0(2, "14:00"):
                            benz = min(benz, 4.6)
                    if t >= T0(5, "18:00"):
                        benz = min(benz, 2.9)
                    hc += 1400 * envp * (0.8 + 0.4 * float(g.random()))
                    h2s += 1.1 * envp * (0.6 + 0.6 * float(g.random()))
                else:
                    wind_to = (d + 180) % 360
                    align = math.cos(math.radians(wind_to - brg_src))
                    f = plume * (0.35 + 0.65 * max(0.0, align) ** 0.5) * (1.0 + 0.5 * calm)
                    benz = min(6.4 + 0.2 * float(g.random()), benz + envp * f * (0.85 + 0.3 * float(g.random())))
                    hc += 1700 * envp * f * (0.8 + 0.4 * float(g.random()))
                    h2s += 1.3 * envp * f * (0.6 + 0.6 * float(g.random()))
                    if sid == REFINERY_ROW and t == T0(2, "16:00"):
                        hc = 12400.0
                    elif sid == REFINERY_ROW:
                        hc = min(hc, 11900.0)
            date, tm = iso(t)[:10], iso(t)[11:16]
            val = lambda name, v, nd: (round(v, nd) if name in params or not params else "")
            rows.append([sid, st.get("state_code", "48"), st.get("county_code", "355"), st["sensor_name"], stype, lat, lon, date, tm,
                         val("PM2.5", max(0.5, pm), 1), val("ozone", oz, 1), val("SO2", max(0.0, so2), 2), val("H2S", max(0.0, h2s), 2),
                         val("benzene", max(0.02, benz), 2), val("total_nonmethane_hydrocarbons", max(5.0, hc), 0),
                         round(spd, 1), int(round(d / 10.0) * 10) % 360, round(T, 1), "V"])
            t += H
        totals[sid] = write_csv(f"05_other_sources/env_sensors/aqs_air_quality_{sid}.csv", AQ_HEADER, rows)
    return totals


JOBS = {"weather": gen_weather, "advisories": gen_advisories, "gauges": gen_gauges, "water": gen_water, "air": gen_air}

if __name__ == "__main__":
    which = sys.argv[1:] or list(JOBS)
    for w in which:
        res = JOBS[w]()
        print(f"{w}: {sum(res.values())} rows in {len(res)} files" if w != "advisories" else f"advisories: {res}")
        for k, v in res.items():
            print(f"   {k}: {v}")
