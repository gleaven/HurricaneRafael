#!/usr/bin/env python3
"""file_integrity.csv vs Windows 5145 WriteData on GW-SRV-OT-01 vs conn flows; rvela presence on hostile-session days after leave; scada command volume in storm."""
import sys,collections,pickle,json; sys.path.insert(0,sys.path[0])
from lib import *
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
fi=audit('file_integrity')
wr=[d for d in W if d['event_id']==5145 and d['host']=='GW-SRV-OT-01']
print('5145 on OT-01',len(wr),collections.Counter((d['access'],d['share']) for d in wr).most_common(12))
fk=collections.defaultdict(list)
for a in fi: fk[a['path'].split('\\',4)[-1].lower() if a['path'].count('\\')>=4 else a['path']].append(a)
def rel(a): 
    p=a['path'].split('\\'); return (p[3], '\\'.join(p[4:]))
fset=collections.defaultdict(list)
for a in fi: fset[rel(a)].append(E(a['time_utc']))
m=0;un=[]
for d in wr:
    if d['access']!='WriteData': continue
    k=(d['share'].split('\\')[-1],d['path'])
    if any(abs(t-E(d['time_utc']))<=5 for t in fset.get(k,[])): m+=1
    else: un.append((d['time_utc'],d['user'],d['src_ip'],d['share'],d['path']))
print('WriteData events',sum(d['access']=='WriteData' for d in wr),'with FIM row (share,path,5s)',m,'without',len(un)); [print('   ',x) for x in un[:8]]
wset=collections.defaultdict(list)
for d in wr:
    if d['access']=='WriteData': wset[(d['share'].split('\\')[-1],d['path'])].append(E(d['time_utc']))
fm=sum(1 for a in fi if any(abs(t-E(a['time_utc']))<=5 for t in wset.get(rel(a),[])))
print('FIM rows',len(fi),'with a 5145 WriteData',fm)
shares=collections.Counter(rel(a)[0] for a in fi); print('FIM shares',shares)
print('extensions x diff_summary present',collections.Counter((a['path'].rsplit('.',1)[-1],bool(a['diff_summary'])) for a in fi).most_common(14))
print('diff on files in share',collections.Counter((rel(a)[0],a['diff_summary'][:40]) for a in fi if a['diff_summary']).most_common(8))
# rvela on days of hostile sessions after leave
for day in ('2027-09-21','2027-09-23','2027-09-24','2027-10-02'):
    ev=collections.Counter((d['host'],d['event_id'],d.get('logon_type')) for d in W if d['time_utc'][:10]==day and d.get('user') in('rvela',) )
    print(day,'rvela windows events',dict(ev))
V=audit('employee_vpn_sessions'); print('rvela VPN sessions around',[(s['login_utc'],s['src_ip'],s['device']) for s in V if s['account']=='rvela' and '2027-09-18'<=s['login_utc']<='2027-10-05'])
lv=[(d['time_utc'],d['host'],d['logon_type']) for d in W if d.get('user')=='rvela' and d['event_id']==4624 and d['logon_type'] in(2,10,11) and '2027-08-25'<=d['time_utc']<='2027-10-06']
print('rvela interactive logons 08-25..10-06:',[(t[:16],h) for t,h,l in lv])
sc=audit('scada_command_log'); c=collections.Counter(r['time_utc'][:10] for r in sc); print('scada commands per day 09-08..09-30',[c['2027-09-%02d'%d] for d in range(8,31)],'mean/day overall',round(len(sc)/181,2))
print('commands on SUB01 devices 09-14..09-20',[(r['time_utc'],r['command'],r['device'],r['operator'],r['origin']) for r in sc if '2027-09-14'<=r['time_utc']<'2027-09-21' and 'SUB01' in r['device']])
print('breaker close after hostile opens:',[(r['time_utc'],r['command'],r['device'],r['operator']) for r in sc if r['device'] in('GW-SUB02-CB-7','GW-SUB03-CB-12') and r['time_utc']>'2027-09-21'])
