"""Area 5: tide gauges (surge), sondes (hydrocarbons), air quality."""
import pandas as pd, numpy as np, os, glob
from common import *
print('== tide / river gauges')
for f in sorted(glob.glob(os.path.join(SRC,'env_sensors','gauge_*.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.ObsDateTime); sid=d.SensorID.iloc[0]; nm=d.SensorName.iloc[0][:45]
    gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=2)]
    gs='; '.join(f"{(r.t-gaps[i]).strftime('%m-%d %H:%M')}->{r.t.strftime('%m-%d %H:%M')}" for i,r in big.iterrows())
    if 'WaterLevel_ft_MLLW' in d:
        pk=d.loc[d.WaterLevel_ft_MLLW.idxmax()]; rs=d.loc[d.Residual_ft.idxmax()]
        base=d[d.t<'2027-09-07']
        print(f"{sid} {nm} ({d.Latitude.iloc[0]},{d.Longitude.iloc[0]}) n={len(d)} max WL {pk.WaterLevel_ft_MLLW} ft ({pk.WaterLevel_ft_MLLW*0.3048:.2f} m) at {pk.t}; max residual {rs.Residual_ft} ft ({rs.Residual_ft*0.3048:.2f} m) at {rs.t}; baseline tidal range {base.WaterLevel_ft_MLLW.min()}..{base.WaterLevel_ft_MLLW.max()}; resid check max|WL-Pred-Res| {(d.WaterLevel_ft_MLLW-d.Predicted_ft_MLLW-d.Residual_ft).abs().max():.2f}; quality {d.Quality.value_counts().to_dict()}; gaps>2h: {gs}; maxwind {d.WindSpeed_kt.max()} kt minP {d.BaroPressure_mb.min()}")
    else:
        pk=d.loc[d.Stage_ft.idxmax()]; print(f"{sid} {nm} n={len(d)} stage max {pk.Stage_ft} ft at {pk.t}, Q max {d.Discharge_cfs.max()} cfs, base stage {d[d.t<'2027-09-06'].Stage_ft.median()}; D-7 stage {d[(d.t>='2027-09-07')&(d.t<'2027-09-08')].Stage_ft.max()}; gaps>2h: {gs}")
print('== sondes: TotalHydrocarbons_ppb')
for f in sorted(glob.glob(os.path.join(SRC,'env_sensors','water_quality_*.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.ObsDateTime); sid=d.SensorID.iloc[0]
    base=d[d.t<'2027-09-13'].TotalHydrocarbons_ppb; thr=base.mean()+6*base.std()
    post=d[(d.t>='2027-09-13T18:00')]
    first=post[post.TotalHydrocarbons_ppb>thr]
    pk=d.loc[d.TotalHydrocarbons_ppb.idxmax()]
    gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=2)]
    gs='; '.join(f"{(r.t-gaps[i]).strftime('%m-%d %H:%M')}->{r.t.strftime('%m-%d %H:%M')}" for i,r in big.iterrows())
    print(f"{sid} {d.SensorName.iloc[0]} ({d.Latitude.iloc[0]},{d.Longitude.iloc[0]}): baseline {base.mean():.1f}±{base.std():.1f} ppb; first >6sd at {first.t.min()} ; peak {pk.TotalHydrocarbons_ppb} ppb at {pk.t}; back <2x base at {post[(post.t>pk.t)&(post.TotalHydrocarbons_ppb<2*base.mean())].t.min()}; QC {d.QC.value_counts().to_dict()}; gaps {gs}; sal {d.Salinity_psu.min()}-{d.Salinity_psu.max()} DO {d.DissolvedOxygen_mgL.min()}-{d.DissolvedOxygen_mgL.max()} pH {d.pH.min()}-{d.pH.max()} T {d.WaterTemp_C.min()}-{d.WaterTemp_C.max()}")
d=pd.read_csv(os.path.join(SRC,'env_sensors','water_quality_WQ-01.csv')); x=d[(d.ObsDateTime>='2027-09-14T03:00')&(d.ObsDateTime<'2027-09-14T07:30')]; print(x[['ObsDateTime','TotalHydrocarbons_ppb','Turbidity_NTU','Salinity_psu','Depth_m','QC']].to_string())
print('== air quality: benzene')
rows=[]
for f in sorted(glob.glob(os.path.join(SRC,'env_sensors','aqs_*.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.Date_GMT+' '+d.Time_GMT); pk=d.loc[d.Benzene_ppb.idxmax()]; gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=3)]
    rows.append((d.SensorID.iloc[0],d.Site_Name.iloc[0][:34],len(d),round(d[d.t<'2027-09-13'].Benzene_ppb.mean(),2),pk.Benzene_ppb,str(pk.t),d.TNMHC_ppbC.max(),d.PM25_ugm3.max(),d.Ozone_ppb.min(),d.Ozone_ppb.max(),'; '.join(f"{(r.t-gaps[i]).strftime('%m-%d %H')}->{r.t.strftime('%m-%d %H')}" for i,r in big.iterrows())))
print(pd.DataFrame(rows,columns=['id','site','n','benz_base','benz_max','at','tnmhc_max','pm25max','o3min','o3max','gaps']).to_string())
