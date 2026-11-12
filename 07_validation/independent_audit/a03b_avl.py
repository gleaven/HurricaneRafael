"""Area 3: AVL — registry ids, over-water fixes (bridges), closure window, speeds."""
import pandas as pd, numpy as np, os, glob, json
from common import *
import mygeo
units={u['unit_id'] for u in json.load(open(os.path.join(REG,'cad_units.json')))['units']}
tot=0; water_all=[]; unk=set(); stats=[]; allp=[]
for f in sorted(glob.glob(os.path.join(SRC,'avl','*.csv'))):
    d=pd.read_csv(f); tot+=len(d); unk|=set(d.unit_id)-units
    d['t']=pd.to_datetime(d.time_utc,utc=True).dt.tz_localize(None)
    land=mygeo.on_land(d.latitude.values,d.longitude.values)
    w=d[~land].copy(); w['f']=os.path.basename(f); water_all.append(w)
    d=d.sort_values(['unit_id','t']); same=d.unit_id.eq(d.unit_id.shift()); dt=(d.t-d.t.shift()).dt.total_seconds().where(same)
    dist=np.hypot((d.latitude-d.latitude.shift())*111195,(d.longitude-d.longitude.shift())*98400).where(same)
    kmh=dist/dt*3.6
    stats.append((os.path.basename(f),len(d),str(d.t.min()),str(d.t.max()),int(d.speed_kmh.max()),int(((kmh>160)&(dt<600)&(dist>200)).sum()),int((~land).sum())))
    allp.append(d.sample(min(len(d),1500),random_state=3)[['time_utc','unit_id','latitude','longitude','speed_kmh','status']])
print(pd.DataFrame(stats,columns=['file','rows','t0','t1','maxspeed','implied>160kmh','in_water']).to_string())
print('total',tot,'unknown units',sorted(unk)[:10])
W=pd.concat(water_all); print('over-water fixes total',len(W))
def where(r):
    la,lo=r.latitude,r.longitude
    if 27.805<la<27.820 and -97.402<lo<-97.390: return 'HARBOR BRIDGE'
    if 27.820<la<27.880 and -97.385<lo<-97.335: return 'NUECES BAY CAUSEWAY'
    if 27.62<la<27.66 and -97.30<lo<-97.20: return 'JFK CAUSEWAY'
    return 'OTHER'
if len(W):
    W['where']=W.apply(where,axis=1); W['day']=(W.t-pd.Timedelta(hours=5)).dt.normalize()
    print(W.groupby('where').size().to_string())
    c=W[(W.t>='2027-09-14T05:00')&(W.t<'2027-09-18T05:00')]
    print('over-water fixes D0..D+3 local:',len(c)); print(c.groupby(['where','day']).size().to_string()); print(c.head(12)[['time_utc','unit_id','latitude','longitude','speed_kmh','status','incident_number','where']].to_string())
    print('OTHER examples'); print(W[W['where']=='OTHER'].groupby(['unit_id']).size().sort_values(ascending=False).head(8).to_string()); print(W[W['where']=='OTHER'].head(8)[['time_utc','unit_id','latitude','longitude','speed_kmh','status']].to_string())
    b=W[W['where'].isin(['HARBOR BRIDGE','NUECES BAY CAUSEWAY'])]; print('bridge fixes by local day around storm:'); print(b.groupby('day').size().loc['2027-09-08':'2027-09-24'].to_string())
pd.concat(allp).to_csv('/tmp/avl_sample.csv',index=False)
