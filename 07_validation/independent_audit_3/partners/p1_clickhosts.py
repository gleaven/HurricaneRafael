from lib import *
from collections import Counter,defaultdict
from datetime import timedelta
import csv
A=ROOT+"/05_other_sources/network_logs/audit/"
clicks=list(csv.DictReader(open(A+'mail_url_clicks_city_airstation.csv')))
R=reg()
for o in ['city','nascc']:
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]
    nine=[h for h in O['hosts'] if '-WS-9' in h['host_id']]
    ha,a=load(o,'auth'); hw,w=load(o,'web'); hd,d=load(o,'dns'); he,e=load(o,'endpoint_alerts'); hm,m=load(o,'mail'); hf,f=load(o,'firewall')
    print('==',o)
    norm=[h for h in O['hosts'] if h['device_type']=='workstation' and '-WS-9' not in h['host_id']]
    import statistics as st
    def cnt(h):
        return (sum(1 for r in a if r['host']==h['host_id'] and r['event_id']=='4624'),sum(1 for r in w if r['client_ip']==h['ip']),sum(1 for r in d if r['client_ip']==h['ip']),sum(1 for r in e if r['host']==h['host_id']))
    nc=[cnt(h) for h in norm]
    print('  ordinary single-user workstations: median (logons, web, dns, endpoint) =',tuple(st.median(x[i] for x in nc) for i in range(4)))
    for h in nine:
        u=h['users'][0]
        lg=[r for r in a if r['host']==h['host_id'] and r['event_id']=='4624']
        hrs=Counter((ts(r['time_utc']).hour-5)%24 for r in lg)
        lures=[r['time_utc'] for r in m if r['recipient'].startswith(u+'@') and r['sender_domain']=='aid-help-portal.example']
        ck=[c for c in clicks if c['client_ip']==h['ip']][0]
        days=sorted({r['time_utc'][:10] for r in lg})
        print(f"  {h['host_id']} {h['ip']} user {u}: (logons,web,dns,endpoint)={cnt(h)} logon days {days[0] if days else None}..{days[-1] if days else None} n={len(days)}; local logon hours {sorted(hrs.items())}; lures to user total {len(lures)} before click {sum(1 for t in lures if t<=ck['time_utc'])}")
    # odd-hour logons overall
    odd=[r for r in a if r['event_id']=='4624' and r['logon_type']=='2' and (ts(r['time_utc']).hour-5)%24 in (10,11,12,13,14,15,16,20,21,22,23,0,1,2,3,4)]
    print('  workstation logons outside 05-09 / 17-19 local (CDT):',len(odd),'hosts',Counter(r['host'] for r in odd).most_common(12))
