"""Geographic ground truth for the Rafael corpus.

Everything here is built from real, published geometry in 99_reference/geo/ (see the SOURCES_*.md
files there): USACE National Channel Framework reaches and centerlines, NOAA ENC land areas,
anchorages and fairways, Census TIGER roads, and real landmark points (docks, airports, runway
ends, hospitals, stations). Generators use it to place and route things; check_geo.py uses the
same functions to verify every position in the corpus. Nothing in this module invents geometry.

    import geo
    G = geo.Geo()                      # loads and caches
    G.is_land(lat, lon)                # exact point-in-polygon on NOAA land areas
    G.land_clearance_m(lat, lon)       # metres to nearest land (0 on land), 25 m raster
    G.channel_at(lat, lon, buffer_m)   # USACE reach id containing the point, or None
    G.nav.route(a, b, draft_ft)        # channel-centerline route between two (lat, lon)
    G.water.route(a, b, clearance_m)   # open-water route for small craft (grid A*)
    G.roads.route(a, b)                # street route, list of (lat, lon)
    G.roads.nearest(lat, lon)          # (distance_m, snapped lat, lon, road name)

Coordinates are (lat, lon) in function arguments and results; GeoJSON on disk is lon, lat.
Python 3.8+, numpy, matplotlib (for Path), opencv (for rasters).
"""
import heapq
import json
import math
import os

import numpy as np
from matplotlib.path import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEO_DIR = os.path.join(ROOT, "99_reference", "geo")
CACHE = os.path.join(GEO_DIR, "_cache")

# local window covered by harbour-scale land polygons
BOX = (-97.65, 27.525, -96.85, 28.125)          # lon_min, lat_min, lon_max, lat_max
LAT0 = 27.8
M_PER_DEG_LAT = 110_950.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))
COARSE_WEST_EDGE = -98.1                         # land_gulf_coarse is clipped here; west of it is inland
RASTER_M = 25.0                                  # land raster cell


def dist_m(a, b):
    """Metres between two (lat, lon) points (equirectangular; fine at this scale)."""
    dy = (b[0] - a[0]) * M_PER_DEG_LAT
    dx = (b[1] - a[1]) * 111_320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dx, dy)


def gc_nm(a, b):
    """Great-circle nautical miles between (lat, lon) points."""
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 3440.065 * math.asin(min(1.0, math.sqrt(h)))


