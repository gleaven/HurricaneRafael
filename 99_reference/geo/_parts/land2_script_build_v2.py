"""Build land_local.geojson v2 + water_overrides_local.geojson v2 (2026-11-10). No coordinate is invented:
vertices are fetched vertices; the only computed ones are cut-line intersections on the 0.075-deg tile grid / extent box."""
import sys,hashlib
from lib import *
from build_local_lib import clip_ring
from kh import keyhole
T=tiles()
XMIN,YMIN,XMAX,YMAX=BOX
Y_RECTS=[r for r in T['coastal_fill_rects'] if tuple(r) in {(-97.65,27.9,-97.2,27.975),(-97.65,27.975,-97.125,28.05),(-97.65,28.05,-97.05,28.125)}]
if '--noY' in sys.argv: Y_RECTS=[]
X_RECTS=[r for r in T['coastal_fill_rects'] if r not in Y_RECTS]
g=Grid(10.0)
def rect_ring(r): return [[r[0],r[1]],[r[2],r[1]],[r[2],r[3]],[r[0],r[3]],[r[0],r[1]]]
v1=json.load(open(P+'land_local.v1.geojson'))
w1=json.load(open(P+'water_overrides_local.v1.geojson'))
# ---------------- land v2
feats=[]; H=g.zeros(); L=g.zeros()
for f in v1['features']:
    pr=f['properties']
    if pr['band']=='harbour':
        feats.append(f)
        for p in gj_polys(f['geometry']): g.fill(H,p); g.fill(L,p)
    elif pr['clip_rect'] not in Y_RECTS:
        feats.append(f)
        for p in gj_polys(f['geometry']): g.fill(L,p)
nrep=sum(1 for f in v1['features'] if f['properties']['band']=='coastal' and f['properties']['clip_rect'] in Y_RECTS)
for r in Y_RECTS:
    feats.append({'type':'Feature','properties':{'name':None,'source':'cut-line rectangle (0.075-deg ENC tile grid / extent box); shoreline inside it is defined by the US Census TIGERweb water polygons in water_overrides_local.geojson (land = rectangle minus overrides)','band':'tiger_complement','enc_cell':None,'objectid':None,'tolerance_deg':0.0001,'clipped':True,'clip_rect':list(r)},'geometry':{'type':'Polygon','coordinates':[rect_ring(r)]}})
    g.fill(L,[rect_ring(r)])
HT=g.zeros()
dHw=cv2.distanceTransform(H,cv2.DIST_L2,5)*g.res
for c,r in T['harbour_cells'].items(): g.fill(HT,[rect_ring(r)])
# ---------------- water candidates
cells=[('tile',c,tuple(r)) for c,r in T['harbour_cells'].items()]+[('Y',None,tuple(r)) for r in Y_RECTS]+[('X',None,tuple(r)) for r in X_RECTS]
MT={'H2030':'lake/pond','H2051':'bay/estuary/gulf/sound','H3010':'stream/river','H3020':'canal/ditch','H2040':'reservoir','H2053':'ocean/sea','H3013':'braided stream'}
cands=[]
tg=esri_feats('land2_raw_tiger_h*.txt')
order=sorted(tg.items(),key=lambda kv:(kv[1][0]['NAME'] is None,kv[0]))
for oid,(a,rings,src) in order:
    cands.append({'kind':'hydro','id':oid,'name':a['NAME'],'mtfcc':a['MTFCC'],'rings':rings,'file':src})
wb={}
for fpath in sorted(glob.glob(P+'land2_raw_wb_*.txt')):
    u,fs,t,_=load(fpath)
    for x in fs: wb.setdefault(x['attributes']['GEOID'],(x,os.path.basename(fpath)))
for k,(x,src) in sorted(wb.items()):
    cands.append({'kind':'block','id':k,'name':None,'mtfcc':None,'rings':x['geometry']['rings'],'file':src})
# Gulf mask (TIGER 'Gulf of America' polygons): never used as override (beach line disagrees with the harbour chart, see SOURCES)
Gf=g.zeros()
for c in cands:
    if c['name']=='Gulf of America': g.fill(Gf,c['rings'])
def split(rings):
    ext=[r for r in rings if sarea(r)<0]; holes=[r for r in rings if sarea(r)>0]   # esri: exterior clockwise
    return ext,holes
def crop_mask(rings):
    xs=[p[0] for r in rings for p in r]; ys=[p[1] for r in rings for p in r]
    a=g.px([[min(xs),max(ys)],[max(xs),min(ys)]])
    x0=max(a[0,0]-1,0); y0=max(a[0,1]-1,0); x1=min(a[1,0]+2,g.nx); y1=min(a[1,1]+2,g.ny)
    if x1<=x0 or y1<=y0: return None
    m=np.zeros((y1-y0,x1-x0),np.uint8)
    cv2.fillPoly(m,[g.px(r)-np.array([x0,y0],np.int32) for r in rings],1)
    return (slice(y0,y1),slice(x0,x1)),m
