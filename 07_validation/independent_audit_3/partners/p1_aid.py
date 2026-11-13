from lib import *
from collections import Counter,defaultdict
for o in ORGS:
    for k,c in [('web','host'),('dns','query')]:
        h,rows=load(o,k)
        rr=[r for r in rows if 'aid-help' in r[c] or 'marine-cert' in r[c]]
        print('==',o,k,len(rr))
        for r in rr: print('   ',r['_f'],r['_n'],[r[x] for x in h])
    h,rows=load(o,'firewall')
    # firewall rows from 203.0.113 or to resolved IPs
    rr=[r for r in rows if r['src_ip'].startswith('203.0.113.') or r['dst_ip'].startswith('203.0.113.') or r['dst_ip'] in('151.231.48.240','52.84.165.220')]
    print('==',o,'fw testnet3/aidip',len(rr))
    for r in rr[:40]: print('   ',r['_f'],r['_n'],[r[x] for x in h])
    for k in ['web','dns','auth','mail','endpoint_alerts']:
        h,rows=load(o,k)
        n=sum(1 for r in rows if any(('203.0.113.' in str(v)) or ('198.51.100.' in str(v) and o!='brw') or ('192.0.2.' in str(v) and o!='brw') for kk,v in r.items() if kk not in('_f','_n')))
        print('   docrange hits',o,k,n)
