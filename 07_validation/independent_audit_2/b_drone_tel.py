# drone telemetry per-flight summary -> /tmp/flights.pkl
from common import *
import glob, math, pickle, collections
fl={}
def dist(a,b):
    return math.hypot((b[0]-a[0])*110950,(b[1]-a[1])*111320*math.cos(math.radians(27.8)))
for f in sorted(glob.glob(SRC+'/drone_video/drone_telemetry_*.csv')):
    for r in rows(f):
        k=r['flight_id']; p=(float(r['latitude']),float(r['longitude'])); t=r['timestamp_utc']; a=float(r['rel_alt_m'])
        d=fl.get(k)
        if d is None:
            d=fl[k]=dict(file=os.path.basename(f),op=r['operator_id'],model=r['drone_model'],mission=r['mission_name'],t0=t,p0=p,n=0,maxalt=a,minalt=a,km=0,last=p,lastt=t,maxv=0,gaps=0,frames_ok=True,maxd=0,pts=[],alt_last=a,alt0=a,maxvz=0,minlat=p[0],maxlat=p[0],minlon=p[1],maxlon=p[1])
        else:
            dtm=(ts(t)-ts(d['lastt'])).total_seconds()
            s=dist(d['last'],p); d['km']+=s/1000
            if dtm>0:
                d['maxv']=max(d['maxv'],s/dtm); d['maxvz']=max(d['maxvz'],abs(a-d['alt_last'])/dtm)
            if dtm!=1: d['gaps']+=1
        d['n']+=1; d['maxalt']=max(d['maxalt'],a); d['minalt']=min(d['minalt'],a); d['last']=p; d['lastt']=t; d['alt_last']=a
        d['maxd']=max(d['maxd'],dist(d['p0'],p))
        d['minlat']=min(d['minlat'],p[0]);d['maxlat']=max(d['maxlat'],p[0]);d['minlon']=min(d['minlon'],p[1]);d['maxlon']=max(d['maxlon'],p[1])
        if d['n']%30==0: d['pts'].append(p)
pickle.dump(fl,open('/tmp/flights.pkl','wb'))
print(len(fl),'flights')
