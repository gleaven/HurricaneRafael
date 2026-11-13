# Pass 2 items 11, 12 + Pass 3 time patterns for auth
import sys,re,collections; sys.path.insert(0,'.')
from common import *
a=load('auth'); t=ts(a); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); a['ltm']=t-pd.to_timedelta(off,unit='h')
a['ld']=a.ltm.dt.strftime('%Y-%m-%d'); a['lh']=a.ltm.dt.hour; a['dow']=a.ltm.dt.dayofweek
r=a[a.logon_type=='remote']; ws=a[a.logon_type!='remote']
print('===== ITEM 11 remote sign-ons by calendar')
hol=['2027-09-06','2027-10-11','2027-11-11','2027-11-25','2027-11-26','2027-12-24','2027-12-25','2027-12-31','2028-01-01']
d=r.groupby(['ld','org']).size().unstack(fill_value=0); d.index=pd.to_datetime(d.index); dd=d.iloc[1:-1]
wk=dd[dd.index.dayofweek<5]; we=dd[dd.index.dayofweek>=5]
print('weekday mean:',wk.mean().round(1).to_dict()); print('weekend mean:',we.mean().round(1).to_dict())
print('holidays:'); print(d.loc[d.index.isin(pd.to_datetime(hol))].to_string())
print('storm window:'); print(d.loc['2027-09-09':'2027-09-22'].to_string())
print('remote hour-of-day % (local):'); print((pd.crosstab(r.lh,r.org,normalize='columns')*100).round(1).to_string())
print('\n===== ITEM 12 workstation sessions')
print('ws 4624 hour-of-day % (local), logon_type 2:'); x=ws[(ws.event_id=='4624')&(ws.logon_type=='2')]; print((pd.crosstab(x.lh,x.org,normalize='columns')*100).round(1).to_string())
# session lengths: pair 4624 with next 4634 same host+account
w2=ws[ws.logon_type=='2'].sort_values('time_utc'); w2['tt']=ts(w2).astype('int64')//10**9
res=collections.defaultdict(list); nolo=collections.Counter(); open_={}
for o,h,ac,ev,tt in zip(w2.org,w2.host,w2.account,w2.event_id,w2.tt):
    k=(o,h,ac)
    if ev=='4624':
        if k in open_: nolo[o]+=1
        open_[k]=tt
    elif ev=='4634' and k in open_:
        res[o].append(tt-open_.pop(k))
for o in ORGS:
    v=np.array(res[o])/3600
    print(o,'sessions',len(v),'len h p5/p25/p50/p75/p95',np.percentile(v,[5,25,50,75,95]).round(1).tolist(),'<1h share',round((v<1).mean(),3),'logons without logoff',nolo[o])
# failed logon followed by success within 3 min
for o in ORGS:
    x=ws[(ws.org==o)].sort_values('time_utc'); x=x.assign(tt=ts(x).astype('int64')//10**9)
    fails=x[x.event_id=='4625']; succ=x[x.event_id=='4624']
    si=collections.defaultdict(list)
    for h,ac,tt in zip(succ.host,succ.account,succ.tt): si[(h,ac)].append(tt)
    gaps=[]
    for h,ac,tt in zip(fails.host,fails.account,fails.tt):
        nx=[s for s in si.get((h,ac),[]) if s>=tt]
        gaps.append(min(nx)-tt if nx else np.inf)
    gaps=np.array(gaps)
    print(o,'ws failures',len(gaps),'followed by success <=180s',round((gaps<=180).mean(),3),'<=1h',round((gaps<=3600).mean(),3),'never',int(np.isinf(gaps).sum()), 'consecutive-failure runs>=3:',)
# remote: failures followed by success
for o in ORGS:
    x=r[r.org==o].sort_values('time_utc'); x=x.assign(tt=ts(x).astype('int64')//10**9)
    fl=x[x.result=='FAILED']; sc=x[x.result=='SUCCESS']
    si=collections.defaultdict(list)
    for ac,tt in zip(sc.account,sc.tt): si[ac].append(tt)
    g=np.array([min([s-tt for s in si.get(ac,[]) if s>=tt] or [np.inf]) for ac,tt in zip(fl.account,fl.tt)])
    print(o,'remote failures',len(g),'success <=180s',round((g<=180).mean(),3),'never',int(np.isinf(g).sum()))
# deny sources unique?
f=load('firewall'); dn=f[f.action=='deny']
for o in ORGS:
    v=dn[dn.org==o].src_ip.value_counts(); print(o,'deny rows',v.sum(),'distinct src',len(v),'max per src',v.max(),'src seen>=2',(v>=2).sum())
# lock/unlock type 7 at hospitals
print('logon_type 7 by event:',a[a.logon_type=='7'].groupby(['org','event_id']).size().to_dict())
