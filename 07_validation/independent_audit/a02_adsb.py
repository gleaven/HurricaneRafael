"""Area 2: ADS-B. Epoch, registry, TFR, type envelopes, transitions."""
import pandas as pd, numpy as np, os, glob, json, sys
from common import *
reg=json.load(open(os.path.join(REG,'aircraft_registry.json')))
ac={a['icao24']:a for a in reg['aircraft']}
df=pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(SRC,'adsb','adsb_*.csv')))],ignore_index=True)
df['t']=pd.to_datetime(df.time_position,unit='s')
df['type']=df.icao24.map(lambda i: ac.get(i,{}).get('type_designator'))
df['mil']=df.icao24.map(lambda i: ac.get(i,{}).get('military'))
df['file_ok']=True
print('rows',len(df),'t range',df.t.min(),df.t.max())
for f in sorted(glob.glob(os.path.join(SRC,'adsb','adsb_*.csv'))):
    d=pd.read_csv(f,usecols=['time_position']); t=pd.to_datetime(d.time_position,unit='s'); print(os.path.basename(f),t.min(),t.max(),len(d))
print('icao24 not in registry:',sorted(set(df.icao24)-set(ac))[:20],' registry aircraft absent from data:',len(set(ac)-set(df.icao24)))
print('callsign variants per icao24 >1:'); cs=df.groupby('icao24').callsign.nunique(); print(cs[cs>1].to_string())
print('dup icao+time',df.duplicated(['icao24','time_position']).sum(),' last_contact<time_position',(df.last_contact<df.time_position).sum())
env=df[~df.on_ground].groupby('type').agg(n=('velocity','size'),vmax=('velocity','max'),v50=('velocity','median'),altmax=('baro_altitude','max'),alt50=('baro_altitude','median'),vrmax=('vertical_rate','max'),vrmin=('vertical_rate','min'))
env['vmax_kt']=(env.vmax*1.94384).round(0); env['altmax_ft']=(env.altmax*3.28084).round(0)
print(env.round(1).to_string())
g=df[df.on_ground]; print('on_ground rows',len(g),'velocity max',g.velocity.max(),'alt>50m on ground:',(g.baro_altitude>60).sum(), g.baro_altitude.describe().round(1).to_dict())
print('airborne with baro<0:',((~df.on_ground)&(df.baro_altitude<0)).sum(),' airborne v<15 m/s fixed wing:',((~df.on_ground)&(df.velocity<15)&(~df.type.isin(['H60','H65','EC45','B407','B429','A139','H47','UH60','EC35','AS50','B06','UH72','H64','R44','B412']))).sum())
df.to_pickle('/tmp/adsb.pkl')
print(df.groupby('type').icao24.nunique().to_string())
