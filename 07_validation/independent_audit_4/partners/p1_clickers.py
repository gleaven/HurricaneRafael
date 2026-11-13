# Pass 1 genuine analysis: accounts that clicked the phish -> remote sign-ons afterwards
import sys; sys.path.insert(0,'.')
from common import *
cl=pd.read_csv(ROOT+'/05_other_sources/network_logs/audit/mail_url_clicks_city_airstation.csv',dtype=str)
d=load('auth',['city','nascc']); r=d[d.logon_type=='remote'].copy()
r['p24']=r.src_ip.str.rsplit('.',n=1).str[0]
for _,c in cl.iterrows():
    x=r[r.account==c.mailbox]
    before=x[x.time_utc<c.time_utc]; after=x[x.time_utc>=c.time_utc]
    known=set(before.src_ip); 
    print('\n==',c.mailbox,'click',c.time_utc,'before',len(before),'ips',len(known),'after',len(after))
    na=after[~after.src_ip.isin(known)]
    print(na[['time_utc','host','src_ip','src_network','result','auth_method','device']].head(12).to_string())
