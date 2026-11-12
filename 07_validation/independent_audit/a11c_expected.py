import pandas as pd, numpy as np, json, os, glob, re, csv, datetime
from common import *
pd.set_option('display.width',240)
idx=pd.read_csv(os.path.join(SRC,'census','nueces_tract_index.csv'),dtype=str); acs=pd.read_csv(os.path.join(SRC,'census','acs_nueces_tracts.csv'),dtype=str)
m=acs.merge(idx[['GEOID','WATER_DISTRICT_AREA_ID']],on='GEOID'); d=m[m.WATER_DISTRICT_AREA_ID.isin(['AREA-WD-3','AREA-WD-4'])]
a=d.S1601_C05_001E.astype(float); b=d.S1601_C01_001E.astype(float); p=d.B01003_001E.astype(float)
print('#13 WD3/4 tracts',len(d),'pop',p.sum(),' S1601_C05/C01 =',round(a.sum()/b.sum()*100,1),'% ; C05/pop',round(a.sum()/p.sum()*100,1),'%; mean of tract ratios',round((a/b).mean()*100,1), ' rest of county',round(m[~m.GEOID.isin(d.GEOID)].S1601_C05_001E.astype(float).sum()/m[~m.GEOID.isin(d.GEOID)].S1601_C01_001E.astype(float).sum()*100,1))
print('#17 zeek dns 2027-08-30')
hr=json.load(open(os.path.join(REG,'gw_host_registry.json'))); txt=json.dumps(hr); i=txt.find('GW-WS-IT-04"'); print('  registry:',txt[max(0,i-200):i+200])
n=0
for line in open(os.path.join(SRC,'network_logs','zeek','2027-08-30','dns.log')):
    if line[0]=='#': continue
    p=line.rstrip('\n').split('\t')
    if 'meridian' in line.lower() or (1819632180<=float(p[0])<=1819632240 and False):
        n+=1; print('  ',datetime.datetime.utcfromtimestamp(float(p[0])).isoformat(),p[2],p[8],p[-2] if len(p)>15 else '')
print('  meridian* dns rows:',n)
for f in ['endpoint_protection.csv','mail_gateway_cbpwa.csv']:
    for line in open(os.path.join(SRC,'network_logs','audit',f)):
        if line.startswith('2027-08-30T13:1') or line.startswith('2027-08-30T13:2'):
            if 'IT-04' in line or 'quarantine' in line.lower() or 'DISABLED' in line.upper() or 'meridian' in line.lower(): print('  ',f,line.strip()[:260])
print('#19 six applications from the takeover network')
a=pd.read_csv(os.path.join(SRC,'payments','aid_applications.csv'),dtype=str)
six=a[(a.record_type=='application')&(a.source_asn=='64512')]; print(six[['application_id','account_id','submitted_utc','source_ip','device_id','damaged_address','deposit_routing_number','deposit_account_masked','applicant_name']].to_string())
t=a[(a.record_type=='account_change')&(a.source_asn=='64512')]
print('  shared devices with takeover logins:',len(set(six.device_id)&set(t.device_id)),' shared deposit accounts:',set(six.deposit_account_masked)&set(t.deposit_account_masked),' takeover deposit accounts',t.deposit_account_masked.value_counts().to_dict(),' shared IPs',len(set(six.source_ip)&set(t.source_ip)))
print('#14 AVL routes for no-find rescue calls near SUB-02 / SUB-03, 21-24 Sep')
cad=pd.read_pickle('/tmp/cad.pkl'); ia=json.load(open(os.path.join(REG,'infrastructure_assets.json'))); s=json.dumps(ia)
subs={}
def walk(o):
    if isinstance(o,dict):
        idv=o.get('asset_id') or o.get('id') or o.get('facility_id')
        if idv in('GW-FAC-SUB-02','GW-FAC-SUB-03') and ('latitude' in o or 'lat' in o): subs[idv]=(float(o.get('latitude',o.get('lat'))),float(o.get('longitude',o.get('lon'))))
        for v in o.values(): walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(ia); print('  substations',subs)
w=cad[(cad.call_received_dttm>='2027-09-21 00:00')&(cad.call_received_dttm<'2027-09-25 00:00')].copy()
for k,(la,lo) in subs.items(): w['d_'+k]=np.hypot((w.lat-la)*111195,(w.lon-lo)*98400)
w['dmin']=w[[c for c in w.columns if c.startswith('d_GW')]].min(axis=1)
near=w[w.dmin<600]; print('  incidents within 600 m of SUB-02/03 in window:',len(near)); print(near.groupby(['nature_code','disposition_code']).size().sort_values(ascending=False).head(8).to_string())
nf=near[near.disposition_desc.str.contains('UNFOUND|NO FIND|UNABLE|GONE|NOTHING',case=False,na=False)|near.narrative.str.contains('NO FIND|NOTHING FOUND|UNABLE TO LOCATE|UTL',case=False,na=False)]
print('  no-find type near subs:',len(nf),' per local day',nf.call_received_dttm.dt.date.value_counts().sort_index().to_dict()); print(nf[['incident_number','call_received_dttm','nature_code','narrative','disposition_desc','unit_id','ali_class_of_service','callback_number','dmin']].head(8).to_string())
print('  callback numbers of those:',nf.callback_number.value_counts().head(5).to_dict(),' class',nf.ali_class_of_service.value_counts().to_dict(),' carrier',nf.ali_carrier.value_counts().to_dict())
