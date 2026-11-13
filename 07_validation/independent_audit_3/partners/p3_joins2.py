# exact web<->firewall join on (client, bytes_out, bytes_in), nearest in time; dst vs DNS answer
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st
for o in ORGS:
    hw,w=load(o,'web'); hd,d=load(o,'dns'); hf,f=load(o,'firewall')
    out=[r for r in f if r['rule_name']=='outbound-web']
    fidx=defaultdict(list)
    for r in out: fidx[(r['src_ip'],r['bytes_sent'],r['bytes_recv'])].append(r)
    ans={}
    for r in d:
        if r['answer'] not in('-','') and r['qtype']=='A': ans[r['query']]=r['answer']
    host_dsts=defaultdict(Counter)
    n=0;nomatch=0;gaps=[];mis=0;misex=[];bytes_differ=0
    for r in w:
        if r['action']!='allowed': continue
        c=fidx.get((r['client_ip'],r['bytes_out'],r['bytes_in']),[])
        if not c:
            nomatch+=1; continue
        t=ts(r['time_utc'])
        x=min(c,key=lambda x:abs((ts(x['time_utc'])-timedelta(seconds=float(x['duration_s']))-t).total_seconds()))
        g=(t-(ts(x['time_utc'])-timedelta(seconds=float(x['duration_s'])))).total_seconds(); gaps.append(g)
        host_dsts[r['host']][x['dst_ip']]+=1
        if r['host'] in ans and ans[r['host']]!=x['dst_ip']:
            mis+=1
            if len(misex)<3 or 'aid-help' in r['host']: misex.append((r['time_utc'],r['client_ip'],r['host'],ans[r['host']],x['dst_ip'],x['_f'],x['_n']))
    print(f"== {o}: allowed web {sum(1 for r in w if r['action']=='allowed')} exact-bytes fw match missing {nomatch}; gap web-fwstart min {min(gaps):.1f} med {st.median(gaps):.1f} max {max(gaps):.1f}; fw dst != DNS A answer: {mis}")
    for e in misex[:12]: print('    ',e)
    nd=Counter(len(v) for v in host_dsts.values()); print('   distinct fw dst per web host:',sorted(nd.items()))
    # the 192.0.2.130 name
    print('   192.0.2.130 names',Counter(r['query'] for r in d if r['answer']=='192.0.2.130').most_common(3))
    # dst ips serving many hosts
    ipn=defaultdict(set)
    for hname,c in host_dsts.items():
        for ip in c: ipn[ip].add(hname)
    print('   dst ips shared by >1 web host',sum(1 for v in ipn.values() if len(v)>1),'of',len(ipn), list((k,sorted(v)[:4]) for k,v in ipn.items() if len(v)>1)[:3])
