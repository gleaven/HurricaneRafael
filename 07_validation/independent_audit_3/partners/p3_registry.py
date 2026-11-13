# registry referential integrity: hosts, ips, accounts
from lib import *
from collections import Counter,defaultdict
import ipaddress
R=reg()
orgmap={'city':'CITY','nascc':'NASCC','brw':'BRW','port':'PORT','srmc':'SRMC','bcmc':'BCMC','county':'COUNTY'}
for o in ORGS:
    O=[x for x in R['organisations'] if x['org_id']==orgmap[o]][0]
    hosts={h['host_id']:h for h in O['hosts']}
    ips={h['ip']:h for h in O['hosts'] if h.get('ip')}
    accts={a['account'] for a in O['accounts']}
    mbox={a['mailbox'] for a in O['accounts'] if a.get('mailbox')}
    internal=ipaddress.ip_network(O['address_plan']['internal'])
    print('=====',o,'hosts',len(hosts),'accounts',len(accts),'kinds',Counter(a['kind'] for a in O['accounts']),'devtypes',Counter(h['device_type'] for h in O['hosts']))
    print('  sites',[(s['site_id'],s['subnet']) for s in O['sites']])
    # dup ips
    c=Counter(h['ip'] for h in O['hosts'] if h.get('ip')); print('  dup ips',[k for k,v in c.items() if v>1][:5])
    # hosts outside site subnet
    sub={s['site_id']:ipaddress.ip_network(s['subnet']) for s in O['sites']}
    out=[(h['host_id'],h['ip'],h['site_id']) for h in O['hosts'] if h.get('ip') and h['ip'].startswith('10.') and ipaddress.ip_address(h['ip']) not in sub.get(h['site_id'],internal)]
    print('  hosts outside own site subnet',len(out),out[:8])
    def chk(kind,col,valid,norm=lambda x:x,skip=lambda r:False):
        h,rows=load(o,kind)
        bad=Counter(); 
        for r in rows:
            if skip(r): continue
            v=norm(r[col])
            if v not in valid: bad[v]+=1
        print(f'  {kind}.{col}: unknown distinct={len(bad)} rows={sum(bad.values())} ex={bad.most_common(6)}')
        return bad
    chk('firewall','device',hosts)
    b=chk('firewall','src_ip',ips,skip=lambda r:r['src_zone']=='internet')
    chk('web','client_ip',ips)
    chk('web','user',accts|{'-'})
    chk('dns','client_ip',ips)
    chk('dns','resolver',ips)
    chk('auth','host',hosts)
    chk('auth','account',accts,norm=lambda x:x.split('@')[0])
    chk('auth','src_ip',ips,skip=lambda r:r['src_network']!='internal')
    chk('mail','gateway',hosts)
    chk('mail','recipient',mbox,skip=lambda r:r['direction']=='outbound')
    chk('mail','sender',mbox,skip=lambda r:r['direction']=='inbound')
    chk('endpoint_alerts','host',hosts)
    chk('endpoint_alerts','ip',ips)
    # registry hosts never seen
    seen=set()
    for k,c in [('firewall','device'),('auth','host'),('endpoint_alerts','host'),('mail','gateway')]:
        seen|={r[c] for r in load(o,k)[1]}
    seenip=set()
    for k,c in [('firewall','src_ip'),('web','client_ip'),('dns','client_ip'),('dns','resolver'),('auth','src_ip'),('firewall','dst_ip')]:
        seenip|={r[c] for r in load(o,k)[1]}
    never=[h['host_id'] for h in O['hosts'] if h['host_id'] not in seen and h.get('ip') not in seenip]
    print('  registry hosts never in any log',len(never),never[:15])
    wsacc={a['account'] for a in O['accounts']}
    seenacc={r['account'].split('@')[0] for r in load(o,'auth')[1]}|{r['user'] for r in load(o,'web')[1]}|{r['recipient'].split('@')[0] for r in load(o,'mail')[1]}
    print('  registry accounts never in any log',len(wsacc-seenacc),list(wsacc-seenacc)[:10])
