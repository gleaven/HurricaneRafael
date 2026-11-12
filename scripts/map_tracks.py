"""Track handling for the map build: split logged fixes into continuous parts, simplify them
without moving the asset off its real path, and verify the simplified segments against geography.

Simplification is Douglas-Peucker with two error terms, so the simplified track is right both
in space and in time:
  cross-track  how far a dropped fix lies from the straight segment that replaces it
  time-synced  how far a dropped fix lies from where linear interpolation BY TIME puts the asset
A fix is dropped only if both are inside tolerance. Stationary runs collapse to two vertices
(arrive, leave) at the same place.
"""
import math

import numpy as np

import geo

MLAT = geo.M_PER_DEG_LAT


def to_xy(lat, lon):
    lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    return lon * 111_320.0 * math.cos(math.radians(27.8)), lat * MLAT


def split_parts(t, x, y, max_gap_s, still_m=25.0):
    """Indices [(i0, i1)] of continuous runs. A gap longer than max_gap_s ends a part unless the
    asset has not moved (moored ships and parked units report rarely)."""
    n = len(t)
    if n == 0:
        return []
    dt = np.diff(t)
    moved = np.hypot(np.diff(x), np.diff(y)) > still_m
    cut = np.where((dt > max_gap_s) & moved)[0]
    out, a = [], 0
    for c in cut:
        out.append((a, int(c)))
        a = int(c) + 1
    out.append((a, n - 1))
    return out


def simplify(t, x, y, tol_perp, tol_sed, z=None, tol_z=None):
    """Boolean keep-mask over one part."""
    n = len(t)
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b <= a + 1:
            continue
        ax, ay, bx, by = x[a], y[a], x[b], y[b]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        px, py = x[a + 1:b], y[a + 1:b]
        if L2 > 0:
            u = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
            perp = np.hypot(px - (ax + u * dx), py - (ay + u * dy))
        else:
            perp = np.hypot(px - ax, py - ay)
        span = t[b] - t[a]
        f = (t[a + 1:b] - t[a]) / span if span > 0 else np.zeros(b - a - 1)
        sed = np.hypot(px - (ax + f * dx), py - (ay + f * dy))
        err = np.maximum(perp / tol_perp, sed / tol_sed)
        if z is not None:
            err = np.maximum(err, np.abs(z[a + 1:b] - (z[a] + f * (z[b] - z[a]))) / tol_z)
        i = int(np.argmax(err))
        if err[i] > 1.0:
            k = a + 1 + i
            keep[k] = True
            stack.append((a, k)); stack.append((k, b))
    return keep


def enforce(keep, ok):
    """Add fixes back until every simplified segment passes ok(i, j). Segments between
    neighbouring original fixes cannot be refined and are left as logged."""
    idx = list(np.where(keep)[0])
    stack = [(idx[k], idx[k + 1]) for k in range(len(idx) - 1) if idx[k + 1] > idx[k] + 1]
    while stack:
        a, b = stack.pop()
        if b <= a + 1 or ok(a, b):
            continue
        m = (a + b) // 2
        keep[m] = True
        stack.append((a, m)); stack.append((m, b))
    return keep


class WaterCheck:
    """Is the straight line between two fixes clear of land? Raster first, exact when close."""

    def __init__(self, G):
        self.G = G

    def clear(self, lat1, lon1, lat2, lon2):
        G = self.G
        d = geo.dist_m((lat1, lon1), (lat2, lon2))
        if d < 20:
            return True
        n = max(2, int(d / 15))
        f = np.linspace(0, 1, n + 1)
        la = lat1 + (lat2 - lat1) * f; lo = lon1 + (lon2 - lon1) * f
        r = ((geo.BOX[3] - la) * MLAT / geo.RASTER_M).astype(int)
        c = ((lo - geo.BOX[0]) * geo.M_PER_DEG_LON / geo.RASTER_M).astype(int)
        inb = (r >= 0) & (r < G.ny) & (c >= 0) & (c < G.nx)
        if inb.all() and (G.dist_land[r, c] >= 40).all():
            return True
        return G.segment_clear((lat1, lon1), (lat2, lon2), 15)


