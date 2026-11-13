#!/usr/bin/env python3
"""Merge endpoint caches, print shapes and rare values per (event,field)."""
import pickle,glob,collections
C=collections.defaultdict(collections.Counter); per={}
for f in sorted(glob.glob('/tmp/c/ep_*.pkl')):
    c=pickle.load(open(f,'rb')); per[f[-11:-4]]=c
    for k,v in c.items(): C[k].update(v)
print('shapes'); 
for k,v in C['shape'].most_common(): print('  ',v,k)
print('sep',C['sep'],'ms000',C['ms'])
for k in sorted(C):
    if not k.startswith('v:'): continue
    mc=C[k].most_common()
    if len(mc)<=25: print(k,len(mc),mc)
    else: print(k,len(mc),'top',mc[:8],'rare',[x for x in mc if x[1]<=3][:40])
