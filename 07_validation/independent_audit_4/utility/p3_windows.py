#!/usr/bin/env python3
"""Item 13 + pass 3: Windows Security internals over the whole span."""
import sys,collections,pickle,statistics,datetime; sys.path.insert(0,sys.path[0])
from lib import *
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
print('events',len(W))
# record ids per host monotonic & ordering
last={};viol=0;dupr=0;seen=set()
for d in W:
    k=d['host']
    if k in last and d['record_id']<=last[k]: viol+=1
    last[k]=d['record_id']
print('record_id not strictly increasing per host (file order):',viol)
srt=all(W[i]['time_utc']<=W[i+1]['time_utc'] for i in range(len(W)-1)); print('time ordered overall (within month files):',srt)
# duplicates of 4624 per logon id
lg=collections.defaultdict(list)
for d in W:
    if d['event_id']==4624: lg[(d['host'],d['logon_id'])].append(d)
multi={k:v for k,v in lg.items() if len(v)>1}
print('4624:',sum(len(v) for v in lg.values()),'distinct (host,logon_id)',len(lg),'ids with >1 4624',len(multi))
# pairing
lo=collections.defaultdict(list)
for d in W:
    if d['event_id'] in(4634,4647): lo[(d['host'],d['logon_id'])].append(d)
nolog=[k for k in lo if k not in lg]; noout=[k for k in lg if k not in lo]
print('logoffs without logon',len(nolog),'logons without logoff',len(noout),'by type',collections.Counter(lg[k][0]['logon_type'] for k in noout))
neg=0;durs=collections.defaultdict(list)
for k,v in lg.items():
    if k in lo:
        a=E(v[0]['time_utc']); b=max(E(x['time_utc']) for x in lo[k])
        if b<a: neg+=1
        durs[v[0]['logon_type']].append(b-a)
print('logoff before logon',neg,{t:(len(v),round(statistics.median(v)),round(max(v))) for t,v in durs.items()})
# logon id reuse across hosts / format
ids=collections.Counter(d['logon_id'] for d in W if d['event_id']==4624); print('logon_id shapes',collections.Counter(len(i) for i in ids).most_common(4),'ids used on >1 host',sum(1 for i in ids if len({k[0] for k in lg if k[1]==i})>1) if len(ids)<5000 else 'skip')
# user/domain consistency
dom=collections.Counter((d.get('domain'),d['user'][:3]=='GW-') for d in W if d['event_id']==4624); print('domain x OTacct',dom)
reg_=reg(); zone={x['hostname']:x['zone'] for x in reg_['hosts']}; hip={x['hostname']:x['ip'] for x in reg_['hosts']}
print('4624 type x zone-class',collections.Counter((d['logon_type'],'ot' if zone.get(d['host'],'').startswith('ot') else 'corp') for d in W if d['event_id']==4624).most_common(12))
print('OT accounts logging on to corp hosts',sum(1 for d in W if d['event_id']==4624 and d['user'].startswith('GW-') and not zone.get(d['host'],'').startswith('ot')),'corp users on OT hosts',collections.Counter((d['host'],d['logon_type']) for d in W if d['event_id']==4624 and not d['user'].startswith(('GW-','svc_')) and not d['user'].endswith('$') and zone.get(d['host'],'').startswith('ot')).most_common(6))
# 4625
f=[d for d in W if d['event_id']==4625]; hosts=collections.Counter(d['host'] for d in f)
lockhosts={d['host'] for d in W if d['event_id'] in(4800,4801)}
print('4625',len(f),'from hosts',len(hosts),'| hosts with 4800/4801',len(lockhosts),'| type-7 failures on hosts with no lock events',sum(1 for d in f if d['logon_type']==7 and d['host'] not in lockhosts))
print('4625 has domain key?',sum('domain' in d for d in f),'src_ip?',sum('src_ip' in d for d in f))
# group events
ge=[d for d in W if d['event_id'] in(4728,4732,4756)]; print('group events',len(ge),'empty subject',sum(1 for d in ge if not d.get('user')),'subjects',len({d['user'] for d in ge}),'from hosts',len({d.get('src_host') for d in ge}))
it={u['username']:u['department'] for u in reg_['users']}
print('  subject departments',collections.Counter(it.get(d['user'],'?') for d in ge).most_common(5))
print('4771',sum(d['event_id']==4771 for d in W),'4740',sum(d['event_id']==4740 for d in W),'| 4771 per (user,day) before a lockout: median',)
# 4672 with logon
adm=collections.Counter(d['user'] for d in W if d['event_id']==4672); print('4672 users',len(adm),'privileges values',len({d['privileges'] for d in W if d['event_id']==4672}))
# 4768/4769 relation, 4769 before 4768
print('4768',sum(d['event_id']==4768 for d in W),'4769',sum(d['event_id']==4769 for d in W),'hosts logging them',collections.Counter(d['host'] for d in W if d['event_id'] in(4768,4769)).most_common(6))
# 4624 type 3 with src_ip not resolvable
ips={x['ip'] for x in reg_['hosts']}
t3=[d for d in W if d['event_id']==4624 and d.get('src_ip')]
unk=collections.Counter(d['src_ip'] for d in t3 if d['src_ip'] not in ips and not d['src_ip'].startswith('10.14.250.')); print('4624 src_ip not registry/VPN pool:',sum(unk.values()),len(unk),'hosts',collections.Counter(d['host'] for d in t3 if d['src_ip'] in unk).most_common(4))
# local-time distribution of interactive logons (type 2) on corp workstations
import zoneinfo
tz=zoneinfo.ZoneInfo('America/Chicago')
hh=collections.Counter(); wd=collections.Counter(); byday=collections.Counter()
for d in W:
    if d['event_id']==4624 and d['logon_type']==2 and d['host'].startswith('GW-WS-IT'):
        t=datetime.datetime.fromtimestamp(E(d['time_utc']),tz); hh[t.hour]+=1; wd[t.weekday()]+=1; byday[t.date().isoformat()]+=1
print('office interactive logons by local hour',sorted(hh.items())); print('by weekday (0=Mon)',sorted(wd.items()))
pickle.dump(dict(byday),open('/tmp/c/office_logons_byday.pkl','wb'))
for day in ('2027-09-06','2027-09-07','2027-09-13','2027-09-14','2027-09-15','2027-09-16','2027-09-20','2027-11-25','2027-11-26','2027-12-24','2027-12-25','2027-12-31','2028-01-01','2027-11-11','2027-10-11','2027-07-19'):
    print('  ',day,datetime.date.fromisoformat(day).strftime('%a'),byday.get(day,0))
wk=[v for k,v in byday.items() if datetime.date.fromisoformat(k).weekday()<5]; print('  weekday median',statistics.median(wk),'weekend median',statistics.median([v for k,v in byday.items() if datetime.date.fromisoformat(k).weekday()>=5]))
