#!/usr/bin/env python3
"""Aggregate pcap summaries: validity totals, joins to conn/ssl, MACs vs DHCP, TTL, SYN options, ClientHello fingerprints (hostile vs rest)."""
import sys,collections,pickle,glob; sys.path.insert(0,sys.path[0])
from lib import *
P=[pickle.load(open(f,'rb')) for f in sorted(glob.glob('/tmp/c/pcap_*.pkl'))]
print('files',len(P),'packets',sum(p['n'] for p in P),'unordered',sum(p['unordered'] for p in P),'bad ip csum',sum(p['badip'] for p in P),'bad l4 csum',sum(p['badl4'] for p in P),'truncated',sum(p['trunc'] for p in P),'ip len mismatch',sum(p['lenmis'] for p in P),'magic',{p['magic'] for p in P},'link',{p['link'] for p in P},'snap',{p['snap'] for p in P})
et=collections.Counter(); ttl=collections.Counter(); macs=collections.Counter(); so=collections.Counter(); wins=collections.Counter(); ipid0=0
for p in P: et.update(p['ethertypes']); ttl.update(p['ttl']); macs.update(p['macs']); so.update(p['synopts']); wins.update(p['wins']); ipid0+=p['ipid0']
print('ethertypes',et,'ip id==0',ipid0)
print('TTL (internal?,ttl)',sorted(ttl.items(),key=lambda x:-x[1])[:12])
print('SYN options variants',len(so),so.most_common(5),'SYN windows',wins.most_common(6))
m2ip=collections.defaultdict(set)
for (m,ip),v in macs.items(): m2ip[m].add(ip)
print('src MACs',len(m2ip),'MACs used by >1 internal ip',sum(1 for v in m2ip.values() if len(v-{"ext"})>1),'MAC of external-sourced packets',[m for m,v in m2ip.items() if 'ext' in v][:4])
h,D=fam('dhcp'); dm={r[3]:r[4] for r in D if r[6]!='corp-vpn'}
ipm=collections.defaultdict(set)
for (m,ip),v in macs.items():
    if ip!='ext': ipm[ip].add(m)
print('internal ips in pcap',len(ipm),'with DHCP mac known',sum(1 for i in ipm if i in dm),'pcap src MAC == DHCP MAC',sum(1 for i in ipm if i in dm and dm[i] in ipm[i]),'sample',[(i,ipm[i],dm.get(i)) for i in list(ipm)[:2]])
# joins
conn=zeek('conn'); ck=collections.defaultdict(list)
def edge(r):
    a=r[2].startswith(('10.','172.20.')); b=r[4].startswith(('10.','172.20.'))
    return a!=b
for r in conn:
    if edge(r): ck[(r[2],int(r[3]),r[4],int(r[5]),r[6])].append(float(r[0]))
tot=0;hit=0;exact=0
pf=0;pm=0
seen=set()
for p in P:
    for k,t in p['flows'].items():
        pf+=1
        c=ck.get(k)
        if not c: pm+=1; continue
        if min(abs(x-t) for x in c)<1e-5: exact+=1
        seen.add((k,round(min(c,key=lambda x:abs(x-t)),3)))
print('pcap flows',pf,'not in conn(edge)',pm,'first packet == conn ts',exact)
ne=sum(len(v) for v in ck.values()); print('edge conn flows',ne,'found in pcap',len(seen),'missing',ne-len(seen))
miss=collections.Counter()
sk={k for k,_ in seen}
for r in conn:
    if edge(r) and (r[2],int(r[3]),r[4],int(r[5]),r[6]) not in sk: miss[(r[6],r[5],r[11],r[15])]+=1
print('  missing by (proto,port,state,history)',miss.most_common(8))
# packets per flow
ppf=collections.Counter()
for p in P:
    for k,n in p['pk'].items(): ppf[(k[4],k[3] if k[3] in(443,80,25,53,123) else 'other',n)]+=1
print('packets kept per flow',sorted(ppf.items(),key=lambda x:-x[1])[:14])
# SNI vs ssl.log
ssl=collections.defaultdict(set)
for r in zeek('ssl'): ssl[(r[2],int(r[3]),r[4],int(r[5]))].add(r[8])
ok=0;bad=0;err=0;fp=collections.Counter();c2fp=collections.Counter();hostfp=collections.Counter();gwfp=collections.Counter(); fpc=collections.defaultdict(set)
for p in P:
    for k,v in p['hello'].items():
        if v is None or v[0]=='ERR': err+=1; continue
        if v[0] in ssl.get(k[:4],()): ok+=1
        else: bad+=1
        f=v[1]; fp[f]+=1; fpc[f].add(k[0])
        if k[2]==C2: c2fp[f]+=1
        if k[0].startswith(HOSTILE_SRC): hostfp[f]+=1
        elif k[2]=='10.72.4.88': gwfp[f]+=1
print('ClientHellos',ok+bad+err,'SNI == ssl.log',ok,'mismatch',bad,'unparsed',err,'distinct fingerprints',len(fp))
for f,n in fp.most_common(12): print('   fp',n,'srcs',len(fpc[f]),'ver',f[0],'ciphers',len(f[1])//4,'exts',f[2],'sv',f[4],'| C2',c2fp.get(f,0),'hostile-gw',hostfp.get(f,0),'other-gw',gwfp.get(f,0))
print('C2 fingerprints',len(c2fp),'hostile gw fps',len(hostfp),'other gw fps',len(gwfp))
fpay=collections.Counter()
for p in P:
    for k,v in p['firstpay'].items(): fpay[(k[3] if k[3] in(443,80,25) else 'other',v[:1].hex())]+=1
print('first payload byte by port',fpay.most_common(10))
