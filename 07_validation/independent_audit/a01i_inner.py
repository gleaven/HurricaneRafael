"""Area 1: deep-draft use of the inner channel during the D+30..D+44 decontamination restriction."""
import pandas as pd, numpy as np, os, json
from common import *
tr=json.load(open(os.path.join(REG,'terminal_registry.json')))
print(type(tr), list(tr.keys())[:8] if isinstance(tr,dict) else '')
terms=tr.get('terminals',tr) if isinstance(tr,dict) else tr
for t in terms:
    if isinstance(t,dict): print(t.get('terminal_id'),'|',t.get('name'),'|',t.get('segment_id') or t.get('channel_segment'),'|',t.get('lat') or t.get('latitude'),t.get('lon') or t.get('longitude'),'|',[k for k in t.keys()][:0])
segs=tr.get('channel_segments') or tr.get('segments')
if segs: print(json.dumps(segs)[:1500])
vs={str(v['mmsi']):v for v in vessels() if v.get('mmsi')}
df=pd.read_csv(os.path.join(SRC,'ais','ais_2027-10.csv'),dtype={'MMSI':str})
x=df[(df.BaseDateTime>='2027-10-14T16:00')&(df.BaseDateTime<'2027-10-28T05:00')&(df.LON<-97.3975)]
x=x[x.MMSI.map(lambda m: bool(vs.get(m,{}).get('deep_draft')))|(x.Draft>=7.5)]
x=x[~x.MMSI.isin(['538847203','352091748'])]
print('deep-draft rows west of Harbor Bridge, 14 Oct 16Z..28 Oct 05Z:',len(x))
print(x.groupby(['MMSI','VesselName']).agg(n=('LON','size'),t0=('BaseDateTime','min'),t1=('BaseDateTime','max'),west=('LON','min'),dr=('Draft','max')).sort_values('t0').to_string())
