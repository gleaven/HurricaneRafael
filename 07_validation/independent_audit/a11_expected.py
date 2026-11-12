"""Area 11: twenty randomly drawn expected observations, each looked up in the raw data."""
import pandas as pd, numpy as np, json, os, glob, re, csv, datetime
from common import *
pd.set_option('display.width',240)
print('#2 news 21-23 Sep');
ns=json.load(open(os.path.join(ROOT,'08_release','news_stories_public.json'))); st=ns if isinstance(ns,list) else ns.get('stories') or ns.get('items')
x=[s for s in st if '2027-09-21'<=str(s.get('published',''))[:10]<='2027-09-23' and re.search(r'claim|responsible party|designat',json.dumps(s),re.I)]
print('  stories total',len(st),' matching in window',len(x)); [print('   ',s.get('published'),s.get('outlet'),(s.get('headline') or s.get('title'))[:100]) for s in x[:5]]
print('#3 insurance ring')
ic=pd.read_csv(os.path.join(SRC,'payments','insurance_claims.csv'),dtype=str)
pt=ic[ic.record_type=='policy_transaction']; cl=ic[ic.record_type=='claim']
up=pt[(pt.transaction_date>='2027-08-09')&(pt.transaction_date<='2027-09-13')&(pt.transaction_type!='renewal')]
print('  policy tx types',pt.transaction_type.value_counts().to_dict()); 
up=up.assign(r=up.new_rcv_usd.astype(float)/up.prior_rcv_usd.astype(float)); big=up[up.r>1.25]
print('  value increases >25% in 5 weeks before landfall: policies',big.policy_id.nunique(),' broker',big.broker_id.value_counts().head(3).to_dict(),' appraiser',big.appraiser_id.value_counts().head(3).to_dict(),' dates',big.transaction_date.min(),big.transaction_date.max())
rc=cl[cl.policy_id.isin(big.policy_id)]; print('  claims on those policies',len(rc),'filed',rc.filed_date.min(),rc.filed_date.max(),' contractor',rc.contractor_estimate_supplier_id.value_counts().head(3).to_dict(),' AOB',rc.assignment_of_benefits.value_counts().to_dict())
ph=cl.photo_ids.dropna().str.split(';').explode(); dupp=ph.value_counts(); print('  photo ids reused >1 claim:',(dupp>1).sum(),' max reuse',dupp.max(),'; share of ring claims with a reused photo',round(rc.photo_ids.dropna().apply(lambda s:any(dupp[p]>1 for p in s.split(';'))).mean(),2))
print('#4 outage map SUB-02 circuits cause on D+8')
o=pd.read_csv(os.path.join(SRC,'telemetry','outage_map.csv')); y=o[(o.substation_id=='GW-FAC-SUB-02')&(o.timestamp_utc>='2027-09-21T14:30')&(o.timestamp_utc<'2027-09-23')]; print('  ',y.groupby('cause',dropna=False).size().to_dict(), y.groupby('feeder_id').customers_out.agg(['min','max']).to_dict())
y=o[(o.substation_id=='GW-FAC-SUB-03')&(o.timestamp_utc>='2027-09-24T19:45')&(o.timestamp_utc<'2027-09-26')]; print('   SUB-03',y.groupby('cause',dropna=False).size().to_dict())
print('#7 satellite D0 08:30Z'); 
for f in glob.glob(os.path.join(SRC,'satellite','*20270914T08*')): 
    p=json.load(open(f))['properties']; print('  ',os.path.basename(f),p['datetime'],p.get('gsd'),p['description'][:330])
print('#9 vessel OT logs')
for f in sorted(glob.glob(os.path.join(SRC,'telemetry','vessel_cargo_control_*.csv'))):
    d=pd.read_csv(f,dtype=str); print('  ',os.path.basename(f),len(d),list(d.columns)); 
    tc=[c for c in d.columns if 'utc' in c.lower() or 'time' in c.lower()][0]
    w=d[(d[tc]>='2027-09-14T03:50')&(d[tc]<'2027-09-14T05:40')]
    print(w.head(8).to_string()[:1500])
    if 'remote' in f: print(d.tail(6).to_string()[:1800])
