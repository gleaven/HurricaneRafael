from common import *
import pickle, collections, math, sys
sys.path.insert(0,ROOT+'/scripts')
fl=pickle.load(open('/tmp/flights.pkl','rb'))
log={r['flight_id']:r for r in rows('drone_video/logs/flight_log.csv')}
print('telemetry flights',len(fl),'log flights',len(log),'only tel',len(set(fl)-set(log)),'only log',sorted(set(log)-set(fl))[:5])
ops=json.load(open(ROOT+'/06_data_streams/drone_operators.json'))
opids={o['operator_id']:o for o in ops['authorized_operators']}
print('unknown operators',{d['op'] for d in fl.values()}-set(opids))
# by day
byday=collections.Counter(); bydayop=collections.defaultdict(collections.Counter)
for k,d in fl.items():
    dd=dday(ts(d['t0'])); byday[dd]+=1; bydayop[d['op']][dd]+=1
print('flights by D-day',sorted(byday.items()))
for o,c in sorted(bydayop.items()): print(o,opids[o]['org_name'],'|',opids[o].get('org_type'),'| n',sum(c.values()),'days',min(c),max(c))
# TFR window: 2027-09-12T05:01Z until ? flights between TFR and landfall, and during storm
tf=[(k,d['t0'],d['mission']) for k,d in fl.items() if '2027-09-12T05:01'<=d['t0']<'2027-09-15T12:00']
print('flights TFR start..D+1 12Z:',tf)
# mission by day table
mis=collections.defaultdict(list)
for k,d in fl.items(): mis[d['mission'].rstrip('0123456789-')].append(dday(ts(d['t0'])))
for m,v in sorted(mis.items()): print('  ',m,len(v),min(v),max(v))
