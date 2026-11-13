#!/usr/bin/env python3
"""Pass 2: canon events across log types (things not covered by other scripts)."""
import sys,collections,json,pickle,re,csv,glob; sys.path.insert(0,sys.path[0])
from lib import *
reg_=reg(); hip={x['hostname']:x['ip'] for x in reg_['hosts']}; iph={v:k for k,v in hip.items()}
W=pickle.load(open('/tmp/c/winsec.pkl','rb')); SY=pickle.load(open('/tmp/c/winsys.pkl','rb'))
conn=zeek('conn')
import collections as _c
_idx=_c.defaultdict(list)
for _r in conn: _idx[(_r[2],_r[4])].append(_r)
def flows(src,dst,port=None,t0=None,t1=None):
    a=E(t0) if t0 else None; b=E(t1) if t1 else None
    return [r for r in _idx.get((src,dst),[]) if (port is None or r[5]==str(port)) and (a is None or a<=float(r[0])<=b)]
print('(a) Defender on IT-04 2027-08-30:',[(d['time_utc'],d['event_id'],d.get('user'),d.get('detail')) for d in SY if d['host']=='GW-WS-IT-04' and d['time_utc'][:10]=='2027-08-30' and d['channel'].startswith('Microsoft-Windows-Windows Defender')])
print('    audit/endpoint_protection:',[ (r['time_utc'],r['event'],r['detail'],r['initiated_by']) for r in audit('endpoint_protection') if r['host']=='GW-WS-IT-04' and r['time_utc'][:10]=='2027-08-30'])
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
print('    SIEM alerts for IT-04 on 08-30:',[(r[1],r[3],r[ix['detail']][:50],r[ix['disposition']]) for r in S if r[ix['src_host']]=='GW-WS-IT-04' and r[1][:10]=='2027-08-30'])
re_dis=[d for d in SY if d['event_id']==5001]; print('    5001 events total',len(re_dis),'followed by re-enable within 1h (5000 "setting changed locally")', '-','| IT-04 re-enabled ever:',[(x['time_utc'],x['detail']) for x in SY if x['host']=='GW-WS-IT-04' and x['event_id']==5000][:3])
sc=audit('scada_command_log'); p4000=[r for r in conn if r[5]=='4000']
print('(b) SCADA log 2027-09-14T06..09:',[(r['time_utc'],r['workstation'],r['operator'],r['command'],r['device'],r['origin']) for r in sc if '2027-09-14T06'<=r['time_utc']<'2027-09-14T09'])
print('    SIEM around 07:12 for SUB-01:',[(r[1],r[3],r[ix['src_host']],r[ix['detail']][:60]) for r in S if '2027-09-14T07:10'<=r[1]<='2027-09-14T07:15' and ('SUB01' in ' '.join(r) or 'RTU-01' in ' '.join(r) or 'sub-01' in ' '.join(r).lower())][:6])
print('(c) SCADA log 2027-09-26T15..17:',[(r['time_utc'],r['workstation'],r['operator'],r['command'],r['device'],r['origin']) for r in sc if '2027-09-26T15'<=r['time_utc']<'2027-09-26T18'])
print('(d) IT-04 -> OT DCs flows:',[(T(r[0]),r[4],r[5]) for r in conn if r[2]=='10.14.22.47' and r[4].startswith('10.72.')], '| OTDC-02 ip',hip.get('GW-SRV-OTDC-02'))
print('    4769 on OTDC from corp-side src:',collections.Counter((d['host'],d['src_ip'][:8]) for d in W if d['event_id']==4769 and d['host'].startswith('GW-SRV-OTDC') ).most_common(6))
x=[d for d in W if d['host']=='GW-SRV-HIST-DMZ' and '2027-09-08T23:5'<=d['time_utc']<='2027-09-09T00:50']; print('    HIST-DMZ events:',[(d['time_utc'][11:19],d['event_id'],d['user'],d.get('src_ip'),d.get('share'),d.get('path'),d.get('access')) for d in x])
print('    ReadData 5145 total',sum(1 for d in W if d['event_id']==5145 and d['access']=='ReadData'),'on HIST-DMZ exports$ by host',collections.Counter(d['src_ip'] for d in W if d['event_id']==5145 and d['host']=='GW-SRV-HIST-DMZ').most_common(5))
print('    logons to HIST-DMZ from corp workstations (type 3):',collections.Counter((d['user'],d['src_ip']) for d in W if d['event_id']==4624 and d['host']=='GW-SRV-HIST-DMZ' and (d.get('src_ip') or '').startswith('10.14.')).most_common(8))
print('    conn flows corp-users -> 10.72.4.20:445:',collections.Counter(r[2] for r in conn if r[4]=='10.72.4.20' and r[5]=='445').most_common(8))
for when,ws in (('2027-09-21T14:28:15Z','GW-WS-OPS-02'),('2027-09-24T19:43:46Z','GW-WS-OPS-02')):
    lg=[d for d in W if d['host']==ws and d['event_id']==4624 and d['logon_type']==10 and 0<E(when)-E(d['time_utc'])<600]
    print('(e) RDP logon on',ws,'before',when,[(d['time_utc'],d['user'],d['src_ip'],round(E(when)-E(d['time_utc']))) for d in lg],'rdp flow',[(T(r[0]),r[8]) for r in flows('10.72.4.88',hip[ws],3389,when[:11]+'00:00:00Z',when)][-1:], 'cmd flow',[(T(r[0]),r[2],r[9],r[10]) for r in p4000 if abs(float(r[0])-E(when))<5])
