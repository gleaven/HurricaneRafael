# containment of older extracts in partner logs; seam statistics
from lib import *
import csv
from collections import Counter,defaultdict
A=ROOT+"/05_other_sources/network_logs/audit/"
def rd(p):
    with open(p,newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
for name,org in [('mail_gateway_city.csv','city'),('mail_gateway_airstation.csv','nascc'),('mail_gateway_brightwake.csv','brw')]:
    old=rd(A+name); h,new=load(org,'mail')
    cols=list(old[0].keys())
    newset=Counter(tuple(r[c] for c in cols) for r in new)
    oldset=Counter(tuple(r[c] for c in cols) for r in old)
    missing=sum((oldset-newset).values())
    t0,t1=min(r['time_utc'] for r in old),max(r['time_utc'] for r in old)
    inwin=[r for r in new if t0<=r['time_utc']<=t1]
    extra=[r for r in inwin if tuple(r[c] for c in cols) not in oldset]
    print(f"== {name}: old rows {len(old)} window {t0}..{t1} missing-in-partner {missing}; partner rows in window {len(inwin)} of which not in extract {len(extra)}")
    print('   old cols',cols==h, 'old dirs',Counter(r['direction'] for r in old),'old sender_domains',Counter(r['sender_domain'] for r in old).most_common(5))
    print('   old verdict',Counter((r['sender_domain'],r['verdict'],r['action']) for r in old if r['sender_domain'] not in('partner-mail.example',)).most_common(8))
    # rate per day inside vs outside window
    days=Counter(r['time_utc'][:10] for r in new)
    ind=[v for d,v in days.items() if t0[:10]<=d<=t1[:10]]; outd=[v for d,v in days.items() if not(t0[:10]<=d<=t1[:10])]
    import statistics as st
    print('   rows/day in window mean %.1f (n=%d) ; outside mean %.1f (n=%d)'%(st.mean(ind),len(ind),st.mean(outd),len(outd)))
    # recipients distinct in vs out
    print('   distinct recipients in-window',len({r['recipient'] for r in inwin}),'outside',len({r['recipient'] for r in new if not (t0<=r['time_utc']<=t1)}))
    # message_id format
    import re
    print('   msgid formats old',Counter(re.sub(r'[0-9a-f]{16}','H16',r['message_id']) for r in old).most_common(4))
    print('   msgid formats new-outside',Counter(re.sub(r'[0-9a-f]{16}','H16',r['message_id']) for r in new if not (t0<=r['time_utc']<=t1)).most_common(4))
    print('   subj old',Counter(r['subject'] for r in old).most_common(12))
    print('   attach frac old',sum(1 for r in old if r['attachment_names'])/len(old),'new-outside',sum(1 for r in new if r['attachment_names'] and not (t0<=r['time_utc']<=t1))/max(1,sum(1 for r in new if not (t0<=r['time_utc']<=t1))))
    print('   spam frac old',sum(1 for r in old if r['verdict']=='spam')/len(old),'new-outside',sum(1 for r in new if r['verdict']=='spam' and not (t0<=r['time_utc']<=t1))/max(1,sum(1 for r in new if not (t0<=r['time_utc']<=t1))))
    print('   internal frac old',sum(1 for r in old if r['direction']=='internal')/len(old),'new-outside',sum(1 for r in new if r['direction']=='internal' and not (t0<=r['time_utc']<=t1))/max(1,sum(1 for r in new if not (t0<=r['time_utc']<=t1))))
# logons
old=rd(A+'account_logons_city_airstation.csv')
print('== logons old',len(old),min(r['time_utc'] for r in old),max(r['time_utc'] for r in old),Counter(r['service'] for r in old),Counter(r['src_network'] for r in old))
for svc,org,host in [('city single sign-on','city','CC-SSO-01'),('base webmail','nascc','NASCC-OWA-01')]:
    o=[r for r in old if r['service']==svc]; h,new=load(org,'auth')
    new=[r for r in new if r['host']==host]
    key=lambda r:(r['time_utc'],r['account'],r['src_ip'],r['src_network'],r['result'],r['auth_method'],r['device'])
    ns=Counter(key(r) for r in new); os_=Counter(key(r) for r in o)
    t0,t1=min(r['time_utc'] for r in o),max(r['time_utc'] for r in o)
    inwin=[r for r in new if t0<=r['time_utc']<=t1]
    print(f"  {svc}: old {len(o)} missing {sum((os_-ns).values())} window {t0}..{t1}; partner in-window {len(inwin)} not-in-extract {sum(1 for r in inwin if key(r) not in os_)}")
    days=Counter(r['time_utc'][:10] for r in new)
    ind=[v for d,v in days.items() if t0[:10]<=d<=t1[:10]]; outd=[v for d,v in days.items() if not(t0[:10]<=d<=t1[:10])]
    import statistics as st
    print('   remote logons/day in window mean %.1f (n=%d); outside mean %.1f (n=%d)'%(st.mean(ind),len(ind),st.mean(outd),len(outd)))
    print('   src_network in-window',Counter(r['src_network'] for r in inwin).most_common(),'\n   outside',Counter(r['src_network'] for r in new if not (t0<=r['time_utc']<=t1)).most_common())
    print('   by day around window',[(d,days[d]) for d in sorted(days) if '2027-09-08'<=d<='2027-09-24'])
for f in ['mail_url_clicks_city_airstation.csv','mail_url_clicks_brightwake.csv']:
    for r in rd(A+f): print('  click',r)
