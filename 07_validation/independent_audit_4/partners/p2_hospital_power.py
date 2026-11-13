# Pass 2: hospital admin-wing activity during commercial-power loss; unlocks vs ED visits
import sys,re,collections; sys.path.insert(0,'.')
from common import *
R=reg()
hc=pd.read_csv(ROOT+'/05_other_sources/public_health/hospital_capacity.csv',dtype=str,keep_default_na=False)
for fid in ['FAC-SRMC-001','FAC-BCMC-002']:
    x=hc[hc.Facility_ID==fid]
    print(fid,'power source runs:'); 
    run=(x.Power_Source!=x.Power_Source.shift()).cumsum()
    print(x.groupby(run).agg(src=('Power_Source','first'),first=('Report_Date','min'),last=('Report_Date','max'),lost=('Commercial_Power_Lost_UTC','max'),rest=('Commercial_Power_Restored_UTC','max')).to_string())
a=load('auth'); w=load('web'); d=load('dns'); e=load('endpoint_alerts'); f=load('firewall')
for k,win in [('srmc',('2027-09-14T06:17:00Z','2027-09-22T14:14:00Z')),('bcmc',None)]:
    o=[o for o in R['organisations'] if o['org_id'].lower()==k][0]
    print(k,[ (s['site_id'],s['name'],s['kind'],s['backup_power'],s.get('subnet')) for s in o['sites']])
    h2s={h['host_id']:h['site_id'] for h in o['hosts']}; ip2s={h['ip']:h['site_id'] for h in o['hosts']}
    if win is None:
        x=hc[hc.Facility_ID=='FAC-BCMC-002']; lost=x.Commercial_Power_Lost_UTC[x.Commercial_Power_Lost_UTC!=''].min(); rest=x.Commercial_Power_Restored_UTC[x.Commercial_Power_Restored_UTC!=''].max(); win=(lost,rest); print(' bcmc window from capacity file',win)
    if not win[0] or str(win[0])=='nan': continue
    def inwin(x): return (x.time_utc>=win[0])&(x.time_utc<=win[1])
    for nm,df,col,mp in [('ws logon',a[(a.org==k)&(a.logon_type!='remote')],'host',h2s),('web',w[w.org==k],'client_ip',ip2s),('dns',d[d.org==k],'client_ip',ip2s),('endpoint',e[e.org==k],'host',h2s),('fw src',f[(f.org==k)&f.src_ip.str.startswith('10.')],'src_ip',ip2s)]:
        x=df[inwin(df)]; s=x[col].map(mp).fillna('vpn/other')
        print(' ',nm,'rows in power-loss window by site:',s.value_counts().to_dict())
        if nm in('ws logon','endpoint'):
            y=x[s=='ADM']; print('    ADM rows by day:',y.time_utc.str[5:10].value_counts().sort_index().to_dict())
            if nm=='endpoint': print('    ADM events:',y.event.value_counts().to_dict())
# unlocks vs ED visits
for k,fid in [('srmc','FAC-SRMC-001'),('bcmc','FAC-BCMC-002')]:
    ed=pd.read_csv(ROOT+f'/05_other_sources/public_health/ed_visits_{fid}.csv',dtype=str,keep_default_na=False)
    tcol=[c for c in ed.columns if 'time' in c.lower() or 'date' in c.lower() or 'utc' in c.lower()]
    print(k,'ed cols',ed.columns.tolist()[:12],len(ed))
    x=hc[hc.Facility_ID==fid].set_index('Report_Date').ED_Visits_24h.astype(float)
    u=a[(a.org==k)&(a.logon_type=='7')].copy(); t=ts(u); off=np.where(t<pd.Timestamp('2027-11-07T07:00:00Z'),5,6); u['ld']=(t-pd.to_timedelta(off,unit='h')).dt.strftime('%Y-%m-%d')
    un=u.groupby('ld').size()
    j=pd.concat([x,un],axis=1,keys=['ed','unlock']).dropna()
    print(' corr unlocks vs ED_Visits_24h:',round(j.ed.corr(j.unlock),3),'n',len(j))
    print(' pre-storm mean unlock/day',round(j.loc[:'2027-09-09'].unlock.mean(),1),'| 09-14..09-21',round(j.loc['2027-09-14':'2027-09-21'].unlock.mean(),1),'| 10-02..10-06',round(j.loc['2027-10-02':'2027-10-06'].unlock.mean(),1),'| Dec',round(j.loc['2027-12-01':'2027-12-31'].unlock.mean(),1))
    print(' ED: pre',round(j.loc[:'2027-09-09'].ed.mean(),1),'| 09-14..21',round(j.loc['2027-09-14':'2027-09-21'].ed.mean(),1),'| 10-02..06',round(j.loc['2027-10-02':'2027-10-06'].ed.mean(),1),'| Dec',round(j.loc['2027-12-01':'2027-12-31'].ed.mean(),1))
    print(' ratio unlock/ed: min',round((j.unlock/j.ed).min(),3),'max',round((j.unlock/j.ed).max(),3),'cv',round((j.unlock/j.ed).std()/(j.unlock/j.ed).mean(),3))
