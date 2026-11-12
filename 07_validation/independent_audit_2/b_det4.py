from common import *
import pickle, collections, statistics, math, sys
sys.path.insert(0,ROOT+'/scripts'); import geo
G=geo.Geo()
tr=pickle.load(open('/tmp/tracks.pkl','rb'))
sites={r['sensor_id']:r for r in rows('drone_detections/sensor_sites.csv')}
# track id numbering near hostile
for s in ('USCG-RDR-R18','USCG-RDR-R22','ESM-CAMCC04'):
    ids=sorted((d['t0'],k[1]) for k,d in tr.items() if k[0]==s and '2027-09-03'<d['t0']<'2027-09-12')
    print(s,[i[1][-12:] for i in ids][:60])
# geometry of the three hostile tracks
import numpy as np
fac=json.load(open(ROOT+'/06_data_streams/infrastructure_assets.json'))
def find(o,key,out):
    if isinstance(o,dict):
        if any(key in str(v) for v in o.values() if isinstance(v,str)) and ('latitude' in o or 'lat' in o): out.append(o)
        for v in o.values(): find(v,key,out)
    elif isinstance(o,list):
        for v in o: find(v,key,out)
out=[]; find(fac,'GW-FAC-SUB-01',out); print([ (o.get('asset_id') or o.get('id'),o.get('latitude') or o.get('lat'),o.get('longitude') or o.get('lon')) for o in out][:3])
term=json.load(open(ROOT+'/06_data_streams/terminal_registry.json')); out2=[]; find(term,'TERM-01',out2); print([(o.get('terminal_id'),o.get('name'),o.get('latitude'),o.get('longitude')) for o in out2][:3])
for k in [('USCG-RDR-R18','R18-270906-00001'),('USCG-RDR-R22','R22-270909-00003'),('USCG-RDR-R22','R22-270911-00004')]:
    d=tr[k]; s=sites[k[0]]; sp=(float(s['latitude']),float(s['longitude']))
    pts=d['pts']
    err=[]; 
    for (t,la,lo),rg,br in zip(pts,d['rng'],d['brg']):
        dm=geo.dist_m(sp,(la,lo)); b=geo.bearing(sp,(la,lo)); err.append((abs(dm-rg),min(abs(b-br),360-abs(b-br))))
    v=[geo.dist_m(pts[i][1:],pts[i+1][1:])/max(1,(ts(pts[i+1][0])-ts(pts[i][0])).total_seconds()) for i in range(len(pts)-1)]
    dts=collections.Counter(int((ts(pts[i+1][0])-ts(pts[i][0])).total_seconds()) for i in range(len(pts)-1))
    print(k,'range err max',round(max(e[0] for e in err)),'brg err max',round(max(e[1] for e in err),1),'range min/max',min(d['rng']),max(d['rng']),'implied v mean/max',round(statistics.mean(v),1),round(max(v),1),'reported sp mean',round(statistics.mean(d['sp']),1),'dt',dict(dts),'first',pts[0],'last',pts[-1],'alt min/max',min(d['alts']),max(d['alts']))
    print('   bbox',min(p[1] for p in pts),max(p[1] for p in pts),min(p[2] for p in pts),max(p[2] for p in pts),'on land share',round(sum(G.is_land(p[1],p[2]) for p in pts)/len(pts),2))
    if out and k[0].endswith('R18'):
        t=(float(out[0].get('latitude') or out[0].get('lat')),float(out[0].get('longitude') or out[0].get('lon'))); print('   min dist to SUB-01',round(min(geo.dist_m(t,p[1:]) for p in pts)),'sensor->SUB-01 m',round(geo.dist_m(sp,t)),'bearing first pt from SUB-01',round(geo.bearing(t,pts[0][1:])))
    if out2 and k[0].endswith('R22'):
        t=(float(out2[0]['latitude']),float(out2[0]['longitude'])); print('   min dist to TERM-01',round(min(geo.dist_m(t,p[1:]) for p in pts)),'sensor->TERM m',round(geo.dist_m(sp,t)))
# geometry check for all radar tracks: range/bearing vs position; within nominal range
bad=0;n=0;over=0
for k,d in tr.items():
    if d['type']!='radar_plot' or not sites[k[0]]['latitude']: continue
    s=sites[k[0]]; sp=(float(s['latitude']),float(s['longitude']))
    for (t,la,lo),rg in list(zip(d['pts'],d['rng']))[::5]:
        n+=1; dm=geo.dist_m(sp,(la,lo))
        if abs(dm-rg)>25: bad+=1
        if rg>float(s['nominal_range_m'])*1.1: over+=1
print('radar plots sampled',n,'range inconsistent',bad,'beyond nominal range',over)
