# Part C block B: spill, landfall, SUB-01 trip, boil-water notices
from common import *
import glob, collections, json
def show(title, xs, n=8):
    print('  *',title,len(xs))
    for x in xs[:n]: print('      ',str(x)[:300])
def posts(pred, a, b):
    out=[]
    for f in glob.glob(SRC+'/social_media/*.jsonl'):
        for l in open(f,encoding='utf-8'):
            if not pred(l): continue
            d=json.loads(l); t=dt.datetime.strptime(d['created_at'],'%a %b %d %H:%M:%S %z %Y').strftime('%Y-%m-%dT%H:%M:%SZ')
            if a<=t<=b: out.append((t,d['user']['screen_name'],d['full_text'][:150]))
    return sorted(out)
print('=== M2 spill valves 2027-09-14T04:00Z-05:30Z')
for v in ('kalvora_star','ostrel_bay'):
    rs=[r for r in rows(f'telemetry/vessel_cargo_control_{v}.csv') if '2027-09-14T03:45'<=r['timestamp_utc']<='2027-09-14T05:45' and r['record_type'] not in('LEVEL',)]
    print('   ',v,collections.Counter(r['record_type'] for r in rs))
    show(v+' non-level records',[(r['timestamp_utc'],r['record_type'],r['station'],r['operator'],r['tag'],r['value'],r['text'][:90]) for r in rs],10)
show('remote sessions 09-14',[(r['session_id'],r['vendor_account'],r['src_asn'],r['login_utc'],r['logout_utc'],r['vessel_name'],r['result']) for r in rows('telemetry/vessel_cargo_control_remote_sessions.csv') if '2027-09-13T20'<=r['login_utc']<='2027-09-14T12'])
for s in ('WQ-01','WQ-02','WQ-05'):
    rs=[(r['ObsDateTime'][11:16],r['TotalHydrocarbons_ppb'],r['QC']) for r in rows(f'env_sensors/water_quality_{s}.csv') if '2027-09-14T03:30'<=r['ObsDateTime']<='2027-09-14T06:30']
    print('   ',s,rs[::1][:14])
show('camera events TERM-01 03:30-09Z',[(r['time_utc'],r['sensor_id'],r['event_type'],r['vessels_in_view'][:50],r['water_surface'],r['note'][:80]) for r in rows('port_surveillance/camera_events.csv') if '2027-09-14T03:30'<=r['time_utc']<='2027-09-14T12:00' and r['sensor_id'] in('CAM-01',)],8)
cad=[r for r in rows('911/cad_incidents_2027-09.csv') if '2027-09-13 22:00'<=r['call_received_dttm']<='2027-09-14 08:00' and r['nature_code'] in('FUELSPILL','HAZMATLVL1','GASLEAK')]
show('911 spill/hazmat D0 (local 22:00-08:00)',[(r['call_received_dttm'],r['nature_code'],r['address'],r['narrative'][:90]) for r in cad])
show('port_conditions 09-13..09-15',[(r['order_id'],r['issued_utc'],r['order_type'],r['segment_id'],r['status'],r['text'][:90]) for r in rows('supply/port_conditions.csv') if '2027-09-13T12'<=r['issued_utc']<='2027-09-15T23'],8)
show('posts spill first',posts(lambda l:'spill' in l.lower() or 'derrame' in l.lower() or 'oil' in l.lower(),'2027-09-14T00:00:00Z','2027-09-14T23:59:59Z'),5)
print('=== M3 landfall 06:00Z / M4 SUB-01 trip 07:12Z')
for st in ('KRAS','KNGP','KCRP'):
    f=SRC+f'/weather/{st}_ASOS_observations.csv'; rs=load(f); k=list(rs[0].keys())
    tcol=[c for c in k if 'time' in c.lower() or 'valid' in c.lower() or 'date' in c.lower()][0]
    seg=[r for r in rs if '2027-09-14T04'<=r[tcol].replace(' ','T')<='2027-09-14T09']
    print('   ',st,'cols',k[:12],'n',len(seg),[(r[tcol][11:16],)+tuple(r[c] for c in k if 'gust' in c.lower() or 'pres' in c.lower() or 'alti' in c.lower() or 'mslp' in c.lower())[:3] for r in seg[::3]][:8])
rs=[(r['ObsDateTime'][11:16],r['WaterLevel_ft_MLLW'],r['Residual_ft'],r['Quality']) for r in rows('env_sensors/gauge_TG-8775237.csv') if '2027-09-14T05:00'<=r['ObsDateTime']<='2027-09-14T07:30']
print('    gauge PA',rs[::5])
om=collections.defaultdict(int)
for r in rows('telemetry/outage_map.csv'):
    if '2027-09-14T05:00'<=r['timestamp_utc']<='2027-09-14T08:00': om[r['timestamp_utc']]+=int(r['customers_out'])
