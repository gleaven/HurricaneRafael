# Pass 1: per-column value frequency; list low-cardinality columns fully and rare values (<=10) in mid-cardinality columns
from lib import *
from collections import Counter
import sys
kinds=sys.argv[1:] or KINDS
for k in kinds:
    for o in ORGS:
        h,rows=load(o,k)
        print(f"\n##### {o} {k} n={len(rows)}")
        for c in h:
            if c in('time_utc',): continue
            cnt=Counter(r[c] for r in rows)
            if len(cnt)<=40:
                print(f"  {c} [{len(cnt)}]: "+", ".join(f"{v!r}:{n}" for v,n in cnt.most_common()))
            else:
                rare=[(v,n) for v,n in cnt.items() if n<=3]
                print(f"  {c} [{len(cnt)} distinct] top: "+", ".join(f"{v!r}:{n}" for v,n in cnt.most_common(6))+f" | n<=3 values: {len(rare)}")
