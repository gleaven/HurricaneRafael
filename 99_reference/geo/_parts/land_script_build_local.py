import sys,glob,json,os
sys.path.insert(0,'./_scratch/work/geo')
from parsefetch import load
G='./99_reference/geo/'
P=G+'_parts/'
# harbour-band ENC cell rectangles (M_COVR, enc_harbour layer 219 query, 2026-11-09). 0.075 deg grid.
CELLS={'US5CRPBE':(-97.275,27.75),'US5CRPBF':(-97.2,27.75),'US5TX2CF':(-96.975,28.05),'US5TX2AC':(-97.2,27.9),
'US5TX2BD':(-97.125,27.975),'US5TX2BE':(-97.05,27.975),'US5CRPBC':(-97.425,27.75),'US5CRPBH':(-97.05,27.75),
'US5TX1TE':(-97.275,27.525),'US5CRPCB':(-97.5,27.825),'US5CRPBD':(-97.35,27.75),'US5CRPCG':(-97.125,27.825),
'US5CRPCC':(-97.425,27.825),'US5CRPBI':(-96.975,27.75),'US5TX1UE':(-97.275,27.6),'US5CRPCA':(-97.575,27.825),
'US5CRPBB':(-97.5,27.75),'US5CRPCD':(-97.35,27.825),'US5CRPCE':(-97.275,27.825),'US5CRPCF':(-97.2,27.825),
'US5TX2AE':(-97.05,27.9),'US5CRPBG':(-97.125,27.75),'US5TX2AD':(-97.125,27.9),'US5TX2CE':(-97.05,28.05),
'US5TX1TD':(-97.35,27.525),'US5TX1VE':(-97.275,27.675),'US5CRPCH':(-97.05,27.825)}
S=0.075
def cellrect(c):
    x,y=CELLS[c]; return (x,y,round(x+S,3),round(y+S,3))
XMIN,XMAX,YMIN,YMAX=-97.65,-96.85,27.525,28.125

def sarea(r):
    return 0.5*sum(r[i][0]*r[i+1][1]-r[i+1][0]*r[i][1] for i in range(len(r)-1))
def clip_ring(ring,rect):
    x0,y0,x1,y1=rect
    pts=ring[:-1] if ring[0]==ring[-1] else ring[:]
    def clip(pts,inside,inter):
        out=[]
        n=len(pts)
        for i in range(n):
            a=pts[i-1]; b=pts[i]
            ia,ib=inside(a),inside(b)
            if ib:
                if not ia: out.append(inter(a,b))
                out.append(b)
            elif ia: out.append(inter(a,b))
        return out
    def ix(xc):
        return lambda a,b:[xc, round(a[1]+(b[1]-a[1])*(xc-a[0])/(b[0]-a[0]),5)]
    def iy(yc):
        return lambda a,b:[round(a[0]+(b[0]-a[0])*(yc-a[1])/(b[1]-a[1]),5), yc]
    for inside,inter in ((lambda p:p[0]>=x0,ix(x0)),(lambda p:p[0]<=x1,ix(x1)),(lambda p:p[1]>=y0,iy(y0)),(lambda p:p[1]<=y1,iy(y1))):
        pts=clip(pts,inside,inter)
        if len(pts)<3: return None
    # drop consecutive duplicates
    o=[pts[0]]
    for p in pts[1:]:
        if p!=o[-1]: o.append(p)
    if o[0]==o[-1]: o.pop()
    if len(o)<3: return None
    o.append(o[0])
    if abs(sarea(o))<1e-10: return None
    return o
def pip_ring(x,y,r):
    c=False
    for i in range(len(r)-1):
        x1,y1=r[i]; x2,y2=r[i+1]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def to_geojson_geom(rings):
    ext=[r for r in rings if sarea(r)<0]   # esri exterior = clockwise
    holes=[r for r in rings if sarea(r)>0]
    if not ext:  # orientation unexpected: treat all as exteriors
        ext=rings; holes=[]
    polys=[[e[::-1]] for e in ext]
    for h in holes:
        hx,hy=h[0]
        placed=False
        for k,e in enumerate(ext):
            if pip_ring(hx,hy,e) or pip_ring(h[1][0],h[1][1],e):
                polys[k].append(h[::-1]); placed=True; break
        if not placed: polys[0].append(h[::-1])
    if len(polys)==1: return {'type':'Polygon','coordinates':polys[0]}
    return {'type':'MultiPolygon','coordinates':polys}

def collect(pattern,keep):
    d={}
    for f in sorted(glob.glob(P+pattern)):
        u,fs,t,_=load(f)
        for x in fs:
            a=x['attributes']
            if keep(a) and a['OBJECTID'] not in d:
                d[a['OBJECTID']]=(a,x['geometry']['rings'],os.path.basename(f))
    return d
