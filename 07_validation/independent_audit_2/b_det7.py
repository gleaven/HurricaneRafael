from common import *
import glob, collections, math
rs=[]
for f in sorted(glob.glob(SRC+'/drone_detections/detections_*.csv')): rs+=load(f)
print(len(rs))
print('alert by class',collections.Counter((r['classification'],r['alert']) for r in rs).most_common(30))
ue=[r for r in rs if r['classification']=='unknown emitter']
print('unknown emitter by sensor',cnt(ue,'sensor_id'),'first',min(r['time_utc'] for r in ue),'sig',cnt(ue,'rf_signature'))
print('unknown emitter per month',collections.Counter(r['time_utc'][:7] for r in ue))
# track id numbering: per sensor, seq number vs time order
seq=collections.defaultdict(dict)
for r in rs:
    k=(r['sensor_id'],r['track_id'])
    if k not in seq[r['sensor_id']]: seq[r['sensor_id']][r['track_id']]=r['time_utc']
for s,d in seq.items():
    nums=sorted((int(t.split('-')[-1]),t,tm) for t,tm in d.items())
    low=[x for x in nums if x[0]<50]
    print(s,'n',len(nums),'min seq',nums[0][:3],'seq<50:',low[:8], 'max',nums[-1][0])
# hostile rows fields vs others: confidence, rcs decimals etc.
host=[r for r in rs if r['track_id'] in('R18-270906-00001','R22-270906-00001','R22-270906-00002','R22-270909-00003','R22-270911-00004')]
print('hostile radar rows',len(host),'classification',cnt(host,'classification'),'alert',cnt(host,'alert'),'conf range',min(float(r['confidence']) for r in host),max(float(r['confidence']) for r in host))
unk=[r for r in rs if r['classification']=='unknown' and r not in host and r['detection_type']=='radar_plot']
import statistics
print('other unknown conf',min(float(r['confidence']) for r in unk),max(float(r['confidence']) for r in unk),'alt>120',sum(float(r['altitude_m'])>120 for r in unk),len(unk))
print('host alt',statistics.mean(float(r['altitude_m']) for r in host),'night-hour unknown tracks (local 22-04) n tracks',len({r['track_id'] for r in unk if local(ts(r['time_utc'])).hour in(22,23,0,1,2,3)}))
# dt between plots hostile vs others
def dts(sel):
    by=collections.defaultdict(list)
    for r in sel: by[(r['sensor_id'],r['track_id'])].append(ts(r['time_utc']))
    c=collections.Counter()
    for v in by.values():
        v.sort()
        for a,b in zip(v,v[1:]): c[int((b-a).total_seconds())]+=1
    return c.most_common(6)
print('dt host',dts(host)); print('dt unk',dts(unk[:20000]))
# last detection day of anything non-authorised uas-like at NAS after D+11
ps5=[r for r in rs if r['sensor_id']=='NASCC-PS-05']; print(ps5)
# sightings geometry
sr=load('drone_detections/sighting_reports.csv')
NAS=(27.6926,-97.2850)
def brg(a,b):
    dy=(b[0]-a[0])*110950; dx=(b[1]-a[1])*111320*math.cos(math.radians(27.7)); return (math.degrees(math.atan2(dx,dy))+360)%360
bad=0;n=0
for r in sr:
    if 'logged' in r['disposition']:
        o=(float(r['observer_latitude']),float(r['observer_longitude'])); b=brg(o,NAS); d=abs((b-float(r['direction_deg'])+180)%360-180); n+=1
        if d>60: bad+=1; print('  bearing off',r['report_id'],r['time_utc'],round(b),r['direction_deg'],r['observer_street'])
print('hostile-night reports',n,'bearing >60 deg off NAS',bad)
print('pre-storm reports',sum(r['time_utc']<'2027-09-14' for r in sr))
ids=sorted((int(r['report_id'].split('-')[-1]),r['disposition'][:20]) for r in sr)
print(ids)
print(collections.Counter((r['received_by'],r['disposition'][:25]) for r in sr))
