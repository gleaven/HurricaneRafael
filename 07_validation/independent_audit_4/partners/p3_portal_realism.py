# Pass 3: portal log realism (benign traffic)
import sys,re,collections; sys.path.insert(0,'.')
from common import *
p=portal('aid_portal_access'); t=ts(p); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); p['ltm']=t-pd.to_timedelta(off,unit='h'); p['ld']=p.ltm.dt.strftime('%Y-%m-%d'); p['lh']=p.ltm.dt.hour; p['t']=t
b=p[p.client_network!='ASN 64512']
print('rows benign',len(b))
d=b.groupby('ld').size(); d.index=pd.to_datetime(d.index)
print('daily benign rows, weekly means:'); print(d.resample('W').mean().round(0).to_string())
print('storm fortnight:'); print(d.loc['2027-09-08':'2027-09-24'].to_dict())
print('registration fortnight:'); print(pd.crosstab(b.ld,b.event).loc['2027-11-08':'2027-11-30'].to_string())
dd=d.loc['2027-07-17':'2027-09-10']; print('pre-storm weekday mean',dd[dd.index.dayofweek<5].mean().round(1),'weekend',dd[dd.index.dayofweek>=5].mean().round(1))
print('hour of day % (local): pre-Nov page views / applications / logins'); 
x=pd.DataFrame({'pv_pre':b[(b.event=='page_view')&(b.ld<'2027-11-01')].lh.value_counts(normalize=True),'apps':b[b.event=='application_submitted'].lh.value_counts(normalize=True),'login':b[b.event=='login_success'].lh.value_counts(normalize=True)}).sort_index(); print((x*100).round(1).T.to_string())
# label per ip
g=p.groupby('client_ip').client_network.nunique(); print('client addresses with more than one client_network label:',(g>1).sum(),'of',len(g)); print(p[p.client_ip.isin(g[g>1].index)].groupby('client_ip').client_network.unique().head(8).to_string())
# UA per ip / per account
ua=b.groupby('client_ip').agg(n=('event','size'),uas=('user_agent_family','nunique'))
print('addresses with >=4 rows:',(ua.n>=4).sum(),'; of those with a single UA:',((ua.n>=4)&(ua.uas==1)).sum(),'; with >=3 UAs:',((ua.n>=4)&(ua.uas>=3)).sum())
acc=b[b.account_ref!=''].sort_values('time_utc')
first2=acc.groupby('account_ref').head(2); pv=first2.groupby('account_ref').user_agent_family.agg(list)
pv=pv[pv.map(len)==2]; print('register and submit (first two events, minutes apart) use the same UA:',round(np.mean([a==c for a,c in pv]),3),'of',len(pv))
# expected same-UA rate if independent
vc=b.user_agent_family.value_counts(normalize=True); print('expected if drawn independently:',round((vc**2).sum(),3))
# session shape: GET before POST?
print('GET /account/register page views (benign):',((b.path=='/account/register')&(b.method=='GET')).sum(),'vs POST',((b.path=='/account/register')&(b.method=='POST')).sum())
print('GET /applications:',((b.path=='/applications')&(b.method=='GET')).sum(),'; GET /login',((b.path=='/login')&(b.method=='GET')).sum(),'vs POST /login',((b.path=='/login')&(b.method=='POST')).sum())
# anonymous page views by address: do applicants ever browse info pages from the same address?
anon=b[b.account_ref=='']; regips=set(b[b.event=='account_created'].client_ip)
print('anonymous page-view rows',len(anon),'from addresses that also registered:',anon.client_ip.isin(regips).sum())
print('anonymous rows per address:',anon.groupby('client_ip').size().describe()[['mean','50%','max']].round(2).to_dict())
# address persistence for accounts
print('accounts with >1 address:',(acc.groupby('account_ref').client_ip.nunique()>1).sum(),'of',acc.account_ref.nunique())
lg=acc[acc.event=='login_success']; print('logins per account: mean',round(len(lg)/acc.account_ref.nunique(),2), lg.groupby('account_ref').size().value_counts().sort_index().head(8).to_dict())
# every login_success followed by exactly one /status page view?
nxt=acc.groupby('account_ref').event.apply(lambda s: list(s))
c=collections.Counter()
for L in nxt:
    for a_,b_ in zip(L,L[1:]):
        if a_=='login_success': c[b_]+=1
    if L[-1]=='login_success': c['<end>']+=1
print('event following login_success:',dict(c))
gp=acc.assign(prev=acc.groupby('account_ref').event.shift(), dt=(acc.t-acc.groupby('account_ref').t.shift()).dt.total_seconds())
x=gp[(gp.prev=='login_success')&(gp.event=='page_view')].dt; print('login->status gap s: min',x.min(),'p50',x.median(),'max',x.max())
x=gp[(gp.prev=='login_failed')&(gp.event=='login_success')].dt; print('failed->success gap s: min',x.min(),'p50',x.median(),'max',x.max(),'n',len(x))
print('status codes benign:',b.status.value_counts().to_dict())
print('seconds field == 00 share:',(b.time_utc.str[17:19]=='00').mean().round(4))
# network share before / after registration
print((pd.crosstab(b.client_network,b.ld>='2027-11-13',normalize='columns')*100).round(1).to_string())
# time zone / language
print('/es/ayuda share of page views by month:',(b[b.path=='/es/ayuda'].groupby(b.time_utc.str[:7]).size()/b[b.event=='page_view'].groupby(b.time_utc.str[:7]).size()).round(3).to_dict())
print('page_view path mix pre-Nov:',b[(b.event=='page_view')&(b.ld<'2027-11-01')].path.value_counts(normalize=True).round(3).to_dict())
