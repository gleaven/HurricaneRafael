from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st, ipaddress
R=reg()
tot_dup=Counter(); unsorted=Counter(); wrongmonth=Counter()
for o in ORGS:
    for k in KINDS:
        h,rows=load(o,k)
        seen=Counter(tuple(r[c] for c in h) for r in rows); tot_dup[k]+=sum(v-1 for v in seen.values() if v>1)
        prev=None;pf=None
        for r in rows:
            if pf==r['_f'] and prev and r['time_utc']<prev: unsorted[k]+=1
            prev=r['time_utc'];pf=r['_f']
            if r['time_utc'][:7]!=r['_f'].split('_')[-1][:7]: wrongmonth[k]+=1
print('exact duplicate rows',dict(tot_dup),'| out-of-order rows',dict(unsorted),'| rows in wrong month file',dict(wrongmonth))
for o in ORGS:
    a=load(o,'auth')[1]
    # 4625 followed by success same host+account within 2 min
    f=[r for r in a if r['event_id']=='4625']; succ=defaultdict(list)
    for r in a:
        if r['event_id']=='4624': succ[(r['host'],r['account'])].append(ts(r['time_utc']))
    fol=sum(1 for r in f if any(0<=(t-ts(r['time_utc'])).total_seconds()<=180 for t in succ[(r['host'],r['account'])]))
    rf=[r for r in a if r['logon_type']=='remote' and r['result']=='FAILED']; rs=defaultdict(list)
    for r in a:
        if r['logon_type']=='remote' and r['result']=='SUCCESS': rs[(r['account'],r['src_ip'])].append(ts(r['time_utc']))
    rfol=sum(1 for r in rf if any(0<=(t-ts(r['time_utc'])).total_seconds()<=300 for t in rs[(r['account'],r['src_ip'])]))
    perhost=Counter(r['account'] for r in rf)
    w=load(o,'web')[1]; fw=load(o,'firewall')[1]; m=load(o,'mail')[1]
    den=[r for r in fw if r['action']=='deny']; pub=ipaddress.ip_network([x for x in R['organisations'] if x['org_id']==o.upper()][0]['address_plan']['public_block'])
    netb=sum(1 for r in den if ipaddress.ip_address(r['dst_ip']) in (pub.network_address,pub.broadcast_address))
    outb=[r for r in m if r['direction']=='outbound']
    print(f"{o}: 4625 n={len(f)} followed by 4624 within 3min {fol}; remote FAILED n={len(rf)} followed by SUCCESS same ip within 5min {rfol}, max fails per account {max(perhost.values()) if perhost else 0}; web status {dict(Counter(r['status'] for r in w))} methods {dict(Counter(r['method'] for r in w))}; deny dst = network/broadcast addr {netb}; deny src distinct {len(set(r['src_ip'] for r in den))}/{len(den)}; outbound mail recipient domains {Counter(r['recipient'].split('@')[1] for r in outb).most_common(3)}")
# http url_path patterns
import re
c=Counter()
for o in ORGS:
    for r in load(o,'web')[1]:
        if r['scheme']=='http': c[re.sub(r'[0-9a-f]{6,8}','H',r['url_path'])]+=1
print('http url_path patterns',c.most_common())
# web bytes == fw bytes identical share (city)
# disasteraid first seen
