from lib import *
from collections import Counter,defaultdict
allhosts=defaultdict(Counter)
for o in ORGS:
    h,rows=load(o,'web')
    cnt=Counter(r['host'] for r in rows)
    for v,n in cnt.items(): allhosts[v][o]=n
    print('== web rare hosts',o)
    for v,n in sorted(cnt.items(),key=lambda x:x[1]):
        if n<=6:
            ex=[r for r in rows if r['host']==v]
            print(f"   {v} n={n} cat={set(r['category'] for r in ex)} months={sorted(set(r['time_utc'][:10] for r in ex))[:6]} act={set(r['action'] for r in ex)} clients={sorted(set(r['client_ip'] for r in ex))[:4]}")
    h,rows=load(o,'dns')
    cnt=Counter(r['query'] for r in rows)
    wh=set(allhosts)
    print('== dns rare queries',o, 'distinct',len(cnt))
    rare=[(v,n) for v,n in cnt.items() if n<=3]
    import re
    kinds=Counter()
    for v,n in rare:
        ex=[r for r in rows if r['query']==v]
        kinds[(ex[0]['rcode'],ex[0]['qtype'])]+=1
    print('   rare kinds',kinds)
    for v,n in rare:
        ex=[r for r in rows if r['query']==v]
        if ex[0]['rcode']!='NXDOMAIN': print('   ',v,n,[(r['time_utc'],r['client_ip'],r['answer']) for r in ex])
    nx=[r for r in rows if r['rcode']=='NXDOMAIN']
    print('   NX examples',[r['query'] for r in nx[:8]])
