#!/usr/bin/env python3
"""Pass 3 misc: breaker state sequences, exception-rule session, lock/unlock, unexpected shutdowns vs activity, alert user at work, out-of-hours alerts vs sessions, DNS-before-TLS, files<->http, guide worked examples, windows event ids vs schema."""
import sys,collections,pickle,json,re,csv,statistics; sys.path.insert(0,sys.path[0])
from lib import *
reg_=reg(); hip={x['hostname']:x['ip'] for x in reg_['hosts']}; hz={x['hostname']:x['zone'] for x in reg_['hosts']}
W=pickle.load(open('/tmp/c/winsec.pkl','rb')); SY=pickle.load(open('/tmp/c/winsys.pkl','rb'))
sc=audit('scada_command_log')
st={};viol=collections.Counter();n=0
for r in sc:
    if r['command'] in('BREAKER OPEN','BREAKER CLOSE'):
        n+=1; s='open' if r['command']=='BREAKER OPEN' else 'closed'
        if st.get(r['device'])==s: viol[r['command']]+=1
        st[r['device']]=s
print('breaker commands',n,'repeating the previous state of the same device (open after open / close after close):',dict(viol))
st={};v2=0;n2=0
for r in sc:
    if r['command'] in('PUMP START','PUMP STOP'):
        n2+=1
        if st.get(r['device'])==r['command']: v2+=1
        st[r['device']]=r['command']
print('pump commands',n2,'repeating previous state',v2)
# exception rule session
ras=audit('remote_access_sessions')
print('svc_fieldops_ext session on 08-19:',[(s['session_id'],s['src_ip'],s['login_utc'],s['logout_utc'],s['auth_method'],s['target_hosts'],s['change_ticket']) for s in ras if s['account']=='svc_fieldops_ext' and s['login_utc'][:10]=='2027-08-19'])
conn=zeek('conn')
print('  flows JMP -> SIEM-OT (',hip.get('GW-SRV-SIEM-OT'),') on 08-19:',[(T(r[0]),r[5],r[8]) for r in conn if r[2]=='10.72.4.88' and r[4]==hip.get('GW-SRV-SIEM-OT') and T(r[0])[:10]=='2027-08-19'])
print('  other rule_changes by vendor/service accounts:',[(r['time_utc'],r['action'],r['rule_id'],r['changed_by'],r['change_ticket']) for r in csv.DictReader(open('siem/rule_changes.csv')) if r['changed_by'].startswith('svc')])
print('  sessions targeting SIEM-OT by account',collections.Counter(s['account'] for s in ras if 'GW-SRV-SIEM-OT' in s['target_hosts']))
# lock/unlock
lk=[d for d in W if d['event_id'] in(4800,4801)]
print('lock/unlock hosts by zone',collections.Counter(hz.get(d['host']) for d in lk))
lo={}
for d in W:
    if d['event_id'] in(4634,4647): lo.setdefault((d['host'],d['logon_id']),E(d['time_utc']))
li={(d['host'],d['logon_id']):E(d['time_utc']) for d in W if d['event_id']==4624}
outside=sum(1 for d in lk if (d['host'],d['logon_id']) not in li or not(li[(d['host'],d['logon_id'])]<=E(d['time_utc'])<=lo.get((d['host'],d['logon_id']),9e12)))
seq=collections.defaultdict(list)
for d in lk: seq[(d['host'],d['logon_id'])].append(d['event_id'])
badseq=sum(1 for v in seq.values() if any(a==b for a,b in zip(v,v[1:])) or v[0]!=4800)
print('lock/unlock events',len(lk),'outside their logon session',outside,'sessions with lock/unlock not alternating or starting with unlock',badseq,'of',len(seq))
# unexpected shutdowns
u=[d for d in SY if d['event_id']==6008]; print('6008 events',len(u),'by day',collections.Counter(d['time_utc'][:10] for d in u).most_common(6),'zones',collections.Counter(hz.get(d['host']) for d in u).most_common(6))
boots=collections.Counter(d['time_utc'][:10] for d in SY if d['event_id']==6005); print('boots 09-12..09-20',[boots['2027-09-%02d'%x] for x in range(12,21)])
# activity of hosts between last event before outage and boot: use endpoint Sept
ep=collections.defaultdict(list)
for line in open('endpoint/endpoint_2027-09.jsonl'):
    ep[line[line.index('"host":"')+8:line.index('"',line.index('"host":"')+8)]].append(line[13:37])
h,D=fam('dhcp'); dh=collections.defaultdict(list)
for r in D: dh[r[5]].append(r[0])
viol=0;gaps=[]
for d in u:
    hst=d['host']; tb=d['time_utc']
    prev=[t for t in ep.get(hst,[]) if t<tb]
    if prev:
        last=max(prev); gaps.append((E(tb)-E(last))/3600)
    # dhcp renewals in the 6h before boot
    viol+=sum(1 for t in dh.get(hst,[]) if 0<E(tb)-E(t)<1200)
