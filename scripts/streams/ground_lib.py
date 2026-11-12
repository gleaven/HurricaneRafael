"""Shared machinery for the ground emergency stream family (911 CAD, AVL, SAR, shelters,
damage assessment): the road network as shortest-path trees, bridge closures, and pools of
real street locations per area. Everything positional comes from scripts/geo.py.
"""
import heapq
import math
import pickle

import numpy as np

from common import *  # noqa: F401,F403
import geo

M_LAT = geo.M_PER_DEG_LAT
M_LON = geo.M_PER_DEG_LON

# Harbor Bridge and Nueces Bay Causeway: closed to traffic as the storm arrives, reopened
# after inspection on D+3 (canon closures.bridges; times of day are generator choices).
BRIDGE_CLOSE = local_ts(-1, "20:00")
BRIDGE_OPEN = local_ts(3, "12:00")
# No ground response in the worst of the storm (canon: ground teams cannot operate; standby).
HOLD_START = local_ts(-1, "22:00")
HOLD_END = local_ts(0, "06:30")


# Real street names that collide with names this corpus does not print: real companies and
# hospitals (check_streams BANNED_EVERYWHERE) and the withheld scenario terms.
import re as _re
STREET_NAMES_NOT_USED = _re.compile(
    "|".join(f"(?:{p})" for p in [r"GridWater", r"Flint Hills", r"Valero", r"Citgo", r"NuStar", r"Buckeye", r"Caller[- ]?Times", r"\bKIII\b", r"\bKRIS\b",
                                  r"CHRISTUS", r"Spohn", r"Driscoll", r"State Farm", r"Auriga Meridian", r"Pier 9\b"]
             + [t["pattern"] for t in load_json("02_public_record/restricted_terms.json")["terms"]
                if not t["pattern"].startswith(("\\b", "BANK-SYN", "readiness", "aid-help", "@"))]), _re.I)


