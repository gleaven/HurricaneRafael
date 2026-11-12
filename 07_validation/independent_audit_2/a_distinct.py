# For each column of a csv, print distinct-value counts when small, to find singling-out values
import sys, collections
from common import *
path=sys.argv[1]; maxd=int(sys.argv[2]) if len(sys.argv)>2 else 12
rs=load(path); print(path,len(rs))
for c in rs[0].keys():
    k=cnt(rs,c)
    if len(k)<=maxd: print('  ',c,dict(k.most_common()))
    else:
        rare=[(v,n) for v,n in k.items() if n<=3]
        print('  ',c,'distinct',len(k),'empty',k.get('',0),'top',k.most_common(3))
