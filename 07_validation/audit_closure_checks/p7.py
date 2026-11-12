import csv,glob,json,re,collections,os,sys,math,statistics,itertools
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
bs=list(rows(O+'maintenance/base_status_reports.csv')); nas=[r for r in bs if r['installation_name']=='Naval Air Station Corpus Christi']
print('D2-21 NASCC perimeter runs',[(k,len(list(v))) for k,v in itertools.groupby(r['perimeter_sensor_status'] for r in nas)],'first offline',next(r['report_date'] for r in nas if 'offline' in r['perimeter_sensor_status']),'last offline',[r['report_date'] for r in nas if 'offline' in r['perimeter_sensor_status'] or 'degraded' in r['perimeter_sensor_status']][-1])
dep=[r for r in bs if r['installation_name']=='Corpus Christi Army Depot']; print('D2-23 depot readiness diffs',C(round(float(b['readiness_pct'])-float(a['readiness_pct']),1) for a,b in zip(dep,dep[1:]) if a['readiness_pct']!=b['readiness_pct']).most_common(8))
tags=C()
out=[]
with open(O+'telemetry/historian_WTP_202709.csv',encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if 'PUMP3' in r['Tagname'] and 'PRESS' in r['Tagname']:
            tags[r['Tagname']]+=1
            if '2027-09-22T18:00'<=r['Timestamp'].replace(' ','T')<='2027-09-23T02:20': out.append((r['Timestamp'][5:19],r['Value']))
print('D2-12 tags',tags.most_common(3)); print('  P3 pressure',out[::8][:6],out[-8:])
f=glob.glob(O+'public_health/ed_visits_*.csv')[0]; print('ED header',open(f,encoding='utf-8').readline().strip()[:400])
hit=[]; n28=0
for f in glob.glob(O+'public_health/ed_visits_*.csv'):
    for r in rows(f):
        if r['Arrive_Date_Time'].startswith('2027-10-28'):
            n28+=1
            if re.search('blast|burn|explos|tug|vessel',' '.join(str(v) for v in r.values()),re.I): hit.append((r['Arrive_Date_Time'],r['Facility_ID'],[v for k,v in r.items() if re.search('Complaint|Mode|Diag|Triage',k)]))
print('D2-14 ED rows on 10-28',n28,'blast/burn/marine rows',len(hit),hit[:3])
h=open(O+'911/cad_incidents_2027-10.csv',encoding='utf-8').readline().strip(); print('CAD header',h[:600])
cad=[r for r in rows(O+'911/cad_incidents_2027-10.csv') if 'EXPLO' in ' '.join(r.values()).upper() and r.get('received_utc',r.get('call_received_utc',''))[:10]=='2027-10-28']
print('  CAD 10-28 explosion rows',len(cad)); 
for r in cad[:4]: print('   ',{k:v for k,v in r.items() if v and k in ('incident_number','received_utc','nature_code','disposition','transport_dest','unit_id','units_assigned','narrative','priority')})
sat=[]
for f in sorted(glob.glob(O+'satellite/CORVUS-SAR-*')):
    o=json.load(open(f)); m=re.search(r'(\d{8})T(\d{4})',f); sat.append((m.group(1),m.group(2),o))
print('D2-15 CORVUS passes',len(sat),'times of day',C(t for d,t,o in sat).most_common(8)); o=[o for d,t,o in sat if d=='20271015'][0]; print('  keys',list(o.keys())[:20]); print('  1015 0420 text',json.dumps(o)[:900])
