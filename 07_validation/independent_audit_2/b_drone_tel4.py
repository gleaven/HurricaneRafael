from common import *
import pickle, collections, math, sys
sys.path.insert(0,ROOT+'/scripts')
import geo
fl=pickle.load(open('/tmp/flights.pkl','rb'))
log={r['flight_id']:r for r in rows('drone_video/logs/flight_log.csv')}
la={r['authorization_id']:r for r in rows('drone_detections/laanc_authorizations.csv')}
print(log['CBAS-TIR-0925'])
bad=collections.Counter(); ex={}
for k,d in fl.items():
    L=log[k]; A=la[L['authorization_id']]
    if not (A['start_utc']<=d['t0'] and d['lastt']<=A['end_utc']): bad['window']+=1; ex['window']=(k,A['start_utc'],A['end_utc'],d['t0'],d['lastt'])
    if A['operator_id']!=d['op']: bad['op']+=1
    c=(float(A['center_latitude']),float(A['center_longitude']))
    far=max(geo.dist_m(c,p) for p in d['pts']+[d['p0']])
    if far>float(A['radius_m'])*1.05: bad['outside radius']+=1; ex['rad']=(k,round(far),A['radius_m'])
    if d['maxalt']/0.3048>float(A['max_altitude_ft_agl'])+5: bad['alt']+=1; ex['alt']=(k,round(d['maxalt']/0.3048),A['max_altitude_ft_agl'])
    if A['issued_utc']>A['start_utc']: bad['issued after start']+=1
    dl=geo.dist_m((float(L['launch_latitude']),float(L['launch_longitude'])),d['p0'])
    if dl>30: bad['launch>30m']+=1; ex['launch']=(k,round(dl))
print(dict(bad)); print(ex)
print('auth type by op in D+1..D+10',collections.Counter((d['op'],la[log[k]['authorization_id']]['authorization_type']) for k,d in fl.items() if 1<=dday(ts(d['t0']))<=10))
print('auth status',collections.Counter(a['status'] for a in la.values()))
print('issue lead hours quantiles',[round(x,1) for x in sorted((ts(a['start_utc'])-ts(a['issued_utc'])).total_seconds()/3600 for a in la.values())[::40]])
# airfields: NAS CC (27.6926,-97.2911), CRP (27.7704,-97.5012)
NAS=(27.6926,-97.2911); CRP=(27.7704,-97.5012); CCAD=(27.6880,-97.2800)
near=[(k,d['mission'],d['t0'],round(min(geo.dist_m(NAS,p) for p in d['pts']+[d['p0']]))) for k,d in fl.items() if min(geo.dist_m(NAS,p) for p in d['pts']+[d['p0']])<3000]
print('flights within 3 km of NAS CC ARP:',len(near)); [print('  ',x) for x in near[:25]]
nearc=[(k,d['mission'],d['t0'],round(min(geo.dist_m(CRP,p) for p in d['pts']+[d['p0']]))) for k,d in fl.items() if min(geo.dist_m(CRP,p) for p in d['pts']+[d['p0']])<2500]
print('flights within 2.5 km of CRP ARP:',len(nearc), nearc[:10])
# altitude regularity
import statistics
for m in ['DJI Matrice 30T','DJI Mavic 3 Thermal','Argus Mk-7 fixed-wing survey aircraft']:
    print(m,collections.Counter(round(d['maxalt'],1) for d in fl.values() if d['model']==m).most_common(5))
# duration regularity
print('durations s sample',sorted(d['n'] for d in fl.values())[::30])
# media under TFR
for k,d in sorted(fl.items(),key=lambda x:x[1]['t0']):
    if d['op'] in('DRN-OP-004','DRN-OP-007','DRN-OP-014') and 1<=dday(ts(d['t0']))<=7: print(k,d['t0'],d['mission'],la[log[k]['authorization_id']]['authorization_type'],log[k]['authorization_id'])
