# Pass 1: aid portal per-IP / per-account shapes outside ASN 64512
import sys,re; sys.path.insert(0,'.')
from common import *
p=portal('aid_portal_access'); p['day']=p.time_utc.str[:10]
b=p[p.client_network!='ASN 64512']
g=b.groupby('client_ip').agg(n=('event','size'),created=('event',lambda s:(s=='account_created').sum()),accts=('account_ref','nunique'),uas=('user_agent_family','nunique'),first=('time_utc','min'),last=('time_utc','max'),asn=('client_network','first'))
print('ips',len(g)); print(g.created.value_counts().sort_index().to_string())
print(g.sort_values('created',ascending=False).head(25).to_string())
print(g.sort_values('accts',ascending=False).head(10).to_string())
print('rows per ip', g.n.describe().to_string())
# the 6 ASN64512 accounts created
h=p[(p.client_network=='ASN 64512')&(p.event.isin(['account_created','application_submitted']))]
print(h.drop(columns=['_file','system']).to_string())
# per account event sequences
acc=b[b.account_ref!=''].sort_values('time_utc')
seq=acc.groupby('account_ref').event.agg(lambda s:'>'.join(x[:3] for x in s))
print(seq.value_counts().head(25).to_string())
print('ips per account', acc.groupby('account_ref').client_ip.nunique().value_counts().sort_index().to_string())
print('UA per account', acc.groupby('account_ref').user_agent_family.nunique().value_counts().sort_index().to_string())
