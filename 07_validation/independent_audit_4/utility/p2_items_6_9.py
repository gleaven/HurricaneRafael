#!/usr/bin/env python3
"""Re-test items 6 (lure mail uniqueness), 7 (VELA leave), 9 (isolation, freeze), + VPN alert join."""
import sys,collections,re,json,glob; sys.path.insert(0,sys.path[0])
from lib import *
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
g=lambda r,c:r[ix[c]]
M=audit('mail_gateway_cbpwa')
subj=collections.Counter(m['subject'] for m in M); dom=collections.Counter(m['sender_domain'] for m in M)
lure=[m for m in M if 'FEMA-PREP' in m['attachment_names']][0]
print('ITEM6 mail rows',len(M),'subjects',len(subj),'singletons',sum(v==1 for v in subj.values()),'lure subject count',subj[lure['subject']],'| sender domains',len(dom),'singletons',sum(v==1 for v in dom.values()),'lure domain count',dom[lure['sender_domain']])
ext=collections.Counter(m['attachment_names'].rsplit('.',1)[-1] for m in M if m['attachment_names']); print('  attachment ext',ext.most_common(25))
print('  verdict x direction',collections.Counter((m['direction'],m['verdict']) for m in M).most_common())
inb=[m for m in M if m['direction']=='inbound' and m['verdict']=='clean' and m['attachment_names'].endswith('.zip')]
print('  inbound clean zip',len(inb),'| subjects containing FEMA/hurricane/storm:',sum(1 for m in M if re.search('FEMA|hurricane|storm',m['subject'],re.I)))
print('  lookalike-domain senders (contain cbpwa, not cbpwa.example):',collections.Counter(m['sender_domain'] for m in M if 'cbpwa' in m['sender_domain'] and m['sender_domain']!='cbpwa.example').most_common(12))
hexs=sum(1 for m in M if m['direction']!='inbound' and re.match(r'^[0-9a-f]{6}@',m['sender'])); print('  internal senders that are hex strings',hexs)
reg_=reg(); users={u['username'] for u in reg_['users']}
snd=[m['sender'].split('@')[0] for m in M if m['sender_domain']=='cbpwa.example']; print('  cbpwa senders not in registry',sum(1 for s in snd if s not in users),'of',len(snd),collections.Counter(s for s in snd if s not in users).most_common(5))
rc=[m['recipient'].split('@')[0] for m in M if m['recipient'].endswith('@cbpwa.example')]; print('  cbpwa recipients not in registry',sum(1 for s in rc if s not in users),'of',len(rc))
# ITEM 7: leave window
L0,L1='2027-09-06T22:00:00Z','2027-09-22T06:00:00Z'
va=[r for r in S if L0<=g(r,'time_utc')<=L1 and ('GW-ENG-VELA' in ' '.join(r) or 'rvela' in ' '.join(r))]
print('ITEM7 SIEM alerts naming VELA/rvela in leave window',len(va),collections.Counter((g(r,'rule_id'),g(r,'src_host'),g(r,'disposition')) for r in va).most_common(12))
for n in ('historian_access','file_integrity','ot_config_changes','alarm_suppression_audit','scada_command_log','employee_vpn_sessions','remote_access_sessions','change_management'):
    R=audit(n); tk=[k for k in R[0] if k in('time_utc','start_utc','login_utc')][0]
    w=[r for r in R if L0<=r[tk]<=L1 and ('GW-ENG-VELA' in ','.join(r.values()) or 'rvela' in ','.join(r.values()))]
    print('  ',n,'rows in leave window naming VELA:',len(w),collections.Counter((r.get('source_host') or r.get('client_host') or r.get('src_ip') or '')[:14] for r in w).most_common(6))
wv=collections.Counter()
for f in sorted(glob.glob('windows/security_2027-09.jsonl')):
    for line in open(f):
        if 'rvela' in line or 'GW-ENG-VELA' in line:
            d=json.loads(line)
            if L0<=d['time_utc']<=L1: wv[(d['host'],d['event_id'],d.get('logon_type'),d.get('src_ip'),d.get('user'))]+=1
print('  Windows events for rvela/GW-ENG-VELA in leave window:',sum(wv.values())); [print('    ',v,k) for k,v in sorted(wv.items(),key=lambda x:-x[1])[:25]]
ev=collections.Counter()
for line in open('endpoint/endpoint_2027-09.jsonl'):
    if '"rvela"' in line or 'GW-ENG-VELA' in line:
        d=json.loads(line)
        if L0<=d['time_utc']<=L1: ev[(d['host'],d['event_type'])]+=1
