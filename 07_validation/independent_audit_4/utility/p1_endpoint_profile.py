#!/usr/bin/env python3
"""Pass 1: endpoint telemetry value counts per month -> cache; key-order shapes; images; users; rare values."""
import json,sys,collections,pickle,os,re
m=sys.argv[1]
out=f'/tmp/c/ep_{m}.pkl'
C=collections.defaultdict(collections.Counter)
n=0
for line in open(f'endpoint/endpoint_{m}.jsonl',encoding='utf-8'):
    n+=1
    d=json.loads(line)
    et=d.get('event_type') or d.get('event')
    C['shape'][et+'|'+','.join(d.keys())]+=1
    C['event'][et]+=1
    for k,v in d.items():
        if k in('time_utc','pid','ppid','src_port','record_id','event_id','sha256','src_ip','dst_ip','query','command_line','target_path','path','file_path','answers','logon_id','parent_pid'): 
            continue
        if isinstance(v,(str,int,bool)) or v is None:
            C['v:'+et+':'+k][v]+=1
    for k in ('command_line','target_path','path','file_path','query'):
        if k in d and d[k] is not None:
            C['v:'+et+':'+k][re.sub(r'[0-9a-f]{8,}','H',str(d[k]))[:140]]+=1
    C['sep'][line[:2]+('sp' if '": ' in line else 'nosp')]+=1
    C['ms'][d['time_utc'][-5:-1]=='.000']+=1
pickle.dump(dict(C),open(out,'wb'))
print(m,n,C['event'].most_common())
