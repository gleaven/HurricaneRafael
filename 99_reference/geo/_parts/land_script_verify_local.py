import json,sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path
G='./99_reference/geo/'
fc=json.load(open(G+'land_local.geojson'))
wo=json.load(open(G+'water_overrides_local.geojson'))
def polys(g): return [g['coordinates']] if g['type']=='Polygon' else g['coordinates']
def pip_ring(x,y,r):
    c=False
    for i in range(len(r)-1):
        x1,y1=r[i]; x2,y2=r[i+1]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1: c=not c
    return c
def is_land(lat,lon):
    for f in wo['features']:
        for p in polys(f['geometry']):
            c=False
            for r in p:
                if pip_ring(lon,lat,r): c=not c
            if c: return None
    for f in fc['features']:
        for p in polys(f['geometry']):
            c=False
            for r in p:
                if pip_ring(lon,lat,r): c=not c
            if c: return f['properties']
    return None
bad=0;n=0
for f in fc['features']:
    for p in polys(f['geometry']):
        for r in p:
            n+=len(r)
            if r[0]!=r[-1] or len(r)<4: bad+=1; print('BAD ring',f['properties']['objectid'],len(r))
            for x,y in r:
                if not(-97.66<=x<=-96.84 and 27.52<=y<=28.13): bad+=1; print('OUT OF RANGE',x,y,f['properties']['objectid']); break
print('features',len(fc['features']),'verts',n,'bad',bad)
T=[('CC Bay centre',27.77,-97.25,'water'),('Gulf 10km off Port A',27.80,-96.93,'water'),('CC Intl Airport',27.770,-97.501,'land'),
('Downtown CC',27.795,-97.398,'land'),('Mid Mustang Island',27.70,-97.16,'land'),('Port Aransas town',27.834,-97.066,'land'),
('Aransas Pass channel btw jetties',27.836,-97.046,'water'),('Nueces Bay centre',27.85,-97.42,'water'),('Rockport town',28.02,-97.055,'land'),('Oso Bay centre (override)',27.70,-97.32,'water'),('Harbor Island',27.848,-97.075,'land'),('CC ship channel mid-bay',27.815,-97.30,'water'),('Inner Harbor at Harbor Bridge',27.8125,-97.396,'water'),('Ingleside town',27.875,-97.21,'land'),('Portland',27.88,-97.325,'land')]
allok=True
for nm,la,lo,exp in T:
    p=is_land(la,lo); got='land' if p else 'water'
    ok= got==exp; allok&=ok
    print(f"{'PASS' if ok else 'FAIL'} {nm:34s} ({la},{lo}) expected {exp:5s} got {got:5s}", (p['band'],p['enc_cell'],p['name']) if p else '')
print('ALL PASS' if allok else 'SOME FAIL')
def draw(ax,xlim,ylim,title):
    for f in fc['features']:
        col='#c9b27c' if f['properties']['band']=='harbour' else '#9bbf8a'
        for p in polys(f['geometry']):
            verts=[];codes=[]
            for r in p:
                verts+=r; codes+=[Path.MOVETO]+[Path.LINETO]*(len(r)-2)+[Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts,codes),facecolor=col,edgecolor='#444',lw=0.25))
    for nm,la,lo,exp in T:
        ax.plot(lo,la,'o',ms=4,color='red' if exp=='land' else 'blue')
        ax.annotate(nm,(lo,la),fontsize=5,xytext=(3,3),textcoords='offset points')
    for f in wo['features']:
        for p in polys(f['geometry']):
            verts=[];codes=[]
            for r in p:
                verts+=r; codes+=[Path.MOVETO]+[Path.LINETO]*(len(r)-2)+[Path.CLOSEPOLY]
            ax.add_patch(PathPatch(Path(verts,codes),facecolor='#7fb8e8',edgecolor='#225',lw=0.3))
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.set_aspect(1/0.885); ax.set_facecolor('#d6ecff'); ax.set_title(title,fontsize=9)
    ax.grid(True,lw=0.2)
fig,ax=plt.subplots(figsize=(13,10)); draw(ax,(-97.66,-96.84),(27.52,28.13),'land_local.geojson  tan=harbour band (ENC US5, 0.0001 deg)  green=coastal band (ENC US3, 0.0002/0.0003 deg)')
fig.savefig(G+'_parts/land_check.png',dpi=110,bbox_inches='tight')
fig,axs=plt.subplots(1,2,figsize=(16,7))
draw(axs[0],(-97.53,-97.20),(27.76,27.90),'Inner Harbor / Nueces Bay / La Quinta / Ingleside')
draw(axs[1],(-97.20,-96.97),(27.78,27.92),'Aransas Pass / Port Aransas / Harbor Island')
fig.savefig(G+'_parts/land_check_zoom.png',dpi=110,bbox_inches='tight')