class Ground:
    _CACHED = ("ax", "ay", "bx", "by", "seg_len", "seg_cls", "seg_name", "seg_na", "seg_nb", "seg_main", "seg_off", "n_nodes", "adj",
               "bridge_points", "bridge_spans", "blocked")

    def __init__(self):
        self.G = geo_handle()
        R = self.R = self.G.roads
        self._trees = {}
        # the arrays derived from the road network take about 20 s to build: keep them beside the geo cache
        self._cache_fp = os.path.join(ROOT, "99_reference", "geo", "_cache", f"ground_lib_{len(R.seg[0])}_{len(R.nodes)}.pkl")
        if os.path.exists(self._cache_fp):
            try:
                with open(self._cache_fp, "rb") as fh:
                    d = pickle.load(fh)
                if all(k in d for k in self._CACHED):
                    self.__dict__.update(d)
                    return
            except Exception:
                pass
        self._build()
        try:
            with open(self._cache_fp, "wb") as fh:
                pickle.dump({k: getattr(self, k) for k in self._CACHED}, fh, protocol=4)
        except Exception:
            pass

    def __getstate__(self):                 # a pickled Ground is rebuilt from the cache; trees are saved separately
        return {}

    def __setstate__(self, d):
        self.__init__()

    def save_trees(self, fp):
        with open(fp, "wb") as fh:
            pickle.dump(self._trees, fh, protocol=4)

    def load_trees(self, fp):
        if os.path.exists(fp):
            with open(fp, "rb") as fh:
                self._trees.update(pickle.load(fh))

    def _build(self):
        R = self.R
        ax, ay, bx, by = R.seg
        self.ax, self.ay, self.bx, self.by = ax, ay, bx, by
        self.seg_len = np.hypot(bx - ax, by - ay)
        self.seg_cls = np.array([R.features[f][1] for f in R.seg_feat])
        self.seg_name = np.array([R.features[f][0] for f in R.seg_feat], dtype=object)
        self.seg_na = self._nearest_nodes(ax, ay)
        self.seg_nb = self._nearest_nodes(bx, by)
        self.seg_main = R.in_main[self.seg_na] & R.in_main[self.seg_nb]
        # distance of each segment's start along its feature (for block numbers)
        off = np.zeros(len(ax))
        run, prev = 0.0, -1
        for i, f in enumerate(R.seg_feat):
            if f != prev:
                run, prev = 0.0, f
            off[i] = run
            run += self.seg_len[i]
        self.seg_off = off
        self.n_nodes = len(R.nodes)
        self.adj = [[] for _ in range(self.n_nodes)]
        for u, nb in R.adj.items():
            for v, (cost, w, name, cls) in nb.items():
                self.adj[u].append((v, cost, w))
        self.blocked = self._bridge_edges()

    # ------------------------------------------------------------ nodes
    def _nearest_nodes(self, xs, ys):
        nxy = self.R.nxy
        out = np.empty(len(xs), dtype=np.int64)
        for s in range(0, len(xs), 500):
            d = (xs[s:s + 500, None] - nxy[None, :, 0]) ** 2 + (ys[s:s + 500, None] - nxy[None, :, 1]) ** 2
            out[s:s + 500] = d.argmin(axis=1)
        return out

    def node_near(self, lat, lon):
        return self.R.nearest_node(lat, lon)[0]

    def _bridge_edges(self):
        """Edges of the Harbor Bridge and the Nueces Bay Causeway: graph edges that pass over
        water near the registry positions of the two crossings."""
        assets = {a["asset_id"]: a for a in reg("infrastructure_assets")["assets"]}
        spans = [((assets["FAC-INF-01A"]["latitude"], assets["FAC-INF-01A"]["longitude"]), 900.0),
                 ((assets["FAC-INF-01B"]["latitude"], assets["FAC-INF-01B"]["longitude"]), 2800.0)]
        self.bridge_points = [s[0] for s in spans]
        self.bridge_spans = spans
        blocked = set()
        nodes = self.R.nodes
        for u in range(self.n_nodes):
            for v, cost, w in self.adj[u]:
                if v <= u:
                    continue
                a, b = nodes[u], nodes[v]
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                # the port road along the north shore of the Inner Harbor (TIGER: Navigation Blvd
                # north of the channel) is the only other way onto North Beach; it is closed with
                # the port and under surge for the same window
                if self.R.adj[u][v][2] == "Navigation Blvd" and mid[0] >= 27.812:
                    blocked.add((u, v)); blocked.add((v, u))
                    continue
                if not any(geo.dist_m(mid, c) <= rad for c, rad in spans):
                    continue
                k = max(2, int(w / 25))
                lats = [a[0] + (b[0] - a[0]) * i / k for i in range(k + 1)]
                lons = [a[1] + (b[1] - a[1]) * i / k for i in range(k + 1)]
                if (~self.G.is_land_many(lats, lons)).any():
                    blocked.add((u, v)); blocked.add((v, u))
        return blocked

    def over_bridge(self, lat, lon):
        """True if a point is on one of the two closed crossings (over water inside a span)."""
        return any(geo.dist_m((lat, lon), c) <= rad for c, rad in self.bridge_spans) and not self.G.is_land(lat, lon)

    def anchor(self, lat, lon):
        """Where a site meets the street network: the closest point on a main-network road, with
        the end node of that road segment. Vehicles park and start here."""
        px, py = lon * M_LON, lat * M_LAT
        dx, dy = self.bx - self.ax, self.by - self.ay
        L2 = dx * dx + dy * dy
        t = np.clip(((px - self.ax) * dx + (py - self.ay) * dy) / np.where(L2 > 0, L2, 1), 0, 1)
        cx, cy = self.ax + t * dx, self.ay + t * dy
        d = np.hypot(px - cx, py - cy)
        d = np.where(self.seg_main, d, np.inf)
        s = int(np.argmin(d))
        end = int(self.seg_na[s] if t[s] < 0.5 else self.seg_nb[s])
        return {"node": end, "rlat": float(cy[s] / M_LAT), "rlon": float(cx[s] / M_LON), "seg": s,
                "street": str(self.seg_name[s]), "off_m": float(d[s]), "lat": lat, "lon": lon}

    # ------------------------------------------------------------ shortest-path trees
    def tree(self, src, closed=False):
        """(seconds[], metres[], prev[]) from node src over the whole network; with closed=True
        the two bay crossings are impassable."""
        key = (int(src), bool(closed))
        if key in self._trees:
            return self._trees[key]
        n = self.n_nodes
        dist = np.full(n, np.inf); met = np.full(n, np.inf); prev = np.full(n, -1, dtype=np.int64)
        dist[src] = 0.0; met[src] = 0.0
        pq = [(0.0, int(src))]
        blocked = self.blocked if closed else ()
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist[u]:
                continue
            for v, cost, w in self.adj[u]:
                if blocked and (u, v) in blocked:
                    continue
                nd = d + cost
                if nd < dist[v]:
                    dist[v] = nd; met[v] = met[u] + w; prev[v] = u
                    heapq.heappush(pq, (nd, v))
        self._trees[key] = (dist, met, prev)
        return self._trees[key]

    def path(self, src, dst, closed=False):
        """Node list src..dst along the fastest route, or None."""
        if (int(src), bool(closed)) not in self._trees and (int(dst), bool(closed)) in self._trees:
            back = self.path(dst, src, closed)          # the network is undirected: reuse the hub's tree
            return None if back is None else back[::-1]
        dist, met, prev = self.tree(src, closed)
        if not np.isfinite(dist[dst]):
            return None
        out = [int(dst)]
        while out[-1] != src:
            out.append(int(prev[out[-1]]))
        out.reverse()
        return out

    def route(self, a, b, closed=False):
        """Route between two places (dicts with node, rlat, rlon as returned by anchor() or
        sample_locations()). Returns (lats, lons, nominal seconds) or None if unreachable. The
        first and last hops run along each place's own street segment to its frontage point."""
        np_ = self.path(a["node"], b["node"], closed)
        if np_ is None:
            return None
        nodes = self.R.nodes
        lats = [a["rlat"]]; lons = [a["rlon"]]; secs = [0.0]
        def push(lat, lon, speed_kmh=None, cost=None):
            d = geo.dist_m((lats[-1], lons[-1]), (lat, lon))
            if d < 0.5:
                return
            secs.append(secs[-1] + (cost if cost is not None else d / (speed_kmh / 3.6)))
            lats.append(lat); lons.append(lon)
        push(nodes[np_[0]][0], nodes[np_[0]][1], 35)
        for u, v in zip(np_, np_[1:]):
            push(nodes[v][0], nodes[v][1], cost=self.R.adj[u][v][0])
        push(b["rlat"], b["rlon"], 35)
        if len(lats) == 1:
            lats.append(lats[0]); lons.append(lons[0]); secs.append(1.0)
        return np.array(lats), np.array(lons), np.array(secs)

    def travel_seconds(self, a, b, closed=False):
        """Nominal drive time between two places without building the geometry."""
        if (int(a["node"]), bool(closed)) not in self._trees and (int(b["node"]), bool(closed)) in self._trees:
            a, b = b, a
        dist, _, _ = self.tree(a["node"], closed)
        d = dist[b["node"]]
        if not np.isfinite(d):
            return None
        ha = geo.dist_m((a["rlat"], a["rlon"]), self.R.nodes[a["node"]]) / (35 / 3.6)
        hb = geo.dist_m((b["rlat"], b["rlon"]), self.R.nodes[b["node"]]) / (35 / 3.6)
        return float(d + ha + hb)

    # ------------------------------------------------------------ street locations
    def sample_locations(self, box, n, rg, local_boost=3.0, classes=("local", "arterial", "secondary"),
                         setback=(12.0, 28.0), need_name=True):
        """n address-like points inside box = (lon0, lat0, lon1, lat1): on land, set back from a
        named street on the main network. Returns a list of dicts (lat, lon, road point, segment,
        nearest end node, street name, block number). The box is widened if it holds too little road.
        A few real streets carry names this corpus never prints (they match a real company or
        hospital, or a withheld scenario term); a point drawn on one is replaced by a point on
        another street of the same box."""
        out = self._sample(box, n, rg, local_boost, classes, setback, need_name, False)
        bad = [i for i, p in enumerate(out) if STREET_NAMES_NOT_USED.search(p["street"])]
        if bad:
            rg2 = np.random.default_rng([len(out), len(bad), int(abs(box[0]) * 1e4) % 100000, int(abs(box[1]) * 1e4) % 100000])
            sub = self._sample(box, len(bad), rg2, local_boost, classes, setback, need_name, True)
            for i, q in zip(bad, sub):
                out[i] = q
            out = [p for p in out if not STREET_NAMES_NOT_USED.search(p["street"])]
        return out

    def _sample(self, box, n, rg, local_boost, classes, setback, need_name, clean):
        mx = (self.ax + self.bx) / 2 / M_LON; my = (self.ay + self.by) / 2 / M_LAT
        base = np.isin(self.seg_cls, classes) & self.seg_main & (self.seg_len > 8)
        if need_name:
            base &= np.array([bool(s) for s in self.seg_name])
        if clean:
            if not hasattr(self, "_seg_clean"):
                self._seg_clean = np.array([not STREET_NAMES_NOT_USED.search(str(s) if s else "") for s in self.seg_name])
            base &= self._seg_clean
        grow = 0.0
        while True:
            m = base & (mx >= box[0] - grow) & (mx <= box[2] + grow) & (my >= box[1] - grow) & (my <= box[3] + grow)
            if self.seg_len[m].sum() > 1500 or grow > 0.08:
                break
            grow += 0.005
        idx = np.where(m)[0]
        if not len(idx):
            return []
        w = self.seg_len[idx] * np.where(self.seg_cls[idx] == "local", local_boost, 1.0)
        out, tries = [], 0
        while len(out) < n and tries < 12:
            tries += 1
            k = (n - len(out)) * 2 + 8
            pick = idx[rg.choice(len(idx), size=k, p=w / w.sum())]
            t = rg.random(k)
            x = self.ax[pick] + (self.bx[pick] - self.ax[pick]) * t
            y = self.ay[pick] + (self.by[pick] - self.ay[pick]) * t
            dx = self.bx[pick] - self.ax[pick]; dy = self.by[pick] - self.ay[pick]
            L = np.hypot(dx, dy)
            side = np.where(rg.random(k) < 0.5, 1.0, -1.0)
            sb = rg.uniform(setback[0], setback[1], k)
            px = x - dy / L * sb * side; py = y + dx / L * sb * side
            lat = py / M_LAT; lon = px / M_LON
            land = self.G.is_land_many(lat, lon)
            for j in np.where(land)[0]:
                s = int(pick[j])
                end = int(self.seg_na[s] if t[j] < 0.5 else self.seg_nb[s])
                block = int((self.seg_off[s] + t[j] * self.seg_len[s]) // 110 + 1) * 100
                num = block + int(rg.integers(0, 49)) * 2 + (1 if side[j] > 0 else 0)
                out.append({"lat": round(float(lat[j]), 6), "lon": round(float(lon[j]), 6),
                            "rlat": float(y[j] / M_LAT), "rlon": float(x[j] / M_LON), "seg": s, "node": end,
                            "street": str(self.seg_name[s]), "number": num, "cls": str(self.seg_cls[s])})
                if len(out) >= n:
                    break
        return out

    def locations_near(self, center, radius_m, n, rg, min_m=0.0, classes=("local", "arterial", "secondary", "primary")):
        """Address-like points within radius_m of a (lat, lon), at least min_m away."""
        dlat = radius_m / M_LAT; dlon = radius_m / M_LON
        box = (center[1] - dlon, center[0] - dlat, center[1] + dlon, center[0] + dlat)
        out = []
        for _ in range(20):
            for p in self.sample_locations(box, n * 4, rg, local_boost=1.0, classes=classes):
                d = geo.dist_m(center, (p["lat"], p["lon"]))
                if min_m <= d <= radius_m:
                    out.append(p)
                    if len(out) >= n:
                        return out
        return out


def address(p):
    return f"{p['number']} {p['street']}".upper()


def sample_route(lats, lons, secs, t_nominal):
    """Position and heading at a nominal elapsed time along a polyline from Ground.polyline."""
    if t_nominal <= 0:
        i = 0
        hd = geo.bearing((lats[0], lons[0]), (lats[1], lons[1])) if len(lats) > 1 else 0.0
        return float(lats[0]), float(lons[0]), hd
    if t_nominal >= secs[-1]:
        hd = geo.bearing((lats[-2], lons[-2]), (lats[-1], lons[-1])) if len(lats) > 1 else 0.0
        return float(lats[-1]), float(lons[-1]), hd
    i = int(np.searchsorted(secs, t_nominal, side="right")) - 1
    f = (t_nominal - secs[i]) / max(1e-9, secs[i + 1] - secs[i])
    la = lats[i] + (lats[i + 1] - lats[i]) * f; lo = lons[i] + (lons[i + 1] - lons[i]) * f
    return float(la), float(lo), geo.bearing((lats[i], lons[i]), (lats[i + 1], lons[i + 1]))


# ======================================================================================
# shelters: one occupancy model shared by the rescue log (where survivors are taken) and the
# shelter files (census, intake log), so that every delivery appears as an arrival
# ======================================================================================
# facility -> (opening day, opening time local, closing day, share of capacity held by evacuees who came by bus or on their own)
SHELTER_PLAN = {"FAC-SHLT-007": (-2, "08:00", 62, 0.80), "FAC-SHLT-006": (-2, "08:00", 12, 0.70), "FAC-SHLT-026": (-2, "08:00", 19, 0.70),
                "FAC-SHLT-027": (-2, "08:00", 19, 0.60), "FAC-SHLT-028": (-1, "07:00", 26, 0.84), "FAC-SHLT-029": (1, "12:00", 21, 0.40)}


def shelter_open_ts(fid):
    od, ot, cd, _ = SHELTER_PLAN[fid]
    return local_ts(od, ot)


def shelter_close_day(fid):
    return SHELTER_PLAN[fid][2]


def shelter_base(fid, cap, d):
    """Evacuees (not rescued persons) in the shelter at the end of local day d."""
    od, ot, cd, peak = SHELTER_PLAN[fid]
    if d < od or d >= cd:
        return 0
    if fid == "FAC-SHLT-029":
        frac = 0.9 * math.exp(-(d - 2) / 7.0) if d >= 2 else 0.6
    elif d < 0:
        frac = {-2: 0.28, -1: 0.72}[d] if od == -2 else 0.45
    elif d <= 1:
        frac = 0.93 if d == 0 else 1.0
    elif d <= 5:
        frac = 1.0 - 0.03 * (d - 1)
    else:
        frac = 0.88 * math.exp(-(d - 5) / (16.0 if fid == "FAC-SHLT-007" else 6.5))
    if fid == "FAC-SHLT-007" and d > 30:
        frac = max(frac, 0.035 + 0.02 * (62 - d) / 32)
    return int(round(cap * peak * frac * rng("ground", "shelter-base", fid, d).uniform(0.975, 1.025)))


def stay_days(key, fid):
    """Nights a rescued household stays at a shelter (drawn once per household)."""
    rg = rng("ground", "stay", key)
    n = 1 + int(rg.geometric(0.16 if fid == "FAC-SHLT-007" else 0.24))
    return min(n, max(1, shelter_close_day(fid) - 1))
