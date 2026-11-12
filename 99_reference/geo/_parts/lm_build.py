#!/usr/bin/env python3
import json, re, math, os, collections, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest
GEO = './99_reference/geo/'
PARTS = GEO + '_parts/'
BOX = (-97.75, 27.55, -96.90, 28.10)
def inbox(lon, lat): return BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]
def nn(v):
    if v is None: return None
    v = str(v).strip()
    return None if v in ('', 'Null', 'null', 'None') else v
def addr(*parts):
    p = [nn(x) for x in parts]; p = [x for x in p if x]
    return ', '.join(p) if p else None
idx = harvest.index()
def files(sub, sub2=''):
    for f, first, txt in idx:
        if sub in first and sub2 in first:
            fe, comp, d = harvest.features(txt)
            yield first, fe
parts = collections.OrderedDict()
def P(tag): return parts.setdefault(tag, [])
def rec(name, cat, lon, lat, source, sid, note, address=None, **extra):
    d = dict(name=name, category=cat, address=address, lon=round(float(lon), 6), lat=round(float(lat), 6), source=source, source_id=sid, accuracy_note=note)
    d.update(extra); return d

# ---- A. USGS structures
SRC_ST = 'USGS National Structures Dataset (carto.nationalmap.gov structures MapServer, layer %s)'
seen = set()
def add_struct(layer, lname, a, g):
    a = {k.lower(): v for k, v in a.items()}
    pid = nn(a.get('permanent_identifier')) or str(a.get('objectid'))
    if (layer, pid) in seen: return
    lon, lat = g['x'], g['y']
    if not inbox(lon, lat): return
    seen.add((layer, pid))
    name = nn(a.get('name')) or '(unnamed)'
    ad = addr(a.get('address'), a.get('city'), a.get('state'), a.get('zipcode'))
    if layer == 49: cat, note, tag = 'hospital', 'hospital / medical center structure point (USGS TNM, same lineage as HIFLD)', 'lm_usgs_hospitals'
    elif layer == 50: cat, note, tag = 'ems', 'ambulance service structure point (USGS TNM)', 'lm_usgs_ems'
    elif layer == 51:
        nm = name.lower()
        isems = ('ems' in re.split(r'\W+', nm) or 'ambulance' in nm or 'emergency medical' in nm) and 'fire' not in nm
        cat = 'ems' if isems else 'fire_station'
        note, tag = 'fire station / EMS station structure point (USGS TNM)', 'lm_usgs_fire_ems'
    elif layer == 53: cat, note, tag = 'police', 'law enforcement structure point (USGS TNM)', 'lm_usgs_police'
    elif layer == 39: cat, note, tag = 'venue', 'city/town hall structure point (USGS TNM); government building, not verified as EOC', 'lm_usgs_cityhalls'
    elif layer == 58: cat, note, tag = 'school', 'school structure point (USGS TNM); source does not say which schools are designated shelters', 'lm_usgs_schools'
    else: return
    P(tag).append(rec(name, cat, lon, lat, SRC_ST % ('%d %s' % (layer, lname)), 'permanent_identifier ' + pid + (('; GNIS ' + nn(a.get('gnis_id'))) if nn(a.get('gnis_id')) else ''), note, ad))
for first, fe in files('structures/MapServer/identify'):
    for r in fe: add_struct(r['layerId'], r['layerName'], r['attributes'], r['geometry'])
for first, fe in files('structures/MapServer/51/query', 'outFields'):
    for r in fe: add_struct(51, 'Fire Stations/EMS Stations', r['attributes'], r['geometry'])
for first, fe in files('structures/MapServer/58/query', 'outFields'):
    for r in fe: add_struct(58, 'Schools', r['attributes'], r['geometry'])

# ---- B. GNIS populated places
seen_g = set()
for first, fe in files('geonames/MapServer/3/query', 'outFields'):
    for r in fe:
        a = r['attributes']; gid = a['gaz_id']
        if gid in seen_g: continue
        seen_g.add(gid)
        lon, lat = r['geometry']['points'][0]
        if not inbox(lon, lat): continue
        P('lm_gnis_places').append(rec(a['gaz_name'], 'community', lon, lat, 'USGS GNIS (carto.nationalmap.gov geonames MapServer, layer 3 Populated Places)', 'GNIS feature id %s' % gid, 'GNIS populated-place point (%s County)' % a.get('county_name')))

# ---- C. airports / helipads
KEEP_OUT = {'NQI'}
av = {}
for first, fe in files('NTAD_Aviation_Facilities', 'outFields=*&f=json&order'):
    for r in fe: av[r['attributes']['OBJECTID']] = r
