#!/usr/bin/env python3
"""Item 5 / guide claim: alerts about historian bulk reads, monitored file writes, alarm-suppression changes, new VPN locations each correspond to one audit row."""
import sys,collections,re; sys.path.insert(0,sys.path[0])
from lib import *
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
g=lambda r,c:r[ix[c]]
ha=audit('historian_access')
bulk=[a for a in ha if a['query_type']=='bulk read']
al=[r for r in S if g(r,'rule_id')=='SE3-OT-1104']
key=collections.Counter()
used=set(); un=[]
for r in al:
    d=g(r,'detail'); du=re.search(r'session_duration=(\d+)s',d).group(1); tq=re.search(r'tags_queried=(\d+)',d).group(1)
    c=[a for a in bulk if a['duration_s']==du and a['tags_queried']==tq and abs(E(a['start_utc'])-E(g(r,'time_utc')))<120]
    if len(c)==1: used.add(c[0]['session_id']); key[(g(r,'src_host')==c[0]['client_host'], g(r,'user')==c[0]['account'])]+=1
    else: un.append((g(r,'alert_id'),d[:60],len(c)))
print('HISTORIAN: 1104 alerts',len(al),'matched 1:1',len(used),'unmatched',len(un),un[:3],'| bulk rows w/o alert',len(bulk)-len(used),'| (src==client, user==account)',dict(key))
ml=[r for r in S if g(r,'rule_id')=='SE3-ML-0044']; sid={a['session_id']:a for a in ha}
print('  ML alerts',len(ml),'with existing session id',sum(1 for r in ml if re.search(r'session_id=(\S+)',g(r,'detail')).group(1) in sid))
# alarm suppression
sa=audit('alarm_suppression_audit'); al=[r for r in S if g(r,'rule_id')=='SE3-OT-3301']
bt=collections.Counter((a['time_utc'][:16],a['changed_by'],a['source_host']) for a in sa)
print('ALARM SUPP: audit rows',len(sa),'distinct (minute,user,host) batches',len(bt),'alerts',len(al))
am=0;aun=[]
for r in al:
    t=E(g(r,'time_utc')); c=[a for a in sa if abs(E(a['time_utc'])-t)<=180]
    if c: am+=1
    else: aun.append((g(r,'alert_id'),g(r,'src_host'),g(r,'user'),g(r,'detail')[:90],g(r,'disposition')))
print('  alerts with an audit row within 3 min',am,'without',len(aun)); [print('    ',x) for x in aun[:12]]
bun=[k for k in bt if not any(abs(E(k[0]+':30Z')-E(g(r,'time_utc')))<=240 for r in al)]
print('  audit batches without alert',len(bun),bun[:10])
# suppressed count consistency
cnt_bad=[]
last={}
srt=sorted(sa,key=lambda a:a['time_utc'])
for r in al:
    m=re.search(r'suppressed_alarm_count=(\d+)',g(r,'detail'))
    if not m: continue
    prior=[a for a in srt if a['time_utc']<=g(r,'time_utc')]
    if prior and int(prior[-1]['active_suppressions_after'])!=int(m.group(1)): cnt_bad.append((g(r,'alert_id'),m.group(1),prior[-1]['active_suppressions_after'],prior[-1]['time_utc']))
print('  alerts whose suppressed_alarm_count != audit running count:',len(cnt_bad),cnt_bad[:8])
# running count arithmetic in audit
bad=0;prev=None
for a in srt:
    n=int(a['active_suppressions_after'])
    if prev is not None and n!=prev+(1 if a['action']=='ADD' else -1): bad+=1
    prev=n
print('  audit running-count arithmetic errors',bad,'first count',srt[0]['active_suppressions_after'],'max',max(int(a['active_suppressions_after']) for a in sa))
# REMOVE of a point never added / ADD twice
state=set();err=collections.Counter()
for a in srt:
    p=a['alarm_point'].split(' ')[0]
    if a['action']=='ADD':
        if p in state: err['add twice']+=1
        state.add(p)
    else:
        if p not in state: err['remove not present']+=1
        state.discard(p)
print('  state errors',dict(err),'remaining at end',len(state))
# file integrity
fi=audit('file_integrity'); al=[r for r in S if g(r,'rule_id')=='SE3-OT-2201']
fk={a['time_utc']:a for a in fi}
m=sum(1 for r in al if any(abs(E(a['time_utc'])-E(g(r,'time_utc')))<=5 and a['path'].lower() in g(r,'detail').lower() for a in fi if a['time_utc'][:13]==g(r,'time_utc')[:13]))
print('FILE INTEGRITY: rows',len(fi),'alerts',len(al),'alerts matching row on time(5s)+path',m, 'sample detail:',g(al[0],'detail')[:150])
print('  seconds==00 rows',sum(a['time_utc'][17:19]=='00' for a in fi))
import re as _re
print('  path name shapes',collections.Counter(_re.sub(r'[0-9a-f]{8}','H',a['path'].split('\\')[-1]) for a in fi).most_common(8))
print('  hash shapes: new_hash==previous of later row chain check')
ph=collections.defaultdict(list)
for a in sorted(fi,key=lambda a:a['time_utc']): ph[a['path']].append(a)
print('  paths with >1 event',sum(1 for v in ph.values() if len(v)>1),'MODIFIED with no prior CREATED in file',sum(1 for v in ph.values() if v[0]['event']=='MODIFIED'))
# vpn new location
va=audit('employee_vpn_sessions'); al=[r for r in S if g(r,'rule_id')=='SE3-NET-3025']
vk={(a['account'],a['login_utc'][:16]) for a in va}
print('VPN NEW LOCATION alerts',len(al),'sample',g(al[0],'user'),g(al[0],'detail')[:120])
m=0
for r in al:
    t=E(g(r,'time_utc'))
    if any(a['account']==g(r,'user') and abs(E(a['login_utc'])-t)<=120 for a in va if a['login_utc'][:10]==g(r,'time_utc')[:10]): m+=1
print('  matched to a VPN session (user, login within 2 min)',m)