M=g.zeros()      # water already added by accepted overrides
out=[]; stats={'tile':[0,0.0],'X':[0,0.0],'Y':[0,0.0]}; dropped={'gulf':0,'tile_straddle':0,'no_gain':0}; nkey=0; tile_list=[]
MINGAIN=3   # cells of 100 m2
def add_piece(c,kind,cellid,rect,rings_ext,rings_holes,reason_forced=None):
    global nkey
    rings=rings_ext+rings_holes
    cm=crop_mask(rings)
    if cm is None: return
    sl,m=cm; area=int(m.sum())
    if area==0: return
    gain=int(((m==1)&(L[sl]==1)&(M[sl]==0)).sum())
    if reason_forced is None:
        if c['name']=='Gulf of America' or (c['kind']=='block' and ((m==1)&(Gf[sl]==1)).sum()>0.5*area):
            dropped['gulf']+=1; return
        if gain<MINGAIN: dropped['no_gain']+=1; return
        if kind=='tile':
            onland=int(((m==1)&(H[sl]==1)).sum())
            if onland<0.85*area: dropped['tile_straddle']+=1; return
            near=int(((m==1)&(H[sl]==1)&(dHw[sl]<=30)).sum())
            if near>0.2*onland: dropped['tile_shore_adjacent']=dropped.get('tile_shore_adjacent',0)+1; return
            if not (c['kind']=='hydro' and c['mtfcc'] in ('H2030','H3010','H3020')): dropped['tile_bay_or_block']=dropped.get('tile_bay_or_block',0)+1; return
    # geometry: one keyholed ring per exterior
    polys=[]
    from build_local_lib import pip_ring
    exts=[e if sarea(e)>0 else e[::-1] for e in rings_ext]     # CCW
    hl=[[] for _ in exts]
    for h in rings_holes:
        k=0
        for i,e in enumerate(exts):
            if pip_ring(h[0][0],h[0][1],e) or pip_ring(h[1][0],h[1][1],e): k=i; break
        hl[k].append(h)
    for e,hs in zip(exts,hl):
        if hs:
            try: ring=keyhole(e,hs); nkey+=len(hs)
            except RuntimeError: ring=None
            if ring is None: polys.append([e]+[h if sarea(h)<0 else h[::-1] for h in hs]); print('WARN keyhole failed, holes kept',c['id'])
            else: polys.append([ring])
        else: polys.append([[list(p) for p in e]])
    geom={'type':'Polygon','coordinates':polys[0]} if len(polys)==1 else {'type':'MultiPolygon','coordinates':polys}
    if c['kind']=='enclake':
        src='NOAA ENC Direct enc_harbour/MapServer/232 Harbor.Lake_area (S-57 LAKARE), cell '+c['cellname']
    elif c['kind']=='hydro':
        src='US Census TIGERweb Hydro/MapServer/1 Areal Hydrography (MTFCC %s %s), vintage 2026-01-01'%(c['mtfcc'],MT.get(c['mtfcc'],''))
    else:
        src='US Census TIGERweb Tracts_Blocks/MapServer/2 Census Blocks 2020, water-only block (AREALAND=0) GEOID '+c['id']
    if reason_forced: reason=reason_forced
    elif kind=='tile': reason='inland lake/pond/stream (TIGER H2030/H3010/H3020) enclosed by the NOAA harbour-band chart land area: >=85%% of it lies on charted land and <=20%% of that within 30 m of charted water, so no charted shoreline moves (adds %.4f km2 of water)'%(gain/1e4)
    elif kind=='X': reason='water that the NOAA coastal-band (1:150k+) land polygon covers: shoreline strip, creek, lake, pond or tidal flat (adds %.4f km2 of water)'%(gain/1e4)
    else: reason='defines water inside a tiger_complement land rectangle (shoreline from Census TIGER, replaces the coastal-band chart there)'
    out.append({'type':'Feature','properties':{'name':c['name'],'source':src,'objectid':c['id'] if c['kind'] in('hydro','enclake') else None,'geoid':c['id'] if c['kind']=='block' else None,'mtfcc':c['mtfcc'],'tolerance_deg':(0.0 if c['kind']=='enclake' else 0.0001),'zone':{'tile':'harbour_tile','X':'coastal_band','Y':'tiger_complement'}[kind],'cell':cellid,'clip_rect':list(rect),'clipped':True,'holes_keyholed':sum(len(h) for h in hl),'reason':reason,'raw_file':c['file']},'geometry':geom})
    M[sl]|=m
    stats[kind][0]+=1; stats[kind][1]+=gain/1e4
    if kind=='tile': tile_list.append((gain/1e4,c['name'],c['id'],cellid))
