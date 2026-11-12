from common import *
import pickle, collections, glob, sys
sys.path.insert(0,ROOT+'/scripts'); import geo
G=geo.Geo()
tr=pickle.load(open('/tmp/tracks.pkl','rb'))
for k in [('USCG-RDR-R22','R22-270906-00001'),('USCG-RDR-R22','R22-270906-00002'),('ESM-CAMCC04','CAMCC04-270905-00976')]:
    d=tr[k]; print(k,d['t0'],d['t1'],d['n'],dict(d['cls']),d['pts'][:1],d['pts'][-1:],d['alts'][:2],d['rcs'][:2],d['rng'][:2],d['brg'][:2],d['rf'],d['rfmhz'])
sr=load('drone_detections/sighting_reports.csv')
print('sightings',len(sr))
byn=collections.Counter(); 
for r in sr:
    t=ts(r['time_utc']); nd=dday(t-dt.timedelta(hours=12))  # night starting on local day nd
    byn[(nd,r['disposition'][:40])]+=1
for k,v in sorted(byn.items()): print('  night D',k[0],k[1],v)
print(cnt(sr,'received_by')); print(cnt(sr,'reporter_type'))
NAS=(27.6926,-97.2911)
for r in sr:
    p=(float(r['observer_latitude']),float(r['observer_longitude']))
    if not G.is_land(*p): print('observer in water',r['report_id'],p)
unres=[r for r in sr if 'matched' not in r['disposition']]
print('unresolved',len(unres),'obs dist to NAS km',sorted(round(geo.dist_m(NAS,(float(r['observer_latitude']),float(r['observer_longitude'])))/1000,1) for r in unres))
print('unresolved local hours',sorted(local(ts(r['time_utc'])).hour for r in unres))
print('ids',[r['report_id'] for r in sr][:30])
print('desc dup',cnt(sr,'description').most_common(5))
res=[r for r in sr if 'matched' in r['disposition']]
print('resolved days',sorted(dday(ts(r['time_utc'])) for r in res))
print(res[0])
# sensor status
st=collections.defaultdict(collections.Counter); notes=collections.Counter(); first={}; 
for f in sorted(glob.glob(SRC+'/drone_detections/sensor_status_*.csv')):
    for r in rows(f):
        st[r['sensor_id']][(r['status'])]+=1; notes[(r['sensor_id'][:6],r['status'],r['note'])]+=1
        first.setdefault((r['sensor_id'],r['status']),[r['time_utc'],r['time_utc']])[1]=r['time_utc']
for s,c in st.items(): print(s,dict(c))
for k,v in sorted(first.items()): 
    if k[1]!='online': print('  ',k,v)
for k,v in notes.most_common(25): print('  note',k,v)