print('    outage total',sorted(om.items()))
import glob
h=[]
for r in rows('telemetry/historian_SUB01_202709.csv'):
    if '2027-09-14T07:00'<=r['Timestamp']<='2027-09-14T07:20' and ('BKR' in r['Tagname'] or 'REL' in r['Tagname'] or 'VOLT' in r['Tagname']): h.append((r['Timestamp'],r['Tagname'],r['Value'],r['Quality']))
show('historian SUB01 07:00-07:20',sorted(h),14)
show('hospital_capacity SRMC power',[(r['Report_Date'],r['Power_Source'],r['Commercial_Power_Lost_UTC'],r['Generator_Start_UTC']) for r in rows('public_health/hospital_capacity.csv') if r['Facility_ID']=='FAC-SRMC-001' and '2027-09-14'<=r['Report_Date']<='2027-09-15'])
show('EAS 09-14',[(r['AlertID'],r['EventCode'],r['ReleasedAt_EN'],r['ReleasedAt_ES'],r['Headline_EN'][:60]) for r in rows('public_health/eas_broadcasts.csv') if r['IssuedAt_UTC'].startswith('2027-09-14')])
hr=collections.Counter(r['call_received_dttm'][:13] for r in rows('911/cad_incidents_2027-09.csv') if r['call_received_dttm'].startswith('2027-09-14') or r['call_received_dttm'].startswith('2027-09-13 2'))
print('    911/hr local',sorted(hr.items()))
show('siem 07:05-07:20 ot',[(r['time_utc'],r['rule_name'],r['src_host'],r['detail'][:60]) for r in rows('network_logs/siem/siem_alerts_2027-09.csv') if '2027-09-14T07:08'<=r['time_utc']<='2027-09-14T07:18' and r['category']=='ot'],8)
show('work orders 09-14 07-09Z',[(r['wonum'],r['reported_date'],r['asset_id'],r['description'][:80]) for r in rows('maintenance/work_orders.csv') if '2027-09-14T07'<=r['reported_date']<='2027-09-14T10'],6)
print('=== M6 citywide boil water 2027-09-18T12:00Z; M10 D3/D4 2027-09-26T22:30Z')
show('EAS BWW',[(r['AlertID'],r['EventCode'],r['IssuedAt_UTC'],r['ReleasedAt_EN'],r['ReleasedAt_ES'],r['ExpiresAt_UTC'],r['GeographicArea'][:30]) for r in rows('public_health/eas_broadcasts.csv') if 'BW' in r['AlertID'] or 'boil' in r['Headline_EN'].lower()])
show('relay log BWW-0926',[(r['alert_id'],r['station_name'],r['received_utc'],r['result']) for r in rows('broadcast/alert_relay_log.csv') if '0926' in r['alert_id']],10)
show('translation jobs',[(r['job_id'],r['alert_id'],r['source_received_utc'],r['translation_delivered_utc'],r['first_aired_utc'],r['status']) for r in rows('broadcast/translation_jobs.csv')],10)
show('program log 09-26T22..09-27T12 alert items',[(r['air_time_utc'],r['station_name'],r['item'],r['language'],r['alert_id'],r['description'][:60]) for r in rows('broadcast/station_program_log.csv') if '2027-09-26T22'<=r['air_time_utc']<='2027-09-27T12' and (r['alert_id'] or 'ALERT' in r['item'])],10)
ws=[r for r in rows('911/cad_incidents_2027-09.csv') if r['nature_code']=='WATERSAFE']
print('    911 WATERSAFE first',ws[0]['call_received_dttm'] if ws else None,'by day',sorted(collections.Counter(r['call_received_dttm'][:10] for r in ws).items())[:6])
ws18=[r for r in rows('911/cad_incidents_2027-09.csv') if '2027-09-18 07:00'<=r['call_received_dttm']<='2027-09-18 12:00' and ('WATER' in r['narrative'] and ('BOIL' in r['narrative'] or 'DRINK' in r['narrative'] or 'PRESSURE' in r['narrative']))]
show('911 boil/pressure narratives 09-18 07-12 local',[(r['call_received_dttm'],r['nature_code'],r['narrative'][:80]) for r in ws18],4)
z=[]
for r in rows('telemetry/historian_DIST_202709.csv'):
    if 'ZONE4.PRESS' in r['Tagname'] and '2027-09-26T12'<=r['Timestamp']<='2027-09-26T23': z.append((r['Timestamp'][11:16],r['Value'],r['Quality']))
print('    zone4 press 09-26',z[::4])
show('work orders 09-26',[(r['wonum'],r['reported_date'],r['description'][:100],r['reported_by']) for r in rows('maintenance/work_orders.csv') if r['reported_date'].startswith('2027-09-26')],6)
show('posts D3/4',posts(lambda l:'Districts 3' in l or 'Distritos 3' in l or 'District 3' in l,'2027-09-26T00:00:00Z','2027-09-27T14:00:00Z'),8)
show('call-in log 09-26..28',[(r['air_time_utc'],r['primary_language'],r['topic']) for r in rows('broadcast/call_in_log.csv') if '2027-09-26'<=r['air_time_utc']<='2027-09-28'],6)
