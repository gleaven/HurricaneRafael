import csv,glob,json,re,collections,os,sys,math
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
sar=list(rows(O+'sar/sar_missions.csv')); intake=list(rows(O+'shelters/shelter_intake_log.csv'))
print('intake reference samples',C(re.sub(r'\d','9',r['reference']) for r in intake).most_common(8))
refs=C(); 
for r in intake: refs[r['reference']]+=int(r['persons'])
sh=[r for r in sar if r['delivered_to'].startswith('FAC-SHLT')]
print('D2-08 SAR cases delivered to shelters',len(sh),'persons',sum(int(r['persons']) for r in sh),'cases found as intake reference',sum(1 for r in sh if r['case_number'] in refs or r['mission_id'] in refs), 'delivered_to kinds',C(r['delivered_to'][:8] for r in sar).most_common(8))
dm=list(rows(O+'infrastructure/damage_assessment.csv')); print('D2-09 OCCUPANCY',C(r['OCCUPANCY'] for r in dm).most_common(8),'types',C(r['structure_type'] for r in dm).most_common(8),'ASMT_TYPE',C(r['ASMT_TYPE'] for r in dm).most_common())
mh=[r for r in dm if re.search('manuf|mobile|MH',r['OCCUPANCY']+r['structure_type'])]; print('  MH rows',len(mh),'stories',C(r['STORIES'] for r in mh).most_common(4),'>2000sqft',sum(1 for r in mh if float(r['SQ_FT'] or 0)>2000))
# ---- D2-07 fuel
fd=list(rows(O+'supply/fuel_deliveries.csv')); dl=[r for r in fd if r['record_type']=='DELIVERY']
v2=[r for r in dl if r['supplier_id']=='VND-0002']; print('D2-07 fuel deliveries',len(dl),'by supplier',C(r['supplier_id'] for r in dl).most_common(5)); print('  VND-0002 deliveries',len(v2),'gal',sum(float(r['volume_gal']) for r in v2),'tickets',sorted({r['ticket_id'] for r in v2})[:3],'..',sorted({r['ticket_id'] for r in v2})[-1],'dates',min(r['delivered_utc'] for r in v2)[:10],max(r['delivered_utc'] for r in v2)[:10])
inv=[r for r in rows(O+'payments/contracts_invoices.csv') if r['supplier_id']=='VND-0002']; print('  VND-0002 invoices',len(inv),'qty',sum(float(r['quantity'] or 0) for r in inv),'amount',sum(float(r['amount_usd']) for r in inv),'desc sample',inv[0]['description'][:120], 'periods',min(r['period_start'] for r in inv),max(r['period_end'] for r in inv))
tk=set(r['ticket_id'] for r in v2); print('  invoice descriptions naming a ledger ticket',sum(1 for r in inv if any(t in r['description'] for t in tk)),'of',len(inv))
act=[r for r in rows(O+'payments/contracts_actions.csv') if r['supplier_id']=='VND-0002']; print('  actions',[(r['action_date'],r['action_type'],r['description'][:110]) for r in act])
bs=list(rows(O+'maintenance/base_status_reports.csv')); print('  base status remarks around 10-24',[(r['report_date'],r['backup_power_status'],r['remarks'][:120]) for r in bs if '2027-10-23'<=r['report_date']<='2027-10-26' and 'NAS' in r['installation_name']][:5])
print('D2-21 perimeter sensor status by date',[(r['report_date'],r['perimeter_sensor_status']) for r in bs if 'NAS' in r['installation_name'] and r['report_date'] in('2027-09-13','2027-09-14','2027-09-15','2027-09-24','2027-09-26','2027-09-27')])
print('D2-23 depot readiness diffs',C(round(float(b['readiness_pct'])-float(a['readiness_pct']),1) for a,b in zip([r for r in bs if 'Depot' in r['installation_name']],[r for r in bs if 'Depot' in r['installation_name']][1:])).most_common(6))
ss=[r for r in rows(O+'drone_detections/sensor_status_2027-09.csv') if r['status'].lower()!='online' and r['status'].lower()!='ok']; 
by=collections.defaultdict(list)
for r in ss: by[r['sensor_id']].append(r['time_utc'])
print('  sensors not online Sept: first/last',{k:(min(v),max(v),len(v)) for k,v in list(by.items())[:6]})
sr=list(rows(O+'drone_detections/sighting_reports.csv')); print('  sunset text at day hours',[(r['report_id'],r['time_utc']) for r in sr if re.search('after sunset|after dark|at night',r['description']) and 12<=int(r['time_utc'][11:13])<24 and int(r['time_utc'][11:13])<=23 and 13<=int(r['time_utc'][11:13])<=23][:5])
# ---- D2-18 outage
om=[r for r in rows(O+'telemetry/outage_map.csv') if r['timestamp_utc'].startswith('2027-10-24') and int(r['customers_out'])>0]
print('D2-18 outage rows 10-24',len(om),C((r['area_id'],r['feeder_id'],r['cause']) for r in om).most_common(5),'times',min((r['timestamp_utc'] for r in om),default=''),max((r['timestamp_utc'] for r in om),default=''))
d0=collections.defaultdict(int)
for r in rows(O+'telemetry/outage_map.csv'):
    if '2027-09-13T18'<=r['timestamp_utc']<'2027-09-14T08': d0[r['timestamp_utc']]+=int(r['customers_out'])
print('  landfall night total out',[(k[5:16],v) for k,v in sorted(d0.items())][::6])
# ---- D2-19 aid vs bank
aid=[r for r in rows(O+'payments/aid_applications.csv')]
print('D2-20 record types',C(r['record_type'] for r in aid).most_common(6))
dis=[r for r in aid if 'DISB' in r['record_type'].upper() or 'disburs' in r['status'].lower()]
print('  disbursement-like rows',len(dis))
