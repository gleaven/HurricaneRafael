import csv,glob,json,re,collections,os,datetime
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
al=list(rows(O+'network_logs/audit/alarm_suppression_audit.csv')); print('ticketless ADDs by account',C(r['changed_by'] for r in al if r['action']=='ADD' and not r['change_ticket']).most_common())
# A1-7 outage bot vs map
om=collections.defaultdict(int)
for r in rows(O+'telemetry/outage_map.csv'): om[r['timestamp_utc'][:16]]+=int(r['customers_out'])
keys=sorted(om)
import bisect
n=bad=0; ex=[]
for ln in open(O+'social_media/TXOutageCount.jsonl',encoding='utf-8'):
    o=json.loads(ln); t=datetime.datetime.strptime(o['created_at'],'%a %b %d %H:%M:%S %z %Y').strftime('%Y-%m-%dT%H:%M'); x=o.get('full_text') or o.get('text','')
    m=re.search(r'(\d{1,3}(?:,\d{3})+|\d+) customers',x)
    if not m or not (keys[0]<=t<=keys[-1]): continue
    v=int(m.group(1).replace(',','')); i=bisect.bisect_right(keys,t)-1; ref=om[keys[i]]; n+=1
    if abs(v-ref)>max(0.03*ref,60): bad+=1; ex.append((t,v,ref))
print('A1-7 bot posts with a customer count',n,'differing >3% from the map',bad,ex[:3])
# A1-8 false rescue calls
fr=[]
for f in sorted(glob.glob(O+'911/cad_incidents_2027-09.csv')):
    for r in rows(f):
        if r['ali_class_of_service'].upper().startswith('PREPAID') or 'PREPAID' in r['ali_class_of_service'].upper() or r['ali_class_of_service'] in('WPH2-PP','PPD'):
            if '2027-09-21'<=r['call_received_dttm'][:10]<='2027-09-24' and ('RESC' in r['nature_code'] or r['sar_priority'] not in('','N')) : fr.append(r)
print('A1-8 prepaid rescue calls 09-21..24',len(fr),C(r['call_received_dttm'][:10] for r in fr).most_common(),'first',min((r['call_received_dttm'] for r in fr),default=''),'dispositions',C(r['disposition_code'] for r in fr).most_common(4), 'classes',C(r['ali_class_of_service'] for r in rows(O+'911/cad_incidents_2027-09.csv')).most_common(6))
dv=list(rows(O+'911/reports/cbecc_daily_call_volume.csv')); print('A1-9 daily 911 calls 2027-08-16..29',[r['calls_911'] for r in dv if '2027-08-16'<=r['date_local']<='2027-08-29'])
# D2-01 benign remote sessions have flows
ra=[r for r in rows(O+'network_logs/audit/remote_access_sessions.csv') if r['src_network']!='internal' and r['account']!='GW-ENG-VELA']
import random; random.seed(1); smp=random.sample(ra,40); hit=0
for r in smp:
    d=r['login_utc'][:10]; p=O+f'network_logs/zeek/{d}/conn.log'
    if os.path.exists(p) and any(('\t'+r['src_ip']+'\t') in ln for ln in open(p,encoding='utf-8')): hit+=1
print('D2-01 benign external remote sessions sampled',len(smp),'with a flow from the source address that day',hit,'of',len(ra))
o=json.load(open(O+'satellite/CORVUS-SAR-20271015T042000Z-APPROACH.json')); pr=o['properties']; print('D2-15',{k:str(v)[:260] for k,v in pr.items() if re.search('desc|note|task|vessel|detect|title|mode',k,re.I)})
sc=json.load(open('06_data_streams/schemas/'+[f for f in os.listdir('06_data_streams/schemas') if 'damage' in f][0])); print('D2-09 schema',re.findall(r'[^"]{0,80}\bAI\b[^"]{0,160}',json.dumps(sc))[:2], re.findall(r'[^"]{0,60}ASMT_DATE[^"]{0,200}',json.dumps(sc))[:2])
print('D2-18',[(r['timestamp_utc'],r['customers_out'],r['cause']) for r in rows(O+'telemetry/outage_map.csv') if r['timestamp_utc'].startswith('2027-10-24') and r['area_id']=='AREA-NBH-FLOURBLUFF' and int(r['customers_out'])>0])
