"""Path building for the maritime generators.

Everything here is a thin layer over scripts/geo.py: routes come from the USACE channel graph
(geo.nav) or the open-water grid (geo.water); this module only repairs harbour mouths at the
25 m raster, simplifies, and verifies every path it hands out with the same rules that
scripts/check_geo.py applies to the finished AIS file. A path that fails is never returned.
"""
import heapq
import math

import numpy as np

import geo

SEA_BAR_LON = -96.9636
M_LAT = geo.M_PER_DEG_LAT
M_LON = geo.M_PER_DEG_LON


def interp(a, b, f):
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def dest_point(p, bearing_deg, metres):
    b = math.radians(bearing_deg)
    return (p[0] + metres * math.cos(b) / M_LAT, p[1] + metres * math.sin(b) / (111_320.0 * math.cos(math.radians(p[0]))))


class Path:
    """Polyline of (lat, lon) with cumulative metres. Immutable once built."""
    __slots__ = ("pts", "cum", "length", "zone", "head", "tail", "nofix")

    def __init__(self, pts):
        self.pts = [(float(p[0]), float(p[1])) for p in pts]
        d = [0.0]
        for a, b in zip(self.pts, self.pts[1:]):
            d.append(d[-1] + geo.dist_m(a, b))
        self.cum = np.array(d)
        self.length = float(d[-1])
        self.zone = None      # per-segment reporting zone, filled by Geom.zones()
        self.head = 0.0       # metres of berth leg at the start (between berth and channel centerline)
        self.tail = 0.0       # metres of berth leg at the end
        self.nofix = None     # per-segment flag: narrow gap where no position report is emitted

    def at(self, s):
        """(lat, lon, heading) at s metres along the path."""
        if s <= 0:
            i = 0
        elif s >= self.length:
            i = len(self.pts) - 2
        else:
            i = int(np.searchsorted(self.cum, s, side="right")) - 1
            i = min(max(i, 0), len(self.pts) - 2)
        if len(self.pts) < 2:
            return self.pts[0][0], self.pts[0][1], 0.0
        a, b = self.pts[i], self.pts[i + 1]
        seg = self.cum[i + 1] - self.cum[i]
        f = 0.0 if seg <= 0 else min(max((s - self.cum[i]) / seg, 0.0), 1.0)
        p = interp(a, b, f)
        return p[0], p[1], geo.bearing(a, b) if seg > 0 else 0.0

    def reversed(self):
        r = Path(list(reversed(self.pts)))
        r.head, r.tail = self.tail, self.head
        r.nofix = list(reversed(self.nofix)) if self.nofix else None
        return r


def join(*paths):
    """Concatenate paths (end of one = start of next), keeping no-report flags and berth legs."""
    pts, flags = [], []
    for p in paths:
        seq = p.pts if isinstance(p, Path) else list(p)
        fl = (p.nofix if isinstance(p, Path) and p.nofix else [False] * (len(seq) - 1))
        for k, q in enumerate(seq):
            if not pts:
                pts.append(q)
            elif geo.dist_m(pts[-1], q) > 0.5:
                pts.append(q)
                flags.append(fl[k - 1] if k > 0 else False)
    out = Path(pts)
    out.nofix = flags if any(flags) else None
    first = paths[0]; last = paths[-1]
    out.head = first.head if isinstance(first, Path) else 0.0
    out.tail = last.tail if isinstance(last, Path) else 0.0
    return out


