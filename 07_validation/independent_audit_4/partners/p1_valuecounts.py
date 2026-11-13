# Pass 1 trick 1: value counts on every low-cardinality column, per org; list rare values
import sys; sys.path.insert(0,'.')
from common import *
t=sys.argv[1]
d=load(t)
for c in d.columns:
    if c in('time_utc','_file','org'): continue
    n=d[c].nunique()
    if n<=60:
        print(f"\n### {t}.{c} nunique={n}")
        print(pd.crosstab(d[c],d['org']).to_string())
    else:
        vc=d.groupby('org')[c].nunique()
        print(f"\n### {t}.{c} nunique={n} per org {vc.to_dict()}")
