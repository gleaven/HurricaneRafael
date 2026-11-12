"""Area 3: units crossing between downtown and North Beach/Portland while the US-181 bridges are closed."""
import pandas as pd, numpy as np, os, glob, json
from common import *
d=pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(SRC,'avl','avl_2027-09_*.csv'))])
d['t']=pd.to_datetime(d.time_utc,utc=True).dt.tz_localize(None)
d=d[(d.t>='2027-09-13T05:00')&(d.t<'2027-09-19T05:00')].sort_values(['unit_id','t']).reset_index(drop=True)
def side(la,lo):
    # north of the ship channel / Nueces Bay along US-181: North Beach and Portland-Gregory-Ingleside
    nb=(la>27.8165)&(la<27.846)&(lo>-97.398)&(lo<-97.365)
    pt=(la>27.846)&(lo>-97.37)&(lo<-97.10)
    cw=(la>27.832)&(la<27.875)&(lo>-97.385)&(lo<-97.33)   # causeway corridor
    return np.where(nb,'NORTH_BEACH',np.where(cw,'CAUSEWAY',np.where(pt,'PORTLAND_SIDE','SOUTH')))
d['side']=side(d.latitude.values,d.longitude.values)
print(d.groupby([(d.t-pd.Timedelta(hours=5)).dt.date,'side']).size().unstack(fill_value=0).to_string())
ch=d[(d.side!=d.side.shift())&(d.unit_id==d.unit_id.shift())].copy(); ch['prev']=d.side.shift()[ch.index]; ch['prev_t']=d.t.shift()[ch.index]
ch=ch[(ch.t>='2027-09-14T05:00')&(ch.t<'2027-09-18T05:00')]
print('side changes D0..D+3 local:',len(ch)); print(ch[['time_utc','prev_t','unit_id','agency','prev','side','latitude','longitude','speed_kmh','status','incident_number']].head(40).to_string())
hb=d[(d.latitude>27.806)&(d.latitude<27.8175)&(d.longitude>-97.40)&(d.longitude<-97.392)&(d.t>='2027-09-14T05:00')&(d.t<'2027-09-18T05:00')]
print('fixes in Harbor Bridge box D0..D+3:',len(hb)); print(hb[['time_utc','unit_id','latitude','longitude','speed_kmh','status','incident_number']].head(25).to_string())
