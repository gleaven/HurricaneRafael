# Pass 1/3: portal address plan vs ASN label, vs partner auth plan
import sys,re; sys.path.insert(0,'.')
from common import *
for n in ['aid_portal_access','base_logistics_access']:
    p=portal(n)
    p['p8']=p.client_ip.str.split('.').str[0]; p['p16']=p.client_ip.str.split('.').str[:2].str.join('.')
    print('\n##',n); print(pd.crosstab(p.p8,p.client_network).to_string())
    x=p[p.p8=='100']; o2=x.client_ip.str.split('.').str[1].astype(int)
    print('100.x second octet range',o2.min(),o2.max(), 'rows',len(x),'of',len(p))
    print(pd.crosstab(p[p.p8.isin(['192','198','203'])].client_ip.str.rsplit('.',n=1).str[0],p.client_network).to_string())
