import csv
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta,date
B=[r for r in csv.DictReader(open(ROOT+'/05_other_sources/maintenance/base_status_reports.csv')) if r['installation_id']=='FAC-DOD-01']
prev=None
for r in B:
    key=(r['flight_ops_status'],r['backup_power_status'],r['facility_status'],r['aircraft_on_station'])
    if key!=prev: print(r['report_date'],r['reported_utc'],key,r['remarks'][:110])
    prev=key
ext=pickle.load(open(HERE+'/cache/logistics_ext.pkl','rb'))
hf,f=load('nascc','firewall')
lp=[r for r in f if r['dst_ip']=='162.40.88.22']
print('fw rows to logistics public addr',len(lp),Counter((r['rule_name'],r['action']) for r in lp),'src /24',Counter('.'.join(r['src_ip'].split('.')[:3]) for r in lp if r['action']=='allow').most_common(4))
al=[r for r in lp if r['action']=='allow']
idx=defaultdict(list)
for r in al: idx[r['src_ip']].append(r)
miss=0;lags=[];used=set()
for e in ext:
    t=ts(e['time_utc'])
    c=[r for r in idx.get(e['client_ip'],[]) if -2<=(ts(r['time_utc'])-t).total_seconds()<=30 and id(r) not in used]
    if not c: miss+=1
    else: used.add(id(c[0])); lags.append((ts(c[0]['time_utc'])-t).total_seconds()-float(c[0]['duration_s']))
print('outside logistics requests',len(ext),'without fw session',miss,'| fw allow rows not tied to a request',len(al)-len(used))
import statistics as st
print(' fw start - request time: min %.1f med %.1f max %.1f'%(min(lags),st.median(lags),max(lags)))
nt=[r for r in al if id(r) not in used]
print(' untied allow rows: months',sorted(Counter(r['time_utc'][:7] for r in nt).items()),'src sample',[r['src_ip'] for r in nt[:5]],'dur max',max(float(r['duration_s']) for r in nt),'ext span',min(e['time_utc'] for e in ext),max(e['time_utc'] for e in ext),'distinct ext ips',len({e['client_ip'] for e in ext}))
print(' ext by day',sorted(Counter(e['time_utc'][:10] for e in ext).items()))
# power windows: gaps in auth+web per site around storm for nascc, city, county, port
R=reg()
for o in ['nascc','city','county','port']:
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]
    site={h['host_id']:h['site_id'] for h in O['hosts']}; ipsite={h['ip']:h['site_id'] for h in O['hosts']}
    ha,a=load(o,'auth'); hw,w=load(o,'web'); hd,d=load(o,'dns'); he,e=load(o,'endpoint_alerts')
    for s in [x['site_id'] for x in O['sites']]:
        ev=sorted([r['time_utc'] for r in a if site.get(r['host'])==s]+[r['time_utc'] for r in w if ipsite.get(r['client_ip'])==s]+[r['time_utc'] for r in d if ipsite.get(r['client_ip'])==s]+[r['time_utc'] for r in e if site.get(r['host'])==s and r['event']!='AGENT_HEARTBEAT_MISSED'])
        ev=[x for x in ev if '2027-09-10'<=x<='2027-11-01']
        gaps=sorted([((ts(ev[i+1])-ts(ev[i])).total_seconds()/3600,ev[i],ev[i+1]) for i in range(len(ev)-1)],reverse=True)[:2]
        print(f"  {o} {s}: largest silent gaps (h,from,to) {[(round(g,1),a_,b_) for g,a_,b_ in gaps]}")
    hb=[r for r in e if r['event']=='AGENT_HEARTBEAT_MISSED' and r['detail']]
    print('  ',o,'heartbeat-missed with last-seen:',len(hb),Counter(r['time_utc'][:10] for r in hb).most_common(4),'last seen min/max',min(r['detail'] for r in hb),max(r['detail'] for r in hb))
