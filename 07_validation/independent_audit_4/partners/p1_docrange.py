# Pass 1 trick 3: remote sign-ons from documentation ranges (private ASNs 64496/64499/64512)
import sys; sys.path.insert(0,'.')
from common import *
d=load('auth'); r=d[d.logon_type=='remote'].copy(); r['t']=ts(r)
r['doc']=r.src_network.isin(['ASN 64496','ASN 64499','ASN 64512'])
x=r[r.doc]
print(len(x), x.src_ip.nunique(), x.account.nunique())
x=x.assign(p24=x.src_ip.str.rsplit('.',n=1).str[0], month=x.time_utc.str[:7], day=x.time_utc.str[:10])
print(pd.crosstab(x.month,[x.org,x.src_network]).to_string())
g=x.groupby('src_ip').agg(n=('account','size'),accts=('account','nunique'),orgs=('org','nunique'),first=('time_utc','min'),last=('time_utc','max'),fail=('result',lambda s:(s=='FAILED').sum()),newdev=('device',lambda s:(s=='new device').sum()))
print(g.sort_values('accts',ascending=False).head(40).to_string())
print(g.n.describe())
# per-ip distribution for normal ASNs for comparison
y=r[~r.doc]; g2=y.groupby('src_ip').agg(n=('account','size'),accts=('account','nunique'))
print('normal ips multi-account:', (g2.accts>1).sum(), 'of', len(g2)); print(g2.sort_values('accts',ascending=False).head(15))
