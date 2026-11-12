# Part C, block A: utility moments (breaker 09-21, P-3 09-23, SUB-03 09-24, isolation 10-12, D3/4 boil water 09-26)
from common import *
import glob, collections, json
def hist(files, tags, a, b, maxn=12):
    out=[]
    for f in files:
        for r in rows(f):
            if a<=r['Timestamp']<=b and any(t in r['Tagname'] for t in tags): out.append((r['Timestamp'],r['Tagname'],r['Value'],r['Quality']))
    out.sort(); return out
def show(title, xs, n=10):
    print('  *',title,len(xs))
    for x in xs[:n]: print('      ',str(x)[:260])
print('=== M7 breaker SUB-02 2027-09-21T14:28:15Z')
show('scada_command_log',[r for r in rows('network_logs/audit/scada_command_log.csv') if '2027-09-21T14:2'<=r['time_utc']<='2027-09-21T14:35'])
h=hist([SRC+'/telemetry/historian_SUB02_202709.csv'],['BKR','CB','AMP','MW','LOAD'],'2027-09-21T14:20','2027-09-21T14:40')
chg=[];last={}
for t,tag,v,q in h:
    if last.get(tag)!=v and ('STS' in tag or 'CMD' in tag): chg.append((t,tag,v,q))
    last[tag]=v
show('historian SUB02 status/cmd changes',chg,12)
show('historian SUB02 load tags around',[x for x in h if 'STS' not in x[1] and 'CMD' not in x[1]][:0])
tags=collections.Counter(x[1] for x in h); print('      tags',list(tags.items())[:14])
om=[r for r in rows('telemetry/outage_map.csv') if r['substation_id'].endswith('SUB-02') and '2027-09-21T14:00'<=r['timestamp_utc']<='2027-09-21T15:00']
show('outage_map SUB-02 feeders',[(r['timestamp_utc'],r['feeder_id'],r['customers_out'],r['cause'],r['crews_assigned']) for r in om],16)
wo=[r for r in rows('maintenance/work_orders.csv') if '2027-09-21T14'<=r['reported_date']<='2027-09-21T16']
show('work_orders reported 14-16Z',[(r['wonum'],r['reported_date'],r['asset_id'],r['description'][:90],r['failure_code'],r['reported_by']) for r in wo])
show('remote_access_sessions',[(r['session_id'],r['login_utc'],r['logout_utc'],r['src_country'],r['target_hosts']) for r in rows('network_logs/audit/remote_access_sessions.csv') if '2027-09-21T14'<=r['login_utc']<='2027-09-21T15'])
show('historian_access',[(r['session_id'],r['start_utc'],r['client_host'],r['query_type'],r['tag_groups']) for r in rows('network_logs/audit/historian_access.csv') if '2027-09-21T14'<=r['start_utc']<='2027-09-21T15'])
show('alarm_suppression',[(r['time_utc'],r['action'],r['category'],r['changed_by'],r['active_suppressions_after']) for r in rows('network_logs/audit/alarm_suppression_audit.csv') if '2027-09-21T14'<=r['time_utc']<='2027-09-21T15'],3)
show('siem JMP/SCADA alerts 14:20-14:40',[(r['time_utc'],r['rule_name'],r['src_host'],r['dst_host'],r['user'],r['disposition']) for r in rows('network_logs/siem/siem_alerts_2027-09.csv') if '2027-09-21T14:20'<=r['time_utc']<='2027-09-21T14:40' and ('JMP' in r['src_host'] or 'SCADA' in r['dst_host'] or r['category']=='ot')],12)
# zeek
def zeek(day,pred):
    out=[];fields=None
    for line in open(f'{SRC}/network_logs/zeek/{day}/conn.log'):
        if line.startswith('#fields'): fields=line.rstrip('\n').split('\t')[1:]; continue
        if line.startswith('#'): continue
        r=dict(zip(fields,line.rstrip('\n').split('\t')))
        if pred(r): out.append((dt.datetime.fromtimestamp(float(r['ts']),dt.timezone.utc).strftime('%H:%M:%S'),r['id.orig_h'],r['id.resp_h'],r['id.resp_p'],r['service'],r['duration'],r['orig_bytes'],r['resp_bytes']))
    return out
