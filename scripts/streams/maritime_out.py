"""Write the maritime streams from a finished port simulation.

    AIS                05_other_sources/ais/ais_YYYY-MM.csv            shore-station feed
                       05_other_sources/ais/satellite/sais_YYYY-MM.csv satellite feed beyond shore range
    port surveillance  05_other_sources/port_surveillance/*.csv         radar tracks, camera log, traffic log, sensor status
    port conditions    05_other_sources/supply/port_conditions.csv
    arrivals           05_other_sources/supply/vessel_arrivals.csv
    cargo manifests    05_other_sources/supply/cargo_manifest.csv
"""
import csv
import math
import os
import zlib

import numpy as np

import geo
import maritime_geom as mg
from common import D0_EPOCH, ROOT, iso, local_ts, out_path, rng, ts, utc_offset
from maritime_base import DAY, H, PORT_NAMES
from maritime_core import (BLAST, DARK_END, DARK_START, INNER_E_PERMITS, LON_BRIDGE, LON_JETTY, REOPEN1, REOPEN2, RESTRICTION_LIFTED,
                           RX, RX_RANGE_NM, T0, T_END, XRAY, YANKEE, ZULU, Emitter, ais_name)

MONTHS = [("2027-08", ts("2027-08-15T00:00Z"), ts("2027-09-01T00:00Z")), ("2027-09", ts("2027-09-01T00:00Z"), ts("2027-10-01T00:00Z")),
          ("2027-10", ts("2027-10-01T00:00Z"), ts("2027-11-01T00:00Z")), ("2027-11", ts("2027-11-01T00:00Z"), ts("2027-12-01T00:00Z")),
          ("2027-12", ts("2027-12-01T00:00Z"), ts("2028-01-01T00:00Z")), ("2028-01", ts("2028-01-01T00:00Z"), T_END)]
AIS_HEADER = ["MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading", "VesselName", "IMO", "CallSign", "VesselType", "Status",
              "Length", "Width", "Draft", "Cargo", "TransceiverClass", "Destination"]


def tstr(t):
    return iso(t, z=False)


def zstr(t):
    return iso(t)


