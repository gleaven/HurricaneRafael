# Pass 2 item 7 + guide claims: web <-> dns <-> firewall joins
import sys,re,collections,bisect; sys.path.insert(0,'.')
from common import *
w=load('web'); d=load('dns'); f=load('firewall')
w['t']=ts(w).astype('int64')//10**9; d['t']=ts(d).astype('int64')//10**9; f['te']=ts(f).astype('int64')//10**9
f['dur']=f.duration_s.astype(float); f['ts_']=f.te-f.dur
for o in ORGS:
    wo=w[(w.org==o)]; al=wo[wo.action=='allowed']; do=d[d.org==o]; fo=f[(f.org==o)&(f.action=='allow')]
    # dns index: (client,query)-> sorted times, answers
    di=collections.defaultdict(list)
    for c,q,t,a,rc in zip(do.client_ip,do['query'],do.t,do.answer,do.rcode): di[(c,q)].append((t,a,rc))
    fi=collections.defaultdict(list)
    for s,dst,t0,te,dp,bs,br,nat in zip(fo.src_ip,fo.dst_ip,fo.ts_,fo.te,fo.dst_port,fo.bytes_sent,fo.bytes_recv,fo.nat_src_ip): fi[(s,dst)].append((t0,te,dp,bs,br))
    nodns=0; lag=[]; nofw=0; fwlag=[]; port_bad=0; bytes_eq=0; n=0; cached=0; bytes_ratio=[]
    for c,h,t,sch,bo,bi in zip(al.client_ip,al.host,al.t,al.scheme,al.bytes_out,al.bytes_in):
        n+=1
        L=[x for x in di.get((c,h),[]) if x[0]<=t]
        if not L: nodns+=1; continue
        t0,ans,rc=L[-1]; lag.append(t-t0)
        if t-t0>300: cached+=1
        S=[x for x in fi.get((c,ans),[]) if abs(x[0]-t)<=5]
        if not S: nofw+=1; continue
        s=S[0]; fwlag.append(s[0]-t)
        if (sch=='https')!=(s[2]=='443'): port_bad+=1
        if int(bo)==int(s[3]) and int(bi)==int(s[4]): bytes_eq+=1
        bytes_ratio.append(int(s[4])/max(int(bi),1))
    lag=np.array(lag); br=np.array(bytes_ratio)
    # reverse: outbound web fw sessions without a web row
    web_rules=fo[fo.app.isin(['ssl','web-browsing'])&fo.src_ip.str.startswith('10.')&fo.rule_name.str.contains('(?i)web|http|Users-Internet')]
    wk=set(zip(al.client_ip,al.t))
    rev_missing=sum(1 for s,t0 in zip(web_rules.src_ip,web_rules.ts_) if not any((s,int(round(t0))+k) in wk for k in range(-5,6)))
    # blocked rows: fw session?
    bl=wo[wo.action=='blocked']; 
    print(f"{o}: allowed web {n}; no prior DNS {nodns}; dns lag s p50={np.median(lag):.0f} max={lag.max():.0f} >300s={cached}; no fw session to DNS answer within 5s: {nofw}; scheme/port mismatch {port_bad}; web bytes == fw bytes {bytes_eq}; fw/web bytes_in ratio p5={np.percentile(br,5):.2f} p50={np.median(br):.2f} p95={np.percentile(br,95):.2f}; outbound web fw sessions {len(web_rules)} without web row {rev_missing}; blocked {len(bl)}")
    # DNS rows that lead to nothing
    dq=do[do.qtype.isin(['A','AAAA'])]
    print('   dns rows',len(do),'qtypes',do.qtype.value_counts().to_dict(),'rcodes',do.rcode.value_counts().to_dict())
    # same (client,query) repeated within 300 s (guide: cached)
    rep=0
    for k,L in di.items():
        tt=sorted(x[0] for x in L)
        rep+=sum(1 for a,b in zip(tt,tt[1:]) if b-a<300)
    print('   repeated lookups of same name by same client within 300 s:',rep)
    # answers stable per name?
    na=do[do.qtype=='A'].groupby('query').answer.nunique(); print('   names with >1 distinct A answers:',(na>1).sum(),'of',len(na),'max',na.max())
