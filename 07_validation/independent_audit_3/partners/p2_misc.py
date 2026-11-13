from lib import *
from collections import Counter,defaultdict
from datetime import timedelta,date
import ipaddress, statistics as st
R=reg()
# EVT-0107 vendor mail time
m=load('brw','mail')[1]
print('BRW lure:',[(r['time_utc'],r['recipient'],r['subject'],r['verdict'],r['message_id']) for r in m if r['sender_domain']=='marine-certification-notices.example'])
a=load('brw','auth')[1]
print(' m.okoye ws events 08-12:',[(r['time_utc'],r['host'],r['event_id']) for r in a if r['account']=='m.okoye' and r['time_utc'][:10]=='2027-08-12'])
print(' m.okoye registered ws:',[(h['host_id'],h['ip']) for h in [o for o in R['organisations'] if o['org_id']=='BRW'][0]['hosts'] if 'm.okoye' in h.get('users',[])])
# EVT-0205 NAS ADM logons by day
O=[x for x in R['organisations'] if x['org_id']=='NASCC'][0]; site={h['host_id']:h['site_id'] for h in O['hosts']}
a=load('nascc','auth')[1]
c=defaultdict(Counter)
for r in a:
    if r['event_id']=='4624' and r['logon_type']=='2': c[site[r['host']]][(ts(r['time_utc'])-timedelta(hours=5)).strftime('%m-%d')]+=1
for s in ['ADM','OPS','SUP','PWD']:
    print(' NAS',s,'logons/day 09-06..09-24:',[c[s].get(f'09-{d:02d}',0) for d in range(6,25)], 'hosts',sum(1 for h in O['hosts'] if h['site_id']==s and h['device_type'] in('workstation','console')))
# EVT-1602 hospital admin endpoint events during no-power window
for o in ['srmc','bcmc']:
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]; site={h['host_id']:h['site_id'] for h in O['hosts']}
    e=load(o,'endpoint_alerts')[1]; a=load(o,'auth')[1]; w=load(o,'web')[1]; ips={h['ip']:h['site_id'] for h in O['hosts']}
    win=[r for r in e if '2027-09-14T06:40'<=r['time_utc']<='2027-09-16T06:00']
    print(o,'endpoint events 09-14T06:40..09-16T06:00 by site/event',Counter((site[r['host']],r['event']) for r in win).most_common())
    aw=[r for r in a if '2027-09-14T06:40'<=r['time_utc']<='2027-09-16T06:00' and site.get(r['host'])=='ADM']; ww=[r for r in w if '2027-09-14T06:40'<=r['time_utc']<='2027-09-16T06:00' and ips.get(r['client_ip'])=='ADM']
    print('   ADM auth events in window',len(aw),'web',len(ww))
    # clinical gap after power loss
    lost={'srmc':'2027-09-14T06:17:03Z','bcmc':'2027-09-14T06:31:40Z'}[o]
    ev=sorted([r['time_utc'] for r in a if site.get(r['host'])=='CLIN']+[r['time_utc'] for r in w if ips.get(r['client_ip'])=='CLIN'])
    before=[x for x in ev if x<=lost][-1]; after=[x for x in ev if x>lost][0]
    lo=[r for r in a if site.get(r['host'])=='CLIN' and r['event_id']=='4634' and lost[:16]<=r['time_utc']<=after]
    print('   CLIN last event before power loss',before,'first after',after,'(min after loss: %.1f)'%((ts(after)-ts(lost)).total_seconds()/60),'logoffs written in gap',len(lo))
    # sessions open at power loss: logoff later?
# port gate web
O=[x for x in R['organisations'] if x['org_id']=='PORT'][0]; ips={h['ip']:h['site_id'] for h in O['hosts']}
w=load('port','web')[1]; c=Counter()
for r in w:
    if ips.get(r['client_ip'])=='GATE' and r['user']!='-': c[(ts(r['time_utc'])-timedelta(hours=5)).date()]+=1
def mean(a_,b_):
    d=date.fromisoformat(a_); tot=0;n=0
    while d<=date.fromisoformat(b_):
        tot+=c.get(d,0); n+=1; d+=timedelta(days=1)
    return tot/n
print('port GATE user web/day: pre %.1f | 9/11-9/13 %s | D0-D3 %.1f | D4-D29 %.1f | D30-D43 %.1f | D44-D57 %.1f | D58+ %.1f'%(mean('2027-07-19','2027-09-10'),[c.get(date(2027,9,d),0) for d in (11,12,13)],mean('2027-09-14','2027-09-17'),mean('2027-09-18','2027-10-13'),mean('2027-10-14','2027-10-27'),mean('2027-10-28','2027-11-10'),mean('2027-11-11','2027-12-17')))
wd=Counter(); 
for d,v in c.items():
    if d<date(2027,9,10): wd[d.weekday()]+=v
print(' gate web by weekday pre-storm',sorted(wd.items()))
# IP sanity
pubs={o['org_id']:ipaddress.ip_network(o['address_plan']['public_block']) for o in R['organisations']}
ints={o['org_id']:ipaddress.ip_network(o['address_plan']['internal']) for o in R['organisations']}
print('public blocks',pubs); 
print('internal overlaps',[(a_,b_) for a_ in ints for b_ in ints if a_<b_ and ints[a_].overlaps(ints[b_])])
bad=Counter(); coll=Counter(); firstoct=Counter()
allext=set()
for o in ORGS:
    f=load(o,'firewall')[1]
    for r in f:
        for col in ('src_ip','dst_ip'):
            ip=r[col]
            if ip.startswith('10.'): continue
            allext.add(ip)
for ip in allext:
    a_=ipaddress.ip_address(ip); firstoct[ip.split('.')[0]]+=1
    if a_.is_private or a_.is_multicast or a_.is_reserved or a_.is_loopback or a_.is_link_local: bad[ip]+=1
    for k,n in pubs.items():
        if a_ in n: coll[k]+=1
print('distinct external IPs in firewalls',len(allext),'reserved/private/doc (python is_private etc.)',len(bad),Counter('.'.join(i.split('.')[:3]) for i in bad).most_common(6))
print('external IPs inside a partner public block',coll)
print('first octets used',len(firstoct),sorted(firstoct, key=int))
# does any org's log contain another org's public block address?
for o in ORGS:
    f=load(o,'firewall')[1]; own=pubs[o.upper()]
    x=Counter()
    for r in f:
        for col in ('src_ip','dst_ip'):
            ip=r[col]
            if ip.startswith('10.'): continue
            a_=ipaddress.ip_address(ip)
            for k,n in pubs.items():
                if k!=o.upper() and a_ in n: x[(k,col)]+=1
    if x: print(' ',o,'rows touching another org block',x)
# NAT stickiness
for o in ['city','brw']:
    f=load(o,'firewall')[1]; per=defaultdict(Counter)
    for r in f:
        if r['nat_src_ip']: per[r['src_ip']][r['nat_src_ip']]+=1
    print(o,'clients',len(per),'median distinct NAT addresses per client',st.median(len(v) for v in per.values()),'max',max(len(v) for v in per.values()))
