import csv,glob,json,re,collections,os,sys,bisect
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
def T(s): return datetime.strptime(s[:19].replace(' ','T'),'%Y-%m-%dT%H:%M:%S')
A=O+'network_logs/audit/'
h=list(rows(A+'historian_access.csv'))
print('D2-03 historian query_type',C(r['query_type'] for r in h).most_common()); 
bulk=[r for r in h if 'bulk' in r['query_type']]; print('  bulk accounts',C(r['account'] for r in bulk).most_common(6)); print('  bulk ids sample',[r['session_id'] for r in bulk][:8]); print('  tag_groups sample',C(r['tag_groups'] for r in bulk).most_common(5))
ids=[int(r['session_id'].rsplit('-',1)[-1]) for r in h]; print('  ids monotonic in start order',all(b>a for a,b in zip(ids,ids[1:])) if [r['start_utc'] for r in h]==sorted(r['start_utc'] for r in h) else 'file not time-sorted')
fi=list(rows(A+'file_integrity.csv')); print('  file_integrity diff_summary filled',sum(1 for r in fi if r['diff_summary'].strip()),'of',len(fi))
ep=list(rows(A+'endpoint_protection.csv')); print('  endpoint events',C(r['event'] for r in ep).most_common(8)); print('  DISABLED details',C((r['detail'],r['initiated_by']) for r in ep if 'DISABLED' in r['event']).most_common(6))
sc=list(rows(A+'scada_command_log.csv')); print('  scada devices',sorted(C(r['device'] for r in sc).items(),key=lambda kv:kv[1])[:6],'...'); print('  origin',C(r['origin'] for r in sc).most_common(),'remote desktop w/ empty operator',sum(1 for r in sc if r['origin']=='remote desktop' and not r['operator'].strip()),'of',sum(1 for r in sc if r['origin']=='remote desktop'))
al=list(rows(A+'alarm_suppression_audit.csv')); print('  alarm changed_by x action',C((r['changed_by'],r['action']) for r in al).most_common(10)); 
ben=[r for r in al if r['changed_by']!='GW-ENG-VELA']; print('  benign time-of-day seconds',C(r['time_utc'][11:19] for r in ben).most_common(4))
rem=[r for r in al if r['action'].upper().startswith('REM')]; ts=sorted(T(r['time_utc']) for r in rem if r['time_utc']>='2027-10-12T12'); gaps=C(int((b-a).total_seconds()) for a,b in zip(ts,ts[1:])); print('  removals from 10-12T12Z',len(ts),'gap seconds',gaps.most_common(5))
oc=list(rows(A+'ot_config_changes.csv')); print('  ot_config local gloss rows',sum(1 for r in oc if 'local' in r['new_value']),'; 2027-09-11T22:11 rows',[(r['time_utc'],r['device'],r['parameter'],r['change_type']) for r in oc if r['time_utc'].startswith('2027-09-11T22:1')])
ra=list(rows(A+'remote_access_sessions.csv')); print('  remote sessions multi-target',sum(1 for r in ra if ';' in r['target_hosts']),'of',len(ra),'by account',C(r['account'] for r in ra if ';' in r['target_hosts']).most_common(5))
vs=list(rows(O+'telemetry/vessel_cargo_control_remote_sessions.csv')); 
print('  vessel sessions',len(vs),'ids in time order',[r['session_id'] for r in vs]==[r['session_id'] for r in sorted(vs,key=lambda r:r['login_utc'])],'login UTC hour hist',sorted(C(int(r['login_utc'][11:13]) for r in vs).items()),'dur%60==0',sum(1 for r in vs if int(float(r['duration_s'] or 1))%60==0),'sec00',sum(1 for r in vs if r['login_utc'][17:19]=='00'))
print('  vessel accounts',C(r['vendor_account'] for r in vs).most_common(6),'src_asn forms',C(re.sub(r'\d','9',r['src_asn']) for r in vs).most_common())
# ---- D2-05 isolation window
w0,w1='2027-10-12T12:00','2027-10-19T20:00'
print('D2-05 scada cmds from JMP in window',sum(1 for r in sc if w0<=r['time_utc']<w1 and 'JMP' in (r['origin_host']+r['workstation'])),'historian client JMP in window',sum(1 for r in h if w0<=r['start_utc']<w1 and 'JMP' in r['client_host']))
n=0
for f in glob.glob(O+'network_logs/siem/siem_alerts_2027-10.csv'):
    for r in rows(f):
        if w0<=r['time_utc']<w1 and r['src_host']=='GW-SYS-JMP-01': n+=1
print('  SIEM alerts src GW-SYS-JMP-01 in window',n)
lab=0
for d in sorted(glob.glob(O+'network_logs/zeek/2027-10-1[2-9]/conn.log')):
    for ln in open(d,encoding='utf-8'):
        if ln.startswith('#'): continue
        p=ln.split('\t')
        if p[2]=='10.72.30.50': lab+=1
print('  zeek flows from 10.72.30.50 on 10-12..19',lab)
# SIEM close notes
cn=C()
for f in glob.glob(O+'network_logs/siem/siem_alerts_2027-09.csv'):
    for r in rows(f):
        if r['rule_name'] and r['close_note']: cn[(r['rule_id'],r['close_note'])]+=1
print('D2-22 SIEM close notes (Sept) top',cn.most_common(8)); print('  DEVICE_COMM_LOSS + Password',sum(v for (a,b),v in cn.items() if 'COMM' in a and 'assword' in b))
sa=list(rows(A+'settings_audits.csv')); print('D2-20 settings_audits',[ (r['item'],r['found'],r['record_value']) for r in sa])
