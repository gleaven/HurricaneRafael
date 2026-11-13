# Pass 1 trick 6: BRW remote-maintenance gateway firewall: long sessions by source network
import sys; sys.path.insert(0,'.')
from common import *
f=load('firewall',['brw']); x=f[f.device=='BRW-FW-DMZ-01'].copy()
x['dur']=x.duration_s.astype(float); x['br']=x.bytes_recv.astype(int); x['bs']=x.bytes_sent.astype(int)
x['p24']=x.src_ip.str.rsplit('.',n=1).str[0]
L=x[x.dur>=300]
print('sessions >=300s:',len(L)); print(L.p24.value_counts().to_string())
print(L[L.p24!='198.51.100'].drop(columns=['_file','org','device','action','nat_src_ip','rule_name','src_zone','dst_zone','duration_s','bytes_sent','bytes_recv']).to_string())
S=x[x.p24.isin(['203.0.113','192.0.2'])]
print(S.groupby('src_ip').agg(n=('dur','size'),mx=('dur','max'),first=('time_utc','min'),last=('time_utc','max'),br=('br','sum')).to_string())
# byte ratio regularity
L=L.assign(ratio=L.br/L.bs, rate=L.br/L.dur)
print(L.groupby(L.p24=='198.51.100')[['ratio','rate','dur']].describe().T.to_string())
# hours of long sessions
L=L.assign(t=ts(L)); L['start']=L.t-pd.to_timedelta(L.dur,unit='s')
print(pd.crosstab(L.start.dt.hour,L.p24=='198.51.100').T.to_string())
print(pd.crosstab(L.start.dt.dayofweek,L.p24=='198.51.100').T.to_string())
print(L.groupby(L.time_utc.str[:7]).size())
