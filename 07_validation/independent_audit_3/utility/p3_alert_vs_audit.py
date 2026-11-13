#!/usr/bin/env python3
"""Pass 3: do SIEM alerts for OT rules have their record in the audit tables? HISTORIAN_BULK_QUERY vs historian_access, ALARM_SUPPRESSION_CHANGE vs alarm_suppression_audit, OT_FILE_WRITE vs file_integrity and Windows 5145."""
import csv,glob,collections,datetime,json
B="./05_other_sources/network_logs/"
P=lambda s: datetime.datetime.strptime(s[:19],'%Y-%m-%dT%H:%M:%S')
al=collections.defaultdict(list)
for f in sorted(glob.glob(B+'siem/siem_alerts_*.csv')):
    for r in csv.DictReader(open(f)):
        if r['rule_name'] in('HISTORIAN_BULK_QUERY','ALARM_SUPPRESSION_CHANGE','OT_FILE_WRITE','MAINT_WINDOW_ACTIVITY'): al[r['rule_name']].append(r)
hist=list(csv.DictReader(open(B+'audit/historian_access.csv')))
hs=sorted(P(h['start_utc']) for h in hist)
import bisect
def near(ts,t,tol):
    i=bisect.bisect_left(ts,t); return any(0<=j<len(ts) and abs((ts[j]-t).total_seconds())<=tol for j in (i-1,i))
a=al['HISTORIAN_BULK_QUERY']; m=sum(near(hs,P(r['time_utc']),120) for r in a)
print('HISTORIAN_BULK_QUERY alerts',len(a),'with a historian_access session starting within 120 s:',m)
print('  alert src_host',collections.Counter(r['src_host'] for r in a).most_common(8))
print('  example unmatched',[ (r['alert_id'],r['src_host'],r['user'],r['detail']) for r in a if not near(hs,P(r['time_utc']),120)][:3])
print('  historian bulk reads in audit',sum(h['query_type']=='bulk read' for h in hist),'sessions',len(hist))
sup=list(csv.DictReader(open(B+'audit/alarm_suppression_audit.csv'))); ss=sorted(P(h['time_utc']) for h in sup)
a=al['ALARM_SUPPRESSION_CHANGE']; m=sum(near(ss,P(r['time_utc']),120) for r in a)
print('ALARM_SUPPRESSION_CHANGE alerts',len(a),'with an alarm_suppression_audit row within 120 s:',m,'audit rows',len(sup))
print('  example unmatched',[ (r['alert_id'],r['src_host'],r['user'],r['detail']) for r in a if not near(ss,P(r['time_utc']),120)][:3])
fi=list(csv.DictReader(open(B+'audit/file_integrity.csv'))); fs=sorted(P(h['time_utc']) for h in fi)
a=al['OT_FILE_WRITE']; m=sum(near(fs,P(r['time_utc']),120) for r in a)
print('OT_FILE_WRITE alerts',len(a),'with a file_integrity row within 120 s:',m,'file_integrity rows',len(fi))
w=[]
for f in sorted(glob.glob(B+'windows/security_*.jsonl')):
    for l in open(f):
        if '"event_id":5145' in l:
            d=json.loads(l); w.append((P(d['time_utc']),d.get('relative_target') or d.get('path'),d['user'],d['src_ip']))
ws=sorted(x[0] for x in w)
print('  with a Windows 5145 within 5 s:',sum(near(ws,P(r['time_utc']),5) for r in a),'; 5145 total',len(w))
print('  file_integrity rows with a 5145 within 60 s:',sum(near(ws,t,60) for t in fs),'of',len(fs))
print('  file_integrity seconds==00:',sum(h['time_utc'][17:19]=='00' for h in fi),'of',len(fi))
print('  alert path sample',[r['detail'] for r in a[:3]]); print('  fim path sample',[h['path'] for h in fi[:3]]); print('  5145 sample',w[:2])
