"""Verification of water_overrides_local.geojson v3 (2026-11-11). Uses scripts/geo.py (Geo.is_land) on the live files and an
independent exact point-in-polygon test on the v1 / v2-interrupted copies in _parts/. Prints a report and writes land_upgrade_check.png."""
import sys, os, json, glob, math, collections
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) + '/'
G = ROOT + '99_reference/geo/'; P = G + '_parts/'
sys.path.insert(0, ROOT + 'scripts')
import numpy as np
from matplotlib.path import Path
for f in glob.glob(G + '_cache/land_*.npz'): os.remove(f)
import geo
Gx = geo.Geo(build_roads=False)
BOX = geo.BOX; MLAT = 110950.0; MLON = 111320.0 * math.cos(math.radians(27.8))
def polys(geom): return [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
class Polys:
    def __init__(s, fn):
        s.feats = json.load(open(fn))['features']; s.items = []
        for k, f in enumerate(s.feats):
            for p in polys(f['geometry']):
                a = np.asarray(p[0], float)
                s.items.append(((a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()), [Path(np.asarray(r, float)) for r in p], k))
    def contains(s, lat, lon, which=False):
        lat = np.atleast_1d(np.asarray(lat, float)); lon = np.atleast_1d(np.asarray(lon, float)); pts = np.column_stack([lon, lat])
        out = np.zeros(len(lat), bool); idx_o = np.full(len(lat), -1)
        for bb, paths, k in s.items:
            m = (lon >= bb[0]) & (lon <= bb[2]) & (lat >= bb[1]) & (lat <= bb[3])
            if not m.any(): continue
            idx = np.where(m)[0]; ins = paths[0].contains_points(pts[idx])
            for h in paths[1:]: ins &= ~h.contains_points(pts[idx])
            out[idx[ins]] = True; idx_o[idx[ins]] = k
        return (out, idx_o) if which else out
L = Polys(G + 'land_local.geojson'); W1 = Polys(P + 'water_overrides_local.v1.geojson'); W2 = Polys(P + 'water_overrides_local.v2_interrupted.geojson'); W3 = Polys(G + 'water_overrides_local.geojson')
def cls(lat, lon):
    l = L.contains(lat, lon)
    return l & ~W1.contains(lat, lon), l & ~W2.contains(lat, lon), l & ~W3.contains(lat, lon)
lw = lambda b: 'land ' if b else 'water'
tot_fail = 0
def run(title, T):
    global tot_fail
    print('---', title); ok = 0; n = 0
    for nm, la, lo, exp in T:
        got = bool(Gx.is_land(la, lo)); a, b, c = cls(la, lo); r, cc = Gx.px(la, lo); ras = bool(Gx.land_mask[min(r, Gx.ny - 1), min(cc, Gx.nx - 1)])
        assert got == bool(c[0]), 'geo.py and independent test disagree'
        if exp == 'info': tag = 'INFO'
        else:
            n += 1; good = (lw(got).strip() == exp); ok += good; tag = 'PASS' if good else 'FAIL'
        print('%s %-62s %9.5f %10.5f expect %-5s | v1 %s v2 %s v3 %s raster %s%s' % (tag, nm[:62], la, lo, exp, lw(a[0]), lw(b[0]), lw(got), lw(ras), '  <- changed by overrides' if a[0] != got else ''))
    print('    %d/%d pass' % (ok, n)); tot_fail += n - ok
    return ok, n
REF = [('CC Bay centre', 27.77, -97.25, 'water'), ('Gulf 10 km off Port Aransas', 27.80, -96.93, 'water'), ('CC Intl Airport', 27.770, -97.501, 'land'),
       ('Downtown CC', 27.795, -97.398, 'land'), ('Mid Mustang Island', 27.70, -97.16, 'land'), ('Port Aransas town', 27.834, -97.066, 'land'),
       ('Aransas Pass between the jetties', 27.836, -97.046, 'water'), ('Nueces Bay centre', 27.85, -97.42, 'water'), ('Rockport', 28.02, -97.055, 'land')]
EXTRA_V1 = [('Oso Bay (v1 extra)', 27.70, -97.32, 'water'), ('Harbor Island (v1 extra)', 27.848, -97.075, 'land'), ('Ship channel mid-bay (v1 extra)', 27.815, -97.30, 'water'),
            ('Inner Harbor at Harbor Bridge (v1 extra)', 27.8125, -97.396, 'water'), ('Ingleside (v1 extra)', 27.875, -97.21, 'land'), ('Portland (v1 extra)', 27.88, -97.325, 'land')]
r1 = run('nine reference points of SOURCES_land.md', REF); r1b = run('extra points of the 2026-11-09 verification', EXTRA_V1)
# ---- landmarks
lm = json.load(open(G + 'landmarks.geojson'))['features']
la = np.array([f['geometry']['coordinates'][1] for f in lm]); lo = np.array([f['geometry']['coordinates'][0] for f in lm])
inb = (lo >= BOX[0]) & (lo <= BOX[2]) & (la >= BOX[1]) & (la <= BOX[3])
LANDCAT = {'school', 'community', 'runway_end', 'fire_station', 'venue', 'wastewater', 'airport', 'police', 'hospital', 'helipad', 'ems', 'refinery', 'military', 'water_plant', 'weather_station', 'coast_guard'}
a, b, c = cls(la, lo); g3 = Gx.is_land_many(la, lo); assert (g3[inb] == c[inb]).all()
sel = inb & np.array([f['properties']['category'] in LANDCAT for f in lm])
print('--- landmarks of land categories in window: %d | land v1 %d, v2 %d, v3 %d | flipped by overrides v2 %d, v3 %d' % (sel.sum(), (a & sel).sum(), (b & sel).sum(), (c & sel).sum(), ((a != b) & sel).sum(), ((a != c) & sel).sum()))
for i in np.where(sel & ~c)[0]:
    p = lm[i]['properties']; print('    NOT LAND: %s [%s] %.5f,%.5f  (v1 %s; inside a land polygon: %s; metres to nearest land %.0f)' % (p['name'], p['category'], la[i], lo[i], lw(a[i]), bool(L.contains(la[i], lo[i])[0]), Gx.land_clearance_m(la[i], lo[i])))
print('    by category (in window, all categories): ' + ', '.join('%s %d/%d land' % (k, sum(1 for i in np.where(inb)[0] if lm[i]['properties']['category'] == k and c[i]), v) for k, v in sorted(collections.Counter(lm[i]['properties']['category'] for i in np.where(inb)[0]).items())))
# ---- additional check points
cp = json.load(open(P + 'land2_checkpoints.json'))['points']
NEW = [('GNIS %s [%s]' % (p['name'], p['cls']), p['lat'], p['lon'], p['expect']) for p in cp]
byname = {f['properties']['name']: f for f in lm}
def LMpt(prefix):
    f = next(f for n, f in byname.items() if n.startswith(prefix)); return f['geometry']['coordinates'][1], f['geometry']['coordinates'][0]
for nm, exp in (('Harbor Bridge', 'water'), ('Nueces Bay Causeway (US 181 southbound)', 'water'), ('Nueces Bay Causeway (US 181 northbound)', 'water'), ('JFK Causeway', 'water'), ('I-37 Nueces River bridge', 'info'),
                ('NOAA CO-OPS 8775792 Packery Channel', 'water'), ('NOAA CO-OPS 8775870 Bob Hall Pier', 'water'), ('NOAA CO-OPS 8775296 USS Lexington', 'water'),
                ('UNIV OF TEXAS AT AUSTIN, MARINE SCIENCE INSTITUTE, BOAT BASIN', 'info'), ('Aransas County Navigation District No. 1, Rockport Harbor Inner Mooring', 'info'), ('Small craft facility (ENC), Packery Channel area', 'info')):
    y, x = LMpt(nm); NEW.append(('landmark %s' % nm, y, x, exp))
# USACE GIWW centreline vertices in the upper Laguna Madre (27.60-27.66 N) and at Packery / JFK
best = {}
for f in json.load(open(G + 'channel_lines_usace.geojson'))['features']:
    g = f['geometry']; lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
    for ln in lines:
        for q in ln:
            x, y = q[:2]
            for tgt in (27.575, 27.61, 27.65):
                if -97.32 <= x <= -97.20 and abs(y - tgt) < 0.01 and (tgt not in best or abs(y - tgt) < abs(best[tgt][0] - tgt)): best[tgt] = (y, x)
for tgt, (y, x) in sorted(best.items()): NEW.append(('USACE GIWW centreline vertex, Laguna Madre near %.3fN' % tgt, round(y, 5), round(x, 5), 'water'))
# road-centreline crossings (derived from the TIGER road geometry: mid-point of the water run of the named road in a box)
def crossing(name, box, files=('roads_major.geojson', 'roads_arterial.geojson', 'roads_local_all.geojson')):
    best = None
    for fn in files:
        for f in json.load(open(G + fn))['features']:
            if f['properties'].get('name') != name: continue
            g = f['geometry']; lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
            for ln in lines:
                pts = []
                for p0, p1 in zip(ln, ln[1:]):
                    d = math.hypot((p1[0] - p0[0]) * MLON, (p1[1] - p0[1]) * MLAT); k = max(1, int(d / 5))
                    pts += [(p0[0] + (p1[0] - p0[0]) * i / k, p0[1] + (p1[1] - p0[1]) * i / k) for i in range(k)]
                pts = [p for p in pts if box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]]
                if not pts: continue
                w = ~Gx.is_land_many([p[1] for p in pts], [p[0] for p in pts]); i = 0
                while i < len(pts):
                    if w[i]:
                        j = i
                        while j + 1 < len(pts) and w[j + 1]: j += 1
                        if best is None or j - i > best[0]: best = (j - i, pts[(i + j) // 2])
                        i = j + 1
                    else: i += 1
    return best
for label, name, box in (('Nueces River at the I-37 bridge', 'I- 37', (-97.65, 27.86, -97.60, 27.91)), ('Oso Bay at the SH 358 (SPID) bridge', 'State Hwy 358', (-97.33, 27.67, -97.30, 27.69)),
                         ('Cayo del Oso at the Yorktown Blvd bridge', 'Yorktown Blvd', (-97.37, 27.62, -97.32, 27.66)), ('Oso Creek at the S Staples St bridge', 'S Staples St', (-97.42, 27.63, -97.36, 27.68)),
                         ('Oso Bay inlet at the Ocean Dr bridge', 'Ocean Dr', (-97.34, 27.70, -97.29, 27.72)), ('Copano Bay at the SH 35 causeway', 'State Hwy 35', (-97.05, 28.09, -96.99, 28.125)),
                         ('Fish Pass / SH 361 bridge, Mustang Island', 'State Hwy 361', (-97.19, 27.67, -97.16, 27.70))):
    bst = crossing(name, box)
    if bst is None: print('    (no water run found on %s for %s)' % (name, label))
    else: NEW.append(('%s [mid-point of a %d m water run on the %s centreline]' % (label, (bst[0] + 1) * 5, name), round(bst[1][1], 5), round(bst[1][0], 5), 'water'))
r2 = run('additional check points (GNIS names, NBI bridges, CO-OPS gauges, USACE centreline, road crossings)', NEW)
# ---- roads over water
X = []; Y = []; Wt = []; NM = []; LID = []; lid = 0
for fn in ('roads_major.geojson', 'roads_arterial.geojson', 'roads_local_all.geojson'):
    for f in json.load(open(G + fn))['features']:
        g = f['geometry']; lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates']
        for ln in lines:
            arr = np.asarray(ln, float)[:, :2]
            for i in range(len(arr) - 1):
                d = math.hypot((arr[i + 1, 0] - arr[i, 0]) * MLON, (arr[i + 1, 1] - arr[i, 1]) * MLAT)
                if d <= 0: continue
                k = max(1, int(round(d / 5))); t = (np.arange(k) + 0.5) / k
                X.append(arr[i, 0] + t * (arr[i + 1, 0] - arr[i, 0])); Y.append(arr[i, 1] + t * (arr[i + 1, 1] - arr[i, 1])); Wt.append(np.full(k, d / k)); NM += [f['properties'].get('name') or '(unnamed)'] * k; LID.append(np.full(k, lid))
            lid += 1
X = np.concatenate(X); Y = np.concatenate(Y); Wt = np.concatenate(Wt); LID = np.concatenate(LID); NM = np.array(NM)
m = (X >= BOX[0]) & (X <= BOX[2]) & (Y >= BOX[1]) & (Y <= BOX[3]); X, Y, Wt, LID, NM = X[m], Y[m], Wt[m], LID[m], NM[m]
l = L.contains(Y, X); o1 = W1.contains(Y, X); o2 = W2.contains(Y, X); o3, o3k = W3.contains(Y, X, True)
tot = Wt.sum()
print('--- road centrelines in window (roads_major + roads_arterial + roads_local_all, 5 m samples): %.1f km' % (tot / 1e3))
for nm, wat in (('v1', ~(l & ~o1)), ('v2 interrupted', ~(l & ~o2)), ('v3', ~(l & ~o3))):
    print('    %-15s in water %.2f km = %.3f %%   (of which no land polygon at all, i.e. charted open water: %.2f km; land turned to water by overrides: %.2f km)' % (nm, Wt[wat].sum() / 1e3, 100 * Wt[wat].sum() / tot, Wt[~l].sum() / 1e3, Wt[wat & l].sum() / 1e3))
wat = ~(l & ~o3)
runs = []
i = 0; n = len(X)
while i < n:
    if wat[i]:
        j = i
        while j + 1 < n and wat[j + 1] and LID[j + 1] == LID[i]: j += 1
        runs.append((Wt[i:j + 1].sum(), NM[i], Y[(i + j) // 2], X[(i + j) // 2], (l[i:j + 1] & o3[i:j + 1]).mean(), o3k[(i + j) // 2])); i = j + 1
    else: i += 1
agg = collections.defaultdict(lambda: [0.0, 0, None, 0.0])
for ln_, nm, y, x, fo, k in runs:
    key = (nm, round(y / 0.03), round(x / 0.03)); a_ = agg[key]; a_[0] += ln_; a_[1] += 1; a_[3] += ln_ * fo
    if a_[2] is None or ln_ > a_[2][0]: a_[2] = (ln_, y, x)
print('    water runs >= 100 m: %d (%.1f km of %.1f km)' % (sum(1 for r in runs if r[0] >= 100), sum(r[0] for r in runs if r[0] >= 100) / 1e3, Wt[wat].sum() / 1e3))
print('    longest stretches (road, carriageways/segments summed per ~3 km cell): length, where, share caused by an override')
for (nm, _, _), a_ in sorted(agg.items(), key=lambda kv: -kv[1][0])[:22]:
    print('      %7.0f m  %-28s %d run(s), longest %5.0f m at %.4f,%.4f  override share %3.0f %%' % (a_[0], nm[:28], a_[1], a_[2][0], a_[2][1], a_[2][2], 100 * a_[3] / a_[0]))
print('    road length inside each override polygon (v3), > 60 m:')
per = collections.defaultdict(float); pn = collections.defaultdict(set)
for k, wl, nm in zip(o3k[l & o3], Wt[l & o3], NM[l & o3]): per[k] += wl; pn[k].add(nm)
for k, v in sorted(per.items(), key=lambda kv: -kv[1]):
    if v > 60:
        p = W3.feats[k]['properties']; print('      %5.0f m  %-20s %s  %s' % (v, str(p['name'])[:20], p['objectid'] or p.get('geoid') or 'seam', sorted(pn[k])[:4]))
# ---- file sanity
nf = len(W3.feats); nv = sum(len(r) for f in W3.feats for p in polys(f['geometry']) for r in p)
bad = sum(1 for f in W3.feats for p in polys(f['geometry']) for r in p if r[0] != r[-1] or len(r) < 4)
req = all(all(k in f['properties'] for k in ('name', 'source', 'objectid', 'tolerance_deg', 'reason')) for f in W3.feats)
print('--- water_overrides_local.geojson: %d features, %d vertices, unclosed/short rings %d, interior rings %d, required properties on every feature: %s' % (nf, nv, bad, sum(len(p) - 1 for f in W3.feats for p in polys(f['geometry'])), req))
v1 = json.load(open(P + 'land_local.v1.geojson')); v2 = json.load(open(G + 'land_local.geojson'))
print('    land_local.geojson geometry identical to v1:', [f['geometry'] for f in v1['features']] == [f['geometry'] for f in v2['features']])
rng = np.random.default_rng(1); rl = rng.uniform(27.53, 28.12, 200000); ro = rng.uniform(-97.645, -96.855, 200000)
ex = Gx.is_land_many(rl, ro); rr = ((BOX[3] - rl) * geo.M_PER_DEG_LAT / geo.RASTER_M).astype(int); cc = ((ro - BOX[0]) * geo.M_PER_DEG_LON / geo.RASTER_M).astype(int)
ra = Gx.land_mask[np.clip(rr, 0, Gx.ny - 1), np.clip(cc, 0, Gx.nx - 1)]
a_, b_, c_ = cls(rl, ro)
print('    200k random points: geo.py raster agrees with exact test on %.2f %%; land fraction v1 %.4f, v2 %.4f, v3 %.4f' % (100 * (ex == ra).mean(), a_.mean(), b_.mean(), c_.mean()))
print('TOTAL: reference %d/%d, v1 extras %d/%d, additional %d/%d, failures %d' % (r1 + r1b + r2 + (tot_fail,)))
# ---- plot
if '--noplot' not in sys.argv:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    def grid(x0, x1, y0, y1, nx):
        ny = int(nx * (y1 - y0) * MLAT / ((x1 - x0) * MLON)); xs = np.linspace(x0, x1, nx); ys = np.linspace(y1, y0, ny); XX, YY = np.meshgrid(xs, ys)
        a, b, c = cls(YY.ravel(), XX.ravel()); return a.reshape(ny, nx), b.reshape(ny, nx), c.reshape(ny, nx)
    views = [('whole window', BOX[0], BOX[2], BOX[1], BOX[3], 800), ('Oso Bay / Flour Bluff / Laguna Madre', -97.42, -97.20, 27.59, 27.74, 700),
             ('Portland / Sunset Lake / Nueces Bay', -97.40, -97.28, 27.83, 27.91, 600), ('Live Oak Peninsula / Port Bay / Copano', -97.28, -97.02, 27.93, 28.125, 700),
             ('Port Aransas / Mustang Beach Airport', -97.11, -97.04, 27.795, 27.845, 600)]
    cm = ListedColormap(['#cfe6fa', '#efe6c8', '#1f6fd0', '#e0403a'])
    fig, axs = plt.subplots(len(views), 3, figsize=(21, 6.2 * len(views)))
    chk = [(nm, y, x, e) for nm, y, x, e in REF + NEW if e != 'info']
    for row, (title, x0, x1, y0, y1, nx) in zip(axs, views):
        a, b, c = grid(x0, x1, y0, y1, nx)
        for ax, (lab, cur) in zip(row, (('v1 (2026-11-09)', a), ('v2 interrupted (2026-11-10): blue = water added vs v1', b), ('v3 audited (2026-11-11): blue = added vs v1, red = dropped from v2', c))):
            img = cur.astype(int)                      # 0 water, 1 land
            img[(a) & (~cur)] = 2                      # land in v1, water now
            if cur is c: img[(~b) & c] = 3             # water in v2, land again in v3
            ax.imshow(img, extent=(x0, x1, y0, y1), cmap=cm, vmin=0, vmax=3, interpolation='nearest', aspect=1 / math.cos(math.radians(27.8)))
            ax.set_title('%s - %s' % (title, lab), fontsize=9); ax.tick_params(labelsize=6)
            if cur is c:
                for nm, y, x, e in chk:
                    if x0 < x < x1 and y0 < y < y1: ax.plot(x, y, marker='v' if e == 'water' else '^', color='k' if (lw(bool(Gx.is_land(y, x))).strip() == e) else 'magenta', ms=4, mfc='none', mew=0.8)
            ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    fig.tight_layout(); fig.savefig(P + 'land_upgrade_check.png', dpi=60)
    print('plot written:', P + 'land_upgrade_check.png')
for f in glob.glob(G + '_cache/land_*.npz'): os.remove(f)
print('cache land_*.npz removed:', glob.glob(G + '_cache/land_*.npz') == [])
