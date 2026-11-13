#!/usr/bin/env python3
"""Pass 1: flows involving the remote-access gateway 10.72.4.88; integral durations; which flows have them."""
import pickle,glob,collections,datetime
rows=[]
for f in sorted(glob.glob('/tmp/c/zeek_conn_*.pkl')):
    h,r=pickle.load(open(f,'rb')); rows+=r
def T(ts): return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%S')
ii=collections.Counter()
for r in rows:
    if r[8]!='-' and float(r[8])==int(float(r[8])): ii[(r[6],r[5],r[7],r[11])]+=1
print('integral durations by (proto,port,svc,state):',ii.most_common(20))
ext=[r for r in rows if r[4]=='10.72.4.88' and not r[2].startswith('10.')]
print('ext->jmp',len(ext))
c=collections.Counter((r[11],r[15],r[7]) for r in ext); print(c)
susp=[r for r in ext if r[2].startswith(('185.220.','45.141.','198.51.'))]
print('suspect flows',len(susp))
for r in susp: print(T(r[0]),r)
print('sample benign ext')
for r in ext[:8]: print(T(r[0]),r)
# jmp as originator
jo=collections.Counter((r[4],r[5],r[7]) for r in rows if r[2]=='10.72.4.88'); print('jmp orig',jo.most_common(40))
ji=collections.Counter((r[5],r[7]) for r in rows if r[4]=='10.72.4.88'); print('jmp resp',ji.most_common(40))
