#!/usr/bin/env python3
"""Pass 1: windows JSONL value counts per channel/month -> cache /tmp/c/win_<chan>_<m>.pkl"""
import json,sys,collections,pickle,re
chan,m=sys.argv[1],sys.argv[2]
C=collections.defaultdict(collections.Counter); n=0
for line in open(f'windows/{chan}_{m}.jsonl',encoding='utf-8'):
    n+=1; d=json.loads(line)
    e=str(d.get('event_id'))
    C['shape'][e+'|'+','.join(d.keys())]+=1
    C['event'][e]+=1
    for k,v in d.items():
        if k in('time_utc','record_id','logon_id','src_port','pid','process_id','target_logon_id','subject_logon_id','logon_guid','ticket_hash'): continue
        if isinstance(v,(str,int,bool)) or v is None:
            C['v:'+e+':'+k][v if not isinstance(v,str) else re.sub(r'[0-9a-f]{12,}','H',v)[:120]]+=1
    C['sep'][('sp' if '": ' in line else 'nosp')]+=1
pickle.dump(dict(C),open(f'/tmp/c/win_{chan}_{m}.pkl','wb'))
print(chan,m,n,sorted(C['event'].items(),key=lambda x:-x[1]))
