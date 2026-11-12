from common import *
import pickle, collections, glob, sys
sys.path.insert(0,ROOT+'/scripts'); import geo
tr=pickle.load(open('/tmp/tracks.pkl','rb')); fl=pickle.load(open('/tmp/flights.pkl','rb'))
log={r['authorization_id']:r for r in rows('drone_video/logs/flight_log.csv')}
sr=load('drone_detections/sighting_reports.csv')
for r in sr:
    if dday(ts(r['time_utc'])-dt.timedelta(hours=12))>10 and 'resolved' not in r['disposition']: print(r['report_id'],r['time_utc'],r['received_by'],r['observer_street'],r['description'],'|',r['disposition'])
print()
for r in sr:
    if 'forwarded' in r['disposition'] or r['report_id'] in('SR-270915-0001','SR-270919-0012'): print(r['report_id'],r['time_utc'],r['observer_latitude'],r['observer_longitude'],r['direction_deg'],r['objects_seen'],r['duration_min'],r['description'][:90])
# uas tracks vs flights
bad=collections.Counter(); 
for k,d in tr.items():
    if 'uas' not in d['cls']: continue
    L=log.get(d['auth'])
    if not L: bad['auth not in flight log']+=1; continue
    f=fl.get(L['flight_id'])
    if not f: bad['no telemetry']+=1; continue
    if not (f['t0']<=d['t0'] and d['t1']<=f['lastt']): bad['time outside flight']+=1
    if d['pts']:
        m=max(min(geo.dist_m(p[1:],q) for q in f['pts']+[f['p0']]) for p in d['pts'][::10])
        if m>600: bad['pos >600m from flight']+=1
    reg=d['rid']
print('uas track vs flights',dict(bad),'n',sum(1 for d in tr.values() if 'uas' in d['cls']))
# which authorized flights within range of an online sensor were NOT detected -> skip
# NAS offline intervals
iv=collections.defaultdict(list)
for f in sorted(glob.glob(SRC+'/drone_detections/sensor_status_*.csv')):
    for r in rows(f):
        if r['sensor_id'].startswith(('NASCC','USCG')):
            L=iv[r['sensor_id']]
            if L and L[-1][0]==r['status'] and L[-1][3]==r['note']: L[-1][2]=r['time_utc']
            else: L.append([r['status'],r['time_utc'],r['time_utc'],r['note']])
for s,L in iv.items():
    print(s,[x for x in L if x[0]!='online' and (x[1]>'2027-09-10' and x[1]<'2027-10-01')], 'first row',L[0][1],'last',L[-1][2])
# ADS-B for CAMCC04 at ESM time
import csv
reg=json.load(open(ROOT+'/06_data_streams/aircraft_registry.json'))
s=json.dumps(reg); i=s.find('CAMCC'); print(s[max(0,i-400):i+300])
