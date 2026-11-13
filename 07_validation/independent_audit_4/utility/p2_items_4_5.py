#!/usr/bin/env python3
"""Re-test of items 4,5 (SIEM notes/dispositions, exception scope, audit<->SIEM joins) and canon SIEM numbers."""
import sys,collections,re; sys.path.insert(0,sys.path[0])
from lib import *
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
g=lambda r,c:r[ix[c]]
print('alerts',len(S))
cn=collections.Counter(g(r,'close_note') for r in S)
si=[k for k in cn if re.match(r'SI-2027-',k)]
print('ITEM4 close_note distinct',len(cn),'; notes used <=40 times that are not "SI-... opened":',sorted([(k,v) for k,v in cn.items() if v<=40 and not k.startswith('SI-2027')],key=lambda x:x[1])[:30])
print('  SI-xxxx opened notes',len(si),'ESCALATED',sum(1 for r in S if g(r,'disposition')=='ESCALATED'))
print('  notes 41..700:',sorted([(k,v) for k,v in cn.items() if 40<v<=700],key=lambda x:x[1]))
pr=collections.Counter((g(r,'priority')) for r in S); print('  priority',pr)
for rule in ('SE3-OT-1104','SE3-NET-9941','SE3-OT-3301','SE3-OT-2201','SE3-ML-0044'):
    c=collections.Counter((g(r,'disposition')) for r in S if g(r,'rule_id')==rule); print('  ',rule,dict(c))
# exception scope: 0892 active 2027-08-19T11:34:20 .. 2027-10-18T15:20:00
A='2027-08-19T11:34:20Z';B='2027-10-18T15:20:00Z'
w=[r for r in S if g(r,'rule_id')=='SE3-OT-1104' and A<=g(r,'time_utc')<=B]
print('  SE3-OT-1104 in exception window',len(w),collections.Counter((g(r,'src_host'),g(r,'disposition'),g(r,'close_note')[:40]) for r in w).most_common(12))
out=[r for r in S if g(r,'rule_id')=='SE3-OT-1104' and not(A<=g(r,'time_utc')<=B) and g(r,'src_host')=='GW-SYS-JMP-01']
print('  JMP-sourced 1104 outside window',collections.Counter((g(r,'disposition')) for r in out))
c2=[r for r in S if g(r,'dst_ip')=='104.21.88.43']
print('  C2 alerts',len(c2),collections.Counter((g(r,'disposition'),g(r,'close_note')[:45],g(r,'closed_by')) for r in c2).most_common(8))
fl=[r for r in S if g(r,'rule_id')=='SE3-NET-9941']
dip=collections.Counter(g(r,'dst_ip') for r in fl); print('  FLAGGED_IP alerts',len(fl),'distinct dst',len(dip),'top',dip.most_common(6),'dst seen>=10:',sum(1 for v in dip.values() if v>=10))
wl=collections.Counter(g(r,'close_note') for r in fl); print('  FLAGGED_IP close notes',wl.most_common(8))
# ITEM5: historian alerts vs audit
ha=audit('historian_access'); hs={r['session_id']:r for r in ha}
al=[r for r in S if g(r,'rule_id') in('SE3-OT-1104','SE3-ML-0044')]
m=0;bad=[]
for r in al:
    sid=re.search(r'session_id=(\S+)',g(r,'detail'))
    if sid and sid.group(1) in hs:
        m+=1; a=hs[sid.group(1)]
        tq=re.search(r'tags_queried=(\d+)',g(r,'detail'))
        if tq and tq.group(1)!=a['tags_queried']: bad.append((g(r,'alert_id'),tq.group(1),a['tags_queried']))
    else: bad.append((g(r,'alert_id'),g(r,'detail')[:80]))
print('ITEM5 historian alerts',len(al),'matched to audit row',m,'mismatch',len(bad),bad[:5])
print('  audit bulk reads',sum(1 for r in ha if r['query_type']=='bulk read'),'vs SE3-OT-1104 alerts',sum(1 for r in al if g(r,'rule_id')=='SE3-OT-1104'))
# historian sessions with a network flow
conn=zeek('conn'); reg_=reg(); ip={x['hostname']:x['ip'] for x in reg_['hosts']}
fidx=collections.defaultdict(list)
for r in conn:
    if r[4]=='10.72.1.10' and r[5]=='5450': fidx[r[2]].append(float(r[0]))
nf=collections.Counter()
for a in ha:
    t=E(a['start_utc']); c=ip.get(a['client_host'])
    ok=any(abs(x-t)<15 for x in fidx.get(c,[]))
    nf[(a['client_host'],ok)]+=1
print('  historian sessions with flow client->hist:5450 at start (client,found):',sorted(nf.items()))
host=[a for a in ha if a['account'].endswith('svc_fieldops_ext') or a['account']=='GW-ENG-VELA']
# hostile cluster per canon: HIST-20270907-00441 .. HIST-20271002-00917
ras=audit('remote_access_sessions'); hr=[s for s in ras if s['src_country']!='US']
clus=[]
for s in hr:
    for a in ha:
        if a['client_host']=='GW-SYS-JMP-01' and s['login_utc']<=a['start_utc']<=s['logout_utc']: clus.append(a)
print('  historian rows inside the 14 hostile sessions',len(clus),'tags sum',sum(int(a['tags_queried']) for a in clus))
for a in clus: print('   ',a['session_id'],a['account'],a['start_utc'],a['duration_s'],a['tags_queried'],a['tag_groups'],a['query_type'])
print('  durations whole minutes among hostile',sum(int(a['duration_s'])%60==0 for a in clus),'; among all others',sum(int(a['duration_s'])%60==0 for a in ha if a not in clus),'/',len(ha)-len(clus))
tg=collections.Counter(a['tag_groups'] for a in ha); print('  tag_groups singletons',[k for k,v in tg.items() if v==1],' hostile tag groups counts',[(a['tag_groups'],tg[a['tag_groups']]) for a in clus][:14])
tq=sorted(int(a['tags_queried']) for a in ha); print('  tags_queried top10 overall',tq[-10:],'hostile',sorted(int(a['tags_queried']) for a in clus))
sidn=[int(a['session_id'].split('-')[-1]) for a in ha]; print('  hist session counter: first/last',sidn[0],sidn[-1],'rows',len(sidn),'monotonic',all(b>a for a,b in zip(sidn,sidn[1:])))
