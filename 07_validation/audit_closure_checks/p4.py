import csv,glob,json,re,collections,os,sys,math,bisect
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
def E(s): return int(datetime.strptime(s[:19].replace(' ','T'),'%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc).timestamp())
def hav(a,b,c,d):
    R=6371000; p1,p2=math.radians(a),math.radians(c); x=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(d-b)/2)**2
    return 2*R*math.asin(math.sqrt(x))
_a=json.load(open('06_data_streams/aircraft_registry.json')); _a=_a if isinstance(_a,list) else next(v for v in _a.values() if isinstance(v,list) and v and isinstance(v[0],dict) and 'icao24' in v[0]); reg={a['registration']:a['icao24'] for a in _a}
sar=list(rows(O+'sar/sar_missions.csv')); air=[r for r in sar if r['asset_type']=='helicopter']
want={reg[r['asset_id']] for r in air if r['asset_id'] in reg}
tr=collections.defaultdict(list)
with open(O+'adsb/adsb_2027-09.csv',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r['icao24'] in want: tr[r['icao24']].append((int(r['time_position']),float(r['latitude']),float(r['longitude']),r['on_ground']))
for k in tr: tr[k].sort()
near=far=nofix=0; ground=0
for r in air:
    L=tr.get(reg.get(r['asset_id'],''),[]); t=E(r['on_scene_utc']); i=bisect.bisect_left(L,(t,))
    cand=[L[j] for j in (i-1,i) if 0<=j<len(L) and abs(L[j][0]-t)<=180]
    if not cand: nofix+=1; continue
    d=min(hav(float(r['latitude']),float(r['longitude']),c[1],c[2]) for c in cand)
    if d<=600: near+=1
    else: far+=1
    if all(c[3]=='True' for c in cand): ground+=1
print('D2-04 helicopter rescues',len(air),'ADS-B fix within 600 m at on-scene time',near,'farther',far,'no fix within 3 min',nofix,'airframe on ground',ground)
ms=collections.defaultdict(list)
for r in air: ms[r['mission_id']].append(r)
surv=[sum(int(x['persons']) for x in v) for v in ms.values()]; dur=[(E(v[0]['recovery_utc'])-E(v[0]['launch_utc']))//60 for v in ms.values()]
print('  sorties',len(ms),'survivors per sortie',sorted(surv),'durations min',sorted(dur))
lm=0
for m,v in ms.items():
    L=tr.get(reg.get(v[0]['asset_id'],''),[]); t=E(v[0]['launch_utc']); 
    # first airborne fix near launch
    ab=[x[0] for x in L if x[3]=='False' and abs(x[0]-t)<=300]
    if ab: lm+=1
print('  sorties with an airborne fix within 5 min of launch',lm,'of',len(ms))
# ---- D2-08 shelters
cen=list(rows(O+'shelters/shelter_daily_census.csv')); intake=list(rows(O+'shelters/shelter_intake_log.csv')); regs={r['facility_id']:r for r in rows(O+'shelters/shelter_registry.csv')}
print('D2-08 occupancy over capacity rows',sum(1 for r in cen if int(r['occupancy'])>int(r['capacity'])))
ia=C(); 
for r in intake: ia[(r['arrival_local'][:10],r['facility_id'])]+=int(r['persons'])
mism=sum(1 for r in cen if ia.get((r['date_local'],r['facility_id']),0)!=int(r['new_arrivals'])); print('  census new_arrivals != intake sum:',mism,'of',len(cen))
early=sum(1 for r in intake if r['arrival_local']<regs[r['facility_id']]['opened_local']); print('  intake before opening',early,'intake modes',C(r['arrival_mode'] for r in intake).most_common())
sd=C(); 
for r in sar:
    if r['delivered_to'].startswith('FAC-SHLT'): sd[r['delivered_to']]+=int(r['persons'])
si=C()
for r in intake:
    if 'rescue' in r['arrival_mode'].lower() or 'sar' in r['arrival_mode'].lower(): si[r['facility_id']]+=int(r['persons'])
print('  SAR delivered to shelters',dict(sd),'intake by SAR mode',dict(si))
bus=list(rows(O+'shelters/evacuation_bus_trips.csv')); print('D2-17 bus arrivals before opening',sum(1 for r in bus if r['arrival_local']<regs[r['facility_id']]['opened_local']),'of',len(bus),'opened',{k:v['opened_local'] for k,v in regs.items()})
# ---- D2-09 damage
dm=list(rows(O+'infrastructure/damage_assessment.csv'))
hh=C((r['ASMT_TYPE'],int(r['ASMT_DATE'][11:13])) for r in dm if len(r['ASMT_DATE'])>12)
types=sorted({k[0] for k in hh}); 
for t in types: print('D2-09 hours',t,[hh[(t,h)] for h in range(24)],'(index = hour as written in file)')
print('  sample ASMT_DATE',dm[0]['ASMT_DATE'])
ne=[r for r in dm if r['FLOOD_DEPTH_FT'] and float(r['FLOOD_DEPTH_FT'])>=5 and 'elev' not in r['FOUNDATION'].lower() and 'pier' not in r['FOUNDATION'].lower() and 'pile' not in r['FOUNDATION'].lower()]
last={}
for r in dm: last[r['structure_id']]=r
ne2=[r for r in last.values() if r['FLOOD_DEPTH_FT'] and float(r['FLOOD_DEPTH_FT'])>=5 and not re.search('elev|pier|pile|stilt',r['FOUNDATION'],re.I)]
print('  structures',len(last),'non-elevated >=5 ft',len(ne2),'of which MIN/AFF/NVD',sum(1 for r in ne2 if r['DMG_LEVEL'] in('MIN','AFF','NVD')),'foundations',C(r['FOUNDATION'] for r in last.values()).most_common(6))
for z in ('78373','78402'):
    L=[r for r in last.values() if r['zip']==z]; 
    if L: print('  zip',z,len(L),'major/destroyed %',round(100*sum(1 for r in L if r['DMG_LEVEL'] in('MAJ','DST'))/len(L)),'mean depth',round(sum(float(r['FLOOD_DEPTH_FT'] or 0) for r in L)/len(L),1))
mh=[r for r in last.values() if 'manuf' in (r['structure_type']+r['OCCUPANCY']).lower() or 'mobile' in (r['structure_type']+r['OCCUPANCY']).lower()]
print('  manufactured homes',len(mh),'two-storey',sum(1 for r in mh if r['STORIES'] not in('1','1.0')),'over 2000 sqft',sum(1 for r in mh if float(r['SQ_FT'] or 0)>2000))
ad=C(r['address'] for r in last.values()); print('  addresses shared by >1 structure',sum(1 for a,n in ad.items() if n>1))
us=list(rows(O+'infrastructure/utility_site_survey.csv')); print('  site survey optical rows before 12:20Z',[(r['asset_id'],r['survey_time_utc'],r['sensor']) for r in us if r['survey_time_utc'][11:16]<'12:20' and not re.search('therm|infra|SAR|radar',r['sensor'],re.I)][:6]); print('  sensors',C(r['sensor'] for r in us).most_common(), [ (r['asset_id'],r['survey_time_utc'],r['sensor'],r['tile_set_id']) for r in us if 'UTL-02' in r['tile_set_id']])
fl=list(rows(O+'drone_video/logs/flight_log.csv')); print('D2-13 0922 UTL flights',[(r['flight_id'],r['takeoff_utc'],r['sensor'],r['spectral_band'],r['tile_set_id']) for r in fl if '0922-UTL' in r['tile_set_id']])
print('D2-23 drone max alt by model distinct',{m:len({r['max_alt_m_agl'] for r in fl if r['drone_model']==m}) for m in {r['drone_model'] for r in fl}})
