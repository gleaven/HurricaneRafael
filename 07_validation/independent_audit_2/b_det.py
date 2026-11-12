from common import *
import glob, collections, pickle, math
tr={}; cols=collections.defaultdict(collections.Counter); n=0
for f in sorted(glob.glob(SRC+'/drone_detections/detections_*.csv')):
    for r in rows(f):
        n+=1
        for c in ('sensor_id','detection_type','classification','alert','rf_signature','remote_id'): cols[c][r[c] if c!='remote_id' else (r[c][:4] if r[c] else '')]+=1
        k=(r['sensor_id'],r['track_id'])
        d=tr.get(k)
        if d is None: d=tr[k]=dict(t0=r['time_utc'],n=0,cls=collections.Counter(),auth=r['authorization_id'],rid=r['remote_id'],alts=[],rcs=[],sp=[],pts=[],alert=False,type=r['detection_type'],rf=r['rf_signature'],rfmhz=r['rf_center_mhz'],rng=[],brg=[],dur=r['duration_s'])
        d['n']+=1; d['t1']=r['time_utc']; d['cls'][r['classification']]+=1
        if r['altitude_m']: d['alts'].append(float(r['altitude_m']))
        if r['rcs_m2']: d['rcs'].append(float(r['rcs_m2']))
        if r['speed_mps']: d['sp'].append(float(r['speed_mps']))
        if r['latitude']: d['pts'].append((r['time_utc'],float(r['latitude']),float(r['longitude'])))
        if r['range_m']: d['rng'].append(float(r['range_m']))
        if r['bearing_deg_true']: d['brg'].append(float(r['bearing_deg_true']))
        if r['alert']=='true': d['alert']=True
        if r['authorization_id'] and not d['auth']: d['auth']=r['authorization_id']
pickle.dump(tr,open('/tmp/tracks.pkl','wb'))
print('rows',n,'tracks',len(tr))
for c,v in cols.items(): print(c,dict(v.most_common(25)))
