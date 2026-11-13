from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import statistics as st
for o in ORGS:
    h,a=load(o,'auth'); hf,f=load(o,'firewall')
    rem=[r for r in a if r['logon_type']=='remote']
    inb=[r for r in f if r['rule_name']=='inbound-remote-access']
    byip=defaultdict(list)
    for r in inb: byip[r['src_ip']].append(r)
    d=[float(r['duration_s']) for r in inb]
    matched=0; offs=[]; used=set()
    for r in rem:
        t=ts(r['time_utc'])
        best=None
        for x in byip.get(r['src_ip'],[]):
            if id(x) in used: continue
            start=ts(x['time_utc'])-timedelta(seconds=float(x['duration_s']))
            off=(t-start).total_seconds()
            if -5<=off<=120 and (best is None or abs(off)<abs(best[0])): best=(off,x)
        if best: matched+=1; offs.append(best[0]); used.add(id(best[1]))
    print(f"{o}: remote sign-ons {len(rem)} (SUCCESS {sum(1 for r in rem if r['result']=='SUCCESS')}); inbound-remote-access fw rows {len(inb)}; sign-ons with fw session starting -5..120s before: {matched}; fw rows not tied to any sign-on {len(inb)-len(used)}; fw dur med {st.median(d):.0f}s p95 {sorted(d)[len(d)*95//100]:.0f} max {max(d):.0f}; offs med {st.median(offs) if offs else None}")
    un=[x for x in inb if id(x) not in used]
    if un: print('    untied fw: src ips also seen in auth?',sum(1 for x in un if any(r['src_ip']==x['src_ip'] for r in rem[:0])),'dur med',st.median(float(x['duration_s']) for x in un),'bytes_recv med',st.median(int(x['bytes_recv']) for x in un),'sample',[(x['time_utc'],x['src_ip'],x['duration_s'],x['bytes_sent'],x['bytes_recv']) for x in un[:2]])
    authips={r['src_ip'] for r in rem}
    print('    untied fw rows whose src_ip never signs on:',sum(1 for x in un if x['src_ip'] not in authips))
