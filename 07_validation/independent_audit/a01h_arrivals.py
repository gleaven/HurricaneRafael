"""Area 1: vessel_arrivals.csv / cargo_manifest.csv against AIS moored segments and closure windows."""
import pandas as pd, numpy as np, os, glob, json
from common import *
files=sorted(glob.glob(os.path.join(SRC,'ais','ais_*.csv')))
df=pd.concat([pd.read_csv(f,usecols=['MMSI','BaseDateTime','LAT','LON','SOG','Status'],dtype={'MMSI':str}) for f in files],ignore_index=True)
df['t']=pd.to_datetime(df.BaseDateTime); df=df.sort_values(['MMSI','t'])
# moored segments
df['seg']=((df.Status!=df.Status.shift())|(df.MMSI!=df.MMSI.shift())).cumsum()
segs=df[df.Status==5].groupby(['MMSI','seg']).agg(t0=('t','first'),t1=('t','last'),lat=('LAT','median'),lon=('LON','median')).reset_index()
arr=pd.read_csv(os.path.join(SRC,'supply','vessel_arrivals.csv'),dtype={'mmsi':str})
for c in ['eta_datetime','ata_anchorage_datetime','ata_datetime','atd_datetime','noa_submitted_datetime']:
    arr[c]=pd.to_datetime(arr[c],utc=True).dt.tz_localize(None)
print('arrivals rows',len(arr),'status',arr.noa_status.value_counts().to_dict())
res=[]
for _,r in arr.iterrows():
    if pd.isna(r.ata_datetime): continue
    s=segs[segs.MMSI==r.mmsi]
    if not len(s): res.append((r.arrival_id,r.vessel_name,r.ata_datetime,None,None,'NO AIS MOORED SEGMENT')); continue
    i=(s.t0-r.ata_datetime).abs().idxmin(); m=s.loc[i]
    d_arr=(m.t0-r.ata_datetime).total_seconds()/60
    d_dep=(m.t1-r.atd_datetime).total_seconds()/60 if pd.notna(r.atd_datetime) else np.nan
    res.append((r.arrival_id,r.vessel_name,r.ata_datetime,round(d_arr,1),round(d_dep,1) if d_dep==d_dep else None,''))
R=pd.DataFrame(res,columns=['id','name','ata','ais_minus_ata_min','ais_last_moored_minus_atd_min','note'])
print('with ATA:',len(R),' no AIS segment:',(R.note!='').sum())
print('AIS moored start - ATA (min):',R.ais_minus_ata_min.describe().round(1).to_dict())
print('AIS last moored - ATD (min):',R.ais_last_moored_minus_atd_min.describe().round(1).to_dict())
print(R[(R.ais_minus_ata_min.abs()>30)|(R.note!='')].to_string())
print(R[(R.ais_last_moored_minus_atd_min.abs()>90)].head(20).to_string())
# ATA / ATD inside closure
W=[('2027-09-13T17:00','2027-10-14T16:00'),('2027-10-28T06:25','2027-11-11T14:00')]
for a,b in W:
    x=arr[((arr.ata_datetime>=a)&(arr.ata_datetime<b))|((arr.atd_datetime>=a)&(arr.atd_datetime<b))]
    print('ATA/ATD inside closure',a,b,':',len(x)); print(x[['arrival_id','vessel_name','ata_datetime','atd_datetime','terminal_id']].to_string())
# berths Oct14-28 in inner harbour W
x=arr[(arr.ata_datetime>='2027-10-14T16:00')&(arr.ata_datetime<'2027-10-28T06:25')]
print('berthings in partial reopening:',len(x)); print(x[['vessel_name','ata_datetime','atd_datetime','terminal_id','berth_id','draft_arrival_m']].to_string())
print(arr[arr.vessel_name.str.contains('PROVIDER|KALVORA|OSTREL|HALCYON')][['arrival_id','vessel_name','ata_anchorage_datetime','ata_datetime','atd_datetime','terminal_id','berth_id','noa_status','hold_log','shift_berth_id','shift_datetime']].to_string())
man=pd.read_csv(os.path.join(SRC,'supply','cargo_manifest.csv'),dtype={'mmsi':str})
sea=man[man['mode']=='SEA'].merge(arr[['arrival_id','ata_datetime','atd_datetime','mmsi','vessel_name']],on='arrival_id',how='left',suffixes=('','_a'))
print('manifest rows',len(man),man['mode'].value_counts().to_dict(),' sea rows w/o arrival match:',sea.ata_datetime.isna().sum(), 'mmsi mismatch:',(sea.mmsi!=sea.mmsi_a).sum())
sea['ad']=pd.to_datetime(sea.arrival_date); sea['diff']=(sea.ad-sea.ata_datetime.dt.normalize()).dt.days
print('manifest arrival_date - ATA date (days):',sea['diff'].value_counts().sort_index().to_dict())
print(sea[sea['diff'].abs()>1][['manifest_id','vessel_name','arrival_date','ata_datetime','release_date']].head(10).to_string())
sea['rd']=pd.to_datetime(sea.release_date); print('release before arrival:',(sea.rd<sea.ad).sum())
gp=man[man.vessel_name.str.contains('PROVIDER',na=False)]; print(gp[['manifest_id','arrival_id','cargo_description','quantity','unit_of_measure','booking_date','planned_arrival_date','arrival_date','release_date','consignee_name']].to_string())
