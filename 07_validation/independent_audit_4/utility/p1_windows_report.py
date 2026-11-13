#!/usr/bin/env python3
import pickle,glob,collections,sys
for chan in ('security','system','defender'):
    C=collections.defaultdict(collections.Counter)
    for f in sorted(glob.glob(f'/tmp/c/win_{chan}_*.pkl')):
        for k,v in pickle.load(open(f,'rb')).items(): C[k].update(v)
    print('#####',chan,'sep',dict(C['sep']))
    for k,v in sorted(C['shape'].items()): print('  shape',v,k)
    for k in sorted(C):
        if not k.startswith('v:'): continue
        mc=C[k].most_common()
        if len(mc)<=20: print(k,len(mc),mc)
        else: print(k,len(mc),'top',mc[:6],'rare',[x for x in mc if x[1]<=2][:15],'nsingle',sum(1 for x in mc if x[1]==1))
