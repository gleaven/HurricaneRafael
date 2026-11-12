"""Area 2: flight segmentation; landings/take-offs vs runways; relief airlift counts; sortie duration."""
import pandas as pd, numpy as np, os, json
from common import *
import geo
G=geo.Geo(build_roads=False)
reg=json.load(open(os.path.join(REG,'aircraft_registry.json'))); ac={a['icao24']:a for a in reg['aircraft']}
fields={a['airfield_id']:a for a in reg['airfields']}
df=pd.read_pickle('/tmp/adsb.pkl').sort_values(['icao24','t']).reset_index(drop=True)
same=df.icao24.eq(df.icao24.shift()); dt=(df.t-df.t.shift()).dt.total_seconds().where(same)
prev_g=df.on_ground.shift().where(same)
# transitions with a short gap
ld=df[same&(prev_g==False)&(df.on_ground)&(dt<120)]
to=df[same&(prev_g==True)&(~df.on_ground)&(dt<120)]
heli={'H60','H65','EC35','B429','AS50','B06','H47','H64'}
def rw(d):
    return np.array([G.runway_distance_m(a,b)[0] for a,b in zip(d.latitude,d.longitude)])
for name,d in (('landings',ld),('take-offs',to)):
    d=d.copy(); d['rw']=rw(d); fw=d[~d.type.isin(heli)]
    print(name,len(d),'fixed-wing',len(fw),'runway dist m quantiles',fw.rw.quantile([.5,.9,.99,1]).round(0).tolist(),' >60 m:',(fw.rw>60).sum())
    if (fw.rw>60).sum(): print(fw[fw.rw>60].groupby(['type','callsign']).agg(n=('rw','size'),mx=('rw','max'),ex=('t','first'),lat=('latitude','first'),lon=('longitude','first')).head(12).to_string())
    hh=d[d.type.isin(heli)]
    print('  helicopters',len(hh),'touch down/lift off on land?', end=' ')
    land=np.array([G.is_land(a,b) for a,b in zip(hh.latitude,hh.longitude)]); print('in water:',(~land).sum())
    if (~land).sum(): print(hh[~land].groupby(['type','callsign']).agg(n=('t','size'),ex=('t','first'),lat=('latitude','first'),lon=('longitude','first')).head(10).to_string())
    if name=='landings': LD=d
# on-ground rows: all on land & near an airfield?
g=df[df.on_ground]
land=G.is_land_many(g.latitude.values,g.longitude.values); print('on_ground rows in water:',(~land).sum(),'of',len(g))
def nearest_field(lat,lon):
    best=None
    for k,a in fields.items():
        d=np.hypot((lat-a['latitude'])*111.2,(lon-a['longitude'])*98.4)
        if best is None or d<best[1]: best=(k,d)
    return best
LD['fld']=[nearest_field(a,b) for a,b in zip(LD.latitude,LD.longitude)]; LD['field']=LD.fld.str[0]; LD['fd']=LD.fld.str[1]
r=LD[(LD.t>='2027-10-14')&(LD.t<'2027-11-02')&(LD.field=='NGP')&(LD.fd<4)&LD.type.isin(['C17','B734','B752','AT72','B350','C208','DH8B','CRJ7','E75L'])]
print('landings at NGP 14 Oct..1 Nov by type/day:'); print(r.groupby([r.t.dt.date,'type']).size().unstack(fill_value=0).to_string())
w=r[(r.t>='2027-10-18T05:00')&(r.t<'2027-10-28T05:00')]
print('D+34..D+43 local window: C17',(w.type=='C17').sum(),' civil',(w.type!='C17').sum(), ' callsigns:',sorted(w.callsign.str.strip().unique())[:60])
allc17=LD[LD.type=='C17']; print('all C17 landings by field:',allc17.groupby('field').size().to_dict(),' date range',allc17.t.min(),allc17.t.max())
civ=LD[LD.type.isin(['B734','B752'])]; print('B734/B752 landings by field:',civ.groupby('field').size().to_dict(),civ.t.min(),civ.t.max())
# sortie durations (continuous airborne with gaps<10 min)
a=df[~df.on_ground].copy(); s2=a.icao24.eq(a.icao24.shift()); d2=(a.t-a.t.shift()).dt.total_seconds().where(s2)
a['seg']=((~s2)|(d2>900)).cumsum()
so=a.groupby(['seg','icao24','callsign','type']).agg(t0=('t','min'),t1=('t','max'),n=('t','size')).reset_index(); so['h']=(so.t1-so.t0).dt.total_seconds()/3600
print('sortie hours by type: max'); print(so.groupby('type').h.agg(['count','median','max']).round(2).to_string())
print(so[(so.type.isin(heli))&(so.h>4.5)].sort_values('h',ascending=False).head(10).to_string())
