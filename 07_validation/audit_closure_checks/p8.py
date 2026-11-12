import csv,glob,json,re,collections,os,sys,math,statistics,itertools
from datetime import datetime,timedelta,timezone
O='05_other_sources/'
def rows(p):
    with open(p,encoding='utf-8',newline='') as f: yield from csv.DictReader(f)
C=collections.Counter
# D2-16 portal
ev=C(); early=0; fail_bytes=C(); fail_ip=C(); ua=C(); fail_existing=0; created=set(); views=0; reg=0; bl=C(); guess=0; first_created=None
for f in sorted(glob.glob(O+'network_logs/portal/aid_portal_access_*.csv')):
    for r in rows(f):
        e=r['event'].split(':')[0]; ev[e]+=1
        if e=='account_created':
            created.add(r['account_ref'])
            if first_created is None or r['time_utc']<first_created: first_created=r['time_utc']
            if r['time_utc']<'2027-11-13T06:00': early+=1
        if e=='login_failed':
            fail_bytes[r['bytes']]+=1; fail_ip[r['client_ip']]+=1
            if r['account_ref'] in created: fail_existing+=1
            if r['account_ref'].lower().startswith('guess'): guess+=1
        ua[r['user_agent_family']]+=1
for f in sorted(glob.glob(O+'network_logs/portal/base_logistics_access_*.csv')):
    for r in rows(f): bl[r['event'].split(':')[0]]+=1
print('D2-16 events',ev.most_common(10)); print('  account_created before 06:00Z 13 Nov',early,'first',first_created,'failed logins',ev['login_failed'],'distinct sizes',len(fail_bytes),'per-address min/max',min(fail_ip.values()),max(fail_ip.values()),'addresses',len(fail_ip),'failures against existing accounts',fail_existing,'guess- ids',guess)
print('  browser families',ua.most_common(9)); print('  base logistics events',bl.most_common(6))
# D2-19 / D2-20 aid
aid=list(rows(O+'payments/aid_applications.csv')); dis=[r for r in aid if r['record_type']=='disbursement']
ring_acc=C(r['deposit_account_masked'] for r in dis).most_common(4); print('D2-19 top deposit accounts',ring_acc)
top={a for a,_ in ring_acc[:3]}; tot=sum(float(r['amount_usd']) for r in dis if r['deposit_account_masked'] in top); cnt=sum(1 for r in dis if r['deposit_account_masked'] in top)
ft=list(rows(O+'payments/financial_transactions.csv')); cr=[r for r in ft if re.search('FEMA|disaster assist|IHP',r['description']+r['counterparty_name'],re.I) and r['direction'].lower().startswith('c')]
byacc=C(); 
print('  aid file: disbursements to 3 top accounts',cnt,round(tot,2),'bank file FEMA credits',len(cr),round(sum(float(r['amount_usd']) for r in cr),2),'samples',C(r['counterparty_name'] for r in cr).most_common(3))
st=C(r['status'] for r in aid); print('D2-20 statuses',st.most_common(8)); fl=C(re.findall(r'SA-\d{4}-TX-\d+',r['status'])[0] for r in aid if 'SA-' in r['status']); print('  flag numbers',len(fl),fl.most_common(4)); 
flt=C(r['changed_utc'] or r['event_utc'] for r in aid if 'SA-2027-TX-4471' in r['status']); print('  4471 timestamps',len(flt),flt.most_common(2))
print('A1-16 applications submitted before 2027-11-13T06:00Z',sum(1 for r in aid if r['record_type']=='application' and r['submitted_utc'] and r['submitted_utc']<'2027-11-13T06:00'),'first',min(r['submitted_utc'] for r in aid if r['record_type']=='application' and r['submitted_utc']))
ph=0; phf=0; tot=0; first=C(); wsafe=[]
for f in sorted(glob.glob(O+'911/cad_incidents_*.csv')):
    for r in rows(f):
        tot+=1
        if re.search(r'IN DANGER NOW',r['narrative']): ph+=1; phf+= (r['disposition_code'] in('UNF','UNFOUNDED','NOFIND') or 'unfound' in r['disposition_desc'].lower() or 'no find' in r['disposition_desc'].lower())
        nc=r['nature_code']
        if nc not in first or r['call_received_dttm']<first[nc]: first[nc]=r['call_received_dttm']
print('D2-20 CAD rows',tot,'"IN DANGER NOW" narratives',ph,'of which unfounded/no-find',phf)
print('A1-4 first dates',{k:first[k][:16] for k in ('CURFEWVIO','WATERRESC','ROOFCOLLAP','SHELTERREQ','WATERSAFE','EXPLOSION') if k in first}, [k for k in first if 'EXPL' in k or 'WATER' in k])
ex=[r for f in [O+'911/cad_incidents_2027-10.csv'] for r in rows(f) if 'EXPL' in r['nature_code'] and r['call_received_dttm'].startswith('2027-10-28')]; print('D2-14 CAD explosion calls 10-28',len(ex),C((r['disposition_code'],r['transport_destination']) for r in ex).most_common(5))
tr=[r for r in rows(O+'911/cad_incidents_2027-10.csv') if r['call_received_dttm'].startswith('2027-10-28') and r['transport_destination'] and re.search('burn|tug|explos|blast',r['narrative'],re.I)]; print('  CAD 10-28 transports with burn/tug/blast narrative',[(r['call_received_dttm'],r['nature_code'],r['transport_destination']) for r in tr][:4])
fr=[r for r in rows(O+'911/cad_incidents_2027-09.csv') if r['call_received_dttm'].startswith('2027-09-21') and (r['disposition_code'] in('UNF','NOFIND') or 'no find' in r['disposition_desc'].lower() or 'unfounded' in r['disposition_desc'].lower()) and 'RESC' in r['nature_code']]; print('A1-8 unfounded rescue calls on 09-21: n',len(fr),'first/last',min((r['call_received_dttm'] for r in fr),default=''),max((r['call_received_dttm'] for r in fr),default=''),'(local or UTC as written)')
# D2-24 contracts
aw={r['piid']:float(r['value_usd']) for r in rows(O+'payments/contracts_awards.csv')}; inv=C()
for r in rows(O+'payments/contracts_invoices.csv'): inv[r['piid']]+=float(r['amount_usd'])
over=sorted(((round(inv[p]/aw[p],2),p) for p in inv if p in aw and aw[p] and inv[p]/aw[p]>1.1),reverse=True); print('D2-24 awards invoiced >1.1x value',over[:8])
print('  port_surveillance README mentions generator script:', 'gen_maritime' in open(O+'port_surveillance/README.md',encoding='utf-8').read() if os.path.exists(O+'port_surveillance/README.md') else 'no README')
c=json.load(open('06_data_streams/stream_catalog.json')); print('  catalogue streams',len(c['streams']),'path_glob null',[(s['stream_id'],s.get('status') or s.get('delivered')) for s in c['streams'] if not s.get('path_glob')])
sm=list(rows(O+'network_logs/siem/daily_summary.csv')); print('D2-23 SIEM open_ml_anomaly_alerts Oct 12-22',[(r['date_utc'][5:],r['open_ml_anomaly_alerts']) for r in sm if '2027-10-12'<=r['date_utc']<='2027-10-22'])
fl=list(rows(O+'drone_video/logs/flight_log.csv')); ar=sorted(r['takeoff_utc'] for r in fl if 'Argus' in r['drone_model'] and r['takeoff_utc'].startswith('2027-09-18')); print('  Argus launches 09-18',ar[:9])
