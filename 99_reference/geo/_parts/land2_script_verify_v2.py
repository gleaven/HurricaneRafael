"""Verification of the 2026-11-10 land/water upgrade. Uses scripts/geo.py (Geo().is_land) on the new files and an
independent even-odd test on the v1 copies in _parts/. Check-point coordinates come from landmarks.geojson (FAA/USGS/EPA),
from USACE channel centerlines, from road centerlines (roads_*.geojson) or are well-known bay/lake centres."""
import sys,os,json,glob,hashlib,math
ROOT='./'
sys.path.insert(0,ROOT+'scripts'); sys.path.insert(0,ROOT+'07_validation/independent_audit')
import numpy as np
import geo, mygeo
G=ROOT+'99_reference/geo/'; P=G+'_parts/'
for f in glob.glob(G+'_cache/*.npz'): os.remove(f)
Gx=geo.Geo(build_roads=False)
L1=mygeo.Polys('_parts/land_local.v1.geojson'); W1=mygeo.Polys('_parts/water_overrides_local.v1.geojson')
def old_land(lat,lon): return bool((L1.contains([lat],[lon])&~W1.contains([lat],[lon]))[0])
lm={f['properties']['name']:f for f in json.load(open(G+'landmarks.geojson'))['features']}
def LM(name):
    f=lm[name]; return (f['geometry']['coordinates'][1],f['geometry']['coordinates'][0])
