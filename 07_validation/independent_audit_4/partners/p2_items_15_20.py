# Pass 2 items 15, 18, 19, 20, and vendor <-> vessel sessions (canon item 22)
import sys,re,collections; sys.path.insert(0,'.')
from common import *
f=load('firewall'); w=load('web'); a=load('auth')
fb=f[f.org=='brw'].copy(); fb['te']=ts(fb).astype('int64')//10**9; fb['dur']=fb.duration_s.astype(float); fb['t0']=fb.te-fb.dur
print('===== ITEM 15')
e=fb[(fb.device=='BRW-FW-EDGE-01')&(fb.dst_ip=='192.0.2.70')]; print('edge sessions to gateway by port:',e.dst_port.value_counts().to_dict(),'app',e.app.value_counts().to_dict(), 'src zones',e.src_zone.value_counts().to_dict())
g=fb[fb.device=='BRW-FW-DMZ-01']
vs=pd.read_csv(ROOT+'/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv',dtype=str,keep_default_na=False)
vs['t0']=pd.to_datetime(vs.login_utc,utc=True).astype('int64')//10**9
vs['t1']=pd.to_datetime(vs.logout_utc.replace('',np.nan),utc=True).astype('int64')//10**9
gi=collections.defaultdict(list)
for s,t0,te,bs,br,d in zip(g.src_ip,g.t0,g.te,g.bytes_sent,g.bytes_recv,g.dur): gi[s].append((t0,te,int(bs),int(br),d))
ei=collections.defaultdict(list)
for s,nat,t0,te,dp in zip(e.src_ip,e.nat_src_ip,e.t0,e.te,e.dst_port): ei[nat].append((t0,te,s,dp))
rows=[]
for _,v in vs.iterrows():
    G=[x for x in gi.get(v.src_ip,[]) if abs(x[0]-v.t0)<=10]
    E=[x for x in ei.get(v.src_ip,[]) if abs(x[0]-v.t0)<=10]
    rows.append((v.session_id,v.vendor_account,v.src_ip,v.src_asn,v.login_utc,v.duration_s,v.result,v.access_level,v.vessel_name[:16],len(G),G[0][4] if G else None,(G[0][3] if G else None),v.bytes_out,len(E),E[0][2] if E else None))
T=pd.DataFrame(rows,columns=['sid','acct','src','asn','login','dur','result','lvl','vessel','gw_fw','gw_dur','gw_bytes_recv','bytes_out','edge_fw','inside_ip'])
pd.set_option('display.width',300); print(T.to_string())
print('vessel sessions without gateway fw session:',(T.gw_fw==0).sum(),'| 64512 sessions with vendor-side record:',((T.asn=='ASN 64512')&(T.edge_fw>0)).sum(),'| vendor sessions without vendor-side record:',((T.asn!='ASN 64512')&(T.edge_fw==0)).sum())
# gateway fw sessions >=300s without a vessel session row
vi=collections.defaultdict(list)
for s,t0 in zip(vs.src_ip,vs.t0): vi[s].append(t0)
long=g[g.dur>=300]; print('gateway fw sessions >=300 s:',len(long),'without vessel-session row:',sum(1 for s,t0 in zip(long.src_ip,long.t0) if not any(abs(t0-x)<=10 for x in vi.get(s,[]))))
print('gateway fw sessions by month, long vs short:'); print(pd.crosstab(g.time_utc.str[:7],g.dur>=300).to_string())
print('\n===== ITEM 18')
print('proto:',f.proto.value_counts().to_dict(),'dst ports:',f.dst_port.nunique(),'web statuses:',w.status.nunique())
fl=a[(a.logon_type=='remote')&(a.result=='FAILED')].copy(); fl['t']=ts(fl).astype('int64')//10**9
F=f.copy(); F['te']=ts(F).astype('int64')//10**9; F['dur']=F.duration_s.astype(float); F['t0']=F.te-F.dur
for o in ORGS:
    fo=F[(F.org==o)&(F.action=='allow')]; idx=collections.defaultdict(list)
    for s,t0,te,d in zip(fo.src_ip,fo.t0,fo.te,fo.dur): idx[s].append((t0,te,d))
    ds=[]
    for s,t in zip(fl[fl.org==o].src_ip,fl[fl.org==o].t):
        c=[x[2] for x in idx.get(s,[]) if x[0]-3<=t<=x[1]+3]
        if c: ds.append(c[0])
    ds=np.array(ds); print(o,'failed remote sign-on fw session durations: n',len(ds),'distinct',len(set(ds)),'p5/p50/p95',np.percentile(ds,[5,50,95]).round(1).tolist() if len(ds) else None)
print('\n===== ITEM 19 vpn')
for o in ORGS:
    fo=F[(F.org==o)]; v=fo[fo.src_zone=='vpn']; wv=w[(w.org==o)&w.client_ip.str.contains(r'^10\.\d+\.250\.')]
    rs=fo[fo.rule_name.str.contains('(?i)vpn')&(fo.action=='allow')]
    print(o,'fw rows from vpn zone',len(v),'web rows from vpn pool',len(wv),'distinct pool addrs',wv.client_ip.nunique(),'| inbound vpn sessions',len(rs),'dur p5/p50/p95',np.percentile(rs.dur,[5,50,95]).round(0).tolist() if len(rs) else None)
print('\n===== ITEM 20 vendor NAT pool')
wb=fb[(fb.device=='BRW-FW-EDGE-01')&(fb.nat_src_ip!='')&fb.src_ip.str.startswith('10.80.')]
per=wb.groupby('src_ip').nat_src_ip.agg(['nunique','size']); print(per.describe().T.to_string())
print('nat per src zone:',wb.groupby('src_zone').nat_src_ip.nunique().to_dict()); 
nn=wb.nat_src_ip.value_counts(); print('nat addrs',len(nn),'top',nn.head(4).to_dict(),'range of rest',nn.iloc[1:].min(),nn.iloc[1:].max())
x=wb.assign(last=wb.nat_src_ip.str.rsplit('.',n=1).str[1].astype(int)); print(pd.crosstab(pd.cut(x['last'],[0,9,59,129,199]),x.src_ip.str.split('.').str[2]).to_string())
