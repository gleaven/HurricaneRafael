"""Audit fix of water_overrides_local.geojson (2026-11-11).
Input : _parts/water_overrides_local.v2_interrupted.geojson (471 features, as left by the interrupted upgrade)
        _parts/land2_nwi_point_checks.json (USFWS NWI class at interior points, fetched 2026-11-11)
Output: water_overrides_local.geojson (v3) and _parts/water_overrides_local.v3_dropped.geojson (what was removed and why)
No geometry is created or moved: features are kept verbatim or dropped; the only vertex edit is removal of consecutive duplicates."""
import json, re, os, sys, glob, collections
import numpy as np
from matplotlib.path import Path
G = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/'
P = G + '_parts/'
sys.path.insert(0, P)
src = json.load(open(P + 'water_overrides_local.v2_interrupted.geojson'))
F = src['features']
nwi = collections.defaultdict(list)
for r in json.load(open(P + 'land2_nwi_point_checks.json'))['rows']:
    nwi[r['v2_index']].append(r['nwi'][0][0] if r['nwi'] else 'none')
OPEN = ('L1', 'L2', 'PUB', 'PAB', 'PUS', 'E1', 'R', 'M1')          # lake, pond, estuarine deepwater, river
FLAT = ('E2US', 'E2AB', 'E2RF')                                     # intertidal flat / aquatic bed (water by the chart convention)
def klass(code):
    if code == 'none': return 'upland'
    if code.startswith('E2US') and code[4:5] == 'P': return 'dry_flat'    # irregularly FLOODED = usually dry
    if code.startswith(FLAT): return 'tidal_flat'
    if code.startswith(('PEM', 'PSS', 'PFO', 'E2EM', 'E2SS', 'E2FO')): return 'marsh'
    if code.startswith(OPEN): return 'open_water'
    return 'other'
def verdict(codes):
    c = collections.Counter(klass(x) for x in codes)
    wet = c['open_water'] + c['tidal_flat']
    return 'water' if wet * 2 > len(codes) else 'not_water'
# case-by-case exceptions (see SOURCES_land.md, 2026-11-11 section)
KEEP_ANYWAY = {7: 'NWI PEM1Fx at the interior point, but the harbour chart (LAKARE) and TIGER (52 % overlap) both show water: two of three sources',
               107: 'NWI has no polygon at the deepest interior point, but NWI is L2UBFh (Lake) at the GNIS coordinate of Fresh Water Lake inside this polygon, and TIGER names it Fresh Water Lk'}
DROP_ANYWAY = {34: 'degenerate ENC LAKARE sliver (4 vertices, zero area)',
               51: 'ENC LAKARE fragment of 0.01 ha; NWI E2EM1N (marsh)'}
keep, drop = [], []
for k, f in enumerate(F):
    p = f['properties']
    if p.get('kind') == 'seam_patch':
        continue
    why = None
    if k in DROP_ANYWAY: why = DROP_ANYWAY[k]
    elif k in nwi and k not in KEEP_ANYWAY and verdict(nwi[k]) == 'not_water':
        cl = sorted(set(klass(x) for x in nwi[k]))
        why = 'USFWS NWI at %d interior point(s): %s = %s, not open water' % (len(nwi[k]), '/'.join(nwi[k]), '/'.join(cl))
        if 'Lake_area' in p['source']: why += '; charted LAKARE not confirmed by TIGER either (<50 % overlap)'
        elif p['zone'] == 'harbour_tile': why += '; the harbour chart shows land here'
        else: why += '; only TIGER shows a lake/pond here'
    if k in nwi:
        p['nwi_check'] = '/'.join(nwi[k]) + ' (' + '/'.join(sorted(set(klass(x) for x in nwi[k]))) + ')'
    else:
        p['nwi_check'] = None
    if why:
        p['drop_reason'] = why; p['v2_index'] = k; drop.append(f)
    else:
        if k in KEEP_ANYWAY: p['audit_note'] = KEEP_ANYWAY[k]
        keep.append((k, f))
# ---- seam patches: keep one copy, only if both parent polygons survive and it still changes land to water
def verts(f):
    return set(tuple(q) for q in f['geometry']['coordinates'][0])
kept_v = collections.defaultdict(set)
for k, f in keep:
    for v in verts(f): kept_v[v].add(k)
land = []
for f in json.load(open(G + 'land_local.geojson'))['features']:
    polys = [f['geometry']['coordinates']] if f['geometry']['type'] == 'Polygon' else f['geometry']['coordinates']
    for pl in polys:
        a = np.asarray(pl[0], float)
        land.append(((a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()), [Path(np.asarray(r, float)) for r in pl]))
kept_paths = [(k, Path(np.asarray(f['geometry']['coordinates'][0], float))) for k, f in keep]
kept_bb = [(pp.vertices[:, 0].min(), pp.vertices[:, 1].min(), pp.vertices[:, 0].max(), pp.vertices[:, 1].max()) for _, pp in kept_paths]
MLAT = 110950.0; MLON = 98471.0
def effective_m2(ring):
    r = np.asarray(ring, float)
    xs = np.arange(r[:, 0].min(), r[:, 0].max(), 1.0 / MLON); ys = np.arange(r[:, 1].min(), r[:, 1].max(), 1.0 / MLAT)
    if len(xs) == 0 or len(ys) == 0: return 0
    XX, YY = np.meshgrid(xs, ys); pts = np.column_stack([XX.ravel(), YY.ravel()])
    pts = pts[Path(r).contains_points(pts)]
    if len(pts) == 0: return 0
    on = np.zeros(len(pts), bool)
    for bb, paths in land:
        if bb[2] < r[:, 0].min() or bb[0] > r[:, 0].max() or bb[3] < r[:, 1].min() or bb[1] > r[:, 1].max(): continue
        ins = paths[0].contains_points(pts)
        for h in paths[1:]: ins &= ~h.contains_points(pts)
        on |= ins
    cov = np.zeros(len(pts), bool)
    for bb, (_, pp) in zip(kept_bb, kept_paths):
        if bb[2] < r[:, 0].min() or bb[0] > r[:, 0].max() or bb[3] < r[:, 1].min() or bb[1] > r[:, 1].max(): continue
        cov |= pp.contains_points(pts)
    return int((on & ~cov).sum())
