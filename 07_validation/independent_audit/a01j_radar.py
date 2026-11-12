"""Area 1: port radar vs AIS, closure windows, uncorrelated contacts; traffic log during closures."""
import pandas as pd, numpy as np, os, glob
from common import *
import mygeo
rd=pd.concat([pd.read_csv(f,dtype={'correlated_mmsi':str}) for f in sorted(glob.glob(os.path.join(SRC,'port_surveillance','radar_tracks_*.csv')))],ignore_index=True)
rd['t']=pd.to_datetime(rd.time_utc,utc=True).dt.tz_localize(None)
print('radar rows',len(rd),rd.sensor_id.value_counts().to_dict(),'size',rd.size_class.value_counts().to_dict(),'corr',rd.ais_correlated.value_counts().to_dict())
land=mygeo.on_land(rd.latitude.values,rd.longitude.values); print('radar contacts on land:',land.sum())
if land.sum(): print(rd[land].groupby(['sensor_id','size_class']).size().to_string()); print(rd[land].head(5).to_string())
W=[('2027-09-13T23:00','2027-10-14T16:00'),('2027-10-28T06:25','2027-11-11T14:00')]
for a,b in W:
    x=rd[(rd.t>=a)&(rd.t<b)&(rd.size_class=='ship')&(rd.speed_kn>1)&(rd.longitude<-97.035)]
    print('radar ship-size moving inside bay during closure',a,b,len(x)); 
    if len(x): print(x.groupby(['correlated_mmsi','sensor_id'],dropna=False).agg(n=('t','size'),t0=('time_utc','min'),t1=('time_utc','max'),L=('est_length_m','max'),v=('speed_kn','max')).head(15).to_string())
u=rd[rd.ais_correlated!='Y']
print('uncorrelated contacts by day (top):'); print(u.groupby(u.t.dt.date).size().sort_values(ascending=False).head(12).to_string())
print('uncorrelated ship-size:'); print(u[u.size_class=='ship'].groupby(['track_id']).agg(n=('t','size'),t0=('time_utc','min'),t1=('time_utc','max'),L=('est_length_m','median'),lat=('latitude','median'),lon=('longitude','median'),v=('speed_kn','max')).to_string())
x=rd[(rd.t>='2027-10-15T01:30')&(rd.t<'2027-10-15T17:00')&((rd.ais_correlated!='Y')|(rd.correlated_mmsi.isin(['338724891','511836259'])))]
print(x.groupby(['track_id','ais_correlated','correlated_mmsi','size_class'],dropna=False).agg(n=('t','size'),t0=('time_utc','min'),t1=('time_utc','max'),lat=('latitude','median'),lon=('longitude','median'),L=('est_length_m','median')).to_string())
# radar gap around landfall
h=rd[(rd.t>='2027-09-13')&(rd.t<'2027-09-18')].groupby([pd.Grouper(key='t',freq='12h'),'sensor_id']).size().unstack(fill_value=0); print(h.to_string())
# ingest lag
lag=(pd.to_datetime(rd.ingest_utc,utc=True).dt.tz_localize(None)-rd.t).dt.total_seconds(); print('ingest lag s',lag.describe().round(1).to_dict())
# radar vs AIS position for correlated in Oct
ais=pd.read_csv(os.path.join(SRC,'ais','ais_2027-10.csv'),dtype={'MMSI':str},usecols=['MMSI','BaseDateTime','LAT','LON']); ais['t']=pd.to_datetime(ais.BaseDateTime)
r=rd[(rd.t>='2027-10-01')&(rd.t<'2027-11-01')&(rd.ais_correlated=='Y')].sort_values('t')
m=pd.merge_asof(r,ais.sort_values('t'),on='t',left_by='correlated_mmsi',right_by='MMSI',direction='nearest',tolerance=pd.Timedelta('120s'))
d=np.hypot((m.latitude-m.LAT)*111195,(m.longitude-m.LON)*98300)
print('Oct correlated radar rows',len(r),'matched to AIS within 120 s',d.notna().sum(),'offset m quantiles',d.quantile([.5,.9,.99,1]).round(0).tolist())
print('correlated mmsi not in AIS month file:',sorted(set(r.correlated_mmsi)-set(ais.MMSI))[:10])
tl=pd.read_csv(os.path.join(SRC,'port_surveillance','vessel_traffic_log.csv')); tl['t']=pd.to_datetime(tl.time_utc,utc=True).dt.tz_localize(None)
for a,b in W:
    x=tl[(tl.t>=a)&(tl.t<b)]; print('traffic log during closure',a,b,len(x),x.vessel_class.value_counts().to_dict())