E=lambda s:ts(s).timestamp()
show('zeek conn involving JMP 10.72.4.88 14:20-14:35',zeek('2027-09-21',lambda r:(r['id.orig_h']=='10.72.4.88' or r['id.resp_h']=='10.72.4.88') and E('2027-09-21T14:20:00Z')<=float(r['ts'])<=E('2027-09-21T14:35:00Z')))
show('zeek conn JMP->OT (orig=JMP) whole day',zeek('2027-09-21',lambda r:r['id.orig_h']=='10.72.4.88'),8)
print('=== M8 P-3 setpoint 2027-09-23T02:04:01Z')
show('ot_config',[tuple(r.values()) for r in rows('network_logs/audit/ot_config_changes.csv') if r['time_utc'].startswith('2027-09-23')])
h=hist(glob.glob(SRC+'/telemetry/historian_*_202709.csv'),['PUMP3.PRESS.SP','P3','ZONE4','Z4'],'2027-09-23T01:30','2027-09-23T06:10')
c=collections.defaultdict(list)
for x in h: c[x[1]].append(x)
for tag,v in list(c.items())[:8]: print('      ',tag,len(v),[ (y[0][11:16],y[2]) for y in v[::max(1,len(v)//8)]][:9])
show('zeek JMP flows 01:55-02:15',zeek('2027-09-23',lambda r:(r['id.orig_h']=='10.72.4.88' or r['id.resp_h']=='10.72.4.88') and E('2027-09-23T01:55:00Z')<=float(r['ts'])<=E('2027-09-23T02:15:00Z')))
print('=== M9 SUB-03 2027-09-24T19:43:46Z')
show('scada_command_log',[tuple(r.values()) for r in rows('network_logs/audit/scada_command_log.csv') if '2027-09-24T19:3'<=r['time_utc']<='2027-09-24T19:59'])
om=[r for r in rows('telemetry/outage_map.csv') if r['substation_id'].endswith('SUB-03') and '2027-09-24T19:15'<=r['timestamp_utc']<='2027-09-24T20:15']
show('outage_map SUB-03',[(r['timestamp_utc'],r['feeder_id'],r['customers_out'],r['cause']) for r in om],14)
print('=== M16 isolation 2027-10-12T12:00Z')
h=hist(glob.glob(SRC+'/telemetry/historian_SYSTEM_202710.csv'),['ISOLATED','COMMS'],'2027-10-12T10:00','2027-10-12T14:00')
show('historian SYSTEM',[x for i,x in enumerate(h) if i==0 or h[i-1][2]!=x[2] or h[i-1][1]!=x[1]],10)
show('work_orders 10-12',[(r['wonum'],r['reported_date'],r['description'][:110]) for r in rows('maintenance/work_orders.csv') if r['reported_date'].startswith('2027-10-12') or 'OT-0881' in r['wonum']])
show('remote sessions 10-11T20..10-20T20',[(r['session_id'],r['login_utc'],r['account'],r['src_country']) for r in rows('network_logs/audit/remote_access_sessions.csv') if '2027-10-11T20'<=r['login_utc']<='2027-10-20T20'],6)
show('scada cmds via remote desktop in window',[(r['time_utc'],r['origin'],r['origin_host']) for r in rows('network_logs/audit/scada_command_log.csv') if '2027-10-12T12'<=r['time_utc']<='2027-10-19T20' and r['origin']!='console'])
show('historian_access from JMP in window',[(r['session_id'],r['start_utc'],r['client_host']) for r in rows('network_logs/audit/historian_access.csv') if '2027-10-12T12'<=r['start_utc']<='2027-10-19T20' and r['client_host']=='GW-SYS-JMP-01'])
show('siem alerts src JMP in window',[(r['time_utc'],r['rule_name'],r['src_host']) for r in rows('network_logs/siem/siem_alerts_2027-10.csv') if '2027-10-12T12'<=r['time_utc']<='2027-10-19T20' and r['src_host']=='GW-SYS-JMP-01'],6)
show('ot_config in window',[tuple(r.values()) for r in rows('network_logs/audit/ot_config_changes.csv') if '2027-10-12T12'<=r['time_utc']<='2027-10-19T23'])
show('file_integrity from JMP in window',[(r['time_utc'],r['source_host'],r['user']) for r in rows('network_logs/audit/file_integrity.csv') if '2027-10-12T12'<=r['time_utc']<='2027-10-19T20' and r['source_host']=='GW-SYS-JMP-01'])
show('alarm_suppression in window',[(r['time_utc'],r['action'],r['changed_by'],r['source_host']) for r in rows('network_logs/audit/alarm_suppression_audit.csv') if '2027-10-12T12'<=r['time_utc']<='2027-10-19T23'],4)
