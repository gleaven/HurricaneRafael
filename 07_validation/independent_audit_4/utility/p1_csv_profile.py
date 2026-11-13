#!/usr/bin/env python3
"""Pass 1: generic multi-file CSV value counts (streamed). usage: glob skipcols(comma) -> prints columns with <=40 distinct, else top/rare."""
import csv,sys,glob,collections,re
files=sorted(glob.glob(sys.argv[1])); skip=set(sys.argv[2].split(',')) if len(sys.argv)>2 else set()
C=collections.defaultdict(collections.Counter); n=0
permonth=collections.defaultdict(collections.Counter)
for f in files:
    m=re.search(r'(20\d\d-\d\d)',f).group(1)
    for r in csv.DictReader(open(f,newline='',encoding='utf-8')):
        n+=1
        for k,v in r.items():
            if k in skip: continue
            C[k][v]+=1
print('rows',n)
for k,c in C.items():
    mc=c.most_common()
    if len(mc)<=40: print(f'[{k}] {len(mc)}:',mc)
    else: print(f'[{k}] {len(mc)} top',mc[:10],'rare',[x for x in mc if x[1]<=2][:25], 'n_singletons',sum(1 for x in mc if x[1]==1))