class Geom:
    def __init__(self, G=None):
        self.G = G or geo.Geo(build_roads=False)
        G = self.G
        docks = G.find(["port_dock", "marina", "ferry", "coast_guard"])
        self.docks = np.array([(l["lat"], l["lon"]) for l in docks])
        self.cache = {}
        # every edge of every land polygon (outer rings and holes), in local metres, for exact segment tests
        ax, ay, bx, by = [], [], [], []
        for it in G.land.items:
            for ring in [it["xy"]] + [h.vertices for h in it["holes"]]:
                r = np.asarray(ring, float)
                ax.append(r[:-1, 0] * M_LON); ay.append(r[:-1, 1] * M_LAT)
                bx.append(r[1:, 0] * M_LON); by.append(r[1:, 1] * M_LAT)
        self._eax, self._eay = np.concatenate(ax), np.concatenate(ay)
        self._ebx, self._eby = np.concatenate(bx), np.concatenate(by)
        self._exmin, self._exmax = np.minimum(self._eax, self._ebx), np.maximum(self._eax, self._ebx)
        self._eymin, self._eymax = np.minimum(self._eay, self._eby), np.maximum(self._eay, self._eby)

    def _crosses_land_edge(self, px, py, qx, qy):
        m = (self._exmax >= min(px, qx)) & (self._exmin <= max(px, qx)) & (self._eymax >= min(py, qy)) & (self._eymin <= max(py, qy))
        if not m.any():
            return False
        ax, ay, bx, by = self._eax[m], self._eay[m], self._ebx[m], self._eby[m]
        d1 = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
        d2 = (bx - ax) * (qy - ay) - (by - ay) * (qx - ax)
        d3 = (qx - px) * (ay - py) - (qy - py) * (ax - px)
        d4 = (qx - px) * (by - py) - (qy - py) * (bx - px)
        return bool(((d1 * d2 <= 0) & (d3 * d4 <= 0)).any())

    margin = 3.0

    def seg_clear_exact(self, a, b, margin_m=None):
        """True if the straight segment a-b, and the same segment shifted margin_m to either side,
        touch no land polygon edge and both ends are in the water. Exact (no sampling), so slivers
        thinner than any sampling step are caught."""
        G = self.G
        if margin_m is None:
            margin_m = self.margin
        if not (G.in_box(*a) or G.in_box(*b)):
            la, lo = self.sample([a, b], 400.0)
            return not G.is_land_many(la, lo).any()
        if G.is_land(*a) or G.is_land(*b):
            return False
        px, py, qx, qy = a[1] * M_LON, a[0] * M_LAT, b[1] * M_LON, b[0] * M_LAT
        L = math.hypot(qx - px, qy - py)
        if L < 0.01:
            return True
        nx, ny = -(qy - py) / L * margin_m, (qx - px) / L * margin_m
        for ox, oy in ((0.0, 0.0), (nx, ny), (-nx, -ny)):
            if self._crosses_land_edge(px + ox, py + oy, qx + ox, qy + oy):
                # edges inside a water-override area (Oso Bay) are not real shoreline
                mid = interp(a, b, 0.5)
                if G.water_override.contains(*a) and G.water_override.contains(*b) and G.water_override.contains(*mid):
                    continue
                return False
        return True

    # ---------------------------------------------------------------- checks (mirror check_geo)
    def sample(self, pts, step=5.0):
        la, lo = [], []
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(geo.dist_m(a, b) / step))
            for k in range(n):
                la.append(a[0] + (b[0] - a[0]) * k / n); lo.append(a[1] + (b[1] - a[1]) * k / n)
        la.append(pts[-1][0]); lo.append(pts[-1][1])
        return np.array(la), np.array(lo)

    def land_hits(self, pts, step=4.0):
        """Number of legs of the polyline that touch land (exact edge test with a 3 m margin)."""
        return sum(0 if self.seg_clear_exact(a, b) else 1 for a, b in zip(pts, pts[1:]))

    def clear(self, a, b, step=4.0):
        return self.seg_clear_exact(a, b)

    def near_dock(self, lat, lon):
        d = np.hypot((self.docks[:, 0] - lat) * M_LAT, (self.docks[:, 1] - lon) * M_LON)
        return float(d.min())

    def deep_ok(self, lat, lon):
        G = self.G
        if not (G.in_box(lat, lon) and lon < SEA_BAR_LON):
            return True
        return bool(G.channel_at(lat, lon, 150, 40) or G.anchorages.contains(lat, lon))

    def shallow_ok(self, lat, lon):
        G = self.G
        if not (G.in_box(lat, lon) and lon < SEA_BAR_LON):
            return True
        return not (G.land_clearance_m(lat, lon) < 30 and not G.channel_at(lat, lon, 150) and self.near_dock(lat, lon) > 200)

    def verify(self, pts, deep=False, what=""):
        """Raise if the polyline would fail check_geo's vessel rule anywhere along it."""
        if self.land_hits(pts, 4.0):
            raise ValueError(f"path touches land: {what}")
        la, lo = self.sample(pts, 20.0)
        test = self.deep_ok if deep else self.shallow_ok
        for a, b in zip(la, lo):
            if not test(float(a), float(b)):
                raise ValueError(f"path leaves {'deep channel' if deep else 'navigable water'} at {a:.5f},{b:.5f}: {what}")
        return True

    def pinch_path(self, pts, what=""):
        """Small craft only. Where a path squeezes through a gap narrower than check_geo's 30 m
        clearance rule (a marina entrance with no dock landmark beside it), replace that stretch
        by one straight segment between the last and first roomy points and flag the segment so
        that no position report is emitted inside the gap. Returns (pts, nofix flags)."""
        if self.land_hits(pts, 4.0):
            raise ValueError(f"path touches land: {what}")
        P = Path(pts)
        step = 5.0
        n = max(1, int(P.length / step))
        ss = [P.length * k / n for k in range(n + 1)]
        ok = []
        for s_ in ss:
            la, lo, _ = P.at(s_)
            ok.append(self.shallow_ok(la, lo))
        if all(ok):
            return list(pts), [False] * (len(pts) - 1)
        if not ok[0] or not ok[-1]:
            raise ValueError(f"path starts or ends in a gap: {what}")
        runs, i = [], 0
        while i <= n:
            if not ok[i]:
                j = i
                while j <= n and not ok[j]:
                    j += 1
                runs.append((ss[i - 1], ss[j]))
                i = j
            else:
                i += 1
        out, flags, pos = [pts[0]], [], 0.0
        verts = list(zip(P.cum.tolist(), P.pts))
        vi = 1
        for s0, s1 in runs:
            if s1 - s0 > 260.0:
                raise ValueError(f"gap too long ({s1 - s0:.0f} m): {what}")
            while vi < len(verts) and verts[vi][0] < s0:
                out.append(verts[vi][1]); flags.append(False); vi += 1
            a = P.at(s0)[:2]; b = P.at(s1)[:2]
            if not self.clear(a, b, 3.0):
                raise ValueError(f"gap chord touches land: {what}")
            if geo.dist_m(out[-1], a) > 0.5:
                out.append(a); flags.append(False)
            out.append(b); flags.append(True)
            while vi < len(verts) and verts[vi][0] <= s1:
                vi += 1
        while vi < len(verts):
            if geo.dist_m(out[-1], verts[vi][1]) > 0.5:
                out.append(verts[vi][1]); flags.append(False)
            vi += 1
        return out, flags

    def point_ok(self, p, deep=False):
        return (not self.G.is_land(*p)) and (self.deep_ok(*p) if deep else self.shallow_ok(*p))

    # ---------------------------------------------------------------- simplification
    def simplify(self, pts, tol_m=6.0):
        """Douglas-Peucker in local metres; the result is re-verified for land by the caller."""
        if len(pts) < 3:
            return list(pts)
        xy = np.array([(p[1] * M_LON, p[0] * M_LAT) for p in pts])
        keep = np.zeros(len(pts), bool)
        keep[0] = keep[-1] = True
        stack = [(0, len(pts) - 1)]
        while stack:
            i, j = stack.pop()
            if j <= i + 1:
                continue
            a, b = xy[i], xy[j]
            ab = b - a
            L = math.hypot(*ab)
            seg = xy[i + 1:j]
            if L == 0:
                d = np.hypot(seg[:, 0] - a[0], seg[:, 1] - a[1])
            else:
                d = np.abs(ab[0] * (seg[:, 1] - a[1]) - ab[1] * (seg[:, 0] - a[0])) / L
            k = int(np.argmax(d))
            if d[k] > tol_m:
                keep[i + 1 + k] = True
                stack.append((i, i + 1 + k)); stack.append((i + 1 + k, j))
        return [p for p, k in zip(pts, keep) if k]

    def densify(self, pts, max_m):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            n = max(1, int(math.ceil(geo.dist_m(a, b) / max_m)))
            for k in range(1, n + 1):
                out.append(interp(a, b, k / n))
        return out

    # ---------------------------------------------------------------- 25 m raster repair for harbour mouths
    def fine_route(self, a, b, margin_m=700.0):
        """Shortest water path on the 25 m land raster inside a window around a and b, kept away
        from the shore where there is room. Returns a list of (lat, lon) or None."""
        G = self.G
        ra, ca = G.px(*a); rb, cb = G.px(*b)
        m = int(margin_m / geo.RASTER_M)
        r0, r1 = max(min(ra, rb) - m, 0), min(max(ra, rb) + m, G.ny - 1)
        c0, c1 = max(min(ca, cb) - m, 0), min(max(ca, cb) + m, G.nx - 1)
        land = G.land_mask[r0:r1 + 1, c0:c1 + 1]
        dl = G.dist_land[r0:r1 + 1, c0:c1 + 1]
        s, t = (ra - r0, ca - c0), (rb - r0, cb - c0)

        def nearest_water(c):
            if not land[c]:
                return c
            best = None
            for rad in range(1, 8):
                for dr in range(-rad, rad + 1):
                    for dc in range(-rad, rad + 1):
                        q = (c[0] + dr, c[1] + dc)
                        if 0 <= q[0] < land.shape[0] and 0 <= q[1] < land.shape[1] and not land[q]:
                            d = dr * dr + dc * dc
                            if best is None or d < best[0]:
                                best = (d, q)
                if best:
                    return best[1]
            return None
        s, t = nearest_water(s), nearest_water(t)
        if s is None or t is None:
            return None
        nbr = [(-1, 0, 1), (1, 0, 1), (0, -1, 1), (0, 1, 1), (-1, -1, 1.4142), (-1, 1, 1.4142), (1, -1, 1.4142), (1, 1, 1.4142)]
        g, prev, pq = {s: 0.0}, {}, [(0.0, s)]
        while pq:
            f, u = heapq.heappop(pq)
            if u == t:
                break
            gu = g[u]
            for dr, dc, w in nbr:
                v = (u[0] + dr, u[1] + dc)
                if not (0 <= v[0] < land.shape[0] and 0 <= v[1] < land.shape[1]) or land[v]:
                    continue
                if dr and dc and (land[u[0] + dr, u[1]] or land[u[0], u[1] + dc]):
                    continue
                pen = max(0.0, (75.0 - float(dl[v])) / 25.0) * 1.5
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
        pts = [G.px_to_ll(r + r0, c + c0) for r, c in cells]
        pts = [a] + pts + [b]
        # string-pull with the exact land test
        out, i = [pts[0]], 0
        while i < len(pts) - 1:
            j = min(len(pts) - 1, i + 60)
            while j > i + 1 and not self.clear(pts[i], pts[j], 4.0):
                j -= 1
            if j == i + 1 and not self.clear(pts[i], pts[j], 4.0):
                return None
            out.append(pts[j]); i = j
        return out

    def water_path(self, a, b, clearance=150.0, deep=False, key=None, tol=6.0):
        """Small-craft path held 3 m off every charted land edge; in the few harbour mouths where
        that is not possible the margin drops to 1 m (still wider than coordinate rounding)."""
        if key is not None and key in self.cache:
            return self.cache[key]
        try:
            return self._water_path(a, b, clearance, deep, key, tol)
        except ValueError:
            self.margin = 1.0
            try:
                return self._water_path(a, b, clearance, deep, key, tol)
            finally:
                self.margin = 3.0

    def _water_path(self, a, b, clearance=150.0, deep=False, key=None, tol=6.0):
        """Verified small-craft path between two water points: geo.water.route, with any leg that
        clips a breakwater or spit re-routed on the 25 m raster. Cached by key."""
        if key is not None and key in self.cache:
            return self.cache[key]
        G = self.G
        r = None
        for c in (clearance, 100.0, 60.0, 40.0):
            if c > clearance:
                continue
            r = G.water.route(a, b, c)
            if r:
                break
        if not r:
            r = self.fine_route(a, b, 1500.0)
            if not r:
                raise ValueError(f"no water route {a} -> {b}")
        if geo.dist_m(r[0], a) > 1:
            r = [tuple(a)] + r
        if geo.dist_m(r[-1], b) > 1:
            r = r + [tuple(b)]
        fixed = [r[0]]
        for p, q in zip(r, r[1:]):
            if self.clear(p, q, 4.0):
                fixed.append(q)
            else:
                f = self.fine_route(p, q)
                if not f:
                    f = self.fine_route(p, q, 2500.0)
                if not f:
                    raise ValueError(f"cannot repair leg {p} -> {q}")
                fixed += f[1:]
        pts = self.simplify(fixed, tol)
        if self.land_hits(pts, 4.0):
            pts = fixed
        if deep:
            self.verify(pts, True, f"water_path {key or (a, b)}")
            path = Path(pts)
        else:
            pts, flags = self.pinch_path(pts, f"water_path {key or (a, b)}")
            path = Path(pts)
            path.nofix = flags
        if key is not None:
            self.cache[key] = path
        return path

    def nav_path(self, a, b, draft_ft=0.0, deep=False, key=None, end_at=None, start_at=None, tol=5.0):
        """Verified channel-centerline path. start_at / end_at add the short leg between a berth
        and the channel (the ship leaves or meets the centerline at the first node with a clear
        straight run to the berth)."""
        if key is not None and key in self.cache:
            return self.cache[key]
        G = self.G

        def attach_node(berth):
            """Channel node with a clear, rule-abiding straight run to the berth (nearest first)."""
            nav = G.nav
            d = np.hypot(nav.xy[:, 0] - berth[1] * M_LON, nav.xy[:, 1] - berth[0] * M_LAT)
            for i in np.argsort(d)[:60]:
                if d[i] > 700:
                    break
                if nav.depth[i] < draft_ft:
                    continue
                node = nav.nodes[int(i)]
                if d[i] < 1.0:
                    return node
                if self.clear(node, berth, 3.0):
                    try:
                        self.verify([node, berth], deep, "berth leg")
                    except ValueError:
                        continue
                    return node
            raise ValueError(f"no clear leg between channel and berth {berth}")
        a2 = attach_node(tuple(start_at)) if start_at is not None else a
        b2 = attach_node(tuple(end_at)) if end_at is not None else b
        r = G.nav.route(a2, b2, draft_ft)
        if not r:
            raise ValueError(f"no channel route {a} -> {b} at {draft_ft} ft")
        r = list(r)
        if start_at is not None and geo.dist_m(r[0], start_at) > 1.0:
            r = [tuple(start_at)] + r
        if end_at is not None and geo.dist_m(r[-1], end_at) > 1.0:
            r = r + [tuple(end_at)]
        r = self.clean_route(r, deep, keep_first=start_at is not None, keep_last=end_at is not None)
        tail = geo.dist_m(r[-2], r[-1]) if end_at is not None else 0.0
        head = geo.dist_m(r[0], r[1]) if start_at is not None else 0.0
        mid = r[(1 if start_at is not None else 0):(len(r) - 1 if end_at is not None else len(r))]
        mid = self.simplify(mid, tol) if len(mid) > 2 else mid
        pts = ([r[0]] if start_at is not None else []) + mid + ([r[-1]] if end_at is not None else [])
        if self.land_hits(pts, 4.0):
            pts = r
        self.verify(pts, deep, f"nav_path {key or (a, b)}")
        path = Path(pts)
        path.head, path.tail = head, tail
        if key is not None:
            self.cache[key] = path
        return path

    def clean_route(self, r, deep, keep_first=False, keep_last=False):
        """A few centerline vertices lie within a metre or two of a charted land edge (bridge
        fendering, tile seams). Where a leg fails the 3 m margin test, cut the corner past the
        offending vertex if the shortcut is clear and still inside the channel."""
        r = list(r)
        guard = 0
        i = 0
        while i < len(r) - 1:
            if self.seg_clear_exact(r[i], r[i + 1]):
                i += 1
                continue
            guard += 1
            if guard > 200:
                raise ValueError('centerline clean-up did not converge')
            fixed = False
            # try dropping the vertex after, then the vertex before, then both
            for lo, hi in ((i, i + 2), (i - 1, i + 1), (i - 1, i + 2), (i, i + 3), (i - 2, i + 1)):
                if lo < 0 or hi > len(r) - 1:
                    continue
                if (keep_first and lo == 0 and hi > 1 and False) or (keep_last and hi == len(r) - 1 and False):
                    continue
                a, b = r[lo], r[hi]
                if self.seg_clear_exact(a, b):
                    try:
                        self.verify([a, b], deep, "shortcut")
                    except ValueError:
                        continue
                    r = r[:lo + 1] + r[hi:]
                    i = max(lo - 1, 0)
                    fixed = True
                    break
            if not fixed:
                raise ValueError(f"centerline leg {r[i]} -> {r[i + 1]} touches land and cannot be bypassed")
        return r

    def offset(self, path, d_m, deep=False):
        """Path shifted d_m to starboard (negative: port) along its channel body; the berth legs
        and the last 300 m at each end are left alone. Falls back to smaller offsets, then to the
        original, when the shifted line would leave the channel or touch land."""
        key = ("off", id(path), d_m, deep)
        if key in self.cache:
            return self.cache[key]
        base = Path(self.densify(path.pts, 450.0))     # so that long straight reaches shift too
        pts = base.pts
        res = path
        lo, hi = path.head + 300.0, path.length - path.tail - 300.0
        for d in (d_m, d_m * 0.6, d_m * 0.3):
            out = []
            for i, p in enumerate(pts):
                s_ = float(base.cum[i])
                if s_ < lo or s_ > hi or i == 0 or i == len(pts) - 1 or not (-97.378 < p[1] < -96.97):
                    out.append(p)      # no offset in the Inner Harbor, at the bridge or outside the bar
                    continue
                b1 = geo.bearing(pts[i - 1], p); b2 = geo.bearing(p, pts[i + 1])
                turn = ((b2 - b1 + 540) % 360) - 180
                brg = (b1 + turn / 2.0) % 360
                k = 1.0 / max(0.5, math.cos(math.radians(turn / 2.0)))
                out.append(dest_point(p, brg + 90.0, d * k))
            try:
                self.verify(out, deep, "offset")
                simp = self.simplify(out, 3.0)
                res = Path(simp if not self.land_hits(simp, 4.0) else out)
                res.head, res.tail, res.nofix = path.head, path.tail, None
                break
            except ValueError:
                continue
        self.cache[key] = res
        return res

    def open_leg(self, a, b, deep=False, max_seg_m=None):
        """Straight open-water leg, verified (coarse coast offshore, exact coast inside the window)."""
        pts = [tuple(a), tuple(b)]
        la, lo = self.sample(pts, 400.0 if geo.dist_m(a, b) > 20000 else 25.0)
        if self.G.is_land_many(la, lo).any() or not self.seg_clear_exact(pts[0], pts[1]):
            raise ValueError(f"open leg crosses land {a} -> {b}")
        if geo.dist_m(a, b) < 40000:
            self.verify(pts, deep, "open leg")
        if max_seg_m:
            pts = self.densify(pts, max_seg_m)
        return Path(pts)

    def water_point_near(self, p, min_clear=40.0, max_m=600.0):
        """Nearest water point to p with at least min_clear metres to land (raster search)."""
        G = self.G
        r, c = G.px(*p)
        best = None
        rad = int(max_m / geo.RASTER_M)
        sub = G.dist_land[max(r - rad, 0):r + rad + 1, max(c - rad, 0):c + rad + 1]
        idx = np.argwhere(sub >= min_clear)
        if not len(idx):
            return None
        rr = idx[:, 0] + max(r - rad, 0); cc = idx[:, 1] + max(c - rad, 0)
        d = (rr - r) ** 2 + (cc - c) ** 2
        k = int(np.argmin(d))
        q = G.px_to_ll(int(rr[k]), int(cc[k]))
        return q if not G.is_land(*q) else None

    def land_point_near(self, p, max_m=400.0):
        """Nearest land point to p that is at least 15 m inland (for shore cameras)."""
        G = self.G
        r, c = G.px(*p)
        rad = int(max_m / geo.RASTER_M)
        r0, c0 = max(r - rad, 0), max(c - rad, 0)
        sub = G.dist_water[r0:r + rad + 1, c0:c + rad + 1]
        idx = np.argwhere(sub >= 15.0)
        if not len(idx):
            return None
        rr = idx[:, 0] + r0; cc = idx[:, 1] + c0
        order = np.argsort((rr - r) ** 2 + (cc - c) ** 2)
        for k in order[:40]:
            q = G.px_to_ll(int(rr[k]), int(cc[k]))
            if G.is_land(*q):
                return q
        return None


def _zone_of_point(G, lat, lon, sea_buoy=(27.79312, -96.96336), rx=(27.8397, -97.0725)):
    """0 = channel or harbour (about 1 min), 1 = open bay or approach (5 min),
    2 = offshore inside shore-station range (30 min), 3 = beyond shore-station range (satellite)."""
    if G.in_box(lat, lon):
        if G.channel_at(lat, lon, 0) or G.land_clearance_m(lat, lon) < 500:
            return 0
        if lon < SEA_BAR_LON or geo.gc_nm((lat, lon), sea_buoy) < 10:
            return 1
        return 2
    if geo.gc_nm((lat, lon), sea_buoy) < 10:
        return 1
    return 2 if geo.gc_nm((lat, lon), rx) <= 45.0 else 3


def zones(G, path):
    """Per-segment reporting zone (taken at the segment midpoint)."""
    if path.zone is None:
        z = []
        for a, b in zip(path.pts, path.pts[1:]):
            m = interp(a, b, 0.5)
            z.append(_zone_of_point(G, m[0], m[1]))
        path.zone = z
    return path.zone
