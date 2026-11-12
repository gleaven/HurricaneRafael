import csv,glob,json,re,collections,os,sys,math,statistics
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
bs=list(rows(O+'maintenance/base_status_reports.csv')); print('installations',C(r['installation_name'] for r in bs).most_common(5))
nas=[r for r in bs if 'Corpus Christi' in r['installation_name'] and 'Depot' not in r['installation_name']]
print('D2-21 perimeter status runs',[(k,len(list(v))) for k,v in __import__('itertools').groupby(r['perimeter_sensor_status'] for r in nas)][:12]); 
chg=[(a['report_date'],a['perimeter_sensor_status'],b['perimeter_sensor_status']) for a,b in zip(nas,nas[1:]) if a['perimeter_sensor_status']!=b['perimeter_sensor_status']]; print('  changes',chg[:8])
print('D2-07 base status 10-23..26',[(r['report_date'],r['backup_power_status'],r['remarks'][:140]) for r in nas if '2027-10-23'<=r['report_date']<='2027-10-26'])
# ---- social posts
pre=C(); cur=C(); n=0; ferry=0; bot=[]
LAND='2027-09-14T06:00'
def created(o):
    c=o.get('created_at','')
    try: return datetime.strptime(c,'%a %b %d %H:%M:%S %z %Y').strftime('%Y-%m-%dT%H:%M:%S')
    except Exception: return c
for f in glob.glob(O+'social_media/*.jsonl'):
    for ln in open(f,encoding='utf-8'):
        o=json.loads(ln); n+=1; t=created(o); x=o.get('full_text') or o.get('text','')
        if t<LAND and re.search(r'after the storm|since the storm|waited more than a day',x,re.I): pre[x[:70]]+=1
        if t<'2027-09-15T14:00' and re.search(r'curfew|toque de queda',x,re.I): cur[t[:10]]+=1
        if '2027-10-28T06'<=t<'2027-11-11' and re.search(r'ferry (wait|line)',x,re.I): ferry+=1
print('D2-10 posts',n,'pre-landfall after-the-storm templates',sum(pre.values()),pre.most_common(3)); print('A1-6 curfew posts before 2027-09-15T14Z',sum(cur.values()),cur.most_common(4)); print('A1-18 ferry-wait posts during blast closure',ferry)
# ---- D2-12 historian
for f in glob.glob(O+'telemetry/historian_WTP_202709.csv'):
    hd=None; out=[]
    for r in rows(f):
        if hd is None: hd=list(r.keys()); print('D2-12 header',hd[:8])
        tag=r.get('tag') or r.get('TagName') or r.get('tag_name') or ''
        if 'PUMP3.PRESS' in tag:
            t=r.get('timestamp_utc') or r.get('time_utc') or r.get('timestamp') or r.get('DateTime')
            if '2027-09-22T18:00'<=t<='2027-09-23T02:20': out.append((t[5:19],r.get('value') or r.get('Value')))
    print('  P3 pressure',out[::6][:9],out[-6:])
# ---- D2-14 ED blast arrivals
ed=glob.glob(O+'public_health/*ed_visits*'); print('ed files',[os.path.basename(x) for x in ed][:6])
for f in ed:
    if '2027-10' in f or '202710' in f:
        L=[r for r in rows(f) if '2027-10-28' in r.get('Arrive_Date_Time','')]
        hit=[(r['Arrive_Date_Time'],r.get('Chief_Complaint','')[:60],r.get('Arrival_Mode',''),r.get('Facility_ID','')) for r in L if re.search('blast|burn|explos|tug|marine',' '.join(r.values()),re.I)]
        print('D2-14 ED 10-28 rows',len(L),'blast/burn/marine',hit[:4])
cad=[r for r in rows(O+'911/cad_incidents_2027-10.csv') if re.search('EXPLO',r.get('nature_code','')+r.get('incident_type',''))]
print('  CAD EXPLOSION incidents',len(cad),C((r.get('disposition',''),r.get('transport_dest','')) for r in cad).most_common(6))
# ---- D2-15 satellite
for f in sorted(glob.glob(O+'satellite/CORVUS-SAR-202710*')): 
    o=json.load(open(f)); s=json.dumps(o)
    print('D2-15',os.path.basename(f),'tasking' , [o.get(k) for k in ('tasking','collection_type','acquisition_type','priority','note','notes') if k in o], 'uncorrelated' in s.lower(), 'routine' in s.lower())
