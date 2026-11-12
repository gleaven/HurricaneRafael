from common import *
import glob, collections, pickle
day=collections.Counter(); fp=collections.Counter(); cols=collections.defaultdict(collections.Counter); rule=collections.defaultdict(collections.Counter)
keep=[]; hosts=collections.Counter(); notes=collections.Counter(); hrs=collections.Counter()
want=('SE3-NET-9941','SE3-OT-1104','SE3-OT-2201','SE3-OT-3301','SE3-ML-0044')
for f in sorted(glob.glob(SRC+'/network_logs/siem/siem_alerts_*.csv')):
    for r in rows(f):
        d=r['time_utc'][:10]; day[d]+=1
        if r['disposition']=='FALSE_POSITIVE': fp[d]+=1
        for c in ('category','priority','disposition','closed_by'): cols[c][r[c]]+=1
        rule[r['rule_id']+' '+r['rule_name']][d[:7]]+=1
        hosts[r['src_host']]+=1; hosts[r['dst_host']]+=1
        notes[(r['rule_name'],r['close_note'])]+=1
        if r['rule_id'] in want or r['priority'] in('HIGH','CRITICAL','ANOMALY_HIGH') : keep.append(r)
        if '2027-10-12'<=d<='2027-10-13': hrs[r['time_utc'][:13]]+=1
pickle.dump((dict(day),dict(fp),keep,dict(hosts)),open('/tmp/siem.pkl','wb'))
ds={r['date_utc']:r for r in rows('network_logs/siem/daily_summary.csv')}
mm=[(d,ds[d]['alerts'],day.get(d,0)) for d in ds if int(ds[d]['alerts'])!=day.get(d,0)]
print('summary vs rows mismatches',len(mm),mm[:8]); 
mf=[(d,ds[d]['closed_false_positive'],fp.get(d,0)) for d in ds if int(ds[d]['closed_false_positive'])!=fp.get(d,0)]
print('fp mismatches',len(mf),mf[:5])
print('days in rows not summary',sorted(set(day)-set(ds))[:5],'span',min(day),max(day))
print('open_ml_anomaly_alerts nonzero days',[(d,r['open_ml_anomaly_alerts']) for d,r in ds.items() if r['open_ml_anomaly_alerts']!='0'])
for c,v in cols.items(): print(c,dict(v.most_common(14)))
print('rules:'); 
for k,v in sorted(rule.items(),key=lambda x:-sum(x[1].values())): print('  ',sum(v.values()),k,dict(sorted(v.items())) if sum(v.values())<400 else '')
print('hourly 10-12/13',sorted(hrs.items())[:30])
print('weekday means (Aug)',{wd:round(sum(day[d] for d in day if d.startswith('2027-08') and dt.date.fromisoformat(d).weekday()==wd)/max(1,sum(1 for d in day if d.startswith('2027-08') and dt.date.fromisoformat(d).weekday()==wd))) for wd in range(7)})
print('close notes for some rules',[ (k,v) for k,v in notes.most_common(400) if k[0] in('ADMIN_GROUP_CHANGE','OT_FILE_WRITE','DEVICE_COMM_LOSS')][:12])
