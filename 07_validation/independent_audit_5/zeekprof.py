import glob,collections,re,pickle,sys
Z='../../05_other_sources/network_logs/zeek/'
def shape(s):
    s=re.sub(r'[A-Z]+','A',s); s=re.sub(r'[a-z]+','a',s); s=re.sub(r'[0-9]+','9',s); return s
def rows(name):
    for d in sorted(glob.glob(Z+'*/'+name+'.log')):
        fields=None
        for line in open(d,encoding='utf-8',errors='replace'):
            line=line.rstrip('\n')
            if line.startswith('#fields'): fields=line.split('\t')[1:]; continue
            if line.startswith('#'): continue
            yield dict(zip(fields,line.split('\t')))
name=sys.argv[1]; cat=sys.argv[2].split(','); shp=sys.argv[3].split(',') if len(sys.argv)>3 and sys.argv[3] else []
vc=collections.defaultdict(collections.Counter); sh=collections.defaultdict(collections.Counter); ex=collections.defaultdict(dict); n=0; frac0=0
for r in rows(name):
    n+=1
    if r['ts'].endswith('.000000'): frac0+=1
    for k in cat: vc[k][r.get(k,'')]+=1
    for k in shp:
        v=r.get(k,''); s=shape(v); sh[k][s]+=1
        if s not in ex[k]: ex[k][s]=v
print('##',name,n,'ts whole-second',frac0)
for k in cat:
    c=vc[k]; rare=[(v,x) for v,x in c.most_common() if x<30]
    print('--',k,len(c),'top',c.most_common(5)); 
    if rare: print('   RARE',len(rare),rare[:25])
for k in shp:
    c=sh[k]; rare=[(s,x,ex[k][s]) for s,x in c.most_common() if x<30]
    print('--',k,len(c),'shapes; top',c.most_common(4))
    if rare: print('   RARE SHAPES',len(rare),rare[:25])
pickle.dump({'vc':{k:dict(v) for k,v in vc.items()},'sh':{k:{s:[x,ex[k][s]] for s,x in v.items()} for k,v in sh.items()}},open('cache/zeek_'+name+'.pkl','wb'))
