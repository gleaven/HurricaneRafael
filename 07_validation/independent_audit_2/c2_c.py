# Part C block C: dark vessel 10-15, GPS window 10-22..27, generator 10-24, blast 10-28, ATO 11-15
from common import *
import glob, collections, json, math
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
def ais(month, pred):
    out=[]
    with open(f'{SRC}/ais/ais_{month}.csv') as f:
        h=f.readline().strip().split(',')
        for line in f:
            p=line.rstrip('\n').split(',')
            if pred(p): out.append(p)
    return h,out
print('=== M11 devices laid / dark vessel 2027-10-15T04:20Z')
h,a=ais('2027-10',lambda p:('PELICAN' in p[7] or 'HALCYON' in p[7]) and '2027-10-14T12'<=p[1]<='2027-10-16T12')
show('AIS Pelican/Halcyon 10-14..16',[(p[1],p[0],p[7],p[2],p[3],p[4],p[11]) for p in a[:3]+a[-3:]],6); print('      names',collections.Counter((p[0],p[7]) for p in a))
rt=[r for r in rows('port_surveillance/radar_tracks_2027-10.csv') if r['ais_correlated']=='N' and '2027-10-15T00'<=r['time_utc']<='2027-10-15T18']
byt=collections.defaultdict(list)
for r in rt: byt[r['track_id']].append(r)
show('radar uncorrelated tracks 10-15',[(k,v[0]['time_utc'],v[-1]['time_utc'],len(v),v[0]['est_length_m'],v[0]['latitude'],v[0]['longitude']) for k,v in byt.items()],8)
# where was NE-001301 at 04:20Z, distance from entrance channel jetties (27.834,-97.045)
x=[r for r in rt if r['time_utc'].startswith('2027-10-15T04:2')][:2]; print('      at 04:20',[(r['track_id'],r['time_utc'],r['latitude'],r['longitude'],r['speed_kn']) for r in x])
x=[r for r in rt if r['time_utc'].startswith('2027-10-15T09:3')][:2]; print('      at 09:30',[(r['track_id'],r['time_utc'],r['latitude'],r['longitude'],r['speed_kn']) for r in x])
show('camera events 10-15 00-16Z w/o mmsi',[(r['time_utc'],r['sensor_id'],r['event_type'],r['direction'],r['mmsi'],r['vessel_name'],r['est_length_m'],r['note'][:60]) for r in rows('port_surveillance/camera_events.csv') if '2027-10-15T00'<=r['time_utc']<='2027-10-15T16' and r['event_type']=='PASSAGE' and not r['mmsi']],6)
show('vessel_traffic_log 10-15 02-16Z',[(r['time_utc'],r['checkpoint'],r['direction'],r['vessel_name'],r['vessel_class']) for r in rows('port_surveillance/vessel_traffic_log.csv') if '2027-10-15T02'<=r['time_utc']<='2027-10-15T16'],8)
print('=== M12 GPS interference 2027-10-22..27')
import csv
nic=collections.defaultdict(list)
with open(SRC+'/adsb/adsb_2027-10.csv') as f:
    rd=csv.reader(f); hh=next(rd); i_t=hh.index('time_position'); i_n=hh.index('nic'); i_g=hh.index('on_ground')
    for p in rd:
        d=dt.datetime.fromtimestamp(int(p[i_t]),dt.timezone.utc).strftime('%m-%d')
        if p[i_n]!='' and '10-18'<=d<='10-31': nic[d].append(int(p[i_n]))
print('    ADS-B mean NIC by UTC day',[(d,round(sum(v)/len(v),2),len(v)) for d,v in sorted(nic.items())])
# AIS position scatter of moored vessels during jam window: KALVORA STAR std of position
h,a=ais('2027-10',lambda p:p[7]=='KALVORA STAR')
bd=collections.defaultdict(list)
for p in a: bd[p[1][:10]].append((float(p[2]),float(p[3])))
def spread(v):
    la=sum(x[0] for x in v)/len(v); lo=sum(x[1] for x in v)/len(v)
    return round(max(math.hypot((x[0]-la)*110950,(x[1]-lo)*98300) for x in v),1)
print('    AIS KALVORA STAR max position deviation m by day',[(d[5:],spread(v)) for d,v in sorted(bd.items()) if '2027-10-18'<=d<='2027-10-30'])
# drone telemetry in window: any flights and their jitter
fl=collections.Counter()
for r in rows('drone_video/drone_telemetry_2027-10.csv'):
    if '2027-10-20'<=r['timestamp_utc'][:10]<='2027-10-29': fl[(r['timestamp_utc'][:10],r['flight_id'])]+=1
print('    drone flights 10-20..29',collections.Counter(k[0] for k in fl))
show('posts gps',posts(lambda l:'GPS' in l,'2027-10-20T00:00:00Z','2027-11-02T00:00:00Z'),5)
show('port_conditions mentioning GPS',[(r['order_id'],r['issued_utc'],r['text'][:120]) for r in rows('supply/port_conditions.csv') if 'GPS' in r['text'] or 'GNSS' in r['text']])
show('911 narratives GPS',[(r['call_received_dttm'],r['narrative'][:80]) for r in rows('911/cad_incidents_2027-10.csv') if 'GPS' in r['narrative']],4)
print('=== M13 NAS generator failure 2027-10-24')
show('base_status 10-22..27 NAS',[(r['report_date'],r['readiness_pct'],r['backup_power_status'],r['generator_test_result'],r['remarks'][:90]) for r in rows('maintenance/base_status_reports.csv') if r['facility_id']=='FAC-DOD-01' and '2027-10-22'<=r['report_date']<='2027-10-27'])
om=collections.defaultdict(int)
for r in rows('telemetry/outage_map.csv'):
    if '2027-10-23'<=r['timestamp_utc'][:10]<='2027-10-26': om[r['timestamp_utc'][:10]]=max(om[r['timestamp_utc'][:10]],int(r['customers_out']))