arp = {}
for r in av.values():
    a, g = r['attributes'], r['geometry']
    lon, lat = g['x'], g['y']
    ib = inbox(lon, lat)
    if not ib and a['ARPT_ID'] not in KEEP_OUT: continue
    arp[a['ARPT_ID']] = (lon, lat, a['ARPT_NAME'])
    cat = 'helipad' if a['SITE_TYPE_CODE'] == 'H' else 'airport'
    ident = a['ARPT_ID'] + ('/' + a['ICAO_ID'] if nn(a.get('ICAO_ID')) else '')
    name = '%s (%s)' % (a['ARPT_NAME'].title(), ident)
    note = ('heliport reference point' if cat == 'helipad' else 'airport reference point') + ' from FAA NASR via NTAD (ownership %s, use %s)' % (a['OWNERSHIP_TYPE_CODE'], a['FACILITY_USE_CODE'])
    extra = {} if ib else {'out_of_box': True}
    if not ib: note += '; outside box on purpose'
    P('lm_faa_airports').append(rec(name, cat, lon, lat, 'USDOT NTAD Aviation Facilities (FAA NASR, eff. %s)' % a['EFF_DATE'], 'FAA site %s; LID %s' % (a['SITE_NO'], a['ARPT_ID']), note, addr(a['CITY'].title(), a['STATE_CODE']), **extra))
# ---- D. runway ends
rw = {}
for first, fe in files('Runways_View', 'outFields'):
    for r in fe: rw[r['attributes']['OBJECTID']] = r
for r in rw.values():
    a = r['attributes']
    if a['ARPT_ID'] not in arp: continue
    for n, (la, lo) in enumerate([(a['LAT1_DECIMAL'], a['LONG1_DECIMAL']), (a['LAT2_DECIMAL'], a['LONG2_DECIMAL'])], 1):
        if la is None or lo is None: continue
        ib = inbox(lo, la); extra = {} if ib else {'out_of_box': True}
        P('lm_faa_runway_ends').append(rec('%s (%s) runway %s end %d' % (a['ARPT_NAME'].title(), a['ARPT_ID'], a['RWY_ID'], n), 'runway_end', lo, la,
            'USDOT NTAD Runways (FAA NASR, eff. %s)' % a['EFF_DATE'], 'FAA site %s; RWY_ID %s; LAT%d/LONG%d_DECIMAL' % (a['SITE_NO'], a['RWY_ID'], n, n),
            'runway end coordinate (attribute LAT%d/LONG%d); %s ft x %s ft %s; which designator is end %d is not stated by the layer' % (n, n, a['RWY_LEN'], a['RWY_WIDTH'], a['SURFACE_TYPE_CODE'], n), **extra))

# ---- E. military (derived centroids)
def ring_centroid(ring):
    A = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        c = x1 * y2 - x2 * y1; A += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c
    A *= 0.5
    if abs(A) < 1e-12: return None
    return cx / (6 * A), cy / (6 * A), abs(A)
def dist_m(lo1, la1, lo2, la2):
    k = 111320.0; return math.hypot((lo1 - lo2) * k * math.cos(math.radians((la1 + la2) / 2)), (la1 - la2) * 110540.0)
for first, fe in files('NTAD_Military_Bases', 'f=pjson'):
    rings = fe[0]['geometry']['rings']
    cs = sorted([c + (i,) for i, c in ((i, ring_centroid(r)) for i, r in enumerate(rings)) if c], key=lambda t: -t[2])
    for cx, cy, A, i in cs[:3]:
        near = min(arp.items(), key=lambda kv: dist_m(cx, cy, kv[1][0], kv[1][1]))
        dm = dist_m(cx, cy, near[1][0], near[1][1])
        P('lm_military').append(rec('Naval Air Station Corpus Christi - installation parcel nearest %s (%s)' % (near[1][2].title(), near[0]), 'military', cx, cy,
            'USDOT NTAD Military Bases (DoD MIRTA) polygon OBJECTID 483', 'siteName "Naval Air Station Corpus Christi"; polygon ring %d of %d' % (i, len(rings)),
            'DERIVED: area centroid computed from the published boundary ring (%.2f km2); %.0f m from the FAA reference point of %s' % (A * 111.32 * 110.54 * math.cos(math.radians(cy)), dm, near[0])))

# ---- F. USACE docks
dk = {}
for first, fe in files('Docks/FeatureServer', 'outFields'):
    for r in fe: dk[r['attributes']['OBJECTID']] = r
