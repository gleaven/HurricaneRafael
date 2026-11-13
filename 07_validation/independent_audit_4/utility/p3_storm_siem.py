#!/usr/bin/env python3
"""Item 14 + canon SIEM numbers: daily/hourly SIEM counts around the storm, daily_summary agreement, people-driven alerts, analysts' shifts, closure plausibility."""
import sys,collections,csv,statistics,datetime; sys.path.insert(0,sys.path[0])
from lib import *
h,S=fam('siem'); ix={n:i for i,n in enumerate(h)}
g=lambda r,c:r[ix[c]]
day=collections.Counter(g(r,'time_utc')[:10] for r in S)
canon={'2027-09-12':4812,'2027-09-13':7341,'2027-09-14':18340,'2027-09-15':16207,'2027-09-16':14884,'2027-09-17':12201,'2027-09-18':6633,'2027-10-19':2312}
print('canon daily counts ok:',all(day[k]==v for k,v in canon.items()),{k:day[k] for k in canon},'sum D-2..D+3',sum(day[k] for k in list(canon)[:6]))
ds=list(csv.DictReader(open('siem/daily_summary.csv')))
bad=[(d['date_utc'],d['alerts'],day[d['date_utc']]) for d in ds if int(d['alerts'])!=day[d['date_utc']]]
fp=collections.Counter(g(r,'time_utc')[:10] for r in S if g(r,'disposition')=='FALSE_POSITIVE')
badfp=[(d['date_utc'],d['closed_false_positive'],fp[d['date_utc']]) for d in ds if int(d['closed_false_positive'])!=fp[d['date_utc']]]
print('daily_summary rows',len(ds),'alert count mismatches',len(bad),bad[:3],'FP mismatches',len(badfp),badfp[:3])
d1019=[d for d in ds if d['date_utc']=='2027-10-19'][0]; print('  10-19',d1019)
mlopen=[(d['date_utc'],d['open_ml_anomaly_alerts']) for d in ds if d['open_ml_anomaly_alerts']!='0']; print('  days with open ML anomaly',mlopen[:10],len(mlopen))
base=[day[k] for k in sorted(day) if '2027-07-20'<=k<='2027-09-10']; print('baseline median/day',statistics.median(base),'weekday/weekend',statistics.median([day[k] for k in day if '2027-07-20'<=k<='2027-09-10' and datetime.date.fromisoformat(k).weekday()<5]),statistics.median([day[k] for k in day if '2027-07-20'<=k<='2027-09-10' and datetime.date.fromisoformat(k).weekday()>=5]))
hr=collections.Counter(g(r,'time_utc')[:13] for r in S)
for d in ('2027-09-11','2027-09-12','2027-09-13','2027-09-14','2027-09-15','2027-09-18','2027-10-12'):
    print('  hourly',d,[hr[f'{d}T{x:02d}'] for x in range(24)])
for rule in ('SE3-OT-6004','SE3-POL-5003','SE3-AUTH-1012','SE3-EP-2003','SE3-EP-2017','SE3-POL-5011','SE3-EP-2010','SE3-NET-3020','SE3-MAIL-4002'):
    c=collections.Counter(g(r,'time_utc')[:10] for r in S if g(r,'rule_id')==rule)
    print('  ',rule,g([r for r in S if g(r,'rule_id')==rule][0],'rule_name'),'09-07..09-20:',[c[f'2027-09-{x:02d}'] for x in range(7,21)])
# alert volume after 08:00Z 10-12
a=sum(1 for r in S if '2027-10-12T00'<=g(r,'time_utc')<'2027-10-12T08'); b=sum(1 for r in S if '2027-10-12T08'<=g(r,'time_utc')<'2027-10-12T16')
print('10-12 alerts 00-08Z',a,'08-16Z',b,'| 10-11 total',day['2027-10-11'],'10-12',day['2027-10-12'],'10-13',day['2027-10-13'],'10-14',day['2027-10-14'],'10-20',day['2027-10-20'])
# analysts
an=collections.defaultdict(lambda: collections.Counter()); days=collections.defaultdict(set)
for r in S:
    cb=g(r,'closed_by')
    if cb and cb!='system' and g(r,'closed_utc'):
        an[cb][int(g(r,'closed_utc')[11:13])]+=1; days[cb].add(g(r,'closed_utc')[:10])
for k,v in an.items(): print('  analyst',k,'days active',len(days[k]),'hours-of-day used',len(v),'by hour',[v[x] for x in range(24)])
# time to close
ttc=[E(g(r,'closed_utc'))-E(g(r,'time_utc')) for r in S if g(r,'closed_utc') and g(r,'closed_by') not in('system','')]
print('time to close (analyst): negative',sum(x<0 for x in ttc),'median h',round(statistics.median(ttc)/3600,2),'max d',round(max(ttc)/86400,1))
print('closed with no closer / open with close time',sum(1 for r in S if g(r,'closed_utc') and not g(r,'closed_by')),sum(1 for r in S if g(r,'disposition')=='OPEN' and g(r,'closed_utc')))
# close_note vs rule plausibility
cn=collections.Counter((g(r,'rule_name'),g(r,'close_note')) for r in S if g(r,'closed_by') not in('system',''))
odd=[(k,v) for k,v in cn.items() if (k[1] in('Storm damage','Storm preparation') )]
sd=collections.Counter(g(r,'time_utc')[:7] for r in S if g(r,'close_note')=='Storm damage'); print('"Storm damage" notes by month',sorted(sd.items()))
print('note x rule sample',sorted(cn.items(),key=lambda x:-x[1])[:14])
print('notes used for ML session anomaly',collections.Counter(g(r,'close_note') for r in S if g(r,'rule_id')=='SE3-ML-0044').most_common(8))
ids=collections.Counter(g(r,'alert_id') for r in S); print('duplicate alert ids',sum(1 for v in ids.values() if v>1))
reg_=reg(); print('analyst ids',[(u['username'],u.get('analyst_id')) for u in reg_['users'] if u.get('analyst_id')])
for aid in ('SE3-NET-9941-20270831T0317Z','SE3-OT-2201-20270911T2211Z','SE3-OT-1104-20270907T0244Z','SE3-OT-1104-20270914T0831Z','SE3-NET-9941-20270915T0117Z','SE3-OT-3301-20270915T0944Z','SE3-ML-0044-20271002T1433Z'):
    x=[r for r in S if g(r,'alert_id')==aid]; print('  ',aid,[(g(r,'time_utc'),g(r,'priority'),g(r,'src_host'),g(r,'dst_ip'),g(r,'detail')[:90],g(r,'disposition'),g(r,'closed_utc'),g(r,'closed_by'),g(r,'close_note')) for r in x])
