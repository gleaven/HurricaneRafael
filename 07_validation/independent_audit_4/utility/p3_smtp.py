#!/usr/bin/env python3
"""Mail gateway rows vs SMTP flows: presence, byte consistency, by verdict."""
import sys,collections; sys.path.insert(0,sys.path[0])
from lib import *
conn=zeek('conn'); smtp=collections.defaultdict(list)
for r in conn:
    if r[5]=='25' and r[4]=='172.20.5.10': smtp[int(float(r[0]))].append(r)
M=audit('mail_gateway_cbpwa'); c=collections.Counter(); used=collections.Counter()
for m in M:
    if m['direction']!='inbound': continue
    t=int(E(m['time_utc'])); f=[r for d in range(-6,7) for r in smtp.get(t+d,[])]
    if not f: c[(m['verdict'],'no flow within 6s')]+=1; continue
    best=min(f,key=lambda r:abs(float(r[0])-t)); used[best[1]]+=1
    ob=int(best[9]) if best[9]!='-' else 0
    c[(m['verdict'],'flow bytes >= size' if ob>=int(m['size_bytes']) else 'flow bytes < size', best[11])]+=1
for k,v in sorted(c.items()): print(v,k)
print('flows matched by >1 mail row',sum(1 for v in used.values() if v>1),'inbound smtp flows never matched',sum(len(v) for v in smtp.values())-len(used))
st=collections.Counter(r[11] for v in smtp.values() for r in v); print('smtp flow states',st)
