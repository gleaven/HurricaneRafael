from common import *
import json, re, collections, bisect, email.utils
om=collections.defaultdict(int); feeders=collections.defaultdict(dict)
for r in rows('telemetry/outage_map.csv'):
    om[r['timestamp_utc']]+=int(r['customers_out']); feeders[r['feeder_id']][r['timestamp_utc']]=int(r['customers_out'])
T=sorted(om); Tt=[ts(t) for t in T]
print('map span',T[0],T[-1],'steps',len(T),'peak',max(om.values()),max(om,key=om.get))
bad=n=0; ex=[]
for line in open(SRC+'/social_media/TXOutageCount.jsonl'):
    j=json.loads(line); m=re.search(r'([\d,]+) customers without power',j['full_text'])
    if not m: continue
    t=email.utils.parsedate_to_datetime(j['created_at'].replace('+0000','+0000'))
    t=dt.datetime.strptime(j['created_at'],'%a %b %d %H:%M:%S %z %Y')
    i=bisect.bisect_right(Tt,t)-1
    if i<0 or t>Tt[-1]+dt.timedelta(hours=1): continue
    v=int(m.group(1).replace(',','')); mv=om[T[i]]; n+=1
    if abs(v-mv)>max(0.02*mv,50): bad+=1; ex.append((str(t),v,mv))
print('bot posts in span',n,'differ >2%',bad, ex[:6])
# restoration regularity
tot=[om[t] for t in T]
import numpy as np
d=np.diff(tot); 
i0=T.index('2027-09-15T00:00:00Z'); i1=T.index('2027-09-21T00:00:00Z')
seg=d[i0:i1]; print('15-21 Sep step diffs: distinct',len(set(seg)),'min',seg.min(),'max',seg.max(),'zero steps',(seg==0).sum(),'of',len(seg))
print(collections.Counter(seg.tolist()).most_common(8))
# by hour of day restoration
byh=collections.defaultdict(int)
for k in range(i0,i1): byh[local(Tt[k]).hour]+= -d[k]
print('restored by local hour',[byh[h] for h in range(24)])
i2=T.index('2027-09-28T00:00:00Z'); i3=T.index('2027-10-12T11:45:00Z')
print('28Sep-12Oct distinct totals',sorted(set(tot[i2:i3]))[:10],len(set(tot[i2:i3])))
# coastal vs inland at D0+36h
t36='2027-09-15T18:00:00Z'
area=collections.defaultdict(lambda:[0,0])
for r in rows('telemetry/outage_map.csv'):
    if r['timestamp_utc']==t36: area[r['area_id']][0]+=int(r['customers_out']); area[r['area_id']][1]+=int(r['customers_served'])
print({a:(v[0],v[1],round(v[0]/v[1],2)) for a,v in area.items()})
for t in ['2027-09-14T07:00:00Z','2027-09-14T07:15:00Z','2027-09-14T10:00:00Z','2027-09-21T14:15:00Z','2027-09-21T14:30:00Z','2027-09-24T19:30:00Z','2027-09-24T19:45:00Z','2027-10-12T12:00:00Z','2027-10-19T19:45:00Z','2027-10-19T20:00:00Z']: print(t,om[t])
