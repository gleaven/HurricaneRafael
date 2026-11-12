from common import *
import glob, re, collections, pickle
day=collections.Counter(); nat=collections.defaultdict(collections.Counter); narr=collections.defaultdict(collections.Counter)
allr=[]
for f in sorted(glob.glob(SRC+'/911/cad_incidents_*.csv')):
    for r in rows(f):
        d=(dt.date.fromisoformat(r['call_received_dttm'][:10])-dt.date(2027,9,14)).days
        day[d]+=1; nat[r['nature_code']][d]+=1
        allr.append((d,r['call_received_dttm'],r['nature_code'],r['narrative'],r['sar_priority'],r['latitude'],r['longitude'],r['incident_number'],r['unit_id'],r['disposition_code'],r['callback_number'],r['ali_class_of_service'],r['sar_case_number']))
pickle.dump(allr,open('/tmp/cad2.pkl','wb'))
print('rows',len(allr),'days',min(day),max(day))
print('daily',[(d,day[d]) for d in range(-30,46)])
pat=re.compile(r'STORM|CURFEW|FLOOD|WATER RISING|ROOF|SHELTER|BOAT|SURGE|HURRICANE|EVAC|DEBRIS|BOIL|OUTAGE|POWER OUT|GENERATOR|RAFAEL|LOOT|PRICE GOUG|TARP|FEMA|DRONE|OIL|SPILL|EXPLOS|BLAST',re.I)
pre=collections.Counter(); 
for a in allr:
    if a[0]<=-8:
        m=pat.search(a[3]) 
        if m: pre[(a[2],a[3])]+=1
print('pre-storm (D<=-8) suspicious narratives:',sum(pre.values()))
for k,v in pre.most_common(40): print('  ',v,k)
print('nature codes with first day / counts pre D-8, D-7..-1, D0..D+30, >D+75')
for n,c in sorted(nat.items()):
    print('  ',n,min(c),max(c),sum(v for d,v in c.items() if d<=-8),sum(v for d,v in c.items() if -8<d<0),sum(v for d,v in c.items() if 0<=d<=30),sum(v for d,v in c.items() if d>75))
