"""Independent point-in-polygon on the raw reference GeoJSON (does not import scripts/geo.py)."""
import json, os, numpy as np
from matplotlib.path import Path
GEO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '99_reference', 'geo'))
BOX = (-97.65, 27.525, -96.85, 28.125)
class Polys:
    def __init__(self, name, filt=None):
        fs = json.load(open(os.path.join(GEO, name)))['features']
        self.items = []
        for f in fs:
            if filt and not filt(f): continue
            g = f['geometry']; polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
            for p in polys:
                rings = [np.asarray(r, float)[:, :2] for r in p]
                bb = (rings[0][:,0].min(), rings[0][:,1].min(), rings[0][:,0].max(), rings[0][:,1].max())
                self.items.append((bb, [Path(r) for r in rings], f['properties']))
    def contains(self, lats, lons):
        lats = np.asarray(lats, float); lons = np.asarray(lons, float)
        out = np.zeros(len(lats), bool); pts = np.column_stack([lons, lats])
        for bb, paths, _ in self.items:
            m = (lons >= bb[0]) & (lons <= bb[2]) & (lats >= bb[1]) & (lats <= bb[3])
            if not m.any(): continue
            idx = np.where(m)[0]; inside = np.zeros(len(idx), bool)
            for p in paths: inside ^= p.contains_points(pts[idx])   # even-odd over rings
            out[idx] |= inside
        return out
_c = {}
def get(name, filt=None, key=None):
    k = key or name
    if k not in _c: _c[k] = Polys(name, filt)
    return _c[k]
def on_land(lats, lons):
    lats = np.asarray(lats, float); lons = np.asarray(lons, float)
    inb = (lons >= BOX[0]) & (lons <= BOX[2]) & (lats >= BOX[1]) & (lats <= BOX[3])
    out = np.zeros(len(lats), bool)
    if inb.any():
        out[inb] = get('land_local.geojson').contains(lats[inb], lons[inb]) & ~get('water_overrides_local.geojson').contains(lats[inb], lons[inb])
    if (~inb).any():
        out[~inb] = get('land_gulf_coarse.geojson').contains(lats[~inb], lons[~inb]) | (lons[~inb] < -98.0)
    return out
def in_channel(lats, lons): return get('channels_usace.geojson').contains(lats, lons)
def in_anchorage(lats, lons): return get('anchorages_fairways_noaa.geojson').contains(lats, lons)
