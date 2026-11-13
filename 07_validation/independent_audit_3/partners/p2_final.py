from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import csv,glob
R=reg()
fw=load('brw','firewall')[1]; web=load('brw','web')[1]
edge=[r for r in fw if r['device']=='BRW-FW-EDGE-01' and r['dst_ip']=='192.0.2.70']
print('BRW edge->gateway rows',len(edge),'by dst_port/app',Counter((r['dst_port'],r['app']) for r in edge),'| DMZ side ports',Counter(r['dst_port'] for r in fw if r['device']=='BRW-FW-DMZ-01' and r['src_ip'].startswith('198.51.100.')))
for r in edge:
    if r['dst_port']!='443': print('   ',r['_f'],r['_n'],r['time_utc'],r['src_ip'],r['dst_port'],r['app'],r['nat_src_ip'])
gw=[r for r in web if r['host'].startswith('rmt-gw')]
print(' web rows to rmt-gw',len(gw),Counter((r['scheme'],r['method']) for r in gw))
print('BRW fw rows with nat_src_ip 198.51.100.44:',sum(1 for r in fw if r['nat_src_ip']=='198.51.100.44'),'| to aid portal 192.0.2.130 from nat .44:',[(r['time_utc'],r['src_ip']) for r in fw if r['nat_src_ip']=='198.51.100.44' and r['dst_ip']=='192.0.2.130'])
da=[r for r in web if 'disasteraid' in r['host']]
print(' BRW web rows to portal.disasteraid.example 2027-11-13..11-16:',[(r['time_utc'],r['client_ip'],r['user']) for r in da if '2027-11-13'<=r['time_utc'][:10]<='2027-11-16'])
P=ROOT+"/05_other_sources/network_logs/portal/"
rows=[]
for f in sorted(glob.glob(P+'aid_portal_access_2027-1[12].csv')):
    with open(f,newline='') as fh:
        for r in csv.DictReader(fh):
            if r['client_ip']=='198.51.100.44': rows.append(r)
print(' aid portal rows from 198.51.100.44:',len(rows),'first',rows[0]['time_utc'],'last',rows[-1]['time_utc'],Counter(r['time_utc'][:10] for r in rows).most_common(5),'UA',Counter(r['user_agent_family'] for r in rows).most_common(3))
# city CH workstations silent during power window?
for o,s,lo,hi in [('city','CH','2027-09-14T06:48','2027-09-18T15:20'),('county','CTH','2027-09-14T06:55','2027-09-18T17:05'),('port','ADM','2027-09-14T06:41','2027-09-18T20:00')]:
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]
    ws={h['host_id'] for h in O['hosts'] if h['site_id']==s and h['device_type'] in('workstation','console')}; ips={h['ip'] for h in O['hosts'] if h['host_id'] in ws}
    a=load(o,'auth')[1]; w=load(o,'web')[1]; d=load(o,'dns')[1]; f=load(o,'firewall')[1]
    n=sum(1 for r in a if r['host'] in ws and lo<=r['time_utc']<=hi)+sum(1 for r in w if r['client_ip'] in ips and lo<=r['time_utc']<=hi)+sum(1 for r in d if r['client_ip'] in ips and lo<=r['time_utc']<=hi)
    infra=sum(1 for r in f if lo<=r['time_utc']<=hi); res=Counter(r['resolver'] for r in d if lo<=r['time_utc']<=hi)
    print(f"{o} {s} workstation events in stated power-out window: {n}; edge firewall rows in same window: {infra}; DNS resolver answers: {dict(res)}; site of fw/resolvers in registry: {[ (h['host_id'],h['site_id']) for h in O['hosts'] if h['device_type']=='firewall' or 'resolver' in h['role']]}")
# sampling check: user web requests per workstation-weekday pre-storm
for o in ['city','srmc']:
    w=load(o,'web')[1]
    n=sum(1 for r in w if r['user']!='-' and '2027-08-02'<=r['time_utc'][:10]<='2027-08-06'); hosts=len({r['client_ip'] for r in w})
    a=load(o,'auth')[1]; l=sum(1 for r in a if r['event_id']=='4624' and r['logon_type']=='2' and '2027-08-02'<=r['time_utc'][:10]<='2027-08-06')
    print(o,'week of 08-02..06: user web rows',n,'hosts',hosts,'=> %.2f web rows per host-day;'%(n/hosts/5),'type-2 logons',l,'=> %.2f per host-day'%(l/hosts/5))
