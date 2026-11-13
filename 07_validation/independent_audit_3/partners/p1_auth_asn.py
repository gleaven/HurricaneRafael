from lib import *
from collections import Counter,defaultdict
for o in ['city','nascc']:
    h,rows=load(o,'auth')
    print('=====',o)
    for r in rows:
        if r['src_network']=='ASN 64512': print(r['_f'],r['_n'],[r[c] for c in h])
    for asn in ['ASN 64503','ASN 64496','ASN 64510','ASN 22773']:
        rr=[r for r in rows if r['src_network']==asn]
        months=Counter(r['time_utc'][:7] for r in rr)
        print(asn,len(rr),sorted(months.items()))
        print('  result',Counter(r['result'] for r in rr),'method',Counter(r['auth_method'] for r in rr),'device',Counter(r['device'] for r in rr))
        print('  ip prefixes',Counter('.'.join(r['src_ip'].split('.')[:2]) for r in rr).most_common(8))
        print('  distinct accounts',len(set(r['account'] for r in rr)), 'acct fmt', Counter('@' in r['account'] for r in rr))
