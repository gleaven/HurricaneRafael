from common import *
rs=load('telemetry/vessel_cargo_control_remote_sessions.csv')
h=[r for r in rs if '64512' in r['src_asn']]; b=[r for r in rs if r not in h]
num=lambda r:int(r['session_id'].split('-')[-1])
print('hostile ids',sorted(num(r) for r in h)); print('benign ids',sorted(num(r) for r in b))
print('hostile login sec==00',sum(r['login_utc'][-3:-1]=='00' for r in h),len(h),'benign',sum(r['login_utc'][-3:-1]=='00' for r in b),len(b))
print('hostile dur%60==0',sum(int(r['duration_s'])%60==0 and int(r['duration_s'])>0 for r in h),'benign',sum(int(r['duration_s'])%60==0 and int(r['duration_s'])>0 for r in b))
print('ticket empty hostile',sum(r['ticket_ref']=='' for r in h),'benign',sum(r['ticket_ref']=='' for r in b), 'benign success no ticket', sum(r['ticket_ref']=='' and r['result']=='SUCCESS' and r['target_system']!='' for r in b), 'benign success w/ target', sum(r['result']=='SUCCESS' and r['target_system']!='' for r in b))
import collections
print(collections.Counter((r['access_level'],'H' if r in h else 'B') for r in rs))
print('order by time ids monotonic?', [num(r) for r in sorted(rs,key=lambda r:r['login_utc'])][:40])
print('local hours hostile',sorted(local(ts(r['login_utc'])).hour for r in h)); print('benign',sorted(local(ts(r['login_utc'])).hour for r in b))
