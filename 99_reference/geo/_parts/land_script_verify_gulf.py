import json,math
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
G='./99_reference/geo/'
fc=json.load(open(G+'land_gulf_coarse.geojson'))
def polys(g): return [g['coordinates']] if g['type']=='Polygon' else g['coordinates']
def pip_ring(x,y,r):
    c=False
    for i in range(len(r)-1):
        x1,y1=r[i]; x2,y2=r[i+1]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def is_land(lat,lon):
    for f in fc['features']:
        for p in polys(f['geometry']):
            c=False
            for r in p:
                if pip_ring(lon,lat,r): c=not c
            if c: return f['properties']
    return None
bad=0
for f in fc['features']:
    for p in polys(f['geometry']):
        for r in p:
            if r[0]!=r[-1] or len(r)<4: bad+=1
            if any(not(-98.2<=x<=-76 and 17.7<=y<=33.7) for x,y in r): bad+=1
print('bad rings',bad)
T=[('mid-Gulf',25,-90,'water'),('inland Cuba',22.5,-80.0,'land'),('Houston',29.76,-95.37,'land'),('inland Florida',28.0,-81.8,'land'),('Merida MX',20.97,-89.62,'land'),
('off Corpus',27.5,-96.5,'water'),('Straits of Florida',24.0,-81.5,'water'),('Yucatan Channel',21.7,-85.8,'water'),('Tampico inland MX',22.3,-97.95,'land'),('New Orleans area',30.4,-90.9,'land'),('Bay of Campeche',20.0,-94.0,'water'),('off Tampa 60km',27.6,-83.4,'water'),('off Galveston 40km',29.0,-94.5,'water')]
ok=True
for nm,la,lo,e in T:
    p=is_land(la,lo); g='land' if p else 'water'; ok&=(g==e)
    print('PASS' if g==e else 'FAIL',nm,la,lo,e,g)
R={'Havana->CC':[(23.25,-82.40),(27.80,-96.90)],'Tampa->CC':[(27.55,-83.10),(27.80,-96.90)],'Galveston->CC':[(29.20,-94.55),(27.80,-96.90)]}
for nm,(a,b) in R.items():
    hits=0
    for i in range(401):
        t=i/400; la=a[0]+(b[0]-a[0])*t; lo=a[1]+(b[1]-a[1])*t
        if is_land(la,lo): hits+=1
    print('route',nm,'straight sea-buoy to sea-buoy, land hits:',hits)
print('ALL PASS' if ok else 'SOME FAIL')
fig,ax=plt.subplots(figsize=(13,9))
for f in fc['features']:
    for p in polys(f['geometry']):
        v=[];c=[]
        for r in p: v+=r; c+=[Path.MOVETO]+[Path.LINETO]*(len(r)-2)+[Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(v,c),facecolor='#c9b27c',edgecolor='#444',lw=0.3))
for nm,la,lo,e in T: ax.plot(lo,la,'o',ms=3,color='red' if e=='land' else 'blue'); ax.annotate(nm,(lo,la),fontsize=5)
for nm,(a,b) in R.items(): ax.plot([a[1],b[1]],[a[0],b[0]],'-',lw=0.6)
ax.set_xlim(-98.5,-75.8); ax.set_ylim(17.5,33.9); ax.set_aspect(1/math.cos(math.radians(26))); ax.set_facecolor('#d6ecff'); ax.grid(True,lw=0.2)
ax.set_title('land_gulf_coarse.geojson (ENC overview US1GC09M, 0.015 deg)',fontsize=9)
fig.savefig(G+'_parts/land_gulf_check.png',dpi=100,bbox_inches='tight')
