import csv
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta,date
PC=list(csv.DictReader(open(ROOT+'/05_other_sources/supply/port_conditions.csv')))
orders={}
for r in PC: orders.setdefault(r['order_id'],r)
hm,m=load('port','mail')
cg=[r for r in m if r['sender_domain']=='uscg-sector-cc.example' or r['subject'].split(':')[0] in orders]
print('distinct orders',len(orders),'CG mails',len(cg), 'authorities',Counter(r['authority'] for r in orders.values()))
for oid,r in orders.items():
    mm=[x for x in cg if x['subject'].startswith(oid+':')]
    lag=[(ts(x['time_utc'])-ts(r['issued_utc'])).total_seconds() for x in mm]
    flag='' if mm and all(0<=l<=600 for l in lag) else '  <<<'
    print(f"  {oid:20s} issued {r['issued_utc']} {r['order_type']:16s} {r['port_condition'][:22]:22s} mails {len(mm)} lag_s {lag} {[ (x['recipient'],x['subject'][-18:]) for x in mm][:1]}{flag}")
print(' CG mails not matching an order:',[(x['time_utc'],x['subject'],x['sender']) for x in cg if x['subject'].split(':')[0] not in orders])
# gate office activity by period
R=reg(); P=[o for o in R['organisations'] if o['org_id']=='PORT'][0]
gate=[h for h in P['hosts'] if h['site_id']=='GATE' and h['device_type'] in('workstation','console')]
gid={h['host_id'] for h in gate}
ha,a=load('port','auth')
days=Counter()
for r in a:
    if r['host'] in gid and r['event_id']=='4624': days[(ts(r['time_utc'])-timedelta(hours=5)).date()]+=1
def mean(a_,b_):
    d=date.fromisoformat(a_); tot=0;n=0
    while d<=date.fromisoformat(b_):
        tot+=days.get(d,0); n+=1; d+=timedelta(days=1)
    return tot/n
print('gate hosts',len(gate),'logons/day: pre(7/19-9/10) %.1f | 9/11 %d 9/12 %d 9/13 %d 9/14 %d | D0-D3 %.1f | D4..D29 (9/18-10/13) %.1f | D30-D43 (10/14-10/27) %.1f | D44-D57 (10/28-11/10) %.1f | D58+ (11/11-12/17) %.1f'%(mean('2027-07-19','2027-09-10'),days.get(date(2027,9,11),0),days.get(date(2027,9,12),0),days.get(date(2027,9,13),0),days.get(date(2027,9,14),0),mean('2027-09-14','2027-09-17'),mean('2027-09-18','2027-10-13'),mean('2027-10-14','2027-10-27'),mean('2027-10-28','2027-11-10'),mean('2027-11-11','2027-12-17')))
gl=sorted(r['time_utc'] for r in a if r['host'] in gid and '2027-09-13'<=r['time_utc'][:10]<='2027-09-18')
print(' gate auth events 9/13..9/18 UTC: last before gap / first after:',[(gl[i],gl[i+1]) for i in range(len(gl)-1) if (ts(gl[i+1])-ts(gl[i])).total_seconds()>6*3600])
# hospitals
HC=list(csv.DictReader(open(ROOT+'/05_other_sources/public_health/hospital_capacity.csv')))
for fac,o in [('FAC-SRMC-001','srmc'),('FAC-BCMC-002','bcmc')]:
    rows=[r for r in HC if r['Facility_ID']==fac]
    pw=sorted({(r['Commercial_Power_Lost_UTC'],r['Generator_Start_UTC'],r['Commercial_Power_Restored_UTC']) for r in rows if r['Commercial_Power_Lost_UTC'] or r['Generator_Start_UTC'] or r['Commercial_Power_Restored_UTC']})
    print(o,'capacity power fields',pw[:6], 'Power_Source by date',[(r['Report_Date'],r['Power_Source']) for r in rows if '2027-09-12'<=r['Report_Date']<='2027-09-24'])
    ha,a=load(o,'auth'); he,e=load(o,'endpoint_alerts'); hw,w=load(o,'web')
    O=[x for x in R['organisations'] if x['org_id']==o.upper()][0]
    site={h['host_id']:h['site_id'] for h in O['hosts']}; ipsite={h['ip']:h['site_id'] for h in O['hosts']}
    for s in ['CLIN','ADM']:
        ev=sorted(r['time_utc'] for r in a if site.get(r['host'])==s and '2027-09-13T12'<=r['time_utc']<='2027-09-23')
        gaps=[(ev[i],ev[i+1],round((ts(ev[i+1])-ts(ev[i])).total_seconds()/60)) for i in range(len(ev)-1) if (ts(ev[i+1])-ts(ev[i])).total_seconds()>20*60 and s=='CLIN' or (ts(ev[i+1])-ts(ev[i])).total_seconds()>6*3600]
        print('  ',s,'auth gaps',gaps[:6])
        wv=sorted(r['time_utc'] for r in w if ipsite.get(r['client_ip'])==s and '2027-09-13T12'<=r['time_utc']<='2027-09-23')
        gaps=[(wv[i],wv[i+1]) for i in range(len(wv)-1) if (ts(wv[i+1])-ts(wv[i])).total_seconds()>4*3600]
        print('  ',s,'web gaps>4h',gaps[:5])
    hb=[r for r in e if r['event']=='AGENT_HEARTBEAT_MISSED' and '2027-09-13'<=r['time_utc'][:10]<='2027-09-23']
    print('   heartbeat missed 9/13-9/23:',len(hb),'first',hb[0]['time_utc'] if hb else None,'last',hb[-1]['time_utc'] if hb else None,'details',Counter(bool(r['detail']) for r in hb),'by site',Counter(site[r['host']] for r in hb),'last-seen range',min((r['detail'] for r in hb if r['detail']),default=None),max((r['detail'] for r in hb if r['detail']),default=None))
    # logoffs at power loss? (guide: no logoff when power lost)
    # ED visits vs unlocks
    try:
        ED=list(csv.DictReader(open(ROOT+f'/05_other_sources/public_health/ed_visits_{fac}.csv')))
        print('   ed cols',list(ED[0].keys())[:12])
        tcol=[c for c in ED[0] if 'utc' in c.lower() or 'time' in c.lower() or 'arriv' in c.lower()][0]
        edd=Counter(r[tcol][:10] for r in ED)
        un=Counter(r['time_utc'][:10] for r in a if r['logon_type']=='7')
        ds=sorted(set(edd)&set(un))
        import numpy as np
        x=np.array([edd[d] for d in ds]);y=np.array([un[d] for d in ds])
        print('   ED visits/day vs type-7 unlocks/day: n days',len(ds),'corr %.3f'%np.corrcoef(x,y)[0,1],'ratio unlock/visit mean %.3f sd %.3f'%((y/x).mean(),(y/x).std()),'ed span',min(edd),max(edd),'tcol',tcol)
        print('   sample days',[(d,edd[d],un[d]) for d in ['2027-08-20','2027-09-13','2027-09-14','2027-09-15','2027-09-16','2027-09-22','2027-10-02','2027-12-01'] if d in edd])
    except Exception as ex: print('   ed err',ex)
