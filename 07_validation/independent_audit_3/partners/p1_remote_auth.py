from lib import *
from collections import Counter,defaultdict
for o in ORGS:
    h,a=load(o,'auth')
    rem=[r for r in a if r['logon_type']=='remote']
    c=Counter((r['result'],r['auth_method'],r['device']) for r in rem)
    print('==',o,len(rem)); 
    for k,v in sorted(c.items()): print('    ',k,v)
    sp=[r for r in rem if r['result']=='SUCCESS' and r['auth_method']=='password']
    print('   SUCCESS+password remote:',len(sp),Counter(r['src_network'] for r in sp))
    # per account: number of distinct networks; ips per account
    acc=defaultdict(set); accip=defaultdict(Counter)
    for r in rem: acc[r['account']].add(r['src_network']); accip[r['account']][r['src_ip']]+=1
    print('   accounts',len(acc),'networks per account',sorted(Counter(len(v) for v in acc.values()).items()))
    reuse=[max(c.values())/sum(c.values()) for c in accip.values() if sum(c.values())>=10]
    import statistics as st
    print('   share of an account\'s remote sign-ons from its most-used IP (accounts with >=10): median %.2f'%st.median(reuse) if reuse else '', '| distinct ips',len({r['src_ip'] for r in rem}),'of',len(rem),'rows')
    # failed followed by success within 5 min same account?
    # ip -> asn consistency
    ipasn=defaultdict(set)
    for r in rem: ipasn[r['src_ip']].add(r['src_network'])
    print('   ips with >1 network label',sum(1 for v in ipasn.values() if len(v)>1))
    # first-octet vs ASN
    fo=defaultdict(Counter)
    for r in rem: fo[r['src_network']][r['src_ip'].split('.')[0]]+=1
    print('   first octets per ASN', {k:len(v) for k,v in fo.items()}, 'overlap of octet sets between ASNs:', len(set.intersection(*[set(v) for v in fo.values()])) )
    # fw inbound match
    hf,f=load(o,'firewall')
    inb=defaultdict(list)
    for r in f:
        if r['rule_name']=='inbound-remote-access': inb[r['src_ip']].append(ts(r['time_utc']))
    nofw=sum(1 for r in rem if not any(-5<=(t-ts(r['time_utc'])).total_seconds()<=120 for t in inb.get(r['src_ip'],[])))
    print('   remote sign-ons without inbound fw session within 120s:',nofw,'| inbound-remote-access fw rows',sum(len(v) for v in inb.values()))
