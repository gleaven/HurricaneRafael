# Pass 2 item 8: partner logs vs portal logs, both directions
import sys,re,collections; sys.path.insert(0,'.')
from common import *
w=load('web'); f=load('firewall'); d=load('dns')
ap=portal('aid_portal_access'); bl=portal('base_logistics_access')
R=reg()
g=json.load(open(ROOT+'/06_data_streams/gw_host_registry.json'))
ext={e['system_id']:e for e in g['external_systems']}
print({k:(v['hostname'],v['ip']) for k,v in ext.items()})
print('partner web hosts matching aid|disaster|fema|logistic|log02:'); x=w[w.host.str.contains('disasteraid|fema|log02|nascc')]
print(x.groupby(['org','host']).size().to_string())
print('partner dns for those:'); y=d[d['query'].str.contains('disasteraid|log02')]; print(y.groupby(['org','query','answer']).size().to_string())
pubs={'city':'64.134.20.','nascc':'162.40.88.','port':'69.15.201.','srmc':'96.88.14.','bcmc':'104.190.33.','county':'199.21.76.','brw':'198.51.100.'}
for o,p in pubs.items():
    print(o,'aid portal rows from its public block:',ap.client_ip.str.startswith(p).sum(),'| logistics rows:',bl.client_ip.str.startswith(p).sum())
# any firewall session to the aid portal address
print('fw sessions to 192.0.2.130:',(f.dst_ip=='192.0.2.130').sum())
# NASCC fw <-> logistics log
fn=f[(f.org=='nascc')&(f.dst_ip=='162.40.88.22')].copy(); fn['te']=ts(fn).astype('int64')//10**9; fn['t0']=fn.te-fn.duration_s.astype(float)
ob=bl[bl.client_network!='base network'].copy(); ob['t']=ts(ob).astype('int64')//10**9
print('fw sessions to logistics public addr:',len(fn),'| logistics rows from outside:',len(ob))
fi=collections.defaultdict(list)
for s,t0,te in zip(fn.src_ip,fn.t0,fn.te): fi[s].append((t0,te))
miss=0; 
for c,t in zip(ob.client_ip,ob.t):
    if not any(a-3<=t<=b+3 for a,b in fi.get(c,[])): miss+=1
print('outside logistics rows without a firewall session covering them:',miss)
oi=collections.defaultdict(list)
for c,t in zip(ob.client_ip,ob.t): oi[c].append(t)
miss2=sum(1 for s,t0,te in zip(fn.src_ip,fn.t0,fn.te) if not any(t0-3<=t<=te+3 for t in oi.get(s,[])))
print('firewall sessions to logistics without a logistics row:',miss2)
# base network rows: 10.200.x: appear anywhere in nascc logs?
print('logistics base-network client /16:',bl[bl.client_network=='base network'].client_ip.str.split('.').str[:2].str.join('.').value_counts().to_dict())
print('nascc fw src in 10.200:',f[(f.org=='nascc')&f.src_ip.str.startswith('10.200.')].shape[0])
# accounts in logistics log vs nascc registry
na=[o for o in R['organisations'] if o['org_id']=='NASCC'][0]
accts={a['account'] for a in na['accounts']}
refs=set(bl.account_ref)-{''}; print('logistics account_ref count',len(refs),'sample',sorted(refs)[:5],' in nascc registry:',len(refs&accts), 'in gw users?')
print('logistics scan rows',(bl.client_network=='ASN 64512').sum(), bl[bl.client_network=='ASN 64512'].time_utc.agg(['min','max']).tolist(), 'login_success from outside:',((bl.client_network!='base network')&(bl.event=='login_success')).sum())
print('scan account_refs:',bl[(bl.client_network=='ASN 64512')&(bl.account_ref!='')].account_ref.value_counts().head(12).to_dict())
print('aid scan account_refs:',ap[(ap.client_network=='ASN 64512')&(ap.time_utc<'2027-09')&(ap.account_ref!='')].account_ref.value_counts().head(12).to_dict())
