from common import *
import pickle, collections, math, sys
sys.path.insert(0,ROOT+'/scripts')
import geo
G=geo.Geo()
fl=pickle.load(open('/tmp/flights.pkl','rb'))
log={r['flight_id']:r for r in rows('drone_video/logs/flight_log.csv')}
laanc=load('drone_detections/laanc_authorizations.csv')
print('laanc cols',list(laanc[0].keys()),len(laanc))
la={r['authorization_id']:r for r in laanc}
# launch on land
water=[(k,d['p0']) for k,d in fl.items() if not G.is_land(*d['p0'])]
print('launch not on land:',len(water),water[:8])
# landing point on land & near launch
far=[(k,round(geo.dist_m(d['p0'],d['last']))) for k,d in fl.items() if geo.dist_m(d['p0'],d['last'])>200]
print('landing >200 m from launch:',len(far),far[:8])
lw=[(k,d['last']) for k,d in fl.items() if not G.is_land(*d['last'])]
print('landing in water',len(lw),lw[:5])
# model envelopes
bym=collections.defaultdict(list)
for k,d in fl.items(): bym[d['model']].append(d)
for m,v in bym.items():
    print(m,'n',len(v),'maxalt',round(max(d['maxalt'] for d in v)),'median maxalt',sorted(d['maxalt'] for d in v)[len(v)//2],'maxv m/s',round(max(d['maxv'] for d in v),1),'max vz',round(max(d['maxvz'] for d in v),1),'max dur min',round(max(d['n'] for d in v)/60),'max range km',round(max(d['maxd'] for d in v)/1000,1),'max track km',round(max(d['km'] for d in v),1),'gaps',sum(d['gaps'] for d in v),'minalt',min(d['minalt'] for d in v))
# compare with log
mm=collections.Counter()
for k,d in fl.items():
    L=log[k]
    if L['takeoff_utc']!=d['t0']: mm['takeoff']+=1
    if abs(int(L['duration_s'])-(d['n']-1))>2: mm['duration']+=1
    if abs(float(L['track_km'])-d['km'])>max(0.3,0.05*d['km']): mm['km']+=1; ex=(k,L['track_km'],round(d['km'],1))
    if abs(float(L['max_alt_m_agl'])-d['maxalt'])>3: mm['alt']+=1
    if geo.dist_m((float(L['launch_latitude']),float(L['launch_longitude'])),d['p0'])>30: mm['launch']+=1
    if L['operator_id']!=d['op']: mm['op']+=1
    if L['authorization_id'] not in la: mm['auth_missing']+=1
print('log vs telemetry mismatches',dict(mm), ex if mm['km'] else '')
print('auth prefixes',collections.Counter(L['authorization_id'].split('-')[0] for L in log.values()))
print('laanc rows not in flight log',len(set(la)-{L['authorization_id'] for L in log.values()}))
print(laanc[0]); 
# night flights (local hour <6 or >=20)
night=[(k,d['t0'],d['mission']) for k,d in fl.items() if local(ts(d['t0'])).hour<6 or local(ts(d['t0'])).hour>=20]
print('night launches',len(night),night[:12])
print('launch local hour hist',sorted(collections.Counter(local(ts(d['t0'])).hour for d in fl.values()).items()))
print('launch second==00',sum(d['t0'][-3:-1]=='00' for d in fl.values()),'minute%5==0',sum(int(d['t0'][14:16])%5==0 for d in fl.values()))
# FEMA grid totals D+3
g=[d for k,d in fl.items() if d['mission'].startswith('FEMA-UAV-0917-GRID')]
print('GRID D+3 flights',len(g),'total km',round(sum(d['km'] for d in g)),[ (d['t0'],round(d['km'])) for d in g])
u=[(k,d['mission'],d['t0'],d['lastt'],d['p0']) for k,d in fl.items() if d['mission'].startswith('FEMA-UAV-0922')]
for x in u: print(x)
pickle.dump(G.is_land, open('/dev/null','wb')) if False else None