skip = collections.Counter()
for k, r in sorted(dk.items()):
    a, g = r['attributes'], r['geometry']
    ft = a['FAC_TYPE']; nm = nn(a['NAV_UNIT_NAME']) or '(unnamed)'; U = nm.upper()
    if ft in ('Milepoint', 'Fleeting Area', 'Open Water', 'Junction', 'Anchorage'): skip[ft] += 1; continue
    if ft is None and not re.search(r'DOCK|WHARF|TERMINAL|PIER|SLIP|MOORING|HARBOR', U): skip['null-type non-facility'] += 1; continue
    lon, lat = g['x'], g['y']
    if not inbox(lon, lat): continue
    if 'FERRY' in U: cat = 'ferry'
    elif 'COAST GUARD' in U or 'USCG' in U: cat = 'coast_guard'
    elif 'PILOT' in U: cat = 'port_dock'
    elif ft == 'Marina' or re.search(r'MARINA|YACHT|BOAT BASIN|HARBOR (INNER|OUTER) MOORING|HARBOR MOORINGS', U): cat = 'marina'
    else: cat = 'port_dock'
    note = 'USACE dock/facility point (FAC_TYPE %s; %s)' % (ft, a.get('PORT_NAME') or a.get('WTWY_NAME'))
    if 'PILOT' in U: note += '; pilot station'
    if nn(a.get('OWNERS')): note += '; owner: ' + nn(a['OWNERS'])[:80]
    P('lm_usace_docks').append(rec(nm, cat, lon, lat, 'USACE Master Docks Plus (services7.arcgis.com/n1YM8pTrFmm7L4hs Docks FeatureServer/0)', 'LOC_DOCK %s; NAV_UNIT_ID %s' % (a.get('LOC_DOCK'), a.get('NAV_UNIT_ID')), note, addr(a.get('STREET_ADDRESS'), a.get('CITY_OR_TOWN'), a.get('STATE'), a.get('ZIPCODE'))))
print('docks skipped', dict(skip))

# write generated parts
for tag, lst in parts.items():
    json.dump(lst, open(PARTS + tag + '.json', 'w'), indent=1, ensure_ascii=False)
# ---- merge all lm_*.json parts
allr = []
for fn in sorted(os.listdir(PARTS)):
    if fn.startswith('lm_') and fn.endswith('.json'):
        lst = json.load(open(PARTS + fn, encoding='utf-8'))
        for d in lst: d['_part'] = fn
        allr += lst
        print('%-28s %d' % (fn, len(lst)))
# exact duplicate removal (same name+category within 50 m)
out = []
for d in allr:
    if any(o['name'] == d['name'] and o['category'] == d['category'] and dist_m(o['lon'], o['lat'], d['lon'], d['lat']) < 50 for o in out): continue
    out.append(d)
print('merged', len(allr), '-> after exact-dup removal', len(out))
# box check
bad = [d for d in out if not inbox(d['lon'], d['lat']) and not d.get('out_of_box')]
print('unflagged out-of-box:', [(d['name'], d['lon'], d['lat']) for d in bad])
out = [d for d in out if d not in bad]
# near-duplicate flags
nd = 0
for i, d in enumerate(out):
    near = [o['name'] for j, o in enumerate(out) if j != i and abs(o['lat'] - d['lat']) < 0.001 and dist_m(o['lon'], o['lat'], d['lon'], d['lat']) < 50]
    if near: d['within_50m_of'] = near[:5]; nd += 1
feats = []
for d in out:
    props = {k: d.get(k) for k in ('name', 'category', 'address', 'source', 'source_id', 'accuracy_note')}
    props['in_box'] = inbox(d['lon'], d['lat'])
    if d.get('within_50m_of'): props['within_50m_of'] = d['within_50m_of']
    feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [d['lon'], d['lat']]}, 'properties': props})
fc = {'type': 'FeatureCollection', 'name': 'landmarks', 'description': 'Real landmark/facility points, Corpus Christi TX area. Every coordinate fetched from the source named per feature on 2026-11-09; see SOURCES_landmarks.md. WGS84 lon/lat.', 'bbox_of_interest': list(BOX), 'features': feats}
json.dump(fc, open(GEO + 'landmarks.geojson', 'w'), indent=1, ensure_ascii=False)
cnt = collections.Counter(f['properties']['category'] for f in feats)
print('TOTAL', len(feats), 'near-dup flagged', nd, 'out_of_box flagged', sum(1 for f in feats if not f['properties']['in_box']))
for k, v in sorted(cnt.items()): print('  %-16s %d' % (k, v))
json.dump({'counts': dict(cnt), 'total': len(feats), 'near_dup_flagged': nd}, open('./_scratch/work/lm/summary.json', 'w'))
