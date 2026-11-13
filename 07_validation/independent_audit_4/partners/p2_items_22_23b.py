import sys,re,collections; sys.path.insert(0,'.')
from common import *
m=load('mail'); w=load('web'); a=load('auth')
pc=pd.read_csv(ROOT+'/05_other_sources/supply/port_conditions.csv',dtype=str,keep_default_na=False)
o=pc.groupby('order_id').agg(issued=('issued_utc','first'),typ=('order_type','first'),cond=('port_condition',lambda s:'|'.join(sorted(set(s)))[:50]),auth=('authority','first')).sort_values('issued')
pm=m[(m.org=='port')]
pm=pm.assign(oid=pm.subject.str.extract(r'^((?:MSIB|COTP ORDER) [\d-]+)')[0])
mm=pm.dropna(subset=['oid']).groupby('oid').agg(mail=('time_utc','min'),n=('time_utc','size'),sender=('sender','first'),subj=('subject','first'))
j=o.join(mm,how='outer'); j['lag_min']=((pd.to_datetime(j.mail)-pd.to_datetime(j.issued)).dt.total_seconds()/60).round(1)
pd.set_option('display.width',300); print(j.to_string())
print('authorities:',pc.authority.value_counts().to_dict())
print('port own notices (outbound/internal) with channel/port words:'); x=pm[(pm.direction!='inbound')&pm.subject.str.contains('(?i)port condition|channel|zulu|reopen|closure|terminal')]; print(x.subject.str.replace(r'\d+','N',regex=True).value_counts().head(10).to_string())
print('\n===== ITEM 23')
ea=pd.read_csv(ROOT+'/05_other_sources/public_health/eas_broadcasts.csv',dtype=str,keep_default_na=False)
print(ea.AlertSource.value_counts().to_dict())
g=w[w.host=='origination.alertgateway.example'].copy(); g['t']=ts(g)
ea['t']=pd.to_datetime(ea.IssuedAt_UTC,utc=True,errors='coerce')
print(g.groupby('org').agg(n=('t','size'),clients=('client_ip','nunique'),users=('user','nunique'),first=('time_utc','min'),last=('time_utc','max')).to_string())
print('requests per month:',pd.crosstab(g.time_utc.str[:7],g.org).to_dict())
rows=[]
for _,e in ea.iterrows():
    near=g[(g.t>=e.t-pd.Timedelta('15min'))&(g.t<=e.t+pd.Timedelta('5min'))]
    rows.append((e.AlertID,e.EventCode,e.IssuedAt_UTC,e.AlertSource[:40],len(near),','.join(sorted(set(near.org))),','.join(near.user.unique()[:3]),','.join((near.t-e.t).dt.total_seconds().round().astype(int).astype(str))))
T=pd.DataFrame(rows,columns=['id','code','issued','source','n_req','orgs','users','offset_s']); print(T.to_string())
# requests not near any alert
iss=ea.t.dropna().values
far=[t for t in g.t if not any(abs((t-pd.Timestamp(i,tz='UTC')).total_seconds())<=900 for i in iss)]
print('alert-gateway requests:',len(g),'not within 15 min of an alert:',len(far))
# operator logged on at the time?
ws=a[(a.logon_type!='remote')].copy(); ws['t']=ts(ws)
R=reg(); ip2h={h['ip']:h['host_id'] for o_ in R['organisations'] for h in o_['hosts']}
bad=0
for _,r in g.iterrows():
    h=ip2h.get(r.client_ip); x=ws[(ws.host==h)&(ws.account==r.user)&(ws.t<=r.t)]
    if not len(x) or x.iloc[-1].event_id not in('4624',): bad+=1
print('alert requests whose user has no open logon on that host:',bad,'of',len(g))
print(g.groupby(['org','client_ip']).size().to_string())
