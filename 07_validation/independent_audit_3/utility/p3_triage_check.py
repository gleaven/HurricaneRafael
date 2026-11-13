#!/usr/bin/env python3
"""Pass 2/3: triage collections: collection.json row counts and SHA-256 of tables, placeholder hashes, logon_history vs Windows Security, services vs System 7045, file_listing vs endpoint file_create."""
import json,csv,glob,hashlib,os,collections,datetime
B="./05_other_sources/network_logs/"
sec=collections.defaultdict(set)
hosts=sorted(os.listdir(B+'triage'))
for f in sorted(glob.glob(B+'windows/security_2027-0[89].jsonl'))+sorted(glob.glob(B+'windows/security_2027-10.jsonl')):
    for l in open(f):
        d=json.loads(l)
        if d['host'] in hosts and d['event_id'] in(4624,4625,4634,4647): sec[d['host']].add((d['time_utc'][:19],d['event_id'],d['user'],str(d.get('logon_id',''))))
svc=collections.defaultdict(set)
for f in sorted(glob.glob(B+'windows/system_*.jsonl')):
    for l in open(f):
        if '"event_id":7045' in l:
            d=json.loads(l)
            if d['host'] in hosts: svc[d['host']].add((d['time_utc'][:19],d['service_name']))
for h in hosts:
    c=json.load(open(B+f'triage/{h}/collection.json')); msg=[]
    for name,meta in c['items'].items():
        raw=open(B+f'triage/{h}/{name}','rb').read(); rows=len(list(csv.reader(open(B+f'triage/{h}/{name}',newline=''))))-1
        if hashlib.sha256(raw).hexdigest()!=meta['sha256']: msg.append(name+' sha MISMATCH')
        if rows!=meta['rows']: msg.append(f'{name} rows {rows}!={meta["rows"]}')
    for s in c.get('samples',[]):
        p=B+f'triage/{h}/'+s['file']
        if hashlib.sha256(open(p,'rb').read()).hexdigest()!=s['sha256']: msg.append(s['file']+' placeholder sha MISMATCH')
    lh=list(csv.DictReader(open(B+f'triage/{h}/logon_history.csv')))
    col=c['collected_utc']
    inlog=sum((r['time_utc'][:19],int(r['event_id']),r['user'],r.get('logon_id','')) in sec[h] for r in lh)
    lo=min(r['time_utc'] for r in lh) if lh else None; hi=max(r['time_utc'] for r in lh) if lh else None
    start=(datetime.datetime.strptime(col[:19],'%Y-%m-%dT%H:%M:%S')-datetime.timedelta(days=45)).strftime('%Y-%m-%dT%H:%M:%S')
    expect=sum(1 for x in sec[h] if start<=x[0]<=col[:19])
    sv=list(csv.DictReader(open(B+f'triage/{h}/services.csv')))
    new=[(r['installed_utc'][:19],r['display_name']) for r in sv if r['installed_utc']>='2027-07-16']
    sm=sum(x in svc[h] for x in new)
    print(h,col,'case',c.get('case'),'| logon_history rows',len(lh),'found in Security log',inlog,'Security events in 45-day window',expect,'span',lo,hi,'| services since 07-16:',len(new),'with 7045',sm,'|',msg)
