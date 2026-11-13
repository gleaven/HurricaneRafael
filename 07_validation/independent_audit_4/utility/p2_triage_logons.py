#!/usr/bin/env python3
"""Triage logon_history vs Windows Security; JMP history lists the 14 sessions; file listing/exec history/hash agreement with endpoint telemetry for IT-04."""
import sys,collections,csv,os,pickle,json; sys.path.insert(0,sys.path[0])
from lib import *
W=pickle.load(open('/tmp/c/winsec.pkl','rb'))
lg=collections.defaultdict(set)
for d in W:
    if d['event_id']==4624: lg[d['host']].add((d['time_utc'][:19]+'Z',d['user'],str(d['logon_type']),d.get('src_ip') or ''))
tot=0;miss=0;rev=0
for h in sorted(os.listdir('triage')):
    R=list(csv.DictReader(open(f'triage/{h}/logon_history.csv'))); c=json.load(open(f'triage/{h}/collection.json'))
    keys=list(R[0].keys()) if R else []
    s={(r[keys[0]],r['user'],r['logon_type'],r.get('src_ip','')) for r in R}
    tot+=len(R); m=sum(1 for x in s if x not in lg[h]); miss+=m
    lo=min(r[keys[0]] for r in R) if R else None
    # reverse: windows interactive+rdp logons within window not in history
    w0=(datetime.datetime.strptime(c['collected_utc'],'%Y-%m-%dT%H:%M:%SZ')-datetime.timedelta(days=c['logon_history_window_days'])).strftime('%Y-%m-%dT%H:%M:%SZ')
    exp={x for x in lg[h] if w0<=x[0]<=c['collected_utc']}
    r_=sum(1 for x in exp if x not in s); rev+=r_
    print(h,'rows',len(R),'not in 4624',m,'| 4624 in window not in history',r_,'of',len(exp),'| first row',lo,'window start',w0)
print('cols',keys,'total',tot,'missing',miss,'reverse-missing',rev)
J=list(csv.DictReader(open('triage/GW-SYS-JMP-01/logon_history.csv')))
print('JMP rows from hostile addr',sum(1 for r in J if r.get('src_ip','').startswith(HOSTILE_SRC)),collections.Counter(r['logon_type'] for r in J))
# IT-04: file listing hashes vs endpoint
ep={}
for f in ('endpoint/endpoint_2027-08.jsonl','endpoint/endpoint_2027-09.jsonl'):
    for line in open(f):
        if '"GW-WS-IT-04"' in line and ('file_create' in line or 'process_start' in line):
            d=json.loads(line)
            if d['event_type']=='file_create': ep[d['path']]=(d['sha256'],d['size'],d['time_utc'])
            else: ep[d['image']]=(d['sha256'],None,d['time_utc'])
F=list(csv.DictReader(open('triage/GW-WS-IT-04/file_listing.csv')))
for r in F:
    if r['path'] in ep and ('Vantage' in r['path'] or 'FEMA' in r['path']):
        e=ep[r['path']]; print('  ',r['path'][-45:],'sha eq',e[0]==r['sha256'],'size',r['size_bytes'],e[1],'created',r['created_utc'],e[2][:19])
X=list(csv.DictReader(open('triage/GW-WS-IT-04/execution_history.csv')))
print([ (r['image_path'][-30:],r['run_count'],r['first_run_utc'],r['last_run_utc']) for r in X if 'FEMA' in r['image_path'] or 'vstel' in r['image_path']])
c=json.load(open('triage/GW-WS-IT-04/collection.json')); print('IT-04 samples',[s['stands_in_for'][-40:] for s in c['samples']])
