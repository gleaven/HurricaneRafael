"""Placement helpers for the land-side registries (used by build_registries_land.py).

Every coordinate a registry carries comes from one of three places, and says which:

  site(...)     a real published point in 99_reference/geo/landmarks.geojson
                -> position_basis "real site: <landmark name> [<source>]"
  beside(...)   a point 35 m off the centreline of a named real road (Census TIGER), at the
                place on that road nearest a target, used only where no real point exists
                -> position_basis "placed beside <road> (no published point in the reference set)"
  abutment(...) the land end of a bridge, found by walking the real road from the published
                mid-span point until it is on land
                -> position_basis "land abutment of <road>, <n> m from the published mid-span point"

Nothing here invents geometry; the targets passed to beside() only choose which part of a
real road to use.
"""
import math
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geo  # noqa: E402

_G = None


def G():
    global _G
    if _G is None:
        _G = geo.Geo()
    return _G


def r5(x):
    return round(float(x), 5)


def landmark(name, category=None, exact=False):
    """The single landmark whose name contains (or equals) `name`."""
    g = G()
    cats = None if category is None else ({category} if isinstance(category, str) else set(category))
    hits = [l for l in g.landmarks if (cats is None or l["category"] in cats)
            and ((l["name"] == name) if exact else (name.lower() in l["name"].lower()))]
    if len(hits) != 1:
        raise LookupError(f"landmark {name!r} ({category}): {len(hits)} matches {[h['name'] for h in hits][:6]}")
    return hits[0]


def site(name, category=None, exact=False, require_land=True):
    """(lat, lon, basis, landmark) for a real landmark point."""
    l = landmark(name, category, exact)
    lat, lon = r5(l["lat"]), r5(l["lon"])
    if require_land and not G().is_land(lat, lon):
        raise ValueError(f"landmark {l['name']} is not on land in the reference layer")
    src = l["source"].split(" (")[0]
    return lat, lon, f"real site: {l['name']} [{src}]", l


def _road_segments(pattern):
    g = G()
    rx = re.compile(pattern, re.I)
    feat_ok = np.array([bool(rx.search(f[0])) for f in g.roads.features])
    return feat_ok[g.roads.seg_feat]


def _project(lat, lon, mask=None):
    """Nearest point on the road network (optionally only masked segments).
    Returns (dist_m, lat, lon, name, unit direction dx, dy in metres)."""
    g = G()
    ax, ay, bx, by = g.roads.seg
    px, py = lon * geo.M_PER_DEG_LON, lat * geo.M_PER_DEG_LAT
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = np.clip(((px - ax) * dx + (py - ay) * dy) / np.where(L2 > 0, L2, 1), 0, 1)
    cx, cy = ax + t * dx, ay + t * dy
    d = np.hypot(px - cx, py - cy)
    if mask is not None:
        d = np.where(mask, d, np.inf)
    i = int(np.argmin(d))
    n = math.hypot(dx[i], dy[i]) or 1.0
    name = g.roads.features[g.roads.seg_feat[i]][0]
    return float(d[i]), cy[i] / geo.M_PER_DEG_LAT, cx[i] / geo.M_PER_DEG_LON, name, dx[i] / n, dy[i] / n


def beside(road, near, setback_m=35.0, max_km=2.5, what=None):
    """A land point `setback_m` off the centreline of a real road.

    road   regex matched against TIGER road names, or None for "whichever road is nearest"
    near   (lat, lon) target choosing which part of the road
    Returns (lat, lon, basis, road_name)."""
    g = G()
    mask = _road_segments(road) if road else None
    if mask is not None and not mask.any():
        raise LookupError(f"no road matches {road!r}")
    d, lat, lon, name, ux, uy = _project(near[0], near[1], mask)
    if d > max_km * 1000:
        raise ValueError(f"nearest {road!r} is {d / 1000:.1f} km from target {near} ({what})")
    best = None
    for side in (1, -1):
        for sb in (setback_m, setback_m * 0.6, setback_m * 1.6):
            la = lat + (ux * sb * side) / geo.M_PER_DEG_LAT
            lo = lon + (-uy * sb * side) / geo.M_PER_DEG_LON
            if g.is_land(la, lo):
                shore = g.shore_distance_m(la, lo) if g.in_box(la, lo) else 5000.0
                if best is None or shore > best[0]:
                    best = (shore, la, lo)
    if best is None:
        raise ValueError(f"no land beside {name} near {near} ({what})")
    label = name or "an unnamed road"
    return r5(best[1]), r5(best[2]), f"placed beside {label} (no published point in the reference set)", name


def abutment(mid, road=None):
    """Land end of a bridge: walk the real road away from the published mid-span point.
    Returns (lat, lon, basis, road_name)."""
    g = G()
    mask = _road_segments(road) if road else None
    d0, lat0, lon0, name, ux, uy = _project(mid[0], mid[1], mask)
    # follow the routable graph outward from the nearest node until a land node with 60 m of land around it
    start, _ = g.roads.nearest_node(lat0, lon0, main_only=False)
    seen, frontier = {start: 0.0}, [(0.0, start)]
    import heapq
    while frontier:
        dist, u = heapq.heappop(frontier)
        la, lo = g.roads.nodes[u]
        if g.is_land(la, lo) and g.shore_distance_m(la, lo) >= 50:
            return r5(la), r5(lo), (f"land abutment on {name or 'the bridge road'}, {dist:.0f} m along the road "
                                    f"from the published mid-span point"), name
        if dist > 6000:
            break
        for v, (cost, w, nm, cls) in g.roads.adj.get(u, {}).items():
            if v not in seen or dist + w < seen[v]:
                seen[v] = dist + w
                heapq.heappush(frontier, (dist + w, v))
    raise ValueError(f"no land abutment found within 6 km of {mid}")


def road_crossing_water(road, near, water_test):
    """Mid-point of the stretch of a named road that lies over water (per water_test) nearest `near`.
    Returns (lat, lon, length_m) or None."""
    g = G()
    mask = _road_segments(road)
    ax, ay, bx, by = g.roads.seg
    best = None
    for i in np.where(mask)[0]:
        a = (ay[i] / geo.M_PER_DEG_LAT, ax[i] / geo.M_PER_DEG_LON)
        b = (by[i] / geo.M_PER_DEG_LAT, bx[i] / geo.M_PER_DEG_LON)
        n = max(1, int(geo.dist_m(a, b) / 15))
        run = []
        for k in range(n + 1):
            p = (a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
            if water_test(*p):
                run.append(p)
            elif run:
                break
        if len(run) >= 2:
            mid = run[len(run) // 2]
            dd = geo.dist_m(mid, near)
            if best is None or dd < best[0]:
                best = (dd, r5(mid[0]), r5(mid[1]), geo.dist_m(run[0], run[-1]))
    return None if best is None else best[1:]


def nominal_box(lat, lon, half_km):
    dlat = half_km * 1000 / geo.M_PER_DEG_LAT
    dlon = half_km * 1000 / geo.M_PER_DEG_LON
    return [r5(lon - dlon), r5(lat - dlat), r5(lon + dlon), r5(lat + dlat)]


def box_of(points):
    """[lon_min, lat_min, lon_max, lat_max] of (lat, lon) points."""
    la = [p[0] for p in points]; lo = [p[1] for p in points]
    return [r5(min(lo)), r5(min(la)), r5(max(lo)), r5(max(la))]


def union_box(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
