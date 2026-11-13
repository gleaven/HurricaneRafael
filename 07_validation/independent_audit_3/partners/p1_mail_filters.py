from lib import *
from collections import Counter
tot=0
for o in ORGS:
    m=load(o,'mail')[1]; tot+=len(m)
    own=reg()['organisations'][ORGS.index(o)]['domain'] if False else None
    nm=[r for r in m if not r['message_id'].endswith('@mail>')]
    sd=Counter(r['sender_domain'] for r in m)
    print(o,len(m),'message_id not ending @mail>:',len(nm),Counter(r['sender_domain'] for r in nm).most_common(3),'| sender_domain values:',sd.most_common(4),'| internal senders not in registry:',sum(1 for r in m if r['direction']=='internal'))
    e=load(o,'endpoint_alerts')[1]
    print('    endpoint THREAT details',Counter(r['detail'] for r in e if r['event']=='THREAT_QUARANTINED'),'DEF details',Counter(r['detail'] for r in e if r['event']=='DEFINITIONS_UPDATED'))
print('total mail rows',tot)
