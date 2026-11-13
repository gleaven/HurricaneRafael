# Pass 3 misc: mac UA, resolvers, volumes vs size, holidays for workstation logons, names, TLDs
import sys,re,collections; sys.path.insert(0,'.')
from common import *
R=reg(); w=load('web'); a=load('auth'); d=load('dns'); m=load('mail'); f=load('firewall'); e=load('endpoint_alerts')
b=[o for o in R['organisations'] if o['org_id']=='BRW'][0]
mac={h['ip'] for h in b['hosts'] if 'macOS' in h['os']}
x=w[(w.org=='brw')&w.client_ip.isin(mac)]; print('BRW macOS hosts',len(mac),'web rows',len(x),'UA',x.user_agent_family.value_counts().to_dict())
x=a[(a.org=='brw')&a.src_ip.isin(mac)]; print(' auth device labels on mac hosts',x.device.value_counts().to_dict(),'event ids',x.event_id.value_counts().to_dict())
x=e[(e.org=='brw')&e.ip.isin(mac)]; print(' endpoint details on mac hosts',x.detail.str.replace(r'\d+','N',regex=True).value_counts().head(6).to_dict())
lin={h['ip'] for o in R['organisations'] for h in o['hosts'] if 'Linux' in h['os']}
print('endpoint events from Linux hosts:',e[e.ip.isin(lin)].shape[0],'| web rows from servers:',w[w.client_ip.isin({h['ip'] for o in R['organisations'] for h in o['hosts'] if h['device_type']=='server'})].groupby('org').size().to_dict())
for o in R['organisations']:
    k=o['org_id'].lower(); ips={h['ip']:h for h in o['hosts']}
    rs=d[d.org==k].resolver.value_counts()
    print(k,'registry resolvers',o['dns_resolvers'],'| log resolvers',{r:(n,ips[r]['role'][:30]) for r,n in rs.items()})
print('\nvolumes vs size (rows / 181 days):')
for o in R['organisations']:
    k=o['org_id'].lower(); nws=sum(1 for h in o['hosts'] if 'workstation' in h['device_type'] or h['device_type']=='console'); nacc=len(o['accounts'])
    print(f" {k}: accounts {nacc}, workstations {nws}, ws-users {sum(a_.get('workstation_user',False) for a_ in o['accounts'])}; per day: web {len(w[w.org==k])/181:.0f}, dns {len(d[d.org==k])/181:.0f}, mail {len(m[m.org==k])/181:.0f}, fw {len(f[f.org==k])/181:.0f}, ws logons {((a.org==k)&(a.event_id=='4624')&(a.logon_type=='2')).sum()/181:.0f}, remote {((a.org==k)&(a.logon_type=='remote')).sum()/181:.0f}; remote-users {a[(a.org==k)&(a.logon_type=='remote')].account.nunique()}; mail/account/day x25 {len(m[m.org==k])/181/nacc*25:.1f}; web/ws/day x40 {len(w[(w.org==k)&(w.user!='-')])/181/max(nws,1)*40:.0f}")
# ws logons on holidays
t=ts(a); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); a['ld']=(t-pd.to_timedelta(off,unit='h')).dt.strftime('%Y-%m-%d')
x=a[(a.event_id=='4624')&(a.logon_type=='2')]; dd=x.groupby(['ld','org']).size().unstack(fill_value=0); dd.index=pd.to_datetime(dd.index)
print('\nws logons: weekday mean',dd[dd.index.dayofweek<5].mean().round(0).to_dict()); print(' weekend mean',dd[dd.index.dayofweek>=5].mean().round(0).to_dict())
print(dd.loc[dd.index.isin(pd.to_datetime(['2027-09-06','2027-10-11','2027-11-11','2027-11-25','2027-11-26','2027-12-24','2027-12-25','2027-12-31','2028-01-01']))].to_string())
# names
hosts=set(w.host)|set(d['query']); tl=collections.Counter(h.rsplit('.',1)[-1] for h in hosts); print('\nhost TLDs:',dict(tl))
print('non-.example web hosts sample:',sorted(h for h in set(w.host) if not h.endswith('.example'))[:60])
md=set(m.sender_domain)|set(m.recipient.str.split('@').str[1]); print('mail domain TLDs:',dict(collections.Counter(x.rsplit('.',1)[-1] for x in md)))
real=r'(?i)microsoft|google|apple|amazon|aws|azure|cisco|palo ?alto|fortinet|crowdstrike|symantec|mcafee|defender|sophos|trend ?micro|oracle|adobe|zoom|slack|dropbox|facebook|twitter|linkedin|netflix|youtube|walmart|fedex|ups\b|dhl|at&t|verizon|comcast|chevron|exxon|valero|citgo|flint hills|cheniere|epic|cerner|meditech|servicenow|salesforce|workday|okta|duo\b|outlook|office ?365|gmail|yahoo|windows|chrome|firefox|safari|edge'
for nm,s in [('web host',pd.Series(sorted(set(w.host)))),('mail domain',pd.Series(sorted(md))),('mail subject',pd.Series(m.subject.unique())),('attachment',pd.Series(m.attachment_names.unique())),('endpoint detail',pd.Series(e.detail.unique())),('fw rule/app',pd.Series(list(set(f.rule_name))+list(set(f.app)))),('web category/policy',pd.Series(list(set(w.category))+list(set(w.policy))))]:
    hit=s[s.str.contains(real)]; print(nm,'real-name hits:',len(hit),hit.head(12).tolist())
# sender local parts: people names?
print('outside sender local-part shapes:',m[m.direction=='inbound'].sender.str.split('@').str[0].str.replace(r'^[a-z]\.[a-z]+$','<i.surname>',regex=True).value_counts().head(12).to_dict())
