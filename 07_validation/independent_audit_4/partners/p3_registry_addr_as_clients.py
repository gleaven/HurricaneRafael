import sys,re,collections; sys.path.insert(0,'.')
from common import *
g=json.load(open(ROOT+'/06_data_streams/gw_host_registry.json')); R=reg()
known={e['ip']:('gw external '+e['system_id']) for e in g['external_systems']}
for o in R['organisations']:
    for h in o['hosts']:
        if not h['ip'].startswith('10.'): known[h['ip']]=o['org_id']+' '+h['host_id']
    pb=o['address_plan'].get('public_block')
for n in ['aid_portal_access','base_logistics_access']:
    p=portal(n); x=p[p.client_ip.isin(known)]
    print(n,x.groupby(['client_ip','client_network']).agg(n=('event','size'),ev=('event',lambda s:dict(s.value_counts())),ua=('user_agent_family',lambda s:dict(s.value_counts()))).assign(who=lambda d:[known[i[0]] for i in d.index]).to_string())
a=load('auth'); r=a[a.logon_type=='remote']; x=r[r.src_ip.isin(known)]; print('partner remote sign-ons from registry/public addresses:',len(x), x.groupby(['org','src_ip']).size().to_dict())
f=load('firewall'); x=f[(f.src_zone.str.lower().isin(['internet','outside','untrust','wan']))&f.src_ip.isin(known)]; print('inbound fw from known addresses:',x.groupby(['org','src_ip','rule_name']).size().to_dict())