harb=collect('land_raw_harbour_*.txt',lambda a:True)
# DSNM missing? infer none here (all pages kept DSNM)
coastCACB=collect('land_raw_coastal_p*.txt',lambda a:a['DSNM'] in('US3TX1CA.000','US3TX1CB.000'))
coastBA=collect('land_raw_coastal_BA_p*.txt',lambda a:a['DSNM']=='US3TX1BA.000')
print('harbour feats',len(harb),'coastal CA/CB',len(coastCACB),'BA',len(coastBA))
feats=[]; stats={'harbour_in':0,'harbour_verts':0,'coastal_in':0,'coastal_pieces':0,'coastal_verts':0}
# harbour: sanity check each within its cell
for oid,(a,rings,src) in sorted(harb.items()):
    c=a['DSNM'][:8]
    if c not in CELLS:
        print('harbour feature in cell outside list, skipped',a); continue
    x0,y0,x1,y1=cellrect(c)
    xs=[p[0] for r in rings for p in r]; ys=[p[1] for r in rings for p in r]
    if min(xs)<x0-1e-4 or max(xs)>x1+1e-4 or min(ys)<y0-1e-4 or max(ys)>y1+1e-4:
        print('WARN outside cell',a,min(xs),max(xs),min(ys),max(ys))
    if x1<=XMIN or x0>=XMAX or y1<=YMIN or y0>=YMAX: continue
    stats['harbour_in']+=1; stats['harbour_verts']+=sum(len(r) for r in rings)
    feats.append({'type':'Feature','properties':{'name':a.get('OBJNAM'),'source':'NOAA ENC Direct enc_harbour/MapServer/233 Harbor.Land_Area (S-57 LNDARE)','band':'harbour','enc_cell':c,'objectid':oid,'tolerance_deg':0.0001,'clipped':False},'geometry':to_geojson_geom(rings)})
# clip rectangles = extent minus harbour cells, merged along rows
import math
harbset={(round(v[0],3),round(v[1],3)) for v in CELLS.values()}
rects=[]
ny0=round(YMIN/S); ny1=round(YMAX/S)
nx0=math.floor(XMIN/S+1e-9); nx1=math.ceil(XMAX/S-1e-9)
for j in range(ny0,ny1):
    y=round(j*S,3); run=None
    for i in range(nx0,nx1+1):
        x=round(i*S,3)
        free = i<nx1 and (x,y) not in harbset
        if free and run is None: run=x
        if (not free) and run is not None:
            rects.append((max(run,XMIN),y,min(x,XMAX),round(y+S,3))); run=None
print('clip rects',len(rects))
json.dump({'extent':[XMIN,YMIN,XMAX,YMAX],'harbour_cells':{c:cellrect(c) for c in CELLS},'coastal_fill_rects':rects},open(P+'land_coverage_rects.json','w'),indent=1)
for dset,tol in ((coastCACB,0.0002),(coastBA,0.0003)):
    for oid,(a,rings,src) in sorted(dset.items()):
        xs=[p[0] for r in rings for p in r]; ys=[p[1] for r in rings for p in r]
        if max(xs)<XMIN or min(xs)>XMAX or max(ys)<YMIN or min(ys)>YMAX: continue
        used=False
        for rc in rects:
            if max(xs)<rc[0] or min(xs)>rc[2] or max(ys)<rc[1] or min(ys)>rc[3]: continue
            out=[c for c in (clip_ring(r,rc) for r in rings) if c]
            if not out: continue
            used=True; stats['coastal_pieces']+=1; stats['coastal_verts']+=sum(len(r) for r in out)
            feats.append({'type':'Feature','properties':{'name':a.get('OBJNAM'),'source':'NOAA ENC Direct enc_coastal/MapServer/171 Coastal.Land_Area (S-57 LNDARE)','band':'coastal','enc_cell':a['DSNM'][:8],'objectid':oid,'tolerance_deg':tol,'clipped':True,'clip_rect':list(rc)},'geometry':to_geojson_geom(out)})
        if used: stats['coastal_in']+=1
fc={'type':'FeatureCollection','name':'land_local',
 'metadata':{'what':'Land polygons (S-57 LNDARE) around Corpus Christi TX. Validator rule: WATER if inside any water_overrides_local.geojson polygon (Oso Bay); else LAND if inside any feature here (even-odd per polygon); else WATER (incl. intertidal flats). See SOURCES_land.md.',
  'valid_extent_lonlat':[XMIN,YMIN,XMAX,YMAX],'datum':'WGS84 (EPSG:4326)','fetched':'2026-11-09',
  'bands':'harbour = NOAA band-5 ENC cells (0.075 deg tiles) inside 27 tiles covering the ship channel, CC Bay north half, Nueces Bay south half, Aransas Pass, Redfish/Aransas Bay, Rockport, GIWW in upper Laguna Madre; coastal = band-3 ENC cells US3TX1CA/CB/BA clipped to everything outside those tiles.',
  'note':'Straight edges on 0.075-deg tile lines and on the extent box are cut lines, not shoreline.'},
 'features':feats}
json.dump(fc,open(G+'land_local.geojson','w'),separators=(',',':'))
tot=0
for f in feats:
    g=f['geometry']; polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
    tot+=sum(len(r) for p in polys for r in p)
print(stats,'features',len(feats),'total verts',tot, 'bytes',os.path.getsize(G+'land_local.geojson'))
