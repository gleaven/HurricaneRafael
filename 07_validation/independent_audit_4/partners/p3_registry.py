# Pass 3: ids against the registry
import sys,re,ipaddress; sys.path.insert(0,'.')
from common import *
r=reg(); key={'CITY':'city','NASCC':'nascc','BRW':'brw','PORT':'port','SRMC':'srmc','BCMC':'bcmc','COUNTY':'county'}
print([o['org_id'] for o in r['organisations']])
for o in r['organisations']:
    k=[x for x in ORGS if x.upper()==o['org_id'].upper() or o['org_id'].upper().startswith(x.upper())]
    k=k[0] if k else {'PCCA':'port','NUECES':'county'}.get(o['org_id'],o['org_id'].lower())
    hosts={h['host_id']:h for h in o['hosts']}; ips={h['ip']:h for h in o['hosts']}
    accts={a['account'] for a in o['accounts']}; mboxes={a.get('mailbox') for a in o['accounts']}
    dom=o['domain']
    print('\n====',o['org_id'],k,'hosts',len(hosts),'accounts',len(accts),'sites',len(o['sites']), 'ws users', sum(a.get('workstation_user',False) for a in o['accounts']))
    import collections
    print(' device types',dict(collections.Counter(h['device_type'] for h in o['hosts'])), 'os',dict(collections.Counter(h['os'] for h in o['hosts'])))
    a=load('auth',[k]); 
    print(' auth hosts not in reg:', sorted(set(a.host)-set(hosts))[:10])
    ac=a.account.str.replace('@'+dom,'',regex=False)
    miss=set(ac)-accts; print(' auth accounts not in reg:',len(miss),sorted(miss)[:8], 'rows',ac.isin(miss).sum())
    ws=a[a.logon_type!='remote']; 
    # ws account is a registered user of the host?
    hu={h['host_id']:set(h.get('users',[])) for h in o['hosts']}
    acw=ws.account.str.replace('@'+dom,'',regex=False)
    bad=[(h,u) for h,u in zip(ws.host,acw) if u not in hu.get(h,set())]
    print(' ws logons by account not listed on host:',len(bad),'of',len(ws), collections.Counter(bad).most_common(5))
    print(' ws src_ip values:', ws.src_ip.value_counts().head(3).to_dict())
    w=load('web',[k]); print(' web client_ip not in reg:',len(set(w.client_ip)-set(ips)), sorted(set(w.client_ip)-set(ips))[:6], ' users not in reg:',sorted(set(w.user)-accts-{'-'})[:6])
    d=load('dns',[k]); print(' dns client not in reg:',len(set(d.client_ip)-set(ips)),sorted(set(d.client_ip)-set(ips))[:6],' resolver not in reg:',set(d.resolver)-set(ips), d.resolver.value_counts().to_dict())
    e=load('endpoint_alerts',[k]); print(' ep hosts not in reg:',set(e.host)-set(hosts),' ip mismatch:',sum(hosts[h]['ip']!=i for h,i in zip(e.host,e.ip) if h in hosts),' initiated_by not in reg:',sorted(set(e.initiated_by)-accts-{'system'})[:6])
    m=load('mail',[k]); own=pd.concat([m.sender[m.sender_domain==dom], m.recipient[m.recipient.str.endswith('@'+dom)]])
    print(' mail gateway:',set(m.gateway),'in reg',set(m.gateway)<=set(hosts),' own mailboxes not in reg:',len(set(own)-mboxes),sorted(set(own)-mboxes)[:6], 'of',own.nunique())
    f=load('firewall',[k]); print(' fw device not in reg:',set(f.device)-set(hosts))
    inn=ipaddress.ip_network(o['address_plan']['internal'])
    src_int=f[f.src_ip.str.startswith('10.')]; print(' fw internal src not in reg:',len(set(src_int.src_ip)-set(ips)),sorted(set(src_int.src_ip)-set(ips))[:6])
    print(' nat_src_ip:',f.nat_src_ip.value_counts().head(8).to_dict(), 'plan',o['address_plan'])
