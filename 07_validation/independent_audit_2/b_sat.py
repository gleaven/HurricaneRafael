from common import *
import glob, collections, re, math
S=SRC+'/satellite'
items=[]
for f in sorted(glob.glob(S+'/*.json')):
    if f.endswith('catalog.json'): continue
    j=json.load(open(f)); j['_f']=os.path.basename(f); items.append(j)
print(len(items))
bad=collections.Counter()
for j in items:
    p=j['properties']; idt=re.search(r'(\d{8}T\d{6})Z',j['id'])
    if idt:
        d=dt.datetime.strptime(idt.group(1),'%Y%m%dT%H%M%S').replace(tzinfo=dt.timezone.utc)
        if abs((ts(p['datetime'])-d).total_seconds())>1: bad['id time != datetime']+=1
    if j['id']+'.json'!=j['_f']: bad['id != filename']+=1
    b=j['bbox']; cs=j['geometry']['coordinates'][0]
    if not (b[0]<b[2] and b[1]<b[3]): bad['bbox order']+=1
    xs=[c[0] for c in cs]; ys=[c[1] for c in cs]
    if abs(min(xs)-b[0])>1e-6 or abs(max(ys)-b[3])>1e-6: bad['bbox != geometry']+=1
    # sun elevation sanity for EO
    if 'eo:cloud_cover' in p:
        if p.get('view:sun_elevation',0)<20: bad['EO with low sun']+=1
    t=ts(p['datetime']); lh=(t.hour+t.minute/60-6.5)%24  # local solar approx
    se=p.get('view:sun_elevation')
    if se is not None and ((6.5<lh<17.5 and se<0) or ((lh<4.5 or lh>19.5) and se>0)): bad['sun elevation sign vs local time']+=1; print('  sun?',j['id'],se,round(lh,1))
print(dict(bad))
by=collections.defaultdict(list)
for j in items: by[j['id'].split('-')[0]+'-'+j['id'].split('-')[1]].append(j)
for k,v in by.items():
    ts_=[ts(j['properties']['datetime']) for j in v]
    gaps=collections.Counter(round((b-a).total_seconds()/86400,1) for a,b in zip(ts_,ts_[1:]))
    print(k,len(v),str(ts_[0])[:16],str(ts_[-1])[:16],'gaps(days)',gaps.most_common(5),'bbox',v[0]['bbox'],'gsd',collections.Counter(j['properties']['gsd'] for j in v).most_common(3))
# EO cloud cover around storm
for j in items:
    p=j['properties']
    if j['id'].startswith('MERIDIAN') and '2027-09-08'<=p['datetime']<='2027-09-24': print(j['id'],'cloud',p.get('eo:cloud_cover'),'sunel',p.get('view:sun_elevation'),'|',p['description'][:230])