class RoadCheck:
    """Is every point of the straight line between two fixes within tol_m of a road centreline?"""

    def __init__(self, G, tol_m=30.0, res=5.0):
        import cv2
        self.G, self.res, self.tol = G, res, tol_m
        self.nx = int((geo.BOX[2] - geo.BOX[0]) * geo.M_PER_DEG_LON / res)
        self.ny = int((geo.BOX[3] - geo.BOX[1]) * MLAT / res)
        img = np.zeros((self.ny, self.nx), np.uint8)
        thick = max(1, int(2 * (tol_m - res) / res))          # under-estimate by one cell
        for _, _, pts in G.roads.features:
            a = np.array(pts)
            xy = np.column_stack([(a[:, 1] - geo.BOX[0]) * geo.M_PER_DEG_LON / res, (geo.BOX[3] - a[:, 0]) * MLAT / res])
            cv2.polylines(img, [np.round(xy).astype(np.int32)], False, 1, thickness=thick)
        self.mask = img.astype(bool)

    def on_road(self, la, lo):
        la = np.asarray(la, float); lo = np.asarray(lo, float)
        r = ((geo.BOX[3] - la) * MLAT / self.res).astype(int)
        c = ((lo - geo.BOX[0]) * geo.M_PER_DEG_LON / self.res).astype(int)
        inb = (r >= 0) & (r < self.ny) & (c >= 0) & (c < self.nx)
        out = np.zeros(len(la), bool)
        out[inb] = self.mask[r[inb], c[inb]]
        return out

    def clear(self, lat1, lon1, lat2, lon2):
        d = geo.dist_m((lat1, lon1), (lat2, lon2))
        if d < 12:
            return True
        n = max(2, int(d / 6))
        f = np.linspace(0, 1, n + 1)
        return bool(self.on_road(lat1 + (lat2 - lat1) * f, lon1 + (lon2 - lon1) * f).all())


