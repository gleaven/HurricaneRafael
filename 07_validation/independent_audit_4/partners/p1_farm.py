# Pass 1: aid portal 198.51.100.44 farm and takeover shapes
import sys,re; sys.path.insert(0,'.')
from common import *
p=portal('aid_portal_access'); p['t']=ts(p)
f=p[p.client_ip=='198.51.100.44']
print(f.event.value_counts().to_string()); print(f.user_agent_family.value_counts().to_string())
print(f.head(30).drop(columns=['_file','system','t']).to_string())
f=f.assign(day=f.time_utc.str[:10],hr=f.t.dt.hour)
print(pd.crosstab(f.day,f.event).to_string())
print(f[f.event=='account_created'].hr.value_counts().sort_index().to_string())
# gap between account_created and application_submitted : farm vs others
b=p[p.event.isin(['account_created','application_submitted'])&(p.account_ref!='')]
pv=b.pivot_table(index='account_ref',columns='event',values='t',aggfunc='first')
gap=(pv['application_submitted']-pv['account_created']).dt.total_seconds()
farm=set(f.account_ref)-{''}
print('gap farm', gap[gap.index.isin(farm)].describe().to_string()); print('gap others',gap[~gap.index.isin(farm)].describe().to_string())
# takeovers
h=p[(p.client_network=='ASN 64512')&(p.time_utc>'2027-11')]
ok=h[h.event=='login_success']; dd=h[h.event.str.startswith('profile')]
print(len(ok),ok.account_ref.nunique(),len(dd),dd.account_ref.nunique())
m=ok.merge(dd,on='account_ref',suffixes=('_l','_d')); print(((m.t_d-m.t_l).dt.total_seconds()).describe().to_string())
print('same ip',(m.client_ip_l==m.client_ip_d).mean())
# fails before success for the victim account
vict=set(ok.account_ref)
fl=h[(h.event=='login_failed')]
print('failed attempts on victim accounts', fl.account_ref.isin(vict).sum(), 'distinct', fl[fl.account_ref.isin(vict)].account_ref.nunique())
print('failed refs distinct',fl.account_ref.nunique(), 'rows',len(fl)); print(fl.account_ref.value_counts().head(10).to_string())
print(fl.account_ref.str.replace(r'[0-9A-F]','X',regex=True).value_counts().head(10).to_string())
# are failed refs real accounts in portal log?
real=set(p[p.event=='account_created'].account_ref)
print('failed refs that are real accounts', len(set(fl.account_ref)&real), 'of real',len(real))
# benign login_failed
bf=p[(p.event=='login_failed')&(p.client_network!='ASN 64512')]; print('benign fails',len(bf), bf.account_ref.isin(real).mean())
# victims benign logins before/after
v=p[p.account_ref.isin(vict)&(p.client_network!='ASN 64512')]
print(v.event.value_counts().to_string())
