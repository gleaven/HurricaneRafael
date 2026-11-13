# Pass 1 trick 2: pairwise crosstabs of auth categorical columns on remote records; rare ASNs
import sys; sys.path.insert(0,'.')
from common import *
d=load('auth'); r=d[d.logon_type=='remote'].copy()
for a,b in [('src_network','result'),('src_network','auth_method'),('src_network','device'),('device','result'),('auth_method','device'),('auth_method','result')]:
    print(f"\n## {a} x {b}"); print(pd.crosstab([r.org,r[a]],r[b]).to_string())
r['p8']=r.src_ip.str.split('.').str[0]
r['p16']=r.src_ip.str.split('.').str[:2].str.join('.')
print("\n## first octet by ASN"); print(pd.crosstab(r.p8,r.src_network).to_string())
