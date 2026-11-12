"""Area 2: TFR window, trainer evacuation/return, relief airlift, runway transitions."""
import pandas as pd, numpy as np, os, json
from common import *
import geo
G=geo.Geo(build_roads=False)
reg=json.load(open(os.path.join(REG,'aircraft_registry.json'))); ac={a['icao24']:a for a in reg['aircraft']}
df=pd.read_pickle('/tmp/adsb.pkl')
def nm(lat,lon,lat0,lon0): return np.hypot((lat-lat0)*60,(lon-lon0)*60*np.cos(np.radians(lat0)))
df['d_crp']=nm(df.latitude,df.longitude,27.77218,-97.50242)
tfr=df[(df.t>='2027-09-12T05:01')&(df.t<'2027-09-14T06:00')&(df.d_crp<=30)&(df.baro_altitude<5486.4)]
print('rows inside TFR volume, TFR start to landfall:',len(tfr),' airborne:',(~tfr.on_ground).sum())
x=tfr[~tfr.on_ground]
print(x.groupby(['icao24','callsign','type','mil']).agg(n=('t','size'),t0=('t','min'),t1=('t','max'),alt=('baro_altitude','median')).to_string())
x2=df[(df.t>='2027-09-12T05:01')&(df.t<'2027-09-14T06:00')&(df.d_crp<=30)&(~df.on_ground)]
print('airborne within 30 nm at any altitude:'); print(x2.groupby(['icao24','callsign','type','mil']).agg(n=('t','size'),t0=('t','min'),t1=('t','max'),alt=('baro_altitude','median')).to_string())
# landfall to +36h
x3=df[(df.t>='2027-09-14T06:00')&(df.t<'2027-09-15T18:00')&(df.d_crp<=60)&(~df.on_ground)]
print('airborne within 60 nm, landfall..+36h:'); print(x3.groupby(['icao24','callsign','type','mil']).agg(n=('t','size'),t0=('t','min'),t1=('t','max'),alt=('baro_altitude','median')).to_string())
# daily unique airborne aircraft by civil/mil D-6..D+10
d=df[(~df.on_ground)&(df.t>='2027-09-07')&(df.t<'2027-09-26')]
print(d.groupby([d.t.dt.date,'mil']).icao24.nunique().unstack(fill_value=0).to_string())
# trainers
tr=df[df.type.isin(['TEX2','T45','BE9L'])&(~df.on_ground)]
print('trainer airborne rows per day around evac/return:')
c=tr.groupby([tr.t.dt.date,'type']).icao24.nunique().unstack(fill_value=0)
print(c.loc[pd.to_datetime('2027-09-05').date():pd.to_datetime('2027-09-27').date()].to_string())
