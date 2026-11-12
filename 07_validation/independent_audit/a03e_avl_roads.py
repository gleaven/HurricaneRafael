"""Area 3: sample of AVL fixes vs real road centrelines (own distance calc on the raw road GeoJSON)."""
import pandas as pd, numpy as np, os, glob, json, time
from common import *
GEO=os.path.join(ROOT,'99_reference','geo')
segs=[]
for f in glob.glob(os.path.join(GEO,'roads_*.geojson')):
    for ft in json.load(open(f))['features']:
        g=ft['geometry']; lines=[g['coordinates']] if g['type']=='LineString' else g['coordinates']
        for l in lines:
            a=np.asarray(l,float)[:,:2]
            if len(a)>1: segs.append(np.hstack([a[:-1],a[1:]]))
S=np.vstack(segs); print('road segments',len(S))
KX,KY=98400.0,111195.0
ax,ay,bx,by=S[:,0]*KX,S[:,1]*KY,S[:,2]*KX,S[:,3]*KY
# grid index
cell=400.0
from collections import defaultdict
idx=defaultdict(list)
for i in range(len(S)):
    x0,x1=sorted((ax[i],bx[i])); y0,y1=sorted((ay[i],by[i]))
    for cx in range(int(x0//cell)-1,int(x1//cell)+2):
        for cy in range(int(y0//cell)-1,int(y1//cell)+2): idx[(cx,cy)].append(i)
def dist(lat,lon):
    px,py=lon*KX,lat*KY; c=idx.get((int(px//cell),int(py//cell)))
    if not c: return 999.0
    c=np.array(c); dx,dy=bx[c]-ax[c],by[c]-ay[c]; L=dx*dx+dy*dy; L[L==0]=1
    t=np.clip(((px-ax[c])*dx+(py-ay[c])*dy)/L,0,1)
    return float(np.sqrt((px-ax[c]-t*dx)**2+(py-ay[c]-t*dy)**2).min())
s=pd.read_csv('/tmp/avl_sample.csv'); s=s.sample(min(len(s),30000),random_state=5)
s['rd']=[dist(a,b) for a,b in zip(s.latitude,s.longitude)]
mv=s[s.speed_kmh>5]; st=s[s.speed_kmh<=5]
print('sample',len(s),' moving',len(mv),'road dist m quantiles',mv.rd.quantile([.5,.9,.99,.999,1]).round(1).tolist(),' >30 m:',(mv.rd>30).sum(),' >100 m:',(mv.rd>100).sum())
print(' stationary',len(st),st.rd.quantile([.5,.9,.99,1]).round(1).tolist(),' >150 m:',(st.rd>150).sum())
print(mv[mv.rd>30].sort_values('rd',ascending=False).head(12).to_string())
print(st[st.rd>150].groupby('unit_id').size().sort_values(ascending=False).head(8).to_string())
