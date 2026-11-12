"""Check every position in the corpus against real geography (scripts/geo.py).

    python scripts/check_geo.py            full report, exit 1 if any violation
    python scripts/check_geo.py --brief    one line per source
    python scripts/check_geo.py --only=registry   only sources whose name contains the text
    python scripts/check_geo.py --resume   run in pieces of about 150 s; repeat until it prints COMPLETE

What is checked is declared in 99_reference/geo/position_rules.json, one entry per source:

  {"name": "AIS", "glob": "05_other_sources/ais/*.csv", "lat": "LAT", "lon": "LON",
   "rule": "vessel", "id": "MMSI", "time": "BaseDateTime", "speed": "SOG", "draft_m": "Draft"}

Rules
  vessel          never on land. Deep-draft vessels (draft >= 9 m, or listed deep in the registry)
                  inside the local window must be in a USACE channel maintained to >= 40 ft
                  (within 150 m, which covers berths alongside), in a NOAA anchorage, or in the
                  open Gulf seaward of the sea bar. Other vessels must have >= 30 m of water around
                  them unless they are within 150 m of a channel or 200 m of a dock or marina.
                  Consecutive fixes less than 30 minutes apart must not have land between them,
                  and implied speed must be plausible.
  land_fixed      on land (>= 0 m). Used for buildings, substations, stations, monitors on shore.
  water_fixed     in water (sondes, buoys); "shore_ok": true allows gauges fixed to piers.
  incident        on land and within 150 m of a street in the reference network (which holds every
                  Census local road in the window).
  vehicle         within 30 m of a road centreline (bridges and causeways count: no land test).
  aircraft_ground rows where the on-ground flag is true must be within 500 m of a runway
                  centreline, or within 300 m of a helipad, hospital, airport or heliport landmark.
  berth           in water, beside a channel of the depth the berth needs (or a real dock).
  airfield_fixed  aircraft parking positions: on land at an airfield or helipad.
  station         response-unit stations: on land, within 400 m of a road in the network.
  on_land_or_air  only checks coordinates are finite and inside the Gulf region (drones, aircraft
                  in flight).

Writes 07_validation/reports/geo_check.json.
"""
import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402

ROOT = geo.ROOT
RULES = os.path.join(geo.GEO_DIR, "position_rules.json")
REPORT = os.path.join(ROOT, "07_validation", "reports", "geo_check.json")
SEA_BAR_LON = -96.9636            # seaward end of the USACE sea bar channel
LOCAL_STREET_BOXES = [(-97.395, 27.815, -97.375, 27.845), (-97.425, 27.800, -97.400, 27.815),
                      (-97.455, 27.755, -97.430, 27.775), (-97.320, 27.655, -97.285, 27.685),
                      (-97.640, 27.855, -97.610, 27.880), (-97.085, 27.820, -97.050, 27.845),
                      (-97.405, 27.785, -97.390, 27.805)]
MAX_KN = {"vessel": 45.0}


def parse_time(s):
    import datetime as dt
    s = str(s).strip()
    if not s:
        return None
    try:
        if s.replace(".", "", 1).isdigit():
            return float(s)
        s = s.replace("Z", "+00:00").replace(" ", "T", 1)
        d = dt.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return d.timestamp()
    except Exception:
        return None


def get_path(obj, path):
    for k in path.split("."):
        if obj is None:
            return None
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj


def read_rows(rule):
    """Yield dict rows for a rule from csv / json / jsonl / geojson sources."""
    for fp in sorted(glob.glob(os.path.join(ROOT, rule["glob"]), recursive=True)):
        if "_consolidated" in fp and not rule.get("include_consolidated"):
            continue
        rel = os.path.relpath(fp, ROOT)
        if fp.endswith(".csv"):
            with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
                for i, row in enumerate(csv.DictReader(fh)):
                    row["_src"] = rel; row["_row"] = i + 2
                    yield row
        elif fp.endswith(".jsonl"):
            with open(fp, encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if line.strip():
                        row = json.loads(line); row["_src"] = rel; row["_row"] = i + 1
                        yield row
        else:
            data = json.load(open(fp, encoding="utf-8"))
            items = get_path(data, rule["items"]) if rule.get("items") else data
            if isinstance(items, dict):
                items = list(items.values())
            for i, row in enumerate(items or []):
                if isinstance(row, dict):
                    row = dict(row); row["_src"] = rel; row["_row"] = i
                    yield row


def in_local_streets(lat, lon):
    return any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] for b in LOCAL_STREET_BOXES)


