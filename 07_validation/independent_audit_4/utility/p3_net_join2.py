#!/usr/bin/env python3
"""Follow-ups: OT deny rows with sensor flows; proxy https rows w/o ssl row; DMZ->corp SMTP without firewall row; conn ssl rows w/o ssl.log; S0/REJ constants; dns constants."""
import sys,collections,statistics; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn'); ck=collections.defaultdict(list)
for r in conn: ck[(r[2],r[3],r[4],r[5],r[6])].append(r)
h,F=fam('fw_ot'); ix={n:i for i,n in enumerate(h)}
c=collections.Counter()
for r in F:
    if r[ix['action']]=='deny':
        x=ck.get((r[ix['src_ip']],r[ix['src_port']],r[ix['dst_ip']],r[ix['dst_port']],r[ix['proto']]))
        c[(x[0][11],x[0][15]) if x else 'none']+=1
print('OT deny rows vs conn state',dict(c))
smtp=[r for r in conn if r[4]=='10.14.10.30' and r[5]=='25']; print('flows to 10.14.10.30:25',collections.Counter(r[2] for r in smtp).most_common(3))
h,P=fam('proxy'); ix={n:i for i,n in enumerate(h)}
ssl={r[1]:r for r in zeek('ssl')}
byc=collections.defaultdict(list)
for r in conn:
    if r[5]=='443': byc[(r[2],int(float(r[0])))].append(r)
st=collections.Counter()
for r in P:
    if r[ix['scheme']]!='https' or r[ix['action']]!='allowed': continue
    t=int(E(r[ix['time_utc']])); c2=[x for x in byc.get((r[ix['client_ip']],t),[])+byc.get((r[ix['client_ip']],t-1),[]) if x[9]==r[ix['bytes_out']] and x[10]==r[ix['bytes_in']]]
    if c2 and c2[0][1] not in ssl: st[(r[ix['status']],c2[0][11],c2[0][7])]+=1
print('proxy https rows whose flow has no ssl.log row',dict(st))
sc=[r for r in conn if r[7]=='ssl']; print('conn service=ssl',len(sc),'with ssl.log row',sum(1 for r in sc if r[1] in ssl),'states of those without',collections.Counter(r[11] for r in sc if r[1] not in ssl))
print('ssl.log rows without conn',sum(1 for u in ssl if not any(True for _ in [0]) ) if False else '', )
cu={r[1] for r in conn}
for l in ('ssl','dns','http'):
    rows=zeek(l); print(l,'rows',len(rows),'uid not in conn',sum(1 for r in rows if r[1] not in cu))
dns=[r for r in conn if r[7]=='dns']
print('dns flows: duration distinct',len({r[8] for r in dns}),'orig_bytes distinct',len({r[9] for r in dns}),'resp distinct',len({r[10] for r in dns}),'pkts',collections.Counter((r[16],r[18]) for r in dns).most_common(3))
s0=[r for r in conn if r[11]=='S0']; print('S0: resp_pkts',collections.Counter(r[18] for r in s0).most_common(3),'dur',collections.Counter(r[8] for r in s0).most_common(4),'orig_pkts',collections.Counter(r[16] for r in s0).most_common(4),'orig_bytes',collections.Counter(r[9] for r in s0).most_common(3))
rej=[r for r in conn if r[11]=='REJ']; print('REJ dur',collections.Counter(r[8] for r in rej).most_common(3),'pkts',collections.Counter((r[16],r[18]) for r in rej).most_common(3))
oth=[r for r in conn if r[11]=='OTH']; print('OTH',collections.Counter((r[6],r[7],r[15]) for r in oth).most_common(5),'with bytes>0',sum(1 for r in oth if r[9] not in('-','0')))
big=[r for r in conn if r[6]=='tcp' and r[10]!='-' and int(r[10])>1_000_000]
print('flows >1MB recv',len(big),'with orig_pkts < resp_pkts/4',sum(1 for r in big if int(r[16])<int(r[18])/4), 'resp bytes/pkt median',statistics.median(int(r[10])/max(1,int(r[18])) for r in big),'max',max(int(r[10])/max(1,int(r[18])) for r in big))
bpp=[int(r[9])/max(1,int(r[16])) for r in conn if r[6]=='tcp' and r[9] not in('-','0')]; print('tcp orig bytes/pkt >1460:',sum(1 for x in bpp if x>1460),'of',len(bpp))
bpr=[int(r[10])/max(1,int(r[18])) for r in conn if r[6]=='tcp' and r[10] not in('-','0')]; print('tcp resp bytes/pkt >1460:',sum(1 for x in bpr if x>1460),'of',len(bpr))
print('proto/service/port combos',len({(r[6],r[7],r[5]) for r in conn}))
icmp=[r for r in conn if r[6]=='icmp']; print('icmp sample',icmp[0][2:12],collections.Counter((r[3],r[5]) for r in icmp).most_common(3))
ntp=[r for r in conn if r[7]=='ntp']; print('ntp bytes',collections.Counter((r[9],r[10]) for r in ntp).most_common(2),'src',collections.Counter(r[2] for r in ntp).most_common(4))
http=zeek('http'); print('http UAs',len({r[12] for r in http}),'status',collections.Counter(r[15] for r in http).most_common(8),'methods',collections.Counter(r[7] for r in http).most_common(5))
n=zeek('notice'); print('notices with msg "-"',sum(1 for r in n if r[6]=='-'),'of',len(n))
ssl_=list(ssl.values()); print('TLSv12 with TLS13 suite',sum(1 for r in ssl_ if r[6]=='TLSv12' and r[7].startswith('TLS_AES')),'TLSv13 with certs',sum(1 for r in ssl_ if r[6]=='TLSv13' and r[11]!='(empty)'),'resumed with certs',sum(1 for r in ssl_ if r[9]=='T' and r[11]!='(empty)'),'TLS12 full handshake without cert',sum(1 for r in ssl_ if r[6]=='TLSv12' and r[9]=='F' and r[11]=='(empty)'))
x=zeek('x509'); fp={r[1] for r in x}; print('cert_chain_fps not in x509',sum(1 for r in ssl_ if r[11]!='(empty)' and not all(f in fp for f in r[11].split(','))), 'x509 rows',len(x),'distinct fp',len(fp))
# tiny TLS full handshakes
small=[r for r in conn if r[1] in ssl and ssl[r[1]][9]=='F' and r[11]=='SF' and int(r[10])<1200]
print('non-resumed established TLS with resp_bytes<1200:',len(small),'of',sum(1 for r in conn if r[1] in ssl and ssl[r[1]][9]=='F'),'; with cert chain (TLS1.2) and resp<1200:',sum(1 for r in small if ssl[r[1]][11]!='(empty)'))
