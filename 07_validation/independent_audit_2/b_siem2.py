from common import *
import pickle, collections
day,fp,keep,hosts=pickle.load(open('/tmp/siem.pkl','rb'))
for r in keep:
    if r['priority'] in('HIGH','ANOMALY_HIGH'): print({k:v for k,v in r.items() if v})
by=collections.defaultdict(list)
for r in keep: by[r['rule_id']].append(r)
for rid,v in by.items():
    print(rid,len(v),'first',v[0]['time_utc'],'last',v[-1]['time_utc'],'disp',dict(collections.Counter(r['disposition'] for r in v)),'src',collections.Counter(r['src_host'] for r in v).most_common(4),'dst',collections.Counter((r['dst_ip'],r['dst_port']) for r in v).most_common(3))
n=by['SE3-NET-9941']
c2=[r for r in n if r['dst_ip']=='104.21.88.43']
print('beacon to 104.21.88.43:',len(c2),'first',c2[0]['time_utc'] if c2 else None,'last',c2[-1]['time_utc'] if c2 else None,'src',collections.Counter(r['src_host'] for r in c2),'disp',collections.Counter(r['disposition'] for r in c2))
if c2:
    print(c2[0]); 
    import statistics
    gaps=[(ts(b['time_utc'])-ts(a['time_utc'])).total_seconds()/3600 for a,b in zip(c2,c2[1:])]
    print('beacon gap hours: median',statistics.median(gaps),'min',min(gaps),'max',max(gaps),'distinct rounded',collections.Counter(round(g) for g in gaps).most_common(5))
    print('detail values',collections.Counter(r['detail'] for r in c2).most_common(3))
    print('other 9941 details',collections.Counter(r['detail'] for r in n if r['dst_ip']!='104.21.88.43').most_common(3))
for aid in ('SE3-NET-9941-20270831T0317Z','SE3-OT-1104-20270907T0244Z','SE3-OT-2201-20270911T2211Z','SE3-OT-3301-20270923T0400Z','SE3-ML-0044-20271002T1433Z','SE3-OT-1104-20270914T0831Z','SE3-NET-9941-20270915T0117Z','SE3-OT-3301-20270915T0944Z'):
    m=[r for r in keep if r['alert_id']==aid]; print(aid,len(m),{k:v for k,v in m[0].items() if v} if m else 'MISSING')
h=[r for r in by['SE3-OT-1104'] if r['src_host']=='GW-SYS-JMP-01']
print('1104 from JMP',len(h),collections.Counter(r['disposition'] for r in h),[r['time_utc'] for r in h][:20])
print('1104 details sample',collections.Counter(r['detail'][:40] for r in by['SE3-OT-1104']).most_common(4))
reg=json.load(open(ROOT+'/06_data_streams/gw_host_registry.json'))
s=json.dumps(reg)
unk=[hh for hh in hosts if hh and hh not in s]; print('SIEM hosts not in registry',len(unk),unk[:10])
