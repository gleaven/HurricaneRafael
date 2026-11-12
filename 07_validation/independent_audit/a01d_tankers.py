import pandas as pd, numpy as np, os
from common import *
dfs=[pd.read_csv(os.path.join(SRC,'ais',f'ais_{m}.csv'),dtype={'MMSI':str}) for m in ['2027-09','2027-10','2027-11','2027-12','2028-01']]
df=pd.concat(dfs); df['t']=pd.to_datetime(df.BaseDateTime)
for mm in ['538847203','352091748','308441927','338190847','511836259','338724891']:
    g=df[df.MMSI==mm].sort_values('t').reset_index(drop=True)
    if not len(g): print(mm,'NO ROWS'); continue
    print('=====',mm,g.VesselName.unique(),'rows',len(g), g.BaseDateTime.iloc[0], g.BaseDateTime.iloc[-1])
    # segments by status / draft / destination change
    key=(g.Status.astype(str)+'|'+g.Draft.astype(str)+'|'+g.Destination.astype(str)+'|'+g.VesselName.astype(str))
    seg=(key!=key.shift()).cumsum()
    out=g.groupby(seg).agg(t0=('BaseDateTime','first'),t1=('BaseDateTime','last'),n=('t','size'),st=('Status','first'),dr=('Draft','first'),dest=('Destination','first'),lat=('LAT','median'),lon=('LON','median'),sogmax=('SOG','max'))
    print(out.head(40).to_string())
