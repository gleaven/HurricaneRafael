#!/usr/bin/env python3
"""JSONL profiler grouped by a discriminator key. Usage: profj.py <label> <groupkey> <glob...>"""
import sys,json,re,glob,collections,pickle
RARE=30
def shape(s):
    s=re.sub(r'[A-Z]+','A',s); s=re.sub(r'[a-z]+','a',s); s=re.sub(r'[0-9]+','9',s); return s
SKIP={'time_utc','record_id','pid','ppid','src_port','logon_id','sha256','parent_pid','bytes','size','size_bytes'}
def main():
    label,gk=sys.argv[1],sys.argv[2]; files=[]
    for g in sys.argv[3:]: files+=sorted(glob.glob(g))
    G=collections.defaultdict(lambda: {'n':0,'keys':collections.Counter(),'vc':collections.defaultdict(collections.Counter),'sh':collections.defaultdict(collections.Counter),'ex':collections.defaultdict(dict),'frac':collections.Counter()})
    for p in files:
        for line in open(p,encoding='utf-8',errors='replace'):
            if not line.strip(): continue
            d=json.loads(line); g=G[str(d.get(gk))]; g['n']+=1
            g['keys'][','.join(d.keys())]+=1
            t=d.get('time_utc','')
            g['frac'][t[19:] if len(t)>20 else 'nofrac']+=0  # placeholder
            if t.endswith('.000Z'): g['frac']['ms000']+=1
            for k,v in d.items():
                if k in SKIP or k==gk: continue
                v=v if isinstance(v,str) else json.dumps(v)
                c=g['vc'][k]
                if len(c)<3000 or v in c: c[v]+=1
                else: c['__OVER__']+=1
                s=shape(v); cs=g['sh'][k]
                if len(cs)<3000 or s in cs:
                    cs[s]+=1
                    if s not in g['ex'][k]: g['ex'][k][s]=v
    out={}
    for gname,g in sorted(G.items(),key=lambda x:-x[1]['n']):
        print(f'## {gk}={gname} n={g["n"]} ms000={g["frac"]["ms000"]} (exp {g["n"]/1000:.1f}) keysigs={len(g["keys"])}')
        if len(g['keys'])>1:
            ks=g['keys'].most_common()
            print('   KEYSIGS:',[(k[-70:],n) for k,n in ks[:6]])
        for k,c in g['vc'].items():
            over=c.get('__OVER__',0); nd=len(c)
            if nd<=80 and not over:
                rare=[(v,x) for v,x in c.most_common() if x<RARE]
                if rare and g['n']>=RARE: print(f'   {k}: {nd} distinct; RARE {len(rare)}: {rare[:12]}')
            else:
                cs=g['sh'][k]; rs=[(s,x,g['ex'][k][s]) for s,x in cs.most_common() if x<RARE]
                if rs and len(cs)<=400: print(f'   {k}: {nd}{"+" if over else ""} distinct, {len(cs)} shapes; RARE SHAPES {len(rs)}: {rs[:12]}')
                elif rs: print(f'   {k}: {len(cs)} shapes, {len(rs)} rare (too many)')
        out[gname]={'n':g['n'],'keys':dict(g['keys']),'vc':{k:dict(c.most_common(3000)) for k,c in g['vc'].items()},'sh':{k:{s:[x,g['ex'][k][s]] for s,x in cs.most_common(600)} for k,cs in g['sh'].items()}}
    pickle.dump(out,open(f'cache/{label}.pkl','wb'))
main()
