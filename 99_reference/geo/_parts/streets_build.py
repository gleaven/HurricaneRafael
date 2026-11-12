#!/usr/bin/env python3
"""Build roads_local_all.geojson from _parts/streets_page_*.json (see streets_ingest.py).
No coordinate is altered: geometry is exactly what TIGERweb returned (outSR=4326,
geometryPrecision=5, maxAllowableOffset=3e-5)."""
import json, glob, os, collections
HERE = os.path.dirname(os.path.abspath(__file__)); GEO = os.path.dirname(HERE)
CLASS = {'S1400': 'local', 'S1640': 'local', 'S1730': 'local', 'S1740': 'local',
         'S1630': 'local',   # ramps: drivable; same convention as roads_local_interchange_ramps.geojson
         'S1780': 'local',   # parking-lot roads: drivable
         'S1500': 'track',   # 4WD vehicular trail
         'S1710': 'walk', 'S1720': 'walk', 'S1820': 'walk', 'S1830': 'walk',
         'S1750': 'other'}   # "internal U.S. Census Bureau use" - not a confirmed public street
idx = {}
for p in sorted(glob.glob(os.path.join(HERE, 'streets_page_*.json'))):
    d = json.load(open(p))
    for i, ft in enumerate(d['features']):
        k = d['offset'] + i
        if k in idx: assert idx[k]['attributes']['OID'] == ft['attributes']['OID'] and idx[k]['geometry'] == ft['geometry'], k
        idx[k] = ft
assert sorted(idx) == list(range(len(idx))), 'gap in server order'
feats = []; seen = set(); cnt = collections.Counter()
for k in range(len(idx)):
    a = idx[k]['attributes']; oid = a['OID']
    assert oid not in seen, oid
    seen.add(oid)
    paths = idx[k]['geometry']['paths']
    for pi, path in enumerate(paths):
        assert len(path) >= 2
        props = {'name': a['NAME'], 'mtfcc': a['MTFCC'], 'class': CLASS[a['MTFCC']], 'source_oid': oid, 'source_layer': 8}
        if len(paths) > 1: props['part'] = pi
        feats.append({'type': 'Feature', 'properties': props, 'geometry': {'type': 'LineString', 'coordinates': path}})
    cnt[(a['MTFCC'], CLASS[a['MTFCC']])] += 1
fc = {'type': 'FeatureCollection', 'name': 'roads_local_all',
      'source': 'US Census TIGERweb Transportation MapServer layer 8 Local Roads (ArcGIS REST), vintage January 1, 2026, fetched 2026-11-10, outSR=4326, geometryPrecision=5, maxAllowableOffset=3e-5 deg',
      'description': 'Every Local Roads (layer 8) feature intersecting lon -97.70..-96.98, lat 27.55..28.08 (features are whole, not clipped). class: local = drivable (S1400/S1630/S1640/S1730/S1740/S1780), track = S1500, walk = S1710, other = S1750.',
      'features': feats}
out = os.path.join(GEO, 'roads_local_all.geojson')
with open(out, 'w') as g:
    g.write('{"type":"FeatureCollection","name":%s,"source":%s,"description":%s,"features":[\n' % tuple(json.dumps(fc[k]) for k in ('name', 'source', 'description')))
    g.write(',\n'.join(json.dumps(f, separators=(',', ':')) for f in feats))
    g.write('\n]}\n')
print('features', len(feats), 'unique OIDs', len(seen), 'bytes', os.path.getsize(out))
for k, v in sorted(cnt.items()): print(k, v)
