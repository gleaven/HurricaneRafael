import csv
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
E=list(csv.DictReader(open(ROOT+'/05_other_sources/public_health/eas_broadcasts.csv')))
print('eas rows',len(E),Counter(r['AlertSource'] for r in E))
src_org={'NCOEM':'county','CCOEM':'city','Corpus Christi Water Department':'city'}
R=reg()
for o in ['county','city']:
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]
    alerthosts=[h for h in O['hosts'] if 'lert' in h['role'] or 'ALERT' in h['host_id']]
    print(o,'alert hosts',[(h['host_id'],h['ip'],h['role'],h.get('users')) for h in alerthosts])
    hw,w=load(o,'web'); hf,f=load(o,'firewall'); hd,d=load(o,'dns'); ha,a=load(o,'auth')
    ow=[r for r in w if r['host']=='origination.alertgateway.example']
    print(' web rows to origination service',len(ow),'clients',Counter(r['client_ip'] for r in ow),'users',Counter(r['user'] for r in ow))
    used=set()
    for e in E:
        if src_org.get(e['AlertSource'])!=o: continue
        times=[('issue',e['IssuedAt_UTC'])]
        if e['WEA_Sent_ES'] and e['WEA_Sent_ES'] not in (e['IssuedAt_UTC'],e['WEA_Sent_EN'],'') : times.append(('wea_es',e['WEA_Sent_ES']))
        for lab,t in times:
            try: tt=ts(t)
            except Exception as ex: print('  bad time',e['AlertID'],lab,t); continue
            c=[r for r in ow if timedelta(seconds=0)<=tt-ts(r['time_utc'])<=timedelta(seconds=60)]
            lead=[(tt-ts(r['time_utc'])).total_seconds() for r in c]
            for r in c: used.add(id(r))
            # logged on?
            lg='-'
            if c:
                hn=[h for h in O['hosts'] if h['ip']==c[0]['client_ip']][0]['host_id']
                ev=[x for x in a if x['host']==hn and x['time_utc']<=c[0]['time_utc']]
                last=ev[-1] if ev else None
                lg=f"{hn} last auth ev before: {last['event_id'] if last else None} {last['account'] if last else ''} user={c[0]['user']}"
            print(f"  {e['AlertID']:22s} {e['AlertSource']:6s} {lab:6s} {t} web rows in 60s before: {len(c)} lead {lead} {lg}")
    print(' origination web rows not tied to an alert:',[(r['time_utc'],r['client_ip']) for r in ow if id(r) not in used])
print('other sources not mapped:',Counter(r['AlertSource'] for r in E if r['AlertSource'] not in src_org))
print('WEA cols sample',[(e['AlertID'],e['IssuedAt_UTC'],e['ReleasedAt_EN'],e['ReleasedAt_ES'],e['WEA_Sent_EN'],e['WEA_Sent_ES']) for e in E if e['AlertSource'] in src_org][:6])
# translation jobs
T=list(csv.DictReader(open(ROOT+'/05_other_sources/broadcast/translation_jobs.csv')))
hm,m=load('county','mail')
tm=[r for r in m if r['subject'].startswith('Translation')]
for t in T:
    rq=[r for r in tm if r['subject']=='Translation request '+t['job_id']]; dl=[r for r in tm if r['subject']=='Translation delivered '+t['job_id']]
    print(t['job_id'],t['status'],'recv',t['source_received_utc'],'deliv',t['translation_delivered_utc'],'| mail req',[(r['time_utc'],r['direction'],r['sender'],r['recipient']) for r in rq],'| mail deliv',[(r['time_utc'],r['direction'],r['sender'],r['recipient']) for r in dl])
