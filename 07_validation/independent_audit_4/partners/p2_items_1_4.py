# Pass 2: re-test items 1-4 of audit 3
import sys,re,ipaddress,collections; sys.path.insert(0,'.')
from common import *
AUD=ROOT+'/05_other_sources/network_logs/audit/'
print('===== ITEM 1: address range / label only on hostile records')
a=load('auth'); r=a[a.logon_type=='remote']
print('auth rows with ASN 64512:',(r.src_network=='ASN 64512').sum(),' 203.0.113.x:',r.src_ip.str.startswith('203.0.113.').sum())
low=r[r.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$')]
print('auth rows 203.0.113.0-99:',len(low),'accounts',low.account.nunique(),'| methods',low.auth_method.value_counts().to_dict(),'| device',low.device.value_counts().to_dict())
hi=r[r.src_ip.str.match(r'^203\.0\.113\.[12]\d\d$')]
print('auth rows 203.0.113.100-255:',len(hi),'min/max last octet',hi.src_ip.str.rsplit('.',n=1).str[1].astype(int).agg(['min','max']).tolist())
x=r[(r.src_network=='ASN 64512')&(r.auth_method=='password')&(r.device=='new device')]
print('conj ASN64512+password+new device:',len(x),' of which low range:',x.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$').sum())
# per-address behaviour: hostile addresses are single-use; decoy addresses are re-used
g=r[r.src_network=='ASN 64512'].groupby('src_ip').size()
print('ASN 64512 addresses used exactly once or twice:',(g<=2).sum(),'of',len(g),'; of those in low range:',sum(int(i.rsplit('.',1)[1])<100 for i in g[g<=2].index))
ex=pd.read_csv(AUD+'account_logons_city_airstation.csv',dtype=str,keep_default_na=False)
print('extract: rows',len(ex),'ASN64512 rows',(ex.src_network=='ASN 64512').sum(),'low range',ex.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$').sum(), 'conj',((ex.src_network=='ASN 64512')&(ex.auth_method=='password')&(ex.device=='new device')).sum())
print(ex.src_network.value_counts().to_dict())
f=load('firewall')
for o in ORGS:
    x=f[(f.org==o)&f.src_ip.str.match(r'^203\.0\.113\.')]
    lo=x[x.src_ip.str.match(r'^203\.0\.113\.\d{1,2}$')]
    print(f' fw {o}: 203.0.113 rows {len(x)}, low-range {len(lo)}, low-range by rule {lo.rule_name.value_counts().to_dict()} action {lo.action.value_counts().to_dict()}')
print('\n===== ITEM 2: registry hosts outside site subnet / naming breaks')
R=reg()
for o in R['organisations']:
    sites={s['site_id']:s for s in o['sites']}
    bad=[]; nums=collections.defaultdict(list)
    for h in o['hosts']:
        s=sites.get(h['site_id'])
        if s and s.get('subnet') and h['ip'].startswith('10.'):
            if ipaddress.ip_address(h['ip']) not in ipaddress.ip_network(s['subnet']): bad.append((h['host_id'],h['ip'],s['subnet']))
        m=re.match(r'(.+-WS-)(\d+)$',h['host_id'])
        if m: nums[m.group(1)].append(int(m.group(2)))
    gaps={k:[n for n in v if n>max(len(v)+5,50)] for k,v in nums.items()}
    print(o['org_id'],'outside-subnet hosts:',len(bad),bad[:5],'| numbering outliers:',{k:v for k,v in gaps.items() if v}, '| sites w/o subnet', [s['site_id'] for s in o['sites'] if not s.get('subnet')])
# clickers' workstations
cl=pd.read_csv(AUD+'mail_url_clicks_city_airstation.csv',dtype=str)
for o in R['organisations']:
    if o['org_id'] not in('CITY','NASCC'): continue
    ip2h={h['ip']:h for h in o['hosts']}
    for _,c in cl.iterrows():
        h=ip2h.get(c.client_ip)
        if h: print('  click host',h['host_id'],h['ip'],h['site_id'],h['device_type'],'users',len(h.get('users',[])),c.mailbox.split('@')[0] in h.get('users',[]))
print('\n===== ITEM 4: vendor plan vs 198.51.100.44')
brw=[o for o in R['organisations'] if o['org_id']=='BRW'][0]; print(brw['address_plan'])
fb=f[f.org=='brw']; nat=fb.nat_src_ip[fb.nat_src_ip!='']
lasts=sorted(set(int(i.rsplit('.',1)[1]) for i in nat.unique()))
print('vendor nat_src last octets:',lasts[:5],'...',lasts[-5:],'count',len(lasts),' missing in 10..59:',[n for n in range(10,60) if n not in lasts], '198.51.100.44 rows:',(nat=='198.51.100.44').sum())
w=load('web',['brw']); print('vendor web rows to disasteraid:',w.host.str.contains('disasteraid').sum())
p=portal('aid_portal_access'); x=p[p.client_ip.str.startswith('198.51.100.')]
print('aid portal rows from 198.51.100.x by address:',x.client_ip.value_counts().to_dict())
print('aid portal labels for 198.51.100.x:',x.groupby('client_ip').client_network.first().to_dict())
vs=pd.read_csv(ROOT+'/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv',dtype=str,keep_default_na=False)
print('vessel sessions label by /24:',vs.groupby([vs.src_ip.str.rsplit('.',n=1).str[0],'src_asn']).size().to_dict())
v=vs[vs.src_ip.str.startswith('198.51.100.')]; v=v.assign(last=v.src_ip.str.rsplit('.',n=1).str[1].astype(int))
print(v.groupby('src_asn')['last'].agg(['min','max','count']).to_string())
print('auth labels 198.51.100.x:',r[r.src_ip.str.startswith('198.51.100.')].src_network.value_counts().to_dict())
