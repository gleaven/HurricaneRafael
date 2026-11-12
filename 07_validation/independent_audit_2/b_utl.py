from common import *
import collections, sys, math
sys.path.insert(0,ROOT+'/scripts'); import geo
sv=[r for r in rows('infrastructure/utility_site_survey.csv')]
sites={r['asset_id']:(float(r['LATITUDE']),float(r['LONGITUDE'])) for r in sv}
near=collections.defaultdict(lambda:collections.defaultdict(list))
for r in rows('drone_video/drone_telemetry_2027-09_argus.csv'):
    if not r['mission_name'].startswith(('FEMA-UAV-0922','FEMA-UAV-0929','FEMA-UAV-0917','FEMA-UAV-0918')): continue
    p=(float(r['latitude']),float(r['longitude']))
    for s,q in sites.items():
        if abs(p[0]-q[0])<0.004 and abs(p[1]-q[1])<0.004 and geo.dist_m(p,q)<300: near[r['mission_name']][s].append(r['timestamp_utc'])
for m in sorted(near):
    if m.startswith(('FEMA-UAV-0922','FEMA-UAV-0929')):
        for s,t in near[m].items(): print(m,s,min(t),max(t),len(t))
print('--- survey rows vs overflight')
for r in sv:
    ph=r['phase']; 
    if ph.startswith('PHASE 2'):
        pref='FEMA-UAV-0922' if '09-22' in r['survey_time_utc'] else 'FEMA-UAV-0929'
        hits=[(m,min(t),max(t)) for m in near if m.startswith(pref) for s,t in near[m].items() if s==r['asset_id']]
        print(r['asset_id'],r['survey_time_utc'],'overflights:',hits)
p1=[r for r in sv if r['phase'].startswith('PHASE 1')]
print('phase1 rows',len(p1))
miss=0
for r in p1:
    hits=[(m,min(t)) for m in near if m.startswith(('FEMA-UAV-0917','FEMA-UAV-0918')) for s,t in near[m].items() if s==r['asset_id']]
    ok=any(abs((ts(h[1])-ts(r['survey_time_utc'])).total_seconds())<900 for h in hits)
    if not ok: miss+=1; print('  no overflight within 15 min:',r['asset_id'],r['survey_time_utc'],hits[:2])
print('phase1 without matching overflight',miss)
