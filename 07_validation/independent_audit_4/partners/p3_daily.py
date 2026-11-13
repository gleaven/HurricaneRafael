# Pass 3: daily counts per org per log (local dates), weekday/holiday/storm patterns
import sys,re; sys.path.insert(0,'.')
from common import *
import datetime as dt
def local(d):
    t=ts(d); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6)
    return t-pd.to_timedelta(off,unit='h')
res={}
for t in TYPES:
    d=load(t); lt=local(d); d['ld']=lt.dt.strftime('%Y-%m-%d'); d['lh']=lt.dt.hour
    if t=='auth':
        d=d.assign(kind=np.where(d.logon_type=='remote','remote','ws'))
        for k in ['remote','ws']:
            res[t+'_'+k]=d[d.kind==k].groupby(['ld','org']).size().unstack(fill_value=0)
            d[d.kind==k].groupby(['org','lh']).size().unstack(fill_value=0).to_pickle(f'{C}/hourly_{t}_{k}.pkl')
    elif t=='firewall':
        for k,m in [('out',d.rule_name.str.contains('web|Web|WEB|http|Users-Internet')),('deny',d.action=='deny')]:
            res[t+'_'+k]=d[m].groupby(['ld','org']).size().unstack(fill_value=0)
    else:
        res[t]=d.groupby(['ld','org']).size().unstack(fill_value=0)
        d.groupby(['org','lh']).size().unstack(fill_value=0).to_pickle(f'{C}/hourly_{t}.pkl')
pd.to_pickle(res,C+'/daily.pkl')
for k,v in res.items():
    v.index=pd.to_datetime(v.index); v['dow']=v.index.dayofweek
    print('\n####',k); 
    print('mean by dow'); print(v.groupby('dow').mean().round(1).to_string())
    print(v.loc['2027-09-05':'2027-10-05'].to_string())
