"""Area 1: implied speed between consecutive AIS reports, per vessel."""
import pandas as pd, numpy as np, os, sys
from common import *
for month in sys.argv[1:]:
    df = pd.read_csv(os.path.join(SRC,'ais',f'ais_{month}.csv'), dtype={'MMSI':str})
    df['t'] = pd.to_datetime(df.BaseDateTime)
    df = df.sort_values(['MMSI','t']).reset_index(drop=True)
    same = df.MMSI.eq(df.MMSI.shift())
    dt = (df.t - df.t.shift()).dt.total_seconds().where(same)
    d = np.hypot((df.LAT-df.LAT.shift())*111195, (df.LON-df.LON.shift())*111195*np.cos(np.radians(df.LAT))).where(same)
    df['kn'] = d/dt*1.94384; df['dt']=dt; df['d']=d
    bad = df[(dt>0)&(dt<=3600)&(df.kn>30)&(d>200)]
    print(month,'implied >30 kn:',len(bad),'of',same.sum())
    if len(bad): print(bad.groupby(['MMSI','VesselName','VesselType']).agg(n=('kn','size'),mx=('kn','max'),ex=('BaseDateTime','first')).sort_values('n',ascending=False).head(12).to_string())
    # ratio
    ok = (dt>30)&(dt<400)&(df.SOG>3)
    r = df.kn[ok]/df.SOG[ok]
    lo = df[ok & (df.kn < 0.3*df.SOG)]
    print(' reported SOG>3 but implied <30% of it:', len(lo), 'of', ok.sum()); 
    if len(lo): print(lo.groupby(['MMSI','VesselName']).size().sort_values(ascending=False).head(8).to_string()); print(lo.head(4)[['MMSI','BaseDateTime','LAT','LON','SOG','kn','dt','Status']].to_string())
    # stationary SOG==0 but jumping
    j = df[(df.SOG<0.2)&(df.SOG.shift()<0.2)&same&(d>500)&(dt<7200)]
    print(' both reports SOG<0.2 but moved >500 m within 2 h:', len(j))
    if len(j): print(j.groupby(['MMSI','VesselName']).agg(n=('d','size'),mx=('d','max'),ex=('BaseDateTime','first')).sort_values('n',ascending=False).head(10).to_string())
    # long gaps and teleports
    tp = df[same&(dt>3600)&(d>0)&(df.kn>30)]
    print(' gap>1h implied>30kn:', len(tp))
    if len(tp): print(tp[['MMSI','VesselName','BaseDateTime','dt','d','kn']].head(8).to_string())
    print(' status/SOG contradictions: moored(5)/anchored(1) with SOG>1:', ((df.Status.isin([1,5]))&(df.SOG>1)).sum(), ' underway(0) SOG 0 rows:', ((df.Status==0)&(df.SOG==0)).sum())
    print(' lat/lon range', df.LAT.min(), df.LAT.max(), df.LON.min(), df.LON.max(), 'heading vals >360 not 511:', ((df.Heading>360)&(df.Heading!=511)).sum(), 'COG>360', (df.COG>=360).sum())
