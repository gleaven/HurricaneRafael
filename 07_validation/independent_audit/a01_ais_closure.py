"""Area 1: deep-draft movement inside the bay system during closure windows; speed plausibility."""
import pandas as pd, numpy as np, glob, os, sys
from common import *
vs = vessels()
deep = {str(v['mmsi']): v for v in vs if v.get('mmsi') and v.get('deep_draft')}
reg = {str(v['mmsi']): v for v in vs if v.get('mmsi')}
W = [('2027-09-13T17:00:00','2027-10-14T16:00:00'),('2027-10-28T06:25:00','2027-11-11T14:00:00')]
month = sys.argv[1]
df = pd.read_csv(os.path.join(SRC,'ais',f'ais_{month}.csv'), dtype={'MMSI':str})
df['t'] = pd.to_datetime(df.BaseDateTime)
print(month, len(df), 'rows', df.MMSI.nunique(), 'mmsi; not in registry:', sorted(set(df.MMSI)-set(reg))[:10])
# inside bay system: west of the jetties tips (approx lon -97.03)
inside = df.LON < -97.035
for a,b in W:
    m = (df.t>=a)&(df.t<b)&inside
    sub = df[m]
    big = sub[(sub.MMSI.isin(deep)) | (sub.Draft>=7.5) | (sub.Length>=120)]
    mov = big[big.SOG>0.5]
    print('window',a,b,'rows inside',len(sub),'deep/large rows',len(big),'moving >0.5kn',len(mov))
    if len(mov):
        print(mov.groupby(['MMSI','VesselName']).agg(n=('SOG','size'),maxsog=('SOG','max'),t0=('BaseDateTime','min'),t1=('BaseDateTime','max'),dr=('Draft','max'),L=('Length','max')).to_string())
    # displacement check for vessels reporting SOG 0 but changing position
    for mm,g in big.groupby('MMSI'):
        d = np.hypot((g.LAT.max()-g.LAT.min())*111000,(g.LON.max()-g.LON.min())*98000)
        if d>300: print('  displaced', mm, g.VesselName.iloc[0], round(d),'m', g.BaseDateTime.min(), g.BaseDateTime.max(), 'status', sorted(g.Status.unique()))
# implied speed
df = df.sort_values(['MMSI','t'])
g = df.groupby('MMSI')
dt = g.t.diff().dt.total_seconds()
dlat = g.LAT.diff()*111195; dlon = g.LON.diff()*111195*np.cos(np.radians(df.LAT))
d = np.hypot(dlat,dlon)
kn = d/dt*1.94384
bad = df[(dt>0)&(dt<3600)&(kn>35)&(d>300)].copy(); bad['kn']=kn; bad['dt']=dt
print('implied speed >35kn (dt<1h, d>300m):', len(bad))
print(bad.groupby(['MMSI','VesselName','VesselType']).agg(n=('kn','size'),mx=('kn','max')).sort_values('n',ascending=False).head(15).to_string())
dup = df.duplicated(['MMSI','BaseDateTime']).sum(); print('dup mmsi+time', dup)
# reported vs implied
ok = (dt>30)&(dt<400)&(df.SOG>3)
r = (kn[ok]/df.SOG[ok])
print('implied/reported SOG ratio quantiles (moving, dt 30-400s):', r.quantile([.01,.05,.5,.95,.99]).round(2).tolist(), 'n', ok.sum())
print('SOG max', df.SOG.max(), 'by type:'); print(df.groupby('VesselType').SOG.max().to_string())
