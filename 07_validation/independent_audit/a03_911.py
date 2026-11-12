"""Area 3: 911 daily counts, land test, response-time vs distance."""
import pandas as pd, numpy as np, os, glob, json
from common import *
import mygeo
df=pd.concat([pd.read_csv(f,dtype=str) for f in sorted(glob.glob(os.path.join(SRC,'911','cad_incidents_*.csv')))],ignore_index=True)
for c in ['call_received_dttm','call_answered_dttm','dispatch_dttm','first_arrival_dttm','cleared_dttm']: df[c]=pd.to_datetime(df[c])
df['lat']=df.latitude.astype(float); df['lon']=df.longitude.astype(float)
print('rows',len(df),'range',df.call_received_dttm.min(),df.call_received_dttm.max(),'dup incident numbers',df.incident_number.duplicated().sum())
df['d']=(df.call_received_dttm.dt.normalize()-pd.Timestamp('2027-09-14')).dt.days
dc=df.groupby('d').size()
src=df[df.call_source=='911'].groupby('d').size()
vol=pd.read_csv(os.path.join(SRC,'911','reports','cbecc_daily_call_volume.csv')); vol['d']=(pd.to_datetime(vol.date_local)-pd.Timestamp('2027-09-14')).dt.days; vol=vol.set_index('d')
t=pd.DataFrame({'incidents':dc,'src911':src,'rep_911':vol.calls_911,'rep_all':vol.calls_all_lines,'rep_inc':vol.incidents_with_unit})
print(t.loc[-5:50].to_string())
print('baseline mean D-30..D-6 incidents',dc.loc[-30:-6].mean().round(0),' D+60..D+119',dc.loc[60:119].mean().round(0))
print('report sums all lines D0..D28',vol.calls_all_lines.loc[0:28].sum(),'D0..D45',vol.calls_all_lines.loc[0:45].sum(),' 911 D0-2',vol.calls_911.loc[0:2].sum())
print('call_source',df.call_source.value_counts().to_dict())
land=mygeo.on_land(df.lat.values,df.lon.values); print('incidents not on land:',(~land).sum(),'of',len(df))
w=df[~land]; print(w.nature_code.value_counts().head(12).to_dict()); print(w[['incident_number','call_received_dttm','nature_code','address','lat','lon']].head(12).to_string())
print('lat/lon range',df.lat.min(),df.lat.max(),df.lon.min(),df.lon.max())
# time ordering
for a,b in [('call_received_dttm','call_answered_dttm'),('call_answered_dttm','dispatch_dttm'),('dispatch_dttm','first_arrival_dttm'),('first_arrival_dttm','cleared_dttm')]:
    m=df[a].notna()&df[b].notna(); print(a,'>',b,':',(df[a][m]>df[b][m]).sum(),' missing b:',df[b].isna().sum())
df['resp']=(df.first_arrival_dttm-df.dispatch_dttm).dt.total_seconds()/60
print('dispatch->arrival min by period:'); 
for lab,a,b in (('pre',-30,-3),('D0-D2',0,2),('D3-D12',3,12),('D13-D45',13,45),('late',46,119)):
    x=df[(df.d>=a)&(df.d<=b)]; print(lab,len(x),x.resp.describe()[['min','25%','50%','75%','max']].round(1).to_dict(),'no arrival',x.first_arrival_dttm.isna().sum())
df.to_pickle('/tmp/cad.pkl')
print('nature codes top'); print(df.nature_code.value_counts().head(25).to_dict())
print('language',(df.caller_language.value_counts(normalize=True)*100).round(1).to_dict())
x=df[df.nature_code.str.contains('WATER',na=False)]; print('WATER codes',x.nature_code.value_counts().to_dict(),'first',x.call_received_dttm.min())
