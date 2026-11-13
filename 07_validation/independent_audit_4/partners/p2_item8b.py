import sys,re,collections; sys.path.insert(0,'.')
from common import *
f=load('firewall',['nascc']); bl=portal('base_logistics_access'); ap=portal('aid_portal_access')
fn=f[(f.dst_ip=='162.40.88.22')].copy(); fn['te']=ts(fn).astype('int64')//10**9; fn['t0']=fn.te-fn.duration_s.astype(float)
ob=bl[bl.client_network!='base network'].copy(); ob['t']=ts(ob).astype('int64')//10**9
oi=collections.defaultdict(list)
for c,t in zip(ob.client_ip,ob.t): oi[c].append(t)
fn['matched']=[any(t0-3<=t<=te+3 for t in oi.get(s,[])) for s,t0,te in zip(fn.src_ip,fn.t0,fn.te)]
fn['br']=fn.bytes_recv.astype(int); fn['bs']=fn.bytes_sent.astype(int); fn['dur']=fn.duration_s.astype(float)
print(fn.groupby('matched')[['bs','br','dur']].describe().T.to_string())
print(fn.groupby('matched').session_end_reason.value_counts().to_string())
u=fn[~fn.matched]; print(u.src_ip.str.split('.').str[0].value_counts().head(12).to_dict()); print(u.head(8).drop(columns=['_file','org','device']).to_string())
print('unmatched per month',u.time_utc.str[:7].value_counts().sort_index().to_dict())
# same test at the other orgs: inbound allow to remote sign-on host vs auth rows
a=load('auth'); F=load('firewall')
R=reg()
for o in R['organisations']:
    k=o['org_id'].lower(); pub=o['remote_sign_on'].get('public_ip') if o.get('remote_sign_on') else None
    host=o['remote_sign_on']['host']
    hip={h['host_id']:h['ip'] for h in o['hosts']}
    dst=pub or hip.get(host)
    fo=F[(F.org==k)&(F.dst_ip==dst)&(F.action=='allow')].copy(); fo['te']=ts(fo).astype('int64')//10**9; fo['t0']=fo.te-fo.duration_s.astype(float)
    ao=a[(a.org==k)&(a.logon_type=='remote')].copy(); ao['t']=ts(ao).astype('int64')//10**9
    fi=collections.defaultdict(list)
    for s,t0,te in zip(fo.src_ip,fo.t0,fo.te): fi[s].append((t0,te))
    miss=sum(1 for c,t in zip(ao.src_ip,ao.t) if not any(x-3<=t<=y+3 for x,y in fi.get(c,[])))
    ai=collections.defaultdict(list)
    for c,t in zip(ao.src_ip,ao.t): ai[c].append(t)
    m2=sum(1 for s,t0,te in zip(fo.src_ip,fo.t0,fo.te) if not any(t0-3<=t<=te+3 for t in ai.get(s,[])))
    print(k,host,dst,'remote auth rows',len(ao),'without fw session',miss,'| fw sessions',len(fo),'without auth row',m2, '| fw dur p50',fo.duration_s.astype(float).median())
# vendor addresses in the aid portal log
x=ap[ap.client_ip.str.startswith('198.51.100.')]
print(x.groupby(['client_ip','client_network']).agg(n=('event','size'),first=('time_utc','min'),last=('time_utc','max'),ev=('event',lambda s:dict(s.value_counts()))).to_string())
fb=load('firewall',['brw']); nat=set(fb.nat_src_ip)-{''}
print('aid-portal 198.51.100 clients that are vendor NAT addresses:',sorted(set(x.client_ip)&nat), '| vendor own hosts .5/.6:',sorted(set(x.client_ip)&{'198.51.100.5','198.51.100.6'}))
y=bl[bl.client_ip.str.startswith('198.51.100.')]; print('logistics 198.51.100 clients:',y.client_ip.value_counts().to_dict(), 'vendor NAT overlap',sorted(set(y.client_ip)&nat))