MLAT=110950.0; MLON=111320.0*math.cos(math.radians(27.8))
def road_crossing(files,name,box):
    """mid-point of the longest run of v2-water samples along the named road inside box (lon0,lat0,lon1,lat1)."""
    best=None
    for fn in files:
        for f in json.load(open(G+fn))['features']:
            if f['properties'].get('name')!=name: continue
            g=f['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
            for ln in lines:
                pts=[]
                for a,b in zip(ln,ln[1:]):
                    d=math.hypot((b[0]-a[0])*MLON,(b[1]-a[1])*MLAT); k=max(1,int(d/5))
                    pts+=[(a[0]+(b[0]-a[0])*i/k,a[1]+(b[1]-a[1])*i/k) for i in range(k)]
                pts=[p for p in pts if box[0]<=p[0]<=box[2] and box[1]<=p[1]<=box[3]]
                if not pts: continue
                w=~Gx.is_land_many([p[1] for p in pts],[p[0] for p in pts])
                i=0
                while i<len(pts):
                    if w[i]:
                        j=i
                        while j+1<len(pts) and w[j+1]: j+=1
                        if best is None or j-i>best[0]: best=(j-i,pts[(i+j)//2])
                        i=j+1
                    else: i+=1
    if best is None: return None,0
    return (round(best[1][1],5),round(best[1][0],5)),(best[0]+1)*5
REF=[('CC Bay centre',27.77,-97.25,'water'),('Gulf 10 km off Port Aransas',27.80,-96.93,'water'),('CC Intl Airport',27.770,-97.501,'land'),
('Downtown CC',27.795,-97.398,'land'),('Mid Mustang Island',27.70,-97.16,'land'),('Port Aransas town',27.834,-97.066,'land'),
('Aransas Pass between the jetties',27.836,-97.046,'water'),('Nueces Bay centre',27.85,-97.42,'water'),('Rockport',28.02,-97.055,'land')]
EXTRA_V1=[('Oso Bay centre',27.70,-97.32,'water'),('Harbor Island',27.848,-97.075,'land'),('CC ship channel mid-bay',27.815,-97.30,'water'),('Inner Harbor at Harbor Bridge',27.8125,-97.396,'water'),('Ingleside town',27.875,-97.21,'land'),('Portland',27.88,-97.325,'land')]
NEW=[]
for nm in ['Corpus Christi Nas (Truax Fld) (NGP/KNGP)','Corpus Christi Nas (Truax Fld) (NGP) runway 13R/31L end 1','Corpus Christi Nas (Truax Fld) (NGP) runway 04/22 end 2','Corpus Christi Nas (Truax Fld) (NGP) runway 13L/31R end 2',
 'Waldron Fld Nolf (NWL/KNWL)','Waldron Fld Nolf (NWL) runway 18/36 end 2','Cabaniss Fld Nolf (NGW/KNGW)','Ingleside Rgnl (TFP/KTFP)','Aransas County (RKP) runway 14/32 end 1','Sinton (T69)',
 'Texas A&M University-Corpus Christi','Oso WWTP (Corpus Christi)','Flour Bluff High School','Flour Bluff Fire Department - Nueces County Emergency Services District 2','Del Mar College Oso Creek Campus','Copano Village','Flour Bluff','Windsor Park Elementary School','Tuloso Midway High School']:
    la,lo=LM(nm); NEW.append((nm+' [landmarks.geojson]',la,lo,'land'))
def add_cross(label,files,name,box):
    p,ln=road_crossing(files,name,box)
    if p is None: NEW.append((label+' [no water crossing found on road centerline]',float('nan'),float('nan'),'water'))
    else: NEW.append((label+' [mid-point of %d m water run on %s centerline]'%(ln,name),p[0],p[1],'water'))
RM=['roads_major.geojson','roads_arterial.geojson']
add_cross('Nueces River at the I-37 bridge',RM,'I- 37',(-97.65,27.86,-97.60,27.90))
add_cross('Oso Bay inlet at the Ocean Dr bridge',RM,'Ocean Dr',(-97.34,27.70,-97.29,27.72))
add_cross('Cayo del Oso at the Yorktown Blvd bridge',RM,'Yorktown Blvd',(-97.37,27.62,-97.32,27.66))
add_cross('Oso Creek at the S Staples St bridge',RM,'S Staples St',(-97.42,27.63,-97.36,27.68))
add_cross('Oso Creek at the Weber Rd bridge',RM,'Weber Rd',(-97.45,27.63,-97.38,27.70))
# Laguna Madre mid-channel: a vertex of the USACE GIWW centerline between 27.60 and 27.66 N
best=None
for f in json.load(open(G+'channel_lines_usace.geojson'))['features']:
    g=f['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
    for ln in lines:
        for x,y in [c[:2] for c in ln]:
            if 27.60<=y<=27.66 and -97.30<=x<=-97.20 and (best is None or abs(y-27.63)<abs(best[0]-27.63)): best=(y,x)
if best: NEW.append(('Laguna Madre mid-channel (USACE GIWW centerline vertex)',round(best[0],5),round(best[1],5),'water'))
NEW+=[('Cayo del Oso south arm near Yorktown Blvd (project road-crossing seed)',27.6407,-97.3438,'water'),
('Oso Bay north basin off TAMU-CC',27.705,-97.315,'water'),('Oso Bay south basin (between SPID and Yorktown)',27.665,-97.335,'water'),
('Copano Bay centre',28.09,-97.12,'water'),('Laguna Madre off Flour Bluff (Laguna Shores)',27.64,-97.265,'water'),
('Sunset Lake, Portland (lake centre)',27.866,-97.338,'water'),('Laguna Madre centre south of JFK Causeway',27.60,-97.25,'water'),
('Corpus Christi Bay 1 km off Ocean Dr / Cole-Ropes Park shore',27.745,-97.36,'water'),('Corpus Christi Bay off NAS north shore',27.72,-97.29,'water'),
('Upper Laguna Madre / Packery flats east of the GIWW',27.66,-97.215,'water')]
def run(T,title):
    ok=0; print('---',title)
    for nm,la,lo,exp in T:
        if la!=la: print('FAIL %-95s no point'%nm); continue
        got='land' if Gx.is_land(la,lo) else 'water'; o='land' if old_land(la,lo) else 'water'
        r,c=Gx.px(la,lo); ras='land' if Gx.land_mask[r,c] else 'water'
        ok+=(got==exp)
        print('%s %-95s (%.5f,%.5f) expected %-5s v2 %-5s raster %-5s | v1 %-5s%s'%('PASS' if got==exp else 'FAIL',nm[:95],la,lo,exp,got,ras,o,'  <-- changed' if o!=got else ''))
    print('    %d/%d pass'%(ok,len(T))); return ok
a=run(REF,'nine reference points of SOURCES_land.md'); b=run(EXTRA_V1,'extra v1 points'); c=run(NEW,'new check points (upgraded areas)')
# mass checks
fs=json.load(open(G+'landmarks.geojson'))['features']
la=np.array([f['geometry']['coordinates'][1] for f in fs]); lo=np.array([f['geometry']['coordinates'][0] for f in fs])
inb=(lo>=-97.65)&(lo<=-96.85)&(la>=27.525)&(la<=28.125)
o=L1.contains(la,lo)&~W1.contains(la,lo); n=Gx.is_land_many(la,lo)
print('landmarks in window %d: land v1 %d, land v2 %d, flipped %d'%(inb.sum(),(o&inb).sum(),(n&inb).sum(),((o!=n)&inb).sum()))
xs=[];ys=[]
for f in json.load(open(G+'channel_lines_usace.geojson'))['features']:
    g=f['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
    for ln in lines:
        for q in ln: xs.append(q[0]); ys.append(q[1])
xs=np.array(xs); ys=np.array(ys); m=(xs>=-97.65)&(xs<=-96.85)&(ys>=27.525)&(ys<=28.125)
print('USACE channel centerline vertices in window %d: on land v1 %d, v2 %d'%(m.sum(),(L1.contains(ys[m],xs[m])&~W1.contains(ys[m],xs[m])).sum(),Gx.is_land_many(ys[m],xs[m]).sum()))
# roads over water (bridges): informational
tot=0;wo=0;wn=0
for fn in sorted(glob.glob(G+'roads_*.geojson')):
    for f in json.load(open(fn))['features']:
        g=f['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
        for ln in lines:
            for a_,b_ in zip(ln,ln[1:]):
                d=math.hypot((b_[0]-a_[0])*MLON,(b_[1]-a_[1])*MLAT); k=max(1,int(d/25))
                px=np.array([a_[0]+(b_[0]-a_[0])*i/k for i in range(k)]); py=np.array([a_[1]+(b_[1]-a_[1])*i/k for i in range(k)])
                mm=(px>=-97.65)&(px<=-96.85)&(py>=27.525)&(py<=28.125)
                if not mm.any(): continue
                tot+=mm.sum(); wo+=(~(L1.contains(py[mm],px[mm])&~W1.contains(py[mm],px[mm]))).sum(); wn+=(~Gx.is_land_many(py[mm],px[mm])).sum()
print('road centerline samples (25 m) in window %d: over water v1 %d (%.1f km), v2 %d (%.1f km)  [bridges/causeways read as water]'%(tot,wo,wo*0.025,wn,wn*0.025))
# hashes
v1=json.load(open(P+'land_local.v1.geojson')); v2=json.load(open(G+'land_local.geojson'))
h=lambda fc:hashlib.sha256(json.dumps([f for f in fc['features'] if f['properties']['band']=='harbour'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
print('harbour-band features: v1 n=%d sha256 %s | v2 n=%d sha256 %s | identical %s'%(sum(f['properties']['band']=='harbour' for f in v1['features']),h(v1),sum(f['properties']['band']=='harbour' for f in v2['features']),h(v2),h(v1)==h(v2)))
print('whole land_local.geojson identical to v1 feature list:',json.dumps(v1['features'],sort_keys=True)==json.dumps(v2['features'],sort_keys=True))
print('raster vs exact on a 100k random sample:', end=' ')
rng=np.random.default_rng(1); rl=rng.uniform(27.53,28.12,100000); ro=rng.uniform(-97.645,-96.855,100000)
ex=Gx.is_land_many(rl,ro); rr=((geo.BOX[3]-rl)*geo.M_PER_DEG_LAT/geo.RASTER_M).astype(int); cc=((ro-geo.BOX[0])*geo.M_PER_DEG_LON/geo.RASTER_M).astype(int)
ra=Gx.land_mask[np.clip(rr,0,Gx.ny-1),np.clip(cc,0,Gx.nx-1)]
print('agree %.3f%%, land fraction exact %.4f raster %.4f'%(100*(ex==ra).mean(),ex.mean(),ra.mean()))
for f in glob.glob(G+'_cache/*.npz'): os.remove(f)
print('cache npz removed:',glob.glob(G+'_cache/*.npz')==[])
