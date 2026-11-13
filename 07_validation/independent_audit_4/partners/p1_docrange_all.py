# Pass 1 trick 9: documentation-range addresses in every log (partner firewall src/dst, dns answers, portal clients), by last-octet band
import sys,re; sys.path.insert(0,'.')
from common import *
def band(s,name):
    s=s[s.str.match(r'^(203\.0\.113|198\.51\.100|192\.0\.2)\.')]
    p=s.str.rsplit('.',n=1).str[0]; l=s.str.rsplit('.',n=1).str[1].astype(int)//10*10
    print('\n##',name,len(s)); 
    if len(s): print(pd.crosstab(l,p).T.to_string())
f=load('firewall')
for o in ORGS:
    x=f[f.org==o]
    band(x.src_ip,f'firewall {o} src_ip'); band(x.dst_ip,f'firewall {o} dst_ip')
dn=load('dns'); band(dn.answer,'dns answer')
for n in ['aid_portal_access','base_logistics_access']:
    p=portal(n); band(p.client_ip,n)