sa=audit('alarm_suppression_audit'); bt=sorted({a['time_utc'] for a in sa if a['changed_by']=='GW-ENG-VELA'})
b1=[];prev=None
for t in bt:
    if prev is None or E(t)-E(prev)>60: b1.append(t)
    prev=t
for t in b1:
    lg=[d for d in W if d['host']=='GW-SYS-SCADA-01' and d['event_id']==4624 and d['logon_type']==10 and -5<E(t)-E(d['time_utc'])<3600]
    print('(f) suppression batch',t,'RDP on SCADA-01:',[(d['time_utc'][11:19],d['user'],d['src_ip']) for d in lg][-1:],'flow',[(T(r[0])[11:19]) for r in flows('10.72.4.88','10.72.1.30',3389,t[:11]+'00:00:00Z',t)][-1:])
x=[d for d in W if d['host']=='GW-SRV-OT-01' and '2027-09-11T22:0'<=d['time_utc']<='2027-09-11T22:2']; print('(g) OT-01 events:',[(d['time_utc'][11:19],d['event_id'],d['user'],d.get('src_ip'),d.get('path'),d.get('access')) for d in x])
print('    flow JMP->OT-01:445',[(T(r[0]),r[8],r[9],r[10]) for r in flows('10.72.4.88','10.72.1.20',445,'2027-09-11T22:00:00Z','2027-09-11T22:20:00Z')])
oc=audit('ot_config_changes')
for r in oc:
    if r['session_user']=='GW-ENG-VELA' and r['change_ticket']=='':
        _t=E(r['time_utc']); f=[(T(x[0]),x[5],x[7]) for x in _idx.get(('10.72.4.88',hip.get(r['device'])),[]) if abs(float(x[0])-_t)<60]
        print('(h) change',r['time_utc'],r['device'],hip.get(r['device']),r['parameter'][:30],r['old_value'][:12],'->',r['new_value'][:12],'flow',f)
ep=[json.loads(l) for l in open('endpoint/endpoint_2027-09.jsonl') if '"GW-WS-IT-04"' in l and '2027-09-08T23:5' in l]
print('(k) endpoint IT-04 23:5x',[(d['time_utc'],d['event_type'],d['image'].split('\\')[-1],d.get('dst_ip'),d.get('dst_port'),d['user']) for d in ep])
ras=audit('remote_access_sessions'); hs=[s for s in ras if s['src_country']!='US']
print('(l) first 7 bytes_out GB',sum(int(s['bytes_out']) for s in hs[:7])/1e9,'total hours',sum(int(s['duration_s']) for s in hs)/3600,'first',hs[0]['login_utc'],'last',hs[-1]['login_utc'])
import zoneinfo,datetime
tz=zoneinfo.ZoneInfo('America/Chicago')
print('    hostile session local start hours',[datetime.datetime.fromtimestamp(E(s['login_utc']),tz).strftime('%a %H:%M') for s in hs])
sb=[r for r in S if r[ix['disposition']]=='STORM_BULK_DISMISSED']
print('(q) storm-dismissed',len(sb),'window',min(r[1] for r in sb),max(r[1] for r in sb),'priorities',collections.Counter(r[ix['priority']] for r in sb),'rules',len({r[2] for r in sb}),'distinct rule ids in whole SIEM',len({r[2] for r in S}))
_rs={x[2] for x in sb}; inw=[r for r in S if '2027-09-14T06:14:05Z'<=r[1]<='2027-09-18T14:00:00Z' and r[ix['priority']] in('LOW','MEDIUM') and r[2] in _rs]
print('    alerts of those rules/priorities in storm-mode window',len(inw),'dismissed',sum(1 for r in inw if r[ix['disposition']]=='STORM_BULK_DISMISSED'),'others',collections.Counter(r[ix['disposition']] for r in inw).most_common(4))
print('    rules dismissed',collections.Counter(r[3] for r in sb).most_common(30))
