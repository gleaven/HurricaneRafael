#!/usr/bin/env python3
"""Pass 1 trick: value counts on every column of a CSV (categorical: <=60 distinct shown; else top 8 + bottom 8)."""
import csv,sys,collections
for f in sys.argv[1:]:
    rows=list(csv.DictReader(open(f,newline='',encoding='utf-8')))
    print('=====',f,len(rows))
    if not rows: continue
    for c in rows[0].keys():
        cnt=collections.Counter(r[c] for r in rows)
        n=len(cnt)
        if n<=40:
            print(f'  [{c}] {n} distinct:', dict(cnt.most_common()))
        else:
            mc=cnt.most_common()
            print(f'  [{c}] {n} distinct; top:',mc[:6],' bottom:',mc[-6:])
