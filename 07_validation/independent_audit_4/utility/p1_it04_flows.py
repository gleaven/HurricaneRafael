#!/usr/bin/env python3
"""Pass 1: flows of the foothold workstation 10.14.22.47 and C2 104.21.88.43; beacon interval regularity; byte patterns; compare to benign periodic agent."""
import pickle,glob,collections,datetime,statistics,sys
ip=sys.argv[1] if len(sys.argv)>1 else '10.14.22.47'
rows=[]
for f in sorted(glob.glob('/tmp/c/zeek_conn_*.pkl')):
    h,r=pickle.load(open(f,'rb')); rows+=r
def T(ts): return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%S')
mine=[r for r in rows if r[2]==ip or r[4]==ip]
print('flows',len(mine))
c=collections.Counter((r[2] if r[2]!=ip else 'ME', r[4] if r[4]!=ip else 'ME', r[5],r[7]) for r in mine)
for k,v in c.most_common(45): print(v,k)
c2=[r for r in rows if r[4]=='104.21.88.43' or r[2]=='104.21.88.43']
print('C2 flows',len(c2),collections.Counter(r[2] for r in c2))
ts=[float(r[0]) for r in c2]
iv=[b-a for a,b in zip(ts,ts[1:])]
print('first',T(ts[0]),'last',T(ts[-1]))
print('interval quantiles (s)',[round(x) for x in statistics.quantiles(iv,n=10)],'min',round(min(iv)),'max',round(max(iv)))
print('hour-of-day',sorted(collections.Counter(datetime.datetime.utcfromtimestamp(t).hour for t in ts).items()))
print('by date',sorted(collections.Counter(T(r[0])[:10] for r in c2).items()))
print('dur/bytes sample')
for r in c2[:6]+sorted(c2,key=lambda r:-int(r[9]))[:12]: print(T(r[0]),r[2],r[3],r[8],r[9],r[10],r[11],r[15])
print('orig_bytes stats',statistics.median(int(r[9]) for r in c2),max(int(r[9]) for r in c2),'resp',statistics.median(int(r[10]) for r in c2))
