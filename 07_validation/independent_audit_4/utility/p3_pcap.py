#!/usr/bin/env python3
"""Pass 3: pcap validity for given month prefixes: header, ordering, IP/TCP/UDP checksums, lengths, MACs, TTL, IP id, flow openings, SNI. Caches per-file summaries to /tmp/c/pcap_<day>.pkl"""
import sys,struct,glob,collections,pickle,os,hashlib
def csum(b):
    if len(b)%2: b+=b'\0'
    s=sum(struct.unpack('!%dH'%(len(b)//2),b))
    while s>>16: s=(s&0xffff)+(s>>16)
    return (~s)&0xffff
def sni_ja3(p):
    # p = TLS record bytes starting at 0x16
    try:
        if p[0]!=0x16 or p[5]!=1: return None
        o=9; ver=p[o:o+2]; o+=2+32; sl=p[o]; o+=1+sl
        cl=struct.unpack('!H',p[o:o+2])[0]; cs=p[o+2:o+2+cl]; o+=2+cl
        ml=p[o]; o+=1+ml
        el=struct.unpack('!H',p[o:o+2])[0]; o+=2; end=o+el; exts=[]; sni=None; sv=None; alpn=None
        while o+4<=end and o+4<=len(p):
            t,l=struct.unpack('!HH',p[o:o+4]); d=p[o+4:o+4+l]; exts.append(t)
            if t==0: sni=d[5:5+struct.unpack('!H',d[3:5])[0]].decode('ascii','replace')
            if t==43: sv=d.hex()
            o+=4+l
        return sni,(ver.hex(),cs.hex(),tuple(exts),sl,sv),len(p)
    except Exception as e: return ('ERR',str(e),0)
for pref in sys.argv[1:]:
  for f in sorted(glob.glob(f'pcap/perimeter_{pref}*.pcap')):
    day=f[-14:-5]; out=f'/tmp/c/pcap_{f[-15:-5]}.pkl'
    if os.path.exists(out): continue
    b=open(f,'rb').read()
    magic,vmaj,vmin,tz,sig,snap,link=struct.unpack('<IHHiIII',b[:24])
    R=dict(file=f,magic=hex(magic),ver=(vmaj,vmin),snap=snap,link=link,n=0,unordered=0,badip=0,badl4=0,trunc=0,lenmis=0)
    o=24; last=0; flows={}; macs=collections.Counter(); ttl=collections.Counter(); ipid0=0; frag=0; ethertypes=collections.Counter(); synopts=collections.Counter(); wins=collections.Counter(); hello={}; firstpay={}; pk=collections.Counter()
    while o<len(b):
        ts,us,incl,orig=struct.unpack('<IIII',b[o:o+16]); p=b[o+16:o+16+incl]; o+=16+incl
        R['n']+=1; t=ts+us/1e6
        if t<last: R['unordered']+=1
        last=t
        if incl!=orig: R['trunc']+=1
        et=struct.unpack('!H',p[12:14])[0]; ethertypes[et]+=1
        if et!=0x0800: continue
        ip=p[14:]; ihl=(ip[0]&15)*4; tot=struct.unpack('!H',ip[2:4])[0]
        if tot!=len(ip): R['lenmis']+=1
        if csum(ip[:ihl])!=0: R['badip']+=1
        proto=ip[9]; src='.'.join(map(str,ip[12:16])); dst='.'.join(map(str,ip[16:20]))
        macs[(p[6:12].hex(':'),src if src.startswith(('10.','172.20.')) else 'ext')]+=1
        ttl[(src.startswith(('10.','172.20.')),ip[8])]+=1
        if ip[4:6]==b'\0\0': ipid0+=1
        l4=ip[ihl:tot]
        pseudo=ip[12:20]+struct.pack('!BBH',0,proto,len(l4))
        if proto in(6,17):
            if not(proto==17 and l4[6:8]==b'\0\0') and csum(pseudo+l4)!=0: R['badl4']+=1
            sp,dp=struct.unpack('!HH',l4[:4])
            if proto==6:
                fl=l4[13]; doff=(l4[12]>>4)*4; pay=l4[doff:]
                k=(src,sp,dst,dp,'tcp') 
                if fl&2 and not fl&16:
                    flows.setdefault(k,t); synopts[l4[20:doff].hex()]+=1; wins[struct.unpack('!H',l4[14:16])[0]]+=1
                kk=k if k in flows else (dst,dp,src,sp,'tcp')
                pk[kk]+=1
                if pay and k in flows and k not in firstpay:
                    firstpay[k]=pay[:8]
                    if pay[0]==0x16: hello[k]=sni_ja3(pay)
            else:
                k=(src,sp,dst,dp,'udp')
                if (dst,dp,src,sp,'udp') not in flows: flows.setdefault(k,t)
                pk[k if k in flows else (dst,dp,src,sp,'udp')]+=1
        elif proto==1: flows.setdefault((src,l4[0],dst,l4[1],'icmp'),t)
    R.update(flows=flows,macs=macs,ttl=ttl,ipid0=ipid0,ethertypes=ethertypes,synopts=synopts,wins=wins,hello=hello,firstpay=firstpay,pk=pk)
    pickle.dump(R,open(out,'wb'))
    print(day,R['n'],'pkts',len(flows),'flows unordered',R['unordered'],'badip',R['badip'],'badl4',R['badl4'],'trunc',R['trunc'],'lenmis',R['lenmis'],R['magic'],R['ver'],R['snap'],R['link'])
