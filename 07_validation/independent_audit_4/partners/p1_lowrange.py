# Pass 1 trick 8: documentation-range addresses by last octet; conjunction filters on auth
import sys,re; sys.path.insert(0,'.')
from common import *
d=load('auth'); r=d[d.logon_type=='remote'].copy()
r['p24']=r.src_ip.str.rsplit('.',n=1).str[0]; r['last']=r.src_ip.str.rsplit('.',n=1).str[1].astype(int)
for p in ['203.0.113','198.51.100','192.0.2']:
    x=r[r.p24==p]
    print('\n##',p,'last-octet histogram (bins of 10), rows / distinct ips')
    print(x.groupby(x['last']//10*10).agg(rows=('account','size'),ips=('src_ip','nunique'),accts=('account','nunique'),orgs=('org',lambda s:','.join(sorted(set(s)))),first=('time_utc','min'),last_=('time_utc','max')).to_string())
print('\n## conjunction: ASN 64512 & password & new device')
x=r[(r.src_network=='ASN 64512')&(r.auth_method=='password')&(r.device=='new device')]
print(len(x)); print(x[['time_utc','org','account','src_ip','result']].to_string())
print('\n## conjunction: password & new device (any network)')
x=r[(r.auth_method=='password')&(r.device=='new device')]
print(pd.crosstab(x.org,x.src_network).to_string())
print('\n## 203.0.113.<100 rows')
x=r[(r.p24=='203.0.113')&(r['last']<100)]
print(len(x)); print(x[['time_utc','org','account','src_ip','result','auth_method','device']].to_string())
