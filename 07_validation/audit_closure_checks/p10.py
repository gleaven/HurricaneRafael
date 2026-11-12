import csv,glob,json,re,collections,os,sys,math,statistics,datetime
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
# A1-1 author notes
n=0;hits=[]
for f in glob.glob(O+'press_releases/*.jsonl'):
    for ln in open(f,encoding='utf-8'):
        n+=1
        m=re.search(r'scenario|placeholder|fictional|hackathon|answer key|synthetic(?! aperture)',ln,re.I)
        if m: hits.append((json.loads(ln).get('record_id') or json.loads(ln).get('id'),m.group(0)))
        o=json.loads(ln)
        if (o.get('record_id') or o.get('id'))=='PUB-024': print('A1-14 PUB-024 names Rendal:', 'Rendal' in ln, o.get('date_local'))
print('A1-1 press statements',n,'author-note hits',hits)
pr=json.load(open('02_public_record/public_record.json')); s=json.dumps(pr); print('  public_record author-note hits',len(re.findall(r"this scenario|scenario value|the scenario ends",s)))
print('A1-3 rule_changes',[(r['time_utc'],r['description'][:90]) for r in rows(O+'network_logs/siem/rule_changes.csv') if r['time_utc'].startswith('2027-10-18')])
ic=list(rows(O+'payments/insurance_claims.csv')); k=[c for c in ic[0].keys() if 'status' in c.lower()]; print('A1-5 claim status cols',k); 
for c in k: print('  ',c,C(r[c] for r in ic).most_common(8))
# A1-12 ASN notation
forms=C()
for f,cols in ((O+'telemetry/vessel_cargo_control_remote_sessions.csv',['src_asn']),(O+'network_logs/audit/remote_access_sessions.csv',['src_network']),(O+'payments/aid_applications.csv',['source_asn']),(O+'network_logs/portal/aid_portal_access_2027-11.csv',['client_network']),(O+'network_logs/audit/account_logons_city_airstation.csv',['src_network'])):
    for i,r in enumerate(rows(f)):
        if i>60000: break
        for c in cols:
            v=r[c]
            if re.search(r'\d',v): forms[(os.path.basename(f)[:22],re.sub(r'\d+','N',v))]+=1
print('A1-12 ASN notations',forms.most_common(12))
# A1-7 bot vs map: sample
om=collections.defaultdict(int)
for r in rows(O+'telemetry/outage_map.csv'): om[r['timestamp_utc'][:16]]+=int(r['customers_out'])
bot=[f for f in glob.glob(O+'social_media/*.jsonl') if re.search('outage|CBPWA',os.path.basename(f),re.I)]; print('A1-7 bot files',[os.path.basename(b) for b in bot][:5])
# A1-10 telemetry loss D0..D+3
q=C(); 
for f in glob.glob(O+'telemetry/historian_SUB*_202709.csv')[:1]:
    for r in rows(f):
        t=r['Timestamp'].replace(' ','T')
        if '2027-09-14T06'<=t<'2027-09-18T00': q[r['Quality']]+=1
    print('A1-10',os.path.basename(f),'quality D0..D+3',q.most_common(5))
# A1-15 health
sr=[r for r in rows(O+'public_health/ed_visits_FAC-SRMC-001.csv') if '2027-09-14T06:00'<=r['Arrive_Date_Time']<'2027-09-14T18:00']; print('A1-15 SRMC arrivals first 12 h after landfall',len(sr))
# A1-16 spill claims window
sp=[r for r in ic if re.search('spill|oil|OPA',r.get('claim_program','')+r.get('loss_cause',''),re.I) and r['record_type'].lower().startswith('claim')]
print('A1-16 spill claims',len(sp),'filed range',min((r['filed_date'] for r in sp),default=''),max((r['filed_date'] for r in sp),default=''),'in 2027-11-13..12-12',sum(1 for r in sp if '2027-11-13'<=r['filed_date']<='2027-12-12'),C(r['claim_program'] for r in ic).most_common(5))
# A1-17 AVL scatter
import itertools
f=sorted(glob.glob(O+'avl/avl_2027-09_*.csv'))[0]; st=C(); 
for i,r in enumerate(rows(f)):
    if i>200000: break
    st[r['status']]+=1
print('A1-17 AVL statuses',st.most_common(6))
print('A1-18 adsb first ts',datetime.datetime.utcfromtimestamp(int(next(rows(sorted(glob.glob(O+'adsb/adsb_*.csv'))[0]))['time_position'])))
v=json.load(open('06_data_streams/vessels.json')); L=v if isinstance(v,list) else next(x for x in v.values() if isinstance(x,list)); print('  Halcyon Drift deep_draft',[x.get('deep_draft') for x in L if 'HALCYON' in json.dumps(x).upper()][:2])
cu=json.load(open('06_data_streams/cad_units.json')); print('  cad_units d0_date present','d0_date' in json.dumps(cu))
print('  shift log CORPUS RETAINED',sum(1 for r in rows(O+'911/reports/cbecc_shift_log.csv') if 'CORPUS' in r['entry'].upper() and 'TRAINING' in r['entry'].upper()))
ea=list(rows(O+'public_health/eas_broadcasts.csv')); print('  EAS cols',[c for c in ea[0].keys() if 'Char' in c], [(r.get('AlertID') or r.get('alert_id'), r.get('CharCount_EN'), len(r.get('Headline_EN','') or r.get('headline_en',''))) for r in ea if 'BWW-2027-0926' in json.dumps(r)][:2])
print('  canon cites SUP-0388/0390',len(re.findall('SUP-0388|SUP-0390',open('00_scenario/canon_timeline.json').read())))
print('  feeder ids not in registry: outage feeders',len({r['feeder_id'] for r in rows(O+'telemetry/outage_map.csv')}))
