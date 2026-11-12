"""Area 5: air-quality monitors; Nueces Bay sonde peak time; O.N. Stevens intake series."""
import pandas as pd, numpy as np, os, glob
from common import *
rows=[]
for f in sorted(glob.glob(os.path.join(SRC,'env_sensors','aqs_*.csv'))):
    d=pd.read_csv(f); d['t']=pd.to_datetime(d.Date_GMT+' '+d.Time_GMT); gaps=d.t.diff(); big=d[gaps>pd.Timedelta(hours=3)]
    b=d.dropna(subset=['Benzene_ppb'])
    pk=b.loc[b.Benzene_ppb.idxmax()] if len(b) else None
    d['hl']=(d.t-pd.Timedelta(hours=5)).dt.hour; o3=d[d.t<'2027-09-07'].groupby('hl').Ozone_ppb.mean()
    rows.append((d.SensorID.iloc[0],d.Site_Name.iloc[0][:30],len(d),round(b[b.t<'2027-09-13'].Benzene_ppb.mean(),2) if len(b) else None,pk.Benzene_ppb if pk is not None else None,str(pk.t) if pk is not None else None,d.TNMHC_ppbC.max(),d.PM25_ugm3.max(),f"{o3.idxmin()}h/{o3.idxmax()}h" if o3.notna().any() else None,d.QC.value_counts().to_dict(),'; '.join(f"{(r.t-gaps[i]).strftime('%m-%d %H')}->{r.t.strftime('%m-%d %H')}" for i,r in big.iterrows())[:60]))
pd.set_option('display.width',250)
print(pd.DataFrame(rows,columns=['id','site','n','benz_base','benz_max','at','tnmhc_max','pm25max','o3 min/max hr','qc','gaps']).to_string())
for sid in ['AQS-480-003','AQS-MOB-001']:
    pass
# find Hillcrest
for f in sorted(glob.glob(os.path.join(SRC,'env_sensors','aqs_*.csv'))):
    d=pd.read_csv(f)
    if 'Hillcrest' in d.Site_Name.iloc[0] or 'efinery' in d.Site_Name.iloc[0] or 'MOB' in f:
        d['t']=pd.to_datetime(d.Date_GMT+' '+d.Time_GMT); x=d[(d.t>='2027-09-16T10:00')&(d.t<='2027-09-17T06:00')]
        print(d.Site_Name.iloc[0]); print(x[['t','Benzene_ppb','TNMHC_ppbC','WindDir_deg','QC']].iloc[::2].to_string())
        ab=d[(d.t>='2027-09-14')&(d.Benzene_ppb>3)]; print(' benzene >3 ppb from',ab.t.min(),'to',ab.t.max())
d=pd.read_csv(os.path.join(SRC,'env_sensors','water_quality_WQ-03.csv')); x=d[(d.ObsDateTime>='2027-09-18T14:00')&(d.ObsDateTime<'2027-09-18T23:00')]; print(x[['ObsDateTime','TotalHydrocarbons_ppb']].iloc[::2].to_string())
