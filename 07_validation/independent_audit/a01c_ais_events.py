"""Area 1: anchorage hold D-2, anchorage empty before landfall, tankers, Gulf Provider, Corrin Bay."""
import pandas as pd, numpy as np, os, json
from common import *
reg = {str(v['mmsi']): v for v in vessels() if v.get('mmsi')}
dfs=[]
for m in ['2027-09','2027-10','2027-11']:
    d=pd.read_csv(os.path.join(SRC,'ais',f'ais_{m}.csv'),dtype={'MMSI':str}); dfs.append(d)
df=pd.concat(dfs); df['t']=pd.to_datetime(df.BaseDateTime)
off = (df.LON>-97.03)   # seaward of the jetties
# anchored (status 1) offshore, by 6h step
print('== vessels with Status 1 (at anchor) offshore, per 6h bin, D-4..D+4')
s=df[(df.Status==1)&off&(df.t>='2027-09-10')&(df.t<'2027-09-19')]
b=s.groupby(pd.Grouper(key='t',freq='6h')).MMSI.nunique()
print(b.to_string())
s2=df[(df.Status==1)&off&(df.t>='2027-09-12T12:00')&(df.t<'2027-09-13T17:00')]
names=s2.groupby(['MMSI','VesselName']).agg(t0=('BaseDateTime','min'),t1=('BaseDateTime','max'),dest=('Destination','first'),dr=('Draft','max'))
print('anchored offshore between Yankee and Zulu:',len(names)); print(names.to_string())
# any vessel at all offshore within 45 nm between 23:00Z D-1 and D+3
s3=df[off&(df.t>='2027-09-13T23:00')&(df.t<'2027-09-17T05:00')]
print('== rows offshore 13 Sep 23Z..17 Sep 05Z:',len(s3)); print(s3.groupby(['MMSI','VesselName','Status']).agg(n=('t','size'),t0=('BaseDateTime','min'),t1=('BaseDateTime','max'),lonmin=('LON','min'),lonmax=('LON','max')).to_string())
# all rows 13 Sep 23Z .. 14 Sep 18Z anywhere
s4=df[(df.t>='2027-09-13T23:00')&(df.t<'2027-09-14T18:00')]
print('== all AIS 13 Sep 23Z..14 Sep 18Z: rows',len(s4),'vessels',s4.MMSI.nunique(),' moving(SOG>0.5):'); print(s4[s4.SOG>0.5].groupby(['MMSI','VesselName','VesselType']).agg(n=('t','size'),t0=('BaseDateTime','min'),t1=('BaseDateTime','max'),mx=('SOG','max')).to_string())
for mm in ['538847203','352091748']:
    g=df[df.MMSI==mm].sort_values('t')
    print('==',mm,g.VesselName.iloc[0],'rows',len(g),g.BaseDateTime.min(),g.BaseDateTime.max())
    pre=g[g.t<'2027-11-15T12:00']
    print(' before 15 Nov 12Z: lat',pre.LAT.min(),pre.LAT.max(),'lon',pre.LON.min(),pre.LON.max(),'status',pre.Status.value_counts().to_dict(),'maxSOG',pre.SOG.max(),'draft',sorted(pre.Draft.unique()))
    gap=pre.t.diff().dt.total_seconds()/3600
    print(' max gap h',gap.max(), 'at', pre.BaseDateTime[gap.idxmax()] if gap.notna().any() else None, ' gaps>3h:',(gap>3).sum())
    mv=g[g.SOG>0.5]; print(' first moving rows:'); print(mv.head(3)[['BaseDateTime','LAT','LON','SOG','Status','Destination']].to_string()); print(' last row:', g.tail(1)[['BaseDateTime','LAT','LON','SOG','Status']].to_string())
