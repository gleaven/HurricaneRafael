"""Area 10: header and value sweep for answer-revealing columns/labels across every delivered CSV."""
import os, csv, re, collections, glob, json
from common import *
KW=re.compile(r'attack|malic|fraud|\bbot\b|is_bot|suspic|unauthor|spoof|fake|stolen|hostile|anomal|covert|illicit|truth|label|scenario|phase|thread|inject|synthetic|adversar|intrus|compromis|rogue|shell|ring|coordinated|inauthentic',re.I)
seen=collections.defaultdict(list); vals=collections.defaultdict(collections.Counter)
for root,_,files in os.walk(SRC):
    for fn in files:
        if not fn.endswith('.csv'): continue
        p=os.path.join(root,fn); rel=os.path.relpath(p,SRC); fam=re.sub(r'\d{4}-?\d{2}|_[A-Z0-9-]+\.csv$|FAC-[A-Z]+-\d+|AQS-[\w-]+|WQ-\d+|GAUGE-\d+|TG-\d+','*',rel)
        with open(p,newline='',encoding='utf-8',errors='replace') as f:
            r=csv.reader(f); h=next(r,[])
            if fam not in seen: seen[fam]=h
            for i,row in enumerate(r):
                if i>30000: break
                for c,v in zip(h,row):
                    if len(v)<90 and KW.search(v): vals[(fam,c)][v]+=1
print('CSV families',len(seen))
for fam,h in sorted(seen.items()):
    bad=[c for c in h if KW.search(c)]
    if bad: print('HEADER',fam,bad)
print('--- values matching keywords (family, column): top values')
for (fam,c),cn in sorted(vals.items()):
    print(fam,'|',c,'|',len(cn),'distinct |',dict(cn.most_common(4)))
