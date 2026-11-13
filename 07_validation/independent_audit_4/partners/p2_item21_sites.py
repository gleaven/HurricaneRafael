# Pass 2 item 21/22 + Pass 3: per-site activity through the storm
import sys,re,collections,ipaddress; sys.path.insert(0,'.')
from common import *
R=reg()
a=load('auth'); w=load('web'); d=load('dns'); e=load('endpoint_alerts'); f=load('firewall')
def ld(x):
    t=ts(x); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); return (t-pd.to_timedelta(off,unit='h')).dt.strftime('%m-%d')
for x in (a,w,d,e,f): x['ld']=ld(x)
days=[f'09-{i:02d}' for i in range(9,31)]+[f'10-{i:02d}' for i in range(1,8)]
sel=sys.argv[1:] or ORGS
for o in R['organisations']:
    k=o['org_id'].lower()
    if k not in sel: continue
    h2s={h['host_id']:h['site_id'] for h in o['hosts']}; ip2s={h['ip']:h['site_id'] for h in o['hosts']}
    sites={s['site_id']:s for s in o['sites']}
    print('\n=====',k,{s:(v['name'],v['kind'],v.get('backup_power')) for s,v in sites.items()})
    ao=a[(a.org==k)&(a.logon_type!='remote')&(a.event_id=='4624')]; wo=w[(w.org==k)&(w.user!='-')]; wm=w[(w.org==k)&(w.user=='-')]; do=d[d.org==k]; eo=e[e.org==k]
    T={}
    T['logon']=pd.crosstab(ao.host.map(h2s),ao.ld)
    T['userweb']=pd.crosstab(wo.client_ip.map(ip2s).fillna('vpn'),wo.ld)
    T['machweb']=pd.crosstab(wm.client_ip.map(ip2s).fillna('vpn'),wm.ld)
    T['dns']=pd.crosstab(do.client_ip.map(ip2s).fillna('vpn'),do.ld)
    T['endpoint']=pd.crosstab(eo.host.map(h2s),eo.ld)
    for nm,t in T.items():
        t=t.reindex(columns=days,fill_value=0)
        print(nm); print(t.to_string())
    fo=f[(f.org==k)]
    print('fw rule x day (storm days):'); print(pd.crosstab(fo.rule_name,fo.ld).reindex(columns=days[4:14],fill_value=0).to_string())