print('  endpoint events user rvela in leave window',dict(ev))
px=fam('proxy')[1]; print('  proxy rows user rvela in window',sum(1 for r in px if r[2]=='rvela' and L0<=r[0]<=L1))
dh=fam('dhcp')[1]; print('  dhcp rows GW-WS-IT-69 in window',sum(1 for r in dh if r[5]=='GW-WS-IT-69' and L0<=r[0]<=L1), 'outside window sept',sum(1 for r in dh if r[5]=='GW-WS-IT-69' and r[0][:7]=='2027-09' and not L0<=r[0]<=L1))
# ITEM 9 isolation / freeze
I0,I1='2027-10-12T12:00:00Z','2027-10-19T18:00:00Z'
ha=audit('historian_access'); zone={x['hostname']:x['zone'] for x in reg_['hosts']}
w=[a for a in ha if I0<=a['start_utc']<=I1]
print('ITEM9 historian sessions in isolation window',len(w),collections.Counter((a['client_host'],zone.get(a['client_host'])) for a in w))
fo=fam('fw_ot')[1]; w=[r for r in fo if I0<=r[0]<=I1]; print('  boundary fw rows in window',collections.Counter((r[2],r[3]) for r in w), 'first allow after',min((r[0] for r in fo if r[0]>I1 and r[2]=='allow'),default=None), 'last allow before',max(r[0] for r in fo if r[0]<I0 and r[2]=='allow'),'first deny',min(r[0] for r in fo if r[2]=='deny'),'last deny',max(r[0] for r in fo if r[2]=='deny'))
ras=audit('remote_access_sessions'); print('  remote sessions in window',sum(1 for s in ras if I0<=s['login_utc']<=I1 or I0<=s['logout_utc']<=I1), 'sessions after JMP power-off 10-12T12:07:57 until', min((s['login_utc'] for s in ras if s['login_utc']>'2027-10-12T12:07:57Z'),default=None))
conn=zeek('conn'); x=[r for r in conn if E(I0)<=float(r[0])<=E(I1) and ((r[2].startswith('10.72.') )!=(r[4].startswith('10.72.')) ) and r[11]=='SF']
print('  zeek SF flows crossing IT<->OT in window',len(x),collections.Counter((r[2],r[4],r[5]) for r in x).most_common(5))
x=[r for r in conn if E(I0)<=float(r[0])<=E(I1) and (r[2]=='10.72.4.88' or r[4]=='10.72.4.88')]; print('  flows involving JMP-01 in window',len(x))
F0,F1='2027-09-10T21:00:04Z','2027-10-25T15:00:40Z'
oc=audit('ot_config_changes'); w=[r for r in oc if F0<=r['time_utc']<=F1]
print('  ot_config_changes in freeze',len(w),collections.Counter(re.sub(r'\d+$','N',r['change_ticket']) for r in w))
cm=audit('change_management'); w=[r for r in cm if F0<=r['time_utc']<=F1]; print('  change_management rows in freeze',collections.Counter(r['record_type'] for r in w))
for n,tk in (('file_integrity','time_utc'),('alarm_suppression_audit','time_utc'),('remote_access_sessions','login_utc')):
    R=audit(n); w=[r for r in R if F0<=r[tk]<=F1]; print('  ',n,'in freeze',len(w),collections.Counter(re.sub(r'\d+$','N',r.get('change_ticket','')) if 'change_ticket' in r else '-' for r in w).most_common(6))
tick={r['record_id'] for r in cm}
for n in ('ot_config_changes','alarm_suppression_audit','remote_access_sessions'):
    R=audit(n); t=[r['change_ticket'] for r in R if r['change_ticket']]
    print('  ',n,'tickets cited',len(t),'present in change_management',sum(1 for x in t if x in tick),'prefixes missing',collections.Counter(x[:3] for x in t if x not in tick))
# VPN alerts
va=audit('employee_vpn_sessions'); al=[r for r in S if g(r,'rule_id')=='SE3-NET-3025']
m=0
for r in al:
    u=re.search(r'user=(\S+)',g(r,'detail')).group(1); ip=re.search(r'src_ip=(\S+)',g(r,'detail')).group(1)
    if any(a['account']==u and a['src_ip']==ip and abs(E(a['login_utc'])-E(g(r,'time_utc')))<=120 for a in va): m+=1
print('VPN_NEW_LOCATION alerts',len(al),'matched to VPN session on user+ip+time',m)
