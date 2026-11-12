"""Area 1: 50,000 random AIS positions (all months, both feeds) tested against land polygons;
deep-draft positions tested against dredged channel/anchorage."""
import pandas as pd, numpy as np, os, glob, time
from common import *
import geo
t=time.time(); G=geo.Geo(build_roads=False); print('geo load',round(time.time()-t,1))
rng=np.random.default_rng(20271109)
files=sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv')))+sorted(glob.glob(os.path.join(SRC,'ais','satellite','*.csv')))
parts=[]
for f in files:
    d=pd.read_csv(f,usecols=['MMSI','BaseDateTime','LAT','LON','SOG','Status','VesselName','Draft','Length'],dtype={'MMSI':str}); d['f']=os.path.basename(f); parts.append(d)
df=pd.concat(parts,ignore_index=True); print('total rows',len(df))
s=df.sample(50000,random_state=7)
t=time.time()
try:
    land=np.array(G.is_land_many(s.LAT.values,s.LON.values))
except Exception as e:
    print('is_land_many failed',e); land=np.array([G.is_land(a,b) for a,b in zip(s.LAT.values,s.LON.values)])
print('land test',round(time.time()-t,1),'s; on land:',int(land.sum()),'of',len(s))
bad=s[land]
if len(bad):
    print(bad.groupby(['MMSI','VesselName']).size().sort_values(ascending=False).head(20).to_string())
    bad=bad.copy(); bad['clear']=[G.shore_distance_m(a,b) if hasattr(G,'shore_distance_m') else None for a,b in zip(bad.LAT,bad.LON)]
    print(bad.sort_values('clear',ascending=False).head(15).to_string())
    bad.to_csv('a01e_ais_on_land_sample.csv',index=False)