def bearing(a, b):
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _load(name):
    with open(os.path.join(GEO_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)["features"]


def _rings(geom):
    """Yield (outer_ring, [holes]) for Polygon / MultiPolygon."""
    if geom["type"] == "Polygon":
        yield geom["coordinates"][0], geom["coordinates"][1:]
    elif geom["type"] == "MultiPolygon":
        for p in geom["coordinates"]:
            yield p[0], p[1:]


def _lines(geom):
    if geom["type"] == "LineString":
        yield geom["coordinates"]
    elif geom["type"] == "MultiLineString":
        for l in geom["coordinates"]:
            yield l


class PolySet:
    """A set of polygons with bbox prefilter and exact contains tests (holes respected)."""

    def __init__(self, features):
        self.items = []
        for f in features:
            for outer, holes in _rings(f["geometry"]):
                a = np.asarray(outer, dtype=float)
                self.items.append({"path": Path(a), "holes": [Path(np.asarray(h, dtype=float)) for h in holes],
                                   "bbox": (a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()),
                                   "xy": a, "props": f["properties"]})

    def contains(self, lat, lon):
        return self.which(lat, lon) is not None

    def which(self, lat, lon):
        for it in self.items:
            b = it["bbox"]
            if b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and it["path"].contains_point((lon, lat)):
                if not any(h.contains_point((lon, lat)) for h in it["holes"]):
                    return it
        return None

    def contains_many(self, lats, lons):
        lats, lons = np.asarray(lats, float), np.asarray(lons, float)
        out = np.zeros(len(lats), bool)
        pts = np.column_stack([lons, lats])
        for it in self.items:
            b = it["bbox"]
            m = (~out) & (lons >= b[0]) & (lons <= b[2]) & (lats >= b[1]) & (lats <= b[3])
            if m.any():
                inside = it["path"].contains_points(pts[m])
                for h in it["holes"]:
                    inside &= ~h.contains_points(pts[m])
                idx = np.where(m)[0]
                out[idx[inside]] = True
        return out


def _seg_dist(px, py, ax, ay, bx, by):
    """Distance (same units) from point to segments; arrays of segments."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = np.where(L2 > 0, ((px - ax) * dx + (py - ay) * dy) / np.where(L2 > 0, L2, 1), 0.0)
    t = np.clip(t, 0, 1)
    cx, cy = ax + t * dx, ay + t * dy
    return np.hypot(px - cx, py - cy), cx, cy


class Geo:
    def __init__(self, build_roads=True):
        os.makedirs(CACHE, exist_ok=True)
        self.land = PolySet(_load("land_local.geojson"))
        self.water_override = PolySet(_load("water_overrides_local.geojson"))
        self.land_coarse = PolySet(_load("land_gulf_coarse.geojson"))
        ch = _load("channels_usace.geojson")
        self.channels = PolySet(ch)
        self.channel_props = {f["properties"]["reach_id"]: f["properties"] for f in ch}
        af = _load("anchorages_fairways_noaa.geojson")
        self.anchorages = PolySet([f for f in af if f["properties"]["kind"] == "anchorage"])
        self.fairways = PolySet([f for f in af if f["properties"]["kind"] == "fairway"])
        self.landmarks = [dict(f["properties"], lat=f["geometry"]["coordinates"][1], lon=f["geometry"]["coordinates"][0])
                          for f in _load("landmarks.geojson")]
        self._raster()
        self._channel_edges()
        self.nav = NavGraph(self)
        self.water = WaterGrid(self)
        self.roads = RoadNet(self) if build_roads else None
        self.runways = self._runways()

    # ------------------------------------------------------------------ land / water
    def in_box(self, lat, lon):
        return BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]

    def is_land(self, lat, lon):
        """True if the point is on land. Local window: NOAA harbour/coastal land areas (10-30 m),
        with Census water overrides. Elsewhere: coarse Gulf-wide land (about 1.6 km)."""
        if self.in_box(lat, lon):
            if self.water_override.contains(lat, lon):
                return False
            return self.land.contains(lat, lon)
        if lon < COARSE_WEST_EDGE:          # west of the coarse coastline file: interior of the continent
            return True
        return self.land_coarse.contains(lat, lon)

    def is_land_many(self, lats, lons):
        lats, lons = np.asarray(lats, float), np.asarray(lons, float)
        inb = (lons >= BOX[0]) & (lons <= BOX[2]) & (lats >= BOX[1]) & (lats <= BOX[3])
        out = np.zeros(len(lats), bool)
        if inb.any():
            l = self.land.contains_many(lats[inb], lons[inb])
            w = self.water_override.contains_many(lats[inb], lons[inb])
            out[inb] = l & ~w
        if (~inb).any():
            out[~inb] = self.land_coarse.contains_many(lats[~inb], lons[~inb]) | (lons[~inb] < COARSE_WEST_EDGE)
        return out

    def _raster(self):
        import cv2
        self.nx = int((BOX[2] - BOX[0]) * M_PER_DEG_LON / RASTER_M)
        self.ny = int((BOX[3] - BOX[1]) * M_PER_DEG_LAT / RASTER_M)
        fp = os.path.join(CACHE, f"land_{self.nx}x{self.ny}.npz")
        src = max(os.path.getmtime(os.path.join(GEO_DIR, n)) for n in ("land_local.geojson", "water_overrides_local.geojson"))
        if os.path.exists(fp) and os.path.getmtime(fp) > src:
            z = np.load(fp)
            self.land_mask, self.dist_land, self.dist_water = z["land"], z["dl"], z["dw"]
            return
        img = np.zeros((self.ny, self.nx), np.uint8)
        for ps, val in ((self.land, 1), (self.water_override, 0)):
            for it in ps.items:
                cv2.fillPoly(img, [self._to_px(it["xy"])], val)
            if val == 1:
                for it in ps.items:
                    for h in it["holes"]:
                        cv2.fillPoly(img, [self._to_px(h.vertices)], 0)
        self.land_mask = img.astype(bool)
        self.dist_land = (cv2.distanceTransform((1 - img).astype(np.uint8), cv2.DIST_L2, 5) * RASTER_M).astype(np.float32)
        self.dist_water = (cv2.distanceTransform(img, cv2.DIST_L2, 5) * RASTER_M).astype(np.float32)
        np.savez_compressed(fp, land=self.land_mask, dl=self.dist_land, dw=self.dist_water)

    def _to_px(self, xy):
        xy = np.asarray(xy, float)
        x = (xy[:, 0] - BOX[0]) * M_PER_DEG_LON / RASTER_M
        y = (BOX[3] - xy[:, 1]) * M_PER_DEG_LAT / RASTER_M
        return np.round(np.column_stack([x, y])).astype(np.int32)

    def px(self, lat, lon):
        return (int((BOX[3] - lat) * M_PER_DEG_LAT / RASTER_M), int((lon - BOX[0]) * M_PER_DEG_LON / RASTER_M))

    def px_to_ll(self, r, c):
        return (BOX[3] - (r + 0.5) * RASTER_M / M_PER_DEG_LAT, BOX[0] + (c + 0.5) * RASTER_M / M_PER_DEG_LON)

    def segment_clear(self, a, b, step_m=20.0):
        """True if the straight line between two (lat, lon) points never touches land."""
        n = max(1, int(dist_m(a, b) / step_m))
        lats = [a[0] + (b[0] - a[0]) * k / n for k in range(n + 1)]
        lons = [a[1] + (b[1] - a[1]) * k / n for k in range(n + 1)]
        return not self.is_land_many(lats, lons).any()

    def path_land_hits(self, pts, step_m=20.0):
        """Number of land samples along a polyline (0 means the whole path is on water)."""
        hits = 0
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(dist_m(a, b) / step_m))
            lats = [a[0] + (b[0] - a[0]) * k / n for k in range(n + 1)]
            lons = [a[1] + (b[1] - a[1]) * k / n for k in range(n + 1)]
            hits += int(self.is_land_many(lats, lons).sum())
        return hits

    def land_clearance_m(self, lat, lon):
        """Metres from a water point to the nearest land (0 if on land). Raster, +/- 25 m."""
        if not self.in_box(lat, lon):
            return 0.0 if self.land_coarse.contains(lat, lon) else 5000.0
        r, c = self.px(lat, lon)
        r, c = min(max(r, 0), self.ny - 1), min(max(c, 0), self.nx - 1)
        return float(self.dist_land[r, c])

    def shore_distance_m(self, lat, lon):
        """Metres from a land point to the nearest water (0 if in water). Raster, +/- 25 m."""
        if not self.in_box(lat, lon):
            return 5000.0 if self.land_coarse.contains(lat, lon) else 0.0
        r, c = self.px(lat, lon)
        r, c = min(max(r, 0), self.ny - 1), min(max(c, 0), self.nx - 1)
        return float(self.dist_water[r, c])

    # ------------------------------------------------------------------ channels
    def _channel_edges(self):
        ax, ay, bx, by, rid = [], [], [], [], []
        for it in self.channels.items:
            xy = it["xy"]
            ax += list(xy[:-1, 0]); ay += list(xy[:-1, 1]); bx += list(xy[1:, 0]); by += list(xy[1:, 1])
            rid += [it["props"]["reach_id"]] * (len(xy) - 1)
        self._ce = (np.array(ax) * M_PER_DEG_LON, np.array(ay) * M_PER_DEG_LAT, np.array(bx) * M_PER_DEG_LON, np.array(by) * M_PER_DEG_LAT)
        self._ce_id = rid

    def channel_at(self, lat, lon, buffer_m=0.0, min_depth_ft=0.0):
        """Reach id of the USACE channel polygon containing the point (optionally within buffer_m
        of one whose maintained depth is at least min_depth_ft). None if outside."""
        it = self.channels.which(lat, lon)
        if it is not None and (it["props"].get("depth_ft") or 0) >= min_depth_ft:
            return it["props"]["reach_id"]
        if buffer_m > 0:
            d, _, _ = _seg_dist(lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT, *self._ce)
            order = np.argsort(d)
            for i in order[:12]:
                if d[i] > buffer_m:
                    break
                rid = self._ce_id[i]
                if (self.channel_props[rid].get("depth_ft") or 0) >= min_depth_ft:
                    return rid
        return None

    def channel_distance_m(self, lat, lon, min_depth_ft=0.0):
        """Metres to the nearest channel polygon of at least min_depth_ft (0 if inside one)."""
        if self.channel_at(lat, lon, 0, min_depth_ft):
            return 0.0
        d, _, _ = _seg_dist(lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT, *self._ce)
        ok = np.array([(self.channel_props[r].get("depth_ft") or 0) >= min_depth_ft for r in self._ce_id])
        return float(d[ok].min()) if ok.any() else float("inf")

    # ------------------------------------------------------------------ landmarks
    def find(self, category=None, name_contains=None):
        out = self.landmarks
        if category:
            cats = {category} if isinstance(category, str) else set(category)
            out = [l for l in out if l["category"] in cats]
        if name_contains:
            s = name_contains.lower()
            out = [l for l in out if s in l["name"].lower()]
        return out

    def nearest_landmark(self, lat, lon, category=None):
        best = None
        for l in self.find(category):
            d = dist_m((lat, lon), (l["lat"], l["lon"]))
            if best is None or d < best[0]:
                best = (d, l)
        return best

    def _runways(self):
        """Pair runway-end landmarks into runways: {airport: [(name, (lat,lon), (lat,lon))]}"""
        ends = {}
        for l in self.find("runway_end"):
            key = l["name"].rsplit(" end ", 1)[0]
            ends.setdefault(key, []).append((l["lat"], l["lon"]))
        out = {}
        for key, pts in ends.items():
            if len(pts) == 2:
                apt = key.split(" runway ")[0]
                out.setdefault(apt, []).append((key.split(" runway ")[1], pts[0], pts[1]))
        return out

    def runway_distance_m(self, lat, lon):
        """(metres to nearest runway centreline, airport name)."""
        best = (float("inf"), None)
        px, py = lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT
        for apt, rws in self.runways.items():
            for _, a, b in rws:
                d, _, _ = _seg_dist(px, py, np.array([a[1] * M_PER_DEG_LON]), np.array([a[0] * M_PER_DEG_LAT]),
                                    np.array([b[1] * M_PER_DEG_LON]), np.array([b[0] * M_PER_DEG_LAT]))
                if d[0] < best[0]:
                    best = (float(d[0]), apt)
        return best


# ======================================================================================
# channel navigation graph (deep-draft and barge traffic)
# ======================================================================================
class NavGraph:
    """Graph of USACE channel centerlines. Nodes are centerline vertices (densified to <= 150 m);
    edges follow the lines, join line ends that meet (<= 450 m, both ends inside channel water),
    and bridge the two turning basins that have no published centerline using the basin
    polygons' own centroids. Each edge carries the maintained depth of its reach."""

    STEP_M = 150.0

    def __init__(self, G):
        self.G = G
        self.nodes = []          # (lat, lon)
        self.depth = []          # maintained depth at node, ft
        self.reach = []          # project/line id
        self.adj = {}
        lines = _load("channel_lines_usace.geojson")
        ends = []
        for f in lines:
            lid = f["properties"]["line_id"]
            depth = self._depth_for(lid)
            for coords in _lines(f["geometry"]):
                pts = self._densify([(c[1], c[0]) for c in coords])
                if len(pts) < 2:
                    continue
                first = len(self.nodes)
                for p in pts:
                    self.nodes.append(p); self.depth.append(depth); self.reach.append(lid)
                for i in range(first, len(self.nodes) - 1):
                    self._edge(i, i + 1)
                ends += [first, len(self.nodes) - 1]
        # reaches without a centerline: use the polygon centroid as a through node
        have = {f["properties"]["line_id"] for f in lines}
        for it in G.channels.items:
            rid = it["props"]["reach_id"]
            if not any(rid.startswith(h) for h in have):
                c = it["xy"][:-1].mean(axis=0)
                if G.channels.contains(c[1], c[0]):
                    self.nodes.append((float(c[1]), float(c[0]))); self.depth.append(it["props"].get("depth_ft") or 0)
                    self.reach.append(rid); ends.append(len(self.nodes) - 1)
        self.xy = np.array([(p[1] * M_PER_DEG_LON, p[0] * M_PER_DEG_LAT) for p in self.nodes])
        # join ends to the nearest node of another line when the straight link stays in channel water
        for e in ends:
            d = np.hypot(self.xy[:, 0] - self.xy[e, 0], self.xy[:, 1] - self.xy[e, 1])
            for j in np.argsort(d)[:40]:
                if j == e or d[j] > 900:
                    continue
                if self.reach[j] == self.reach[e] and abs(j - e) < 3:
                    continue
                if self._link_ok(self.nodes[e], self.nodes[j]):
                    self._edge(e, int(j))
                    if self.reach[j] != self.reach[e]:
                        break
        self._crossings()

    def _depth_for(self, lid):
        ds = [p.get("depth_ft") or 0 for rid, p in self.G.channel_props.items() if rid.startswith(lid)]
        return min(ds) if ds else 0

    def _densify(self, pts):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(math.ceil(dist_m(a, b) / self.STEP_M)))
            for k in range(1, n + 1):
                out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
        return out

    def _edge(self, i, j):
        w = dist_m(self.nodes[i], self.nodes[j])
        self.adj.setdefault(i, {})[j] = w
        self.adj.setdefault(j, {})[i] = w

    def _link_ok(self, a, b):
        """A connecting link is allowed if every 40 m sample is inside (or within 60 m of) a channel
        polygon and not on land."""
        n = max(2, int(dist_m(a, b) / 40))
        for k in range(n + 1):
            lat, lon = a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n
            if self.G.is_land(lat, lon) or not self.G.channel_at(lat, lon, 60):
                return False
        return True

    def _crossings(self):
        """Where two different channels' centerlines pass within 120 m (e.g. the Intracoastal
        Waterway crossing the ship channel), link the closest pair of nodes."""
        n = len(self.nodes)
        cell = 300.0
        grid = {}
        for i in range(n):
            grid.setdefault((int(self.xy[i, 0] // cell), int(self.xy[i, 1] // cell)), []).append(i)
        best = {}
        for (cx, cy), idx in grid.items():
            cand = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in grid.get((cx + dx, cy + dy), [])]
            for i in idx:
                for j in cand:
                    if j <= i or self.reach[i][:8] == self.reach[j][:8]:
                        continue
                    d = math.hypot(self.xy[i, 0] - self.xy[j, 0], self.xy[i, 1] - self.xy[j, 1])
                    if d <= 160:
                        key = (self.reach[i], self.reach[j])
                        if key not in best or d < best[key][0]:
                            best[key] = (d, i, j)
        for d, i, j in best.values():
            if not self.G.is_land(*self.nodes[i]) and not self.G.is_land(*self.nodes[j]):
                self._edge(i, j)

    def nearest(self, p, min_depth_ft=0):
        d = np.hypot(self.xy[:, 0] - p[1] * M_PER_DEG_LON, self.xy[:, 1] - p[0] * M_PER_DEG_LAT)
        if min_depth_ft:
            d = np.where(np.array(self.depth) >= min_depth_ft, d, np.inf)
        i = int(np.argmin(d))
        return i, float(d[i])

    def route(self, a, b, draft_ft=0.0):
        """Shortest centerline path between the graph nodes nearest a and b, using only reaches
        maintained to at least draft_ft. Returns a list of (lat, lon) or None."""
        s, _ = self.nearest(a, draft_ft)
        t, _ = self.nearest(b, draft_ft)
        dist, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, w in self.adj.get(u, {}).items():
                if self.depth[v] < draft_ft:
                    continue
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if t not in dist:
            return None
        path = [t]
        while path[-1] != s:
            path.append(prev[path[-1]])
        return [self.nodes[i] for i in reversed(path)]

    def components(self, draft_ft=0.0):
        seen, comps = set(), []
        for i in range(len(self.nodes)):
            if i in seen or self.depth[i] < draft_ft:
                continue
            stack, comp = [i], []
            seen.add(i)
            while stack:
                u = stack.pop(); comp.append(u)
                for v in self.adj.get(u, {}):
                    if v not in seen and self.depth[v] >= draft_ft:
                        seen.add(v); stack.append(v)
            comps.append(comp)
        return sorted(comps, key=len, reverse=True)


# ======================================================================================
# open-water grid (small craft: pilot boats, fishing vessels, patrol boats, skimmers)
# ======================================================================================
class WaterGrid:
    """A* over a 100 m grid of the local window. A cell is passable if it is water and at least
    clearance_m from land, or inside a USACE channel polygon (harbours and cuts are narrower than
    the clearance). Outside the window, use straight offshore legs checked with Geo.is_land."""

    CELL = 4  # raster cells per grid cell (4 x 25 m = 100 m)

    def __init__(self, G):
        self.G = G
        import cv2
        k = self.CELL
        ny, nx = G.ny // k, G.nx // k
        self.shape = (ny, nx)
        self.clear = G.dist_land[:ny * k, :nx * k].reshape(ny, k, nx, k).min(axis=(1, 3))
        ch = np.zeros((G.ny, G.nx), np.uint8)
        for it in G.channels.items:
            cv2.fillPoly(ch, [G._to_px(it["xy"])], 1)
        self.chan = ch[:ny * k, :nx * k].reshape(ny, k, nx, k).max(axis=(1, 3)).astype(bool)
        self.chan &= self.clear > 0
        self._ok = {}

    def cell(self, p):
        r, c = self.G.px(p[0], p[1])
        return (min(max(r // self.CELL, 0), self.shape[0] - 1), min(max(c // self.CELL, 0), self.shape[1] - 1))

    def ll(self, rc):
        return self.G.px_to_ll(rc[0] * self.CELL + self.CELL / 2 - 0.5, rc[1] * self.CELL + self.CELL / 2 - 0.5)

    def passable(self, clearance_m):
        key = int(clearance_m)
        if key not in self._ok:
            import cv2
            ok = (self.clear >= clearance_m) | self.chan
            n, lab = cv2.connectedComponents(ok.astype(np.uint8), connectivity=8)
            sizes = np.bincount(lab.ravel()); sizes[0] = 0
            self._ok[key] = lab == int(np.argmax(sizes))        # the connected open water only
        return self._ok[key]

    def snap(self, p, ok, max_cells=6):
        """Nearest passable cell within max_cells (600 m), else None."""
        r, c = self.cell(p)
        if ok[r, c]:
            return (r, c)
        for rad in range(1, max_cells + 1):
            r0, r1, c0, c1 = max(r - rad, 0), min(r + rad + 1, self.shape[0]), max(c - rad, 0), min(c + rad + 1, self.shape[1])
            sub = np.argwhere(ok[r0:r1, c0:c1])
            if len(sub):
                d = (sub[:, 0] + r0 - r) ** 2 + (sub[:, 1] + c0 - c) ** 2
                for i in np.argsort(d)[:6]:
                    cand = (int(sub[i, 0] + r0), int(sub[i, 1] + c0))
                    if self.G.segment_clear(p, self.ll(cand)):
                        return cand
        return None

    def _harbour_leg(self, p, ok):
        """For a point inside a harbour or cut that the 100 m grid cannot resolve: follow the
        channel centerlines from the nearest channel node out to open water.
        Returns (leg points from p's channel node to open water, open-water cell) or None."""
        nav = self.G.nav
        s, d = nav.nearest(p)
        if d > 700:
            return None
        dist, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            du, u = heapq.heappop(pq)
            cell = self.cell(nav.nodes[u])
            if ok[cell] and self.clear[cell] >= 100:
                path = [u]
                while path[-1] != s:
                    path.append(prev[path[-1]])
                return [nav.nodes[i] for i in reversed(path)], cell
            for v, w in nav.adj.get(u, {}).items():
                if du + w < dist.get(v, 1e18):
                    dist[v] = du + w; prev[v] = u
                    heapq.heappush(pq, (du + w, v))
        return None

    def route(self, a, b, clearance_m=150.0):
        """Water path between two (lat, lon) points inside the local window. Open water is crossed
        on the grid keeping clearance_m from land; harbours and cuts are entered and left along the
        USACE channel centerlines. Returns a list of (lat, lon), or None if there is no water path."""
        ok = self.passable(clearance_m)
        head, tail = [], []
        s = self.snap(a, ok)
        if s is None:
            leg = self._harbour_leg(a, ok)
            if leg is None:
                return None
            head, s = leg
        t = self.snap(b, ok)
        if t is None:
            leg = self._harbour_leg(b, ok)
            if leg is None:
                return None
            tail, t = list(reversed(leg[0])), leg[1]
        mid = self._astar(s, t, ok, clearance_m)
        if mid is None:
            return None
        out = head + mid + tail
        if not self.G.is_land(*a) and self.G.segment_clear(a, out[0]):
            out = [tuple(a)] + out
        if not self.G.is_land(*b) and self.G.segment_clear(out[-1], b):
            out = out + [tuple(b)]
        return out

    def _astar(self, s, t, ok, clearance_m):
        if s == t:
            return [self.ll(s)]
        nbr = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
        g, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            f, u = heapq.heappop(pq)
            if u == t:
                break
            gu = g[u]
            if f - math.hypot(u[0] - t[0], u[1] - t[1]) > gu + 1e-6:
                continue
            for dr, dc, w in nbr:
                v = (u[0] + dr, u[1] + dc)
                if not (0 <= v[0] < self.shape[0] and 0 <= v[1] < self.shape[1]) or not ok[v]:
                    continue
                # prefer the middle of the water: small penalty near shore
                pen = 0.6 if self.clear[v] < clearance_m * 2 and not self.chan[v] else 0.0
                ng = gu + w + pen
                if ng < g.get(v, 1e18):
                    g[v] = ng; prev[v] = u
                    heapq.heappush(pq, (ng + math.hypot(v[0] - t[0], v[1] - t[1]), v))
        if t not in g:
            return None
        cells = [t]
        while cells[-1] != s:
            cells.append(prev[cells[-1]])
        cells.reverse()
        # string-pull: keep a cell only when the straight line to the next kept cell would leave water
        out, i = [cells[0]], 0
        while i < len(cells) - 1:
            j = len(cells) - 1
            while j > i + 1 and not self._los(cells[i], cells[j], ok):
                j -= 1
            out.append(cells[j]); i = j
        return [self.ll(c) for c in out]

    def _los(self, a, b, ok):
        n = int(max(abs(a[0] - b[0]), abs(a[1] - b[1])) * 2) + 1
        for k in range(n + 1):
            r = int(round(a[0] + (b[0] - a[0]) * k / n)); c = int(round(a[1] + (b[1] - a[1]) * k / n))
            if not ok[r, c]:
                return False
        return True


# ======================================================================================
# road network
# ======================================================================================
ROAD_FILES = ["roads_major.geojson", "roads_arterial.geojson", "roads_local_all.geojson"]
# roads_local_all.geojson holds every Census local road in the window (it contains the earlier
# per-neighbourhood files); the per-area files are used only if it is missing.
ROAD_FILES_FALLBACK = ["roads_local_interchange_ramps.geojson", "roads_local_north_beach.geojson", "roads_local_hillcrest.geojson",
                       "roads_local_molina.geojson", "roads_local_flour_bluff.geojson", "roads_local_calallen.geojson",
                       "roads_local_port_aransas.geojson", "roads_local_downtown.geojson"]
SPEED_KMH = {"primary": 100, "secondary": 75, "arterial": 55, "local": 35}
NOT_DRIVABLE = {"walk", "track", "other"}


class RoadNet:
    """Census TIGER centerlines turned into a routable graph. Vertices within 12 m are merged and
    roads are noded where they cross, so routes turn at real intersections. Geometry is never
    altered: every route vertex is a TIGER vertex or a crossing point of two TIGER segments.
    The built network is cached in 99_reference/geo/_cache and rebuilt when a road file changes."""

    SNAP_M = 12.0
    CELL_M = 150.0

    def __init__(self, G):
        import pickle
        self.G = G
        files = [f for f in ROAD_FILES if os.path.exists(os.path.join(GEO_DIR, f))]
        if "roads_local_all.geojson" not in files:
            files += [f for f in ROAD_FILES_FALLBACK if os.path.exists(os.path.join(GEO_DIR, f))]
        stamp = "|".join(f"{f}:{os.path.getsize(os.path.join(GEO_DIR, f))}:{int(os.path.getmtime(os.path.join(GEO_DIR, f)))}" for f in files)
        import hashlib
        fp = os.path.join(CACHE, "roadnet_" + hashlib.md5(stamp.encode()).hexdigest()[:10] + ".pkl")
        if os.path.exists(fp):
            with open(fp, "rb") as fh:
                self.__dict__.update(pickle.load(fh))
            self.G = G
            return
        feats, seen = [], set()
        for fn in files:
            for f in _load(fn):
                p = f["properties"]
                if (p.get("class") or "local") in NOT_DRIVABLE:
                    continue
                key = p.get("source_oid")
                if key is not None and key in seen:
                    continue
                seen.add(key)
                for coords in _lines(f["geometry"]):
                    if len(coords) >= 2:
                        feats.append((p.get("name") or "", p.get("class") or "local", [(c[1], c[0]) for c in coords]))
        self.features = feats
        # segments in metres for nearest/intersection work
        sx0, sy0, sx1, sy1, sf = [], [], [], [], []
        for fi, (_, _, pts) in enumerate(feats):
            for a, b in zip(pts, pts[1:]):
                sx0.append(a[1] * M_PER_DEG_LON); sy0.append(a[0] * M_PER_DEG_LAT)
                sx1.append(b[1] * M_PER_DEG_LON); sy1.append(b[0] * M_PER_DEG_LAT); sf.append(fi)
        self.seg = (np.array(sx0), np.array(sy0), np.array(sx1), np.array(sy1))
        self.seg_feat = np.array(sf)
        self.seg_cls = np.array([feats[f][1] for f in sf])
        self._index()
        self._build_graph()
        state = {k: v for k, v in self.__dict__.items() if k != "G"}
        with open(fp, "wb") as fh:
            pickle.dump(state, fh, protocol=4)

    def _index(self):
        """Bucket segments into CELL_M cells (a segment is listed in every cell its bounding box touches)."""
        ax, ay, bx, by = self.seg
        c = self.CELL_M
        grid = {}
        x0 = np.floor(np.minimum(ax, bx) / c).astype(int); x1 = np.floor(np.maximum(ax, bx) / c).astype(int)
        y0 = np.floor(np.minimum(ay, by) / c).astype(int); y1 = np.floor(np.maximum(ay, by) / c).astype(int)
        for i in range(len(ax)):
            for gx in range(x0[i], x1[i] + 1):
                for gy in range(y0[i], y1[i] + 1):
                    grid.setdefault((gx, gy), []).append(i)
        self.grid = {k: np.array(v, dtype=np.int32) for k, v in grid.items()}

    def _cands(self, gx, gy, rad):
        out = [self.grid[k] for k in ((gx + dx, gy + dy) for dx in range(-rad, rad + 1) for dy in range(-rad, rad + 1)) if k in self.grid]
        return np.unique(np.concatenate(out)) if out else None

    # ---------- nearest
    def nearest(self, lat, lon, classes=None):
        """(distance_m, lat, lon, road_name, class) of the closest point on any road
        (optionally only roads of the given classes)."""
        px, py = lon * M_PER_DEG_LON, lat * M_PER_DEG_LAT
        gx, gy = int(px // self.CELL_M), int(py // self.CELL_M)
        ax, ay, bx, by = self.seg
        for rad in (1, 3, 8, 25, None):
            idx = self._cands(gx, gy, rad) if rad is not None else np.arange(len(ax))
            if idx is None:
                continue
            if classes is not None:
                idx = idx[np.isin(self.seg_cls[idx], list(classes))]
                if not len(idx):
                    continue
            d, cx, cy = _seg_dist(px, py, ax[idx], ay[idx], bx[idx], by[idx])
            k = int(np.argmin(d))
            if rad is None or d[k] <= rad * self.CELL_M:
                i = int(idx[k])
                name, cls, _ = self.features[self.seg_feat[i]]
                return float(d[k]), float(cy[k] / M_PER_DEG_LAT), float(cx[k] / M_PER_DEG_LON), name, cls
        return float("inf"), lat, lon, "", ""

    def distance_many(self, lats, lons):
        """Metres from each point to the nearest road. Exact up to 1,200 m; farther points report
        the distance found within that search radius or 1e9 if there is no road within it."""
        lats, lons = np.asarray(lats, float), np.asarray(lons, float)
        out = np.full(len(lats), 1e9)
        px, py = lons * M_PER_DEG_LON, lats * M_PER_DEG_LAT
        gx, gy = np.floor(px / self.CELL_M).astype(int), np.floor(py / self.CELL_M).astype(int)
        ax, ay, bx, by = self.seg
        order = np.lexsort((gy, gx))
        todo = order
        for rad in (1, 3, 8):
            nxt = []
            if not len(todo):
                break
            keys = np.stack([gx[todo], gy[todo]], axis=1)
            brk = np.where(np.any(keys[1:] != keys[:-1], axis=1))[0] + 1
            for grp in np.split(np.arange(len(todo)), brk):
                ids = todo[grp]
                idx = self._cands(int(gx[ids[0]]), int(gy[ids[0]]), rad)
                if idx is None:
                    nxt.append(ids)
                    continue
                qx, qy = px[ids][:, None], py[ids][:, None]
                dx, dy = bx[idx] - ax[idx], by[idx] - ay[idx]
                L2 = dx * dx + dy * dy
                t = np.clip(((qx - ax[idx]) * dx + (qy - ay[idx]) * dy) / np.where(L2 > 0, L2, 1), 0, 1)
                d = np.hypot(qx - (ax[idx] + t * dx), qy - (ay[idx] + t * dy)).min(axis=1)
                good = d <= rad * self.CELL_M
                out[ids] = np.minimum(out[ids], d)
                if (~good).any():
                    nxt.append(ids[~good])
            todo = np.concatenate(nxt) if nxt else np.array([], dtype=int)
            if len(todo):
                todo = todo[np.lexsort((gy[todo], gx[todo]))]
        return out

    # ---------- graph
    def _build_graph(self):
        ax, ay, bx, by = self.seg
        nseg = len(ax)
        # crossings: split parameters per segment
        cuts = {i: [] for i in range(nseg)}
        cell = 250.0
        grid = {}
        for i in range(nseg):
            x0, x1 = sorted((ax[i], bx[i])); y0, y1 = sorted((ay[i], by[i]))
            for gx in range(int(x0 // cell), int(x1 // cell) + 1):
                for gy in range(int(y0 // cell), int(y1 // cell) + 1):
                    grid.setdefault((gx, gy), []).append(i)
        done = set()
        for idx in grid.values():
            for a in range(len(idx)):
                i = idx[a]
                for b in range(a + 1, len(idx)):
                    j = idx[b]
                    if (i, j) in done or self.seg_feat[i] == self.seg_feat[j]:
                        continue
                    done.add((i, j))
                    r = (bx[i] - ax[i], by[i] - ay[i]); s = (bx[j] - ax[j], by[j] - ay[j])
                    den = r[0] * s[1] - r[1] * s[0]
                    if abs(den) < 1e-9:
                        continue
                    qp = (ax[j] - ax[i], ay[j] - ay[i])
                    t = (qp[0] * s[1] - qp[1] * s[0]) / den
                    u = (qp[0] * r[1] - qp[1] * r[0]) / den
                    if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
                        cuts[i].append(min(max(t, 0), 1)); cuts[j].append(min(max(u, 0), 1))
        # T-junctions: a road that ends on (or has a vertex on) another road's segment without crossing it.
        # Simplified whole-road features lose the shared vertex, so cut the other road at the projection.
        vx = np.concatenate([ax, bx]); vy = np.concatenate([ay, by]); vf = np.concatenate([self.seg_feat, self.seg_feat])
        gxs, gys = np.floor(vx / self.CELL_M).astype(int), np.floor(vy / self.CELL_M).astype(int)
        order = np.lexsort((gys, gxs))
        keys = np.stack([gxs[order], gys[order]], axis=1)
        brk = np.where(np.any(keys[1:] != keys[:-1], axis=1))[0] + 1
        for grp in np.split(order, brk):
            idx = self._cands(int(gxs[grp[0]]), int(gys[grp[0]]), 1)
            if idx is None:
                continue
            qx, qy = vx[grp][:, None], vy[grp][:, None]
            dx, dy = bx[idx] - ax[idx], by[idx] - ay[idx]
            L2 = dx * dx + dy * dy
            t = ((qx - ax[idx]) * dx + (qy - ay[idx]) * dy) / np.where(L2 > 0, L2, 1)
            tc = np.clip(t, 0, 1)
            d = np.hypot(qx - (ax[idx] + tc * dx), qy - (ay[idx] + tc * dy))
            hit = (d <= 8.0) & (t > 1e-3) & (t < 1 - 1e-3) & (self.seg_feat[idx][None, :] != vf[grp][:, None])
            for r, c in zip(*np.where(hit)):
                cuts[int(idx[c])].append(float(t[r, c]))
        # node merging by snap grid
        self.nodes, self.adj, self.edge_name = [], {}, {}
        key_of = {}

        def node(x, y):
            k = (int(round(x / self.SNAP_M)), int(round(y / self.SNAP_M)))
            for dx in (0, -1, 1):
                for dy in (0, -1, 1):
                    kk = (k[0] + dx, k[1] + dy)
                    if kk in key_of:
                        n = key_of[kk]
                        if math.hypot(self._nx[n] - x, self._ny[n] - y) <= self.SNAP_M:
                            return n
            key_of[k] = len(self.nodes)
            self.nodes.append((y / M_PER_DEG_LAT, x / M_PER_DEG_LON)); self._nx.append(x); self._ny.append(y)
            return key_of[k]

        self._nx, self._ny = [], []
        for i in range(nseg):
            name, cls, _ = self.features[self.seg_feat[i]]
            ts = sorted(set([0.0, 1.0] + [round(t, 6) for t in cuts[i]]))
            prev = None
            for t in ts:
                n = node(ax[i] + (bx[i] - ax[i]) * t, ay[i] + (by[i] - ay[i]) * t)
                if prev is not None and prev != n:
                    w = math.hypot(self._nx[prev] - self._nx[n], self._ny[prev] - self._ny[n])
                    cost = w / (SPEED_KMH.get(cls, 35) / 3.6)
                    if n not in self.adj.setdefault(prev, {}) or cost < self.adj[prev][n][0]:
                        self.adj.setdefault(prev, {})[n] = (cost, w, name, cls)
                        self.adj.setdefault(n, {})[prev] = (cost, w, name, cls)
                prev = n
        self.nxy = np.column_stack([self._nx, self._ny])
        # largest connected component
        comp, cid = {}, 0
        for i in range(len(self.nodes)):
            if i in comp:
                continue
            stack = [i]; comp[i] = cid
            while stack:
                u = stack.pop()
                for v in self.adj.get(u, {}):
                    if v not in comp:
                        comp[v] = cid; stack.append(v)
            cid += 1
        sizes = {}
        for c in comp.values():
            sizes[c] = sizes.get(c, 0) + 1
        self.main_comp = max(sizes, key=sizes.get)
        self.comp = comp
        self.in_main = np.array([comp[i] == self.main_comp for i in range(len(self.nodes))])

    def nearest_node(self, lat, lon, main_only=True):
        d = np.hypot(self.nxy[:, 0] - lon * M_PER_DEG_LON, self.nxy[:, 1] - lat * M_PER_DEG_LAT)
        if main_only:
            d = np.where(self.in_main, d, np.inf)
        i = int(np.argmin(d))
        return i, float(d[i])

    def route(self, a, b):
        """Fastest street route between the network nodes nearest a and b.
        Returns {"points": [(lat, lon)...], "metres": float, "seconds": float, "roads": [names]} or None."""
        s, _ = self.nearest_node(*a)
        t, _ = self.nearest_node(*b)
        tx, ty = self.nxy[t]
        vmax = 100 / 3.6
        dist, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            f, u = heapq.heappop(pq)
            if u == t:
                break
            du = dist[u]
            for v, (cost, w, name, cls) in self.adj.get(u, {}).items():
                nd = du + cost
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u
                    heapq.heappush(pq, (nd + math.hypot(self.nxy[v, 0] - tx, self.nxy[v, 1] - ty) / vmax, v))
        if t not in dist:
            return None
        path = [t]
        while path[-1] != s:
            path.append(prev[path[-1]])
        path.reverse()
        metres, roads, legs = 0.0, [], []
        for u, v in zip(path, path[1:]):
            cost, w, name, cls = self.adj[u][v]
            metres += w
            legs.append((cost, w, name, cls))
            if name and (not roads or roads[-1] != name):
                roads.append(name)
        return {"points": [self.nodes[i] for i in path], "metres": metres, "seconds": dist[t], "roads": roads, "legs": legs}

    def random_point(self, rng, box=None, classes=("local", "arterial", "secondary"), setback_m=0.0):
        """A point on a road segment (optionally inside box = (lon0, lat0, lon1, lat1) and offset
        sideways by setback_m, as a building frontage would be). Returns (lat, lon, road name)."""
        ax, ay, bx, by = self.seg
        cls = np.array([self.features[f][1] for f in self.seg_feat])
        m = np.isin(cls, classes)
        if box:
            mx, my = (ax + bx) / 2 / M_PER_DEG_LON, (ay + by) / 2 / M_PER_DEG_LAT
            m &= (mx >= box[0]) & (mx <= box[2]) & (my >= box[1]) & (my <= box[3])
        idx = np.where(m)[0]
        if not len(idx):
            return None
        L = np.hypot(bx[idx] - ax[idx], by[idx] - ay[idx])
        i = idx[rng.choice(len(idx), p=L / L.sum())]
        t = rng.random()
        x, y = ax[i] + (bx[i] - ax[i]) * t, ay[i] + (by[i] - ay[i]) * t
        if setback_m:
            dx, dy = bx[i] - ax[i], by[i] - ay[i]
            n = math.hypot(dx, dy) or 1.0
            side = 1 if rng.random() < 0.5 else -1
            x += -dy / n * setback_m * side; y += dx / n * setback_m * side
        return (float(y / M_PER_DEG_LAT), float(x / M_PER_DEG_LON), self.features[self.seg_feat[i]][0])


def path_length_m(pts):
    return sum(dist_m(a, b) for a, b in zip(pts, pts[1:]))


def walk(pts, metres):
    """Point (lat, lon) and heading at a distance along a polyline."""
    if metres <= 0:
        return pts[0], bearing(pts[0], pts[1]) if len(pts) > 1 else 0.0
    for a, b in zip(pts, pts[1:]):
        d = dist_m(a, b)
        if metres <= d and d > 0:
            t = metres / d
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), bearing(a, b)
        metres -= d
    return pts[-1], bearing(pts[-2], pts[-1]) if len(pts) > 1 else 0.0


if __name__ == "__main__":
    import time
    t0 = time.time()
    G = Geo()
    print(f"loaded in {time.time() - t0:.1f}s: {len(G.land.items)} land polygons, {len(G.channels.items)} channel reaches, "
          f"{len(G.nav.nodes)} channel nodes, {len(G.roads.nodes)} road nodes, {len(G.landmarks)} landmarks")
    tests = [("Corpus Christi Bay centre", 27.77, -97.25, False), ("Gulf off Port Aransas", 27.80, -96.93, False),
             ("CC International Airport", 27.770, -97.501, True), ("Downtown Corpus Christi", 27.795, -97.398, True),
             ("Mustang Island", 27.70, -97.16, True), ("Port Aransas town", 27.834, -97.066, True),
             ("Aransas Pass between jetties", 27.836, -97.046, False), ("Nueces Bay", 27.85, -97.42, False),
             ("Rockport", 28.02, -97.055, True)]
    for name, lat, lon, want in tests:
        got = G.is_land(lat, lon)
        print(f"  {'ok ' if got == want else 'BAD'} {name}: {'land' if got else 'water'}")
    comps = G.nav.components()
    print("channel graph components:", [len(c) for c in comps[:6]])
    deep = G.nav.components(40)
    print("deep-draft (>=40 ft) components:", [len(c) for c in deep[:6]])
    sea = (27.7927, -96.9636); viola = (27.8440, -97.5215); lq = (27.878, -97.268)
    for nm, a, b, dr in (("sea buoy -> Viola basin", sea, viola, 40), ("sea buoy -> La Quinta", sea, lq, 40)):
        r = G.nav.route(a, b, dr)
        if r:
            bad = sum(G.is_land(*p) for p in r)
            print(f"  {nm}: {path_length_m(r) / 1852:.1f} nm, {len(r)} pts, {bad} on land, "
                  f"{sum(1 for p in r if not G.channel_at(p[0], p[1], 30))} outside channel")
        else:
            print(f"  {nm}: NO ROUTE")
    print("road net: main component", int(G.roads.in_main.sum()), "of", len(G.roads.nodes), "nodes")
    r = G.roads.route((27.7722, -97.5024), (27.8357, -97.0684))
    print("  airport -> Port Aransas EMS:", None if not r else f"{r['metres'] / 1000:.1f} km, {r['seconds'] / 60:.0f} min via {r['roads'][:8]}")
    w = G.water.route((27.8389, -97.0600), (28.0253, -97.0489))
    print("  water: Port Aransas CG station -> Rockport harbor:", None if not w else f"{path_length_m(w) / 1852:.1f} nm, {len(w)} pts")
