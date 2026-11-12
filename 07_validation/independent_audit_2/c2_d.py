from common import *
import glob, collections, json, math, csv
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
print('=== M13 NAS generator failure 2027-10-24')
show('base_status 10-22..27 NAS',[(r['report_date'],r['readiness_pct'],r['backup_power_status'],r['generator_test_result'],r['remarks'][:90]) for r in rows('maintenance/base_status_reports.csv') if r.get('facility_id',r.get('installation_id',''))=='FAC-DOD-01' and '2027-10-22'<=r['report_date']<='2027-10-27'])
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
