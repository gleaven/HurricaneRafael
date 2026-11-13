# web <-> dns <-> firewall joins
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st
glob_ans=defaultdict(set)
for o in ORGS:
    hw,w=load(o,'web'); hd,d=load(o,'dns'); hf,f=load(o,'firewall')
    out=[r for r in f if r['rule_name']=='outbound-web']
    # index fw by (src_ip, bytes_sent, bytes_recv)
    fidx=defaultdict(list)
    for r in out: fidx[(r['src_ip'],r['bytes_recv'])].append(r)
    didx=defaultdict(list)
    for r in d: didx[(r['client_ip'],r['query'])].append(ts(r['time_utc']))
    ans={}
    multi=Counter()
    for r in d:
        if r['answer'] not in('-','') and r['qtype']=='A':
            glob_ans[r['query']].add(r['answer'])
            if r['query'] in ans and ans[r['query']]!=r['answer']: multi[r['query']]+=1
            ans[r['query']]=r['answer']
    allowed=[r for r in w if r['action']=='allowed']; blocked=[r for r in w if r['action']!='allowed']
    nofw=0; nodns=0; dstmis=0; gaps=[]; dnsgaps=[]; portmis=0; natmissing=0
    used=set()
    for r in allowed:
        t=ts(r['time_utc'])
        c=[x for x in fidx.get((r['client_ip'],r['bytes_in']),[])]
        if not c: nofw+=1
        else:
            x=c[0]; used.add(id(x))
            start=ts(x['time_utc'])-timedelta(seconds=float(x['duration_s']))
            gaps.append((t-start).total_seconds())
            if r['host'] in ans and ans[r['host']]!=x['dst_ip']: dstmis+=1
            if (r['scheme']=='https')!=(x['dst_port']=='443'): portmis+=1
            if not x['nat_src_ip']: natmissing+=1
        q=didx.get((r['client_ip'],r['host']),[])
        prev=[(t-qt).total_seconds() for qt in q if timedelta(seconds=-2)<=t-qt<=timedelta(minutes=5,seconds=5)]
        if not prev: nodns+=1
        else: dnsgaps.append(min(prev))
    fw_noweb=sum(1 for x in out if id(x) not in used)
    print(f"== {o}: web allowed {len(allowed)} blocked {len(blocked)}; no fw session {nofw}; fw dst != dns answer {dstmis}; scheme/port mismatch {portmis}; no dns within 5min {nodns}; fw outbound without web row {fw_noweb} of {len(out)}")
    if gaps: print('   web time - fw start (s): min %.1f med %.1f max %.1f'%(min(gaps),st.median(gaps),max(gaps)), ' web-dns gap med %.1f max %.1f; share of dns gap==1s: %.2f'%(st.median(dnsgaps),max(dnsgaps),sum(1 for g in dnsgaps if g==1)/len(dnsgaps)))
    # blocked: any fw session? any dns?
    bf=sum(1 for r in blocked if fidx.get((r['client_ip'],r['bytes_in']))); print('   blocked rows with fw session',bf,'| blocked categories',Counter(r['category'] for r in blocked).most_common(5), 'bytes_in sample',[r['bytes_in'] for r in blocked[:5]])
    print('   queries with >1 distinct A answers within org',len(multi))
    # dns not tied to web: internal names etc
    wk={(r['client_ip'],r['host']) for r in w}
    dn=[r for r in d if (r['client_ip'],r['query']) not in wk]
    print('   dns rows w/o any web for that client+name',len(dn),Counter((r['qtype'],r['rcode'],r['answer']=='-') for r in dn).most_common(6))
    # AAAA answers
    print('   AAAA answers',Counter(r['answer'] for r in d if r['qtype']=='AAAA').most_common(3), '| doc-range answers',Counter(r['answer'] for r in d if r['answer'].startswith(('192.0.2.','198.51.100.','203.0.113.'))).most_common(6))
    # 5-minute rule: same client+query repeated within 5 min?
    last={};viol=0
    for r in d:
        k=(r['client_ip'],r['query'],r['qtype']); t=ts(r['time_utc'])
        if k in last and (t-last[k]).total_seconds()<300: viol+=1
        last[k]=t
    print('   dns repeats within 5 min (guide says none)',viol)
    # fw time ordering and duration
    print('   fw outbound duration: med %.1f p99 %.1f max %.1f'%(st.median(float(r['duration_s']) for r in out),sorted(float(r['duration_s']) for r in out)[len(out)*99//100],max(float(r['duration_s']) for r in out)))
import json
# cross-org answer consistency
print('names with different answers across orgs:',sum(1 for q,a in glob_ans.items() if len(a)>1),'of',len(glob_ans))
pickle.dump(dict(glob_ans),open(HERE+'/cache/dns_answers.pkl','wb'))
