import pandas as pd, numpy as np, os, glob
from common import *
import mygeo
vs={str(v['mmsi']):v for v in vessels() if v.get('mmsi')}
files=sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv')))+sorted(glob.glob(os.path.join(SRC,'ais','satellite','*.csv')))
df=pd.concat([pd.read_csv(f,usecols=['MMSI','BaseDateTime','LAT','LON','SOG','Status','VesselName','Draft','Length'],dtype={'MMSI':str}) for f in files],ignore_index=True)
s=df.sample(50000,random_state=11)
land=mygeo.on_land(s.LAT.values,s.LON.values)
print('independent PIP: on land',land.sum(),'of',len(s))
if land.sum(): print(s[land].groupby(['MMSI','VesselName']).size().sort_values(ascending=False).head(15).to_string()); print(s[land].head(10).to_string())
# deep-draft vessels inside the local box west of the jetties: in a dredged channel polygon?
deep=df[df.MMSI.map(lambda m: bool(vs.get(m,{}).get('deep_draft'))) & (df.LON<-97.04)]
ch=mygeo.in_channel(deep.LAT.values,deep.LON.values)
print('deep-draft rows inside the bay system',len(deep),'outside USACE channel polygons',(~ch).sum())
o=deep[~ch]
print(' of which moving SOG>0.5:',(o.SOG>0.5).sum(),' moored/slow:',(o.SOG<=0.5).sum())
print(o[o.SOG>0.5].groupby(['MMSI','VesselName']).size().sort_values(ascending=False).head(10).to_string())
print(o[o.SOG>0.5].head(8).to_string())
# full-file land test on every 3rd row, local box only
