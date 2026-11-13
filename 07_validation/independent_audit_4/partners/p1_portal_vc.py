# Pass 1 trick 10: portal logs value counts, singly and in pairs
import sys,re; sys.path.insert(0,'.')
from common import *
n=sys.argv[1]
p=portal(n); p['month']=p.time_utc.str[:7]
for c in ['system','client_network','method','path','status','event','user_agent_family']:
    print(f'\n### {c} nunique={p[c].nunique()}'); print(pd.crosstab(p[c],p.month).to_string())
print('\n### event x status'); print(pd.crosstab(p.event,p.status).to_string())
print('\n### path x event'); print(pd.crosstab(p.path,p.event).to_string())
print('\n### path x method'); print(pd.crosstab(p.path,p.method).to_string())
print('\n### client_network x event'); print(pd.crosstab(p.client_network,p.event).to_string())
print('\n### ua x client_network'); print(pd.crosstab(p.user_agent_family,p.client_network).to_string())
print('account_ref nunique',p.account_ref.nunique(),' empty',(p.account_ref=='').sum())
print('client_ip nunique',p.client_ip.nunique())
