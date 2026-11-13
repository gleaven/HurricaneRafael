from lib import *
from collections import Counter,defaultdict
h,fw=load('brw','firewall')
dmz=[r for r in fw if r['device']=='BRW-FW-DMZ-01']
print('DMZ rows',len(dmz), Counter(r['action'] for r in dmz), Counter(r['rule_name'] for r in dmz), Counter(r['dst_ip'] for r in dmz), Counter(r['dst_port'] for r in dmz),Counter(r['src_zone'] for r in dmz))
def cls(ip):
    p=ip.split('.')
    if ip.startswith('198.51.100.'):
        n=int(p[3]); return 'office_nat' if 10<=n<=59 else ('vpn_egress' if 128<=n<=191 else 'brw_other')
    if ip.startswith('203.0.113.'): return 'testnet3'
    if ip.startswith('192.0.2.'): return 'testnet1'
    return 'other:'+p[0]
c=Counter(cls(r['src_ip']) for r in dmz); print(c)
for k in c:
    rr=[r for r in dmz if cls(r['src_ip'])==k]
    print('==',k,len(rr),'months',sorted(Counter(r['time_utc'][:7] for r in rr).items()))
    print('   distinct src',len(set(r['src_ip'] for r in rr)),Counter(r['src_ip'] for r in rr).most_common(5))
    import statistics as st
    d=[float(r['duration_s']) for r in rr]
    print('   dur med',st.median(d),'min',min(d),'max',max(d),'bytes_sent med',st.median(int(r['bytes_sent']) for r in rr),'recv med',st.median(int(r['bytes_recv']) for r in rr))
    print('   end',Counter(r['session_end_reason'] for r in rr),'app',Counter(r['app'] for r in rr))
    hours=Counter(int(r['time_utc'][11:13]) for r in rr); print('   end-hours utc',sorted(hours.items()))
    wd=Counter(ts(r['time_utc']).weekday() for r in rr); print('   weekday',sorted(wd.items()))
    for r in rr[:3]: print('   ',[r[c] for c in h])
# vpn zone rows
print('--- vpn zone')
for r in fw:
    if r['src_zone']=='vpn': print([r[c] for c in h])
# edge fw outbound to 192.0.2.70
out=[r for r in fw if r['dst_ip']=='192.0.2.70' and r['device']=='BRW-FW-EDGE-01']
print('edge->gw',len(out)); 
for r in out[:5]: print([r[c] for c in h])
print(Counter(r['src_ip'] for r in out).most_common(12))
