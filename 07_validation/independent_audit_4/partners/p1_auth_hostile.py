# Pass 1 trick 7: remote sign-ons: /24s used by many accounts; accounts' first-seen addresses after 09-15; per-day new-device rates
import sys; sys.path.insert(0,'.')
from common import *
d=load('auth'); r=d[d.logon_type=='remote'].copy(); r['t']=ts(r); r['day']=r.time_utc.str[:10]
r['p24']=r.src_ip.str.rsplit('.',n=1).str[0]
g=r.groupby(['org','p24']).agg(n=('account','size'),accts=('account','nunique'),ips=('src_ip','nunique'),first=('time_utc','min'),last=('time_utc','max'),fail=('result',lambda s:(s=='FAILED').sum()),newdev=('device',lambda s:(s=='new device').sum()),asn=('src_network','first'))
print('## /24 with >=4 accounts'); print(g[g.accts>=4].sort_values('accts',ascending=False).head(40).to_string())
# daily new device counts, city & nascc
for o in ['city','nascc']:
    x=r[r.org==o]
    dd=x.groupby('day').agg(n=('account','size'),newdev=('device',lambda s:(s=='new device').sum()),fail=('result',lambda s:(s=='FAILED').sum()),pw=('auth_method',lambda s:(s=='password').sum()))
    print(o); print(dd.loc['2027-09-08':'2027-09-30'].to_string())
