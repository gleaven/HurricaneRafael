#!/usr/bin/env python3
"""Pass 1 artefact filters on conn.log: durations with trailing 000 (ms precision), ts with trailing zeros, tiny established TLS, pkts/bytes ratio outliers, src port outside ephemeral range, ip_bytes arithmetic."""
import pickle,glob,collections,datetime
rows=[]
for f in sorted(glob.glob('/tmp/c/zeek_conn_*.pkl')):
    h,r=pickle.load(open(f,'rb')); rows+=r
def T(ts): return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%S')
d3=[r for r in rows if r[8]!='-' and r[8].endswith('000') and float(r[8])!=int(float(r[8]))]
print('durations ending 000 (non-integral):',len(d3),'expected ~',round(sum(1 for r in rows if r[8]!='-' and float(r[8])!=int(float(r[8])))/1000))
c=collections.Counter((r[2],r[4],r[5]) for r in d3); print(c.most_common(25))
for r in d3[:40]: print('  ',T(r[0]),r[2:12])
t3=[r for r in rows if r[0].endswith('000')]
print('ts ending 000:',len(t3),'expected',len(rows)//1000, collections.Counter((r[2],r[4],r[5]) for r in t3).most_common(8))
tiny=[r for r in rows if r[7]=='ssl' and r[11]=='SF' and r[10]!='-' and int(r[10])<1000]
print('ssl SF with resp_bytes<1000:',len(tiny),collections.Counter((r[4],r[5]) for r in tiny).most_common(10))
tiny2=[r for r in rows if r[7]=='ssl' and r[11]=='SF' and r[9]!='-' and int(r[9])<400]
print('ssl SF with orig_bytes<400:',len(tiny2),collections.Counter((r[4],r[5]) for r in tiny2).most_common(10))
# ip bytes arithmetic for tcp: ip_bytes = bytes + 40*pkts ?
k=collections.Counter()
for r in rows:
    if r[6]=='tcp' and r[9]!='-':
        k[(int(r[17])-int(r[9]))/max(1,int(r[16]))]+=1
print('tcp (orig_ip_bytes-orig_bytes)/orig_pkts distinct',len(k),k.most_common(6))
k=collections.Counter()
for r in rows:
    if r[6]=='udp' and r[9]!='-':
        k[(int(r[17])-int(r[9]))/max(1,int(r[16]))]+=1
print('udp overhead per pkt',k.most_common(5))
sp=collections.Counter()
for r in rows:
    p=int(r[3])
    sp['<1024' if p<1024 else '1024-32767' if p<32768 else '32768-49151' if p<49152 else '49152+']+=1
print('src port ranges',sp)
low=collections.Counter((r[2],r[3],r[5]) for r in rows if int(r[3])<49152 and r[6]!='icmp'); print(len(low),low.most_common(25))
