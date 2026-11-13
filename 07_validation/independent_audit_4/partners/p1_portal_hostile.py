# Pass 1: aid portal ASN 64512 activity
import sys,re; sys.path.insert(0,'.')
from common import *
p=portal('aid_portal_access'); p['day']=p.time_utc.str[:10]; p['hour']=p.time_utc.str[:13]
h=p[p.client_network=='ASN 64512']
print(pd.crosstab(h.day,h.event).to_string())
a=h[h.day<'2027-09']
print(a.groupby(['user_agent_family','path','status','event']).size().to_string())
print(a.client_ip.value_counts().head(20)); print(a.time_utc.min(),a.time_utc.max())
print(a.head(30).drop(columns=['_file','system']).to_string())
n=h[h.day>='2027-11']
print(n.client_ip.nunique()); print(n.client_ip.value_counts().describe())
print(n.groupby('hour').size().to_string())
print(n[n.user_agent_family!='python-requests'].drop(columns=['_file','system']).to_string())