print('  hours between last endpoint event and the boot after power loss: median',round(statistics.median(gaps),1),'min',round(min(gaps),2),'| DHCP renewals within 20 min before such a boot',viol)
# alert names someone at work
h2,S=fam('siem'); ix={n:i for i,n in enumerate(h2)}
sess=collections.defaultdict(list)
for d in W:
    if d['event_id']==4624 and d['logon_type'] in(2,10,11): sess[(d['host'],d['user'])].append((E(d['time_utc']),lo.get((d['host'],d['logon_id']),9e12)))
c=collections.Counter()
for r in S:
    if r[1][:7]!='2027-11': continue
    u_=r[ix['user']]; hst=r[ix['src_host']]
    if not u_ or u_.startswith(('svc','GW-')) or '\\' in u_ or not hst.startswith(('GW-WS','GW-LT')): continue
    t=E(r[1]); c[(r[ix['rule_name']], any(a-2<=t<=b+2 for a,b in sess.get((hst,u_),[])))]+=1
print('Nov alerts naming a person on a workstation: (rule, user has open session)',sorted(c.items()))
# out-of-hours logon alerts
oo=[r for r in S if r[ix['rule_id']]=='SE3-AUTH-1012']
print('LOGON_OUTSIDE_HOURS',len(oo),'sample',[(r[1],r[ix['src_host']],r[ix['dst_host']],r[ix['user']],r[ix['detail']][:60]) for r in oo[:2]])
rk={(d['host'],d['user'],d['time_utc'][:16]) for d in W if d['event_id']==4624 and d['logon_type']==10}
m=sum(1 for r in oo if any((hh,r[ix['user']],r[1][:16]) in rk for hh in (r[ix['dst_host']],r[ix['src_host']])))
print('  matched to a type-10 4624 (host,user,minute)',m)
hl=[(d['time_utc'],d['src_ip']) for d in W if d['event_id']==4624 and d['host']=='GW-SYS-JMP-01' and (d.get('src_ip') or '').startswith(HOSTILE_SRC)]
print('  hostile gateway logons with a LOGON_OUTSIDE_HOURS alert within 2 min:',sum(1 for t,_ in hl if any(abs(E(r[1])-E(t))<120 for r in oo)),'of',len(hl))
# DNS before TLS
dns=collections.defaultdict(list)
for r in zeek('dns'): dns[(r[2],r[8])].append(float(r[0]))
ssl=zeek('ssl'); ext=[r for r in ssl if not r[4].startswith(('10.','172.20.')) and r[2].startswith('10.')]
have=sum(1 for r in ext if any(0<=float(r[0])-t<=300 for t in dns.get((r[2],r[8]),[])))
print('outbound TLS flows',len(ext),'with a dns.log lookup of the server name by the same client in the previous 5 min',have)
ans={}
for r in zeek('dns'):
    for a in r[15].split(','): ans.setdefault(r[8],set()).add(a)
mism=sum(1 for r in ext if r[8] in ans and r[4] not in ans[r[8]]); print('  server_name resolves (in dns.log) to a different address than the flow destination',mism)
# files<->http
fu={r[1] for r in zeek('files')}; hf=[r for r in zeek('http') if r[18] not in('-','(empty)')]
print('http rows with resp_fuids',len(hf),'fuid present in files.log',sum(1 for r in hf if all(f in fu for f in r[18].split(','))),'files rows',len(fu))
fb=sum(1 for r in zeek('files') if r[13]!=r[14]); print('  files seen_bytes != total_bytes',fb)
# worked examples
d1=[r for r in zeek('dns') if r[1]=='C3dcc2df8db1daf365']; print('guide ex dns',[(r[0],r[2],r[4],r[8],r[15]) for r in d1])
s1=[r for r in ssl if r[1]=='C01f7601175cace614']; print('guide ex ssl',[(r[0],r[2],r[4],r[8]) for r in s1],[(r[8],r[10]) for r in conn if r[1]=='C01f7601175cace614'])
c1=[r for r in conn if r[1]=='Cc0d3cc91300643dd2']; print('guide ex conn',[(T(r[0]),r[2],r[3],r[4],r[8],r[9],r[10],r[17],r[19]) for r in c1])
# windows event ids vs schema
sch=json.load(open('../../06_data_streams/schemas/windows_event_logs_schema.json')); txt=json.dumps(sch)
ids=sorted({d['event_id'] for d in W}|{d['event_id'] for d in SY}); print('event ids in data',ids,'not mentioned in schema',[i for i in ids if str(i) not in txt])
