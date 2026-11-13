# Pass 1 trick 11: web/dns hosts that are rare, seen in one narrow window, or one org only with few clients
import sys,re; sys.path.insert(0,'.')
from common import *
w=load('web'); d=load('dns'); f=load('firewall')
w['day']=w.time_utc.str[:10]
g=w.groupby(['org','host']).agg(n=('day','size'),days=('day','nunique'),clients=('client_ip','nunique'),first=('day','min'),last=('day','max'),cat=('category','first'),act=('action',lambda s:','.join(sorted(set(s)))))
g['span']=(pd.to_datetime(g['last'])-pd.to_datetime(g['first'])).dt.days+1
print('hosts per org with n<=3:', g[g.n<=3].groupby('org').size().to_dict())
print('\n## hosts with span<=10 days and n>=3'); print(g[(g.span<=10)&(g.n>=3)].to_string())
print('\n## uncategorised hosts'); print(g[g.cat=='uncategorised'].sort_values('n').to_string()[:5000])
for k in ['aid-help','marine-cert','disasteraid','brightwake','rmt-gw']:
    print('\n##',k,'web'); print(w[w.host.str.contains(k)].drop(columns=['_file']).to_string()[:3500])
    print('##',k,'dns'); print(d[d['query'].str.contains(k)].drop(columns=['_file']).to_string()[:3500])
