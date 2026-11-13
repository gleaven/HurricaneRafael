#!/usr/bin/env python3
"""Generic profiler: value counts for low-card columns, shape profile for text columns,
timestamp fraction profile. Usage: prof.py <label> <glob...> ; writes cache/<label>.json and prints rare things."""
import sys, csv, json, re, glob, collections, os
csv.field_size_limit(10**9)
RARE=30
def shape(s):
    s=re.sub(r'[A-Z]+','A',s); s=re.sub(r'[a-z]+','a',s); s=re.sub(r'[0-9]+','9',s)
    return s
def rows(path):
    if path.endswith('.jsonl'):
        with open(path,encoding='utf-8',errors='replace') as f:
            for line in f:
                line=line.strip()
                if not line: continue
                d=json.loads(line)
                flat={}
                def fl(p,o):
                    if isinstance(o,dict):
                        for k,v in o.items(): fl(p+k+'.',v)
                    else: flat[p[:-1]]=o if isinstance(o,str) else json.dumps(o)
                fl('',d)
                flat['__keys__']=','.join(d.keys())
                yield flat
    elif path.endswith('.log'):
        with open(path,encoding='utf-8',errors='replace') as f:
            fields=None
            for line in f:
                line=line.rstrip('\n')
                if line.startswith('#fields'): fields=line.split('\t')[1:]; continue
                if line.startswith('#'): continue
                yield dict(zip(fields,line.split('\t')))
    else:
        with open(path,encoding='utf-8',errors='replace',newline='') as f:
            for r in csv.DictReader(f): yield r
def main():
    label=sys.argv[1]; files=[]
    for g in sys.argv[2:]: files+=sorted(glob.glob(g))
    vc=collections.defaultdict(collections.Counter); sh=collections.defaultdict(collections.Counter)
    shex=collections.defaultdict(dict)
    n=0
    for p in files:
        for r in rows(p):
            n+=1
            for k,v in r.items():
                if v is None: v=''
                if k is None: k='__extra__'; v=str(v)
                c=vc[k]
                if len(c)<5000 or v in c: c[v]+=1
                else: c['__OVERFLOW__']+=1
                s=shape(v)
                cs=sh[k]
                if len(cs)<5000 or s in cs:
                    cs[s]+=1
                    if s not in shex[k]: shex[k][s]=v
    out={'n':n,'files':len(files),'cols':{}}
    print(f'### {label}: {n} rows, {len(files)} files')
    for k in vc:
        c=vc[k]; cs=sh[k]
        nd=len(c); over=c.get('__OVERFLOW__',0)
        info={'distinct':nd,'overflow':over}
        if nd<=60 and not over:
            rare=[(v,x) for v,x in c.most_common() if x<RARE]
            print(f'-- {k}: {nd} distinct; top: {c.most_common(4)}')
            if rare and nd<=400: print(f'   RARE(<{RARE}) [{len(rare)}]: {rare[:10]}')
        else:
            rs=[(s,x,shex[k][s]) for s,x in cs.most_common() if x<RARE]
            info['nshapes']=len(cs)
            print(f'-- {k}: {nd}{"+" if over else ""} distinct, {len(cs)} shapes; top shapes: {cs.most_common(4)}')
            if rs and len(cs)<=300: print(f'   RARE SHAPES [{len(rs)}]: {rs[:8]}')
            elif rs: print(f'   RARE SHAPES count={len(rs)} (too many to list); sample {rs[:8]}')
        info['values']=dict(c.most_common()) if nd<=400 and not over else None
        info['shapes']={s:[x,shex[k][s]] for s,x in cs.most_common(400)}
        out['cols'][k]=info
    json.dump(out,open(f'cache/{label}.json','w'))
main()