print('    outage_map max customers_out per feeder-row by day',dict(om))
show('work orders 10-24/25 mention generator/NAS',[(r['wonum'],r['reported_date'],r['site_id'],r['description'][:90]) for r in rows('maintenance/work_orders.csv') if '2027-10-24'<=r['reported_date'][:10]<='2027-10-26'],6)
show('posts generator NAS',posts(lambda l:'generator' in l.lower() and ('NAS' in l or 'air station' in l.lower() or 'base' in l.lower()),'2027-10-24T00:00:00Z','2027-10-27T00:00:00Z'),4)
show('911 10-24 power',[(r['call_received_dttm'],r['nature_code'],r['narrative'][:60]) for r in rows('911/cad_incidents_2027-10.csv') if r['call_received_dttm'].startswith('2027-10-24') and r['nature_code'] in('UTILEMER','DWNPWRLINE')],4)
print('=== M14 jetty blast 2027-10-28T06:10Z')
h,a=ais('2027-10',lambda p:p[7]=='CORRIN BAY' and '2027-10-28T05:50'<=p[1]<='2027-10-28T06:30')
show('AIS CORRIN BAY',[(p[1],p[2],p[3],p[4],p[11]) for p in a],14)
ed=[]
for f in glob.glob(SRC+'/public_health/ed_visits_*.csv'):
    for r in rows(f):
        if '2027-10-28T06:10'<=r['Arrive_Date_Time']<='2027-10-28T10:00' and (r['CC_Category'] in('INJ','BURN','TRAUMA') or 'blast' in r['Chief_Complaint_Text'].lower() or 'explos' in r['Chief_Complaint_Text'].lower() or 'burn' in r['Chief_Complaint_Text'].lower()): ed.append((r['Arrive_Date_Time'],r['Facility_ID'],r['Arrival_Mode'],r['Chief_Complaint_Text'],r['Age'],r['Sex'],r['Disposition']))
show('ED injury arrivals 06:10-10:00Z',sorted(ed),10)
cad=[r for r in rows('911/cad_incidents_2027-10.csv') if r['nature_code']=='EXPLOSION' or ('2027-10-28 01:0'<=r['call_received_dttm']<='2027-10-28 02:30' and r['transport_destination'])]
show('911 explosion / transports',[(r['call_received_dttm'],r['nature_code'],r['unit_id'],r['disposition_code'],r['transport_destination'],r['narrative'][:60]) for r in cad],14)
show('posts blast',posts(lambda l:any(w in l.lower() for w in('explosion','blast','boom','tug')),'2027-10-28T06:00:00Z','2027-10-28T16:00:00Z'),6)
show('EAS 10-28',[(r['AlertID'],r['IssuedAt_UTC'],r['Headline_EN'][:70]) for r in rows('public_health/eas_broadcasts.csv') if r['IssuedAt_UTC'].startswith('2027-10-28')])
g=[(r['ObsDateTime'][11:16],r['WaterLevel_ft_MLLW'],r['Sigma_ft']) for r in rows('env_sensors/gauge_TG-8775237.csv') if '2027-10-28T06:00'<=r['ObsDateTime']<='2027-10-28T06:30']
print('    PA gauge',g)
print('=== M15 first account takeover 2027-11-15T19:37Z')
ft=[r for r in rows('payments/financial_transactions.csv') if r['account_id'] in('ACCT-40134','ACCT-40172','ACCT-40203') and 'assistance' in r['description']]
print('    diverted aid credits',len(ft),'first',min(r['timestamp'] for r in ft),'last',max(r['timestamp'] for r in ft),'sum',round(sum(float(r['amount_usd']) for r in ft)),collections.Counter(r['counterparty_account_masked'] for r in ft).most_common(4))
pp=[r for r in rows('payments/financial_transactions.csv') if 'prepaid' in r['description'].lower() or 'prepaid' in r['counterparty_name'].lower()]
print('    prepaid tx',len(pp),min(r['timestamp'] for r in pp),max(r['timestamp'] for r in pp),round(sum(float(r['amount_usd']) for r in pp)),collections.Counter(r['account_id'] for r in pp).most_common(3))
aid=[r for r in rows('payments/aid_applications.csv') if r['record_type']=='payment' or r['assistance_type']]
print('    aid rows with assistance_type',len(aid),collections.Counter(r['record_type'] for r in aid).most_common(5))
pay=[r for r in aid if r['deposit_account_masked'] in('****1073','****5333','****3176')]
print('    aid payments to the three accounts',len(pay),min((r['event_utc'] for r in pay),default=None),max((r['event_utc'] for r in pay),default=None),round(sum(float(r['amount_usd'] or 0) for r in pay)))
show('posts deposit',posts(lambda l:'deposit' in l.lower(),'2027-11-13T00:00:00Z','2027-11-20T00:00:00Z'),4)