seen = set(); seam_keep = []; seam_stats = collections.Counter()
for k, f in enumerate(F):
    p = f['properties']
    if p.get('kind') != 'seam_patch': continue
    ring = f['geometry']['coordinates'][0]
    key = tuple(sorted(set(tuple(q) for q in ring)))
    parents = set()
    for v in set(tuple(q) for q in ring): parents |= kept_v.get(v, set())
    orphan = any(tuple(q) not in kept_v for q in ring)
    p['nwi_check'] = None
    if key in seen: why = 'exact duplicate of another seam patch (the patch pass was run three times)'; seam_stats['duplicate'] += 1
    elif orphan or len(parents) < 2: why = 'a parent polygon of this seam patch was dropped'; seam_stats['orphan'] += 1
    else:
        e = effective_m2(ring)
        if e == 0: why = 'no effect: every land cell inside is already covered by another override'; seam_stats['no_effect'] += 1
        else: why = None; p['effective_m2'] = e
    seen.add(key)
    if why: p['drop_reason'] = why; p['v2_index'] = k; drop.append(f)
    else: seam_keep.append((k, f)); seam_stats['kept'] += 1
# ---- tidy kept features
from land2_script_parsefetch import load as rawload
rawv = {}
for fp in sorted(glob.glob(P + 'land2_raw_*.txt')):
    try: u, fs, t, _ = rawload(fp)
    except Exception: continue
    for x in fs:
        a = x['attributes']; kid = a.get('OBJECTID', a.get('GEOID'))
        tag = ('lake' if 'enc_lake' in fp else 'block' if '_wb_' in fp else 'hydro', kid)
        rawv.setdefault(tag, set()).update(tuple(q) for r in x['geometry']['rings'] for q in r)
out = []
ndup = 0; nclipfix = 0
for k, f in keep + seam_keep:
    p = f['properties']
    ring = f['geometry']['coordinates'][0]
    r2 = [ring[0]]
    for q in ring[1:]:
        if q != r2[-1]: r2.append(q)
        else: ndup += 1
    assert r2[0] == r2[-1] and len(r2) >= 4
    f['geometry']['coordinates'][0] = r2
    if p.get('kind') != 'seam_patch':
        tag = ('lake' if 'Lake_area' in p['source'] else 'block' if 'Blocks' in p['source'] else 'hydro', p['objectid'] if p['objectid'] is not None else p['geoid'])
        rv = rawv[tag]; ov = set(tuple(q) for q in r2)
        truly = (not ov <= rv) or (len(ov) < len(rv))
        if p['clipped'] != truly: nclipfix += 1
        p['clipped'] = truly
    p['v2_index'] = k
    out.append(f)
meta = dict(src['metadata'])
meta.update({'version': 3, 'audited': '2026-11-11',
             'audit': 'v2 (471 features, interrupted 2026-11-10) audited against the raw responses, landmarks.geojson, the road centrelines and the USFWS National Wetlands Inventory. %d features kept, %d dropped (see _parts/water_overrides_local.v3_dropped.geojson and SOURCES_land.md, 2026-11-11 section). Geometry of kept features is unchanged.' % (len(out), len(drop)),
             'properties_note': 'nwi_check = NWI code(s) at interior point(s) where looked up, else null (not checked); v2_index = position in the interrupted file; clipped = true only if the polygon was really cut on a tile / extent line.'})
json.dump({'type': 'FeatureCollection', 'name': 'water_overrides_local', 'metadata': meta, 'features': out}, open(G + 'water_overrides_local.geojson', 'w'), separators=(',', ':'))
json.dump({'type': 'FeatureCollection', 'name': 'water_overrides_local_v3_dropped', 'metadata': {'what': 'Features removed from water_overrides_local.geojson by the 2026-11-11 audit, with drop_reason. Not used by the validator.'}, 'features': drop}, open(P + 'water_overrides_local.v3_dropped.geojson', 'w'), separators=(',', ':'))
def kind(p):
    return 'seam_patch' if p.get('kind') == 'seam_patch' else 'enc_lake' if 'Lake_area' in p['source'] else 'census_block' if 'Blocks' in p['source'] else 'tiger_hydro'
print('kept', len(out), dict(collections.Counter((kind(f['properties']), f['properties']['zone']) for f in out)))
print('dropped', len(drop), dict(collections.Counter((kind(f['properties']), f['properties']['zone']) for f in drop)))
print('seam patches', dict(seam_stats))
print('vertices kept', sum(len(f['geometry']['coordinates'][0]) for f in out), '| consecutive duplicate vertices removed', ndup, '| clipped flags corrected', nclipfix)
for f in drop:
    p = f['properties']
    if kind(p) != 'seam_patch': print('  DROP', p['v2_index'], kind(p), p['zone'], p['objectid'] or p['geoid'], p['name'], '|', p['drop_reason'])
