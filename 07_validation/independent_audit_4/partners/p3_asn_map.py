# Pass 3: is "ASN <n>" a consistent function of the address across delivered streams?
import sys,re,collections,glob; sys.path.insert(0,'.')
from common import *
src=[]
a=load('auth'); r=a[a.logon_type=='remote']; src.append(('partner auth',r.src_ip,r.src_network))
for n in ['aid_portal_access','base_logistics_access']:
    p=portal(n); p=p[p.client_network.str.startswith('ASN')]; src.append((n,p.client_ip,p.client_network))
vs=pd.read_csv(ROOT+'/05_other_sources/telemetry/vessel_cargo_control_remote_sessions.csv',dtype=str,keep_default_na=False); src.append(('vessel sessions',vs.src_ip,vs.src_asn))
ap=pd.read_csv(ROOT+'/05_other_sources/payments/aid_applications.csv',dtype=str,keep_default_na=False,usecols=['source_ip','source_asn']); ap=ap[ap.source_ip!='']; src.append(('aid applications',ap.source_ip,'ASN '+ap.source_asn))
AUD=ROOT+'/05_other_sources/network_logs/audit/'
for fn in ['remote_access_sessions.csv','employee_vpn_sessions.csv']:
    x=pd.read_csv(AUD+fn,dtype=str,keep_default_na=False); ipc=[c for c in x.columns if 'ip' in c.lower()]; ac=[c for c in x.columns if 'asn' in c.lower() or 'network' in c.lower()]
    print(fn,x.columns.tolist())
    if ipc and ac: src.append((fn,x[ipc[0]],x[ac[0]].map(lambda v: v if str(v).startswith('ASN') else 'ASN '+str(v))))
rows=[]
for nm,ip,asn in src:
    df=pd.DataFrame({'ip':ip.values,'asn':asn.values}); df=df[df.ip.str.match(r'^\d+\.\d+\.\d+\.\d+$')]
    df['p8']=df.ip.str.split('.').str[0]; df['p24']=df.ip.str.rsplit('.',n=1).str[0]
    df['key']=np.where(df.p8.isin(['192','198','203']),df.p24,df.p8+'.x')
    g=df.groupby('key').asn.agg(lambda s:','.join(sorted(set(s))))
    for k,v in g.items(): rows.append((k,nm,v))
T=pd.DataFrame(rows,columns=['prefix','stream','asns']).pivot(index='prefix',columns='stream',values='asns').fillna('')
pd.set_option('display.width',400); pd.set_option('display.max_colwidth',60); print(T.to_string())
# per-ASN prefix sets per stream
for nm,ip,asn in src:
    df=pd.DataFrame({'ip':ip.values,'asn':asn.values}); df=df[df.ip.str.match(r'^\d+\.\d+\.\d+\.\d+$')]
    print(nm, df.groupby('asn').ip.apply(lambda s:','.join(sorted(set(x.split('.')[0] for x in s)))).to_dict())
