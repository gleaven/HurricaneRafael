"""Area 4: outage_map totals vs canon restoration curve."""
import pandas as pd, numpy as np, os
from common import *
o=pd.read_csv(os.path.join(SRC,'telemetry','outage_map.csv')); o['t']=pd.to_datetime(o.timestamp_utc,utc=True).dt.tz_localize(None)
print(len(o),o.t.min(),o.t.max(),'areas',o.area_id.nunique(),'feeders',o.feeder_id.nunique(),'subs',o.substation_id.unique().tolist())
print('served total per ts (unique):',o.groupby('t').customers_served.sum().unique()[:5],' rows per ts:',o.groupby('t').size().unique()[:5])
tot=o.groupby('t').customers_out.sum()
print('peak',tot.max(),'at',tot.idxmax(),' first nonzero',tot[tot>0].index.min(),' last nonzero',tot[tot>0].index.max())
for ts in ['2027-09-14T06:00','2027-09-14T07:00','2027-09-14T07:15','2027-09-14T08:00','2027-09-14T10:00','2027-09-15T00:00','2027-09-17T00:00','2027-09-21T14:15','2027-09-21T14:30','2027-09-21T14:45','2027-09-24T19:30','2027-09-24T19:45','2027-09-24T20:00','2027-09-28T12:00','2027-10-05T12:00','2027-10-12T11:45','2027-10-12T12:15','2027-10-15T00:00','2027-10-19T19:45','2027-10-19T20:00','2027-10-19T20:15','2027-10-22T00:00']:
    t=pd.Timestamp(ts); print(ts, int(tot.get(t,-1)))
d=tot.resample('1D').agg(['min','max']); print(d.loc['2027-09-13':'2027-10-22'].to_string())
print('negative or >served:',(o.customers_out<0).sum(),(o.customers_out>o.customers_served).sum())
print('cause values',o.cause.value_counts(dropna=False).to_dict())
sub=o.groupby(['t','substation_id']).customers_out.sum().unstack()
for ts in ['2027-09-14T07:00','2027-09-14T07:15','2027-09-14T07:30','2027-09-21T14:15','2027-09-21T14:30','2027-09-24T19:30','2027-09-24T19:45']:
    print(ts, sub.loc[pd.Timestamp(ts)].to_dict())
# regularity: increments
dd=tot.diff().loc['2027-09-15':'2027-09-21']; print('15-min change distribution 15-21 Sep:',dd.round(0).value_counts().head(8).to_dict())
print('missing timestamps (gaps>15min):', (tot.index.to_series().diff()>pd.Timedelta('15min')).sum(), tot.index.to_series().diff().max())
