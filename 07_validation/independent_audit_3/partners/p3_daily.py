# daily / weekday / hourly patterns per org and stream subtype
from lib import *
from collections import Counter,defaultdict
from datetime import timedelta,datetime,timezone
import statistics as st, sys, json
def local(t):
    d=ts(t); off=5 if d<datetime(2027,11,7,7,tzinfo=timezone.utc) else 6
    return d-timedelta(hours=off)
series={}
def add(name,rows,pred=lambda r:True):
    c=Counter(); hh=Counter(); 
    for r in rows:
        if pred(r):
            l=local(r['time_utc']); c[l.strftime('%Y-%m-%d')]+=1; hh[(l.weekday()<5,l.hour)]+=1
    series[name]=(c,hh)
for o in ORGS:
    h,fw=load(o,'firewall')
    add(o+':fw_out',fw,lambda r:r['rule_name']=='outbound-web')
    add(o+':fw_deny',fw,lambda r:r['action']=='deny')
    add(o+':fw_in_remote',fw,lambda r:r['rule_name']=='inbound-remote-access')
    h,w=load(o,'web'); add(o+':web_user',w,lambda r:r['user']!='-'); add(o+':web_machine',w,lambda r:r['user']=='-')
    h,d=load(o,'dns'); add(o+':dns',d)
    h,a=load(o,'auth'); add(o+':auth_ws_4624',a,lambda r:r['event_id']=='4624'); add(o+':auth_remote',a,lambda r:r['logon_type']=='remote'); add(o+':auth_4625',a,lambda r:r['event_id']=='4625')
    h,m=load(o,'mail'); add(o+':mail_in',m,lambda r:r['direction']=='inbound'); add(o+':mail_internal',m,lambda r:r['direction']=='internal'); add(o+':mail_out',m,lambda r:r['direction']=='outbound')
    h,e=load(o,'endpoint_alerts'); add(o+':ep',e)
pickle.dump(series,open(HERE+'/cache/daily.pkl','wb'))
from datetime import date
def drange(a,b):
    d=date.fromisoformat(a)
    while d<=date.fromisoformat(b):
        yield d; d+=timedelta(days=1)
print('name | preWD preWE | D-3..D-1 | D0 | D1-D5 | D6-D13 wd | Oct wd | Nov wd | Dec wd | LaborDay(9/6) Thanksgiving(11/25) Xmas(12/25 Sat) 12/24 NewYear(1/1 Sat) 12/31 | hours(weekday share 8-17 local) night share(0-5)')
for name,(c,hh) in series.items():
    def m(a,b,wd=None):
        v=[c.get(d.isoformat(),0) for d in drange(a,b) if wd is None or (d.weekday()<5)==wd]
        return st.mean(v) if v else 0
    tot=sum(hh.values()) or 1; day=sum(v for (wd,h),v in hh.items() if 8<=h<17 and wd); night=sum(v for (wd,h),v in hh.items() if h<6)
    print(f"{name:22s} | {m('2027-07-19','2027-09-03',True):6.1f} {m('2027-07-17','2027-09-05',False):6.1f} | {m('2027-09-11','2027-09-13'):6.1f} | {c.get('2027-09-14',0):4d} | {m('2027-09-15','2027-09-19'):6.1f} | {m('2027-09-20','2027-09-27',True):6.1f} | {m('2027-10-04','2027-10-29',True):6.1f} | {m('2027-11-08','2027-11-19',True):6.1f} | {m('2027-12-06','2027-12-17',True):6.1f} | {c.get('2027-09-06',0)} {c.get('2027-11-25',0)} {c.get('2027-12-25',0)} {c.get('2027-12-24',0)} {c.get('2028-01-01',0)} {c.get('2027-12-31',0)} | {day/tot:.2f} {night/tot:.2f}")
