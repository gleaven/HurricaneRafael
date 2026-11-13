#!/usr/bin/env python3
"""Pass 1: generic per-column rarity scan for a CSV. usage: p1_colrare.py file [maxcard]"""
import csv,sys,collections
f=sys.argv[1]; maxcard=int(sys.argv[2]) if len(sys.argv)>2 else 40
rows=list(csv.DictReader(open(f,newline='')))
print(f,len(rows))
for c in rows[0].keys():
    cnt=collections.Counter(r[c] for r in rows)
    if len(cnt)<=maxcard:
        print(' ',c,len(cnt),sorted(cnt.items(),key=lambda x:-x[1]))
    else:
        rare=[(k,v) for k,v in cnt.items() if v<=2]
        top=cnt.most_common(5)
        print(' ',c,'card',len(cnt),'top',top,'n_rare',len(rare))