class Checker:
    """Runs one rule at a time. Large CSV sources are handled with rasters first (a point well
    clear of land, well inside a channel corridor or road corridor passes immediately) and only
    the borderline points get the exact polygon or segment test, so the verdicts are exact."""

    def __init__(self):
        self.G = geo.Geo()
        self.docks = np.array([(l["lat"], l["lon"]) for l in self.G.find(["port_dock", "marina", "ferry", "coast_guard"])])
        self.pads = np.array([(l["lat"], l["lon"]) for l in self.G.find(["helipad", "hospital", "airport"])])
        self.results = []
        self._r = {}

    # ---------------------------------------------------------------- rasters
    def _px(self, lats, lons):
        G = self.G
        r = ((geo.BOX[3] - lats) * geo.M_PER_DEG_LAT / geo.RASTER_M).astype(int)
        c = ((lons - geo.BOX[0]) * geo.M_PER_DEG_LON / geo.RASTER_M).astype(int)
        inb = (r >= 0) & (r < G.ny) & (c >= 0) & (c < G.nx)
        return np.clip(r, 0, G.ny - 1), np.clip(c, 0, G.nx - 1), inb

    def corridor(self, min_depth_ft, buffer_m):
        """Raster: within (buffer_m - 40) m of a channel polygon of at least min_depth_ft (a safe
        under-estimate of the buffer, so 'inside' needs no exact test)."""
        key = ("ch", min_depth_ft, buffer_m)
        if key not in self._r:
            import cv2
            G = self.G
            img = np.zeros((G.ny, G.nx), np.uint8)
            for it in G.channels.items:
                if (it["props"].get("depth_ft") or 0) >= min_depth_ft:
                    cv2.fillPoly(img, [G._to_px(it["xy"])], 1)
            k = max(0, int((buffer_m - 40) / geo.RASTER_M))
            if k:
                img = cv2.dilate(img, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
            self._r[key] = img.astype(bool)
        return self._r[key]

    def road_corridor(self, tol_m):
        """Raster at 10 m: within (tol_m - 12) m of a road centreline (under-estimate)."""
        key = ("road", tol_m)
        if key not in self._r:
            import cv2
            G = self.G
            res = 10.0
            nx = int((geo.BOX[2] - geo.BOX[0]) * geo.M_PER_DEG_LON / res); ny = int((geo.BOX[3] - geo.BOX[1]) * geo.M_PER_DEG_LAT / res)
            img = np.zeros((ny, nx), np.uint8)
            thick = max(1, int(2 * (tol_m - 12) / res))
            for _, _, pts in G.roads.features:
                a = np.array(pts)
                xy = np.column_stack([(a[:, 1] - geo.BOX[0]) * geo.M_PER_DEG_LON / res, (geo.BOX[3] - a[:, 0]) * geo.M_PER_DEG_LAT / res])
                cv2.polylines(img, [np.round(xy).astype(np.int32)], False, 1, thickness=thick)
            self._r[key] = (img.astype(bool), res, ny, nx)
        return self._r[key]

    def near(self, arr, lat, lon):
        d = np.hypot((arr[:, 0] - lat) * geo.M_PER_DEG_LAT, (arr[:, 1] - lon) * geo.M_PER_DEG_LON)
        return float(d.min())

    def land_exact(self, lats, lons):
        """Exact land test, skipping points the raster shows are >= 60 m from land or >= 60 m inland."""
        G = self.G
        out = np.zeros(len(lats), bool)
        r, c, inb = self._px(lats, lons)
        sure_water = inb & (G.dist_land[r, c] >= 60)
        sure_land = inb & (G.dist_water[r, c] >= 60)
        out[sure_land] = True
        rest = ~(sure_water | sure_land)
        if rest.any():
            out[rest] = G.is_land_many(lats[rest], lons[rest])
        return out

    # ---------------------------------------------------------------- reading
    def read(self, rule):
        """Columns needed by the rule as parallel lists: lat, lon, ident, time, draft, ground, src, row."""
        cols = {"lat": [], "lon": [], "id": [], "t": [], "draft": [], "ground": [], "src": [], "row": []}
        bad = 0
        for fp in sorted(glob.glob(os.path.join(ROOT, rule["glob"]), recursive=True)):
            if "_consolidated" in fp:
                continue
            rel = os.path.relpath(fp, ROOT)
            if fp.endswith(".csv"):
                with open(fp, encoding="utf-8", errors="replace", newline="") as fh:
                    rd = csv.reader(fh)
                    try:
                        h = next(rd)
                    except StopIteration:
                        continue
                    ix = {k: (h.index(rule[k]) if rule.get(k) in h else None) for k in ("lat", "lon", "id", "time", "draft_m", "ground")}
                    if ix["lat"] is None or ix["lon"] is None:
                        bad += 1
                        continue
                    wk, wv = (rule["where"][0], [str(x).lower() for x in (rule["where"][1] if isinstance(rule["where"][1], list) else [rule["where"][1]])]) if rule.get("where") else (None, None)
                    wi = h.index(wk) if wk in h else None
                    for n, row in enumerate(rd, start=2):
                        if wi is not None and row[wi].lower() not in wv:
                            continue
                        try:
                            la, lo = float(row[ix["lat"]]), float(row[ix["lon"]])
                        except (ValueError, IndexError):
                            if not rule.get("allow_missing"):
                                bad += 1
                            continue
                        cols["lat"].append(la); cols["lon"].append(lo)
                        cols["id"].append(row[ix["id"]] if ix["id"] is not None else "")
                        cols["t"].append(row[ix["time"]] if ix["time"] is not None else "")
                        cols["draft"].append(row[ix["draft_m"]] if ix["draft_m"] is not None else "")
                        cols["ground"].append(row[ix["ground"]] if ix["ground"] is not None else "")
                        cols["src"].append(rel); cols["row"].append(n)
            else:
                for r in read_rows(dict(rule, glob=os.path.relpath(fp, ROOT))):
                    if rule.get("where"):
                        k, v = rule["where"]
                        if str(get_path(r, k)).lower() not in [str(x).lower() for x in (v if isinstance(v, list) else [v])]:
                            continue
                    try:
                        la, lo = float(get_path(r, rule["lat"])), float(get_path(r, rule["lon"]))
                    except (TypeError, ValueError):
                        if not rule.get("allow_missing"):
                            bad += 1
                        continue
                    cols["lat"].append(la); cols["lon"].append(lo)
                    cols["id"].append(str(get_path(r, rule["id"])) if rule.get("id") else "")
                    cols["t"].append(get_path(r, rule["time"]) if rule.get("time") else "")
                    cols["draft"].append(get_path(r, rule.get("draft_m", "")) if rule.get("draft_m") else "")
                    cols["ground"].append(get_path(r, rule.get("ground", "")) if rule.get("ground") else "")
                    cols["src"].append(r["_src"]); cols["row"].append(r["_row"])
                    if rule["rule"] == "berth":
                        cols.setdefault("need", []).append(get_path(r, rule.get("min_depth_field", "min_channel_depth_ft")) or 0)
        return cols, bad

    # ---------------------------------------------------------------- rules
    def run(self, rule):
        G = self.G
        cols, bad_coord = self.read(rule)
        lats = np.array(cols["lat"], float); lons = np.array(cols["lon"], float)
        finite = np.isfinite(lats) & np.isfinite(lons) & (lats >= 17) & (lats <= 34) & (lons >= -100) & (lons <= -79)
        out = {"name": rule["name"], "rule": rule["rule"], "rows": int(len(lats)), "violations": 0, "by_kind": defaultdict(int),
               "examples": [], "bad_coordinates": int(bad_coord + (~finite).sum())}
        if out["bad_coordinates"]:
            out["violations"] += out["bad_coordinates"]; out["by_kind"]["missing or out-of-region coordinates"] += out["bad_coordinates"]

        def flag(kind, i, extra=""):
            out["violations"] += 1; out["by_kind"][kind] += 1
            if len(out["examples"]) < 12:
                out["examples"].append(f"{kind}: {cols['id'][i]} {lats[i]:.5f},{lons[i]:.5f} {extra} [{cols['src'][i]}:{cols['row'][i]}]")

        kind = rule["rule"]
        n = len(lats)
        if n == 0:
            pass
        elif kind == "vessel":
            self.vessel(rule, cols, lats, lons, finite, flag)
        elif kind == "land_fixed":
            land = self.land_exact(lats, lons)
            for i in np.where(finite & ~land)[0]:
                flag("land asset in water", i, f"{G.land_clearance_m(lats[i], lons[i]):.0f} m from shore")
        elif kind == "water_fixed":
            land = self.land_exact(lats, lons)
            for i in np.where(finite & land)[0]:
                if not (rule.get("shore_ok") and G.shore_distance_m(lats[i], lons[i]) <= 60):
                    flag("water asset on land", i, f"{G.shore_distance_m(lats[i], lons[i]):.0f} m inland")
        elif kind == "berth":
            for i in range(n):
                try:
                    need = float(cols.get("need", [0] * n)[i] or 0)
                except (TypeError, ValueError):
                    need = 0
                if G.is_land(lats[i], lons[i]):
                    flag("berth position on land", i, f"{G.shore_distance_m(lats[i], lons[i]):.0f} m inland")
                elif not G.channel_at(lats[i], lons[i], 150, need) and self.near(self.docks, lats[i], lons[i]) > 250:
                    flag("berth not beside a channel of the required depth or a real dock", i,
                         f"needs {need:.0f} ft; {G.channel_distance_m(lats[i], lons[i], need):.0f} m from such a channel")
        elif kind == "airfield_fixed":
            for i in range(n):
                if not G.in_box(lats[i], lons[i]):
                    continue
                dr, _ = G.runway_distance_m(lats[i], lons[i])
                if not G.is_land(lats[i], lons[i]) or (dr > 900 and self.near(self.pads, lats[i], lons[i]) > 300):
                    flag("aircraft parking position not at an airfield or helipad", i, f"{dr:.0f} m from nearest runway")
        elif kind == "station":
            d = G.roads.distance_many(lats, lons); land = G.is_land_many(lats, lons)
            for i in range(n):
                if not G.in_box(lats[i], lons[i]):
                    continue
                if not land[i]:
                    flag("station in water", i)
                elif d[i] > 400:
                    flag("station not near any road in the reference network", i, f"{d[i]:.0f} m")
        elif kind == "incident":
            land = self.land_exact(lats, lons)
            d = self.road_distance(lats, lons, 150)
            for i in np.where(finite)[0]:
                if not land[i]:
                    flag("location in water", i)
                elif d[i] > 150:                      # the reference network holds every local street in the window
                    flag("location not near any street", i, f"{d[i]:.0f} m from nearest road")
        elif kind == "vehicle":
            tol = rule.get("tolerance_m", 30)
            d = self.road_distance(lats, lons, tol)
            for i in np.where(finite & (d > tol))[0]:
                flag("vehicle off the road", i, f"{d[i]:.0f} m from nearest road")
        elif kind == "aircraft_ground":
            g = np.array([str(x).lower() in ("true", "1", "yes") for x in cols["ground"]])
            inb = (lons >= geo.BOX[0]) & (lons <= geo.BOX[2]) & (lats >= geo.BOX[1]) & (lats <= geo.BOX[3])
            idx = np.where(g & inb & finite)[0]
            if len(idx):
                px, py = lons[idx] * geo.M_PER_DEG_LON, lats[idx] * geo.M_PER_DEG_LAT
                best = np.full(len(idx), np.inf)
                for rws in G.runways.values():
                    for _, a, b in rws:
                        d, _, _ = geo._seg_dist(px, py, a[1] * geo.M_PER_DEG_LON, a[0] * geo.M_PER_DEG_LAT, b[1] * geo.M_PER_DEG_LON, b[0] * geo.M_PER_DEG_LAT)
                        best = np.minimum(best, d)
                padd = np.full(len(idx), np.inf)
                for la, lo in self.pads:
                    padd = np.minimum(padd, np.hypot(px - lo * geo.M_PER_DEG_LON, py - la * geo.M_PER_DEG_LAT))
                for k in np.where((best > 500) & (padd > 300))[0]:
                    flag("aircraft on the ground away from any airfield or helipad", idx[k], f"{best[k]:.0f} m from nearest runway")
        out["by_kind"] = dict(out["by_kind"])
        self.results.append(out)
        return out

    def road_distance(self, lats, lons, tol):
        """Distance to the nearest road; points inside the raster corridor get 0 without the exact test."""
        mask, res, ny, nx = self.road_corridor(tol)
        r = ((geo.BOX[3] - lats) * geo.M_PER_DEG_LAT / res).astype(int); c = ((lons - geo.BOX[0]) * geo.M_PER_DEG_LON / res).astype(int)
        inb = (r >= 0) & (r < ny) & (c >= 0) & (c < nx)
        ok = np.zeros(len(lats), bool)
        ok[inb] = mask[r[inb], c[inb]]
        d = np.zeros(len(lats))
        if (~ok).any():
            d[~ok] = self.G.roads.distance_many(lats[~ok], lons[~ok])
        return d

    def vessel(self, rule, cols, lats, lons, finite, flag):
        G = self.G
        n = len(lats)
        land = self.land_exact(lats, lons)
        for i in np.where(finite & land)[0]:
            flag("vessel on land", i)
        draft = np.zeros(n)
        for i, v in enumerate(cols["draft"]):
            try:
                draft[i] = float(v or 0)
            except (TypeError, ValueError):
                pass
        r, c, inb = self._px(lats, lons)
        local = inb & (lons < SEA_BAR_LON) & finite & ~land
        deep = local & (draft >= rule.get("deep_draft_m", 9.0))
        try:                                  # ships the registry marks deep-draft are held to the deep channel even in ballast
            reg = json.load(open(os.path.join(ROOT, "06_data_streams", "vessels.json"), encoding="utf-8"))["vessels"]
            deep_ids = {str(v.get("mmsi")) for v in reg if v.get("deep_draft")}
            deep |= local & np.isin(np.array(cols["id"]), list(deep_ids))
        except Exception:
            pass
        cand = np.where(deep & ~self.corridor(40, 150)[r, c])[0]
        for i in cand:
            if not (G.channel_at(lats[i], lons[i], 150, 40) or G.anchorages.contains(lats[i], lons[i])):
                flag("deep-draft vessel outside deep channel", i, f"draft {draft[i]} m, {G.channel_distance_m(lats[i], lons[i], 40):.0f} m from channel")
        shallow = local & ~deep
        cand = np.where(shallow & (G.dist_land[r, c] < 60) & ~self.corridor(0, 150)[r, c])[0]
        for i in cand:
            if G.land_clearance_m(lats[i], lons[i]) < 30 and not G.channel_at(lats[i], lons[i], 150) and self.near(self.docks, lats[i], lons[i]) > 200:
                flag("vessel aground (no water around it, not at a dock)", i)
        if not rule.get("time"):
            return
        t = np.array([parse_time(x) or np.nan for x in cols["t"]])
        ids = np.array(cols["id"])
        order = np.lexsort((t, ids))
        a, b = order[:-1], order[1:]
        same = (ids[a] == ids[b]) & np.isfinite(t[a]) & np.isfinite(t[b])
        dt_s = t[b] - t[a]
        dy = (lats[b] - lats[a]) * geo.M_PER_DEG_LAT; dx = (lons[b] - lons[a]) * 111_320.0 * np.cos(np.radians((lats[a] + lats[b]) / 2))
        dm = np.hypot(dx, dy)
        with np.errstate(divide="ignore", invalid="ignore"):
            kn = dm / 1852.0 / (dt_s / 3600.0)
        for k in np.where(same & (dt_s > 0) & (kn > MAX_KN["vessel"]) & (dm > 550))[0]:
            flag("impossible speed between fixes", b[k], f"{kn[k]:.0f} kn over {dt_s[k] / 60:.0f} min")
        seg = np.where(same & (dt_s > 0) & (dt_s <= 1800) & (dm > 90) & ~(kn > MAX_KN["vessel"]) & ~land[a] & ~land[b])[0]
        # raster pass: sample each segment every ~20 m; clear if every sample is >= 40 m from land
        suspect = []
        for s0 in range(0, len(seg), 20000):
            sk = seg[s0:s0 + 20000]
            m = np.maximum(2, np.ceil(dm[sk] / 20).astype(int))
            for mm in np.unique(np.minimum(m, 400)):
                sel = sk[np.minimum(m, 400) == mm]
                f = np.linspace(0, 1, mm + 1)[None, :]
                la = lats[a[sel]][:, None] + (lats[b[sel]] - lats[a[sel]])[:, None] * f
                lo = lons[a[sel]][:, None] + (lons[b[sel]] - lons[a[sel]])[:, None] * f
                rr, cc, ib = self._px(la.ravel(), lo.ravel())
                near_land = (G.dist_land[rr, cc] < 40) & ib
                # outside the local window: test the coarse layer exactly below
                near_land |= ~ib
                bad = near_land.reshape(la.shape).any(axis=1)
                suspect += list(sel[bad])
        for k in suspect:
            p, q = (lats[a[k]], lons[a[k]]), (lats[b[k]], lons[b[k]])
            if not G.segment_clear(p, q, 20):
                flag("track crosses land between fixes", b[k], f"{dt_s[k] / 60:.0f} min gap")


def expand(rules, split_mb=25.0):
    """Split a rule into one unit per file when its files are large, so the check can be run in
    resumable pieces. (Track continuity across a file boundary is then not tested.)"""
    units = []
    for r in rules:
        files = [f for f in sorted(glob.glob(os.path.join(ROOT, r["glob"]), recursive=True)) if "_consolidated" not in f]
        total = sum(os.path.getsize(f) for f in files) / 1e6
        if total > split_mb and len(files) > 1:
            for f in files:
                units.append(dict(r, glob=os.path.relpath(f, ROOT), _unit=f"{r['name']} :: {os.path.basename(f)}", _group=r["name"]))
        else:
            units.append(dict(r, _unit=r["name"], _group=r["name"]))
    return units


def main():
    """--resume keeps finished units in geo_check.progress.json and stops cleanly before
    --budget=<seconds> (default 150) runs out; call it repeatedly until it prints COMPLETE."""
    import time
    brief = "--brief" in sys.argv
    resume = "--resume" in sys.argv
    budget = next((float(a.split("=")[1]) for a in sys.argv if a.startswith("--budget=")), 150.0 if resume else 1e9)
    rules = json.load(open(RULES, encoding="utf-8"))["sources"]
    for extra in sorted(glob.glob(os.path.join(geo.GEO_DIR, "position_rules.d", "*.json"))):
        rules += json.load(open(extra, encoding="utf-8"))["sources"]
    only = [a.split("=", 1)[1].lower() for a in sys.argv if a.startswith("--only=")]
    if only:
        rules = [r for r in rules if any(o in r["name"].lower() for o in only)]
    units = expand(rules)
    prog_path = REPORT.replace(".json", ".progress.json")
    done = json.load(open(prog_path)) if resume and os.path.exists(prog_path) else {}
    t0 = time.time()
    C = None
    pending = [u for u in units if u["_unit"] not in done]
    for u in pending:
        if time.time() - t0 > budget:
            break
        if C is None:
            C = Checker()
        o = C.run(dict(u, name=u["_unit"]))
        o["group"] = u["_group"]
        done[u["_unit"]] = o
        if resume:
            json.dump(done, open(prog_path, "w"))
    remaining = [u["_unit"] for u in units if u["_unit"] not in done]
    results = [done[u["_unit"]] for u in units if u["_unit"] in done]
    total = sum(o["violations"] for o in results)
    for o in results:
        status = "ok  " if not o["violations"] else "FAIL"
        print(f"{status} {o['name'][:58]:<58} {o['rule']:<16} rows {o['rows']:>8}  violations {o['violations']:>7}")
        if o["rows"] == 0 and o["rule"] != "on_land_or_air":
            print("       (no rows found: check the glob/columns in the rules)")
        if not brief:
            for k, n in o["by_kind"].items():
                print(f"       {n:>7}  {k}")
            for e in o["examples"][:4]:
                print(f"         e.g. {e}")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    json.dump({"complete": not remaining, "total_violations": total, "rows_checked": sum(o["rows"] for o in results), "sources": results},
              open(REPORT, "w", encoding="utf-8"), indent=1)
    if remaining:
        print(f"\nINCOMPLETE: {len(remaining)} of {len(units)} pieces still to check (run again with --resume); {total} violation(s) so far")
        sys.exit(2)
    print(f"\nCOMPLETE - {'PASS' if total == 0 else 'FAILED'}: {total} violation(s) in {sum(o['rows'] for o in results):,} positions across {len(units)} pieces")
    if resume and os.path.exists(prog_path):
        os.remove(prog_path)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
