"""Area 4: water plant / distribution state during the boil-water windows, straight from the historian."""
import pandas as pd, numpy as np, os, glob
from common import *
def load(prefix):
    d=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(SRC,'telemetry',f'historian_{prefix}_*.csv')))],ignore_index=True)
    d['t']=pd.to_datetime(d.Timestamp,utc=True).dt.tz_localize(None); d['v']=pd.to_numeric(d.Value,errors='coerce'); return d
w=load('WTP'); dist=load('DIST')
print('WTP tags:',sorted(w.Tagname.unique())); print('DIST tags:',sorted(dist.Tagname.unique()))
print('Quality codes WTP:',w.Quality.value_counts().to_dict())
wins={'pre D-30..D-1':('2027-08-15','2027-09-14T06:00'),'D0..D+4 07:00':('2027-09-14T06:00','2027-09-18T12:00'),'citywide BWN D+4..D+9':('2027-09-18T12:00','2027-09-23T02:00'),'D+9..D+28 isolation':('2027-09-23T02:05','2027-10-12T12:00'),'D+28..D+39 lift':('2027-10-12T12:30','2027-10-23T14:00'),'D+39..D+42':('2027-10-23T14:00','2027-10-26T16:00'),'after D+42':('2027-10-26T16:00','2027-11-30')}
def summ(d,tags):
    rows=[]
    for tag in tags:
        x=d[d.Tagname==tag]
        r={'tag':tag}
        for k,(a,b) in wins.items():
            y=x[(x.t>=a)&(x.t<b)]
            good=y[y.Quality==192]
            r[k]=f"{good.v.median():.1f} [{good.v.min():.0f},{good.v.max():.0f}] bad{(y.Quality!=192).mean()*100:.0f}%" if len(good) else f"no good data n={len(y)}"
        rows.append(r)
    print(pd.DataFrame(rows).set_index('tag').T.to_string())
summ(w,[t for t in sorted(w.Tagname.unique()) if any(s in t for s in ['PUMP2.RUN','PUMP3.RUN','PUMP4.RUN','PUMP1.RUN','PUMP3.PRESS.PV','PUMP2.VIB','PUMP3.BEAR','HEADER','FLOW','CL2','TURB','FEEDA','FEEDB','GEN'])][:16])
summ(dist,[t for t in sorted(dist.Tagname.unique()) if 'PRESS' in t])
z4=dist[(dist.Tagname=='GW.DIST.ZONE4.PRESS.PV')&(dist.Quality==192)].set_index('t').v
for ts in ['2027-09-13T12:00','2027-09-14T12:00','2027-09-18T12:00','2027-09-22T12:00','2027-09-23T02:00','2027-09-23T06:00','2027-09-24T19:30','2027-09-24T20:30','2027-09-26T16:00','2027-10-05','2027-10-12T11:45','2027-10-14','2027-10-20','2027-10-23T14:00','2027-10-26T16:00','2027-11-05']:
    i=z4.index.searchsorted(pd.Timestamp(ts)); print(ts, z4.index[min(i,len(z4)-1)], z4.iloc[min(i,len(z4)-1)])
