import pandas as pd, numpy as np, json, os, glob, re, csv, datetime
from common import *
pd.set_option('display.width',240)
print('#10 alarm suppression diff at 2027-09-23T04:00Z')
s=pd.read_csv(os.path.join(SRC,'network_logs','audit','alarm_suppression_audit.csv'))
w=s[(s.time_utc>='2027-09-09')&(s.time_utc<='2027-09-23T06:00')]; print('  rows since D-5',len(w),w.action.value_counts().to_dict(),' adds by category',w[w.action=='ADD'].category.value_counts().to_dict(),' changed_by',w.changed_by.value_counts().to_dict(),' source',w.source_host.value_counts().to_dict())
print('  active_suppressions_after: before D-5',s[s.time_utc<'2027-09-09'].active_suppressions_after.iloc[-1],' at/before 23 Sep 04:00Z',s[s.time_utc<='2027-09-23T04:00:00Z'].active_suppressions_after.iloc[-1],' max',s.active_suppressions_after.max(),'at',s.loc[s.active_suppressions_after.idxmax(),'time_utc'],' distinct change times since D-5 by jump host',w[w.source_host=='GW-SYS-JMP-01'].time_utc.str[:16].nunique())
print('#11 SRMC generator'); hc=pd.read_csv(os.path.join(SRC,'public_health','hospital_capacity.csv')); print('  ',hc[(hc.Facility_ID=='FAC-SRMC-001')&(hc.Report_Date=='2027-09-14')][['Commercial_Power_Lost_UTC','Generator_Start_UTC','Power_Source']].to_dict('records'))
print('#12 EAS BWW'); e=pd.read_csv(os.path.join(SRC,'public_health','eas_broadcasts.csv')); r=e[e.AlertID=='BWW-2027-0926-001'].iloc[0]; print('  ',r.EventCode,r.IssuedAt_UTC,r.CharCount_EN,len(r.Headline_EN),'ES headline present:',isinstance(r.Headline_ES,str) and len(r.Headline_ES)>0,'| WEA ES',r.WEA_Sent_ES)
print('#13 census LEP in Districts 3/4')
idx=pd.read_csv(os.path.join(SRC,'census','nueces_tract_index.csv'),dtype=str); acs=pd.read_csv(os.path.join(SRC,'census','acs_nueces_tracts.csv'),dtype=str); print('  idx cols',list(idx.columns)); print('  acs cols',list(acs.columns))
wd=[c for c in idx.columns if 'WATER' in c.upper()][0]; key=[c for c in idx.columns if c in acs.columns][0]
m=acs.merge(idx[[key,wd]],on=key); d34=m[m[wd].isin(['AREA-WD-3','AREA-WD-4'])]
lep=[c for c in acs.columns if 'LEP' in c.upper() or 'ENGLISH' in c.upper() or 'LIMITED' in c.upper()]; pop=[c for c in acs.columns if 'POP' in c.upper()]
print('  tracts in WD3/4',len(d34),'lep cols',lep,'pop cols',pop)
for c in lep:
    v=d34[c].astype(float); p=d34[pop[0]].astype(float)
    print('   ',c,'sum',v.sum(),' / pop',p.sum(),'=',round(v.sum()/p.sum()*100,1),'% ; mean of col',round(v.mean(),1))
print('#15 advisories'); a=json.load(open(os.path.join(SRC,'weather','nhc_advisories.json')))['advisories']
ts=[x for x in a if x['classification']=='Tropical Storm']; print('  first TS advisory',ts[0]['issued_utc'],ts[0]['storm_name'],ts[0]['center']); h=[x for x in a if x['classification']=='Hurricane']; print('  first hurricane',h[0]['issued_utc'],h[0]['center'])
for x in a:
    if '2027-09-09'<=x['issued_utc'][:10]<='2027-09-09': 
        f=x['forecast'][-1]; print('  ',x['issued_utc'],'last fcst',f['valid_utc'],f['lat'],f['lon'],'cone',f['cone_radius_nm'],'dist CC',x['distance_to_corpus_christi_nm'],x['watches_and_warnings'][:1]); break
print('#16 KNGP/KCRP minima');
for st in ['KNGP','KCRP']:
    d=pd.read_csv(os.path.join(SRC,'weather',f'{st}_ASOS_observations.csv')); w=d[(d.ObsDateTime>='2027-09-13T18')&(d.ObsDateTime<'2027-09-16')]; i=w.SeaLevelPressure_mb.idxmin(); j=w.WindSpeed_mps.idxmax(); t=pd.to_datetime(w.ObsDateTime); g=t.diff().max()
    print('  ',st,'min SLP',w.SeaLevelPressure_mb[i],w.ObsDateTime[i],' max wind',w.WindSpeed_mps[j],'gust',w.WindGust_mps[j],w.ObsDateTime[j],' longest gap',g,' dir before/after',w.WindDir_deg.iloc[0],w.WindDir_deg.iloc[-1])
print('#18 CG-6033'); df=pd.read_pickle('/tmp/adsb.pkl'); x=df[(df.callsign.str.strip()=='C6033')&(df.t>='2027-09-14T06:00')&(df.t<'2027-09-14T08:00')].sort_values('t')
print(x[['t','latitude','longitude','baro_altitude','on_ground','velocity']].iloc[[0,1,2,20,60,100,130,131,132,133,140,160,200]].to_string())
hv=x[(x.velocity<5)&(~x.on_ground)]; print('  first hover row',hv.t.min(),hv.latitude.iloc[0],hv.longitude.iloc[0],' hover rows',len(hv))
