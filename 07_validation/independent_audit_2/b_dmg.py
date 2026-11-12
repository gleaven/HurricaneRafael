from common import *
import collections, sys, statistics, re
sys.path.insert(0,ROOT+'/scripts'); import geo
G=geo.Geo()
rs=load('infrastructure/damage_assessment.csv')
by=collections.defaultdict(list)
for r in rs: by[r['structure_id']].append(r)
print('structures',len(by),'rows per structure',collections.Counter(len(v) for v in by.values()))
print('type x level'); 
for t in ('AI','RS','FV','HI'):
    v=[r for r in rs if r['ASMT_TYPE']==t]; print(' ',t,len(v),dict(cnt(v,'DMG_LEVEL')),'dates',min(r['ASMT_DATE'] for r in v),max(r['ASMT_DATE'] for r in v))
    print('     by day',sorted(collections.Counter(r['ASMT_DATE'][:10] for r in v).items())[:8],'...', 'hours',sorted(collections.Counter(int(r['ASMT_DATE'][11:13]) for r in v).items()))
# land + road
S=list(by.values())
nl=[v[0]['structure_id'] for v in S if not G.is_land(float(v[0]['LATITUDE']),float(v[0]['LONGITUDE']))]
print('structures not on land',len(nl),nl[:5])
import random; random.seed(1); samp=random.sample(S,1500)
rd=[];nm=0;ex=[]
for v in samp:
    r=v[0]; nn=G.roads.nearest(float(r["LATITUDE"]),float(r["LONGITUDE"])); d=nn[0]; name=str(nn[-1]); rd.append(d)
    st=re.sub(r'^\d+\s+','',r['address'].split(',')[0]).upper()
    if name and st.split()[0] not in name.upper() and name.upper().split()[0] not in st: nm+=1; ex.append((r['address'],name,round(d)))
rd.sort(); print('road distance m: median',round(rd[750]),'p95',round(rd[1425]),'max',round(rd[-1]),'| street name != nearest road',nm,'of 1500',ex[:6])
# coords constant per structure?
print('structures with varying coords',sum(1 for v in S if len({(r['LATITUDE'],r['LONGITUDE']) for r in v})>1),'varying address',sum(1 for v in S if len({r['address'] for r in v})>1),'varying year/sqft',sum(1 for v in S if len({(r['YEAR_BUILT'],r['SQ_FT'],r['FOUNDATION'],r['OCCUPANCY']) for r in v})>1))
# duplicates of address across structures
ad=collections.Counter(v[0]['address'] for v in S); print('addresses shared by >1 structure',sum(1 for a,c in ad.items() if c>1),ad.most_common(3))
co=collections.Counter((v[0]['LATITUDE'],v[0]['LONGITUDE']) for v in S); print('coords shared by >1 structure',sum(1 for a,c in co.items() if c>1),co.most_common(2))
# damage vs flood depth and roof
lv={'NVD':0,'AFF':1,'MIN':2,'MAJ':3,'DST':4}
for t in ('AI','FV'):
    print(t,'mean flood depth / roof pct by level',{l:(round(statistics.mean(float(r['FLOOD_DEPTH_FT']) for r in rs if r['ASMT_TYPE']==t and r['DMG_LEVEL']==l),1),round(statistics.mean(float(r['ROOF_DAMAGE_PCT']) for r in rs if r['ASMT_TYPE']==t and r['DMG_LEVEL']==l))) for l in lv})
odd=[r for r in rs if float(r['FLOOD_DEPTH_FT'])>=5 and r['DMG_LEVEL'] in('NVD','AFF','MIN') and r['FOUNDATION']!='Elevated']
print('flood>=5 ft, non-elevated, level<=MIN:',len(odd),'of',sum(1 for r in rs if float(r['FLOOD_DEPTH_FT'])>=5 and r['FOUNDATION']!='Elevated'), odd[0] if odd else '')
odd2=[r for r in rs if float(r['FLOOD_DEPTH_FT'])==0 and float(r['ROOF_DAMAGE_PCT'])<10 and r['DMG_LEVEL'] in('MAJ','DST')]
print('no flood, roof<10% but MAJ/DST:',len(odd2))
print('flood depth varies between assessments of same structure',sum(1 for v in S if len({r['FLOOD_DEPTH_FT'] for r in v})>1),'roof varies',sum(1 for v in S if len({r['ROOF_DAMAGE_PCT'] for r in v})>1))
# level changes between AI and field
ch=collections.Counter()
for v in S:
    a=[r for r in v if r['ASMT_TYPE']=='AI']; f=[r for r in v if r['ASMT_TYPE']=='FV']
    if a and f: ch[lv[f[0]['DMG_LEVEL']]-lv[a[0]['DMG_LEVEL']]]+=1
print('FV level minus AI level',sorted(ch.items()))
# by city/zip
for z,c in collections.Counter(v[0]['zip'] for v in S).most_common(20):
    vv=[v for v in S if v[0]['zip']==z]; last=[x[-1] for x in vv]
    print(z,vv[0][0]['city'],c,'MAJ+DST share',round(sum(x['DMG_LEVEL'] in('MAJ','DST') for x in last)/c,2),'mean flood',round(statistics.mean(float(x['FLOOD_DEPTH_FT']) for x in last),1),'mean roof',round(statistics.mean(float(x['ROOF_DAMAGE_PCT']) for x in last)))
print('MH stories 2:',sum(1 for v in S if v[0]['OCCUPANCY']=='RES-MH' and v[0]['STORIES']=='2'),'MH sqft>2000',sum(1 for v in S if v[0]['OCCUPANCY']=='RES-MH' and int(v[0]['SQ_FT'])>2000),'of',sum(1 for v in S if v[0]['OCCUPANCY']=='RES-MH'), 'year>2027',sum(int(v[0]['YEAR_BUILT'])>2027 for v in S))
print('spill-zone access notes zips',collections.Counter(r['zip'] for r in rs if 'spill' in r['ACCESS_NOTE']).most_common(6), 'dates',min(r['ASMT_DATE'] for r in rs if 'spill' in r['ACCESS_NOTE']),max(r['ASMT_DATE'] for r in rs if 'spill' in r['ACCESS_NOTE']))
