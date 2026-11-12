"""Area 5: ASOS/buoy physical sanity, diurnal cycle, storm peak, outages."""
import pandas as pd, numpy as np, os, glob
from common import *
for f in sorted(glob.glob(os.path.join(SRC,'weather','*_ASOS_observations.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.ObsDateTime); st=d.StationID.iloc[0]
    d['hl']=(d.t-pd.Timedelta(hours=5)).dt.hour
    base=d[(d.t<'2027-09-07')]
    di=base.groupby('hl').DryBulbTemp_C.mean()
    gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=3)]
    gapstr='; '.join(f"{(r.t-gaps[i]).strftime('%m-%d %H:%M')}->{r.t.strftime('%m-%d %H:%M')}" for i,r in big.iterrows())
    pk=d.loc[d.WindSpeed_mps.idxmax()]; pmin=d.loc[d.SeaLevelPressure_mb.idxmin()]
    storm=d[(d.t>='2027-09-13T12:00')&(d.t<'2027-09-15T12:00')]
    print(f"{st}: n={len(d)} {d.t.min()}..{d.t.max()} | T range {d.DryBulbTemp_C.min()}..{d.DryBulbTemp_C.max()} diurnal min@{di.idxmin()}h {di.min():.1f} max@{di.idxmax()}h {di.max():.1f} | dew>T: {(d.DewPoint_C>d.DryBulbTemp_C+0.05).sum()} RH range {d.RelativeHumidity_pct.min()}-{d.RelativeHumidity_pct.max()} | max wind {pk.WindSpeed_mps} m/s ({pk.WindSpeed_mps*1.944:.0f} kt) gust {pk.WindGust_mps} at {pk.t} | min SLP {pmin.SeaLevelPressure_mb} at {pmin.t} | precip total storm {storm.Precip1hr_mm.sum():.0f} mm max1h {d.Precip1hr_mm.max()} | gust<wind: {(d.WindGust_mps<d.WindSpeed_mps).sum()} | gaps>3h: {gapstr} | rows in storm 36h: {len(storm)}")
    # station pressure vs SLP diff consistency
    diff=(d.SeaLevelPressure_mb-d.StationPressure_mb); print('    SLP-StnP mean',round(diff.mean(),2),'sd',round(diff.std(),2),' hourly dT max',round(d.DryBulbTemp_C.diff().abs().max(),1),' dP max',round(d.SeaLevelPressure_mb.diff().abs().max(),1),' vis min',d.Visibility_m.min(),' wx codes',d.PresentWx.dropna().unique()[:8].tolist(), 'reporttypes',d.ReportType.value_counts().to_dict())
for f in sorted(glob.glob(os.path.join(SRC,'weather','BUOY*_observations.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.ObsDateTime); pk=d.loc[d.WSPD_mps.idxmax()]; hs=d.loc[d.WVHT_m.idxmax()]; pm=d.loc[d.PRES_mb.idxmin()]
    gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=3)]
    print(d.StationID.iloc[0],len(d),'max wind',pk.WSPD_mps,pk.t,'max Hs',hs.WVHT_m,hs.t,'min P',pm.PRES_mb,pm.t,'WTMP range',d.WTMP_C.min(),d.WTMP_C.max(),'gaps',[(str(r.t-gaps[i]),str(r.t)) for i,r in big.iterrows()])
# hourly sequence KRAS around landfall
d=pd.read_csv(os.path.join(SRC,'weather','KRAS_ASOS_observations.csv')); x=d[(d.ObsDateTime>='2027-09-13T18')&(d.ObsDateTime<'2027-09-14T20')]
print(x[['ObsDateTime','ReportType','WindDir_deg','WindSpeed_mps','WindGust_mps','SeaLevelPressure_mb','Precip1hr_mm','Visibility_m','PresentWx','Remarks']].to_string())
d=pd.read_csv(os.path.join(SRC,'weather','KCRP_ASOS_observations.csv')); x=d[(d.ObsDateTime>='2027-09-13T22')&(d.ObsDateTime<'2027-09-14T16')]
print(x[['ObsDateTime','WindDir_deg','WindSpeed_mps','WindGust_mps','SeaLevelPressure_mb','Precip1hr_mm','DryBulbTemp_C','DewPoint_C','Remarks']].to_string())
