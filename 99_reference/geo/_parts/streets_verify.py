#!/usr/bin/env python3
"""Verification of roads_local_all.geojson (TIGERweb layer 8, whole Corpus Christi area).
Run: python3 streets_verify.py   (writes streets_verify_output.txt and streets_check.png next to it)
"""
import json, os, math, collections, sys, glob
HERE = os.path.dirname(os.path.abspath(__file__)); GEO = os.path.dirname(HERE)
KX = 111320 * math.cos(math.radians(27.8)); KY = 110574.0
OUT = []
def P(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.append(s)
def load(fn): return json.load(open(os.path.join(GEO, fn)))['features']
def km(co): return sum(math.hypot((co[i+1][0]-co[i][0])*KX, (co[i+1][1]-co[i][1])*KY) for i in range(len(co)-1)) / 1000.0

new = load('roads_local_all.geojson')
# ---------------------------------------------------------------- 1. basics
P('== 1. roads_local_all.geojson: basics')
lons = [c[0] for f in new for c in f['geometry']['coordinates']]; lats = [c[1] for f in new for c in f['geometry']['coordinates']]
P('features', len(new), '| unique source_oid', len({f['properties']['source_oid'] for f in new}), '| vertices', len(lons), '| km %.1f' % sum(km(f['geometry']['coordinates']) for f in new))
P('geometry types', dict(collections.Counter(f['geometry']['type'] for f in new)), '| min vertices per feature', min(len(f['geometry']['coordinates']) for f in new))
P('lon range %.5f .. %.5f | lat range %.5f .. %.5f  (features are whole, so they may leave the request box -97.70..-96.98 / 27.55..28.08)' % (min(lons), max(lons), min(lats), max(lats)))
inside = sum(1 for x, y in zip(lons, lats) if -97.70 <= x <= -96.98 and 27.55 <= y <= 28.08)
P('vertices inside request box: %d of %d (%.2f%%)' % (inside, len(lons), 100.0 * inside / len(lons)))
P('max decimals in any coordinate:', max(len(repr(v).split('.')[1]) if '.' in repr(v) else 0 for v in lons + lats))
longest = max(max(math.hypot((co[i+1][0]-co[i][0])*KX, (co[i+1][1]-co[i][1])*KY) for i in range(len(co)-1)) for co in (f['geometry']['coordinates'] for f in new))
P('longest single segment: %.0f m' % longest)
bycls = collections.defaultdict(lambda: [0, 0, 0.0])
for f in new:
    k = (f['properties']['class'], f['properties']['mtfcc']); co = f['geometry']['coordinates']
    bycls[k][0] += 1; bycls[k][1] += len(co); bycls[k][2] += km(co)
for k in sorted(bycls): P('  class %-6s mtfcc %s: features %5d vertices %6d km %8.1f' % (k[0], k[1], *bycls[k]))
P('  named features: %d, unnamed (NAME null): %d' % (sum(1 for f in new if f['properties']['name']), sum(1 for f in new if not f['properties']['name'])))

# ---------------------------------------------------------------- 2. page bookkeeping
P('\n== 2. fetch bookkeeping (server order index = resultOffset + position)')
idx = {}; mism = 0; pages = sorted(glob.glob(os.path.join(HERE, 'streets_page_*.json')))
for p in pages:
    d = json.load(open(p))
    for i, ft in enumerate(d['features']):
        k = d['offset'] + i
        if k in idx and idx[k] != ft['attributes']['OID']: mism += 1
        idx[k] = ft['attributes']['OID']
tc = json.load(open(os.path.join(HERE, 'streets_tile_counts.json')))
P('pages', len(pages), '| indices covered', len(idx), 'contiguous 0..%d: %s' % (len(idx) - 1, sorted(idx) == list(range(len(idx)))), '| overlap order mismatches', mism)
P('server returnCountOnly for whole box:', tc['area_count'], '| unique OIDs fetched:', len(set(idx.values())), '| written:', len({f['properties']['source_oid'] for f in new}),
  '=> %s' % ('EQUAL' if tc['area_count'] == len(set(idx.values())) == len({f['properties']['source_oid'] for f in new}) else 'DIFFERENT'))

# ---------------------------------------------------------------- 3. per-tile counts
def seg_hits_box(x0, y0, x1, y1, bx0, by0, bx1, by1):
    # Liang-Barsky: does segment intersect closed rectangle
    dx = x1 - x0; dy = y1 - y0; t0 = 0.0; t1 = 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0:
            if q < 0: return False
        else:
            t = q / p
            if p < 0:
                if t > t1: return False
                if t > t0: t0 = t
            else:
                if t < t0: return False
                if t < t1: t1 = t
    return True
def feat_hits_box(co, b):
    for i in range(len(co) - 1):
        if seg_hits_box(co[i][0], co[i][1], co[i+1][0], co[i+1][1], *b): return True
    return False
P('\n== 3. per-tile counts: features of the written file intersecting each tile vs server returnCountOnly')
P('   (the written geometry is simplified by <=3 m and rounded to 1e-5 deg, so a feature that only touches a tile edge can differ;')
P('    "lo..hi" = local count with the tile shrunk / grown by 6e-5 deg (~6 m); the server count must fall inside)')
LE = tc['lon_edges']; LA = tc['lat_edges']; EPS = 6e-5; ok_exact = 0; ok_band = 0; ntile = 0; rows_txt = []
bb = [(min(c[0] for c in f['geometry']['coordinates']), min(c[1] for c in f['geometry']['coordinates']), max(c[0] for c in f['geometry']['coordinates']), max(c[1] for c in f['geometry']['coordinates'])) for f in new]
tile_rows = []
for j in range(len(LA) - 1):
    for i in range(len(LE) - 1):
        b = (LE[i], LA[j], LE[i+1], LA[j+1]); srv = tc['counts_rows_south_to_north'][j][i]
        n = lo = hi = 0
        for f, fb in zip(new, bb):
            if fb[2] < b[0] - EPS or fb[0] > b[2] + EPS or fb[3] < b[1] - EPS or fb[1] > b[3] + EPS: continue
            co = f['geometry']['coordinates']
            if feat_hits_box(co, b): n += 1
            if feat_hits_box(co, (b[0] + EPS, b[1] + EPS, b[2] - EPS, b[3] - EPS)): lo += 1
            if feat_hits_box(co, (b[0] - EPS, b[1] - EPS, b[2] + EPS, b[3] + EPS)): hi += 1
        ntile += 1; ok_exact += (n == srv); ok_band += (lo <= srv <= hi)
        tile_rows.append((i, j, b, srv, n, lo, hi))
        P('  tile %d_%d  %.2f,%.3f,%.2f,%.3f  server %5d  written %5d  %s  band %d..%d %s' % (i, j, b[0], b[1], b[2], b[3], srv, n, 'EQUAL' if n == srv else 'diff %+d' % (n - srv), lo, hi, 'ok' if lo <= srv <= hi else 'OUTSIDE'))
P('tiles: %d | exactly equal: %d | server count inside the +-6 m band: %d | sum server %d, sum written %d' % (ntile, ok_exact, ok_band, sum(r[3] for r in tile_rows), sum(r[4] for r in tile_rows)))
whole = sum(1 for f in new if feat_hits_box(f['geometry']['coordinates'], tuple(tc['area_box'])))
P('whole box: server %d, written features intersecting the box %d' % (tc['area_count'], whole))
json.dump([{'tile': '%d_%d' % (r[0], r[1]), 'box': r[2], 'server': r[3], 'written': r[4], 'band': [r[5], r[6]]} for r in tile_rows], open(os.path.join(HERE, 'streets_tile_check.json'), 'w'), indent=0)

# ---------------------------------------------------------------- 4. earlier neighbourhood files
def pt_seg_m(px, py, ax, ay, bx, by):
    px, ax, bx = px * KX, ax * KX, bx * KX; py, ay, by = py * KY, ay * KY, by * KY
    dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
def pt_line_m(pt, co): return min(pt_seg_m(pt[0], pt[1], co[i][0], co[i][1], co[i+1][0], co[i+1][1]) for i in range(len(co) - 1))
byoid = collections.defaultdict(list)
for f in new: byoid[f['properties']['source_oid']].append(f['geometry']['coordinates'])
P('\n== 4. earlier files found again in roads_local_all (match on source_oid; geometry = every old vertex within 10 m of the new line and vice versa)')
for fn in sorted(glob.glob(os.path.join(GEO, 'roads_local_*.geojson'))) + [os.path.join(GEO, 'roads_arterial.geojson'), os.path.join(GEO, 'roads_major.geojson')]:
    base = os.path.basename(fn)
    if base == 'roads_local_all.geojson': continue
    old = json.load(open(fn))['features']
    if base == 'roads_major.geojson': old = [f for f in old if f['properties'].get('source_layer') == 8]; base += ' (layer-8 FM routes only)'
    found = geo_ok = 0; worst = 0.0; missing = []; nseg = fseg = 0
    for f in old:
        oid = f['properties']['source_oid']; co = f['geometry']['coordinates']; nseg += len(co) - 1
        if oid not in byoid: missing.append((oid, f['properties']['name'])); continue
        found += 1; fseg += len(co) - 1
        d = max(max(min(pt_line_m(pt, nc) for nc in byoid[oid]) for pt in co), max(pt_line_m(pt, co) for nc in byoid[oid] for pt in nc))
        worst = max(worst, d); geo_ok += (d <= 10.0)
    P('  %-46s features %3d found %3d (%.1f%%) | segments %4d found %4d (%.1f%%) | geometry within 10 m: %d | worst deviation %.1f m%s' % (
        base, len(old), found, 100.0 * found / max(1, len(old)), nseg, fseg, 100.0 * fseg / max(1, nseg), geo_ok, worst, (' | missing: %s' % missing[:6]) if missing else ''))

# ---------------------------------------------------------------- 5. connectivity
P('\n== 5. connectivity of roads_major + roads_arterial + roads_local_all (unique source_oid)')
net = []; seen = set()
for fn in ('roads_major.geojson', 'roads_arterial.geojson', 'roads_local_all.geojson'):
    for f in load(fn):
        o = f['properties']['source_oid']
        if fn != 'roads_local_all.geojson':
            if o in seen: continue
            seen.add(o)
        elif o in seen: continue   # arterial / FM route already taken from the earlier file
        net.append((fn, f['properties']['class'], [(c[0] * KX, c[1] * KY) for c in f['geometry']['coordinates']]))
P('network features', len(net), '| km %.1f' % (sum(sum(math.hypot(c[i+1][0]-c[i][0], c[i+1][1]-c[i][1]) for i in range(len(c)-1)) for _, _, c in net) / 1000))
CELL = 100.0
def run(feats, tol, crossings):
    n = len(feats); par = list(range(n))
    def find(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    segs = []; grid = collections.defaultdict(set); segcells = []
    for fi, (_, _, c) in enumerate(feats):
        for i in range(len(c) - 1):
            ax, ay = c[i]; bx, by = c[i+1]; L = math.hypot(bx - ax, by - ay); k = max(1, int(math.ceil(L / (CELL / 2))))
            si = len(segs); segs.append((fi, ax, ay, bx, by)); cs = set()
            for t in range(k + 1):
                cs.add((int(math.floor((ax + (bx - ax) * t / k) / CELL)), int(math.floor((ay + (by - ay) * t / k) / CELL))))
            for cc in cs: grid[cc].add(si)
            segcells.append(cs)
    def d_pt_seg(px, py, ax, ay, bx, by):
        dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
        return math.hypot(px - ax - t * dx, py - ay - t * dy)
    # (a) snap every endpoint to any other feature's line within tol
    for fi, (_, _, c) in enumerate(feats):
        for (px, py) in (c[0], c[-1]):
            cx, cy = int(math.floor(px / CELL)), int(math.floor(py / CELL))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for si in grid.get((cx + dx, cy + dy), ()):
                        fj, ax, ay, bx, by = segs[si]
                        if fj == fi: continue
                        ra, rb = find(fi), find(fj)
                        if ra == rb: continue
                        if d_pt_seg(px, py, ax, ay, bx, by) <= tol: par[ra] = rb
    # (b) proper crossings at interior points (TIGER features are whole roads; cross streets meet at non-vertex points)
    if crossings:
        def ccw(ax, ay, bx, by, cx, cy): return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        for si, (fi, ax, ay, bx, by) in enumerate(segs):
            cand = set()
            for (cx, cy) in segcells[si]:
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        cand |= grid.get((cx + dx, cy + dy), set())
            for sj in cand:
                if sj <= si: continue
                fj, px, py, qx, qy = segs[sj]
                if fj == fi: continue
                ra, rb = find(fi), find(fj)
                if ra == rb: continue
                d1 = ccw(px, py, qx, qy, ax, ay); d2 = ccw(px, py, qx, qy, bx, by); d3 = ccw(ax, ay, bx, by, px, py); d4 = ccw(ax, ay, bx, by, qx, qy)
                if (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0): par[ra] = rb
    comp = collections.defaultdict(lambda: [0, 0.0])
    for fi, (_, _, c) in enumerate(feats):
        r = find(fi); comp[r][0] += 1; comp[r][1] += sum(math.hypot(c[i+1][0]-c[i][0], c[i+1][1]-c[i][1]) for i in range(len(c)-1))
    tot = sum(v[1] for v in comp.values()); big = sorted(comp.values(), key=lambda v: -v[1])
    return len(comp), big, tot, [find(i) for i in range(n)]
drivable = [x for x in net if x[1] not in ('walk', 'track', 'other')]
results = {}
for label, feats in (('all classes', net), ('drivable only (walk/track/other removed)', drivable)):
    for tol, cr, how in ((12.0, False, 'endpoints snapped to lines within 12 m'), (12.0, True, 'endpoints snapped within 12 m + geometric crossings noded')):
        nc, big, tot, lab = run(feats, tol, cr)
        results[(label, cr)] = (feats, lab)
        P('  %-42s | %-58s | components %5d | largest %.2f%% of length (%.1f of %.1f km, %d features) | 2nd %.1f km, 3rd %.1f km | features outside largest: %d (%.1f km)' % (
            label, how, nc, 100.0 * big[0][1] / tot, big[0][1] / 1000, tot / 1000, big[0][0], big[1][1] / 1000 if len(big) > 1 else 0, big[2][1] / 1000 if len(big) > 2 else 0, len(feats) - big[0][0], (tot - big[0][1]) / 1000))

# ---------------------------------------------------------------- 6. plot
try:
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    fig, ax = plt.subplots(figsize=(17, 14), dpi=110)
    def lc(feats, **kw): ax.add_collection(LineCollection([f['geometry']['coordinates'] for f in feats], **kw))
    lc([f for f in new if f['properties']['class'] == 'local'], colors='#3b6fb6', linewidths=0.35)
    lc([f for f in new if f['properties']['class'] != 'local'], colors='#2ca02c', linewidths=0.8)
    lc(load('roads_arterial.geojson'), colors='#ff8c00', linewidths=0.8)
    lc(load('roads_major.geojson'), colors='#d62728', linewidths=1.1)
    feats, lab = results[('all classes', True)]
    cnt = collections.Counter(lab); main = cnt.most_common(1)[0][0]
    iso = [[(x / KX, y / KY) for x, y in c] for (fn, cl, c), l in zip(feats, lab) if l != main]
    ax.add_collection(LineCollection(iso, colors='#e000e0', linewidths=1.0))
    for v in tc['lon_edges']: ax.axvline(v, color='k', lw=0.3, alpha=0.4)
    for v in tc['lat_edges']: ax.axhline(v, color='k', lw=0.3, alpha=0.4)
    for nm, x, y in (('Corpus Christi', -97.40, 27.80), ('Flour Bluff', -97.30, 27.665), ('Padre Island', -97.215, 27.60), ('Calallen', -97.63, 27.875), ('Robstown', -97.668, 27.79), ('Portland', -97.325, 27.885),
                     ('Gregory', -97.29, 27.925), ('Ingleside', -97.21, 27.875), ('Aransas Pass', -97.15, 27.91), ('Port Aransas', -97.065, 27.835), ('Rockport', -97.055, 28.02), ('Fulton', -97.035, 28.065)):
        ax.text(x, y, nm, fontsize=9, weight='bold', ha='center', bbox=dict(fc='white', ec='none', alpha=0.6, pad=1))
    ax.set_xlim(-97.72, -96.96); ax.set_ylim(27.54, 28.09); ax.set_aspect(1 / math.cos(math.radians(27.8)))
    ax.set_title('roads_local_all.geojson (blue = local streets, green = walk/track/other) + arterial (orange) + major (red); magenta = not in largest connected component; grid = count tiles', fontsize=10)
    fig.tight_layout(); fig.savefig(os.path.join(HERE, 'streets_check.png')); P('\nplot written: _parts/streets_check.png')
except Exception as e:
    P('plot failed:', e)
open(os.path.join(HERE, 'streets_verify_output.txt'), 'w').write('\n'.join(OUT) + '\n')
