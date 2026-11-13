#!/usr/bin/env python3
"""Pass 1: compact per-column rarity scan. usage: p1_colrare2.py file [maxcard] ; prints low-card columns fully (truncated) and rare values of others"""
import csv,sys,collections
f=sys.argv[1]; maxcard=int(sys.argv[2]) if len(sys.argv)>2 else 15
rows=list(csv.DictReader(open(f,newline='')))
print('##',f,len(rows))
for c in rows[0].keys():
    cnt=collections.Counter(r[c] for r in rows)
    if len(cnt)<=maxcard:
        print(' ',c,len(cnt),str(sorted(cnt.items(),key=lambda x:-x[1]))[:900])
    else:
        rare=[(k,v) for k,v in cnt.items() if v<=2]
        print(' ',c,'card',len(cnt),'top',str(cnt.most_common(4))[:300],'n_rare',len(rare), str(rare[:6])[:300] if len(rare)<40 else '')
