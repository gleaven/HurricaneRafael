"""Regional weather and storm model shared by the environment and health generators.

One deterministic picture of the atmosphere over the Coastal Bend for the whole span, so that
weather stations, buoys, tide gauges, sondes and air monitors all describe the same days:
  * a seasonal and diurnal background with sea breeze, return flow and autumn/winter cold fronts
  * the pre-storm soaking (stalled front and tropical moisture, D-7 to D-3)
  * Hurricane Rafael as a moving vortex on the canon track (09_shared_state_timeline/data),
    with a Holland pressure profile and central pressures from the best-track file

    env = Env()
    w = env.wind(t, lat, lon, land=0.85)     # (speed m/s, direction-from deg, gust m/s or None)
    p = env.slp(t, lat, lon)                 # sea-level pressure, mb
    T, Td = env.temp(t, lat, lon, coastal=0.6)
    r = env.rain_mm_per_h(t, lat, lon, key)  # hourly rate

Not a forecast model: a consistent, physically sensible description.
"""
import math
import os

import numpy as np

from common import D0_EPOCH, LANDFALL, SPAN_START, SPAN_END, ROOT, load_json, rng, ts, utc_offset

H = 3600
PN = 1010.5                      # environmental pressure for the storm profile
KT = 0.514444                    # m/s per knot


def _bearing(lat1, lon1, lat2, lon2):
    dy = (lat2 - lat1) * 60.0
    dx = (lon2 - lon1) * 60.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy), (math.degrees(math.atan2(dx, dy)) + 360) % 360


# cold fronts: (passage at Corpus Christi UTC, strength 0..1, rain with passage)
FRONTS = [("2027-09-07T03:00Z", 0.22, False), ("2027-09-26T10:00Z", 0.35, False), ("2027-10-07T08:00Z", 0.50, True),
          ("2027-10-16T14:00Z", 0.45, False), ("2027-10-26T21:00Z", 0.70, True), ("2027-11-04T06:00Z", 0.50, False),
          ("2027-11-11T03:00Z", 0.60, True), ("2027-11-18T12:00Z", 0.55, False), ("2027-11-25T05:00Z", 0.80, True),
          ("2027-12-02T16:00Z", 0.50, False), ("2027-12-08T09:00Z", 0.75, True), ("2027-12-15T04:00Z", 0.60, False),
          ("2027-12-21T18:00Z", 0.90, True), ("2027-12-28T11:00Z", 0.55, False), ("2028-01-03T07:00Z", 0.85, True),
          ("2028-01-09T02:00Z", 0.60, False)]
# daily-mean temperature at the airport, deg C
SEASON = [("2027-08-13T00:00Z", 30.2), ("2027-09-01T00:00Z", 29.6), ("2027-09-20T00:00Z", 28.2), ("2027-10-10T00:00Z", 25.6),
          ("2027-11-01T00:00Z", 22.2), ("2027-11-20T00:00Z", 19.2), ("2027-12-10T00:00Z", 16.6), ("2028-01-01T00:00Z", 14.6),
          ("2028-01-14T00:00Z", 14.0)]
# light northerly drainage behind the departing storm (lets channel vapours reach Hillcrest)
LIGHT_NORTH = (ts("2027-09-16T10:00Z"), ts("2027-09-17T12:00Z"))
# winter drizzle / coastal-low rain episodes (start, hours, mean mm/h)
SOAKERS = [("2027-10-20T21:00Z", 4, 6.5), ("2027-11-07T08:00Z", 6, 2.6), ("2027-11-29T18:00Z", 9, 2.4),
           ("2027-12-18T02:00Z", 7, 1.6), ("2028-01-06T10:00Z", 10, 2.8)]
PRE_STORM_SOAK = (ts("2027-09-07T05:00Z"), ts("2027-09-12T05:00Z"))


