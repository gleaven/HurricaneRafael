# Pass 3: mail rows <-> firewall SMTP sessions; source addresses of the lure wave
import sys,re,collections; sys.path.insert(0,'.')
from common import *
R=reg(); m=load('mail'); f=load('firewall')
m['t']=ts(m).astype('int64')//10**9; f['te']=ts(f).astype('int64')//10**9; f['t0']=f.te-f.duration_s.astype(float)
for o in R['organisations']:
    k=o['org_id'].lower(); mx=[h for h in o['hosts'] if h['host_id']==o['mail_gateway']][0]
    fo=f[(f.org==k)&(f.app=='smtp')&(f.action=='allow')]
    mi=m[(m.org==k)&(m.direction=='inbound')]; mo=m[(m.org==k)&(m.direction=='outbound')]
    fin=fo[fo.dst_ip==mx['ip']]; fout=fo[fo.src_ip==mx['ip']]
    print(f"\n{k}: gateway {mx['host_id']} {mx['ip']} site {mx['site_id']}; inbound mail {len(mi)} vs inbound smtp sessions {len(fin)}; outbound mail {len(mo)} vs outbound smtp sessions {len(fout)}; other smtp allow {len(fo)-len(fin)-len(fout)}")
    if len(fin)==0: continue
    # match inbound by time: session covering message time
    ti=np.sort(fin.te.values); 
    lag=[]; srcs=[]
    fin_s=fin.sort_values('te'); te=fin_s.te.values; t0=fin_s.t0.values; src=fin_s.src_ip.values
    for t in mi.t.values:
        i=np.searchsorted(te,t); ok=None
        for jx in range(max(0,i-3),min(len(te),i+4)):
            if t0[jx]-2<=t<=te[jx]+2: ok=jx;break
        lag.append(ok is not None); srcs.append(src[ok] if ok is not None else None)
    mi=mi.assign(matched=lag,smtp_src=srcs)
    print('  inbound messages with a covering smtp session:',mi.matched.sum(),'of',len(mi))
    # one sender domain -> stable source address?
    g=mi[mi.matched].groupby('sender_domain').smtp_src.nunique()
    print('  sending domains with >1 source address:',(g>1).sum(),'of',len(g),'; max',g.max())
    L=mi[mi.sender_domain=='aid-help-portal.example']
    if len(L):
        print('  lure wave smtp sources:',L.smtp_src.value_counts().head(8).to_dict(),'distinct',L.smtp_src.nunique())
        print('  lure source /24:',L.smtp_src.str.rsplit('.',n=1).str[0].value_counts().to_dict())
    V=mi[mi.sender_domain.str.contains('marine-certification')]
    if len(V): print('  vendor lure smtp source:',V.smtp_src.tolist())
    for dom in ['benefits-portal.example','training-lms.example','federal-notices.example']:
        B=mi[mi.sender_domain==dom]
        if len(B): print('  ',dom,'sources',B.smtp_src.nunique(),B.smtp_src.value_counts().head(3).to_dict())
    doc=fin[fin.src_ip.str.match(r'^(203\.0\.113|198\.51\.100|192\.0\.2)\.')]
    print('  inbound smtp from documentation ranges:',len(doc), doc.src_ip.str.rsplit('.',n=1).str[0].value_counts().to_dict())