class RoadMatcher:
    """Finds the street path a vehicle took between two logged fixes.

    Each fix is snapped to the nearest road edge (whatever its distance: a unit parked in a
    station yard is connected to the street outside). A bounded shortest-path search then runs
    from both ends of the first fix's edge to both ends of the second's, so the path leaves and
    arrives through whichever end is shorter and never doubles back. Every vertex returned is a
    snapped fix position or a node of the Census road graph; nothing is invented.
    """

    CELL = 150.0

    def __init__(self, G):
        import heapq
        self.hq = heapq
        self.G, self.R = G, G.roads
        R = self.R
        u, v, w = [], [], []
        for a, nb in R.adj.items():
            for b, e in nb.items():
                if a < b:
                    u.append(a); v.append(b); w.append(e[1])
        self.u, self.v, self.w = np.array(u), np.array(v), np.array(w)
        self.ax, self.ay = R.nxy[self.u, 0], R.nxy[self.u, 1]
        self.bx, self.by = R.nxy[self.v, 0], R.nxy[self.v, 1]
        grid = {}
        c = self.CELL
        x0 = np.floor(np.minimum(self.ax, self.bx) / c).astype(int); x1 = np.floor(np.maximum(self.ax, self.bx) / c).astype(int)
        y0 = np.floor(np.minimum(self.ay, self.by) / c).astype(int); y1 = np.floor(np.maximum(self.ay, self.by) / c).astype(int)
        for i in range(len(self.u)):
            for gx in range(x0[i], x1[i] + 1):
                for gy in range(y0[i], y1[i] + 1):
                    grid.setdefault((gx, gy), []).append(i)
        self.grid = {k: np.array(val, dtype=np.int32) for k, val in grid.items()}
        self._snap = {}
        self.adj = {a: [(b, e[1]) for b, e in nb.items()] for a, nb in R.adj.items()}

    def snap(self, lat, lon, max_m=600.0):
        """(distance_m, x, y, edge index) of the nearest point on the road graph, or None."""
        key = (round(lat, 5), round(lon, 5))
        if key in self._snap:
            return self._snap[key]
        px, py = lon * geo.M_PER_DEG_LON, lat * geo.M_PER_DEG_LAT
        gx, gy = int(px // self.CELL), int(py // self.CELL)
        out = None
        for rad in (1, 2, 4):
            idx = [self.grid[k] for k in ((gx + dx, gy + dy) for dx in range(-rad, rad + 1) for dy in range(-rad, rad + 1)) if k in self.grid]
            if not idx:
                continue
            idx = np.unique(np.concatenate(idx))
            dx, dy = self.bx[idx] - self.ax[idx], self.by[idx] - self.ay[idx]
            L2 = dx * dx + dy * dy
            t = np.clip(((px - self.ax[idx]) * dx + (py - self.ay[idx]) * dy) / np.where(L2 > 0, L2, 1), 0, 1)
            cx, cy = self.ax[idx] + t * dx, self.ay[idx] + t * dy
            d = np.hypot(px - cx, py - cy)
            k = int(np.argmin(d))
            if d[k] <= rad * self.CELL and d[k] <= max_m:
                out = (float(d[k]), float(cx[k]), float(cy[k]), int(idx[k]))
                break
        self._snap[key] = out
        return out

    def _ll(self, x, y):
        return (y / geo.M_PER_DEG_LAT, x / geo.M_PER_DEG_LON)

    def path(self, a, b, limit_m):
        """Road path from fix a to fix b (lat, lon). Returns (points, metres, stub_a_m, stub_b_m) where
        points run from the snapped position of a to the snapped position of b, or None when the
        two are not connected within limit_m of driving."""
        sa, sb = self.snap(*a), self.snap(*b)
        if sa is None or sb is None:
            return None
        pa, pb = (sa[1], sa[2]), (sb[1], sb[2])
        ea, eb = sa[3], sb[3]
        if ea == eb:
            m = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            return [self._ll(*pa), self._ll(*pb)], m, sa[0], sb[0]
        nxy = self.R.nxy
        src = {int(self.u[ea]): math.hypot(pa[0] - self.ax[ea], pa[1] - self.ay[ea]), int(self.v[ea]): math.hypot(pa[0] - self.bx[ea], pa[1] - self.by[ea])}
        dst = {int(self.u[eb]): math.hypot(pb[0] - self.ax[eb], pb[1] - self.ay[eb]), int(self.v[eb]): math.hypot(pb[0] - self.bx[eb], pb[1] - self.by[eb])}
        tx, ty = pb
        hq = self.hq
        dist, prev, pq = dict(src), {}, [(c + math.hypot(nxy[n, 0] - tx, nxy[n, 1] - ty), c, n) for n, c in src.items()]
        hq.heapify(pq)
        best, best_n = float("inf"), None
        while pq:
            f, c, n = hq.heappop(pq)
            if f >= best or f > limit_m:
                break
            if c > dist.get(n, 1e18):
                continue
            if n in dst and c + dst[n] < best:
                best, best_n = c + dst[n], n
            for m2, w in self.adj.get(n, ()):
                nc = c + w
                if nc < dist.get(m2, 1e18):
                    dist[m2] = nc; prev[m2] = n
                    hq.heappush(pq, (nc + math.hypot(nxy[m2, 0] - tx, nxy[m2, 1] - ty), nc, m2))
        if best_n is None or best > limit_m:
            return None
        nodes = [best_n]
        while nodes[-1] in prev:
            nodes.append(prev[nodes[-1]])
        nodes.reverse()
        pts = [self._ll(*pa)] + [self.R.nodes[n] for n in nodes] + [self._ll(*pb)]
        return pts, best, sa[0], sb[0]

    def _reach(self, snap, limit_m):
        """Driving distance (and predecessor) from a snapped fix to every node within limit_m."""
        e, px, py = snap[3], snap[1], snap[2]
        dist = {int(self.u[e]): math.hypot(px - self.ax[e], py - self.ay[e]), int(self.v[e]): math.hypot(px - self.bx[e], py - self.by[e])}
        prev, pq = {}, [(c, n) for n, c in dist.items()]
        self.hq.heapify(pq)
        while pq:
            c, n = self.hq.heappop(pq)
            if c > dist.get(n, 1e18):
                continue
            for m2, w in self.adj.get(n, ()):
                nc = c + w
                if nc <= limit_m and nc < dist.get(m2, 1e18):
                    dist[m2] = nc; prev[m2] = n
                    self.hq.heappush(pq, (nc, m2))
        return dist, prev

    def bridged(self, a, b, limit_m, max_bridge_m=60.0):
        """Best partial street path for two fixes that the graph only joins by a long way round
        (the two carriageways of a divided road, a crossing the Census file leaves un-noded):
        streets from a as far as they go towards b, one hop of at most max_bridge_m to a street
        that leads to b, then streets to b. Same return as path(), or None."""
        sa, sb = self.snap(*a), self.snap(*b)
        if sa is None or sb is None:
            return None
        A, pA = self._reach(sa, limit_m)
        B, pB = self._reach(sb, limit_m)
        an = np.fromiter(A.keys(), dtype=np.int64); bn = np.fromiter(B.keys(), dtype=np.int64)
        nxy = self.R.nxy
        D = np.hypot(nxy[an, 0][:, None] - nxy[bn, 0][None, :], nxy[an, 1][:, None] - nxy[bn, 1][None, :])
        tot = np.array([A[int(n)] for n in an])[:, None] + D + np.array([B[int(n)] for n in bn])[None, :]
        tot = np.where(D <= max_bridge_m, tot + 2.0 * D, np.inf)      # a short hop is preferred to a long one
        i, j = np.unravel_index(int(np.argmin(tot)), tot.shape)
        if not np.isfinite(tot[i, j]):
            return None
        metres = float(tot[i, j] - 2.0 * D[i, j])
        if metres > limit_m:
            return None
        na = [int(an[i])]
        while na[-1] in pA:
            na.append(pA[na[-1]])
        na.reverse()
        nb = [int(bn[j])]
        while nb[-1] in pB:
            nb.append(pB[nb[-1]])
        nodes = na + [n for n in nb if n != na[-1]]
        pts = [self._ll(sa[1], sa[2])] + [self.R.nodes[n] for n in nodes] + [self._ll(sb[1], sb[2])]
        return pts, metres, sa[0], sb[0]