class Env:
    def __init__(self):
        self.t0 = SPAN_START - 72 * H
        self.n = int((SPAN_END + 48 * H - self.t0) // H) + 1
        self.fronts = [(ts(a), s, r) for a, s, r in FRONTS]
        self._season = ([ts(a) for a, _ in SEASON], [v for _, v in SEASON])
        self._track()
        g = rng("envmodel", "regional")
        # slow regional anomalies (temperature, pressure) from filtered noise
        self.an_T = self._smooth(g.normal(0, 1, self.n), 30) * 1.1
        self.an_P = self._smooth(g.normal(0, 1, self.n), 40) * 2.2
        self.an_W = self._smooth(g.normal(0, 1, self.n), 9) * 1.0     # wind speed wobble
        self.an_D = self._smooth(g.normal(0, 1, self.n), 14) * 14.0   # wind direction wobble, deg
        self._rain_cache = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _smooth(x, k):
        w = np.hanning(2 * k + 1)
        w /= w.sum()
        y = np.convolve(x, w, mode="same")
        return y / (y.std() or 1.0)

    def _an(self, arr, t):
        x = (t - self.t0) / H
        i = int(max(0, min(self.n - 2, math.floor(x))))
        f = x - i
        return float(arr[i] * (1 - f) + arr[i + 1] * f)

    def local_hour(self, t):
        return ((t + utc_offset(t) * H) % 86400) / H

    # ------------------------------------------------------------------ storm
    def _track(self):
        pts = sorted(load_json("09_shared_state_timeline/data/storm_track.json"), key=lambda p: p["t"])
        pres = {}
        fp = os.path.join(ROOT, "09_shared_state_timeline", "data", "hurdat2_AL092027_2027.txt")
        with open(fp, encoding="utf-8") as fh:
            for line in fh.read().splitlines()[1:]:
                c = [x.strip() for x in line.split(",")]
                if len(c) > 7 and c[0].isdigit():
                    import datetime as dt
                    d = dt.datetime.strptime(c[0] + c[1], "%Y%m%d%H%M").replace(tzinfo=dt.timezone.utc)
                    pres[int((d.timestamp() - D0_EPOCH) // H)] = float(c[7])
        self.trk = [(p["t"], p["lat"], p["lon"], p["wind_kt"], pres.get(int(p["t"]), 1008.0)) for p in pts]

    def storm(self, t):
        """Storm state at epoch t: dict(lat, lon, vmax_kt, pc_mb, heading_deg, speed_kt, rmax_nm), or None."""
        h = (t - D0_EPOCH) / H
        tr = self.trk
        if h < tr[0][0] or h > tr[-1][0]:
            return None
        for a, b in zip(tr, tr[1:]):
            if a[0] <= h <= b[0]:
                f = (h - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0.0
                lat, lon = a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f
                d, brg = _bearing(a[1], a[2], b[1], b[2])
                hl = (t - LANDFALL) / H
                rmax = 10.0 if hl <= 0 else min(24.0, 10.0 + hl * 1.3)
                return {"lat": lat, "lon": lon, "vmax_kt": a[3] + (b[3] - a[3]) * f, "pc_mb": a[4] + (b[4] - a[4]) * f,
                        "heading_deg": brg, "speed_kt": d / max(1e-6, b[0] - a[0]), "rmax_nm": rmax}
        return None

    def storm_at_point(self, t, lat, lon, land=0.85):
        """(wind speed m/s, direction-from deg, pressure deficit mb, rain mm/h, radius nm) from the vortex."""
        st = self.storm(t)
        if st is None or st["vmax_kt"] < 22:
            return None
        r, theta = _bearing(st["lat"], st["lon"], lat, lon)
        r = max(0.6, r)
        rm = st["rmax_nm"]
        v = st["vmax_kt"] * (r / rm) ** 1.15 if r < rm else st["vmax_kt"] * (rm / r) ** 0.58
        v *= (1.0 + 0.10 * math.sin(math.radians(theta - st["heading_deg"]))) * land * 0.92
        deficit = (PN - st["pc_mb"]) * (1.0 - math.exp(-((rm / r) ** 1.25)))
        intensity = max(0.0, (st["vmax_kt"] - 25.0) / 85.0)
        core = 30.0 * intensity * math.exp(-(((r - rm) / (1.1 * rm)) ** 2))
        bands = 5.0 * intensity * math.exp(-r / 100.0)
        if r < 0.45 * rm:                         # inside the eye
            core *= 0.15
        return v * KT, (theta + 70.0) % 360.0, deficit, core + bands, r

    # ------------------------------------------------------------------ fronts
    def _front_terms(self, t):
        """(cooling degC, extra dew-point drop degC, north wind m/s, pressure mb, hours since last front, strength)."""
        cool = dry = north = pres = 0.0
        since, strength = 1e9, 0.0
        for tf, s, _ in self.fronts:
            dh = (t - tf) / H
            if dh < -18:
                continue
            if dh < 0:
                pres -= s * 3.5 * (1 - abs(dh) / 18.0) * (abs(dh) / 18.0) * 4 * 0.6
                continue
            rise = min(1.0, dh / 8.0)
            cool += s * 10.5 * rise * math.exp(-dh / 62.0)
            dry += s * 9.0 * rise * math.exp(-dh / 50.0)
            north += (5.0 + 7.5 * s) * min(1.0, dh / 2.0) * math.exp(-dh / 22.0)
            pres += s * 10.0 * min(1.0, dh / 18.0) * math.exp(-max(0.0, dh - 18.0) / 60.0)
            if dh < since:
                since, strength = dh, s
        return cool, dry, north, pres, since, strength

    # ------------------------------------------------------------------ fields
    def season_T(self, t):
        return float(np.interp(t, self._season[0], self._season[1]))

    def temp(self, t, lat, lon, coastal=1.0, water=False):
        """(dry bulb C, dew point C). coastal: 1 airport inland, ~0.45 on the barrier island."""
        lh = self.local_hour(t)
        mean = self.season_T(t) + 0.5 * (1 - coastal)
        winter = min(1.0, max(0.0, (t - ts("2027-10-01T00:00Z")) / (60 * 86400)))
        amp = (4.6 + 1.0 * winter) * coastal * (0.25 if water else 1.0)
        diurnal = amp * math.cos((lh - 15.3) / 24 * 2 * math.pi)
        if lh < 15.3:                                   # slower morning warm-up, sharper pre-dawn minimum
            diurnal -= 0.5 * coastal * math.exp(-((lh - 6.5) / 2.2) ** 2)
        cool, dry, north, _, since, s = self._front_terms(t)
        T = mean + diurnal * (1 - 0.35 * min(1.0, north / 9.0)) + self._an(self.an_T, t) - cool * (0.75 if water else 1.0)
        td_base = self.season_T(t) - 5.6 - 2.5 * winter + 0.6 * self._an(self.an_T, t)
        Td = min(td_base - dry, T - 0.4)
        st = self.storm_at_point(t, lat, lon)
        if st and st[4] < 160:                          # cloud, rain and wind: saturated, cooler, no diurnal cycle
            w = min(1.0, (160 - st[4]) / 110.0)
            T = T * (1 - w) + (25.4 - 1.2 * w) * w
            Td = Td * (1 - w) + (T - 0.9) * w
        if PRE_STORM_SOAK[0] <= t <= PRE_STORM_SOAK[1]:
            T = T - 1.6 - 0.45 * diurnal
            Td = max(Td, T - 1.8)
        return T, min(Td, T - 0.3)

    def slp(self, t, lat, lon):
        lh = self.local_hour(t)
        winter = min(1.0, max(0.0, (t - ts("2027-09-20T00:00Z")) / (80 * 86400)))
        base = 1014.6 + 4.2 * winter + 1.05 * math.cos((lh - 10.0) / 12 * 2 * math.pi)
        _, _, _, pres, _, _ = self._front_terms(t)
        quiet = 0.35 if ts("2027-09-07T00:00Z") <= t <= ts("2027-09-13T00:00Z") else 1.0
        p = base + self._an(self.an_P, t) * quiet + pres + (lat - 27.77) * 0.25
        st = self.storm_at_point(t, lat, lon)
        if st:
            p -= st[2]
        return p

    def background_wind(self, t, coastal=1.0):
        """(speed m/s, direction-from deg) without the hurricane."""
        lh = self.local_hour(t)
        winter = min(1.0, max(0.0, (t - ts("2027-10-01T00:00Z")) / (60 * 86400)))
        day = max(0.0, math.sin((lh - 8.5) / 12.5 * math.pi)) if 8.5 <= lh <= 21 else 0.0
        spd = (2.6 + 4.6 * day * (1 - 0.35 * winter)) * (0.9 + 0.25 * (1 - coastal)) + 0.9 * self._an(self.an_W, t)
        d = 162.0 - 28.0 * day + self._an(self.an_D, t)
        cool, dry, north, _, since, s = self._front_terms(t)
        if since < 96 and north > 0.3:
            turn = min(1.0, since / 84.0)
            nd = (350.0 + 150.0 * turn ** 1.4) % 360.0            # N -> NE -> E -> SE as the high moves off
            w = min(1.0, north / max(spd, 0.5) * 0.9)
            spd = spd * (1 - w) + (north + 1.5 * day) * w
            d = self._blend_dir(d, nd, w if since < 60 else w * 0.7)
        if LIGHT_NORTH[0] <= t <= LIGHT_NORTH[1]:
            edge = min(1.0, (t - LIGHT_NORTH[0]) / (3 * H), (LIGHT_NORTH[1] - t) / (3 * H))
            spd = spd * (1 - edge) + (1.3 + 0.5 * math.sin(t / 5400.0)) * edge
            d = self._blend_dir(d, 12.0 + 14.0 * math.sin(t / 9000.0), edge)
        return max(0.3, spd), d % 360.0

    @staticmethod
    def _blend_dir(a, b, w):
        ax, ay = math.sin(math.radians(a)), math.cos(math.radians(a))
        bx, by = math.sin(math.radians(b)), math.cos(math.radians(b))
        x, y = ax * (1 - w) + bx * w, ay * (1 - w) + by * w
        return (math.degrees(math.atan2(x, y)) + 360) % 360

    def wind(self, t, lat, lon, land=0.85, coastal=1.0):
        """(sustained m/s, direction-from deg, storm radius nm or None)."""
        spd, d = self.background_wind(t, coastal)
        st = self.storm_at_point(t, lat, lon, land)
        if st:
            v, sd = st[0], st[1]
            w = max(0.0, min(1.0, (v - spd * 0.8) / (0.6 * spd + 1.0)))
            if w > 0:
                spd = spd * (1 - w) + v * w
                d = self._blend_dir(d, sd, w)
            return spd, d, st[4]
        return spd, d, None

    # ------------------------------------------------------------------ rain
    def rain_series(self, key, lat, lon):
        """Hourly rainfall (mm in the hour ending at t0 + (i+1)h) for a named site; cached, deterministic."""
        if key in self._rain_cache:
            return self._rain_cache[key]
        g = rng("envmodel", "rain", key)
        gs = rng("envmodel", "rain", "shared")        # regional events hit every site at about the same time
        r = np.zeros(self.n)
        idx = lambda t: int((t - self.t0) // H)
        # 1. the canon soaking: several multi-hour episodes a day, every day
        d = PRE_STORM_SOAK[0]
        while d < PRE_STORM_SOAK[1]:
            for _ in range(2 + int(gs.integers(0, 2))):
                start = d + int(gs.integers(0, 22)) * H
                for k in range(int(gs.integers(2, 5))):
                    i = idx(start + k * H)
                    if idx(PRE_STORM_SOAK[0]) <= i < idx(PRE_STORM_SOAK[1]):
                        r[i] += float(gs.uniform(2.5, 10.5)) * float(g.uniform(0.65, 1.3))
            d += 86400
        # 2. summer and early-autumn showers (local)
        day = SPAN_START - 86400
        while day < ts("2027-10-20T00:00Z"):
            if not (PRE_STORM_SOAK[0] - 86400 <= day <= ts("2027-09-18T00:00Z")) and g.random() < 0.21:
                i = idx(day + (19 + int(g.integers(0, 6))) * H)
                r[i] += float(g.gamma(1.8, 4.6))
                if g.random() < 0.4:
                    r[i + 1] += float(g.gamma(1.4, 2.6))
            day += 86400
        # 3. frontal rain
        for tf, s, wet in self.fronts[1:]:
            if wet:
                for k in range(-1, 3):
                    r[idx(tf + k * H)] += max(0.0, float(gs.gamma(2.0, 2.4 * s + 0.8)) * float(g.uniform(0.6, 1.3)) * (1.0 if k in (0, 1) else 0.45))
        # 4. winter drizzle episodes
        for a, hours, rate in SOAKERS:
            for k in range(hours):
                r[idx(ts(a) + k * H)] += float(g.gamma(2.0, rate / 2.0))
        # 5. Rafael
        t = ts("2027-09-12T12:00Z")
        while t < ts("2027-09-16T06:00Z"):
            tot = 0.0
            st_rm = (self.storm(t) or {"rmax_nm": 10.0})["rmax_nm"]
            for q in range(4):
                st = self.storm_at_point(t + q * 900, lat, lon)
                if st:
                    band = 0.35 + 1.3 * max(0.0, math.sin((t + q * 900) / 5200.0 + st[4] / 21.0)) ** 2 if st[4] > 2.2 * st_rm else 1.0
                    tot += st[3] * band / 4.0
            r[idx(t)] += tot * float(g.uniform(0.8, 1.2))
            t += H
        self._rain_cache[key] = np.round(r, 1)
        return self._rain_cache[key]

    def rain_at(self, key, lat, lon, t):
        return float(self.rain_series(key, lat, lon)[int((t - self.t0) // H)])