# v1 Oso Bay first (same three TIGER polygons, forced, clipped per cell like the rest)
oso_ids=[f['properties']['objectid'] for f in w1['features']]
def process(c,forced=None):
    ext,holes=split(c['rings'])
    xs=[p[0] for r in c['rings'] for p in r]; ys=[p[1] for r in c['rings'] for p in r]
    bb=(min(xs),min(ys),max(xs),max(ys))
    for kind,cid,rc in cells:
        if bb[2]<=rc[0] or bb[0]>=rc[2] or bb[3]<=rc[1] or bb[1]>=rc[3]: continue
        inside=bb[0]>=rc[0] and bb[2]<=rc[2] and bb[1]>=rc[1] and bb[3]<=rc[3]
        if inside: e2,h2=ext,holes
        else:
            e2=[x for x in (clip_ring(r,rc) for r in ext) if x]; h2=[x for x in (clip_ring(r,rc) for r in holes) if x]
        if not e2: continue
        add_piece(c,kind,cid,rc,e2,h2,forced)
lk=esri_feats('land2_raw_enc_lake_*.txt')
for oid,(a,rings,src) in sorted(lk.items()):
    process({'kind':'enclake','id':oid,'name':a['OBJNAM'],'mtfcc':None,'rings':rings,'file':src,'cellname':a['DSNM'][:8]},'charted lake (S-57 LAKARE) lying on the harbour-band land area: the chart itself shows water here')
nlake=len(out); LK=M.copy()
for c in cands:
    if c['kind']=='hydro' and c['id'] in oso_ids:
        process(c,'Oso Bay: a real bay that the NOAA coastal-band chart draws as land (v1 override, kept)')
for c in cands:
    if c['kind']=='hydro' and c['id'] in oso_ids: continue
    process(c)
print('ENC lake pieces',nlake); print('override pieces',len(out),'by zone',stats,'dropped',dropped,'holes keyholed',nkey)
tile_list.sort(key=lambda t:-t[0]); print('largest harbour-tile inland pieces:',[(round(a,3),n,i,c) for a,n,i,c in tile_list[:25]])
print('harbour-tile pieces total',len(tile_list),'km2 %.2f'%sum(a for a,_,_,_ in tile_list))
def nverts(fs):
    n=0
    for f in fs:
        for p in gj_polys(f['geometry']): n+=sum(len(r) for r in p)
    return n
fc={'type':'FeatureCollection','name':'land_local',
 'metadata':{'what':'Land polygons around Corpus Christi TX. Validator rule (unchanged): WATER if inside any water_overrides_local.geojson polygon; else LAND if inside any feature here; else WATER. See SOURCES_land.md (2026-11-10 section).',
  'valid_extent_lonlat':[XMIN,YMIN,XMAX,YMAX],'datum':'WGS84 (EPSG:4326)','fetched':'2026-11-09 (harbour, coastal); 2026-11-10 (v2 upgrade)','version':2,
  'bands':'harbour = NOAA band-5 ENC LNDARE in 27 tiles (unchanged from v1, byte-identical features); coastal = NOAA band-3 ENC LNDARE clipped to rectangles outside the tiles (unchanged where kept; shoreline corrected by Census TIGER water overrides); tiger_complement = whole cut-line rectangles north of 27.9N (Copano/Port/Mission Bay area) where land is the rectangle minus the Census TIGER water polygons in water_overrides_local.geojson.',
  'note':'Straight edges on 0.075-deg tile lines and on the extent box are cut lines, not shoreline. NEVER use this file without water_overrides_local.geojson.'},
 'features':feats}
json.dump(fc,open(G+'land_local.geojson','w'),separators=(',',':'))
wc={'type':'FeatureCollection','name':'water_overrides_local','metadata':{'what':'Water polygons that take precedence over land_local.geojson. Validator rule (unchanged): WATER if inside any feature here; else LAND if inside any land_local.geojson feature; else WATER.',
 'datum':'WGS84 (server-projected from NAD83)','fetched':'2026-11-10','version':2,
 'zones':'coastal_band = corrects the coastal-band chart polygon (creeks, lakes, ponds, tidal flats, shoreline strips); tiger_complement = defines all water inside the tiger_complement land rectangles; harbour_tile = inland water bodies only (>=85% on charted land) - charted shorelines are never moved.',
 'geometry_note':'Every polygon is a single ring without interior rings: islands are cut out through zero-width bridges between two existing vertices (keyhole), so that raster fills and even-odd tests agree. Straight edges on the 0.075-deg grid / extent box are cut lines.'},'features':out}
json.dump(wc,open(G+'water_overrides_local.geojson','w'),separators=(',',':'))
hh=hashlib.sha256(json.dumps([f for f in feats if f['properties']['band']=='harbour'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
h1=hashlib.sha256(json.dumps([f for f in v1['features'] if f['properties']['band']=='harbour'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
print('harbour features sha256 v1',h1[:16],'v2',hh[:16],'identical',h1==hh)
print('land v1: feats',len(v1['features']),'verts',nverts(v1['features']),'| v2: feats',len(feats),'verts',nverts(feats),'| coastal pieces replaced',nrep,'by',len(Y_RECTS),'rects')
print('overrides v1: feats',len(w1['features']),'verts',nverts(w1['features']),'| v2: feats',len(out),'verts',nverts(out))
print('bytes',os.path.getsize(G+'land_local.geojson'),os.path.getsize(G+'water_overrides_local.geojson'))
np.savez_compressed('v2masks.npz',L=L,M=M,H=H,HT=HT,LK=LK)