# ====================================================================================== AIS
class AisWriter:
    def __init__(self, sim):
        self.sim, self.GM, self.G = sim, sim.GM, sim.GM.G
        self.em = Emitter(sim.GM)
        self._jit = {}
        self.static = {}
        for v in sim.vessels.values():
            if v.mmsi is None:
                continue
            r = v.rec
            rs = rng("ais-static", v.id)
            self.static[v.id] = dict(mmsi=str(v.mmsi), name=ais_name(v.name), imo=(r.get("imo") or ""), cs=(r.get("call_sign") or ""),
                                     vt=r.get("ais_type_code") or 0, length=int(round(v.loa)), width=int(round(v.beam)),
                                     tc=v.tc or "A", no_heading=(v.tc == "B" and rs.random() < 0.6))

    def jitter_ok(self, pos):
        k = (round(pos[0], 5), round(pos[1], 5))
        if k not in self._jit:
            ok = True
            for ang in range(0, 360, 45):
                if self.G.is_land(*mg.dest_point(pos, ang, 4.0)):
                    ok = False
                    break
            self._jit[k] = ok
        return self._jit[k]

    def rows(self, t_lo, t_hi):
        """Yield (feed, time, row list) for every position report in [t_lo, t_hi)."""
        for v in self.sim.vessels.values():
            if v.mmsi is None:
                continue
            st = self.static[v.id]
            classb = st["tc"] == "B"
            rs = rng("ais-noise", v.id, int(t_lo))
            last_sec, last_pos = None, None
            for t, la, lo, sog, cog, hdg, seg in self.em.fixes(v, t_lo, t_hi - 0.001):
                if seg.kind == "stay" and seg.mode == "moored" and self.jitter_ok(seg.pos):
                    la += float(rs.normal(0, 1.1)) / geo.M_PER_DEG_LAT
                    lo += float(rs.normal(0, 1.1)) / geo.M_PER_DEG_LON
                # time stamps are whole seconds: one report per transponder per second
                sec, pos = int(t), (round(la, 5), round(lo, 5))
                if last_sec is not None and sec <= last_sec:
                    if pos == last_pos:
                        continue
                    sec = last_sec + 1
                    if sec >= t_hi:
                        continue
                last_sec, last_pos = sec, pos
                t = float(sec)
                if classb:
                    status, draft, dest = 15, "", ""
                else:
                    status = seg.status if seg.status is not None else (5 if (seg.kind == "stay" and seg.mode == "moored") else 1 if (seg.kind == "stay" and seg.mode == "anchored") else 0)
                    d = seg.draft if seg.draft is not None else v.draft_max
                    draft = f"{d:.1f}"
                    dest = seg.dest or ""
                heading = 511 if st["no_heading"] else int(round(hdg)) % 360
                feed = "T" if (v.id.startswith("SPOOF") or geo.gc_nm((la, lo), RX) <= RX_RANGE_NM) else "S"
                yield feed, t, [st["mmsi"], tstr(t), f"{la:.5f}", f"{lo:.5f}", f"{sog:.1f}", f"{cog % 360:.1f}", heading, st["name"], st["imo"], st["cs"],
                                st["vt"], status, st["length"], st["width"], draft, st["vt"], st["tc"], dest]

    def write_month(self, ym, t_lo, t_hi):
        feeds = {"T": [], "S": []}
        for feed, t, row in self.rows(t_lo, t_hi):
            feeds[feed].append((t, row))
        n = {}
        for feed, rel in (("T", f"05_other_sources/ais/ais_{ym}.csv"), ("S", f"05_other_sources/ais/satellite/sais_{ym}.csv")):
            rows = feeds[feed]
            rows.sort(key=lambda x: (x[0], x[1][0]))
            with open(out_path(rel), "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(AIS_HEADER)
                for _, row in rows:
                    w.writerow(row)
            n[feed] = len(rows)
        return n


# ====================================================================================== port surveillance
RADAR_HEADER = ["time_utc", "sensor_id", "track_id", "latitude", "longitude", "range_nm", "bearing_deg", "speed_kn", "course_deg",
                "est_length_m", "size_class", "ais_correlated", "correlated_mmsi", "ingest_utc"]
CAMERA_HEADER = ["time_utc", "sensor_id", "event_type", "direction", "mmsi", "vessel_name", "est_length_m", "berth_id", "vessels_in_view",
                 "water_surface", "note"]
VTS_HEADER = ["time_utc", "checkpoint", "direction", "mmsi", "vessel_name", "vessel_class", "pilot_order_id", "pilot_boat", "tugs",
              "from_place", "to_place"]
STATUS_HEADER = ["time_utc", "sensor_id", "status", "detail"]


def online(windows, t):
    return any(a <= t < b for a, b in windows)


class Surveillance:
    def __init__(self, sim):
        self.sim, self.GM, self.G = sim, sim.GM, sim.GM.G
        self.sensors = {s["sensor_id"]: s for s in sim.sensors}
        self.win = sim.sensor_windows
        self.ne = (self.sensors["RADAR-BUOY-NE"]["latitude"], self.sensors["RADAR-BUOY-NE"]["longitude"])
        self.sw = (self.sensors["RADAR-BUOY-SW"]["latitude"], self.sensors["RADAR-BUOY-SW"]["longitude"])

    # ---------------------------------------------------------------- radar geometry
    def seen_by(self, lat, lon):
        """Which radar buoy holds a contact at this position (line of sight approximated by water region)."""
        if lon >= -97.046 or (lon >= -97.0525 and 27.829 <= lat <= 27.842):
            if geo.gc_nm((lat, lon), self.ne) <= 9.5 and lon > -97.06:
                return "RADAR-BUOY-NE"
            return None
        if -97.392 <= lon <= -97.135 and 27.69 <= lat <= 27.875 and geo.gc_nm((lat, lon), self.sw) <= 7.0:
            if self.G.land_clearance_m(lat, lon) >= 200:
                return "RADAR-BUOY-SW"
        return None

    def path_in_range(self, path, cache={}):
        k = id(path)
        if k not in cache:
            a = np.array(path.pts)
            ok = False
            if a[:, 1].max() >= -97.0525 and a[:, 1].min() <= -96.80 and a[:, 0].min() <= 28.0 and a[:, 0].max() >= 27.63:
                ok = True
            if a[:, 1].max() >= -97.392 and a[:, 1].min() <= -97.135 and a[:, 0].min() <= 27.875 and a[:, 0].max() >= 27.69:
                ok = True
            cache[k] = ok
        return cache[k]

    def chord_ok(self, a, b, margin=3.0):
        """True if the straight line between two plots stays off the land (with a side margin)."""
        d = geo.dist_m(a, b)
        if d < 1.0:
            return True
        G = self.G
        if G.in_box(*a) and G.in_box(*b) and min(G.land_clearance_m(*a), G.land_clearance_m(*b)) > d / 2 + margin + 40.0:
            return True
        return self.GM.seg_clear_exact(a, b, margin)

    def plot_ok(self, p):
        """A plot beside the shore is kept only if it and the water 1.5 m either side of it are clear of the land."""
        if not self.GM.point_ok(p):
            return False
        for brg in (0.0, 90.0, 180.0, 270.0):
            if self.G.is_land(*mg.dest_point(p, brg, 1.5)):
                return False
        return not self.G.is_land(*p)

    def plot_times(self, pos, t_first, t_end, step=120.0):
        """Plot times for a moving contact: one per `step`, plus extra plots through bends where
        the line between two plots would otherwise lie across a jetty or a point of land."""
        base = []
        t = t_first
        while t < t_end:
            base.append(t)
            t += step
        if len(base) < 2:
            return base
        out = [base[0]]

        def refine(ta, tb, depth):
            pa, pb = pos(ta)[:2], pos(tb)[:2]
            if tb - ta <= 8.0 or depth > 6:
                return
            if self.seen_by(*pa) is None or self.seen_by(*pb) is None or self.chord_ok(pa, pb, 12.0):
                return
            tm = (ta + tb) / 2.0
            refine(ta, tm, depth + 1)
            out.append(tm)
            refine(tm, tb, depth + 1)
        for ta, tb in zip(base, base[1:]):
            refine(ta, tb, 0)
            out.append(tb)
        return out

    def radar_samples(self):
        """(sensor, vessel key, t, lat, lon, sog, cog, length, correlated, mmsi) for every hull a radar buoy holds."""
        out = []
        for v in self.sim.vessels.values():
            if getattr(v, "radar", True) is False:
                continue
            L = v.loa
            for seg in v.itin:
                if seg.t1 <= T0 or seg.t0 >= T_END:
                    continue
                corr = bool(seg.ais and v.mmsi)
                if seg.kind == "stay":
                    s = self.seen_by(*seg.pos)
                    if s is None:
                        continue
                    step = 1800.0 if seg.mode in ("moored", "anchored") else 120.0
                    ph = (zlib.crc32(v.id.encode()) % 1800) if step == 1800.0 else (zlib.crc32(v.id.encode()) % 120)
                    t = math.ceil((max(seg.t0, T0) - ph) / step) * step + ph
                    while t < min(seg.t1, T_END):
                        if seg.mode == "anchored":
                            from maritime_core import swing
                            p, hd = swing(t, seg.pos, seg.radius or 220.0, v.phase / 3600.0)
                        else:
                            p, hd = seg.pos, (seg.heading or 0.0)
                        out.append((s, v.id, t, p[0], p[1], 0.0 if seg.mode != "drift" else 0.7, hd, L, corr, v.mmsi))
                        t += step
                else:
                    if not self.path_in_range(seg.path):
                        continue
                    ph = zlib.crc32(v.id.encode()) % 120
                    t = math.ceil((max(seg.t0, T0) - ph) / 120.0) * 120.0 + ph
                    fwd = seg.ks[-1] >= seg.ks[0]
                    for t in self.plot_times(seg.pos, t, min(seg.t1, T_END)):
                        la, lo, brg = seg.pos(t)
                        s = self.seen_by(la, lo)
                        if s is not None:
                            out.append((s, v.id, t, la, lo, seg.speed_kn(t), brg if fwd else (brg + 180) % 360, L, corr, v.mmsi))
        return out

    def storm_clutter(self):
        """Short-lived small contacts the trackers log in hurricane-force seas (breaking waves, drifting debris)."""
        rs = rng("radar-clutter")
        t_peak = ts("2027-09-14T06:00Z")
        lo_t, hi_t = ts("2027-09-13T20:00Z"), ts("2027-09-14T16:00Z")
        out = []
        n_id = 0
        # (sensor, position of the buoy, how many, max range nm, storm clutter or wreckage adrift the day after)
        for sensor, src, count, rmax, adrift in (("RADAR-BUOY-SW", self.sw, 80, 5.5, False), ("RADAR-BUOY-NE", self.ne, 70, 8.0, False),
                                                 ("RADAR-BUOY-SW", self.sw, 34, 5.5, True)):
            made = tries = 0
            while made < count and tries < count * 30:
                tries += 1
                if adrift:
                    t = float(rs.uniform(ts("2027-09-14T12:30Z"), ts("2027-09-15T10:50Z")))
                else:
                    t = t_peak + float(rs.normal(0, 3.4)) * 3600.0
                if not (lo_t <= t <= (ts("2027-09-15T11:00Z") if adrift else hi_t)):
                    continue
                p = mg.dest_point(src, float(rs.uniform(0, 360)), float(rs.uniform(0.6, rmax)) * 1852.0)
                crs = float(rs.uniform(0, 360))
                spd = float(rs.uniform(0.3, 1.4)) if adrift else float(rs.uniform(0.8, 3.5))
                L = float(rs.uniform(4, 14))
                t = math.floor(t / 120.0) * 120.0 + float(rs.integers(0, 120))
                pts = []
                for k in range(int(rs.integers(5, 17)) if adrift else int(rs.integers(2, 7))):
                    q = mg.dest_point(p, crs, spd * 0.514444 * 120.0 * k)
                    if self.seen_by(*q) != sensor or self.G.is_land(*q) or (self.G.in_box(*q) and self.G.land_clearance_m(*q) < 400):
                        break
                    pts.append((t + 120.0 * k, q))
                if len(pts) < 2:
                    continue
                n_id += 1
                made += 1
                for tk, q in pts:
                    out.append((sensor, f"CLUTTER-{n_id}", tk, q[0], q[1], spd, crs, L, False, None))
        return out

    def small_boats(self):
        """Small craft with no AIS that the radars pick up now and then (recreational boats)."""
        sim = self.sim
        rs = rng("radar-small")
        out = []
        day = -30
        from maritime_local import STORM_STOP, local_day, weekday
        bay_pairs = [k for k in sim._paths if len(k) == 3 and k[0] == "w" and isinstance(k[1], str) and isinstance(k[2], str)
                     and k[1].startswith("cc_") and k[2].startswith("cc_")]
        n_id = 0
        while day < 120:
            t0 = local_ts(day, "06:30")
            if STORM_STOP - 6 * H < t0 < ts("2027-11-13T00:00Z"):
                day += 1
                continue
            wd = weekday(t0)
            pre = t0 < STORM_STOP
            n = int(rs.poisson((9 if wd >= 5 else 4) if pre else (2.5 if wd >= 5 else 0.8)))
            for _ in range(n):
                n_id += 1
                key = f"SMALL-{n_id}"
                L = float(rs.uniform(5.5, 11.5))
                t = t0 + float(rs.uniform(0, 12.5)) * H
                if rs.random() < 0.6 or not bay_pairs:
                    q = mg.dest_point((27.79312, -96.96336), float(rs.uniform(40, 170)), float(rs.uniform(3000, 14000)))
                    if not sim.gulf_ok(q):
                        continue
                    P = mg.Path([(27.79312, -96.96336), q])
                    legs = [(P, False, float(rs.uniform(14, 24))), (P, True, float(rs.uniform(14, 24)))]
                    wait = float(rs.uniform(0.6, 3.5)) * H
                else:
                    P = sim._paths[bay_pairs[int(rs.integers(0, len(bay_pairs)))]]
                    legs = [(P, False, float(rs.uniform(12, 22))), (P, True, float(rs.uniform(12, 22)))]
                    wait = float(rs.uniform(0.3, 2.5)) * H
                for i, (P, rev, sp) in enumerate(legs):
                    dur = P.length / (sp * 0.514444)
                    def pos(tq, P=P, rev=rev, t=t, dur=dur):
                        s_ = min(max((tq - t) / dur, 0.0), 1.0) * P.length
                        return P.at(P.length - s_ if rev else s_)
                    for tt in self.plot_times(pos, math.ceil(t / 120.0) * 120.0, t + dur):
                        la, lo, brg = pos(tt)
                        s = self.seen_by(la, lo)
                        if s is not None:
                            out.append((s, key, tt, la, lo, sp, (brg + 180) % 360 if rev else brg, L, False, None))
                    t += dur + (wait if i == 0 else 0)
            day += 1
        return out

    def write_radar(self):
        sim = self.sim
        samples = self.radar_samples() + self.small_boats() + self.storm_clutter()
        samples.sort(key=lambda x: (x[0], x[1], x[2]))
        rs = rng("radar-noise")
        rows = []
        prev = None
        last_p = None
        first = None
        for s, vid, t, la, lo, sog, cog, L, corr, mmsi in samples:
            if not online(self.win[s], t):
                prev = None
                continue
            new = prev is None or prev[0] != s or prev[1] != vid or t - prev[2] > 2700
            dla = float(rs.normal(0, 9.0)) / geo.M_PER_DEG_LAT
            dlo = float(rs.normal(0, 9.0)) / geo.M_PER_DEG_LON
            exact = (round(la, 5), round(lo, 5))
            p = (round(la + dla, 5), round(lo + dlo, 5))       # test the position exactly as it will be written
            if self.G.in_box(*p) and self.G.land_clearance_m(*p) < 80 and not self.plot_ok(p):
                p = exact
            if not new and not self.chord_ok(last_p, p):
                p = exact
                if not self.chord_ok(last_p, p):
                    new = True          # contact lost behind land: the tracker starts again
            if new:
                first = t
            prev = (s, vid, t)
            last_p = p
            src = self.ne if s.endswith("NE") else self.sw
            est = L * (1.0 + min(max(float(rs.normal(0, 0.035)), -0.09), 0.09))
            ingest = t + float(rs.uniform(1.0, 4.0))
            if s == "RADAR-BUOY-SW" and sim.buoy_sw_live_lost <= t < ts("2027-09-15T11:00Z"):
                ingest = sim.buoy_sw_buffer_recovered + (t - sim.buoy_sw_live_lost) / 60.0
            rows.append([t, s, (s, vid, first), p[0], p[1], geo.gc_nm(src, p), geo.bearing(src, p), max(0.0, sog + float(rs.normal(0, 0.15))), cog % 360,
                         est, "ship" if L >= 50 else "small", "Y" if corr else "N", str(mmsi) if (corr and mmsi) else "", ingest])
        # track ids: per buoy, numbered in order of first detection
        firsts = sorted({r[2] for r in rows}, key=lambda k: (k[0], k[2], str(k[1])))
        ids, counter = {}, {}
        for k in firsts:
            tag = "NE" if k[0].endswith("NE") else "SW"
            counter[tag] = counter.get(tag, 0) + 1
            ids[k] = f"{tag}-{counter[tag]:06d}"
        rows.sort(key=lambda r: (r[0], r[1], ids[r[2]]))
        counts = {}
        files = {}
        for ym, a, b in MONTHS:
            fp = out_path(f"05_other_sources/port_surveillance/radar_tracks_{ym}.csv")
            fh = open(fp, "w", encoding="utf-8", newline="")
            files[ym] = (fh, csv.writer(fh), a, b)
            files[ym][1].writerow(RADAR_HEADER)
            counts[ym] = 0
        for r in rows:
            for ym, (fh, w, a, b) in files.items():
                if a <= r[0] < b:
                    w.writerow([zstr(r[0]), r[1], ids[r[2]], f"{r[3]:.5f}", f"{r[4]:.5f}", f"{r[5]:.2f}", f"{r[6]:.1f}", f"{r[7]:.1f}", f"{r[8]:.1f}",
                                f"{r[9]:.0f}", r[10], r[11], r[12], zstr(r[13])])
                    counts[ym] += 1
                    break
        for fh, *_ in files.values():
            fh.close()
        return counts

    # ---------------------------------------------------------------- cameras and traffic log
    def surface(self, t):
        if t < ts("2027-09-14T04:05Z"):
            return "clear"
        if t < local_ts(5, "12:00"):
            return "heavy sheen"
        if t < local_ts(20, "17:00"):
            return "sheen"
        if t < local_ts(44, "00:00"):
            return "light sheen"
        return "clear"

    def write_cameras_and_vts(self):
        sim = self.sim
        cams = [s for s in sim.sensors if s["sensor_type"] == "fixed camera"]
        berth_cam = {}
        for c in cams:
            for b in c.get("berths", []):
                berth_cam[b] = c["sensor_id"]
        events = []      # (t, row)
        vts = []
        stays_by_berth = {}
        for v in sim.vessels.values():
            if getattr(v, "radar", True) is False:
                continue
            nm = ais_name(v.name)
            for seg in v.itin:
                if seg.t1 <= T0 or seg.t0 >= T_END:
                    continue
                if seg.kind == "stay":
                    if seg.mode == "moored" and seg.place in berth_cam and v.loa >= 20:
                        stays_by_berth.setdefault(seg.place, []).append((seg.t0, seg.t1, v))
                    continue
                for lon, cam, cp, lat_lo, lat_hi in ((LON_JETTY, "CAM-13", "JETTIES", 27.826, 27.846), (LON_BRIDGE, "CAM-04", "HARBOR BRIDGE", 27.806, 27.820)):
                    t = seg.t_at_lon(lon)
                    if t is None or not (T0 <= t < T_END):
                        continue
                    la, lo, brg = seg.pos(t)
                    if not (lat_lo <= la <= lat_hi):
                        continue
                    fwd = seg.ks[-1] >= seg.ks[0]
                    course = brg if fwd else (brg + 180) % 360
                    direction = "INBOUND" if 180 < course < 360 else "OUTBOUND"
                    shown = bool(seg.ais and v.mmsi)
                    if online(self.win[cam], t):
                        events.append((t, [zstr(t), cam, "PASSAGE", direction, str(v.mmsi) if shown else "", nm if shown else "UNIDENTIFIED",
                                           f"{v.loa * 1.0:.0f}", "", "", "", ""]))
                    if v.loa >= 20 and v.cls not in ("ferry",):
                        vts.append((t, cp, direction, v, seg, shown))
        # berth arrivals and departures, merged across consecutive stays of the same ship at the same berth
        alongside = {}
        for b, lst in stays_by_berth.items():
            lst.sort(key=lambda x: x[0])
            merged = []
            for a, e, v in lst:
                if merged and merged[-1][2] is v and a - merged[-1][1] < 300:
                    merged[-1][1] = e
                else:
                    merged.append([a, e, v])
            alongside[b] = merged
            cam = berth_cam[b]
            for a, e, v in merged:
                if T0 <= a and online(self.win[cam], a):
                    events.append((a, [zstr(a), cam, "BERTH ARRIVAL", "", str(v.mmsi or ""), ais_name(v.name), f"{v.loa:.0f}", b, "", "", ""]))
                if e < T_END and online(self.win[cam], e):
                    events.append((e, [zstr(e), cam, "BERTH DEPARTURE", "", str(v.mmsi or ""), ais_name(v.name), f"{v.loa:.0f}", b, "", "", ""]))
        # frames every two hours, plus the frames canon singles out
        special = {ts("2027-09-14T02:29Z"): "last frame before loss of shore power", ts("2027-09-15T14:10Z"): "first frame after restoration"}
        for c in cams:
            cid, berths = c["sensor_id"], c.get("berths", [])
            if not berths:
                continue
            times = list(np.arange(math.ceil(T0 / 7200.0) * 7200.0, T_END, 7200.0))
            if cid == "CAM-01":
                times += list(special)
            for t in sorted(times):
                if not online(self.win[cid], t) and not (cid == "CAM-01" and t == ts("2027-09-14T02:29Z")):
                    continue
                here = []
                for b in berths:
                    for a, e, v in alongside.get(b, []):
                        if a <= t < e:
                            here.append(f"{ais_name(v.name)} ({b})")
                surf = ""
                note = special.get(t, "") if cid == "CAM-01" else ""
                if cid in ("CAM-01", "CAM-02", "CAM-03"):
                    surf = self.surface(t)
                    if cid == "CAM-01" and t == ts("2027-09-14T02:29Z"):
                        note += "; mooring lines intact; no visible sheen"
                    if cid == "CAM-01" and ts("2027-09-15T14:00Z") <= t < local_ts(20, "17:00"):
                        note = (note + "; " if note else "") + "containment boom across the berth"
                events.append((t, [zstr(t), cid, "FRAME", "", "", "", "", "", "; ".join(here) if here else "none", surf, note.strip("; ")]))
        # the jetty camera on the night of D+44
        bp = getattr(sim, "blast_point", None)
        if bp:
            cb = sim.vessels["VSL-0077"]
            events.append((BLAST + 3, [zstr(BLAST + 3), "CAM-13", "INCIDENT", "", str(cb.mmsi), ais_name(cb.name), f"{cb.loa:.0f}", "", "",
                                       "", "flash and water column close aboard the tug in the jetty channel; tug loses way"]))
        events.sort(key=lambda x: (x[0], x[1][1]))
        with open(out_path("05_other_sources/port_surveillance/camera_events.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(CAMERA_HEADER)
            for _, r in events:
                w.writerow(r)
        # vessel traffic log: pilot orders, tugs, origin and destination where a pilot order exists
        order_at = {}
        for tr in sim.transits:
            for key in ("t_jetty", "t_bridge"):
                if tr.get(key) is not None:
                    order_at[(tr["v"].id, int(tr[key] // 60))] = tr
        rows = []
        for t, cp, direction, v, seg, shown in sorted(vts, key=lambda x: x[0]):
            tr = None
            for dm in (0, -1, 1, -2, 2):
                tr = order_at.get((v.id, int(t // 60) + dm))
                if tr:
                    break
            if tr:
                origin, dest = ("SEA", tr["berth"]) if tr["dir"] == "IN" else (tr["berth"], "SEA")
                rows.append([zstr(t), cp, direction, str(v.mmsi or ""), ais_name(v.name), v.cls, tr["order"], tr.get("pilot_boat", ""), "; ".join(tr.get("tugs", [])), origin, dest])
            else:
                rows.append([zstr(t), cp, direction, str(v.mmsi) if shown else "", ais_name(v.name) if shown else "UNIDENTIFIED", v.cls if shown else "", "", "", "", "", ""])
        for tr in sim.transits:
            if tr["dir"] == "SHIFT":
                rows.append([zstr(tr["t_start"]), "INNER HARBOR", "SHIFT", str(tr["v"].mmsi), ais_name(tr["v"].name), tr["v"].cls, tr["order"], "", "; ".join(tr["tugs"]),
                             tr["from_berth"], tr["berth"]])
        rows.sort(key=lambda r: r[0])
        with open(out_path("05_other_sources/port_surveillance/vessel_traffic_log.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(VTS_HEADER)
            w.writerows(rows)
        return len(events), len(rows)

    def write_status_and_sensors(self):
        sim = self.sim
        rows = []
        for s in sim.sensors:
            sid = s["sensor_id"]
            if sid == "VTS-CC":
                continue
            t = math.ceil(T0 / 3600.0) * 3600.0
            while t < T_END:
                if sid == "RADAR-BUOY-SW" and sim.buoy_sw_live_lost <= t < ts("2027-09-15T11:00Z"):
                    st, det = "NO UPLINK", "recording to onboard buffer"
                elif online(self.win[sid], t):
                    st, det = "ONLINE", ""
                else:
                    st, det = "OFFLINE", ""
                rows.append([zstr(t), sid, st, det])
                t += 3600.0
        # the moments things changed, and the buffer recovery
        extra = [(ts("2027-09-14T02:30Z"), s_["sensor_id"], "OFFLINE", "loss of shore power; all fixed cameras dark")
                 for s_ in sim.sensors if s_["sensor_type"] == "fixed camera"]
        extra += [(sim.buoy_sw_live_lost, "RADAR-BUOY-SW", "NO UPLINK", "live feed lost; antenna damage; onboard buffer recording"),
                 (ts("2027-09-14T05:10Z"), "RADAR-BUOY-NE", "OFFLINE", "feed lost"),
                 (sim.buoy_sw_buffer_recovered, "RADAR-BUOY-SW", "BUFFER RECOVERED",
                  "BUOY-SW-REC-20270915: continuous radar record 2027-09-14T03:38Z to 2027-09-15T11:00Z recovered from onboard buffer"),
                 (ts("2027-09-15T11:00Z"), "RADAR-BUOY-SW", "OFFLINE", "buffer full; awaiting antenna repair"),
                 (ts("2027-09-16T19:30Z"), "RADAR-BUOY-NE", "ONLINE", "feed restored"),
                 (ts("2027-10-02T15:00Z"), "RADAR-BUOY-SW", "ONLINE", "antenna repaired; live feed restored"),
                 (ts("2027-09-19T09:00Z"), "VTS-CC", "ARCHIVE EXPORT", "camera, radar and AIS archive 2027-09-11 to 2027-09-19 handed to investigators")]
        for sid, wins in self.win.items():
            if sid.startswith("CAM") and len(wins) > 1:
                extra.append((wins[1][0], sid, "ONLINE", "camera restored"))
        for t, sid, st, det in extra:
            rows.append([zstr(t), sid, st, det])
        rows.sort(key=lambda r: (r[0], r[1]))
        with open(out_path("05_other_sources/port_surveillance/sensor_status.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(STATUS_HEADER)
            w.writerows(rows)
        with open(out_path("05_other_sources/port_surveillance/sensors.csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["sensor_id", "sensor_type", "name", "latitude", "longitude", "range_nm", "berths_in_view"])
            for s in sim.sensors:
                w.writerow([s["sensor_id"], s["sensor_type"], s["name"], s["latitude"], s["longitude"], s["range_nm"], "; ".join(s.get("berths", []))])
        return len(rows)
