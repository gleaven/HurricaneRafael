#!/usr/bin/env python3
"""Pass 1: Zeek conn rarity scan (expects /tmp/z_conn.tsv = all conn.log rows without headers; build with: cat zeek/*/conn.log | grep -v '^#' > /tmp/z_conn.tsv)"""
import collections,sys
svc=collections.Counter(); st=collections.Counter(); hist=collections.Counter(); port=collections.Counter(); proto=collections.Counter()
lo=collections.Counter(); rows=0; day=collections.Counter()
pktratio=collections.Counter(); 
for l in open('/tmp/z_conn.tsv'):
    f=l.rstrip('\n').split('\t'); rows+=1
    svc[(f[6],f[7])]+=1; st[f[11]]+=1; hist[f[15]]+=1; port[(f[6],f[5],f[7])]+=1; lo[(f[12],f[13])]+=1
    day[int(float(f[0]))//86400]+=1
print(rows); print('svc',sorted(svc.items(),key=lambda x:-x[1])); print('state',st); print('hist',hist); print('local',lo)
print('ports',len(port)); 
for k,v in sorted(port.items(),key=lambda x:x[1]): 
    if v<=200: print(v,k)
