#!/usr/bin/env python3
"""Pass 3: pcap vs Zeek conn for given days: every edge-crossing conn row has a SYN at conn ts; pcap validity. usage: p3_pcap_check.py 2027-08-30 [...]"""
import struct,sys,collections
B="./05_other_sources/network_logs/"
def inside(ip): return ip.startswith('10.') or ip.startswith('172.20.5.')
for day in sys.argv[1:]:
    f=open(B+f'pcap/perimeter_{day}.pcap','rb').read(); off=24; syn={}; n=0; cipher=collections.Counter(); mac=collections.Counter(); ttl=collections.Counter()
    while off<len(f):
        ts,us,incl,orig=struct.unpack('<IIII',f[off:off+16]); off+=16; p=f[off:off+incl]; off+=incl; n+=1
        ip=p[14:]; ihl=(ip[0]&0xf)*4
        if ip[9]!=6: continue
        src='.'.join(map(str,ip[12:16])); dst='.'.join(map(str,ip[16:20])); sp,dp=struct.unpack('!HH',ip[ihl:ihl+4]); fl=ip[ihl+13]
        if fl&0x3f==2: syn[(src,str(sp),dst,str(dp))]=ts+us/1e6; mac[(p[6:12].hex(),inside(src))]+=1; ttl[(ip[8],inside(src))]+=1
        doff=(ip[ihl+12]>>4)*4; pl=ip[ihl+doff:]
        if len(pl)>44 and pl[0]==0x16 and pl[5]==2:
            sid=pl[43]; cipher[pl[44+sid:46+sid].hex()]+=1
    tot=miss=0; dts=[]
    extra=set(syn)
    for l in open(B+f'zeek/{day}/conn.log'):
        if l[0]=='#': continue
        c=l.split('\t')
        if inside(c[2])!=inside(c[4]) and c[6]=='tcp':
            tot+=1; k=(c[2],c[3],c[4],c[5])
            if k in syn: dts.append(abs(syn[k]-float(c[0]))); extra.discard(k)
            else: miss+=1
    print(day,'packets',n,'SYNs',len(syn),'edge conn rows',tot,'missing in pcap',miss,'max |dt|',max(dts) if dts else None,'pcap flows without conn row',len(extra))
    print('   serverhello ciphers',dict(cipher),'src MACs of SYN',len(mac),mac.most_common(3),'ttl',ttl.most_common(6))
