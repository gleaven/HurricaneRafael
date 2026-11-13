# Pass 3: base logistics access log realism
import sys,re,collections; sys.path.insert(0,'.')
from common import *
p=portal('base_logistics_access'); t=ts(p); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); p['ltm']=t-pd.to_timedelta(off,unit='h'); p['ld']=p.ltm.dt.strftime('%Y-%m-%d'); p['lh']=p.ltm.dt.hour; p['t']=t
b=p[p.client_network=='base network']; o=p[(p.client_network!='base network')&(p.client_network!='ASN 64512')]
d=b.groupby('ld').size(); d.index=pd.to_datetime(d.index)
print('base-network rows/day: weekday mean',d[d.index.dayofweek<5].mean().round(1),'weekend',d[d.index.dayofweek>=5].mean().round(1))
print('storm window:',{k.strftime('%m-%d'):v for k,v in d.loc['2027-09-06':'2027-09-26'].items()})
print('holidays:',{k:int(d.get(pd.Timestamp(k),0)) for k in ['2027-09-06','2027-11-25','2027-12-25','2028-01-01']})
print('weekly mean:',d.resample('W').mean().round(0).to_dict().__repr__()[:1500])
print('hour of day % local:',(b.lh.value_counts(normalize=True).sort_index()*100).round(1).to_dict())
acc=b.groupby('account_ref').agg(n=('event','size'),ips=('client_ip','nunique'),first=('time_utc','min'),last=('time_utc','max'))
print('accounts',len(acc),'rows per account',acc.n.describe()[['min','50%','max']].to_dict(),'ips per account',acc.ips.describe()[['min','50%','max']].to_dict())
print('account id shapes:',b.account_ref.str.replace(r'[0-9a-f]{6}$','<hex6>',regex=True).value_counts().head(5).to_dict())
ip=b.groupby('client_ip').account_ref.nunique(); print('addresses',len(ip),'with >1 account',(ip>1).sum(),'| third octets',sorted(set(b.client_ip.str.split('.').str[2].astype(int)))[:40])
print('event x path (base):'); print(pd.crosstab(b.path,[b.method,b.event]).to_string())
print('fail rate',(b.event=='login_failed').mean().round(3)); 
bs=b.sort_values('time_utc'); g=bs.assign(prev=bs.groupby('account_ref').event.shift(),dt=(bs.t-bs.groupby('account_ref').t.shift()).dt.total_seconds())
x=g[g.prev=='login_failed'].dt; print('after a failure: next row gap s min/p50/max',x.min(),x.median(),x.max(),'next event',g[g.prev=='login_failed'].event.value_counts().to_dict())
print('rows per account-day:',bs.groupby(['account_ref','ld']).size().value_counts().sort_index().head(8).to_dict())
print('UA base:',b.user_agent_family.value_counts().to_dict())
print('outside benign: rows',len(o),'events',o.event.value_counts().to_dict(),'paths',o.path.value_counts().to_dict())
print(' crawler rows',(o.user_agent_family=='crawler').sum(),'paths',o[o.user_agent_family=='crawler'].path.value_counts().to_dict(), 'non-crawler robots.txt',((o.user_agent_family!='crawler')&(o.path=='/robots.txt')).sum())
od=o.groupby('ld').size(); od.index=pd.to_datetime(od.index); print(' outside per day weekday/weekend',od[od.index.dayofweek<5].mean().round(1),od[od.index.dayofweek>=5].mean().round(1),' storm week',od.loc['2027-09-13':'2027-09-19'].tolist())
print(' outside hour-of-day',(o.lh.value_counts(normalize=True).sort_index()*100).round(0).to_dict())
g2=p.groupby('client_ip').client_network.nunique(); print('addresses with >1 label:',(g2>1).sum())
h=p[p.client_network=='ASN 64512']; print('scan: rows',len(h),'addresses',h.client_ip.nunique(),'per-day',h.time_utc.str[:10].value_counts().sort_index().to_dict(),'gap between rows s p50',h.t.sort_values().diff().dt.total_seconds().median())
a=portal('aid_portal_access'); ha=a[(a.client_network=='ASN 64512')&(a.time_utc<'2027-09')]
print('aid scan addresses',ha.client_ip.nunique(),'shared with logistics scan',len(set(ha.client_ip)&set(h.client_ip)),'| last octet range aid',sorted(set(ha.client_ip.str.rsplit('.',n=1).str[1].astype(int)))[0],sorted(set(ha.client_ip.str.rsplit('.',n=1).str[1].astype(int)))[-1])
st=a[(a.client_network=='ASN 64512')&(a.time_utc>'2027-11')]; print('stuffing addresses last octets:',sorted(set(st.client_ip.str.rsplit('.',n=1).str[1].astype(int)))[0],'-',sorted(set(st.client_ip.str.rsplit('.',n=1).str[1].astype(int)))[-1],'n',st.client_ip.nunique())
