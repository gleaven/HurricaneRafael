"""Area 3: CAD dispatch->arrival versus AVL path for the same incident (Sept and Nov)."""
import pandas as pd, numpy as np, os, glob
from common import *
cad=pd.read_pickle('/tmp/cad.pkl')
for mon in ('2027-09','2027-11'):
    a=pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(SRC,'avl',f'avl_{mon}_*.csv'))])
    a['t']=pd.to_datetime(a.time_utc,utc=True).dt.tz_localize(None)
    a=a.dropna(subset=['incident_number']).sort_values(['incident_number','unit_id','t'])
    same=(a.incident_number.eq(a.incident_number.shift()))&(a.unit_id.eq(a.unit_id.shift()))
    a['step']=np.hypot((a.latitude-a.latitude.shift())*111195,(a.longitude-a.longitude.shift())*98400).where(same,0)
    enr=a[a.status=='ENR']
    g=enr.groupby(['incident_number','unit_id']).agg(t0=('t','min'),t1=('t','max'),path=('step','sum'),n=('t','size')).reset_index()
    ons=a[a.status=='ONS'].groupby(['incident_number','unit_id']).agg(ons_t=('t','min'),olat=('latitude','first'),olon=('longitude','first')).reset_index()
    m=g.merge(ons,on=['incident_number','unit_id'],how='left').merge(cad[['incident_number','unit_id','dispatch_dttm','first_arrival_dttm','lat','lon','d','priority','call_received_dttm']],on=['incident_number','unit_id'],how='inner')
    utc_off=5 if mon<'2027-11' else None
    # local -> UTC (CDT until 7 Nov 07:00Z)
    def toutc(s): 
        off=np.where(s<pd.Timestamp('2027-11-07 02:00'),5,6); return s+pd.to_timedelta(off,unit='h')
    m['disp_utc']=toutc(m.dispatch_dttm); m['arr_utc']=toutc(m.first_arrival_dttm)
    m['cad_min']=(m.arr_utc-m.disp_utc).dt.total_seconds()/60
    m['avl_enr_start_vs_dispatch_s']=(m.t0-m.disp_utc).dt.total_seconds()
    m['ons_vs_arrival_s']=(m.ons_t-m.arr_utc).dt.total_seconds()
    m['ons_to_incident_m']=np.hypot((m.olat-m.lat)*111195,(m.olon-m.lon)*98400)
    m['kmh']=m.path/1000/(m.cad_min/60)
    print('=====',mon,'incident-unit pairs with AVL ENR and CAD arrival:',len(m),'of CAD rows in month with arrival:',cad[(cad.call_received_dttm.dt.strftime('%Y-%m')==mon)&cad.first_arrival_dttm.notna()].shape[0])
    for c in ['avl_enr_start_vs_dispatch_s','ons_vs_arrival_s','ons_to_incident_m','kmh','path','cad_min']:
        print(' ',c,m[c].quantile([.01,.25,.5,.75,.99]).round(1).tolist(),'nan',m[c].isna().sum())
    print('  implied avg speed >130 km/h:',(m.kmh>130).sum(),' <3 km/h with path>500m:',((m.kmh<3)&(m.path>500)).sum(),' ONS fix >300 m from incident:',(m.ons_to_incident_m>300).sum(),' |ons-arrival|>120 s:',(m.ons_vs_arrival_s.abs()>120).sum())
    print(m[m.kmh>130][['incident_number','unit_id','path','cad_min','kmh','d']].head(5).to_string())
    print(m[m.ons_to_incident_m>300][['incident_number','unit_id','ons_to_incident_m','d']].head(5).to_string())
    if mon=='2027-11':
        x=m[(m.disp_utc>='2027-11-07T07:00')&(m.disp_utc<'2027-11-09')]; print('  after DST change: enr start vs dispatch s',x.avl_enr_start_vs_dispatch_s.quantile([.05,.5,.95]).tolist(), len(x))
        y=m[(m.disp_utc>='2027-11-05')&(m.disp_utc<'2027-11-07T06:00')]; print('  before DST change:',y.avl_enr_start_vs_dispatch_s.quantile([.05,.5,.95]).tolist(), len(y))
