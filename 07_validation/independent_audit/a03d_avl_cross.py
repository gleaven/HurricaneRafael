"""Area 3: strict ship-channel crossings (south bank <-> North Beach) by unit, 13-19 Sep."""
import pandas as pd, numpy as np, os, glob
from common import *
d=pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(SRC,'avl','avl_2027-09_*.csv'))])
d['t']=pd.to_datetime(d.time_utc,utc=True).dt.tz_localize(None)
d=d[(d.t>='2027-09-10T05:00')&(d.t<'2027-09-20T05:00')].sort_values(['unit_id','t']).reset_index(drop=True)
la,lo=d.latitude.values,d.longitude.values
north=((la>27.8170)&(la<27.90)&(lo>-97.40)&(lo<-97.30))
south=(la<27.8100)
d['z']=np.where(north,'N',np.where(south,'S',None))
z=d.dropna(subset=['z']).copy()
z['pz']=z.groupby('unit_id').z.shift(); z['pt']=z.groupby('unit_id').t.shift(); z['plat']=z.groupby('unit_id').latitude.shift()
x=z[(z.z!=z.pz)&z.pz.notna()].copy(); x['gap_min']=(x.t-x.pt).dt.total_seconds()/60
x['local']=x.t-pd.Timedelta(hours=5)
print('crossings per local day:'); print(x.groupby(x.local.dt.date).size().to_string())
c=x[(x.t>='2027-09-14T05:00')&(x.t<'2027-09-18T05:00')]
print(c[['local','unit_id','agency','pz','z','gap_min','plat','latitude','longitude','status','incident_number']].sort_values('local').head(30).to_string())
print('units resident north of channel 14-16 Sep (fix counts):'); n=d[north&(d.t>='2027-09-14T05:00')&(d.t<'2027-09-17T05:00')]; print(n.groupby(['unit_id','agency']).size().sort_values(ascending=False).head(15).to_string())
