import pandas as pd, numpy as np, os, glob
from common import *
import mygeo, geo
G=geo.Geo(build_roads=False)
vs={str(v['mmsi']):v for v in vessels() if v.get('mmsi')}
files=sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv')))
df=pd.concat([pd.read_csv(f,usecols=['MMSI','BaseDateTime','LAT','LON','SOG','Status','VesselName','Draft','Length'],dtype={'MMSI':str}) for f in files],ignore_index=True)
deep=df[df.MMSI.map(lambda m: bool(vs.get(m,{}).get('deep_draft'))) & (df.LON<-97.04) & (df.SOG>3)]
ch=mygeo.in_channel(deep.LAT.values,deep.LON.values)
o=deep[~ch].copy()
print('deep-draft, SOG>3, inside bay, outside channel polygon:',len(o),'of',len(deep))
o['dist']=[G.channel_distance_m(a,b) for a,b in zip(o.LAT,o.LON)]
print(o.dist.describe().round(0).to_string())
print(o[o.dist>100].groupby(['MMSI','VesselName']).agg(n=('dist','size'),mx=('dist','max'),sog=('SOG','max'),t0=('BaseDateTime','min')).sort_values('n',ascending=False).head(12).to_string())
print(o.sort_values('dist',ascending=False).head(8).to_string())
